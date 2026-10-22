#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 词对实验 v2（多生成模型 + 双评委 + 断点续跑）
================================================================
生成模型（每个模型独立跑完整网格）：
  - stepfun-ai/step-5-preview
  - deepseek-ai/deepseek-v4.1-flash
  - z-ai/glm-5.3
  - z-ai/glm-5.3-flash

评委（各做一次完整评审；内部 A/B 双顺序以抵消位置偏差）：
  - deepseek-ai/deepseek-v4.1-flash
  - z-ai/glm-5.3

每个生成模型：
  阶段 0：6 任务 x 2 条件(baseline / word_pairs) x N_RUNS
  阶段 1：清洗 word_pairs 输出；严格去除词对列表和编号引用，残留会标记
  阶段 2：每个评委对 baseline vs cleaned 做盲评；A/B 双顺序

结果目录：
  llm_experiment_results_v2/<model>/results.jsonl
  llm_experiment_results_v2/<model>/cleaned.jsonl
  llm_experiment_results_v2/<model>/comparison__<judge>.jsonl
  llm_experiment_results_v2/<model>/... markdown
  llm_experiment_results_v2/summary*.json / SUMMARY.md

关键修复（相对 notebook22d6286ede）：
  - clone 后显式设置 git identity；commit 失败立即抛错，不再“假完成”
  - 只 git add 结果白名单；提交前扫描密钥；token 用 http.extraheader，不写进 remote URL
  - 清洗 prompt 去除词对编号/“从上面词对中”等残留；正则校验 + 二次清洗
  - 每个评委对每对做 A/B 双顺序；记录 swap 和 A/B 来源
  - 每条记录带 run_id/timestamp/model/temperature/prompt_version
  - 全局时间预算 + 每条 checkpoint + 断点续跑
  - 单个模型连续失败会熔断，避免一个坏模型烧完全部时间

环境变量（Kaggle Secrets 可覆盖；代码内默认值仅用于私有 Kaggle 运行）：
  OPENAI_API_KEY / OPENAI_BASE_URL
  GEN_MODELS / JUDGE_MODELS（逗号分隔）
  N_RUNS / CONCURRENCY / COUNTERBALANCE
  TIME_BUDGET_MIN / MAX_RETRIES / PER_CALL_TIMEOUT
  GITEE_TOKEN / GITEE_USER / GIT_REMOTE_URL / GIT_BRANCH
  GIT_PUSH_INTERVAL / GIT_COMMIT_EVERY
  DRY_RUN / SKIP_SYNC
"""

import asyncio
import base64
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from openai import AsyncOpenAI
except ImportError:
    print("[环境] 未检测到 openai 包，自动安装 …", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "openai"],
                   check=False, timeout=900)
    from openai import AsyncOpenAI


# ============ 运行环境与配置 ============
IS_KAGGLE = bool(
    os.environ.get("KAGGLE_KERNEL_RUN_TYPE")
    or os.environ.get("KAGGLE_URL_BASE")
    or os.environ.get("KAGGLE_CONTAINER_ID")
    or Path("/kaggle/working").exists()
)


def _get_env(name, default=None):
    val = os.environ.get(name)
    if val:
        return val
    if IS_KAGGLE:
        try:
            from kaggle_secrets import UserSecretsClient  # type: ignore
            s = UserSecretsClient().get_secret(name)
            if s:
                return s
        except Exception:
            pass
    return default


# 这两个占位符在 Gitee 归档版中替换为空字符串；Kaggle 私有运行版注入真实值。
GITEE_TOKEN = _get_env("GITEE_TOKEN", "")
API_KEY = _get_env("OPENAI_API_KEY", "")
BASE_URL = _get_env("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")

GITEE_USER = _get_env("GITEE_USER", "qwe12345678")
GIT_REMOTE_URL = _get_env("GIT_REMOTE_URL", "https://gitee.com/qwe12345678/jkdsfn.git")
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")

GEN_MODELS = [
    x.strip() for x in _get_env(
        "GEN_MODELS",
        "stepfun-ai/step-5-preview,deepseek-ai/deepseek-v4.1-flash,"
        "z-ai/glm-5.3,z-ai/glm-5.3-flash",
    ).split(",") if x.strip()
]
JUDGE_MODELS = [
    x.strip() for x in _get_env(
        "JUDGE_MODELS",
        "deepseek-ai/deepseek-v4.1-flash,z-ai/glm-5.3",
    ).split(",") if x.strip()
]

N_RUNS = int(os.environ.get("N_RUNS", "10"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "10"))
COUNTERBALANCE = os.environ.get("COUNTERBALANCE", "0").lower() not in ("0", "false", "no")
TEMPERATURE_GEN = float(os.environ.get("TEMPERATURE_GEN", "0.6"))
TEMPERATURE_JUDGE = float(os.environ.get("TEMPERATURE_JUDGE", "0.3"))
MAX_TOKENS_GEN = int(os.environ.get("MAX_TOKENS_GEN", "16384"))
MAX_TOKENS_CLEAN = int(os.environ.get("MAX_TOKENS_CLEAN", "16384"))
MAX_TOKENS_JUDGE = int(os.environ.get("MAX_TOKENS_JUDGE", "16384"))
PER_CALL_TIMEOUT = int(os.environ.get("PER_CALL_TIMEOUT", "1200"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
MODEL_FAILURE_LIMIT = int(os.environ.get("MODEL_FAILURE_LIMIT", "5"))
TIME_BUDGET_MIN = float(os.environ.get("TIME_BUDGET_MIN", "660"))
GIT_COMMIT_EVERY = int(os.environ.get("GIT_COMMIT_EVERY", "5"))
GIT_PUSH_INTERVAL = int(os.environ.get("GIT_PUSH_INTERVAL", "20"))
DRY_RUN = os.environ.get("DRY_RUN", "").lower() not in ("", "0", "false", "no")
SKIP_SYNC = os.environ.get("SKIP_SYNC", "").lower() not in ("", "0", "false", "no")

RUN_ID = os.environ.get("RUN_ID") or datetime.now(timezone.utc).strftime("v2-%Y%m%dT%H%M%SZ")
SEED = int(os.environ.get("SEED", "20261022"))
PROMPT_VERSION = "v2"

WORK_DIR = Path(os.environ.get("WORK_DIR", "/kaggle/working" if IS_KAGGLE else "."))
REPO_DIR = Path(os.environ.get("REPO_DIR", str(WORK_DIR / "jkdsfn_repo")))
RESULTS_ROOT = REPO_DIR / "llm_experiment_results_v2"

TASKS_BY_ID = {
    1: {"id": 1, "name": "函数式编程语言", "prompt": "设计一个全新的函数式编程语言"},
    2: {"id": 2, "name": "提升LLM性能", "prompt": "怎么低成本不需要额外训练大幅提升现有LLM的性能"},
    3: {"id": 3, "name": "CLI工具Idea", "prompt": "给出适合独立开发者开发CLI工具的一个Idea"},
    4: {"id": 4, "name": "新理论", "prompt": "提出一个新的理论"},
    5: {"id": 5, "name": "人格模型", "prompt": "提出一个新的类似于九型和荣格八维的模型"},
    6: {"id": 6, "name": "ML架构", "prompt": "提出一个新的机器学习架构"},
}
PREFIX = "在回答前面输出200组词，每组有两个词，从这些词获得灵感"
CONDITIONS = ("baseline", "word_pairs")
DIMS = ("logic", "concreteness", "actionability", "originality", "overall")

CLEAN_PROMPT = """下面是一段 LLM 的输出。开头是 200 组词对，之后才是正文。
请删除开头的词对列表，并删除/改写正文中所有依赖该词表的表述：

- 删除“从上面词对中 / 从这些词中 / 上述词 / 这些词中”等引导语；
- 删除“第 N 组 / 词组 N / 词对 N”等编号引用；
- 如果删除引用后句子不通顺，把它改写为不依赖外部词表的自然表述；
- 保留正文的技术内容、结构、结论和代码，不要新增事实；
- 不要输出前言、后记、解释或 markdown 代码块标记。

只输出清洗后的正文。

=== 原文开始 ===
{content}
=== 原文结束 ==="""

CLEAN_PROMPT_STRICT = CLEAN_PROMPT + """

注意：上一次清洗仍残留词对引用。这次必须彻底删除所有
“第 N 组 / 词组 N / 词对 N / 从上面词对中 / 这些词中”等字样，
必要时改写句子；不要保留任何对不可见词表的指代。"""

COMPARE_PROMPT = """你是一位严谨、公正的评审专家。下面有两篇针对同一任务的回答（A 和 B）。
两篇回答都可能引用了一组未展示给您的“灵感词”；这种引用本身不应作为扣分理由，
请只评价回答的内容质量。

请从以下 5 个维度分别打分，每项 1-10 分（整数）：
- logic:          逻辑性与结构
- concreteness:   具体性与细节
- actionability:  可操作性
- originality:    原创性
- overall:        整体质量

然后给出最终结论，winner 必须是以下之一："A"、"B"、"tie"。
只输出一个 JSON 对象，不要任何多余文字、不要 markdown 代码块。格式：
{{"A": {{"logic": 0, "concreteness": 0, "actionability": 0, "originality": 0, "overall": 0}}, "B": {{"logic": 0, "concreteness": 0, "actionability": 0, "originality": 0, "overall": 0}}, "winner": "A", "reason": "..."}}

任务：{task}

=== 回答 A ===
{answer_a}

=== 回答 B ===
{answer_b}"""

RESIDUAL_RE = re.compile(
    r"(第\s*\d+\s*组|词组\s*\d+|词对\s*\d+|从上面|上面的词|上述词|"
    r"这些词中|从这些词|200\s*组)"
)


# ============ 通用工具 ============
_write_lock = threading.Lock()
_checkpoint_lock = None  # 在事件循环内初始化
_checkpoint_count = 0
_deadline = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str) -> str:
    return s.replace("/", "__").replace(":", "_").replace(" ", "_")


def _model_dir(model: str) -> Path:
    return RESULTS_ROOT / _slug(model)


def _judge_path(model: str, judge: str) -> Path:
    return _model_dir(model) / f"comparison__{_slug(judge)}.jsonl"


def _base_record(model: str, **kw):
    rec = {
        "schema_version": 2,
        "run_id": RUN_ID,
        "timestamp": _now(),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "seed": SEED,
    }
    rec.update(kw)
    return rec


def _append_jsonl(path: Path, rec: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


def _load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception as e:
            print(f"  [警告] 解析 {path.name} 某行失败: {e}", flush=True)
    return out


def _is_error_text(t):
    return not t or str(t).strip().startswith("[ERROR]")


def _valid_result(r) -> bool:
    return not _is_error_text(r.get("content"))


def _valid_cleaned(r) -> bool:
    return not _is_error_text(r.get("cleaned_content"))


def _valid_scores(s) -> bool:
    if not isinstance(s, dict):
        return False
    for d in DIMS:
        v = s.get(d)
        if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 10):
            return False
    return True


def _valid_comparison(r) -> bool:
    if r.get("winner_label") not in ("baseline", "cleaned_word_pairs", "tie"):
        return False
    return _valid_scores(r.get("A_scores")) and _valid_scores(r.get("B_scores"))


def _latest_valid(records: list, keys: tuple, valid_fn) -> dict:
    out = {}
    for r in records:
        key = tuple(r.get(k) for k in keys)
        if any(x is None for x in key):
            continue
        if not valid_fn(r):
            continue
        out[key] = r
    return out


def _check_deadline():
    if _deadline is not None and time.monotonic() > _deadline:
        raise TimeBudgetExceeded()


class TimeBudgetExceeded(Exception):
    pass


def _raise_stage_errors(results, stage: str):
    for r in results:
        if isinstance(r, TimeBudgetExceeded):
            continue
        if isinstance(r, BaseException):
            raise RuntimeError(f"{stage} 有任务异常: {type(r).__name__}: {r}")


# ============ Git（白名单 + extraheader + 密钥扫描） ============
SECRET_RE = re.compile(
    r"(KGAT_[0-9a-f]{32}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)"
)


def _git_auth_args():
    if not GITEE_TOKEN:
        return []
    raw = f"{GITEE_USER}:{GITEE_TOKEN}".encode()
    auth = base64.b64encode(raw).decode()
    return ["-c", f"http.extraheader=Authorization: Basic {auth}"]


def _redact(s: str) -> str:
    s = s or ""
    s = re.sub(r"(https?://)[^/\s]+:[^@\s]+@", r"\1***@", s)
    for secret in (GITEE_TOKEN, API_KEY):
        if secret:
            s = s.replace(secret, "***")
    return s


def _run_git(args, cwd=None, timeout=300):
    cmd = [
        "git",
        "-c", "http.lowSpeedLimit=1000",
        "-c", "http.lowSpeedTime=60",
    ] + _git_auth_args() + args
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "echo",
    }
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("  [警告] 未找到 git 命令", flush=True)
        return None
    except subprocess.TimeoutExpired:
        print(f"  [警告] git {' '.join(args)} 超时", flush=True)
        return None
    except Exception as e:
        print(f"  [警告] git 执行异常: {e}", flush=True)
        return None


def _ensure_repo():
    REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
    if (REPO_DIR / ".git").exists():
        _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=REPO_DIR)
        p = _run_git(["pull", "--rebase", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
        if p and p.returncode != 0:
            print(f"  [警告] pull --rebase 失败：{_redact(p.stderr)[:300]}", flush=True)
            _run_git(["rebase", "--abort"], cwd=REPO_DIR)
    else:
        if REPO_DIR.exists() and any(REPO_DIR.iterdir()):
            print("  [Git] 目录非空但不是仓库，改用 init + fetch", flush=True)
            _run_git(["init"], cwd=REPO_DIR)
        else:
            clone = _run_git(
                ["clone", "--branch", GIT_BRANCH, GIT_REMOTE_URL, str(REPO_DIR)],
                cwd=REPO_DIR.parent, timeout=900,
            )
            if not (clone and clone.returncode == 0):
                err = _redact(clone.stderr if clone else "unknown")
                print(f"  [Git] clone 失败（{err[:300]}），改用 init + fetch", flush=True)
                REPO_DIR.mkdir(parents=True, exist_ok=True)
                _run_git(["init"], cwd=REPO_DIR)
            else:
                print(f"  [Git] clone 成功 -> {REPO_DIR}", flush=True)
        _run_git(["remote", "remove", "origin"], cwd=REPO_DIR)
        _run_git(["remote", "add", "origin", GIT_REMOTE_URL], cwd=REPO_DIR)
        _run_git(["fetch", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
        rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
        if rb and rb.returncode == 0 and rb.stdout.strip():
            _run_git(
                ["merge", "--allow-unrelated-histories", "-X", "ours",
                 f"origin/{GIT_BRANCH}", "-m", "Merge remote content"],
                cwd=REPO_DIR,
            )

    # 关键修复：无论 clone 还是已有仓库，都设置 identity
    _run_git(["config", "user.name", "auto-experiment"], cwd=REPO_DIR)
    _run_git(["config", "user.email", "auto@experiment.local"], cwd=REPO_DIR)
    _run_git(["config", "http.version", "HTTP/1.1"], cwd=REPO_DIR)


def _git_sha() -> str | None:
    r = _run_git(["rev-parse", "--short", "HEAD"], cwd=REPO_DIR)
    return r.stdout.strip() if r and r.returncode == 0 else None


def _scan_staged() -> list[str]:
    r = _run_git(["diff", "--cached", "--name-only", "-z"], cwd=REPO_DIR)
    names = [x for x in (r.stdout or "").split("\0") if x] if r else []
    hits = []
    for name in names:
        p = REPO_DIR / name
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if SECRET_RE.search(text):
            hits.append(name)
            continue
        for secret in (GITEE_TOKEN, API_KEY):
            if secret and secret in text:
                hits.append(name)
                break
    return hits


def _git_push_sync() -> bool:
    _run_git(["fetch", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
    rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    if rb and rb.returncode == 0 and rb.stdout.strip():
        rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
        if not (rbr and rbr.returncode == 0):
            print("  [警告] rebase 冲突，放弃本次 push", flush=True)
            _run_git(["rebase", "--abort"], cwd=REPO_DIR)
            return False
    p = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
    if p and p.returncode == 0:
        return True
    print(f"  [警告] push 失败，重试一次：{_redact(p.stderr if p else '')[:300]}", flush=True)
    _run_git(["fetch", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
    rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    if rb and rb.returncode == 0 and rb.stdout.strip():
        _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    p2 = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
    if p2 and p2.returncode == 0:
        return True
    print(f"  [警告] push 仍然失败：{_redact(p2.stderr if p2 else '')[:300]}", flush=True)
    return False


def _git_commit_sync(message: str, push: bool) -> bool:
    # 只加结果目录，绝不 add 脚本/密钥/临时文件
    _run_git(["add", "-A", "--", "llm_experiment_results_v2"], cwd=REPO_DIR)
    r = _run_git(["status", "--porcelain"], cwd=REPO_DIR)
    if not (r and r.stdout.strip()):
        return _git_push_sync() if push else True

    hits = _scan_staged()
    if hits:
        _run_git(["reset"], cwd=REPO_DIR)
        raise RuntimeError(f"暂存区发现疑似密钥，拒绝提交：{hits}")

    c = _run_git(["commit", "-m", message], cwd=REPO_DIR)
    if not (c and c.returncode == 0):
        raise RuntimeError(f"git commit 失败：{_redact(c.stderr if c else '')[:300]}")
    return _git_push_sync() if push else True


async def _checkpoint(label: str, force_push: bool = False) -> bool:
    global _checkpoint_count
    async with _checkpoint_lock:
        _checkpoint_count += 1
        n = _checkpoint_count
        if not force_push and n % GIT_COMMIT_EVERY != 0 and n % GIT_PUSH_INTERVAL != 0:
            return True
        push = force_push or (n % GIT_PUSH_INTERVAL == 0)
        return await asyncio.to_thread(
            _git_commit_sync, f"v2: {label} [{n}]", push
        )


# ============ 模型状态与 LLM ============
_model_failures = {}
_model_disabled = set()


def _model_ok(model: str) -> bool:
    return model not in _model_disabled


def _record_model_result(model: str, ok: bool):
    if ok:
        _model_failures[model] = 0
        return
    n = _model_failures.get(model, 0) + 1
    _model_failures[model] = n
    if n >= MODEL_FAILURE_LIMIT and model not in _model_disabled:
        _model_disabled.add(model)
        print(f"[熔断] {model} 连续失败 {n} 次，本次运行跳过该模型", flush=True)


def _error_result(err):
    return {
        "content": f"[ERROR] {err}",
        "prompt_tokens": None,
        "completion_tokens": None,
        "elapsed": None,
    }


def _parse_compare_json(text: str):
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    i, j = text.find("{"), text.rfind("}")
    if i == -1 or j == -1 or j <= i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except Exception:
        return None


async def _stream_once(client, model, prompt, temperature, max_tokens):
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    try:
        stream = await client.chat.completions.create(**kwargs)
    except Exception as e:
        msg = str(e)
        # 兼容部分模型只接受 max_completion_tokens
        if "max_tokens" in msg and "max_completion_tokens" not in msg:
            kwargs.pop("max_tokens", None)
            kwargs["max_completion_tokens"] = max_tokens
            stream = await client.chat.completions.create(**kwargs)
        else:
            raise

    parts, usage, finish = [], None, None
    async for chunk in stream:
        _check_deadline()
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if not getattr(chunk, "choices", None):
            continue
        choice = chunk.choices[0]
        finish = choice.finish_reason or finish
        delta = choice.delta
        content = getattr(delta, "content", None)
        if content:
            if isinstance(content, list):
                parts.extend(str(c) for c in content)
            else:
                parts.append(content)
    return "".join(parts), usage, finish


async def call_llm(model: str, prompt: str, temperature: float,
                   max_tokens: int, tag: str) -> dict:
    if not _model_ok(model):
        return _error_result("model disabled")
    t0 = time.monotonic()
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        _check_deadline()
        if not _model_ok(model):
            return _error_result("model disabled")
        remaining = max(1.0, min(PER_CALL_TIMEOUT, _deadline - time.monotonic()))
        try:
            text, usage, finish = await asyncio.wait_for(
                _stream_once(client_for_call, model, prompt, temperature, max_tokens),
                timeout=remaining,
            )
            if not (text or "").strip():
                raise RuntimeError(f"EmptyResponse(finish={finish})")
            _record_model_result(model, True)
            return {
                "content": text,
                "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
                "elapsed": round(time.monotonic() - t0, 2),
            }
        except TimeBudgetExceeded:
            raise
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            # 429/限流通常是瞬时的，不要因此把模型熔断掉
            if "429" not in last_err and "rate limit" not in last_err.lower():
                _record_model_result(model, False)
            print(f"  [警告] {tag} {model} 调用失败 "
                  f"(attempt {attempt}/{MAX_RETRIES}): {last_err[:200]}", flush=True)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(min(2 ** attempt, 20) + random.random())
    return _error_result(last_err or "unknown")


# 客户端在 main 里赋值；避免每个任务重复创建连接池
client_for_call = None


# ============ 数据分析 ============
def _expected_results():
    return {(t, c, r) for t in TASKS_BY_ID for c in CONDITIONS
            for r in range(1, N_RUNS + 1)}


def _analyze_model(model: str) -> dict:
    d = _model_dir(model)
    results = _latest_valid(_load_jsonl(d / "results.jsonl"),
                            ("task_id", "condition", "run"), _valid_result)
    cleaned = _latest_valid(_load_jsonl(d / "cleaned.jsonl"),
                            ("task_id", "run"), _valid_cleaned)

    baseline_map, wp_map = {}, {}
    for (tid, cond, run), r in results.items():
        if cond == "baseline":
            baseline_map[(tid, run)] = r
        elif cond == "word_pairs":
            wp_map[(tid, run)] = r

    expected = _expected_results()
    missing_gen = sorted(expected - set(results))
    to_clean = [wp_map[k] for k in sorted(wp_map) if k not in cleaned]

    pairs = []
    for (tid, run) in sorted(set(baseline_map) & set(cleaned)):
        pairs.append((tid, run, baseline_map[(tid, run)], cleaned[(tid, run)]))

    judge_missing = {}
    for judge in JUDGE_MODELS:
        comps = _latest_valid(
            _load_jsonl(_judge_path(model, judge)),
            ("task_id", "run", "swap"), _valid_comparison,
        )
        need = []
        for (tid, run, base_rec, clean_rec) in pairs:
            orders = (False, True) if COUNTERBALANCE else (_deterministic_swap(model, judge, tid, run),)
            for sw in orders:
                if (tid, run, sw) not in comps:
                    need.append((tid, run, base_rec, clean_rec, sw))
        judge_missing[judge] = need

    return {
        "model": model,
        "n_results": len(_load_jsonl(d / "results.jsonl")),
        "n_results_valid": len(results),
        "n_cleaned": len(_load_jsonl(d / "cleaned.jsonl")),
        "n_cleaned_valid": len(cleaned),
        "missing_gen": missing_gen,
        "to_clean": to_clean,
        "pairs": pairs,
        "judge_missing": judge_missing,
    }


def _deterministic_swap(model: str, judge: str, task_id: int, run: int) -> bool:
    raw = f"{model}|{judge}|{task_id}|{run}|{SEED}".encode()
    return int(hashlib.sha256(raw).hexdigest(), 16) % 2 == 1


# ============ 阶段 0：生成 ============
async def generate_one(model, task, cond, run, sem):
    if not _model_ok(model):
        return None
    prompt = task["prompt"] if cond == "baseline" else f"{PREFIX}\n{task['prompt']}"
    async with sem:
        res = await call_llm(model, prompt, TEMPERATURE_GEN,
                             MAX_TOKENS_GEN, f"gen:{task['id']}:{cond}:{run}")
    rec = _base_record(
        model, stage="generate", task_id=task["id"], task_name=task["name"],
        condition=cond, run=run, prompt=prompt, content=res["content"],
        prompt_tokens=res["prompt_tokens"], completion_tokens=res["completion_tokens"],
        elapsed=res["elapsed"], temperature=TEMPERATURE_GEN,
    )
    d = _model_dir(model) / f"task{task['id']}_{task['name']}" / cond
    d.mkdir(parents=True, exist_ok=True)
    (d / f"run_{run:02d}.md").write_text(
        f"# [v2:{model}] 任务{task['id']} {task['name']} | 条件: {cond} | 第 {run} 次\n\n"
        f"**Prompt:** {prompt}\n\n"
        f"**耗时:** {res['elapsed']}s | tokens: {res['prompt_tokens']}/{res['completion_tokens']}\n\n"
        f"---\n\n{res['content']}\n",
        encoding="utf-8",
    )
    _append_jsonl(_model_dir(model) / "results.jsonl", rec)
    print(f"[生成] {model} | task{task['id']} {cond} run{run:02d} | {res['elapsed']}s", flush=True)
    await _checkpoint(f"gen {model} t{task['id']} {cond} r{run}")
    return rec


async def run_generation(models):
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = []
    for model in models:
        a = _analyze_model(model)
        print(f"[分析] {model}: 生成缺 {len(a['missing_gen'])} / 清洗缺 "
              f"{len(a['to_clean'])}", flush=True)
        for (tid, cond, run) in a["missing_gen"]:
            jobs.append(generate_one(model, TASKS_BY_ID[tid], cond, run, sem))
    if not jobs:
        print("[阶段0] 无缺失，跳过", flush=True)
        return
    print(f"[阶段0] 启动 {len(jobs)} 个生成任务，并发 {CONCURRENCY}", flush=True)
    results = await asyncio.gather(*jobs, return_exceptions=True)
    _raise_stage_errors(results, "阶段0")
    await _checkpoint("阶段0完成", force_push=True)


# ============ 阶段 1：清洗 ============
async def clean_one(model, record, sem):
    if not _model_ok(model):
        return None
    content = record.get("content") or ""
    if _is_error_text(content):
        return None
    residual = False
    attempts = 0
    res = None
    cleaned = ""
    for prompt in (CLEAN_PROMPT, CLEAN_PROMPT_STRICT):
        attempts += 1
        async with sem:
            res = await call_llm(model, prompt.format(content=content),
                                 TEMPERATURE_JUDGE, MAX_TOKENS_CLEAN,
                                 f"clean:{record['task_id']}:{record['run']}")
        cleaned = (res["content"] or "").strip()
        residual = bool(RESIDUAL_RE.search(cleaned))
        if not residual:
            break

    rec = _base_record(
        model, stage="clean", task_id=record["task_id"], task_name=record["task_name"],
        condition=record.get("condition", "word_pairs"), run=record["run"],
        original_prompt=record.get("prompt"), original_content=content,
        cleaned_content=cleaned, residual=residual, clean_attempts=attempts,
        clean_prompt_tokens=res["prompt_tokens"] if res else None,
        clean_completion_tokens=res["completion_tokens"] if res else None,
        clean_elapsed=res["elapsed"] if res else None,
        temperature=TEMPERATURE_JUDGE,
    )
    d = _model_dir(model) / "cleaned" / f"task{record['task_id']}_{record['task_name']}"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"run_{record['run']:02d}.md").write_text(
        f"# [v2:{model}] 清洗 | task{record['task_id']} {record['task_name']} | "
        f"run {record['run']} | residual={residual}\n\n"
        f"## 原始输出\n\n{content}\n\n---\n\n## 清洗后\n\n{cleaned}\n",
        encoding="utf-8",
    )
    _append_jsonl(_model_dir(model) / "cleaned.jsonl", rec)
    print(f"[清洗] {model} | task{record['task_id']} run{record['run']:02d} | "
          f"residual={residual} | {attempts} 次", flush=True)
    await _checkpoint(f"clean {model} t{record['task_id']} r{record['run']}")
    return rec


async def run_cleaning(models):
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = []
    for model in models:
        a = _analyze_model(model)
        for rec in a["to_clean"]:
            jobs.append(clean_one(model, rec, sem))
    if not jobs:
        print("[阶段1] 无缺失，跳过", flush=True)
        return
    print(f"[阶段1] 启动 {len(jobs)} 个清洗任务，并发 {CONCURRENCY}", flush=True)
    results = await asyncio.gather(*jobs, return_exceptions=True)
    _raise_stage_errors(results, "阶段1")
    await _checkpoint("阶段1完成", force_push=True)


# ============ 阶段 2：盲评 ============
async def judge_one(judge, model, task, baseline_rec, cleaned_rec, swap, sem):
    if not _model_ok(judge):
        return None
    baseline_ans = baseline_rec.get("content") or ""
    cleaned_ans = cleaned_rec.get("cleaned_content") or ""
    if _is_error_text(baseline_ans) or _is_error_text(cleaned_ans):
        return None

    if swap:
        ans_a, ans_b = cleaned_ans, baseline_ans
        label_a, label_b = "cleaned_word_pairs", "baseline"
    else:
        ans_a, ans_b = baseline_ans, cleaned_ans
        label_a, label_b = "baseline", "cleaned_word_pairs"

    prompt = COMPARE_PROMPT.format(task=task["prompt"], answer_a=ans_a, answer_b=ans_b)
    res = None
    parsed = None
    for attempt in (1, 2):
        async with sem:
            res = await call_llm(judge, prompt, TEMPERATURE_JUDGE,
                                 MAX_TOKENS_JUDGE,
                                 f"judge:{judge}:{model}:{task['id']}:{baseline_rec['run']}")
        parsed = _parse_compare_json(res["content"] or "")
        if parsed and _valid_scores(parsed.get("A")) and _valid_scores(parsed.get("B")):
            break

    winner_raw = winner_label = None
    scores_a = scores_b = reason = None
    if parsed:
        winner_raw = str(parsed.get("winner", "")).strip()
        scores_a = parsed.get("A")
        scores_b = parsed.get("B")
        reason = parsed.get("reason")
        if winner_raw.upper() == "A":
            winner_label = label_a
        elif winner_raw.upper() == "B":
            winner_label = label_b
        elif winner_raw.lower() == "tie":
            winner_label = "tie"

    rec = _base_record(
        judge, stage="judge", judge_model=judge, gen_model=model,
        pair_id=f"{_slug(model)}:{task['id']}:{baseline_rec['run']}",
        task_id=task["id"], task_name=task["name"], run=baseline_rec["run"],
        swap=swap, A_source=label_a, B_source=label_b,
        baseline_content=baseline_ans, cleaned_content=cleaned_ans,
        raw_llm_output=res["content"] if res else None, parsed=parsed,
        winner_raw=winner_raw, winner_label=winner_label,
        A_scores=scores_a, B_scores=scores_b, reason=reason,
        compare_elapsed=res["elapsed"] if res else None,
        compare_prompt_tokens=res["prompt_tokens"] if res else None,
        compare_completion_tokens=res["completion_tokens"] if res else None,
        temperature=TEMPERATURE_JUDGE,
    )
    d = _model_dir(model) / "comparison" / _slug(judge) / f"task{task['id']}_{task['name']}"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"run_{baseline_rec['run']:02d}_swap{int(swap)}.md").write_text(
        f"# [v2:{judge} 评 {model}] task{task['id']} {task['name']} | "
        f"run {baseline_rec['run']} | swap={swap}\n\n"
        f"**Winner:** {winner_label} (raw={winner_raw})\n\n"
        f"**A:** {label_a} | **B:** {label_b}\n\n"
        f"---\n\n## 回答 A\n\n{ans_a}\n\n---\n\n## 回答 B\n\n{ans_b}\n\n"
        f"---\n\n## 评审输出\n\n{res['content'] if res else ''}\n",
        encoding="utf-8",
    )
    _append_jsonl(_judge_path(model, judge), rec)
    print(f"[盲评] {judge} × {model} | task{task['id']} run{baseline_rec['run']:02d} "
          f"swap={swap} winner={winner_label}", flush=True)
    await _checkpoint(f"judge {judge} {model} t{task['id']} r{baseline_rec['run']} s{int(swap)}")
    return rec


async def run_comparison(models, judges):
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = []
    for model in models:
        a = _analyze_model(model)
        for judge in judges:
            for (tid, run, base_rec, clean_rec, sw) in a["judge_missing"].get(judge, []):
                jobs.append(judge_one(judge, model, TASKS_BY_ID[tid],
                                      base_rec, clean_rec, sw, sem))
    if not jobs:
        print("[阶段2] 无缺失，跳过", flush=True)
        return
    print(f"[阶段2] 启动 {len(jobs)} 个盲评任务（{len(judges)} 位评委），"
          f"并发 {CONCURRENCY}", flush=True)
    results = await asyncio.gather(*jobs, return_exceptions=True)
    _raise_stage_errors(results, "阶段2")
    await _checkpoint("阶段2完成", force_push=True)


# ============ 汇总 ============
def _avg(vals):
    vals = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return round(sum(vals) / len(vals), 2) if vals else None


def _summarize(model, judge) -> dict:
    recs = list(_latest_valid(
        _load_jsonl(_judge_path(model, judge)),
        ("task_id", "run", "swap"), _valid_comparison,
    ).values())
    wins = {"baseline": 0, "cleaned_word_pairs": 0, "tie": 0}
    for r in recs:
        w = r.get("winner_label")
        if w in wins:
            wins[w] += 1

    scores = {}
    for d in DIMS:
        base, clean = [], []
        for r in recs:
            sa, sb = r.get("A_scores") or {}, r.get("B_scores") or {}
            if r.get("A_source") == "baseline":
                b, c = sa.get(d), sb.get(d)
            else:
                b, c = sb.get(d), sa.get(d)
            if isinstance(b, int) and not isinstance(b, bool):
                base.append(b)
            if isinstance(c, int) and not isinstance(c, bool):
                clean.append(c)
        scores[d] = {"baseline": _avg(base), "cleaned": _avg(clean),
                     "diff": (round(_avg(base) - _avg(clean), 2)
                              if _avg(base) is not None and _avg(clean) is not None else None)}

    # 位置统计
    pos = {"A": [], "B": [], "A_baseline": [], "A_cleaned": []}
    for r in recs:
        sa, sb = r.get("A_scores") or {}, r.get("B_scores") or {}
        if isinstance(sa.get("overall"), int):
            pos["A"].append(sa["overall"])
        if isinstance(sb.get("overall"), int):
            pos["B"].append(sb["overall"])
        if r.get("A_source") == "baseline" and isinstance(sa.get("overall"), int):
            pos["A_baseline"].append(sa["overall"] - (sb.get("overall") or 0))
        if r.get("A_source") == "cleaned_word_pairs" and isinstance(sa.get("overall"), int):
            pos["A_cleaned"].append(sa["overall"] - (sb.get("overall") or 0))

    by_task = {}
    for r in recs:
        tid = r.get("task_id")
        by_task.setdefault(tid, {"baseline": 0, "cleaned_word_pairs": 0, "tie": 0})
        w = r.get("winner_label")
        if w in by_task[tid]:
            by_task[tid][w] += 1

    return {
        "model": model, "judge": judge, "n_comparisons": len(recs),
        "wins": wins, "scores": scores,
        "position": {
            "A_mean": _avg(pos["A"]), "B_mean": _avg(pos["B"]),
            "A_minus_B_when_A_baseline": _avg(pos["A_baseline"]),
            "A_minus_B_when_A_cleaned": _avg(pos["A_cleaned"]),
        },
        "by_task": by_task,
    }


def write_summary(models, judges):
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for model in models:
        d = _model_dir(model)
        clean_recs = list(_latest_valid(
            _load_jsonl(d / "cleaned.jsonl"), ("task_id", "run"), _valid_cleaned).values())
        residual = sum(1 for r in clean_recs if r.get("residual"))
        for judge in judges:
            s = _summarize(model, judge)
            s["cleaned_valid"] = len(clean_recs)
            s["cleaned_residual"] = residual
            (d / f"summary__{_slug(judge)}.json").write_text(
                json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            all_rows.append(s)

    (RESULTS_ROOT / "summary.json").write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# v2 汇总",
        "",
        f"- run_id: `{RUN_ID}`",
        f"- 生成模型: {', '.join(f'`{m}`' for m in models)}",
        f"- 评委: {', '.join(f'`{j}`' for j in judges)}",
        f"- N_RUNS: {N_RUNS} | COUNTERBALANCE: {COUNTERBALANCE} | 并发: {CONCURRENCY}",
        "",
        "| 生成模型 | 评委 | 有效比较 | baseline 胜 | cleaned 胜 | tie | cleaned 残留 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for s in all_rows:
        lines.append(
            f"| `{s['model']}` | `{s['judge']}` | {s['n_comparisons']} | "
            f"{s['wins']['baseline']} | {s['wins']['cleaned_word_pairs']} | "
            f"{s['wins']['tie']} | {s['cleaned_residual']}/{s['cleaned_valid']} |"
        )
    lines += [
        "",
        "> 每个评委内部对每对做 A/B 双顺序；位置偏差见每个 `summary__*.json` 的 `position` 字段。",
        "> `cleaned_residual` 是清洗后仍含词对编号/“这些词中”等引用的条数。",
    ]
    (RESULTS_ROOT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


# ============ 主流程 ============
def _print_banner():
    print("=" * 72, flush=True)
    print("LLM 词对实验 v2：多生成模型 + 双评委 + 断点续跑", flush=True)
    print("=" * 72, flush=True)
    print(f"运行环境 : {'Kaggle' if IS_KAGGLE else '本地'}", flush=True)
    print(f"仓库目录 : {REPO_DIR}", flush=True)
    print(f"结果目录 : {RESULTS_ROOT}", flush=True)
    print(f"生成模型 : {', '.join(GEN_MODELS)}", flush=True)
    print(f"评委     : {', '.join(JUDGE_MODELS)}", flush=True)
    print(f"网格     : {len(TASKS_BY_ID)} 任务 x {len(CONDITIONS)} 条件 x {N_RUNS} run "
          f"x {len(GEN_MODELS)} 模型", flush=True)
    print(f"并发     : {CONCURRENCY} | 双顺序: {COUNTERBALANCE} | "
          f"时间预算: {TIME_BUDGET_MIN:.0f} min", flush=True)
    print(f"git      : {GIT_REMOTE_URL} [{GIT_BRANCH}] | push every {GIT_PUSH_INTERVAL}", flush=True)
    print("=" * 72, flush=True)


async def main():
    global _deadline, _checkpoint_lock, client_for_call
    _checkpoint_lock = asyncio.Lock()
    _deadline = time.monotonic() + TIME_BUDGET_MIN * 60

    _print_banner()
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY 未配置：请设置环境变量/Kaggle Secret，或在私有版本中注入")
    if not GITEE_TOKEN:
        print("[警告] GITEE_TOKEN 未配置：可以生成结果，但无法 push", flush=True)

    if not SKIP_SYNC and not DRY_RUN:
        _ensure_repo()
    else:
        print("[Git] 跳过同步（DRY_RUN 或 SKIP_SYNC）", flush=True)

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"[Git] HEAD = {_git_sha()}", flush=True)

    client_for_call = AsyncOpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=PER_CALL_TIMEOUT,
        max_retries=0,
    )

    models = [m for m in GEN_MODELS if _model_ok(m)]
    judges = [j for j in JUDGE_MODELS if _model_ok(j)]

    try:
        if not DRY_RUN:
            await run_generation(models)
            models = [m for m in models if _model_ok(m)]
            await run_cleaning(models)
            models = [m for m in models if _model_ok(m)]
            judges = [j for j in judges if _model_ok(j)]
            await run_comparison(models, judges)
            write_summary(models, judges)
        else:
            for model in models:
                a = _analyze_model(model)
                print(f"[DRY_RUN] {model}: 生成缺 {len(a['missing_gen'])}，"
                      f"清洗缺 {len(a['to_clean'])}，"
                      f"盲评缺 {sum(len(v) for v in a['judge_missing'].values())}", flush=True)
    except TimeBudgetExceeded:
        print(f"\n[时间预算] 已用满 {TIME_BUDGET_MIN:.0f} 分钟，保存进度，下次运行继续", flush=True)
    finally:
        if not DRY_RUN:
            try:
                ok = await asyncio.to_thread(
                    _git_commit_sync, "v2: 运行结束 checkpoint", True)
                if not ok:
                    print("[错误] 最终 push 失败：结果只在本地，请检查网络/凭据", flush=True)
                    raise RuntimeError("最终 Git push 失败：结果未持久化到 Gitee")
            except Exception as e:
                print(f"[错误] 最终提交失败：{e}", flush=True)
                raise
    print("\n完成（若上方提示时间预算/失败，重跑本 notebook 会自动续跑）。", flush=True)


def run_main():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(main())
        return

    box = {}

    def _worker():
        try:
            asyncio.run(main())
        except BaseException as e:
            box["error"] = e

    t = threading.Thread(target=_worker, name="llm-word-pairs-v2")
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]


if __name__ == "__main__":
    run_main()

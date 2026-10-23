#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kaggle 补数脚本（Gitee 版）—— 基于原后处理脚本 vfdjk.py 修改
================================================================
用途：检查 Gitee 仓库（jkdsfn 的 main 分支，即 llm_experiment_results 目录）
中实验数据的缺失/失效部分，用 LLM 逐条补齐，并把结果增量推回 Gitee。

补什么（只新增，不删除/覆盖 jsonl 旧内容，读取时取每个键"最新有效"记录）：
  阶段 0（补生成）：results.jsonl 缺失 (task_id, condition, run)，
                    或该键最新记录 content 为 [ERROR] -> 重新生成
                    （prompt 优先复用同条件已有记录的原 prompt，与原实验保持一致）
  阶段 1（补清洗）：cleaned.jsonl 缺失 (task_id, run)，
                    或最新记录 cleaned_content 为 [ERROR] -> 重新清洗
  阶段 2（补盲评）：comparison.jsonl 缺失 (task_id, run)，
                    或最新记录 winner_label 无效（含 LLM 空回复导致解析失败）
                    -> 重新盲评

相对原后处理脚本的三处针对性修复（对应仓库里实际存在的两类脏数据）：
  a) 8 条 cleaned 记录为 [ERROR] TimeoutError：原脚本重试总预算(600s)恰好等于
     单次超时(600s)，超时一次就没有重试机会；本脚本默认预算 1800s
  b) 8 条 comparison 记录 LLM 返回空字符串导致解析失败：本脚本把"空回复"
     视为失败自动重试
  c) 新增熔断器：连续 N 次调用全部失败（如 API Key 失效/断网）时自动停止，
     避免在 Kaggle 上空烧会话时长；已完成的增量结果仍会推送到 Gitee

Kaggle 使用步骤：
  1. 新建 Notebook：Settings -> Internet 打开（必须；纯 API 调用，CPU 即可，无需 GPU）
  2. 可选：Settings -> Secrets 添加 OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL
     （不配则使用脚本内默认值；环境变量优先级最高）
  3. 把本文件全部内容粘贴到一个 cell 运行（或 File -> Import Notebook 上传本文件）
  4. 工作目录为 /kaggle/working/llm_experiment_results，Kaggle 会随 Notebook 版本保存
  5. 会话超时/中断后直接重跑：脚本自动跳过已完成部分，只补缺失（断点续跑）

其他环境/调试：
  - WORK_DIR   指定工作目录（默认 Kaggle 自动检测，否则当前目录）
  - SKIP_SYNC=1 跳过 Git 同步，直接使用本地已有数据
  - DRY_RUN=1   只打印缺失分析，不调用 LLM、不写文件、不推送
"""

import asyncio
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---- openai 自动安装（Kaggle 镜像默认不带 openai 包） ----
try:
    from openai import AsyncOpenAI
except ImportError:
    print("[环境] 未检测到 openai 包，自动执行 pip install openai …", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "openai"],
        check=False, timeout=900,
    )
    from openai import AsyncOpenAI

# ============ 运行环境识别 ============
IS_KAGGLE = bool(
    os.environ.get("KAGGLE_KERNEL_RUN_TYPE")
    or os.environ.get("KAGGLE_URL_BASE")
    or Path("/kaggle/working").exists()
)


def _get_env(name, default=None):
    """读取配置。优先级：环境变量 > Kaggle Secrets > 内置默认值"""
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
            pass  # 未挂载该 Secret 属正常情况，静默回退
    return default


# ============ 配置 ============
API_KEY = _get_env(
    "OPENAI_API_KEY",
    "",
)
BASE_URL = _get_env("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = _get_env("LLM_MODEL", "moonshotai/kimi-k3")

GEN_TEMPERATURE = float(os.environ.get("GEN_TEMPERATURE", "0.6"))    # 阶段 0：与生成脚本一致
POST_TEMPERATURE = float(os.environ.get("POST_TEMPERATURE", "0.3"))  # 阶段 1/2：与后处理脚本一致

CONCURRENCY = int(os.environ.get("CONCURRENCY", "2"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "20"))
PER_CALL_TIMEOUT = int(os.environ.get("PER_CALL_TIMEOUT", "600"))
# 注意：重试总预算必须大于单次超时，否则"超时一次"就没有任何重试机会
# （原脚本 600 == 600，导致仓库里留下 8 条 [ERROR] TimeoutError 清洗记录）
RETRY_TOTAL_BUDGET = int(os.environ.get("RETRY_TOTAL_BUDGET", "1800"))
# 熔断阈值：连续 N 次调用彻底失败则停止后续调用（0 = 关闭熔断）
CIRCUIT_BREAKER = int(os.environ.get("CIRCUIT_BREAKER", "5"))

# 期望的实验网格：6 任务 x 2 条件 x N_RUNS
N_RUNS = int(os.environ.get("N_RUNS", "10"))
CONDITIONS = ("baseline", "word_pairs")

DRY_RUN = os.environ.get("DRY_RUN", "").lower() not in ("", "0", "false", "no")
SKIP_SYNC = os.environ.get("SKIP_SYNC", "").lower() not in ("", "0", "false", "no")

WORK_DIR = Path(os.environ.get("WORK_DIR", "/kaggle/working" if IS_KAGGLE else "."))
OUTPUT_DIR = WORK_DIR / "llm_experiment_results"
RESULTS_PATH = OUTPUT_DIR / "results.jsonl"       # 输入 + 阶段 0 输出（增量）
CLEANED_PATH = OUTPUT_DIR / "cleaned.jsonl"       # 阶段 1 输出（增量）
COMPARISON_PATH = OUTPUT_DIR / "comparison.jsonl"  # 阶段 2 输出（增量）
CLEANED_DIR = OUTPUT_DIR / "cleaned"
COMPARISON_DIR = OUTPUT_DIR / "comparison"

# ============ Git 配置 ============
GIT_REMOTE_URL = _get_env(
    "GIT_REMOTE_URL",
    "https://gitee.com/qwe12345678/jkdsfn.git",
)
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")
GIT_PUSH_INTERVAL = int(os.environ.get("GIT_PUSH_INTERVAL", "5"))

# ============ 任务表（与生成/后处理脚本保持一致） ============
TASKS_BY_ID = {
    1: {"id": 1, "name": "函数式编程语言", "prompt": "设计一个全新的函数式编程语言"},
    2: {"id": 2, "name": "提升LLM性能",   "prompt": "怎么低成本不需要额外训练大幅提升现有LLM的性能"},
    3: {"id": 3, "name": "CLI工具Idea",   "prompt": "给出适合独立开发者开发CLI工具的一个Idea"},
    4: {"id": 4, "name": "新理论",        "prompt": "提出一个新的理论"},
    5: {"id": 5, "name": "人格模型",      "prompt": "提出一个新的类似于九型和荣格八维的模型"},
    6: {"id": 6, "name": "ML架构",        "prompt": "提出一个新的机器学习架构"},
}

# word_pairs 条件的前缀指令（与生成脚本 jvdfka.py 完全一致）
PREFIX = "在回答前面输出200组词，每组有两个词，从这些词获得灵感"

# ============ Prompt 模板（与原后处理脚本完全一致，勿改） ============
CLEAN_PROMPT = """下面是一段 LLM 的输出，它的开头先输出了很多组词对（每组两个词），
词对之后才是真正的回答内容。

请你只保留词对之后的真正回答部分，把开头的词对全部删除。
要求：
- 不要改动、不要改写、不要总结保留部分的内容，原样输出；
- 不要添加任何前言、后记、解释、代码块标记或标题；
- 如果原文中不存在明显独立的词对段落，则原样返回全部内容。

只输出清洗后的正文，不要输出任何其他内容。

=== 原始输出开始 ===
{content}
=== 原始输出结束 ==="""

COMPARE_PROMPT = """你是一位严谨、公正的评审专家。下面有两个针对同一任务的回答（A 和 B）。
请从以下 5 个维度分别打分，每项 1-10 分（整数）：
- logic:          逻辑性与结构
- concreteness:   具体性与细节
- actionability:  可操作性
- originality:    原创性
- overall:        整体质量

然后给出最终结论，winner 必须是以下之一："A"、"B"、"tie"。

只输出一个 JSON 对象，不要任何多余文字、不要 markdown 代码块。格式如下：
{{"A": {{"logic": 0, "concreteness": 0, "actionability": 0, "originality": 0, "overall": 0}}, "B": {{"logic": 0, "concreteness": 0, "actionability": 0, "originality": 0, "overall": 0}}, "winner": "A", "reason": "..."}}

任务：{task}

=== 回答 A ===
{answer_a}

=== 回答 B ===
{answer_b}"""

# ============ 通用工具 ============
_write_lock = threading.Lock()
_git_lock = threading.Lock()
_commit_counter = 0


def _append_jsonl(path: Path, record: dict):
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception as e:
                print(f"  [警告] 解析 {path.name} 某行失败: {e}", flush=True)
    return out


def _next_commit_count() -> int:
    global _commit_counter
    with _write_lock:
        _commit_counter += 1
        return _commit_counter


# ---- "缺失"判定：只认每个键最新的一条有效记录 ----
def _is_error_text(t):
    return not t or str(t).strip().startswith("[ERROR]")


def _valid_result(r) -> bool:
    """results.jsonl 记录有效：content 非空且非 [ERROR]"""
    return not _is_error_text(r.get("content"))


def _valid_cleaned(r) -> bool:
    """cleaned.jsonl 记录有效：cleaned_content 非空且非 [ERROR]"""
    return not _is_error_text(r.get("cleaned_content"))


def _valid_comparison(r) -> bool:
    """comparison.jsonl 记录有效：winner_label 成功映射到三个合法值之一"""
    return r.get("winner_label") in ("baseline", "cleaned_word_pairs", "tie")


def _latest_valid_by_key(records: list, key_fields: tuple, valid_fn) -> dict:
    """追加式 jsonl 越靠后越新：对每个键保留最新一条有效记录（ERROR/无效不算数，
    因此失败的键会被视为缺失，交给补数阶段重做）"""
    out = {}
    for r in records:
        key = tuple(r.get(f) for f in key_fields)
        if any(k is None for k in key):
            continue
        if not valid_fn(r):
            continue
        out[key] = r
    return out


def _split_conditions(valid_results: dict):
    """把 (task, condition, run) -> record 拆成 baseline / word_pairs 两个 (task, run) 映射"""
    baseline_map, wp_map = {}, {}
    for (tid, cond, run), r in valid_results.items():
        if cond == "baseline":
            baseline_map[(tid, run)] = r
        elif cond == "word_pairs":
            wp_map[(tid, run)] = r
    return baseline_map, wp_map


# ============ Git 工具 ============
def _run_git(args, cwd=None, timeout=300):
    try:
        return subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        print("  [警告] 未找到 git 命令，跳过自动提交", flush=True)
        return None
    except subprocess.TimeoutExpired:
        print(f"  [警告] git {' '.join(args)} 超时", flush=True)
        return None
    except Exception as e:
        print(f"  [警告] git 执行异常: {e}", flush=True)
        return None


def _is_git_repo(d: Path) -> bool:
    r = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=d)
    return bool(r and r.returncode == 0 and r.stdout.strip() == "true")


def _ensure_git_repo(repo_dir: Path):
    """幂等地确保目录是 git 仓库、remote/身份/分支就绪"""
    repo_dir.mkdir(parents=True, exist_ok=True)

    if not _is_git_repo(repo_dir):
        _run_git(["init"], cwd=repo_dir)

    _run_git(["checkout", "-B", GIT_BRANCH], cwd=repo_dir)

    r = _run_git(["remote"], cwd=repo_dir)
    remotes = r.stdout.split() if (r and r.returncode == 0) else []
    if "origin" in remotes:
        _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=repo_dir)
    else:
        _run_git(["remote", "add", "origin", GIT_REMOTE_URL], cwd=repo_dir)

    _run_git(["config", "user.email", "auto@experiment.local"], cwd=repo_dir)
    _run_git(["config", "user.name",  "auto-experiment"], cwd=repo_dir)


def _sync_from_gitee():
    """
    从 Gitee 拉取最新内容到 OUTPUT_DIR。
    策略：
      - 目录不存在/为空  -> git clone
      - 存在但非仓库     -> init + fetch + merge -X ours
      - 已是仓库         -> pull --rebase；失败则 fetch + merge -X ours
    """
    print(f"[Git] 从 Gitee 同步最新内容（branch={GIT_BRANCH}）…", flush=True)

    # 1) 目录不存在或为空 -> clone
    if not OUTPUT_DIR.exists() or not any(OUTPUT_DIR.iterdir()):
        OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
        r = _run_git(
            ["clone", "-b", GIT_BRANCH, GIT_REMOTE_URL, str(OUTPUT_DIR)],
            cwd=OUTPUT_DIR.parent,
        )
        if r and r.returncode == 0:
            print(f"[Git] clone 成功 -> {OUTPUT_DIR}", flush=True)
            return
        err = (r.stderr.strip() if r else "unknown")
        print(f"[Git] clone 失败（{err}），改为本地 init", flush=True)
        _ensure_git_repo(OUTPUT_DIR)
        _run_git(["fetch", "origin", GIT_BRANCH], cwd=OUTPUT_DIR)
        rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=OUTPUT_DIR)
        if rb and rb.returncode == 0 and rb.stdout.strip():
            _run_git(
                ["merge", "--allow-unrelated-histories", "-X", "ours",
                 f"origin/{GIT_BRANCH}", "-m", "Merge remote content"],
                cwd=OUTPUT_DIR,
            )
        return

    # 2) 目录存在但不是 git 仓库 -> init + fetch + merge
    if not _is_git_repo(OUTPUT_DIR):
        print("[Git] 目录存在但非 git 仓库，执行 init + fetch + merge", flush=True)
        _ensure_git_repo(OUTPUT_DIR)
        _run_git(["fetch", "origin", GIT_BRANCH], cwd=OUTPUT_DIR)
        rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=OUTPUT_DIR)
        if rb and rb.returncode == 0 and rb.stdout.strip():
            _run_git(
                ["merge", "--allow-unrelated-histories", "-X", "ours",
                 f"origin/{GIT_BRANCH}", "-m", "Merge remote content"],
                cwd=OUTPUT_DIR,
            )
        return

    # 3) 已是仓库 -> remote 校正 -> 先提交未提交改动 -> pull --rebase
    _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=OUTPUT_DIR)
    _run_git(["config", "user.email", "auto@experiment.local"], cwd=OUTPUT_DIR)
    _run_git(["config", "user.name",  "auto-experiment"], cwd=OUTPUT_DIR)

    r = _run_git(["status", "--porcelain"], cwd=OUTPUT_DIR)
    if r and r.stdout.strip() and not DRY_RUN:
        print("[Git] 存在本地未提交改动，先 commit 以防丢失", flush=True)
        _run_git(["add", "-A"], cwd=OUTPUT_DIR)
        _run_git(["commit", "-m", "wip: local changes before sync"], cwd=OUTPUT_DIR)

    p = _run_git(["pull", "--rebase", "origin", GIT_BRANCH], cwd=OUTPUT_DIR)
    if p and p.returncode == 0:
        print("[Git] pull --rebase 成功，本地已是最新", flush=True)
        return

    print("[Git] pull --rebase 失败，改用 fetch + merge -X ours", flush=True)
    _run_git(["rebase", "--abort"], cwd=OUTPUT_DIR)
    _run_git(["fetch", "origin", GIT_BRANCH], cwd=OUTPUT_DIR)
    rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=OUTPUT_DIR)
    if rb and rb.returncode == 0 and rb.stdout.strip():
        _run_git(
            ["merge", "--allow-unrelated-histories", "-X", "ours",
             f"origin/{GIT_BRANCH}", "-m", "Sync from remote"],
            cwd=OUTPUT_DIR,
        )


def _git_commit_and_push(repo_dir: Path, message: str, push: bool = True):
    """提交并推送。push 前先 fetch + rebase 避免覆盖远端；rebase 冲突则 abort。"""
    if DRY_RUN:
        return

    with _git_lock:
        _run_git(["add", "-A"], cwd=repo_dir)

        r = _run_git(["status", "--porcelain"], cwd=repo_dir)
        if not (r and r.stdout.strip()):
            return

        c = _run_git(["commit", "-m", message], cwd=repo_dir)
        if not (c and c.returncode == 0):
            err = c.stderr.strip() if c else "unknown"
            print(f"  [警告] git commit 失败: {err}", flush=True)
            return

        if not push:
            return

        _run_git(["fetch", "origin", GIT_BRANCH], cwd=repo_dir)
        rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
        if rb and rb.returncode == 0 and rb.stdout.strip():
            rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
            if not (rbr and rbr.returncode == 0):
                print("  [警告] rebase 冲突，放弃本次 push（本地 commit 保留）", flush=True)
                _run_git(["rebase", "--abort"], cwd=repo_dir)
                return

        p = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=repo_dir)
        if p and p.returncode == 0:
            return

        print("  [警告] push 失败，重试一次…", flush=True)
        _run_git(["fetch", "origin", GIT_BRANCH], cwd=repo_dir)
        rb = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
        if rb and rb.returncode == 0 and rb.stdout.strip():
            rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
            if not (rbr and rbr.returncode == 0):
                _run_git(["rebase", "--abort"], cwd=repo_dir)
                return
        p2 = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=repo_dir)
        if p2 and p2.returncode != 0:
            print(f"  [警告] push 仍然失败: {p2.stderr.strip()}", flush=True)


# ============ 熔断器 ============
class _Breaker:
    """连续 N 次调用彻底失败（超时/异常/空回复）则跳过后续 LLM 调用，
    防止 API Key 失效或断网时在 Kaggle 上空烧会话时长"""

    def __init__(self, threshold: int):
        self.threshold = threshold
        self.consecutive = 0
        self.tripped = False

    def record(self, ok: bool):
        if ok:
            self.consecutive = 0
            return
        self.consecutive += 1
        if self.threshold > 0 and self.consecutive >= self.threshold and not self.tripped:
            self.tripped = True
            print(f"[熔断] 连续 {self.consecutive} 次调用失败，停止后续 LLM 调用"
                  f"（已完成的增量结果仍会推送）", flush=True)


_BREAKER = _Breaker(CIRCUIT_BREAKER)


def _should_skip_write(result: dict) -> bool:
    """熔断已触发且本次又失败 -> 不把 [ERROR] 记录写进 jsonl（避免批量垃圾行）"""
    return _BREAKER.tripped and _is_error_text(result.get("content"))


# ============ LLM 调用 ============
def _error_result(err):
    return {"content": f"[ERROR] {err}", "prompt_tokens": None,
            "completion_tokens": None, "elapsed": None}


async def call_llm(client: AsyncOpenAI, prompt: str, temperature: float = None) -> dict:
    """带超时、退避重试、空回复重试与熔断的 LLM 调用"""
    if temperature is None:
        temperature = POST_TEMPERATURE

    deadline = time.time() + RETRY_TOTAL_BUDGET
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        if time.time() > deadline:
            break
        if _BREAKER.tripped:
            return _error_result("circuit breaker tripped")
        try:
            t0 = time.time()
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                ),
                timeout=PER_CALL_TIMEOUT,
            )
            content = resp.choices[0].message.content
            if not (content or "").strip():
                # 修复点 b)：历史上 8 条盲评因 LLM 返回空字符串而作废 -> 视为失败重试
                last_err = "EmptyResponse"
                _BREAKER.record(False)
                print(f"  [警告] LLM 返回空内容 (attempt {attempt}/{MAX_RETRIES})，视为失败重试",
                      flush=True)
            else:
                _BREAKER.record(True)
                usage = resp.usage
                return {
                    "content": content,
                    "prompt_tokens": usage.prompt_tokens if usage else None,
                    "completion_tokens": usage.completion_tokens if usage else None,
                    "elapsed": round(time.time() - t0, 2),
                }
        except asyncio.TimeoutError:
            last_err = "TimeoutError"
            _BREAKER.record(False)
            print(f"  [警告] 调用超时 (attempt {attempt}/{MAX_RETRIES})", flush=True)
        except Exception as e:
            last_err = str(e)
            _BREAKER.record(False)
            print(f"  [警告] 调用失败 (attempt {attempt}/{MAX_RETRIES}): {e}", flush=True)

        backoff = min(2 ** attempt, 30)
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise

    return _error_result(last_err)


# ============ 缺失分析 ============
def _analyze() -> dict:
    """全量扫描三个 jsonl，计算各阶段的缺口（"缺失"= 键不存在 或 最新记录无效）"""
    all_records = _load_jsonl(RESULTS_PATH)
    valid_results = _latest_valid_by_key(
        all_records, ("task_id", "condition", "run"), _valid_result)
    valid_cleaned = _latest_valid_by_key(
        _load_jsonl(CLEANED_PATH), ("task_id", "run"), _valid_cleaned)
    valid_cmp = _latest_valid_by_key(
        _load_jsonl(COMPARISON_PATH), ("task_id", "run"), _valid_comparison)

    baseline_map, wp_map = _split_conditions(valid_results)

    # 阶段 0 缺口：期望网格 - 有效 results
    expected = {(t, c, r) for t in TASKS_BY_ID for c in CONDITIONS
                for r in range(1, N_RUNS + 1)}
    missing_gen = sorted(expected - set(valid_results))

    # 阶段 1 缺口：已有 word_pairs 生成但尚无有效清洗
    to_clean = [wp_map[k] for k in sorted(wp_map) if k not in valid_cleaned]

    # 阶段 2 缺口：baseline 与有效清洗都齐、但尚无有效盲评
    grid_2 = {(t, r) for t in TASKS_BY_ID for r in range(1, N_RUNS + 1)}
    keys_all = sorted(set(baseline_map) | set(wp_map) | set(valid_cleaned) | grid_2)
    pairs, skip_no_base, skip_no_clean = [], [], []
    for (tid, run) in keys_all:
        if (tid, run) in valid_cmp:
            continue
        if (tid, run) not in baseline_map:
            skip_no_base.append((tid, run))
            continue
        if (tid, run) not in valid_cleaned:
            skip_no_clean.append((tid, run))
            continue
        pairs.append((tid, run, baseline_map[(tid, run)], valid_cleaned[(tid, run)]))

    return {
        "n_results": len(all_records),
        "n_results_valid": len(valid_results),
        "n_cleaned": len(_load_jsonl(CLEANED_PATH)),
        "n_cleaned_valid": len(valid_cleaned),
        "n_cmp": len(_load_jsonl(COMPARISON_PATH)),
        "n_cmp_valid": len(valid_cmp),
        "missing_gen": missing_gen,
        "to_clean": to_clean,
        "pairs": pairs,
        "skip_no_base": skip_no_base,
        "skip_no_clean": skip_no_clean,
        "valid_cmp": valid_cmp,
    }


def _print_missing_report(a: dict):
    print("\n========== 缺失分析 ==========", flush=True)
    total_gen = len(TASKS_BY_ID) * len(CONDITIONS) * N_RUNS
    print(f"results.jsonl   : 共 {a['n_results']} 行，有效 {a['n_results_valid']} / 期望 {total_gen}"
          f" -> 待补生成 {len(a['missing_gen'])} 条", flush=True)
    for k in a["missing_gen"]:
        print(f"    缺生成: task{k[0]} {k[1]} run{k[2]}", flush=True)

    print(f"cleaned.jsonl   : 共 {a['n_cleaned']} 行，有效 {a['n_cleaned_valid']} / 期望 {len(TASKS_BY_ID) * N_RUNS}"
          f" -> 待补清洗 {len(a['to_clean'])} 条", flush=True)
    for r in a["to_clean"]:
        print(f"    缺清洗: task{r['task_id']} run{r['run']}", flush=True)

    print(f"comparison.jsonl: 共 {a['n_cmp']} 行，有效 {a['n_cmp_valid']} / 期望 {len(TASKS_BY_ID) * N_RUNS}"
          f" -> 待补盲评 {len(a['pairs'])} 对", flush=True)
    for (tid, run, _, _) in a["pairs"]:
        print(f"    缺盲评: task{tid} run{run}", flush=True)

    if a["skip_no_base"]:
        print(f"（另有 {len(a['skip_no_base'])} 对因缺 baseline 生成暂无法盲评："
              f"{a['skip_no_base']}）", flush=True)
    if a["skip_no_clean"]:
        print(f"（另有 {len(a['skip_no_clean'])} 对因缺有效清洗暂无法盲评："
              f"{a['skip_no_clean']}，将在阶段 1 补齐后于下次重跑时补评）", flush=True)
    print("=" * 40, flush=True)


# ============ 阶段 0：补生成 ============
def _resolve_gen_prompt(task_id: int, condition: str, all_records: list) -> str:
    """优先复用同 (task, condition) 已有记录的 prompt，保证补生成与原实验完全一致"""
    candidates = [
        r for r in all_records
        if r.get("task_id") == task_id and r.get("condition") == condition and r.get("prompt")
    ]
    if candidates:
        good = [r for r in candidates if _valid_result(r)]
        pick = (good or candidates)[-1]
        return pick["prompt"]
    # 没有任何可参考记录时才走模板兜底（与生成脚本 jvdfka.py 的构造方式一致）
    if condition == "word_pairs":
        return f"{PREFIX}\n{TASKS_BY_ID[task_id]['prompt']}"
    return TASKS_BY_ID[task_id]["prompt"]


async def generate_one(client, semaphore, task, condition, run_idx, prompt) -> dict | None:
    if _BREAKER.tripped:
        print(f"[熔断跳过] task{task['id']} {condition} run{run_idx}", flush=True)
        return None

    async with semaphore:
        result = await call_llm(client, prompt, temperature=GEN_TEMPERATURE)

    if _should_skip_write(result):
        print(f"[熔断跳过写入] task{task['id']} {condition} run{run_idx}", flush=True)
        return None

    record = {
        "task_id": task["id"],
        "task_name": task["name"],
        "condition": condition,
        "run": run_idx,
        "prompt": prompt,
        "content": result["content"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "elapsed": result["elapsed"],
    }

    # 单条 markdown（目录结构与生成脚本一致：task{id}_{name}/{condition}/run_XX.md）
    md_dir = OUTPUT_DIR / f"task{task['id']}_{task['name']}" / condition
    md_dir.mkdir(parents=True, exist_ok=True)
    try:
        (md_dir / f"run_{run_idx:02d}.md").write_text(
            f"# [补] 任务{task['id']} {task['name']} | 条件: {condition} | 第 {run_idx} 次\n\n"
            f"**Prompt:** {prompt}\n\n"
            f"**耗时:** {result['elapsed']}s | "
            f"**tokens:** {result['prompt_tokens']}/{result['completion_tokens']}\n\n"
            f"---\n\n{result['content']}\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"  [警告] 写生成 markdown 失败: {e}", flush=True)

    _append_jsonl(RESULTS_PATH, record)

    ok = _valid_result(record)
    tag = "生成完成" if ok else "生成失败"
    print(f"[{tag}] task{task['id']} {task['name']} | {condition} | "
          f"run {run_idx:2d} | {result['elapsed']}s", flush=True)

    n = _next_commit_count()
    _git_commit_and_push(
        OUTPUT_DIR,
        f"gen: task{task['id']} {condition} run{run_idx} [{n} total]",
        push=(n % GIT_PUSH_INTERVAL == 0),
    )
    return record if ok else None


async def run_generation(missing_gen: list, all_records: list) -> list:
    print(f"\n========== 阶段 0：补生成（{len(missing_gen)} 条） ==========", flush=True)
    if not missing_gen:
        print("[生成] 无缺失，跳过", flush=True)
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    tasks = []
    for (tid, cond, run) in missing_gen:
        task = TASKS_BY_ID.get(tid)
        if not task:
            print(f"  [警告] 未知任务 id={tid}，跳过", flush=True)
            continue
        prompt = _resolve_gen_prompt(tid, cond, all_records)
        tasks.append(generate_one(client, semaphore, task, cond, run, prompt))

    done = [r for r in await asyncio.gather(*tasks) if r]
    _git_commit_and_push(OUTPUT_DIR, f"gen: 阶段0完成，本次补生成 {len(done)} 条", push=True)
    print(f"\n[阶段0完成] 本次补生成 {len(done)} 条", flush=True)
    return done


# ============ 阶段 1：补清洗 ============
async def clean_one(client, semaphore, record) -> dict | None:
    content = record.get("content") or ""
    if not content or content.startswith("[ERROR]"):
        print(f"[跳过清洗] task{record['task_id']} run{record['run']} 无有效内容", flush=True)
        return None

    if _BREAKER.tripped:
        print(f"[熔断跳过] task{record['task_id']} run{record['run']}", flush=True)
        return None

    prompt = CLEAN_PROMPT.format(content=content)

    async with semaphore:
        result = await call_llm(client, prompt, temperature=POST_TEMPERATURE)

    if _should_skip_write(result):
        print(f"[熔断跳过写入] task{record['task_id']} run{record['run']}", flush=True)
        return None

    cleaned_content = (result["content"] or "").strip()

    rec = {
        "task_id": record["task_id"],
        "task_name": record["task_name"],
        "condition": record["condition"],
        "run": record["run"],
        "original_prompt": record["prompt"],
        "original_content": content,
        "cleaned_content": cleaned_content,
        "clean_elapsed": result["elapsed"],
        "clean_prompt_tokens": result["prompt_tokens"],
        "clean_completion_tokens": result["completion_tokens"],
    }

    md_dir = CLEANED_DIR / f"task{record['task_id']}_{record['task_name']}"
    md_dir.mkdir(parents=True, exist_ok=True)
    try:
        (md_dir / f"run_{record['run']:02d}.md").write_text(
            f"# [清洗] 任务{record['task_id']} {record['task_name']} | "
            f"word_pairs | 第 {record['run']} 次\n\n"
            f"**清洗耗时:** {result['elapsed']}s | "
            f"**tokens:** {result['prompt_tokens']}/{result['completion_tokens']}\n\n"
            f"## 原始输出（含词对）\n\n{content}\n\n"
            f"---\n\n## 清洗后输出\n\n{cleaned_content}\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"  [警告] 写清洗 markdown 失败: {e}", flush=True)

    _append_jsonl(CLEANED_PATH, rec)

    ok = _valid_cleaned(rec)
    tag = "清洗完成" if ok else "清洗失败（下次重跑会再试）"
    print(f"[{tag}] 任务{record['task_id']} {record['task_name']} | "
          f"run {record['run']:2d} | {result['elapsed']}s", flush=True)

    n = _next_commit_count()
    _git_commit_and_push(
        OUTPUT_DIR,
        f"clean: task{record['task_id']} word_pairs run{record['run']} "
        f"[{n} total, {result['elapsed']}s]",
        push=(n % GIT_PUSH_INTERVAL == 0),
    )
    return rec if ok else None


async def run_cleaning(records_to_clean: list) -> list:
    print(f"\n========== 阶段 1：补清洗 word_pairs（{len(records_to_clean)} 条） ==========",
          flush=True)
    if not records_to_clean:
        print("[清洗] 无缺失，跳过", flush=True)
        return []

    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    tasks = [clean_one(client, semaphore, r) for r in records_to_clean]
    cleaned = [c for c in await asyncio.gather(*tasks) if c]

    _git_commit_and_push(OUTPUT_DIR, f"clean: 阶段1完成，本次补清洗 {len(cleaned)} 条", push=True)
    print(f"\n[阶段1完成] 本次补清洗 {len(cleaned)} 条", flush=True)
    return cleaned


# ============ 阶段 2：补盲评 ============
def _parse_compare_json(text: str) -> dict | None:
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


async def compare_one(client, semaphore, task, run_idx,
                      baseline_rec, cleaned_rec) -> dict | None:
    baseline_ans = baseline_rec.get("content") or ""
    cleaned_ans = cleaned_rec.get("cleaned_content") or ""

    if not baseline_ans or baseline_ans.startswith("[ERROR]"):
        return None
    if not cleaned_ans or cleaned_ans.startswith("[ERROR]"):
        return None

    if _BREAKER.tripped:
        print(f"[熔断跳过] task{task['id']} run{run_idx}", flush=True)
        return None

    swap = random.random() < 0.5
    if swap:
        ans_a, ans_b = cleaned_ans, baseline_ans
        label_a, label_b = "cleaned_word_pairs", "baseline"
    else:
        ans_a, ans_b = baseline_ans, cleaned_ans
        label_a, label_b = "baseline", "cleaned_word_pairs"

    prompt = COMPARE_PROMPT.format(task=task["prompt"], answer_a=ans_a, answer_b=ans_b)

    async with semaphore:
        result = await call_llm(client, prompt, temperature=POST_TEMPERATURE)

    if _should_skip_write(result):
        print(f"[熔断跳过写入] task{task['id']} run{run_idx}", flush=True)
        return None

    parsed = _parse_compare_json(result["content"] or "")
    winner_raw = winner_label = None
    scores_a = scores_b = reason = None
    if parsed:
        winner_raw = parsed.get("winner")
        scores_a = parsed.get("A")
        scores_b = parsed.get("B")
        reason = parsed.get("reason")
        if winner_raw == "A":
            winner_label = label_a
        elif winner_raw == "B":
            winner_label = label_b
        elif winner_raw == "tie":
            winner_label = "tie"

    rec = {
        "task_id": task["id"],
        "task_name": task["name"],
        "run": run_idx,
        "swap": swap,
        "A_source": label_a,
        "B_source": label_b,
        "baseline_content": baseline_ans,
        "cleaned_content": cleaned_ans,
        "raw_llm_output": result["content"],
        "parsed": parsed,
        "winner_raw": winner_raw,
        "winner_label": winner_label,
        "A_scores": scores_a,
        "B_scores": scores_b,
        "reason": reason,
        "compare_elapsed": result["elapsed"],
        "compare_prompt_tokens": result["prompt_tokens"],
        "compare_completion_tokens": result["completion_tokens"],
    }

    md_dir = COMPARISON_DIR / f"task{task['id']}_{task['name']}"
    md_dir.mkdir(parents=True, exist_ok=True)
    try:
        (md_dir / f"run_{run_idx:02d}.md").write_text(
            f"# [比较] 任务{task['id']} {task['name']} | 第 {run_idx} 次\n\n"
            f"**任务 prompt:** {task['prompt']}\n\n"
            f"**A 来源:** {label_a}  |  **B 来源:** {label_b}  |  **是否交换:** {swap}\n\n"
            f"**Winner（原始 A/B/tie）:** {winner_raw}  |  "
            f"**Winner（条件映射）:** {winner_label}\n\n"
            f"**耗时:** {result['elapsed']}s | "
            f"**tokens:** {result['prompt_tokens']}/{result['completion_tokens']}\n\n"
            f"---\n\n## 回答 A（{label_a}）\n\n{ans_a}\n\n"
            f"---\n\n## 回答 B（{label_b}）\n\n{ans_b}\n\n"
            f"---\n\n## 评审输出\n\n```json\n"
            f"{json.dumps(parsed, ensure_ascii=False, indent=2) if parsed else result['content']}\n```\n\n"
            f"**理由:** {reason}\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"  [警告] 写比较 markdown 失败: {e}", flush=True)

    _append_jsonl(COMPARISON_PATH, rec)

    ok = _valid_comparison(rec)
    tag = "比较完成" if ok else "比较结果无效（下次重跑会再评）"
    print(f"[{tag}] 任务{task['id']} {task['name']} | run {run_idx:2d} | "
          f"winner={winner_label} | {result['elapsed']}s", flush=True)

    n = _next_commit_count()
    _git_commit_and_push(
        OUTPUT_DIR,
        f"cmp: task{task['id']} run{run_idx} winner={winner_label} [{n} total]",
        push=(n % GIT_PUSH_INTERVAL == 0),
    )
    return rec if ok else None


async def run_comparison(pairs: list) -> list:
    print(f"\n========== 阶段 2：补盲评（{len(pairs)} 对） ==========", flush=True)
    if not pairs:
        print("[比较] 无缺失，跳过", flush=True)
        return []

    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    jobs = []
    for task_id, run_i, base_rec, clean_rec in pairs:
        task = TASKS_BY_ID.get(task_id)
        if not task:
            continue
        jobs.append(compare_one(client, semaphore, task, run_i, base_rec, clean_rec))

    results = [r for r in await asyncio.gather(*jobs) if r]

    _git_commit_and_push(OUTPUT_DIR, f"cmp: 阶段2完成，本次补评 {len(results)} 对", push=True)
    print(f"\n[阶段2完成] 本次补评 {len(results)} 对", flush=True)
    return results


# ============ 汇总统计 ============
def print_summary(comparisons: list):
    """汇总统计（输入应传入去重后的有效比较记录）"""
    print("\n========== 汇总统计（全部有效记录） ==========", flush=True)
    if not comparisons:
        print("（无有效比较记录）", flush=True)
        return

    wins = {"baseline": 0, "cleaned_word_pairs": 0, "tie": 0, "unknown": 0}
    for r in comparisons:
        w = r.get("winner_label") or "unknown"
        wins[w] = wins.get(w, 0) + 1

    total = len(comparisons)
    print(f"总比较次数: {total}")
    for k, v in wins.items():
        if v:
            print(f"  {k:20s}: {v:3d}  ({v / max(total, 1) * 100:5.1f}%)")

    print("\n按任务：")
    task_ids = sorted({r["task_id"] for r in comparisons})
    for tid in task_ids:
        rs = [r for r in comparisons if r["task_id"] == tid]
        wb = sum(1 for r in rs if r["winner_label"] == "baseline")
        wc = sum(1 for r in rs if r["winner_label"] == "cleaned_word_pairs")
        wt = sum(1 for r in rs if r["winner_label"] == "tie")
        name = rs[0]["task_name"] if rs else ""
        print(f"  任务{tid} {name:20s} 共{len(rs):3d} | "
              f"baseline 胜 {wb:2d} | cleaned 胜 {wc:2d} | 平 {wt:2d}")

    print("\n平均分（1-10）：")
    print(f"  {'维度':<15s} {'baseline':>10s} {'cleaned':>10s}")
    for key in ["logic", "concreteness", "actionability", "originality", "overall"]:
        base_vals, clean_vals = [], []
        for r in comparisons:
            sa = r.get("A_scores") or {}
            sb = r.get("B_scores") or {}
            if r.get("A_source") == "baseline":
                b, c = sa.get(key), sb.get(key)
            else:
                b, c = sb.get(key), sa.get(key)
            if isinstance(b, (int, float)):
                base_vals.append(b)
            if isinstance(c, (int, float)):
                clean_vals.append(c)
        b_avg = sum(base_vals) / len(base_vals) if base_vals else float("nan")
        c_avg = sum(clean_vals) / len(clean_vals) if clean_vals else float("nan")
        print(f"  {key:<15s} {b_avg:>10.2f} {c_avg:>10.2f}")


def _report_remaining():
    """收尾时重新扫描磁盘，报告仍存在的缺口"""
    a = _analyze()
    print("\n========== 补数后仍剩余的缺口 ==========", flush=True)
    print(f"生成   : 缺 {len(a['missing_gen'])} 条"
          f"{'（OK，已补齐）' if not a['missing_gen'] else ''}", flush=True)
    print(f"清洗   : 缺 {len(a['to_clean'])} 条"
          f"{'（OK，已补齐）' if not a['to_clean'] else ''}", flush=True)
    print(f"盲评   : 缺 {len(a['pairs'])} 对"
          f"{'（OK，已补齐）' if not a['pairs'] else ''}", flush=True)
    blocked = len(a["skip_no_base"]) + len(a["skip_no_clean"])
    if blocked:
        print(f"（另有 {blocked} 对因缺 baseline 生成或有效清洗暂时无法配对盲评）", flush=True)
    if a["missing_gen"] or a["to_clean"] or a["pairs"] or blocked:
        print("提示：直接重跑本脚本即可继续补齐剩余部分（增量、断点续跑）。", flush=True)


# ============ 主流程 ============
def _print_banner():
    print("=" * 60, flush=True)
    print("Kaggle 补数脚本（Gitee 版）：补生成 / 补清洗 / 补盲评", flush=True)
    print("=" * 60, flush=True)
    print(f"运行环境 : {'Kaggle' if IS_KAGGLE else '本地/其他'}")
    print(f"工作目录 : {WORK_DIR}")
    print(f"输出目录 : {OUTPUT_DIR}")
    print(f"模型     : {MODEL} @ {BASE_URL}")
    print(f"并发     : {CONCURRENCY} | 单次超时 {PER_CALL_TIMEOUT}s | "
          f"重试预算 {RETRY_TOTAL_BUDGET}s | 熔断阈值 {CIRCUIT_BREAKER}")
    print(f"期望网格 : {len(TASKS_BY_ID)} 任务 x {len(CONDITIONS)} 条件 x {N_RUNS} run "
          f"= {len(TASKS_BY_ID) * len(CONDITIONS) * N_RUNS} 条")
    print(f"DRY_RUN  : {DRY_RUN} | SKIP_SYNC : {SKIP_SYNC}", flush=True)
    print("=" * 60, flush=True)


async def main():
    _print_banner()

    # 0) 从 Gitee 同步旧内容
    if SKIP_SYNC:
        print("[Git] SKIP_SYNC=1，跳过同步，直接使用本地已有数据", flush=True)
    else:
        _sync_from_gitee()

    if not RESULTS_PATH.exists():
        print(f"[错误] 找不到 {RESULTS_PATH}：请确认 Gitee 仓库 main 分支包含 results.jsonl，"
              f"或先运行生成脚本", flush=True)
        return

    # 1) 缺失分析
    a = _analyze()
    _print_missing_report(a)

    if DRY_RUN:
        print("\n[DRY_RUN] 仅分析模式：未调用 LLM、未写入任何文件、未推送。", flush=True)
        base = len(a["missing_gen"]) + len(a["to_clean"]) + len(a["pairs"])
        # 阶段 0/1 补齐成功后，同一次运行内会解锁更多可配对的盲评
        unlock = len(a["skip_no_base"]) + len(a["skip_no_clean"])
        print(f"按当前数据，本次实际运行预计需要 LLM 调用 {base} 次；"
              f"若前置阶段补齐顺利，最多可到 {base + unlock} 次。", flush=True)
        return

    try:
        # 2) 阶段 0：补生成
        all_records = _load_jsonl(RESULTS_PATH)
        await run_generation(a["missing_gen"], all_records)

        # 阶段 0 可能新增了记录，重新加载再算阶段 1 的缺口
        a = _analyze()
        await run_cleaning(a["to_clean"])

        # 阶段 1 可能新增了有效清洗，重新加载再算阶段 2 的缺口
        a = _analyze()
        await run_comparison(a["pairs"])

        # 3) 汇总（读全量历史，按最新有效去重）
        valid_cmp = _latest_valid_by_key(
            _load_jsonl(COMPARISON_PATH), ("task_id", "run"), _valid_comparison)
        print_summary(list(valid_cmp.values()))

        # 4) 剩余缺口报告
        _report_remaining()
    finally:
        # 5) 最终 push（即使中途异常/熔断，也尽量把已完成的增量推上去）
        _git_commit_and_push(OUTPUT_DIR, "fill: 补数运行结束", push=True)

    print("\n全部完成。", flush=True)


def run_main():
    """兼容脚本 / Jupyter（Kaggle Notebook 的 cell 里已有事件循环时自动切线程）"""
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

    t = threading.Thread(target=_worker, name="llm-fill-missing")
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]


if __name__ == "__main__":
    run_main()

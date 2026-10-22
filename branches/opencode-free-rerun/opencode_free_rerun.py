#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCode 免费模型重跑脚本（Gitee 断点续跑版）
================================================================
用途：把上一轮本地实测过的 11 个 OpenCode 免费模型，在 Kaggle 上每个
模型重跑一遍（并发=1，串行），结果增量推回 Gitee 新分支
opencode-free-rerun 的 opencode_free_results/ 目录。

断点续跑（核心要求）：
  - 每完成一个模型 -> 追加 results.jsonl + raw/*.json -> git commit + push
  - 中途停止（Kaggle 会话超时/手动停止/熔断/时间预算耗尽）后重新运行：
    clone 或 pull 分支 -> 读 results.jsonl -> 跳过已完成模型 -> 继续跑
  - 「已完成」= 该模型存在 status 为 ok / gave_up / 终局性错误 的记录
    （瞬时错误如 429/超时/上游不可用，重跑时会自动重试）

OpenCode 免费层调用要点（逆向自官方客户端，实测有效）：
  - 端点   : POST https://opencode.ai/zen/v1/chat/completions（OpenAI 兼容）
  - 头     : User-Agent: opencode/<ver>
             x-opencode-client: cli / x-opencode-project: global
             x-opencode-session: ses_ + 9位hex + [fc0..fff] + 14位字母数字
             x-opencode-request: msg_<26位hex>
  - 请求体 : 必须 stream=true，且带 bash/read 等真实工具定义
  - 否则 403 FreeTierError（"free tier can only be used from within OpenCode"）

已知模型特性（来自上一轮实测，用于排序与预算）：
  - space-bunny-free 最快且免 Key 可用；glm-5.3-flash-free 偶发 429
  - nemotron-3.5-lightning-free 返回 200 但只发 keep-alive（约 5 分钟）
  - beam-free 区域限制；jev-1.13-free 三种协议均不支持
  （后三个排在队尾，即使失败也不影响前面的进度）

环境变量（可用 Kaggle Secrets 覆盖，见 _get_env）：
  OPENCODE_API_KEY / OPENCODE_BASE_URL / OPENCODE_MODELS（逗号分隔）
  MAX_RETRIES / PER_CALL_TIMEOUT / RETRY_TOTAL_BUDGET / CIRCUIT_BREAKER
  TIME_BUDGET_MIN / GIT_REMOTE_URL / GIT_BRANCH / GIT_PUSH_INTERVAL
  DRY_RUN / SKIP_SYNC / RETRY_GAVE_UP / WORK_DIR
"""

import json
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ============ 运行环境识别 ============
IS_KAGGLE = bool(
    os.environ.get("KAGGLE_KERNEL_RUN_TYPE")
    or os.environ.get("KAGGLE_URL_BASE")
    or os.environ.get("KAGGLE_CONTAINER_ID")
)


def _get_env(name, default=None):
    """读环境变量；Kaggle 上再尝试读同名 Secret；最后用默认值。"""
    val = os.environ.get(name)
    if val:
        return val
    if IS_KAGGLE:
        try:
            from kaggle_secrets import UserSecretsClient  # type: ignore

            try:
                sec = UserSecretsClient().get_secret(name)
                if sec:
                    return sec
            except Exception:
                pass  # 该 Secret 不存在时静默跳过
        except Exception:
            pass  # 无 kaggle_secrets 模块（本地运行）
    return default


# ============ 配置 ============
API_KEY = _get_env(
    "OPENCODE_API_KEY",
    "oc_sk_ff49ac51b5d4_wPFPCGRAKdtqOcz18KA6SB8OrA_8YIg4",
)
BASE_URL = _get_env("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1").rstrip("/")

# 11 个免费模型（可靠→次可靠→已知问题模型，见文件头说明）
DEFAULT_MODELS = ",".join([
    "space-bunny-free",
    "big-pickle",
    "test",
    "deepseek-v4.1-flash-free",
    "longcat-2.5-preview-free",
    "mimo-v2.6-flash-free",
    "nemotron-3.5-super-vl-free",
    "glm-5.3-flash-free",
    "nemotron-3.5-lightning-free",
    "beam-free",
    "jev-1.13-free",
])
MODELS = [m.strip() for m in _get_env("OPENCODE_MODELS", DEFAULT_MODELS).split(",") if m.strip()]

CONCURRENCY = 1  # 需求：串行
MAX_RETRIES = int(_get_env("MAX_RETRIES", "5"))            # 每个模型最多尝试次数
PER_CALL_TIMEOUT = int(_get_env("PER_CALL_TIMEOUT", "90"))  # 单次 socket 读超时(秒)
HARD_READ_LIMIT = int(_get_env("HARD_READ_LIMIT", "420"))   # 单次尝试读流硬上限(秒)
RETRY_TOTAL_BUDGET = int(_get_env("RETRY_TOTAL_BUDGET", "1500"))  # 单模型重试总预算(秒)
BACKOFFS = [5, 10, 20, 40, 60]                                # 重试退避
CIRCUIT_BREAKER = int(_get_env("CIRCUIT_BREAKER", "5"))     # 连续终局失败熔断阈值
TIME_BUDGET_MIN = int(_get_env("TIME_BUDGET_MIN", "600"))   # 总时间预算(分钟)
DRY_RUN = _get_env("DRY_RUN", "").lower() not in ("", "0", "false", "no")
SKIP_SYNC = _get_env("SKIP_SYNC", "").lower() not in ("", "0", "false", "no")
RETRY_GAVE_UP = _get_env("RETRY_GAVE_UP", "").lower() not in ("", "0", "false", "no")

WORK_DIR = Path(_get_env("WORK_DIR", "/kaggle/working" if IS_KAGGLE else "."))

# ============ Git 配置 ============
GIT_REMOTE_URL = _get_env(
    "GIT_REMOTE_URL",
    "https://gitee.com/qwe12345678/jkdsfn.git",
)
GIT_BRANCH = _get_env("GIT_BRANCH", "opencode-free-rerun")
GIT_PUSH_INTERVAL = int(_get_env("GIT_PUSH_INTERVAL", "1"))  # 每个模型完成即 push
GIT_USER_EMAIL = _get_env("GIT_USER_EMAIL", "auto@experiment.local")
GIT_USER_NAME = _get_env("GIT_USER_NAME", "auto-experiment")

REPO_DIR = WORK_DIR / "jkdsfn"
OUTPUT_DIR = REPO_DIR / "opencode_free_results"
RESULTS_PATH = OUTPUT_DIR / "results.jsonl"
RAW_DIR = OUTPUT_DIR / "raw"

# ============ 实验参数（与上一轮实测一致，保证可比） ============
PROMPT = "Say OK and nothing else."
MAX_TOKENS = 300
OPENCODE_UA = _get_env("OPENCODE_UA", "opencode/1.18.34")

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a bash command",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read", "description": "Read a file",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "edit", "description": "Edit a file",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "glob", "description": "Glob files",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "grep", "description": "Grep files",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}}}},
]

# 终局性错误：重试无意义，直接记为完成
DEFINITIVE_ERRORS = {
    "RegionError",               # 区域限制
    "ModelProtocolUnsupported",  # 协议不支持
    "InsufficientFunds",         # 余额不足（不该出现在免费模型上）
    "AuthError",                 # Key 无效
    "FreeTierError",             # 客户端头失效（配置问题，重试无解）
    "ModelError",
}

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============ OpenCode 免费层调用 ============
def _gen_ses():
    """ses_ + 9位hex + [fc0..fff](低12位须落在此区间) + 14位字母数字。每次请求新造。"""
    tail = secrets.choice(["fc0", "fcf", "fd0", "fe0", "ff0", "ffc", "fff"])
    head9 = "".join(secrets.choice("0123456789abcdef") for _ in range(9))
    alnum14 = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
    return "ses_" + head9 + tail + alnum14


def _build_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": OPENCODE_UA,
        "x-opencode-client": "cli",
        "x-opencode-project": "global",
        "x-opencode-session": _gen_ses(),
        "x-opencode-request": "msg_" + secrets.token_hex(13),
        "Accept": "text/event-stream",
    }


def _classify_error(status_code, body_text):
    """从 HTTP 错误响应里提取 (error_type, message, is_definitive)。"""
    etype, message = "HTTPError", (body_text or "")[:200]
    try:
        j = json.loads(body_text)
        err = j.get("error") or j.get("type") or {}
        if isinstance(err, dict):
            etype = err.get("type", etype)
            message = err.get("message", message)
        elif isinstance(err, str):
            message = err
        if not etype or etype == "HTTPError":
            etype = j.get("type", etype)
    except Exception:
        pass
    if status_code == 429 or "unavailable" in message.lower():
        # 上游容量/端点不可用 -> 瞬时
        if etype not in DEFINITIVE_ERRORS:
            etype = "Transient429" if status_code == 429 else "EndpointUnavailable"
    return etype, message, etype in DEFINITIVE_ERRORS


def single_call(model, attempt):
    """对单个模型做一次流式调用。返回结果 dict（不含 model 公共字段）。

    返回:
      ok=True:  {ok, reply, reasoning, finish_reason, usage, elapsed_s, sse_head}
      ok=False: {ok=False, http_status, error_type, error_message, is_definitive, elapsed_s, sse_head}
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": True,
        "max_tokens": MAX_TOKENS,
        "tools": TOOLS,
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers=_build_headers(),
        method="POST",
    )
    start = time.time()
    sse_head, head_len = [], 0
    try:
        with urllib.request.urlopen(req, timeout=PER_CALL_TIMEOUT) as resp:
            content_parts, reasoning_parts, usage, finish = [], [], {}, None
            for raw in resp:
                if time.time() - start > HARD_READ_LIMIT:
                    return {"ok": False, "http_status": 200, "error_type": "StreamTimeout",
                            "error_message": f"读流超过 {HARD_READ_LIMIT}s 硬上限（疑似 keep-alive 空转）",
                            "is_definitive": False, "elapsed_s": round(time.time() - start, 1),
                            "sse_head": "\n".join(sse_head)[:2000]}
                line = raw.decode("utf-8", "ignore").strip()
                if not line:
                    continue
                if head_len < 1600:
                    sse_head.append(line[:200])
                    head_len += len(line[:200])
                if not line.startswith("data:"):
                    continue  # keep-alive 注释行等
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except Exception:
                    continue
                if chunk.get("error"):
                    etype, msg = chunk["error"].get("type", "StreamError"), chunk["error"].get("message", "")
                    return {"ok": False, "http_status": 200, "error_type": etype,
                            "error_message": msg[:200], "is_definitive": etype in DEFINITIVE_ERRORS,
                            "elapsed_s": round(time.time() - start, 1),
                            "sse_head": "\n".join(sse_head)[:2000]}
                usage = chunk.get("usage") or usage
                for ch in chunk.get("choices", []):
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        content_parts.append(d["content"])
                    if d.get("reasoning_content") or d.get("reasoning"):
                        reasoning_parts.append(str(d.get("reasoning_content") or d.get("reasoning")))
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
            return {
                "ok": True,
                "reply": "".join(content_parts)[:500],
                "reasoning": bool(reasoning_parts),
                "finish_reason": finish,
                "usage": usage,
                "elapsed_s": round(time.time() - start, 1),
                "sse_head": "\n".join(sse_head)[:2000],
            }
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        etype, msg, definitive = _classify_error(e.code, body)
        return {"ok": False, "http_status": e.code, "error_type": etype,
                "error_message": msg[:200], "is_definitive": definitive,
                "elapsed_s": round(time.time() - start, 1), "sse_head": "\n".join(sse_head)[:2000]}
    except Exception as e:
        return {"ok": False, "http_status": None, "error_type": type(e).__name__,
                "error_message": str(e)[:200], "is_definitive": False,
                "elapsed_s": round(time.time() - start, 1), "sse_head": "\n".join(sse_head)[:2000]}


def run_one_model(model):
    """带重试地跑一个模型（串行，每模型各一遍）。返回最终记录 dict。"""
    budget_end = time.time() + RETRY_TOTAL_BUDGET
    attempts = 0
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        if time.time() > budget_end:
            log(f"    [预算] {model} 重试总预算耗尽，停止尝试")
            break
        attempts = attempt
        log(f"    [尝试 {attempt}/{MAX_RETRIES}] {model} 调用中 …")
        r = single_call(model, attempt)
        last = r
        # 保存每次尝试的原始数据（小文件，便于排查）
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{model}_try{attempt}.json"
        (RAW_DIR / raw_name).write_text(
            json.dumps({"model": model, "attempt": attempt, "result": r}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        if r["ok"]:
            log(f"    [成功] {model} 用时 {r['elapsed_s']}s 回复: {r['reply'][:40]!r}")
            break
        tag = "终局" if r["is_definitive"] else "瞬时"
        log(f"    [失败/{tag}] {model} {r['error_type']}: {r['error_message'][:80]}")
        if r["is_definitive"]:
            break
        if attempt < MAX_RETRIES:
            wait = BACKOFFS[min(attempt - 1, len(BACKOFFS) - 1)]
            log(f"    [退避] {wait}s 后重试")
            time.sleep(wait)
    status = "ok" if (last and last["ok"]) else (
        "error_definitive" if (last and last.get("is_definitive")) else "gave_up")
    if not last:
        last = {"ok": False, "error_type": "NoBudget", "error_message": "未及调用即超出预算",
                "is_definitive": True, "elapsed_s": 0, "http_status": None, "sse_head": ""}
    rec = {
        "model": model,
        "run": 1,
        "status": status,
        "attempts": attempts,
        "http_status": last.get("http_status"),
        "error_type": None if last["ok"] else last.get("error_type"),
        "error_message": None if last["ok"] else last.get("error_message"),
        "reply": last.get("reply"),
        "reasoning": last.get("reasoning", False),
        "finish_reason": last.get("finish_reason"),
        "usage": last.get("usage"),
        "elapsed_s": last.get("elapsed_s"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return rec


# ============ JSONL 增量读写 ============
def append_jsonl(path, record):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path):
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
                log(f"  [警告] 解析 {path.name} 某行失败: {e}")
    return out


def is_final_record(rec):
    """该记录是否代表此模型已完成（重跑时跳过）。

    ok / error_definitive -> 永远视为完成；
    gave_up -> 默认视为完成（每模型各跑一遍即可）；
                RETRY_GAVE_UP=1 时视为未完成，重跑会重试这类模型。
    """
    if rec.get("model") is None or rec.get("run") != 1:
        return False
    if rec.get("status") in ("ok", "error_definitive"):
        return True
    if rec.get("status") == "gave_up":
        return not RETRY_GAVE_UP
    return False


# ============ Git 工具 ============
def _run_git(args, cwd=None, timeout=300):
    try:
        return subprocess.run(["git"] + args, cwd=str(cwd) if cwd else None,
                              capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        log("  [警告] 未找到 git 命令，跳过自动提交")
        return None
    except subprocess.TimeoutExpired:
        log(f"  [警告] git {' '.join(args)} 超时")
        return None
    except Exception as e:
        log(f"  [警告] git 执行异常: {e}")
        return None


def _ok(r):
    return r is not None and r.returncode == 0


def _apply_git_tweaks():
    """针对 Kaggle（美国出口）访问 gitee.com 偶发 SSL 挂起的加固：
    - 强制 HTTP/1.1（HTTP/2 在部分链路上会挂起）
    - 低速断线保护：低于 1000 B/s 持续 120s 则主动失败转为可重试错误，避免无限挂起
    """
    for k, v in [
        ("http.version", "HTTP/1.1"),
        ("http.postBuffer", "524288000"),
        ("http.lowSpeedLimit", "1000"),
        ("http.lowSpeedTime", "120"),
    ]:
        _run_git(["config", "--global", k, v])


def _fetch_origin(retries=2, wait=15):
    """带重试的 fetch（网络抖动时多试几次）。"""
    for i in range(1, retries + 1):
        r = _run_git(["fetch", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
        if _ok(r):
            return True
        if i < retries:
            log(f"  [警告] fetch 失败（第 {i} 次），{wait}s 后重试: {(r.stderr if r else '')[:120]}")
            time.sleep(wait)
    return False


CLONE_ATTEMPTS = int(_get_env("CLONE_ATTEMPTS", "4"))  # clone 失败重试次数（后几次降级为浅克隆）


def sync_from_gitee():
    """把远端分支同步到本地 REPO_DIR（不存在则 clone，失败重试+浅克隆降级；已存在则先兜底提交再 rebase）。"""
    _apply_git_tweaks()
    if SKIP_SYNC:
        log("[Git] SKIP_SYNC=1，跳过同步（本地调试用）")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return
    if not (REPO_DIR / ".git").exists():
        REPO_DIR.mkdir(parents=True, exist_ok=True)
        log(f"[Git] clone {GIT_BRANCH} 分支 …")
        last_err = ""
        for attempt in range(1, CLONE_ATTEMPTS + 1):
            # 第 1 次完整克隆（--single-branch 只拉目标分支，减小传输量）；
            # 之后降级为 --depth 1 浅克隆（只需最新快照，速度最快）
            if attempt == 1:
                args = ["clone", "--single-branch", "-b", GIT_BRANCH, GIT_REMOTE_URL, str(REPO_DIR)]
            else:
                args = ["clone", "--depth", "1", "--single-branch", "-b", GIT_BRANCH,
                        GIT_REMOTE_URL, str(REPO_DIR)]
            r = _run_git(args, timeout=900)
            if _ok(r):
                log(f"[Git] clone 成功（第 {attempt} 次尝试） → {REPO_DIR}")
                break
            last_err = (r.stderr if r else "")[-200:]
            log(f"  [警告] clone 第 {attempt} 次失败: {last_err[-120:]}")
            shutil.rmtree(REPO_DIR, ignore_errors=True)  # 清理半成品目录
            REPO_DIR.mkdir(parents=True, exist_ok=True)
            if attempt < CLONE_ATTEMPTS:
                wait = 20 * attempt
                log(f"  [重试] {wait}s 后再次尝试{'（浅克隆）' if attempt >= 1 else ''} …")
                time.sleep(wait)
        else:
            raise RuntimeError(f"clone 连续 {CLONE_ATTEMPTS} 次失败: {last_err}")
        _config_identity()
        return
    # 已存在仓库：校正 remote -> 兜底提交未提交改动 -> fetch + rebase
    _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=REPO_DIR)
    _config_identity()
    st = _run_git(["status", "--porcelain"], cwd=REPO_DIR)
    if st and st.stdout.strip():
        _run_git(["add", "-A"], cwd=REPO_DIR)
        _run_git(["commit", "-m", "wip: 自动保存未提交进度"], cwd=REPO_DIR)
        log("[Git] 发现未提交改动，已自动提交")
    _fetch_origin(retries=2)
    _run_git(["checkout", "-B", GIT_BRANCH, f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    r = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    if _ok(r):
        log("[Git] rebase 同步完成，本地已是最新")
    else:
        _run_git(["rebase", "--abort"], cwd=REPO_DIR)
        log("[Git] rebase 冲突，已 abort 并保留本地提交（稍后 push 时再合并）")


def _config_identity():
    _run_git(["config", "user.email", GIT_USER_EMAIL], cwd=REPO_DIR)
    _run_git(["config", "user.name", GIT_USER_NAME], cwd=REPO_DIR)


_commit_counter = 0


def git_commit_and_push(message, push=True):
    """提交 REPO_DIR 全部改动；push 前先 fetch+rebase，冲突则放弃本次 push（保留本地）。"""
    global _commit_counter
    _commit_counter += 1
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _run_git(["add", "-A"], cwd=REPO_DIR)
    st = _run_git(["status", "--porcelain"], cwd=REPO_DIR)
    if not (st and st.stdout.strip()):
        return  # 无改动
    r = _run_git(["commit", "-m", message], cwd=REPO_DIR)
    if not _ok(r):
        log(f"  [警告] commit 失败: {(r.stderr if r else '')[:150]}")
        return
    if not push:
        return
    if not _fetch_origin(retries=2):
        log("  [警告] fetch 失败，放弃本次 push（本地 commit 保留，下次再推）")
        return
    rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    if not _ok(rbr):
        _run_git(["rebase", "--abort"], cwd=REPO_DIR)
        log("  [警告] rebase 冲突，放弃本次 push（本地 commit 保留，下次再推）")
        return
    p = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
    if not _ok(p):
        log("  [警告] push 失败，重试一次 …")
        time.sleep(15)
        if not _fetch_origin(retries=1):
            return
        rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
        if not _ok(rbr):
            _run_git(["rebase", "--abort"], cwd=REPO_DIR)
            return
        p2 = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
        if not _ok(p2):
            log(f"  [警告] push 仍失败: {(p2.stderr if p2 else '')[:150]}")


# ============ 主流程 ============
def analyze_progress():
    """返回 (done_models, todo_models)。已完成以最新一条记录为准。"""
    records = load_jsonl(RESULTS_PATH)
    latest = {}
    for rec in records:
        latest[rec.get("model")] = rec  # 后写的覆盖先写的
    done, todo = [], []
    for m in MODELS:
        rec = latest.get(m)
        if rec and is_final_record(rec):
            done.append(m)
        else:
            todo.append(m)
    return done, todo, latest


def write_summary():
    """写 summary_<ts>.txt（每次运行结束都生成，只新增不覆盖）。"""
    done, todo, latest = analyze_progress()
    lines = [
        "=" * 62,
        f"OpenCode 免费模型重跑 summary  @ {datetime.now(timezone.utc).isoformat()}",
        f"分支: {GIT_BRANCH}   目录: opencode_free_results/",
        "=" * 62,
        f"{'模型':<34}{'状态':<16}{'尝试':<4}{'耗时':<8}回复/错误",
        "-" * 62,
    ]
    for m in MODELS:
        rec = latest.get(m)
        if not rec:
            lines.append(f"{m:<34}{'未运行':<16}")
            continue
        status = rec.get("status", "?")
        if status == "ok":
            tail = (rec.get("reply") or "")[:30]
        else:
            tail = f"{rec.get('error_type')}: {(rec.get('error_message') or '')[:40]}"
        lines.append(f"{m:<34}{status:<16}{rec.get('attempts', '?'):<4}{str(rec.get('elapsed_s', '?')):<8}{tail}")
    lines += ["-" * 62, f"已完成 {len(done)}/{len(MODELS)}，未完成 {len(todo)}: {', '.join(todo) or '无'}"]
    txt = "\n".join(lines)
    path = OUTPUT_DIR / f"summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    path.write_text(txt, encoding="utf-8")
    print(txt)
    return path


def main():
    t_start = time.time()
    log(f"=== OpenCode 免费模型重跑 | 并发=1 | 分支 {GIT_BRANCH} ===")
    log(f"运行环境: {'Kaggle' if IS_KAGGLE else '本地'}  WORK_DIR={WORK_DIR}  DRY_RUN={DRY_RUN}")

    # 1) 同步远端进度
    sync_from_gitee()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 2) 分析已完成/待跑
    done, todo, latest = analyze_progress()
    log(f"[进度] 已完成 {len(done)}/{len(MODELS)}: {', '.join(done) or '无'}")
    log(f"[进度] 本次待跑 {len(todo)}: {', '.join(todo) or '无'}")

    if DRY_RUN:
        log("[DRY_RUN] 仅分析模式：不调用、不写入、不推送。")
        return

    # 3) 串行逐模型执行
    n_done_this_run = 0
    n_consecutive_fail = 0
    stopped_reason = None
    try:
        for i, model in enumerate(todo, 1):
            elapsed_min = (time.time() - t_start) / 60
            remaining_min = TIME_BUDGET_MIN - elapsed_min
            if remaining_min <= 10:
                stopped_reason = f"总时间预算将耗尽（已用 {elapsed_min:.0f}min / 预算 {TIME_BUDGET_MIN}min）"
                log(f"[停止] {stopped_reason}，干净收尾，下次运行可续跑")
                break
            log(f"\n===== [{i}/{len(todo)}] {model} =====")
            rec = run_one_model(model)
            append_jsonl(RESULTS_PATH, rec)
            n_done_this_run += 1
            push_now = (n_done_this_run % GIT_PUSH_INTERVAL == 0)
            git_commit_and_push(
                f"opencode-free: {model} -> {rec['status']}"
                f" [{len(done) + n_done_this_run}/{len(MODELS)} total]",
                push=push_now,
            )
            # 熔断器：连续终局失败过多则停
            if rec["status"] == "ok":
                n_consecutive_fail = 0
            else:
                n_consecutive_fail += 1
                if n_consecutive_fail >= CIRCUIT_BREAKER:
                    stopped_reason = f"连续 {n_consecutive_fail} 个模型终局失败，触发熔断"
                    log(f"[停止] {stopped_reason}")
                    break
    except KeyboardInterrupt:
        stopped_reason = "手动中断 (KeyboardInterrupt)"
        log(f"[停止] {stopped_reason}，已完成的模型均已提交")
    finally:
        # 4) 无论正常结束/中断/熔断，都做最终提交与推送（保住进度）
        try:
            summary_path = write_summary()
            git_commit_and_push(
                f"opencode-free: 运行结束 (本次完成 {n_done_this_run} 个"
                f"{', 原因: ' + stopped_reason if stopped_reason else ''})",
                push=True,
            )
            log("[Git] 最终 commit + push 完成，进度已保存到 Gitee")
        except Exception as e:
            log(f"[警告] 收尾阶段异常（进度可能已部分保存）: {e}")

    # 5) 结束报告
    done2, todo2, _ = analyze_progress()
    log(f"\n=== 结束 === 本次运行完成 {n_done_this_run} 个模型"
        f"{'; 提前停止: ' + stopped_reason if stopped_reason else ''}")
    log(f"总进度: {len(done2)}/{len(MODELS)} 已完成，剩余: {', '.join(todo2) or '无（全部完成）'}")
    if todo2:
        log("提示: 重新运行本 Notebook（或脚本）即可从断点继续，已完成的模型不会重跑。")


if __name__ == "__main__":
    main()

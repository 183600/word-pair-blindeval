#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCode 免费模型实验重跑（Gitee 断点续跑版）
================================================================
重跑什么：仓库 jkdsfn「之前的实验」——即 Kaggle notebooka6f1f91666
（补数脚本，基于 vfdjk.py/jvdfka.py）的三阶段流水线，但把实验 LLM
换成 OpenCode 的每一个免费模型，每个模型各自完整跑一遍：

  阶段 0 生成：6 任务 × 2 条件(baseline / word_pairs) × N_RUNS 次
               -> <model>/results.jsonl + task{id}_{name}/{cond}/run_XX.md
  阶段 1 清洗：word_pairs 输出去掉开头词对
               -> <model>/cleaned.jsonl + cleaned/task{id}_{name}/run_XX.md
  阶段 2 盲评：清洗后 vs baseline，随机交换 A/B 位置，5 维打分
               -> <model>/comparison.jsonl + comparison/task{id}_{name}/run_XX.md

任务表 / 前缀指令 / 清洗与盲评 Prompt 模板 / 温度(0.6/0.3) 与原实验完全
一致（本文件内置一份，Notebook 启动时会优先从 Kaggle API 拉取之前的
实验代码提取定义并校验一致，见 PREV_DEFS_JSON）。

与原实验的必要差异（由 OpenCode 免费层强制造成，均已实测验证）：
  - 传输层：必须 stream=true + 携带 bash/read 等真实工具定义 +
    x-opencode-* 客户端头，否则 403 FreeTierError
  - tool_choice="none" + 直答系统提示：抑制"工具调用倾向"
    （否则模型想去跑 bash 而不直接回答）
  - max_tokens=16000（推理型模型会先烧推理 token，4k 会导致正文为空；
    glm-5.3-flash-free 单独 32000，且任何模型遇到"推理烧光"自动升档重试）
  - 每模型结果写入独立命名空间 llm_experiment_results_opencode/<model>/

断点续跑（核心要求）：
  - 每完成一条记录 -> 追加 jsonl + 写 markdown -> git commit + push
  - 中途停止（会话超时/手动停止/熔断/预算耗尽）后重新运行：
    clone/pull 分支 -> 逐模型分析缺口 -> 跳过已完成记录 -> 继续补
  - 「已完成」= 该键最新一条记录有效（内容非空且非 [ERROR]；
    盲评 winner_label 合法）。失败记录写 [ERROR]，下次重跑自动重做
  - 连续终局失败(协议不支持等) >= 5 -> 该模型标记 gave_up，以后跳过

预算与保护：
  - 单条记录重试预算 ITEM_RETRY_BUDGET；单模型每会话 PER_MODEL_BUDGET_MIN；
    整个会话 TIME_BUDGET_MIN（到点干净收尾并 push，防被 Kaggle 硬杀）
  - 熔断：连续 CIRCUIT_BREAKER 条彻底失败 -> 跳过当前模型
  - git 加固：HTTP/1.1 + lowSpeed 保护 + clone 重试 + 浅克隆降级
    （解决 Kaggle(美国出口) -> gitee.com 偶发 SSL 挂起）

环境变量（Kaggle Secrets 可覆盖，见 _get_env）：
  OPENCODE_API_KEY / OPENCODE_BASE_URL / OPENCODE_MODELS(逗号分隔)
  N_RUNS / MAX_TOKENS / PER_MODEL_BUDGET_MIN / TIME_BUDGET_MIN
  MAX_RETRIES / ITEM_RETRY_BUDGET / CIRCUIT_BREAKER / INTER_CALL_SLEEP
  GIT_REMOTE_URL / GIT_BRANCH / GIT_PUSH_INTERVAL / WORK_DIR
  PREV_DEFS_JSON(之前实验定义文件，由 Notebook 从 Kaggle 拉取生成)
  DRY_RUN / SKIP_SYNC / RETRY_GAVE_UP / MODELS_LIMIT(只跑前 N 个模型)
"""

import json
import os
import random
import re
import secrets
import shutil
import string
import subprocess
import sys
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
            pass
    return default


# ============ OpenCode 配置 ============
API_KEY = _get_env("OPENCODE_API_KEY",
                   "oc_sk_ff49ac51b5d4_wPFPCGRAKdtqOcz18KA6SB8OrA_8YIg4")
BASE_URL = _get_env("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1").rstrip("/")
OPENCODE_UA = _get_env("OPENCODE_UA", "opencode/1.18.34")

# 模型顺序：可靠/快 -> 慢 -> 已知问题（上一轮 Kaggle 实测排序）
DEFAULT_MODELS = ",".join([
    "space-bunny-free",             # ~40s/次，最快
    "deepseek-v4.1-flash-free",     # ~60s/次
    "glm-5.3-flash-free",           # 偶发429；推理重，需32k
    "test",                         # 偶发503，重试可过
    "mimo-v2.6-flash-free",         # ~112s/次
    "longcat-2.5-preview-free",     # ~126s/次
    "big-pickle",                   # ~190s/次
    "nemotron-3.5-super-vl-free",   # ~208s/次
    "beam-free",                    # 仅美国出口可用(Kaggle OK)
    "nemotron-3.5-lightning-free",  # 排队慢
    "jev-1.13-free",                # 协议不支持 -> 快速 gave_up
])
MODELS = [m.strip() for m in _get_env("OPENCODE_MODELS", DEFAULT_MODELS).split(",") if m.strip()]
MODELS_LIMIT = int(_get_env("MODELS_LIMIT", "0"))  # >0 时只跑前 N 个（测试用）

# ============ 实验参数（与原实验一致） ============
N_RUNS = int(_get_env("N_RUNS", "10"))
CONDITIONS = ("baseline", "word_pairs")
GEN_TEMPERATURE = float(_get_env("GEN_TEMPERATURE", "0.6"))    # 原生成脚本 jvdfka.py
POST_TEMPERATURE = float(_get_env("POST_TEMPERATURE", "0.3"))  # 原后处理 vfdjk.py

# ============ 传输参数（免费层要求 + 标定结论） ============
MAX_TOKENS = int(_get_env("MAX_TOKENS", "16000"))
MODEL_MAX_TOKENS = {"glm-5.3-flash-free": 32000}   # 推理烧 token 最重
PER_CALL_TIMEOUT = int(_get_env("PER_CALL_TIMEOUT", "120"))   # socket 超时
HARD_READ_LIMIT = int(_get_env("HARD_READ_LIMIT", "1500"))    # 单次读流硬上限(秒)
MAX_RETRIES = int(_get_env("MAX_RETRIES", "6"))
BACKOFFS = [5, 15, 30, 60, 120, 180]
ITEM_RETRY_BUDGET = int(_get_env("ITEM_RETRY_BUDGET", "4500"))  # 单条记录重试总预算(秒)
CIRCUIT_BREAKER = int(_get_env("CIRCUIT_BREAKER", "5"))         # 连续失败熔断(每模型)
GAVE_UP_DEFINITIVE = int(_get_env("GAVE_UP_DEFINITIVE", "5"))   # 连续终局失败->永久放弃
INTER_CALL_SLEEP = float(_get_env("INTER_CALL_SLEEP", "3"))

# ============ 预算 ============
PER_MODEL_BUDGET_MIN = float(_get_env("PER_MODEL_BUDGET_MIN", "240"))  # 每模型每会话
TIME_BUDGET_MIN = float(_get_env("TIME_BUDGET_MIN", "600"))           # 整个会话

DRY_RUN = _get_env("DRY_RUN", "").lower() not in ("", "0", "false", "no")
SKIP_SYNC = _get_env("SKIP_SYNC", "").lower() not in ("", "0", "false", "no")
RETRY_GAVE_UP = _get_env("RETRY_GAVE_UP", "").lower() not in ("", "0", "false", "no")

WORK_DIR = Path(_get_env("WORK_DIR", "/kaggle/working" if IS_KAGGLE else "."))

# ============ Git 配置 ============
GIT_REMOTE_URL = _get_env(
    "GIT_REMOTE_URL",
    "https://gitee.com/qwe12345678/jkdsfn.git",
)
GIT_BRANCH = os.environ.get("GIT_BRANCH", "opencode-experiment-rerun")
GIT_PUSH_INTERVAL = int(_get_env("GIT_PUSH_INTERVAL", "1"))  # 每条记录即 push（断点安全）
GIT_USER_EMAIL = _get_env("GIT_USER_EMAIL", "auto@experiment.local")
GIT_USER_NAME = _get_env("GIT_USER_NAME", "auto-experiment")
CLONE_ATTEMPTS = int(_get_env("CLONE_ATTEMPTS", "5"))
CLONE_WAITS = [15, 30, 60, 120]          # clone 失败重试间隔（curl 自身 300s 连接超时）
GIT_PUSH_FAIL_STREAK_LIMIT = 3           # git push 连续失败 N 次后降级 API 模式

REPO_DIR = WORK_DIR / "jkdsfn"
EXP_ROOT = REPO_DIR / "llm_experiment_results_opencode"
PREV_DEFS_JSON = _get_env("PREV_DEFS_JSON", "")  # Notebook 从 Kaggle 拉取的原实验定义

_print_lock = __import__("threading").Lock()


def log(msg):
    with _print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ============ 实验定义（与之前实验 notebooka6f1f91666 完全一致） ============
# 内置一份兜底副本；Notebook 启动时会从 Kaggle API 拉取之前的实验代码，
# 提取定义写入 PREV_DEFS_JSON，此处优先加载并校验一致（保证是"重跑"）。
_TASKS_BY_ID = {
    1: {"id": 1, "name": "函数式编程语言", "prompt": "设计一个全新的函数式编程语言"},
    2: {"id": 2, "name": "提升LLM性能",   "prompt": "怎么低成本不需要额外训练大幅提升现有LLM的性能"},
    3: {"id": 3, "name": "CLI工具Idea",   "prompt": "给出适合独立开发者开发CLI工具的一个Idea"},
    4: {"id": 4, "name": "新理论",        "prompt": "提出一个新的理论"},
    5: {"id": 5, "name": "人格模型",      "prompt": "提出一个新的类似于九型和荣格八维的模型"},
    6: {"id": 6, "name": "ML架构",        "prompt": "提出一个新的机器学习架构"},
}

_PREFIX = "在回答前面输出200组词，每组有两个词，从这些词获得灵感"

_CLEAN_PROMPT = """下面是一段 LLM 的输出，它的开头先输出了很多组词对（每组两个词），
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

_COMPARE_PROMPT = """你是一位严谨、公正的评审专家。下面有两个针对同一任务的回答（A 和 B）。
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


def load_experiment_defs():
    """加载实验定义。优先 PREV_DEFS_JSON（来自 Kaggle 拉取的之前实验代码），
    校验失败或文件不存在则回退内置副本。返回 (tasks, prefix, clean_p, cmp_p, note)。"""
    tasks, prefix, clean_p, cmp_p = _TASKS_BY_ID, _PREFIX, _CLEAN_PROMPT, _COMPARE_PROMPT
    note = "内置副本"
    if PREV_DEFS_JSON and Path(PREV_DEFS_JSON).exists():
        try:
            d = json.loads(Path(PREV_DEFS_JSON).read_text(encoding="utf-8"))
            t = {int(k): v for k, v in d["tasks"].items()}
            assert len(t) == 6 and all(
                t[i]["name"] == _TASKS_BY_ID[i]["name"] and t[i]["prompt"] == _TASKS_BY_ID[i]["prompt"]
                for i in t if i in _TASKS_BY_ID), "任务表与内置副本不一致"
            assert d["prefix"] == _PREFIX, "PREFIX 与内置副本不一致"
            assert d["clean_prompt"] == _CLEAN_PROMPT, "CLEAN_PROMPT 与内置副本不一致"
            assert d["compare_prompt"] == _COMPARE_PROMPT, "COMPARE_PROMPT 与内置副本不一致"
            assert int(d.get("n_runs", N_RUNS)) == N_RUNS, "N_RUNS 与之前实验不一致"
            tasks, prefix, clean_p, cmp_p = t, d["prefix"], d["clean_prompt"], d["compare_prompt"]
            note = f"Kaggle 拉取的定义（{d.get('source', '?')}，校验一致）"
        except Exception as e:
            note = f"PREV_DEFS_JSON 校验失败({e})，改用内置副本"
    return tasks, prefix, clean_p, cmp_p, note


TASKS_BY_ID, PREFIX, CLEAN_PROMPT, COMPARE_PROMPT, DEFS_NOTE = load_experiment_defs()

# 测试用：TASKS_LIMIT>0 时只跑前 N 个任务（先完整校验定义再截取）
TASKS_LIMIT = int(_get_env("TASKS_LIMIT", "0"))
if TASKS_LIMIT > 0:
    TASKS_BY_ID = {k: v for k, v in TASKS_BY_ID.items() if k <= TASKS_LIMIT}

# 免费层强制 tools + tool_choice=none + 直答系统提示（标定实测，防止模型跑去调工具）
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
TOOL_CHOICE = "none"
SYS_DIRECT = ("You are in direct-answer mode. Do NOT call any tools. "
              "Do not explore files or run commands. Keep your internal "
              "reasoning brief, then give the complete final answer directly "
              "in your reply text.")

# 终局性错误：重试无意义
DEFINITIVE_ERRORS = {
    "RegionError", "ModelProtocolUnsupported", "InsufficientFunds",
    "AuthError", "FreeTierError", "ModelError",
}

# ============ OpenCode 免费层传输 ============
def _gen_ses():
    """ses_ + 9位hex + [fc0..fff](低12位须落在此区间) + 14位字母数字。每次请求新造。"""
    tail = secrets.choice(["fc0", "fcf", "fd0", "fe0", "ff0", "ffc", "fff"])
    head9 = "".join(secrets.choice("0123456789abcdef") for _ in range(9))
    alnum14 = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
    return "ses_" + head9 + tail + alnum14


def _headers():
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
    """从 HTTP 错误响应提取 (error_type, message, is_definitive)。"""
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
        if etype not in DEFINITIVE_ERRORS:
            etype = "Transient429" if status_code == 429 else "EndpointUnavailable"
    return etype, message, etype in DEFINITIVE_ERRORS


def _one_request(model, prompt, max_tokens, temperature):
    """单次 SSE 流式请求（不含重试）。返回:
      ok:   {ok:True, content, reasoning_tokens, finish_reason, prompt_tokens,
             completion_tokens, elapsed_s}
      fail: {ok:False, http_status, error_type, error_message, is_definitive,
             soft_retryable, elapsed_s}   # soft_retryable: 参数被拒等可去掉参数重试
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYS_DIRECT},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "max_tokens": max_tokens,
        "tools": TOOLS,
    }
    # 降级路径：免费层若拒绝某参数则省略之（_SOFT_DROP 控制）
    if temperature is not None:
        payload["temperature"] = temperature
    if TOOL_CHOICE:
        payload["tool_choice"] = TOOL_CHOICE
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(), headers=_headers(), method="POST")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=PER_CALL_TIMEOUT) as resp:
            parts, usage, finish = [], {}, None
            for raw in resp:
                if time.time() - start > HARD_READ_LIMIT:
                    return {"ok": False, "http_status": 200, "error_type": "StreamTimeout",
                            "error_message": f"读流超过 {HARD_READ_LIMIT}s 硬上限",
                            "is_definitive": False, "soft_retryable": False,
                            "elapsed_s": round(time.time() - start, 1)}
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except Exception:
                    continue
                if chunk.get("error"):
                    et = chunk["error"].get("type", "StreamError")
                    return {"ok": False, "http_status": 200, "error_type": et,
                            "error_message": chunk["error"].get("message", "")[:200],
                            "is_definitive": et in DEFINITIVE_ERRORS,
                            "soft_retryable": False,
                            "elapsed_s": round(time.time() - start, 1)}
                usage = chunk.get("usage") or usage
                for ch in chunk.get("choices", []):
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        parts.append(d["content"])
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
            content = "".join(parts)
            u = usage or {}
            cd = u.get("completion_tokens_details") or {}
            return {
                "ok": True, "content": content,
                "finish_reason": finish,
                "prompt_tokens": u.get("prompt_tokens"),
                "completion_tokens": u.get("completion_tokens"),
                "reasoning_tokens": cd.get("reasoning_tokens"),
                "elapsed_s": round(time.time() - start, 1),
            }
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        etype, msg, definitive = _classify_error(e.code, body)
        # 参数被拒（400）：提示可做"去参数降级重试"（错误信息需明确提到参数名）
        soft = (e.code == 400 and any(k in msg.lower()
                for k in ("tool_choice", "temperature")))
        return {"ok": False, "http_status": e.code, "error_type": etype,
                "error_message": msg[:200], "is_definitive": definitive,
                "soft_retryable": soft, "elapsed_s": round(time.time() - start, 1)}
    except Exception as e:
        return {"ok": False, "http_status": None, "error_type": type(e).__name__,
                "error_message": str(e)[:200], "is_definitive": False,
                "soft_retryable": False, "elapsed_s": round(time.time() - start, 1)}


# soft 降级：免费层若拒绝某参数，则去掉后重试
_SOFT_DROP = {"tool_choice": False, "temperature": False}   # 全局记忆，避免反复撞 400


def call_llm(model, prompt, temperature, breaker=None):
    """带退避重试 + 自适应 max_tokens 升档的一次实验调用。
    返回 {content, prompt_tokens, completion_tokens, reasoning_tokens,
          finish_reason, elapsed_s, attempts, error}（error 非空 = 彻底失败，
          content 为 "[ERROR] ..."）。"""
    mt = int(MODEL_MAX_TOKENS.get(model, MAX_TOKENS))
    budget_end = time.time() + ITEM_RETRY_BUDGET
    attempts = 0
    last_err = None
    bump_done = False     # 是否已做过一次 2x 升档重试
    endpoint_fail = 0     # 同一条记录连续 EndpointUnavailable(503) 计数
    while attempts < MAX_RETRIES:
        if time.time() > budget_end:
            last_err = last_err or "ItemRetryBudgetExhausted"
            break
        if breaker is not None and breaker.tripped:
            last_err = "circuit breaker tripped"
            break
        attempts += 1
        r = _one_request(model, prompt, mt, temperature)
        if r["ok"]:
            content = r["content"] or ""
            if not content.strip():
                # 空回复：finish=length 且推理烧光 -> 升档重试一次；否则普通重试
                if r.get("finish_reason") == "length" and not bump_done and mt < 32000:
                    mt = min(mt * 2, 32000)
                    bump_done = True
                    last_err = "ReasoningBudgetExhausted(bumped)"
                    log(f"    [升档] 空正文+length，max_tokens -> {mt} 重试")
                    continue
                last_err = "EmptyResponse"
                if breaker: breaker.record(False)
            else:
                if breaker: breaker.record(True)
                return {"content": content,
                        "prompt_tokens": r.get("prompt_tokens"),
                        "completion_tokens": r.get("completion_tokens"),
                        "reasoning_tokens": r.get("reasoning_tokens"),
                        "finish_reason": r.get("finish_reason"),
                        "elapsed_s": r.get("elapsed_s"), "attempts": attempts, "error": None}
        else:
            last_err = f"{r['error_type']}: {r['error_message']}"
            if breaker: breaker.record(False)
            if r.get("soft_retryable"):
                key = "tool_choice" if "tool_choice" in r["error_message"].lower() else "temperature"
                if key == "tool_choice" and not _SOFT_DROP["tool_choice"]:
                    _SOFT_DROP["tool_choice"] = True
                    log("    [降级] 免费层拒绝 tool_choice，后续请求去掉该参数")
                    globals()["TOOL_CHOICE"] = None
                    continue
                if key == "temperature" and not _SOFT_DROP["temperature"]:
                    _SOFT_DROP["temperature"] = True
                    log("    [降级] 免费层拒绝 temperature，后续请求去掉该参数")
                    globals()["GEN_TEMPERATURE"] = None
                    globals()["POST_TEMPERATURE"] = None
                    continue
            if r.get("error_type") == "EndpointUnavailable":
                endpoint_fail += 1
                if endpoint_fail >= 3:
                    # 端点当前不可用：别把整条预算耗在同一错误上，留到下次会话再试
                    break
            if r.get("is_definitive"):
                break
        wait = BACKOFFS[min(attempts - 1, len(BACKOFFS) - 1)]
        if time.time() + wait < budget_end:
            time.sleep(wait)
    return {"content": f"[ERROR] {last_err}",
            "prompt_tokens": None, "completion_tokens": None, "reasoning_tokens": None,
            "finish_reason": None, "elapsed_s": None, "attempts": attempts,
            "error": last_err}


# ============ JSONL 增量读写 ============
def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _is_error_text(t):
    return not t or str(t).strip().startswith("[ERROR]")


def valid_result(r):
    return not _is_error_text(r.get("content"))


def valid_cleaned(r):
    return not _is_error_text(r.get("cleaned_content"))


def valid_comparison(r):
    return r.get("winner_label") in ("baseline", "cleaned_word_pairs", "tie")


def latest_valid_by_key(records, key_fields, valid_fn):
    """追加式 jsonl 越靠后越新：每个键保留最新一条有效记录。"""
    out = {}
    for r in records:
        key = tuple(r.get(f) for f in key_fields)
        if any(k is None for k in key):
            continue
        if not valid_fn(r):
            continue
        out[key] = r
    return out

# ============ Git 工具（Kaggle->Gitee 加固版） ============
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
    """Kaggle(美国出口)访问 gitee.com 偶发 SSL 挂起的加固：
    HTTP/1.1 + 低速断线保护（<1000B/s 持续 120s 主动失败转为可重试）。"""
    for k, v in [("http.version", "HTTP/1.1"), ("http.postBuffer", "524288000"),
                 ("http.lowSpeedLimit", "1000"), ("http.lowSpeedTime", "120")]:
        _run_git(["config", "--global", k, v])


def _config_identity():
    _run_git(["config", "user.email", GIT_USER_EMAIL], cwd=REPO_DIR)
    _run_git(["config", "user.name", GIT_USER_NAME], cwd=REPO_DIR)


def _fetch_origin(retries=2, wait=15):
    for i in range(1, retries + 1):
        r = _run_git(["fetch", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
        if _ok(r):
            return True
        if i < retries:
            log(f"  [警告] fetch 失败（第 {i} 次），{wait}s 后重试: {(r.stderr if r else '')[:120]}")
            time.sleep(wait)
    return False


def sync_from_gitee():
    """远端分支 -> 本地。git 通道优先（clone 重试+浅克隆降级），
    全部失败则自动切换 Gitee API 传输模式。"""
    global API_MODE
    _apply_git_tweaks()
    if API_MODE:
        api_sync_from_gitee()
        return
    if SKIP_SYNC:
        log("[Git] SKIP_SYNC=1，跳过同步（本地调试用）")
        EXP_ROOT.mkdir(parents=True, exist_ok=True)
        _api_snapshot()
        return
    if not (REPO_DIR / ".git").exists():
        REPO_DIR.mkdir(parents=True, exist_ok=True)
        log(f"[Git] clone {GIT_BRANCH} 分支 …")
        last_err = ""
        for attempt in range(1, CLONE_ATTEMPTS + 1):
            if attempt == 1:
                args = ["clone", "--single-branch", "-b", GIT_BRANCH, GIT_REMOTE_URL, str(REPO_DIR)]
            else:
                args = ["clone", "--depth", "1", "--single-branch", "-b", GIT_BRANCH,
                        GIT_REMOTE_URL, str(REPO_DIR)]
            # curl 默认 300s 连接超时，外层 320s 即可，不白等 900s
            r = _run_git(args, timeout=320)
            if _ok(r):
                log(f"[Git] clone 成功（第 {attempt} 次尝试） -> {REPO_DIR}")
                break
            last_err = (r.stderr if r else "")[-200:]
            log(f"  [警告] clone 第 {attempt} 次失败: {last_err[-120:]}")
            shutil.rmtree(REPO_DIR, ignore_errors=True)
            REPO_DIR.mkdir(parents=True, exist_ok=True)
            if attempt < CLONE_ATTEMPTS:
                wait = CLONE_WAITS[min(attempt - 1, len(CLONE_WAITS) - 1)]
                log(f"  [重试] {wait}s 后再次尝试 …")
                time.sleep(wait)
        else:
            log(f"[降级] clone 连续 {CLONE_ATTEMPTS} 次失败（{last_err[-80:]}），"
                f"切换 Gitee API 传输模式（api.gitee.com 走不同链路）")
            API_MODE = True
            api_sync_from_gitee()
            return
        _config_identity()
        _api_snapshot()
        return
    _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=REPO_DIR)
    _config_identity()
    st = _run_git(["status", "--porcelain"], cwd=REPO_DIR)
    if st and st.stdout.strip():
        _run_git(["add", "-A"], cwd=REPO_DIR)
        _run_git(["commit", "-m", "wip: 自动保存未提交进度"], cwd=REPO_DIR)
        log("[Git] 发现未提交改动，已自动提交")
    if not _fetch_origin(retries=2):
        log("[降级] fetch 失败，切换 Gitee API 传输模式")
        API_MODE = True
        api_sync_from_gitee()
        return
    _run_git(["checkout", "-B", GIT_BRANCH, f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    r = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
    if _ok(r):
        log("[Git] rebase 同步完成，本地已是最新")
    else:
        _run_git(["rebase", "--abort"], cwd=REPO_DIR)
        log("[Git] rebase 冲突，已 abort 并保留本地提交（稍后 push 时再合并）")
    _api_snapshot()


_commit_counter = 0


def git_commit_and_push(message, push=True):
    """提交并推送。API 模式走 _gitee_put_file；git 模式 commit 后
    fetch+rebase+push，push 连续失败达阈值则自动降级 API 模式补推。"""
    global _commit_counter, API_MODE, _git_push_fail_streak
    _commit_counter += 1
    EXP_ROOT.mkdir(parents=True, exist_ok=True)
    if API_MODE:
        api_commit_and_push(message, push)
        return
    if SKIP_SYNC:  # 本地调试：只写文件，不动 git
        return
    _run_git(["add", "-A"], cwd=REPO_DIR)
    st = _run_git(["status", "--porcelain"], cwd=REPO_DIR)
    if not (st and st.stdout.strip()):
        return
    r = _run_git(["commit", "-m", message], cwd=REPO_DIR)
    if not _ok(r):
        log(f"  [警告] commit 失败: {(r.stderr if r else '')[:150]}")
        return
    if not push:
        return
    pushed = False
    if _fetch_origin(retries=2):
        rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
        if _ok(rbr):
            p = _run_git(["push", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
            if not _ok(p):
                log("  [警告] push 失败，重试一次 …")
                time.sleep(15)
                if _fetch_origin(retries=1):
                    rbr = _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=REPO_DIR)
                    if _ok(rbr):
                        p2 = _run_git(["push", "origin", GIT_BRANCH], cwd=REPO_DIR, timeout=600)
                        pushed = _ok(p2)
                        if not pushed:
                            log(f"  [警告] push 仍失败: {(p2.stderr if p2 else '')[:150]}")
                    else:
                        _run_git(["rebase", "--abort"], cwd=REPO_DIR)
            else:
                pushed = True
        else:
            _run_git(["rebase", "--abort"], cwd=REPO_DIR)
            log("  [警告] rebase 冲突，放弃本次 push（本地 commit 保留）")
    else:
        log("  [警告] fetch 失败，放弃本次 push（本地 commit 保留）")
    if pushed:
        _git_push_fail_streak = 0
    else:
        _git_push_fail_streak += 1
        if _git_push_fail_streak >= GIT_PUSH_FAIL_STREAK_LIMIT:
            log(f"[降级] git push 连续 {_git_push_fail_streak} 次失败，"
                f"切换 Gitee API 传输模式并补推未上传内容")
            API_MODE = True
            _api_push_all_changed()


# ============ 熔断器（每模型一个） ============
class Breaker:
    def __init__(self, threshold):
        self.threshold = threshold
        self.consecutive = 0
        self.tripped = False

    def record(self, ok):
        if ok:
            self.consecutive = 0
            return
        self.consecutive += 1
        if self.threshold > 0 and self.consecutive >= self.threshold and not self.tripped:
            self.tripped = True
            log(f"    [熔断] 连续 {self.consecutive} 次失败，跳过该模型剩余调用")

# ============ 每模型三阶段流水线 ============
def model_dir(model):
    return EXP_ROOT / model


def read_status(model):
    p = model_dir(model) / "_status.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def write_status(model, **kv):
    d = read_status(model)
    d.update(kv)
    d["updated"] = datetime.now(timezone.utc).isoformat()
    (model_dir(model) / "_status.json").parent.mkdir(parents=True, exist_ok=True)
    (model_dir(model) / "_status.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def analyze_model(model):
    """分析该模型三阶段的缺口。返回 dict（含各阶段待办列表）。"""
    d = model_dir(model)
    all_results = load_jsonl(d / "results.jsonl")
    vres = latest_valid_by_key(all_results, ("task_id", "condition", "run"), valid_result)
    vclean = latest_valid_by_key(load_jsonl(d / "cleaned.jsonl"), ("task_id", "run"), valid_cleaned)
    vcmp = latest_valid_by_key(load_jsonl(d / "comparison.jsonl"), ("task_id", "run"), valid_comparison)

    expected = {(t, c, r) for t in TASKS_BY_ID for c in CONDITIONS for r in range(1, N_RUNS + 1)}
    missing_gen = sorted(expected - set(vres))

    baseline_map, wp_map = {}, {}
    for (tid, cond, run), r in vres.items():
        if cond == "baseline":
            baseline_map[(tid, run)] = r
        elif cond == "word_pairs":
            wp_map[(tid, run)] = r
    to_clean = [wp_map[k] for k in sorted(wp_map) if k not in vclean]

    pairs = []
    for tid in sorted(TASKS_BY_ID):
        for run in range(1, N_RUNS + 1):
            k = (tid, run)
            if k in vcmp or k not in baseline_map or k not in vclean:
                continue
            pairs.append((tid, run, baseline_map[k], vclean[k]))

    return {"n_valid_res": len(vres), "n_expect_res": len(expected),
            "n_valid_clean": len(vclean), "n_expect_clean": len(TASKS_BY_ID) * N_RUNS,
            "n_valid_cmp": len(vcmp), "n_expect_cmp": len(TASKS_BY_ID) * N_RUNS,
            "missing_gen": missing_gen, "to_clean": to_clean, "pairs": pairs}


def gen_prompt_for(task, condition):
    """与原实验一致：word_pairs = 前缀指令 + \\n + 任务 prompt。"""
    if condition == "word_pairs":
        return f"{PREFIX}\n{task['prompt']}"
    return task["prompt"]


def stage_generate(model, brk, deadline_model, deadline_global):
    """阶段 0：逐条补生成（严格串行）。返回 (n_ok, n_fail, stop_reason)。"""
    a = analyze_model(model)
    todo = a["missing_gen"]
    log(f"  [阶段0 生成] 缺 {len(todo)} / {a['n_expect_res']}")
    n_ok = n_fail = 0
    for (tid, cond, run) in todo:
        if brk.tripped:
            return n_ok, n_fail, "breaker"
        if time.time() > deadline_model:
            return n_ok, n_fail, "model_budget"
        if time.time() > deadline_global:
            return n_ok, n_fail, "global_budget"
        task = TASKS_BY_ID[tid]
        prompt = gen_prompt_for(task, cond)
        log(f"    [gen] task{tid} {task['name']} | {cond} | run{run:02d} …")
        r = call_llm(model, prompt, GEN_TEMPERATURE, breaker=brk)
        ok = not r["error"]
        rec = {
            "model": model, "task_id": tid, "task_name": task["name"],
            "condition": cond, "run": run, "prompt": prompt,
            "content": r["content"],
            "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
            "reasoning_tokens": r["reasoning_tokens"], "finish_reason": r["finish_reason"],
            "elapsed": r["elapsed_s"], "attempts": r["attempts"],
            "error": r["error"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # markdown（目录结构与原实验一致）
        md_dir = model_dir(model) / f"task{tid}_{task['name']}" / cond
        md_dir.mkdir(parents=True, exist_ok=True)
        try:
            (md_dir / f"run_{run:02d}.md").write_text(
                f"# [rerun:{model}] 任务{tid} {task['name']} | 条件: {cond} | 第 {run} 次\n\n"
                f"**Prompt:** {prompt}\n\n"
                f"**耗时:** {r['elapsed_s']}s | **tokens:** {r['prompt_tokens']}/"
                f"{r['completion_tokens']}(推理 {r['reasoning_tokens']}) | "
                f"**finish:** {r['finish_reason']}\n\n---\n\n{r['content']}\n",
                encoding="utf-8")
        except Exception as e:
            log(f"    [警告] 写生成 markdown 失败: {e}")
        append_jsonl(model_dir(model) / "results.jsonl", rec)
        n_ok, n_fail = (n_ok + 1, n_fail) if ok else (n_ok, n_fail + 1)
        tag = "生成完成" if ok else f"生成失败({r['error'][:60]})"
        log(f"    [{tag}] {r['elapsed_s']}s | {len(r['content'])} chars | task{tid} {cond} run{run}")
        git_commit_and_push(
            f"gen: [{model}] task{tid} {cond} run{run} "
            f"{'ok' if ok else 'error'}", push=(GIT_PUSH_INTERVAL == 1))
        time.sleep(INTER_CALL_SLEEP)
    return n_ok, n_fail, None


def stage_clean(model, brk, deadline_model, deadline_global):
    """阶段 1：逐条补清洗 word_pairs。"""
    a = analyze_model(model)
    todo = a["to_clean"]
    log(f"  [阶段1 清洗] 缺 {len(todo)} / {a['n_expect_clean']}")
    n_ok = n_fail = 0
    for rec_in in todo:
        if brk.tripped:
            return n_ok, n_fail, "breaker"
        if time.time() > deadline_model:
            return n_ok, n_fail, "model_budget"
        if time.time() > deadline_global:
            return n_ok, n_fail, "global_budget"
        content = rec_in.get("content") or ""
        tid, run = rec_in["task_id"], rec_in["run"]
        task = TASKS_BY_ID[tid]
        log(f"    [clean] task{tid} {task['name']} | run{run:02d} …")
        prompt = CLEAN_PROMPT.format(content=content)
        r = call_llm(model, prompt, POST_TEMPERATURE, breaker=brk)
        ok = not r["error"]
        rec = {
            "model": model, "task_id": tid, "task_name": task["name"],
            "condition": "word_pairs", "run": run,
            "original_prompt": rec_in.get("prompt"),
            "original_content": content,
            "cleaned_content": r["content"],
            "clean_elapsed": r["elapsed_s"],
            "clean_prompt_tokens": r["prompt_tokens"],
            "clean_completion_tokens": r["completion_tokens"],
            "clean_reasoning_tokens": r["reasoning_tokens"],
            "error": r["error"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        md_dir = model_dir(model) / "cleaned" / f"task{tid}_{task['name']}"
        md_dir.mkdir(parents=True, exist_ok=True)
        try:
            (md_dir / f"run_{run:02d}.md").write_text(
                f"# [清洗:{model}] 任务{tid} {task['name']} | word_pairs | 第 {run} 次\n\n"
                f"**耗时:** {r['elapsed_s']}s | **tokens:** {r['prompt_tokens']}/"
                f"{r['completion_tokens']}\n\n## 原始输出（含词对）\n\n{content}\n\n"
                f"---\n\n## 清洗后输出\n\n{r['content']}\n",
                encoding="utf-8")
        except Exception as e:
            log(f"    [警告] 写清洗 markdown 失败: {e}")
        append_jsonl(model_dir(model) / "cleaned.jsonl", rec)
        n_ok, n_fail = (n_ok + 1, n_fail) if ok else (n_ok, n_fail + 1)
        log(f"    [{'清洗完成' if ok else '清洗失败'}] task{tid} run{run} | {r['elapsed_s']}s")
        git_commit_and_push(
            f"clean: [{model}] task{tid} word_pairs run{run} "
            f"{'ok' if ok else 'error'}", push=(GIT_PUSH_INTERVAL == 1))
        time.sleep(INTER_CALL_SLEEP)
    return n_ok, n_fail, None


def _parse_compare_json(text):
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


def stage_compare(model, brk, deadline_model, deadline_global):
    """阶段 2：逐条补盲评（随机交换 A/B 防位置偏差，与原实验一致）。"""
    a = analyze_model(model)
    todo = a["pairs"]
    log(f"  [阶段2 盲评] 缺 {len(todo)} / {a['n_expect_cmp']}")
    n_ok = n_fail = 0
    for (tid, run, base_rec, clean_rec) in todo:
        if brk.tripped:
            return n_ok, n_fail, "breaker"
        if time.time() > deadline_model:
            return n_ok, n_fail, "model_budget"
        if time.time() > deadline_global:
            return n_ok, n_fail, "global_budget"
        task = TASKS_BY_ID[tid]
        baseline_ans = base_rec.get("content") or ""
        cleaned_ans = clean_rec.get("cleaned_content") or ""
        swap = random.random() < 0.5
        if swap:
            ans_a, ans_b = cleaned_ans, baseline_ans
            label_a, label_b = "cleaned_word_pairs", "baseline"
        else:
            ans_a, ans_b = baseline_ans, cleaned_ans
            label_a, label_b = "baseline", "cleaned_word_pairs"
        log(f"    [cmp] task{tid} {task['name']} | run{run:02d} | swap={swap} …")
        prompt = COMPARE_PROMPT.format(task=task["prompt"], answer_a=ans_a, answer_b=ans_b)
        r = call_llm(model, prompt, POST_TEMPERATURE, breaker=brk)
        parsed = _parse_compare_json(r["content"]) if not r["error"] else None
        winner_raw = winner_label = None
        scores_a = scores_b = reason = None
        if parsed:
            winner_raw = parsed.get("winner")
            scores_a, scores_b = parsed.get("A"), parsed.get("B")
            reason = parsed.get("reason")
            if winner_raw == "A":
                winner_label = label_a
            elif winner_raw == "B":
                winner_label = label_b
            elif winner_raw == "tie":
                winner_label = "tie"
        rec = {
            "model": model, "task_id": tid, "task_name": task["name"], "run": run,
            "swap": swap, "A_source": label_a, "B_source": label_b,
            "baseline_content": baseline_ans, "cleaned_content": cleaned_ans,
            "raw_llm_output": r["content"],
            "parsed": parsed, "winner_raw": winner_raw, "winner_label": winner_label,
            "A_scores": scores_a, "B_scores": scores_b, "reason": reason,
            "compare_elapsed": r["elapsed_s"],
            "compare_prompt_tokens": r["prompt_tokens"],
            "compare_completion_tokens": r["completion_tokens"],
            "error": r["error"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        md_dir = model_dir(model) / "comparison" / f"task{tid}_{task['name']}"
        md_dir.mkdir(parents=True, exist_ok=True)
        try:
            (md_dir / f"run_{run:02d}.md").write_text(
                f"# [比较:{model}] 任务{tid} {task['name']} | 第 {run} 次\n\n"
                f"**A 来源:** {label_a} | **B 来源:** {label_b} | **交换:** {swap}\n\n"
                f"**Winner:** {winner_label}\n\n"
                f"**耗时:** {r['elapsed_s']}s\n\n---\n\n"
                f"## 回答 A（{label_a}）\n\n{ans_a}\n\n---\n\n"
                f"## 回答 B（{label_b}）\n\n{ans_b}\n\n---\n\n## 评审输出\n\n"
                f"{json.dumps(parsed, ensure_ascii=False, indent=2) if parsed else r['content']}\n",
                encoding="utf-8")
        except Exception as e:
            log(f"    [警告] 写比较 markdown 失败: {e}")
        append_jsonl(model_dir(model) / "comparison.jsonl", rec)
        ok = valid_comparison(rec)
        n_ok, n_fail = (n_ok + 1, n_fail) if ok else (n_ok, n_fail + 1)
        log(f"    [{'比较完成' if ok else '比较无效(下次重跑再评)'}] "
            f"task{tid} run{run} winner={winner_label}")
        git_commit_and_push(
            f"cmp: [{model}] task{tid} run{run} winner={winner_label}",
            push=(GIT_PUSH_INTERVAL == 1))
        time.sleep(INTER_CALL_SLEEP)
    return n_ok, n_fail, None

# ============ 进度汇总 ============
def write_progress():
    """刷新 EXP_ROOT/PROGRESS.md（每模型三阶段完成度 + 总体状态）。"""
    lines = [
        "# OpenCode 免费模型实验重跑 · 进度总览",
        "",
        f"- 更新时间: {datetime.now(timezone.utc).isoformat()}",
        f"- 实验网格: {len(TASKS_BY_ID)} 任务 × {len(CONDITIONS)} 条件 × {N_RUNS} 次",
        f"- 实验定义来源: {DEFS_NOTE}",
        "",
        "| 模型 | 生成 | 清洗 | 盲评 | 状态 |",
        "|---|---|---|---|---|",
    ]
    n_complete = 0
    for m in MODELS:
        a = analyze_model(m)
        st = read_status(m)
        gen_ok = a["n_valid_res"]; gen_n = a["n_expect_res"]
        cl_ok = a["n_valid_clean"]; cl_n = a["n_expect_clean"]
        cmp_ok = a["n_valid_cmp"]; cmp_n = a["n_expect_cmp"]
        if gen_ok >= gen_n and cl_ok >= cl_n and cmp_ok >= cmp_n:
            state = "✅ 完成"
            n_complete += 1
        elif st.get("gave_up"):
            state = f"⛔ gave_up: {st.get('reason', '')[:40]}"
            n_complete += 1
        elif gen_ok or cl_ok or cmp_ok:
            state = "⏳ 进行中"
        else:
            state = "◻ 未开始"
        lines.append(f"| {m} | {gen_ok}/{gen_n} | {cl_ok}/{cl_n} | {cmp_ok}/{cmp_n} | {state} |")
    lines += ["", f"**完成 {n_complete}/{len(MODELS)} 个模型**（含 gave_up）。",
              "", "重跑本 Notebook/脚本即可从断点继续（已完成的记录不会重跑）。"]
    p = EXP_ROOT / "PROGRESS.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)


def model_complete(model):
    a = analyze_model(model)
    return (a["n_valid_res"] >= a["n_expect_res"]
            and a["n_valid_clean"] >= a["n_expect_clean"]
            and a["n_valid_cmp"] >= a["n_expect_cmp"])


# ============ 主流程 ============
def main():
    t0 = time.time()
    deadline_global = t0 + TIME_BUDGET_MIN * 60
    # 收尾预留：预留 10% 时间做最终 push/汇总（至少 60s，至多 10min）
    reserve = min(600, max(60, TIME_BUDGET_MIN * 6))
    deadline_soft = deadline_global - reserve
    models = MODELS[:MODELS_LIMIT] if MODELS_LIMIT > 0 else MODELS

    log("=" * 64)
    log("OpenCode 免费模型实验重跑（三阶段流水线 · 并发=1 · 断点续跑）")
    log("=" * 64)
    log(f"环境: {'Kaggle' if IS_KAGGLE else '本地'} | WORK_DIR={WORK_DIR} | 分支={GIT_BRANCH}")
    log(f"定义: {DEFS_NOTE}")
    log(f"网格: {len(TASKS_BY_ID)}任务 × {len(CONDITIONS)}条件 × {N_RUNS}次 = "
        f"{len(TASKS_BY_ID) * len(CONDITIONS) * N_RUNS} 生成/模型")
    log(f"模型: {len(models)} 个 | 每模型预算 {PER_MODEL_BUDGET_MIN:.0f}min | "
        f"会话预算 {TIME_BUDGET_MIN:.0f}min")
    log(f"DRY_RUN={DRY_RUN} | max_tokens={MAX_TOKENS}(默认) | "
        f"熔断={CIRCUIT_BREAKER} | gave_up阈值={GAVE_UP_DEFINITIVE}")

    # 1) 同步远端进度
    sync_from_gitee()

    # 1.5) 心跳：会话启动即推一条可见信号（确认传输通道 + 观测会话次数）
    if not DRY_RUN:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            hb = EXP_ROOT / f"_session_{ts}.json"
            hb.parent.mkdir(parents=True, exist_ok=True)
            hb.write_text(json.dumps({
                "started": datetime.now(timezone.utc).isoformat(),
                "mode": "api" if API_MODE else "git",
                "kaggle": IS_KAGGLE,
                "time_budget_min": TIME_BUDGET_MIN,
                "defs": DEFS_NOTE,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            git_commit_and_push(f"session start ({'api' if API_MODE else 'git'} mode)", push=True)
        except Exception as e:
            log(f"[警告] 心跳推送失败: {e}")

    if DRY_RUN:
        log("[DRY_RUN] 仅分析模式：打印各模型缺口，不调用、不写入、不推送。")
        for i, model in enumerate(models, 1):
            a = analyze_model(model)
            st = read_status(model)
            log(f"[{i}/{len(models)}] {model}: 生成缺 {len(a['missing_gen'])}/{a['n_expect_res']}"
                f" | 清洗缺 {len(a['to_clean'])}/{a['n_expect_clean']}"
                f" | 盲评缺 {len(a['pairs'])}/{a['n_expect_cmp']}"
                f" | gave_up={bool(st.get('gave_up'))}")
        return

    # 2) 逐模型串行执行（每个模型各跑一遍三阶段）
    stopped = None
    summary_bits = []
    prog = None
    try:
        for i, model in enumerate(models, 1):
            if time.time() > deadline_soft:
                stopped = "会话总预算将耗尽"
                log(f"[停止] {stopped}，干净收尾（下次运行自动续跑）")
                break
            if read_status(model).get("gave_up") and not RETRY_GAVE_UP:
                log(f"\n===== [{i}/{len(models)}] {model} -> 跳过（gave_up） =====")
                continue
            if model_complete(model):
                log(f"\n===== [{i}/{len(models)}] {model} -> 跳过（已完成） =====")
                continue

            m_start = time.time()
            deadline_model = min(deadline_soft, m_start + PER_MODEL_BUDGET_MIN * 60)
            log(f"\n===== [{i}/{len(models)}] {model} =====")
            brk = Breaker(CIRCUIT_BREAKER)
            stop_reason = None
            for stage_fn, sname in ((stage_generate, "gen"), (stage_clean, "clean"),
                                     (stage_compare, "cmp")):
                n_ok, n_fail, s = stage_fn(model, brk, deadline_model, deadline_soft)
                summary_bits.append(f"{model}/{sname}: +{n_ok} ok, +{n_fail} fail"
                                    + (f", stop={s}" if s else ""))
                if sname == "gen":
                    # 阶段0后检查：全部生成都终局失败且零成功（如协议不支持）
                    a = analyze_model(model)
                    allrec = load_jsonl(model_dir(model) / "results.jsonl")
                    recent_errors = [r for r in allrec if _is_error_text(r.get("content"))][-5:]
                    if (recent_errors and len(recent_errors) >= GAVE_UP_DEFINITIVE
                            and a["n_valid_res"] == 0
                            and all(any(k in (r.get("error") or "")
                                        for k in ("ProtocolUnsupported", "RegionError"))
                                    for r in recent_errors)):
                        write_status(model, gave_up=True,
                                     reason=recent_errors[-1].get("error") or "definitive errors")
                        stop_reason = "gave_up"
                        log(f"  [放弃] {model} 连续 {len(recent_errors)} 条终局失败且无任何成功，"
                            f"标记 gave_up（不再重试）")
                        break
                if brk.tripped or s == "breaker":
                    stop_reason = "breaker"
                    break
                if s in ("model_budget", "global_budget"):
                    stop_reason = s
                    break

            used_min = (time.time() - m_start) / 60
            if stop_reason == "global_budget":
                stopped = "会话总预算将耗尽"
                break
            state = ("完成" if model_complete(model)
                     else f"部分完成（{stop_reason or '继续'}，用时 {used_min:.0f}min）")
            log(f"===== {model} {state} =====")
            write_progress()
            git_commit_and_push(f"progress: [{model}] {state}", push=True)
    except KeyboardInterrupt:
        stopped = "手动中断"
        log(f"[停止] {stopped}，已完成记录均已提交")
    finally:
        try:
            prog = write_progress()
            git_commit_and_push(
                f"run end: 本次会话结束{'; ' + stopped if stopped else ''}", push=True)
            log(f"[{'API' if API_MODE else 'Git'}] 最终提交推送完成，进度已保存到 Gitee")
        except Exception as e:
            log(f"[警告] 收尾异常（进度可能已部分保存）: {e}")

    # 3) 结束报告
    log("\n" + "=" * 64)
    log("本次会话小结：")
    for b in summary_bits:
        log("  " + b)
    if stopped:
        log(f"提前停止原因: {stopped}")
    log("总进度: 见 PROGRESS.md（完成/全部模型）")
    log("提示: 重新运行本 Notebook（或脚本）即可从断点继续，已完成记录不会重跑。")
    log("=" * 64)
    if prog:
        print("\n" + prog)



# ============ Gitee API 传输层（git 通道失败时的降级通道） ============
# api.gitee.com 与 gitee.com 的 git-over-HTTPS 走不同链路/边缘节点，
# 实测 Kaggle(美国出口) 偶发 gitee.com SSL 连接超时时 API 通道仍可用。
API_MODE = os.environ.get("GIT_MODE", "").strip().lower() == "api"  # 强制 API 模式
_git_push_fail_streak = 0

_gitee_auth = None


def _gitee_headers(json_body=False):
    global _gitee_auth
    import base64
    if _gitee_auth is None:
        m = re.match(r"https://([^:]+):([^@]+)@gitee\.com", GIT_REMOTE_URL)
        if m:
            _gitee_auth = base64.b64encode(
                f"{m.group(1)}:{m.group(2)}".encode()).decode()
        else:
            _gitee_auth = ""
    h = {"Authorization": f"Basic {_gitee_auth}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _gitee_repo():
    m = re.search(r"gitee\.com/([^/]+)/([^/.]+?)(?:\.git)?/?$", GIT_REMOTE_URL)
    if not m:
        raise RuntimeError(f"无法从 GIT_REMOTE_URL 解析 owner/repo: {GIT_REMOTE_URL[:40]}...")
    return f"{m.group(1)}/{m.group(2)}"


def _gitee_api(path, params=None, method="GET", body=None, timeout=60, raw=False):
    import urllib.parse as up
    url = f"https://gitee.com/api/v5{path}"
    if params:
        url += "?" + up.urlencode(params)
    data = json.dumps(body).encode() if (body is not None and method != "GET") else None
    req = urllib.request.Request(url, data=data,
                                 headers=_gitee_headers(json_body=(data is not None)),
                                 method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = r.read().decode("utf-8", "replace")
    return payload if raw else json.loads(payload)


def _gitee_get_file(rel_path):
    """读分支上文件 -> (text|None, sha|None)。404/太大 -> 内容走 raw 兜底。"""
    import base64 as b64
    import urllib.parse as up
    try:
        d = _gitee_api(f"/repos/{_gitee_repo()}/contents/{up.quote(rel_path)}",
                       params={"ref": GIT_BRANCH})
        if not isinstance(d, dict):   # 不存在时 Gitee 返回父目录列表
            return None, None
        content, sha = None, d.get("sha")
        if d.get("encoding") == "base64" and d.get("content"):
            content = b64.b64decode(d["content"]).decode("utf-8", "replace")
        elif d.get("content") is not None:
            content = str(d.get("content"))
        return content, sha
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        # 403/413 等（文件过大）-> raw 端点取内容 + 目录列表取 sha
        content = _gitee_get_raw(rel_path)
        sha = _gitee_dir_sha(rel_path)
        if content is None and sha is None:
            return None, None
        return content, sha
    except Exception as e:
        log(f"  [API警告] GET {rel_path} 异常: {e}")
        return None, None


def _gitee_get_raw(rel_path):
    import urllib.parse as up
    try:
        return _gitee_api(f"/repos/{_gitee_repo()}/raw/{up.quote(rel_path)}",
                          params={"ref": GIT_BRANCH}, raw=True)
    except Exception:
        return None


def _gitee_dir_sha(rel_path):
    """通过父目录列表拿文件 blob sha（contents 单文件过大时的兜底）。"""
    import urllib.parse as up
    parent, _, name = rel_path.rpartition("/")
    try:
        entries = _gitee_api(f"/repos/{_gitee_repo()}/contents/{up.quote(parent)}",
                             params={"ref": GIT_BRANCH})
        if isinstance(entries, list):
            for it in entries:
                if it.get("name") == name:
                    return it.get("sha")
    except Exception:
        pass
    return None


def _gitee_put_file(rel_path, content_text, message):
    """写分支上的文件（一次一个 commit）。
    Gitee 语义：POST 创建新文件（无需 sha）；PUT + sha 更新已有文件。"""
    import base64 as b64
    import urllib.parse as up
    b64content = b64.b64encode(content_text.encode("utf-8")).decode()
    path_q = up.quote(rel_path)
    content, sha = _gitee_get_file(rel_path)
    if content is None:
        try:
            _gitee_api(f"/repos/{_gitee_repo()}/contents/{path_q}", method="POST",
                       body={"content": b64content, "message": message[:200],
                             "branch": GIT_BRANCH})
            return True
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:150]
            except Exception:
                pass
            if e.code not in (400, 409):
                log(f"  [API警告] POST {rel_path} HTTP {e.code}: {detail}")
                return False
            # 可能并发已被创建 -> 重取 sha 改走 PUT
            content, sha = _gitee_get_file(rel_path)
            if content is None:
                log(f"  [API警告] POST {rel_path} 失败且文件不存在: {detail}")
                return False
        except Exception as e:
            log(f"  [API警告] POST {rel_path} 异常: {e}")
            return False
    # 更新已有文件
    body = {"content": b64content, "message": message[:200], "branch": GIT_BRANCH}
    if sha:
        body["sha"] = sha
    try:
        _gitee_api(f"/repos/{_gitee_repo()}/contents/{path_q}", method="PUT", body=body)
        return True
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:150]
        except Exception:
            pass
        # sha 过期（远端刚被并发更新）-> 重取 sha 再试一次
        if e.code in (409, 400):
            _, sha2 = _gitee_get_file(rel_path)
            if sha2 and sha2 != sha:
                body["sha"] = sha2
                try:
                    _gitee_api(f"/repos/{_gitee_repo()}/contents/{path_q}",
                               method="PUT", body=body)
                    return True
                except Exception:
                    pass
        log(f"  [API警告] PUT {rel_path} HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        log(f"  [API警告] PUT {rel_path} 异常: {e}")
        return False


# ---- API 模式的增量文件同步 ----
_api_snap = {}


def _file_hash(p):
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _api_snapshot():
    _api_snap.clear()
    if EXP_ROOT.exists():
        for p in EXP_ROOT.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                _api_snap[p.relative_to(REPO_DIR).as_posix()] = _file_hash(p)


def _api_dirty_files():
    out = []
    if EXP_ROOT.exists():
        for p in EXP_ROOT.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                rel = p.relative_to(REPO_DIR).as_posix()
                if _api_snap.get(rel) != _file_hash(p):
                    out.append((rel, p))
    return out


def api_sync_from_gitee():
    """API 模式启动同步：拉取各模型结果文件到本地。"""
    log("[API模式] 通过 Gitee API 拉取已有进度 …")
    EXP_ROOT.mkdir(parents=True, exist_ok=True)
    n = 0
    for model in MODELS:
        for name in ("results.jsonl", "cleaned.jsonl", "comparison.jsonl", "_status.json"):
            rel = f"{EXP_ROOT.name}/{model}/{name}"
            text, _sha = _gitee_get_file(rel)
            if text is None:
                continue
            p = EXP_ROOT / model / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            n += 1
    log(f"[API模式] 已拉取 {n} 个结果文件")
    _api_snapshot()


def _api_push_all_changed():
    """git->API 降级时的全量补推：GET 远端内容对比，仅推有差异的文件。"""
    n = 0
    if not EXP_ROOT.exists():
        return
    for p in sorted(EXP_ROOT.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        rel = p.relative_to(REPO_DIR).as_posix()
        local = p.read_text(encoding="utf-8")
        remote, _ = _gitee_get_file(rel)
        if remote != local:
            if _gitee_put_file(rel, local, f"sync fallback: {rel}"):
                n += 1
                _api_snap[rel] = _file_hash(p)
    if n:
        log(f"[API模式] 降级补推 {n} 个文件完成")


def api_commit_and_push(message, push=True):
    """API 模式：把本地改动过的文件逐个 PUT。"""
    if not push or DRY_RUN:
        return
    files = _api_dirty_files()
    if not files:
        return
    ok = 0
    for rel, p in files:
        if _gitee_put_file(rel, p.read_text(encoding="utf-8"), f"{message}"):
            ok += 1
            _api_snap[rel] = _file_hash(p)
    if ok < len(files):
        time.sleep(10)
        for rel, p in _api_dirty_files():
            if _gitee_put_file(rel, p.read_text(encoding="utf-8"), f"{message} (retry)"):
                _api_snap[rel] = _file_hash(p)


def push_error_note(text):
    """致命错误回传（尽力而为，git 或 API 通道）。"""
    global API_MODE
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        p = EXP_ROOT / f"_error_{ts}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text[:60000], encoding="utf-8")
        if API_MODE:
            _gitee_put_file(p.relative_to(REPO_DIR).as_posix(),
                            text[:60000], f"kaggle error report {ts}")
        else:
            git_commit_and_push(f"kaggle error report {ts}", push=True)
    except Exception as e:
        print(f"[错误回传失败] {e}", flush=True)


if __name__ == "__main__":
    main()

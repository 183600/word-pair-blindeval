#!/usr/bin/env python3
"""
LLM 对照实验脚本（修复版 + Gitee 自动提交）
- 6 个任务，每个任务 20 次调用：
  - baseline  × 10：只有任务本身的 prompt
  - word_pairs × 10：前面加上 200 组词的灵感指令
- 结果增量保存到 llm_experiment_results/ 目录
- 每次 LLM 调用带超时，避免长时间挂起
- 兼容 Jupyter / IPython（已有事件循环时自动切换运行方式）
- 每完成一次调用自动 git commit；按间隔自动 push 到 Gitee
"""

import asyncio
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from openai import AsyncOpenAI

# ============ 配置（可用环境变量覆盖） ============
API_KEY     = os.environ.get("OPENAI_API_KEY", "")
BASE_URL    = os.environ.get("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL       = os.environ.get("LLM_MODEL", "moonshotai/kimi-k3")
TEMPERATURE = 0.6
CONCURRENCY = 1           # 并发数（修复：从 1 提到 5）
MAX_RETRIES = 100           # 重试次数（修复：从 30 降到 8）
PER_CALL_TIMEOUT = 20000    # 单次调用最长 180 秒（修复：新增超时保护）
RETRY_TOTAL_BUDGET = 600  # 单条任务最长重试总时长 10 分钟
OUTPUT_DIR  = Path("llm_experiment_results")

PREFIX = "在回答前面输出200组词，每组有两个词，从这些词获得灵感"

# ============ Git 自动提交配置 ============
GIT_REMOTE_URL = os.environ.get(
    "GIT_REMOTE_URL",
    "https://gitee.com/qwe12345678/jkdsfn.git",
)
GIT_BRANCH       = os.environ.get("GIT_BRANCH", "main")
# 每完成多少条调用执行一次 push（1 表示每次都 push）
GIT_PUSH_INTERVAL = int(os.environ.get("GIT_PUSH_INTERVAL", "5"))

TASKS = [
    {"id": 1, "name": "函数式编程语言", "prompt": "设计一个全新的函数式编程语言"},
    {"id": 2, "name": "提升LLM性能",   "prompt": "怎么低成本不需要额外训练大幅提升现有LLM的性能"},
    {"id": 3, "name": "CLI工具Idea",   "prompt": "给出适合独立开发者开发CLI工具的一个Idea"},
    {"id": 4, "name": "新理论",        "prompt": "提出一个新的理论"},
    {"id": 5, "name": "人格模型",      "prompt": "提出一个新的类似于九型和荣格八维的模型"},
    {"id": 6, "name": "ML架构",        "prompt": "提出一个新的机器学习架构"},
]

CONDITIONS = {
    "baseline":   None,
    "word_pairs": PREFIX,
}


# ============ 增量写入锁 / 计数器 ============
_write_lock = threading.Lock()
_git_lock   = threading.Lock()
_commit_counter = 0


def _append_jsonl(path: Path, record: dict):
    """线程/协程安全地追加一条记录到 jsonl 文件"""
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============ Git 工具函数 ============
def _run_git(args, cwd=None, timeout=300):
    """执行一条 git 命令，返回 CompletedProcess 或 None（异常时）"""
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
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


def _git_init(repo_dir: Path):
    """初始化本地仓库 / 绑定远程 / 配置身份 / 合并远程初始内容"""
    repo_dir.mkdir(parents=True, exist_ok=True)

    # 1) 初始化本地仓库
    r = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    if not (r and r.returncode == 0 and r.stdout.strip() == "true"):
        _run_git(["init"], cwd=repo_dir)

    # 2) 切到目标分支（本地还没提交也能跑通）
    _run_git(["checkout", "-B", GIT_BRANCH], cwd=repo_dir)

    # 3) 设置 remote
    r = _run_git(["remote"], cwd=repo_dir)
    remotes = r.stdout.split() if (r and r.returncode == 0) else []
    if "origin" in remotes:
        _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=repo_dir)
    else:
        _run_git(["remote", "add", "origin", GIT_REMOTE_URL], cwd=repo_dir)

    # 4) 仅本仓库范围的身份
    _run_git(["config", "user.email", "auto@experiment.local"], cwd=repo_dir)
    _run_git(["config", "user.name",  "auto-experiment"], cwd=repo_dir)

    # 5) 尝试把远程已有内容合并进来（Gitee 上带 README 的情况）
    _run_git(["fetch", "origin", GIT_BRANCH], cwd=repo_dir)
    r = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
    if r and r.returncode == 0 and r.stdout.strip():
        _run_git(
            ["merge", "--allow-unrelated-histories", "-X", "ours",
             f"origin/{GIT_BRANCH}", "-m", "Merge remote initial commit"],
            cwd=repo_dir,
        )


def _git_commit_and_push(repo_dir: Path, message: str, push: bool = True):
    """添加 → 提交；push=True 时推送（失败先 rebase 再重试一次）"""
    with _git_lock:
        _run_git(["add", "-A"], cwd=repo_dir)

        # 没有改动就跳过
        r = _run_git(["status", "--porcelain"], cwd=repo_dir)
        if not (r and r.stdout.strip()):
            return

        c = _run_git(["commit", "-m", message], cwd=repo_dir)
        if not (c and c.returncode == 0):
            print(f"  [警告] git commit 失败: {c.stderr.strip() if c else 'unknown'}", flush=True)
            return

        if not push:
            return

        p = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=repo_dir)
        if p and p.returncode == 0:
            return

        # push 失败：尝试 fetch + rebase 后重试一次
        print("  [警告] push 失败，尝试 rebase 后重试…", flush=True)
        _run_git(["fetch", "origin", GIT_BRANCH], cwd=repo_dir)
        r = _run_git(["rev-parse", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
        if r and r.returncode == 0 and r.stdout.strip():
            _run_git(["rebase", f"origin/{GIT_BRANCH}"], cwd=repo_dir)
        p2 = _run_git(["push", "-u", "origin", GIT_BRANCH], cwd=repo_dir)
        if p2 and p2.returncode != 0:
            print(f"  [警告] push 仍然失败: {p2.stderr.strip()}", flush=True)


def _next_commit_count() -> int:
    global _commit_counter
    with _write_lock:
        _commit_counter += 1
        return _commit_counter


# ============ LLM 调用 ============
async def call_llm(client: AsyncOpenAI, prompt: str) -> dict:
    """带超时与重试的 LLM 调用"""
    deadline = time.time() + RETRY_TOTAL_BUDGET
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        if time.time() > deadline:
            break
        try:
            t0 = time.time()
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=TEMPERATURE,
                ),
                timeout=PER_CALL_TIMEOUT,
            )
            usage = resp.usage
            return {
                "content": resp.choices[0].message.content,
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "elapsed": round(time.time() - t0, 2),
            }
        except asyncio.TimeoutError:
            last_err = "TimeoutError"
            print(f"  [警告] 调用超时 (attempt {attempt}/{MAX_RETRIES})", flush=True)
        except Exception as e:
            last_err = str(e)
            print(f"  [警告] 调用失败 (attempt {attempt}/{MAX_RETRIES}): {e}", flush=True)

        backoff = min(2 ** attempt, 30)
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise

    return {
        "content": f"[ERROR] {last_err}",
        "prompt_tokens": None,
        "completion_tokens": None,
        "elapsed": None,
    }


async def run_trial(client, semaphore, task, condition, prefix,
                    run_idx: int, results_path: Path):
    full_prompt = f"{prefix}\n{task['prompt']}" if prefix else task["prompt"]

    async with semaphore:
        result = await call_llm(client, full_prompt)

    record = {
        "task_id": task["id"],
        "task_name": task["name"],
        "condition": condition,
        "run": run_idx,
        "prompt": full_prompt,
        **result,
    }

    # 保存单条 markdown
    md_dir = OUTPUT_DIR / f"task{task['id']}_{task['name']}" / condition
    md_dir.mkdir(parents=True, exist_ok=True)
    try:
        (md_dir / f"run_{run_idx:02d}.md").write_text(
            f"# 任务{task['id']} {task['name']} | 条件: {condition} | 第 {run_idx} 次\n\n"
            f"**Prompt:** {full_prompt}\n\n"
            f"**耗时:** {result['elapsed']}s | "
            f"**tokens:** {result['prompt_tokens']}/{result['completion_tokens']}\n\n---\n\n"
            f"{result['content']}\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"  [警告] 写 markdown 失败: {e}", flush=True)

    # 增量写入 jsonl
    _append_jsonl(results_path, record)

    print(f"[完成] 任务{task['id']} {task['name']} | {condition:10s} | "
          f"run {run_idx:2d} | {result['elapsed']}s", flush=True)

    # ===== 自动提交到 Gitee =====
    n = _next_commit_count()
    should_push = (n % GIT_PUSH_INTERVAL == 0)
    _git_commit_and_push(
        OUTPUT_DIR,
        f"auto: task{task['id']} {condition} run{run_idx} "
        f"[{n} total, {result['elapsed']}s]",
        push=should_push,
    )

    return record


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUTPUT_DIR / "results.jsonl"

    # 重新开始：清空旧的 jsonl（如果你想续跑可以注释掉这一行）
    results_path.write_text("", encoding="utf-8")

    # 初始化本地 git 仓库并绑定 Gitee 远程
    print("[Git] 初始化本地仓库并绑定 Gitee 远程…", flush=True)
    _git_init(OUTPUT_DIR)
    # 先把目录结构/空 results.jsonl 提交一次，避免后续 push 空仓
    _git_commit_and_push(OUTPUT_DIR, "init: experiment workspace", push=False)

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    jobs = [
        run_trial(client, semaphore, task, condition, prefix, i, results_path)
        for task in TASKS
        for condition, prefix in CONDITIONS.items()
        for i in range(1, 11)
    ]

    t0 = time.time()
    try:
        records = await asyncio.gather(*jobs)
    except asyncio.Cancelled:
        print("\n[中断] 被取消，保存已完成的记录。", flush=True)
        # 尝试把已落盘的内容推上去
        _git_commit_and_push(OUTPUT_DIR, "partial: cancelled", push=True)
        return

    print(f"\n全部完成：{len(records)} 次调用，总耗时 {time.time() - t0:.1f}s", flush=True)

    # 最终提交 + 推送，确保所有结果都在 Gitee 上
    _git_commit_and_push(
        OUTPUT_DIR,
        f"final: all {len(records)} runs done in {time.time() - t0:.1f}s",
        push=True,
    )

    # 简单统计
    print("\n=== 统计（平均输出 tokens / 平均耗时）===")
    for task in TASKS:
        for condition in CONDITIONS:
            rs = [r for r in records
                  if r["task_id"] == task["id"] and r["condition"] == condition]
            ctoks = [r["completion_tokens"] for r in rs if r["completion_tokens"]]
            times = [r["elapsed"] for r in rs if r["elapsed"]]
            if ctoks and times:
                print(f"任务{task['id']} [{condition:10s}] "
                      f"tokens: {sum(ctoks)/len(ctoks):7.0f} | "
                      f"耗时: {sum(times)/len(times):6.1f}s")
            else:
                print(f"任务{task['id']} [{condition:10s}] 无有效数据")


def run_main():
    """在普通脚本和 Jupyter/IPython 里都能同步执行 main()"""
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

    t = threading.Thread(target=_worker, name="llm-experiment")
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]


if __name__ == "__main__":
    run_main()
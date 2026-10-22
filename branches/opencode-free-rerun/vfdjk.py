#!/usr/bin/env python3
"""
后处理脚本（Gitee 版）
--------------------------------------------------
1. 从 Gitee 拉取旧内容（clone 或 pull --rebase）
2. 读取 llm_experiment_results/results.jsonl（输入）
3. 对 condition == "word_pairs" 的记录，用 LLM 去掉开头的 200 组词对
   -> 增量写入 llm_experiment_results/cleaned.jsonl 与 cleaned/
4. 对每个任务，用 LLM 盲评「清洗后的 word_pairs」vs「baseline」
   -> 增量写入 llm_experiment_results/comparison.jsonl 与 comparison/
5. 每步完成后自动 git commit（按间隔 push 到 Gitee）
   - 只新增，不删除/覆盖旧内容
   - push 前先 fetch + rebase，冲突则 abort 并保留本地 commit
"""

import asyncio
import json
import os
import random
import re
import subprocess
import threading
import time
from pathlib import Path

from openai import AsyncOpenAI

# ============ 配置 ============
API_KEY     = os.environ.get("OPENAI_API_KEY",
                             "")
BASE_URL    = os.environ.get("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL       = os.environ.get("LLM_MODEL", "moonshotai/kimi-k3")
TEMPERATURE = 0.3
CONCURRENCY = 2
MAX_RETRIES = 20
PER_CALL_TIMEOUT = 600
RETRY_TOTAL_BUDGET = 600

OUTPUT_DIR      = Path("llm_experiment_results")
RESULTS_PATH    = OUTPUT_DIR / "results.jsonl"       # 输入（来自 Gitee）
CLEANED_PATH    = OUTPUT_DIR / "cleaned.jsonl"       # 输出（增量）
COMPARISON_PATH = OUTPUT_DIR / "comparison.jsonl"    # 输出（增量）
CLEANED_DIR     = OUTPUT_DIR / "cleaned"
COMPARISON_DIR  = OUTPUT_DIR / "comparison"

# ============ Git 配置 ============
GIT_REMOTE_URL = os.environ.get(
    "GIT_REMOTE_URL",
    "https://gitee.com/qwe12345678/jkdsfn.git",
)
GIT_BRANCH        = os.environ.get("GIT_BRANCH", "main")
GIT_PUSH_INTERVAL = int(os.environ.get("GIT_PUSH_INTERVAL", "5"))

# ============ 任务表（与生成脚本保持一致） ============
TASKS_BY_ID = {
    1: {"id": 1, "name": "函数式编程语言", "prompt": "设计一个全新的函数式编程语言"},
    2: {"id": 2, "name": "提升LLM性能",   "prompt": "怎么低成本不需要额外训练大幅提升现有LLM的性能"},
    3: {"id": 3, "name": "CLI工具Idea",   "prompt": "给出适合独立开发者开发CLI工具的一个Idea"},
    4: {"id": 4, "name": "新理论",        "prompt": "提出一个新的理论"},
    5: {"id": 5, "name": "人格模型",      "prompt": "提出一个新的类似于九型和荣格八维的模型"},
    6: {"id": 6, "name": "ML架构",        "prompt": "提出一个新的机器学习架构"},
}

# ============ Prompt 模板 ============
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

    # 1) 目录不存在或为空 → clone
    if not OUTPUT_DIR.exists() or not any(OUTPUT_DIR.iterdir()):
        OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
        r = _run_git(
            ["clone", "-b", GIT_BRANCH, GIT_REMOTE_URL, str(OUTPUT_DIR)],
            cwd=OUTPUT_DIR.parent,
        )
        if r and r.returncode == 0:
            print(f"[Git] clone 成功 → {OUTPUT_DIR}", flush=True)
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

    # 2) 目录存在但不是 git 仓库 → init + fetch + merge
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

    # 3) 已是仓库 → remote 校正 → 先提交未提交改动 → pull --rebase
    _run_git(["remote", "set-url", "origin", GIT_REMOTE_URL], cwd=OUTPUT_DIR)
    _run_git(["config", "user.email", "auto@experiment.local"], cwd=OUTPUT_DIR)
    _run_git(["config", "user.name",  "auto-experiment"], cwd=OUTPUT_DIR)

    r = _run_git(["status", "--porcelain"], cwd=OUTPUT_DIR)
    if r and r.stdout.strip():
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


# ============ LLM 调用 ============
async def call_llm(client: AsyncOpenAI, prompt: str) -> dict:
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


# ============ 阶段 1：清洗 word_pairs ============
async def clean_one(client, semaphore, record) -> dict | None:
    content = record.get("content") or ""
    if not content or content.startswith("[ERROR]"):
        print(f"[跳过清洗] task{record['task_id']} run{record['run']} 无有效内容", flush=True)
        return None

    prompt = CLEAN_PROMPT.format(content=content)

    async with semaphore:
        result = await call_llm(client, prompt)

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

    print(f"[清洗完成] 任务{record['task_id']} {record['task_name']} | "
          f"run {record['run']:2d} | {result['elapsed']}s", flush=True)

    n = _next_commit_count()
    _git_commit_and_push(
        OUTPUT_DIR,
        f"clean: task{record['task_id']} word_pairs run{record['run']} "
        f"[{n} total, {result['elapsed']}s]",
        push=(n % GIT_PUSH_INTERVAL == 0),
    )
    return rec


async def run_cleaning(records_to_clean: list) -> list:
    print(f"\n========== 阶段 1：清洗 word_pairs 输出（{len(records_to_clean)} 条）==========",
          flush=True)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    if not records_to_clean:
        print("[清洗] 无新增记录，跳过", flush=True)
        return []

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    tasks = [clean_one(client, semaphore, r) for r in records_to_clean]
    cleaned = await asyncio.gather(*tasks)
    cleaned = [c for c in cleaned if c]

    _git_commit_and_push(
        OUTPUT_DIR,
        f"clean: 阶段1完成，本次清洗 {len(cleaned)} 条",
        push=True,
    )
    print(f"\n[阶段1完成] 本次清洗 {len(cleaned)} 条", flush=True)
    return cleaned


# ============ 阶段 2：盲评比较 ============
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
    cleaned_ans  = cleaned_rec.get("cleaned_content") or ""

    if not baseline_ans or baseline_ans.startswith("[ERROR]"):
        return None
    if not cleaned_ans or cleaned_ans.startswith("[ERROR]"):
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
        result = await call_llm(client, prompt)

    parsed = _parse_compare_json(result["content"] or "")
    winner_raw = winner_label = None
    scores_a = scores_b = reason = None
    if parsed:
        winner_raw = parsed.get("winner")
        scores_a = parsed.get("A")
        scores_b = parsed.get("B")
        reason   = parsed.get("reason")
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

    print(f"[比较完成] 任务{task['id']} {task['name']} | run {run_idx:2d} | "
          f"winner={winner_label} | {result['elapsed']}s", flush=True)

    n = _next_commit_count()
    _git_commit_and_push(
        OUTPUT_DIR,
        f"cmp: task{task['id']} run{run_idx} winner={winner_label} [{n} total]",
        push=(n % GIT_PUSH_INTERVAL == 0),
    )
    return rec


async def run_comparison(pairs: list) -> list:
    print(f"\n========== 阶段 2：盲评比较（{len(pairs)} 对）==========", flush=True)
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

    if not pairs:
        print("[比较] 无新增配对，跳过", flush=True)
        return []

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    semaphore = asyncio.Semaphore(CONCURRENCY)

    jobs = []
    for task_id, run_i, base_rec, clean_rec in pairs:
        task = TASKS_BY_ID.get(task_id)
        if not task:
            continue
        jobs.append(compare_one(client, semaphore, task, run_i, base_rec, clean_rec))

    results = await asyncio.gather(*jobs)
    results = [r for r in results if r]

    _git_commit_and_push(
        OUTPUT_DIR,
        f"cmp: 阶段2完成，本次比较 {len(results)} 对",
        push=True,
    )
    print(f"\n[阶段2完成] 本次比较 {len(results)} 对", flush=True)
    return results


# ============ 汇总统计 ============
def print_summary(comparisons: list):
    print("\n========== 汇总统计（全部历史记录） ==========", flush=True)
    if not comparisons:
        print("（无比较记录）", flush=True)
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


# ============ 主流程 ============
async def main():
    # 1) 从 Gitee 同步旧内容
    _sync_from_gitee()

    # 2) 读取 results.jsonl（输入）
    if not RESULTS_PATH.exists():
        print(f"[错误] 同步后仍找不到 {RESULTS_PATH}，请先运行生成脚本", flush=True)
        return

    all_records = _load_jsonl(RESULTS_PATH)
    print(f"[读取] results.jsonl 共 {len(all_records)} 条", flush=True)

    baseline_by_task = {}
    wp_records = []
    for r in all_records:
        if r.get("condition") == "baseline":
            baseline_by_task.setdefault(r["task_id"], {})[r["run"]] = r
        elif r.get("condition") == "word_pairs":
            wp_records.append(r)

    # 3) 阶段 1：只清洗 cleaned.jsonl 里没有过的 (task_id, run)
    existing_cleaned_keys = {
        (r["task_id"], r["run"]) for r in _load_jsonl(CLEANED_PATH)
    }
    to_clean = [
        r for r in wp_records
        if (r["task_id"], r["run"]) not in existing_cleaned_keys
    ]
    print(f"[清洗] 需清洗 {len(wp_records)} 条，其中新增 {len(to_clean)} 条", flush=True)
    await run_cleaning(to_clean)

    # 4) 阶段 2：只用 baseline + 完整 cleaned.jsonl 做配对，跳过已比较的
    all_cleaned = _load_jsonl(CLEANED_PATH)
    cleaned_by_task = {}
    for r in all_cleaned:
        cleaned_by_task.setdefault(r["task_id"], {})[r["run"]] = r

    existing_cmp_keys = {
        (r["task_id"], r["run"]) for r in _load_jsonl(COMPARISON_PATH)
    }

    pairs = []
    for task_id in sorted(TASKS_BY_ID.keys()):
        base_runs  = baseline_by_task.get(task_id, {})
        clean_runs = cleaned_by_task.get(task_id, {})
        common = sorted(set(base_runs.keys()) & set(clean_runs.keys()))
        for run_i in common:
            if (task_id, run_i) in existing_cmp_keys:
                continue
            pairs.append((task_id, run_i, base_runs[run_i], clean_runs[run_i]))

    print(f"[比较] 可配对 {sum(len(v) for v in baseline_by_task.values())} baseline "
          f"/ 已清洗 {len(all_cleaned)} 条 → 本次新增 {len(pairs)} 对", flush=True)
    await run_comparison(pairs)

    # 5) 汇总（读全量历史）
    print_summary(_load_jsonl(COMPARISON_PATH))

    # 6) 最终 push 一次
    _git_commit_and_push(OUTPUT_DIR, "done: 同步 + 清洗 + 比较完成", push=True)
    print("\n全部完成。", flush=True)


def run_main():
    """兼容脚本 / Jupyter"""
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

    t = threading.Thread(target=_worker, name="llm-postprocess")
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]


if __name__ == "__main__":
    run_main()
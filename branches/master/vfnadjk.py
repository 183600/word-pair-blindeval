# ===== Cell 1: 安装依赖 + 设置 =====
# Notebook里可用下面这行；脚本运行时请注释掉
# !pip install httpx -q

import os
import json
import time
import re
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager

try:
    import httpx
except ImportError:
    print("请安装httpx库: pip install httpx")
    raise

os.environ["NVIDIA_API_KEY"] = "xxxxx"  # 请替换为你的真实密钥


# ============================================================
# 配置常量
# ============================================================

API_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODELS = [
    "qwen/qwen3.5-397b-a17b",
    "z-ai/glm-5.1",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2.6",
]

# 6个创新问题
PROBLEMS = [
    {
        "id": "P1",
        "domain": "编程语言设计",
        "title": "设计一个全新的函数式编程语言",
        "description": (
            "设计一个全新的函数式编程语言，需要在范式、类型系统、"
            "求值策略或抽象机制上有真正的创新，"
            "而不是对现有语言的微小变体。"
        ),
        "extra_instruction": "",
    },
    {
        "id": "P2",
        "domain": "LLM性能提升",
        "title": "怎么低成本不需要额外训练大幅提升现有LLM的性能",
        "description": (
            "怎么低成本不需要额外训练大幅提升现有LLM的性能，"
            "通过修改模型，我发现LLM思考时有时候不会考虑到模型"
            "（这里说的是模型而不是prompt）里面存储的所有相关的信息"
        ),
        "extra_instruction": "如果方案涉及技术实现，请给出可以直接运行的完整的在kaggle上面做实验的代码。",
    },
    {
        "id": "P3",
        "domain": "独立开发者CLI工具",
        "title": "给出适合独立开发者开发CLI工具的一个Idea",
        "description": (
            "给出适合独立开发者开发CLI工具的一个Idea，"
            "要求价值极大但实现简单，并且别人没有开发过，"
            "需要明确工具的目标用户、核心功能、与现有工具的差异点。"
        ),
        "extra_instruction": "",
    },
    {
        "id": "P4",
        "domain": "新理论",
        "title": "提出一个新的理论",
        "description": (
            "提出一个新的理论，可以是任何领域的新理论，"
            "但需要有清晰的公理/假设基础、推导逻辑和可检验的预测，"
            "理论应当具有解释力和预测力，而非仅仅是描述性的分类。"
        ),
        "extra_instruction": "",
    },
    {
        "id": "P5",
        "domain": "新人格/认知模型",
        "title": "提出一个新的类似于九型和荣格八维的模型",
        "description": (
            "提出一个新的类似于九型人格和荣格八维的人格/认知模型，"
            "需要定义模型的基本维度、类型划分逻辑、类型间的关系/转化路径，"
            "以及模型相比九型和荣格八维的创新点和优势。"
        ),
        "extra_instruction": "",
    },
    {
        "id": "P6",
        "domain": "新机器学习架构",
        "title": "提出一个新的机器学习架构",
        "description": (
            "提出一个新的机器学习架构，"
            "需要明确与Transformer/CNN/RNN等现有架构的本质差异、"
            "核心计算机制、适用场景、理论优势。"
        ),
        "extra_instruction": (
            "给出可以直接运行的完整的在kaggle上面做实验的代码，"
            "用一个小规模实验验证该架构的可行性。"
        ),
    },
]

# 实验条件定义（3×2正交因子设计+温度控制）
CONDITIONS = {
    "A": {"name": "基线",              "rws": False, "mode": "none",            "temperature": 0.7},
    "B": {"name": "仅RWS",             "rws": True,  "mode": "none",            "temperature": 0.7},
    "C": {"name": "仅评估",            "rws": False, "mode": "evaluate",        "temperature": 0.7},
    "D": {"name": "RWS+评估",          "rws": True,  "mode": "evaluate",        "temperature": 0.7},
    "E": {"name": "评估+修改",         "rws": False, "mode": "evaluate_revise", "temperature": 0.7},
    "F": {"name": "RWS+评估+修改",     "rws": True,  "mode": "evaluate_revise", "temperature": 0.7},
    "G": {"name": "高温基线",          "rws": False, "mode": "none",            "temperature": 1.2},
}


# ============================================================
# 原子写文件工具（关键修改：确保每次LLM调用后写非raw文件也安全）
# ============================================================

@contextmanager
def _atomic_open(path: Path, mode: str = "w", encoding: Optional[str] = "utf-8", newline=None):
    """
    原子写：写到 .tmp 文件，成功后 replace 到目标文件，避免中途崩溃导致文件损坏。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    f = None
    try:
        f = open(tmp, mode=mode, encoding=encoding, newline=newline)
        yield f
        f.flush()
        os.fsync(f.fileno())
        f.close()
        f = None
        tmp.replace(path)
    finally:
        try:
            if f is not None:
                f.close()
        except Exception:
            pass


def _atomic_write_json(path: Path, data: dict, ensure_ascii: bool = False, indent: int = 2):
    with _atomic_open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)


# ============================================================
# Prompt 构建（一次任务只有一个 prompt）
# ============================================================

def build_prompt(problem: dict, condition_id: str) -> str:
    cond = CONDITIONS[condition_id]
    desc = problem["description"]
    extra = problem.get("extra_instruction", "")
    rws = cond["rws"]
    mode = cond["mode"]

    prompt = "设计一个方案，"

    if rws:
        prompt += "在新的方案前面输出200组词，每组有两个词，从这些词获得灵感，"

    prompt += "确保这个方案是之前没有的，并且低成本，并且具有可行性"

    if mode == "evaluate":
        prompt += "\n生成方案之后判断这个方案好不好"
    elif mode == "evaluate_revise":
        prompt += "\n生成方案之后判断这个方案好不好，如果不好就生成新的方案，然后再判断这个方案好不好，直到判断这个方案好为止"

    prompt += f"\n{desc}"

    if extra:
        prompt += f"\n{extra}"

    if mode == "evaluate_revise":
        prompt += "\n\n在最后用【最终方案】标记输出最终确定的方案。"
    elif mode == "evaluate":
        prompt += "\n\n用【最终方案】标记输出你的方案。"

    return prompt


# ============================================================
# 结果提取工具
# ============================================================

def extract_final_scheme(text: str, mode: str) -> str:
    if mode == "none":
        return text

    markers = ["【最终方案】", "[最终方案]", "**最终方案**"]
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            extracted = text[idx + len(marker):].strip()
            if extracted:
                return extracted

    if mode == "evaluate":
        eval_markers = ["【自我评估】", "[自我评估]", "新颖性：", "新颖性:",
                        "判断这个方案", "评估：", "评估:"]
        for marker in eval_markers:
            idx = text.find(marker)
            if idx != -1:
                return text[:idx].strip()

    return text


def parse_word_pairs(text: str) -> List[List[str]]:
    pairs = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r'^[\d]+[.、):）\]]\s*', '', line).strip()
        if not cleaned:
            continue
        parts = None
        for sep in [',', '，', '、', ' ']:
            if sep in cleaned:
                parts = [p.strip() for p in cleaned.split(sep) if p.strip()]
                break
        if parts and len(parts) == 2 and all(len(p) >= 1 for p in parts):
            if all(len(p) <= 10 for p in parts):
                pairs.append(parts)
    return pairs


# ============================================================
# API客户端（流式响应 + 健壮错误处理 + 修复429解析 + 抖动）
# ============================================================

class NvidiaNIMClient:
    """NVIDIA NIM API客户端，使用流式响应避免网关超时"""

    def __init__(self, api_key: str, base_url: str = API_BASE_URL,
                 max_retries: int = 10, retry_base_delay: float = 5.0,
                 max_rate_limit_retries: int = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.max_rate_limit_retries = max_rate_limit_retries

        self._http_client = httpx.Client(
            timeout=httpx.Timeout(900.0, connect=30.0, read=900.0, write=60.0, pool=30.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    def __del__(self):
        try:
            self._http_client.close()
        except Exception:
            pass

    def _stream_request(self, url: str, headers: dict, payload: dict) -> Optional[str]:
        """流式响应调用API。返回内容或特殊错误字符串 __HTTP_ERROR_<CODE>__:..."""
        content_parts = []
        try:
            with self._http_client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_body = b""
                    for chunk in response.iter_bytes():
                        error_body += chunk
                        if len(error_body) > 2000:
                            break
                    error_text = error_body.decode("utf-8", errors="replace")
                    return f"__HTTP_ERROR_{response.status_code}__:{error_text[:500]}"

                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                    else:
                        continue

                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    piece = delta.get("content")
                    if piece and isinstance(piece, str):
                        content_parts.append(piece)
                    piece_rc = delta.get("reasoning_content")
                    if piece_rc and isinstance(piece_rc, str) and not piece:
                        content_parts.append(piece_rc)

        except httpx.TimeoutException:
            raise
        except Exception as e:
            if content_parts:
                logging.warning(f"流式读取中途异常，返回已获取的部分内容: {str(e)[:200]}")
                return "".join(content_parts)
            raise

        result = "".join(content_parts).strip()
        return result if result else None

    def chat(self, model: str, prompt: str, temperature: float = 0.7,
             max_tokens: int = 16384) -> Optional[str]:
        """调用chat completion API，流式响应 + 指数退避重试 + 抖动"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        normal_attempt = 0
        rate_limit_attempt = 0

        while True:
            if normal_attempt >= self.max_retries and rate_limit_attempt >= self.max_rate_limit_retries:
                logging.error(f"模型 {model} 调用彻底失败: 正常重试{normal_attempt}次, 限速重试{rate_limit_attempt}次")
                return None

            try:
                result = self._stream_request(url, headers, payload)

                if result and result.startswith("__HTTP_ERROR_"):
                    m = re.match(r'__HTTP_ERROR_(\d+)__', result)
                    if m:
                        status_code = int(m.group(1))
                        error_detail = result[len(f"__HTTP_ERROR_{status_code}__:"):] if ":" in result else ""

                        if status_code == 429:
                            rate_limit_attempt += 1
                            if rate_limit_attempt > self.max_rate_limit_retries:
                                logging.error(f"模型 {model} 429限速重试已耗尽({rate_limit_attempt}次)")
                                return None
                            wait = min(60 + (rate_limit_attempt - 1) * 10, 300) + random.uniform(0, 10)
                            logging.warning(
                                f"速率限制 429 (模型: {model}), 等待 {wait:.1f}s 后重试 "
                                f"(限速重试 {rate_limit_attempt}/{self.max_rate_limit_retries})"
                            )
                            time.sleep(wait)
                            continue

                        elif status_code in (500, 502, 503, 504):
                            normal_attempt += 1
                            if normal_attempt > self.max_retries:
                                logging.error(f"模型 {model} {status_code}重试已耗尽({normal_attempt}次)")
                                return None
                            wait = min(self.retry_base_delay * (2 ** min(normal_attempt - 1, 6)), 120) + random.uniform(0, 5)
                            logging.warning(
                                f"服务器错误 {status_code} (模型: {model}), 等待 {wait:.1f}s 后重试 "
                                f"(重试 {normal_attempt}/{self.max_retries}): {error_detail[:200]}"
                            )
                            time.sleep(wait)
                            continue

                        else:
                            normal_attempt += 1
                            if normal_attempt > self.max_retries:
                                logging.error(f"模型 {model} HTTP {status_code} 重试已耗尽")
                                return None
                            wait = min(self.retry_base_delay * (2 ** min(normal_attempt - 1, 6)), 120) + random.uniform(0, 3)
                            logging.warning(
                                f"API错误 {status_code} (模型: {model}), 等待 {wait:.1f}s 后重试: {error_detail[:200]}"
                            )
                            time.sleep(wait)
                            continue
                    else:
                        normal_attempt += 1
                        if normal_attempt > self.max_retries:
                            logging.error(f"模型 {model} 返回无法解析的错误: {result[:200]}")
                            return None
                        logging.warning(f"模型 {model} 返回未知错误格式，重试 {normal_attempt}/{self.max_retries}")
                        time.sleep(self.retry_base_delay + random.uniform(0, 2))
                        continue

                if result and result.strip():
                    return result.strip()

                normal_attempt += 1
                if normal_attempt > self.max_retries:
                    logging.error(f"模型 {model} 返回空内容，重试已耗尽({normal_attempt}次)")
                    return None
                logging.warning(f"模型 {model} 返回空内容，重试中 ({normal_attempt}/{self.max_retries})...")
                time.sleep(self.retry_base_delay + random.uniform(0, 2))

            except httpx.TimeoutException:
                normal_attempt += 1
                if normal_attempt > self.max_retries:
                    logging.error(f"模型 {model} 超时失败，重试已耗尽({normal_attempt}次)")
                    return None
                wait = min(self.retry_base_delay * (2 ** min(normal_attempt - 1, 6)), 120) + random.uniform(0, 5)
                logging.warning(
                    f"API超时 (模型: {model}), 等待 {wait:.1f}s 后重试 "
                    f"(重试 {normal_attempt}/{self.max_retries})"
                )
                time.sleep(wait)

            except httpx.ConnectError as e:
                normal_attempt += 1
                if normal_attempt > self.max_retries:
                    logging.error(f"模型 {model} 连接失败: {str(e)[:300]}")
                    return None
                wait = min(self.retry_base_delay * (2 ** min(normal_attempt - 1, 6)), 120) + random.uniform(0, 5)
                logging.warning(f"连接错误 (模型: {model}, 重试 {normal_attempt}/{self.max_retries}): {str(e)[:200]}")
                time.sleep(wait)

            except Exception as e:
                normal_attempt += 1
                if normal_attempt > self.max_retries:
                    logging.error(f"模型 {model} 调用彻底失败: {str(e)[:500]}")
                    return None
                wait = min(self.retry_base_delay * (2 ** min(normal_attempt - 1, 6)), 120) + random.uniform(0, 3)
                logging.warning(
                    f"API调用异常 (模型: {model}, 重试 {normal_attempt}/{self.max_retries}): {str(e)[:300]}"
                )
                time.sleep(wait)


# ============================================================
# 输出保存函数
# ============================================================

def _save_raw(raw_path: Path, timestamp: str, model_safe: str, pid: str,
              cond_id: str, repeat: int, result: dict):
    raw_file = raw_path / f"{timestamp}_{model_safe}_{pid}_{cond_id}_R{repeat}.json"
    _atomic_write_json(raw_file, result, ensure_ascii=False, indent=2)


def _save_readable_summary(results: list, output_file: Path):
    with _atomic_open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("创新方案生成实验结果摘要\n")
        f.write("3×2正交因子设计 + 温度控制 | RWS: LLM自生成200组词对\n")
        f.write("每任务单次API调用(流式响应)，所有指令合并为一条prompt\n")
        f.write("=" * 80 + "\n\n")

        f.write("【实验设计】\n")
        f.write("条件A: 基线 (无RWS, 无自评估, temp=0.7)\n")
        f.write("条件B: 仅RWS (LLM生成200组词对, 无自评估, temp=0.7)\n")
        f.write("条件C: 仅评估 (无RWS, 生成后评估不修改, temp=0.7)\n")
        f.write("条件D: RWS+评估 (LLM生成200组词对, 生成后评估不修改, temp=0.7)\n")
        f.write("条件E: 评估+修改 (无RWS, 生成后评估,不好就改直到好, temp=0.7)\n")
        f.write("条件F: RWS+评估+修改 (LLM生成200组词对, 生成后评估,不好就改直到好, temp=0.7)\n")
        f.write("条件G: 高温基线 (无RWS, 无自评估, temp=1.2)\n\n")

        f.write("【问题列表】\n")
        for p in PROBLEMS:
            f.write(f"  {p['id']}: {p['title']} ({p['domain']})\n")
        f.write("\n")

        for r in results:
            sep = "─" * 80
            if r.get("status") != "success":
                f.write(sep + "\n")
                f.write(f"[FAILED] {r.get('task_id','')} - 状态: {r.get('status')}\n\n")
                continue

            f.write(sep + "\n")
            f.write(f"模型: {r['model']}\n")
            f.write(f"问题: {r['problem_id']} - {r.get('problem_title', '')} ({r['problem_domain']})\n")
            f.write(f"条件: {r['condition']} - {r['condition_name']}\n")
            f.write(
                f"RWS: {'是' if r['rws'] else '否'} | "
                f"模式: {r['mode']} | "
                f"温度: {r['temperature']}\n"
            )
            if r.get("word_pairs_count", 0) > 0:
                f.write(f"随机词对数: {r['word_pairs_count']}组\n")
            f.write(f"重复: 第{r['repeat']}次\n\n")

            f.write("【Prompt】\n")
            f.write(r.get("prompt", "") + "\n\n")

            f.write("【LLM完整输出】\n")
            f.write(r.get("output", "") + "\n\n")

            f.write("【提取的最终方案】\n")
            f.write(r.get("final_scheme", "") + "\n\n")

        f.write("=" * 80 + "\n")
        f.write("摘要结束\n")


def _save_for_evaluation(results: list, output_file: Path):
    eval_data = []
    for r in results:
        if r.get("status") != "success":
            continue
        eval_data.append({
            "task_id": r["task_id"],
            "model": r["model"],
            "problem_id": r["problem_id"],
            "problem_domain": r["problem_domain"],
            "problem_title": r.get("problem_title", ""),
            "condition": r["condition"],
            "condition_name": r["condition_name"],
            "rws": r["rws"],
            "mode": r["mode"],
            "temperature": r["temperature"],
            "repeat": r["repeat"],
            "word_pairs_count": r.get("word_pairs_count", 0),
            "prompt": r.get("prompt", ""),
            "final_scheme": r.get("final_scheme", ""),
        })

    _atomic_write_json(output_file, eval_data, ensure_ascii=False, indent=2)


def _save_csv(results: list, output_file: Path):
    import csv

    headers = [
        "task_id", "model", "problem_id", "problem_domain", "problem_title",
        "condition", "condition_name", "rws", "mode", "temperature",
        "repeat", "word_pairs_count",
        "prompt", "final_scheme", "status",
    ]

    with _atomic_open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = dict(r)
            if "rws" in row:
                row["rws"] = "Y" if row["rws"] else "N"
            for key in ["prompt", "final_scheme"]:
                val = row.get(key, "")
                row[key] = (val.replace("\n", " ").replace("\r", "")) if val else ""
            writer.writerow(row)


# ============================================================
# 关键新增：每次LLM调用后也保存“非raw”文件（results/summary/eval/csv）
# ============================================================

def _save_non_raw_outputs(
    output_path: Path,
    timestamp: str,
    results: list,
    model_list: list,
    cond_list: list,
    problem_list: list,
    n_repeats: int,
    total_schemes: int,
):
    all_success = sum(1 for r in results if r.get("status") == "success")
    all_fail = sum(1 for r in results if r.get("status") != "success")

    consolidated = {
        "experiment_info": {
            "timestamp": timestamp,
            "last_update": datetime.now().isoformat(),
            "total_schemes_planned": total_schemes,
            "success_count": all_success,
            "fail_count": all_fail,
            "success_rate": all_success / (all_success + all_fail) if (all_success + all_fail) > 0 else 0,
            "models": model_list,
            "conditions": cond_list,
            "n_problems": len(problem_list),
            "n_repeats": n_repeats,
            "design": "3x2 orthogonal factorial design + temperature control",
            "rws_mechanism": "LLM self-generates 200 word pairs before solution",
            "api_calls_per_task": 1,
            "prompt_style": "concise direct style (reference-based)",
            "streaming": True,
            "checkpoint": True,  # 标记这是可持续覆盖写入的checkpoint
        },
        "results": results,
    }

    result_file = output_path / f"results_{timestamp}.json"
    summary_file = output_path / f"summary_{timestamp}.txt"
    eval_file = output_path / f"for_evaluation_{timestamp}.json"
    csv_file = output_path / f"for_evaluation_{timestamp}.csv"

    _atomic_write_json(result_file, consolidated, ensure_ascii=False, indent=2)
    _save_readable_summary(results, summary_file)
    _save_for_evaluation(results, eval_file)
    _save_csv(results, csv_file)


# ============================================================
# 实验核心逻辑
# ============================================================

def run_experiment(
    client: NvidiaNIMClient,
    n_repeats: int = 3,
    output_dir: str = "output",
    condition_filter: Optional[List[str]] = None,
    model_filter: Optional[List[str]] = None,
    problem_filter: Optional[List[str]] = None,
    delay: float = 1.0,
    max_tokens: int = 16384,
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    raw_path = output_path / "raw"
    raw_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    cond_list = condition_filter if condition_filter else list(CONDITIONS.keys())
    model_list = model_filter if model_filter else MODELS
    problem_list = [p for p in PROBLEMS if not problem_filter or p["id"] in problem_filter]

    total_schemes = len(model_list) * len(problem_list) * len(cond_list) * n_repeats

    logging.info("=" * 70)
    logging.info("创新方案生成实验 (3×2正交因子设计+温度控制)")
    logging.info("=" * 70)
    logging.info(f"时间戳:       {timestamp}")
    logging.info(f"模型数:       {len(model_list)}")
    logging.info(f"问题数:       {len(problem_list)}")
    logging.info(f"条件数:       {len(cond_list)} -> {cond_list}")
    logging.info(f"重复数:       {n_repeats}")
    logging.info(f"总方案数:     {total_schemes}")
    logging.info(f"API调用数:    {total_schemes} (每任务1次, 流式响应)")
    logging.info("=" * 70)

    # ---- 断点续传：扫描已有raw文件（关键改进：加载所有raw结果，并支持checkpoint持续写入） ----
    existing_success_tasks = set()
    results_map = {}     # task_id -> result
    results_order = []   # 保持稳定顺序

    for fp in sorted(raw_path.glob("*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                existing = json.load(f)
            tid = existing.get("task_id")
            if not tid:
                continue
            if tid not in results_map:
                results_order.append(tid)
            results_map[tid] = existing
            if existing.get("status") == "success":
                existing_success_tasks.add(tid)
        except Exception:
            pass

    if existing_success_tasks:
        logging.info(f"发现 {len(existing_success_tasks)} 个已完成(success)任务，将跳过")

    # 初始就写一次非raw文件（避免“只有raw没有汇总”的情况）
    results = [results_map[tid] for tid in results_order]
    _save_non_raw_outputs(
        output_path=output_path,
        timestamp=timestamp,
        results=results,
        model_list=model_list,
        cond_list=cond_list,
        problem_list=problem_list,
        n_repeats=n_repeats,
        total_schemes=total_schemes,
    )

    total_to_do = total_schemes - len(existing_success_tasks)
    completed_new = 0

    for model in model_list:
        model_safe = model.replace("/", "_")
        for problem in problem_list:
            pid = problem["id"]

            for cond_id in cond_list:
                cond = CONDITIONS[cond_id]

                for repeat in range(1, n_repeats + 1):
                    task_id = f"{model}|{pid}|{cond_id}|R{repeat}"

                    if task_id in existing_success_tasks:
                        continue

                    completed_new += 1
                    logging.info(
                        f"[{completed_new}/{total_to_do}] {task_id} "
                        f"(RWS={'Y' if cond['rws'] else 'N'}, mode={cond['mode']}, T={cond['temperature']})"
                    )

                    prompt = build_prompt(problem, cond_id)

                    result = {
                        "task_id": task_id,
                        "model": model,
                        "problem_id": pid,
                        "problem_domain": problem["domain"],
                        "problem_title": problem["title"],
                        "condition": cond_id,
                        "condition_name": cond["name"],
                        "rws": cond["rws"],
                        "mode": cond["mode"],
                        "temperature": cond["temperature"],
                        "repeat": repeat,
                        "timestamp": datetime.now().isoformat(),
                        "status": "pending",
                        "prompt": prompt,
                        "word_pairs": None,
                        "word_pairs_count": 0,
                        "output": None,
                        "final_scheme": None,
                    }

                    output = client.chat(
                        model=model,
                        prompt=prompt,
                        temperature=cond["temperature"],
                        max_tokens=max_tokens,
                    )

                    if output is None:
                        result["status"] = "api_failed"
                        # 保存raw
                        _save_raw(raw_path, timestamp, model_safe, pid, cond_id, repeat, result)

                        # 写入results_map并立刻保存非raw文件（关键需求）
                        if task_id not in results_map:
                            results_order.append(task_id)
                        results_map[task_id] = result
                        results = [results_map[tid] for tid in results_order]
                        _save_non_raw_outputs(
                            output_path=output_path,
                            timestamp=timestamp,
                            results=results,
                            model_list=model_list,
                            cond_list=cond_list,
                            problem_list=problem_list,
                            n_repeats=n_repeats,
                            total_schemes=total_schemes,
                        )

                        time.sleep(delay + random.uniform(0, 2))
                        continue

                    result["output"] = output
                    result["final_scheme"] = extract_final_scheme(output, cond["mode"])

                    if cond["rws"]:
                        word_pairs = parse_word_pairs(output)
                        result["word_pairs"] = word_pairs
                        result["word_pairs_count"] = len(word_pairs)
                        logging.info(f"  RWS: 从输出中解析到 {len(word_pairs)} 组词对")

                    result["status"] = "success"

                    # 保存raw
                    _save_raw(raw_path, timestamp, model_safe, pid, cond_id, repeat, result)

                    # 写入results_map并立刻保存非raw文件（关键需求：每次LLM调用后保存除raw外的文件）
                    if task_id not in results_map:
                        results_order.append(task_id)
                    results_map[task_id] = result
                    results = [results_map[tid] for tid in results_order]
                    _save_non_raw_outputs(
                        output_path=output_path,
                        timestamp=timestamp,
                        results=results,
                        model_list=model_list,
                        cond_list=cond_list,
                        problem_list=problem_list,
                        n_repeats=n_repeats,
                        total_schemes=total_schemes,
                    )

                    logging.info(f"  成功! 输出长度: {len(output)} 字符")
                    time.sleep(delay + random.uniform(0, 2))

    # 最终再保存一次（checkpoint->最终状态）
    results = [results_map[tid] for tid in results_order]
    _save_non_raw_outputs(
        output_path=output_path,
        timestamp=timestamp,
        results=results,
        model_list=model_list,
        cond_list=cond_list,
        problem_list=problem_list,
        n_repeats=n_repeats,
        total_schemes=total_schemes,
    )

    all_success = sum(1 for r in results if r.get("status") == "success")
    all_fail = sum(1 for r in results if r.get("status") != "success")

    logging.info("=" * 70)
    logging.info(f"实验完成: 成功 {all_success}, 失败 {all_fail}")
    logging.info(f"输出目录: {output_path}")
    logging.info("=" * 70)

    return results


# ============================================================
# 辅助工具
# ============================================================

def print_experiment_plan(condition_filter=None, model_filter=None,
                          problem_filter=None, n_repeats=3):
    cond_list = condition_filter if condition_filter else list(CONDITIONS.keys())
    model_list = model_filter if model_filter else MODELS
    problem_list = [p for p in PROBLEMS if not problem_filter or p["id"] in problem_filter]

    print("\n" + "=" * 70)
    print("实验计划")
    print("=" * 70)
    print(f"模型: {len(model_list)}")
    for m in model_list:
        print(f"  - {m}")
    print(f"问题: {len(problem_list)}")
    for p in problem_list:
        print(f"  - {p['id']}: {p['title']} ({p['domain']})")
    print(f"条件: {len(cond_list)} -> {cond_list}")
    print(f"重复: {n_repeats}")
    total = len(model_list) * len(problem_list) * len(cond_list) * n_repeats
    print(f"总方案数: {total}")
    print(f"API调用数: {total} (每任务1次, 流式响应)")

    for cid in cond_list:
        cond = CONDITIONS[cid]
        n = len(model_list) * len(problem_list) * n_repeats
        rws_tag = " [RWS: LLM生成200组词对]" if cond["rws"] else ""
        mode_desc = {
            "none": "直接生成",
            "evaluate": "生成+评估(不修改)",
            "evaluate_revise": "生成+评估+迭代修改",
        }
        print(
            f"  条件{cid} ({cond['name']}{rws_tag}): "
            f"{n}方案, 模式={mode_desc[cond['mode']]}"
        )

    print("=" * 70 + "\n")


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="创新方案生成实验脚本 (3×2正交因子设计, 每任务单次prompt, 流式响应)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="output")
    parser.add_argument("--n-repeats", type=int, default=3)
    parser.add_argument("--conditions", type=str, nargs="+", default=None)
    parser.add_argument("--models", type=str, nargs="+", default=None)
    parser.add_argument("--problems", type=str, nargs="+", default=None)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--delay", type=float, default=100.0)
    parser.add_argument("--retry", type=int, default=10)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    model_filter = None
    if args.models:
        model_filter = [m.replace("~", "/") for m in args.models]

    if args.plan_only:
        print_experiment_plan(args.conditions, model_filter, args.problems, args.n_repeats)
        return

    log_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"experiment_{log_ts}.log", encoding="utf-8"),
        ],
    )

    api_key = args.api_key or os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        logging.error("请设置NVIDIA_API_KEY环境变量或使用--api-key参数")
        raise SystemExit(1)

    client = NvidiaNIMClient(api_key=api_key, max_retries=args.retry)

    run_experiment(
        client=client,
        n_repeats=args.n_repeats,
        output_dir=args.output_dir,
        condition_filter=args.conditions,
        model_filter=model_filter,
        problem_filter=args.problems,
        delay=args.delay,
        max_tokens=args.max_tokens,
    )


# ===== Cell 2: 运行实验 =====
if __name__ == "__main__":
    import sys
    if "ipykernel" in sys.modules:
        # Notebook环境
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler()],
        )
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        if not api_key:
            raise RuntimeError("请先设置环境变量 NVIDIA_API_KEY")

        client = NvidiaNIMClient(api_key=api_key, max_retries=10, max_rate_limit_retries=30)
        results = run_experiment(
            client=client,
            n_repeats=3,
            output_dir="/kaggle/working/output",
            delay=5,
            max_tokens=16384,
        )
    else:
        main()

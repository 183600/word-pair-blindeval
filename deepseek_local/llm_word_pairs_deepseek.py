#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek 官方 API 本地实验入口（v2）。

实现复用仓库里的通用 v2 脚本 `notebook_v2/llm_word_pairs_v2.py`，本文件只负责
注入 DeepSeek 官方 API 的默认配置，避免复制一份 1000+ 行代码造成分叉。

用法：
    export DEEPSEEK_API_KEY='sk-...'
    export GITEE_TOKEN='...'
    python3 deepseek_local/llm_word_pairs_deepseek.py

可用环境变量覆盖默认值，例如：
    N_RUNS=3 CONCURRENCY=64 GIT_BRANCH=v2-deepseek-pilot \
        python3 deepseek_local/llm_word_pairs_deepseek.py
"""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "notebook_v2" / "llm_word_pairs_v2.py"


def _set_default(key: str, value: str) -> None:
    os.environ.setdefault(key, value)


def main() -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("缺少 DEEPSEEK_API_KEY（或 OPENAI_API_KEY）：请先 export，不要把密钥写入文件")
    os.environ["OPENAI_API_KEY"] = api_key

    _set_default("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    _set_default("GEN_MODELS", "deepseek-flash,deepseek-v4-pro")
    _set_default("JUDGE_MODELS", "deepseek-flash,deepseek-v4-pro")
    _set_default("N_RUNS", "10")
    _set_default("CONCURRENCY", "2400")
    _set_default("COUNTERBALANCE", "0")
    _set_default("MAX_TOKENS_GEN", "16384")
    _set_default("MAX_TOKENS_CLEAN", "8192")
    _set_default("MAX_TOKENS_JUDGE", "8192")
    _set_default("PER_CALL_TIMEOUT", "600")
    _set_default("MAX_RETRIES", "3")
    _set_default("MODEL_FAILURE_LIMIT", "8")
    _set_default("TIME_BUDGET_MIN", "1440")
    _set_default("GIT_COMMIT_EVERY", "5")
    _set_default("GIT_PUSH_INTERVAL", "20")
    _set_default("GITEE_USER", "qwe12345678")
    _set_default("GIT_REMOTE_URL", "https://gitee.com/qwe12345678/jkdsfn.git")
    _set_default("GIT_BRANCH", "v2-deepseek")
    _set_default("REPO_DIR", str(Path.cwd() / "jkdsfn_deepseek_repo"))

    if not SCRIPT.exists():
        sys.exit(f"找不到通用 v2 脚本：{SCRIPT}")

    # 通用脚本在 __main__ 下会调用 run_main()；这里直接执行同一入口。
    runpy.run_path(str(SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()

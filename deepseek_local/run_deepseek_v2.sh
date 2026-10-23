#!/usr/bin/env bash
# DeepSeek 官方 API 本地实验启动脚本（v2）。
#
# 用法：
#   export DEEPSEEK_API_KEY='sk-...'
#   export GITEE_TOKEN='...'
#   bash deepseek_local/run_deepseek_v2.sh
#
# 可选覆盖：
#   N_RUNS=3 CONCURRENCY=64 GIT_BRANCH=v2-deepseek-pilot bash deepseek_local/run_deepseek_v2.sh
set -euo pipefail

: "${DEEPSEEK_API_KEY:?请先 export DEEPSEEK_API_KEY（DeepSeek 官方 API key）}"
: "${GITEE_TOKEN:?请先 export GITEE_TOKEN（用于把结果推回 Gitee；只读本地可先不推）}"

cd "$(dirname "$0")/.."
exec python3 -u deepseek_local/llm_word_pairs_deepseek.py

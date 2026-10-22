# v2 本地 DeepSeek 官方 API 实验

本目录是 **本地** 运行的 v2 实验结果，使用 DeepSeek 官方 API（`https://api.deepseek.com/v1`），
与 Kaggle 上的 NVIDIA 多模型实验分开保存在分支 `v2-deepseek`。

## 配置

| 项目 | 值 |
|---|---|
| 生成模型 | `deepseek-flash`（DeepSeek-V4.1-Flash）、`deepseek-v4-pro`（DeepSeek-V4-Pro） |
| 评委 | 同上两个模型（各评一次） |
| 任务 | 6 个（与 v1 相同） |
| 条件 | `baseline` vs `word_pairs` |
| 重复 | 每模型 × 条件 × 10 run = 120 条/模型，共 240 条 |
| 清洗 | 每模型 60 条，共 120 条 |
| 盲评 | 2 评委 × 2 生成模型 × 60 对 = 240 对 |
| 并发 | 2400（按用户要求设置） |
| 清洗校验 | 严格 prompt + 正则 + 二次清洗；`residual` 标记 |

## 结果

| 生成模型 | 评委 | 有效比较 | baseline 胜 | cleaned 胜 | tie | cleaned 残留 |
|---|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | `deepseek-flash` | 60 | 54 | 5 | 1 | 0/60 |
| `deepseek-flash` | `deepseek-v4-pro` | 60 | 52 | 8 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-flash` | 60 | 59 | 1 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-v4-pro` | 60 | 59 | 1 | 0 | 0/60 |

- 生成：两个模型各 120 条，0 条 `[ERROR]`。
- 清洗：两个模型各 60 条，0 条 `[ERROR]`，**0 条残留**（v1 的 17/60 残留问题已修复）。
- 盲评：240 对全部有效；baseline 仍显著占优。

## 与 v1 的对比

| 实验 | 生成模型 | 评委 | baseline 胜 | cleaned 胜 | tie | 清洗残留 |
|---|---|---|---:|---:|---:|---:|
| v1 | `moonshotai/kimi-k3` | 同模型 | 49 | 10 | 1 | 17/60 含引用 |
| v2 本地 | `deepseek-flash` | `deepseek-flash` | 54 | 5 | 1 | 0/60 |
| v2 本地 | `deepseek-flash` | `deepseek-v4-pro` | 52 | 8 | 0 | 0/60 |
| v2 本地 | `deepseek-v4-pro` | `deepseek-flash` | 59 | 1 | 0 | 0/60 |
| v2 本地 | `deepseek-v4-pro` | `deepseek-v4-pro` | 59 | 1 | 0 | 0/60 |

v2 在清洗残留为 0 的条件下，baseline 依然大幅胜出；说明 v1 的 baseline 优势不只是
“词对引用被评审当成幻觉”造成的，词对提示 + 清洗后的整体质量确实低于直接回答。

## 目录

```
llm_experiment_results_v2/
├── deepseek-flash/
│   ├── results.jsonl
│   ├── cleaned.jsonl
│   ├── comparison__deepseek-flash.jsonl
│   ├── comparison__deepseek-v4-pro.jsonl
│   ├── task{1..6}_*/{baseline,word_pairs}/run_*.md
│   ├── cleaned/task*/run_*.md
│   ├── comparison/<judge>/task*/run_*.md
│   └── summary__*.json
├── deepseek-v4-pro/...
├── summary.json
└── SUMMARY.md
```

## 说明

- 本分支只包含本地 DeepSeek 结果；Kaggle 的 NVIDIA 多模型结果在 `main` 分支。
- 运行脚本与 v2 Notebook 相同；本实验通过环境变量注入 `OPENAI_API_KEY`/`OPENAI_BASE_URL`，
  仓库中不保存密钥。
- 参数：`N_RUNS=10`、`CONCURRENCY=2400`、`COUNTERBALANCE=0`（每个评委单顺序，A/B 位置由
  确定性 hash 平衡）、`GIT_BRANCH=v2-deepseek`。

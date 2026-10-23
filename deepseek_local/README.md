# DeepSeek 官方 API 本地实验（v2）

本目录是 **DeepSeek 官方 API** 本地实验的代码入口与复现说明。

- 通用实现：`notebook_v2/llm_word_pairs_v2.py`（与 Kaggle 版共用）
- DeepSeek 配置入口：`deepseek_local/llm_word_pairs_deepseek.py`
- 一键启动：`deepseek_local/run_deepseek_v2.sh`
- 依赖：`deepseek_local/requirements.txt`

> 单独做一个入口、而不是复制一份 1000+ 行代码，是为了让 DeepSeek / Kaggle 两套实验
> 共用同一份流水线，避免逻辑分叉。

## 配置

| 项目 | 值 |
|---|---|
| API | `https://api.deepseek.com/v1` |
| 生成模型 | `deepseek-flash`、`deepseek-v4-pro` |
| 评委 | `deepseek-flash`、`deepseek-v4-pro`（各评一次） |
| 任务 | 6 个（函数式语言、提升 LLM 性能、CLI Idea、新理论、人格模型、ML 架构） |
| 条件 | `baseline` vs `word_pairs` |
| 重复 | 2 模型 × 6 任务 × 2 条件 × 10 run = 240 条生成 |
| 清洗 | 每模型 60 条，共 120 条 |
| 盲评 | 2 评委 × 2 生成模型 × 60 对 = 240 对 |
| 并发 | 2400 |
| 位置平衡 | 每个评委单顺序，A/B 位置由确定性 hash 平衡 |
| 断点续跑 | 每 5 条 commit、每 20 条 push；结果分支 `v2-deepseek` |

## 运行

```bash
python3 -m pip install -r deepseek_local/requirements.txt

export DEEPSEEK_API_KEY='sk-...'      # 不要写入仓库
export GITEE_TOKEN='...'              # 用于 push；只跑本地可以改成空并跳过 push

bash deepseek_local/run_deepseek_v2.sh
```

可选覆盖示例：

```bash
N_RUNS=3 CONCURRENCY=64 GIT_BRANCH=v2-deepseek-pilot \
  bash deepseek_local/run_deepseek_v2.sh
```

脚本的工作方式：

1. 从 Gitee `v2-deepseek` 分支 clone 或 pull 到 `REPO_DIR`（默认 `./jkdsfn_deepseek_repo`）；
2. 分析 `llm_experiment_results_v2/` 中的缺口；
3. 补生成 → 补清洗 → 双评委盲评；
4. 每 5 条 commit、每 20 条 push；中断后重跑自动续。

## 结果

完整结果已归档在 `main` 分支的 `llm_experiment_results_v2/`，也保留在 `v2-deepseek` 分支。

汇总：<https://gitee.com/qwe12345678/jkdsfn/blob/main/llm_experiment_results_v2/SUMMARY.md>

| 生成模型 | 评委 | 有效比较 | baseline 胜 | cleaned 胜 | tie | 清洗残留 |
|---|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | `deepseek-flash` | 60 | 54 | 5 | 1 | 0/60 |
| `deepseek-flash` | `deepseek-v4-pro` | 60 | 52 | 8 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-flash` | 60 | 59 | 1 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-v4-pro` | 60 | 59 | 1 | 0 | 0/60 |

- 240 对盲评全部有效；两个模型各 120 条生成、60 条清洗，0 条错误。
- 严格清洗后残留 **0/60/模型**，v1 的 17/60 引用残留问题已消除。
- 二项检验：baseline vs cleaned 的 p 值在 1.9e-11 到 1.1e-16 之间。

## 数据目录

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

## 安全

- 本目录和通用脚本都**不包含** API key 或 Gitee token；必须通过环境变量注入。
- 提交前 `_scan_staged()` 会扫描 `GITEE_TOKEN`、`OPENAI_API_KEY`、`KGAT_`/`ghp_`/`sk-`/
  `PRIVATE KEY`；命中会拒绝提交。
- 旧 key 曾出现在历史中，仍建议在 DeepSeek / Gitee / Kaggle 控制台撤销并轮换。

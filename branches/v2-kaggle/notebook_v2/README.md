# LLM 词对实验 v2（多生成模型 + 双评委）

本目录是 `notebook22d6286ede` 的重跑版本：修复了 Git 持久化、密钥处理、清洗残留、
位置偏差、记录 provenance 等问题，并把实验扩展到 **4 个生成模型 × 2 个评委**。

> 脱敏说明：本目录的 `.ipynb` / `.py` 中 `OPENAI_API_KEY` 和 `GITEE_TOKEN` 默认值为空，
> 必须通过环境变量或 Kaggle Secrets 注入。不要在 Notebook 或脚本里写回密钥。

## 1. 实验设计

| 项目 | 内容 |
|---|---|
| 生成模型 | `stepfun-ai/step-5-preview`、`deepseek-ai/deepseek-v4.1-flash`、`z-ai/glm-5.3`、`z-ai/glm-5.3-flash` |
| 评委 | `deepseek-ai/deepseek-v4.1-flash`、`z-ai/glm-5.3` |
| 任务 | 6 个（函数式语言、提升 LLM 性能、CLI Idea、新理论、人格模型、ML 架构） |
| 条件 | `baseline` vs `word_pairs`（回答前输出 200 组词） |
| 重复 | 每个生成模型 × 条件 × 10 run，共 480 条生成 |
| 清洗 | 每个生成模型 60 条 `word_pairs`，共 240 条 |
| 盲评 | 每个评委对每个生成模型的 60 对 baseline vs cleaned 做一次评审（共 480 对） |
| 位置平衡 | 默认每个评委对每对只评一次，但 A/B 位置由确定性 hash 平衡；设置 `COUNTERBALANCE=1` 可改为每对双顺序 |

盲评 prompt 明确告诉评委：两篇回答都可能引用未展示的“灵感词”，引用本身不扣分；
清洗 prompt 会删除词对编号和“从上面词对中/这些词中”等残留。`cleaned.jsonl` 的
`residual` 字段标记二次清洗后仍残留的条数，分析时可单独剔除。

## 2. 相对 v1 的修复

- **Git identity**：clone 成功后显式 `git config user.name/user.email`；`commit` 失败立即抛错，
  不再出现“commit 全失败但最后打印全部完成”。
- **提交白名单**：只 `git add -A -- llm_experiment_results_v2`，不再把脚本/日志/密钥提交。
- **提交前密钥扫描**：命中 `GITEE_TOKEN`、`OPENAI_API_KEY`、`KGAT_/ghp_/sk-/PRIVATE KEY` 时
  拒绝提交并 `git reset`。
- **token 不落盘**：`http.extraheader` 传递 `Authorization`，remote URL 保持
  `https://gitee.com/qwe12345678/jkdsfn.git`，不把 token 写进 `.git/config`。
- **清洗残留**：严格 prompt + 正则校验 + 二次清洗；`residual` 标记。
- **位置偏差**：评委 A/B 位置用确定性 hash 平衡；可选双顺序。
- **provenance**：每条记录带 `schema_version/run_id/timestamp/model/prompt_version/seed`。
- **断点续跑**：每 5 条 commit、每 20 条 push；全局 11h 时间预算；重跑自动分析缺口。
- **模型熔断**：单模型连续 5 次失败后本次跳过，避免一个坏模型烧完全部时间。
- **DRY_RUN**：`DRY_RUN=1` 不 clone/pull/push，只做缺口分析。

## 3. 运行方式

在 Kaggle 私有 Notebook 中运行（CPU + Internet）：

```bash
# 可选：用 Kaggle Secrets 提供，优先级高于代码默认值
export OPENAI_API_KEY='<your-key>'
export OPENAI_BASE_URL='https://integrate.api.nvidia.com/v1'
export GITEE_TOKEN='<gitee-token>'
export GITEE_USER='qwe12345678'
export GIT_BRANCH='main'
# 可选
export N_RUNS=10
export CONCURRENCY=10
export COUNTERBALANCE=0
export TIME_BUDGET_MIN=660
```

直接执行 `run_main()`；如果会话超时，重新运行同一个 Notebook 即可从 Gitee 上的
`llm_experiment_results_v2/` 续跑。

## 4. 结果目录

```
llm_experiment_results_v2/
├── <model>/
│   ├── results.jsonl
│   ├── cleaned.jsonl
│   ├── comparison__<judge>.jsonl
│   ├── task{1..6}_*/{baseline,word_pairs}/run_*.md
│   ├── cleaned/task*/
│   ├── comparison/<judge>/task*/
│   └── summary__<judge>.json
├── summary.json
└── SUMMARY.md
```

## 5. 注意事项

- 四个模型都是推理型，单次调用可能 200–900s；默认并发 10，时间预算 11h。
  如果某个模型被熔断，重跑时会再次尝试。
- `deepseek-ai/deepseek-v4.1-flash` 既做生成也做评委；如果该模型不可用，对应结果会缺失，
  `SUMMARY.md` 会显示有效比较数。
- 旧版实验已归档在 `branches/main/notebook/`；本目录是新实验，二者互不覆盖。
- 旧密钥已在历史中暴露，运行前请撤销/轮换；本次运行使用的凭据只存在于 Kaggle 私有
  Notebook，不在本仓库。

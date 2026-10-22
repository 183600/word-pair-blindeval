# OpenCode 免费模型实验重跑（opencode-experiment-rerun 分支）

用 **OpenCode 每一个免费模型**，重跑仓库「之前的实验」（Kaggle
notebooka6f1f91666 / vfdjk.py / jvdfka.py 的三阶段流水线），**每个模型各跑
一遍、并发=1**，在 Kaggle 上运行，结果增量推送回本分支。

## 实验内容（与原实验完全一致）

| 阶段 | 内容 | 每模型调用量 |
|---|---|---|
| 0 生成 | 6 任务 × 2 条件(baseline / word_pairs) × 10 次 | 120 |
| 1 清洗 | word_pairs 输出去掉开头 200 组词对 | 60 |
| 2 盲评 | 清洗后 vs baseline，随机交换 A/B，5 维打分 | 60 |

任务表、PREFIX 指令、清洗/盲评 Prompt、温度(生成0.6/后处理0.3) 均与原实验
逐字一致；Notebook 启动时还会从 Kaggle API 拉取之前的实验代码提取定义并校验。

## 与原实验的必要差异（OpenCode 免费层强制）

- 传输层：`stream=true` + bash/read 等真实工具定义 + `x-opencode-*` 客户端头
  （否则 403 FreeTierError，客户端校验逆向自官方 CLI）
- `tool_choice="none"` + 直答系统提示：抑制模型的工具调用倾向
- `max_tokens=16000`（推理型模型先烧推理 token；glm-5.3-flash-free 用 32000，
  任何模型遇"推理烧光导致空正文"自动升档重试一次）

## 目录结构

```
llm_experiment_results_opencode/
  PROGRESS.md                  # 进度总览（每模型三阶段完成度）
  <model>/
    results.jsonl              # 生成记录（追加式，最新有效记录为准）
    cleaned.jsonl              # 清洗记录
    comparison.jsonl           # 盲评记录
    task{id}_{name}/{cond}/run_XX.md
    cleaned/task{id}_{name}/run_XX.md
    comparison/task{id}_{name}/run_XX.md
    _status.json               # gave_up 等状态标记
opencode_experiment_rerun.py   # 本脚本（可在任意环境运行）
opencode_experiment_rerun.ipynb # Kaggle Notebook（内嵌同一脚本）
```

## 断点续跑

- 每完成一条记录：追加 jsonl + 写 markdown + git commit + **push**
- 中断后重新运行（Kaggle 上重新 Save & Run All 即可）：clone/pull 分支 →
  逐模型分析缺口 → 跳过已完成记录 → 继续补缺
- 「已完成」= 该键最新一条记录有效；失败记录为 `[ERROR]`，下次自动重做
- 连续 5 条终局失败（如协议不支持）→ 该模型标记 `gave_up`，以后跳过
- 预算：单条重试 75min / 每模型每会话 240min / 会话 600min（到点干净收尾）
- 熔断：单模型连续 5 条彻底失败 → 跳到下一个模型

## 运行

Kaggle：直接 Save & Run All `opencode_experiment_rerun.ipynb`（无需配置）。
本地/其他环境：

```bash
python3 opencode_experiment_rerun.py            # 正式跑（写 Gitee）
DRY_RUN=1 python3 opencode_experiment_rerun.py  # 只分析缺口
```

主要环境变量见脚本头部说明（OPENCODE_MODELS / N_RUNS / TIME_BUDGET_MIN 等）。

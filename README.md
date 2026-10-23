# LLM 词对提示实验 v2（DeepSeek 官方 API）

本仓库当前以 **v2 DeepSeek 官方 API 实验** 为主线，保存代码、逐条生成/清洗/盲评结果与论文。
实验覆盖 2 个生成模型 × 6 个开放式任务 × 2 个条件（`baseline` / `word_pairs`）× 10 次重复，
共 240 条生成；每个模型 60 条清洗、2 个评委各评 60 对，共 240 对盲评。

> **历史版本已归档**：v1 Kaggle 实验（`notebook22d6286ede`）的代码、120 条生成、60 条清洗、
> 60 对盲评已移到 [`branches/main-20261023/`](branches/main-20261023/)；
> v2 Kaggle 分支快照在 [`branches/v2-kaggle/`](branches/v2-kaggle/)。
> 更早的 master、opencode 分支归档见 [`branches/README.md`](branches/README.md)。

## 快速入口

| 内容 | 路径 |
|---|---|
| DeepSeek 官方 API 本地运行入口 | [`deepseek_local/`](deepseek_local/) |
| 通用流水线（Kaggle / DeepSeek 共用） | [`notebook_v2/`](notebook_v2/) |
| v2 结果、逐条数据与汇总 | [`llm_experiment_results_v2/`](llm_experiment_results_v2/) |
| 论文、LaTeX 源码与复算材料 | [`paper/`](paper/) |
| 分支与历史版本归档 | [`branches/`](branches/) |

## 1. 实验结果

| 生成模型 | 评委 | 有效比较 | baseline 胜 | cleaned 胜 | tie | cleaned 残留 |
|---|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | `deepseek-flash` | 60 | 54 | 5 | 1 | 0/60 |
| `deepseek-flash` | `deepseek-v4-pro` | 60 | 52 | 8 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-flash` | 60 | 59 | 1 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-v4-pro` | 60 | 59 | 1 | 0 | 0/60 |

- 240 对盲评全部有效；baseline 合计胜 **224/240（93.3%）**，cleaned 胜 15，平 1。
- 两个模型各 120 条生成、60 条清洗，0 条 `[ERROR]`；严格清洗后残留 **0/60/模型**。
- v1 的“词对引用被评委当成幻觉”解释不成立：在清洗残留为 0 的条件下，baseline 仍大幅领先。

完整汇总见 [`llm_experiment_results_v2/SUMMARY.md`](llm_experiment_results_v2/SUMMARY.md)。

## 2. 实验配置

| 项目 | 内容 |
|---|---|
| API | `https://api.deepseek.com/v1` |
| 生成模型 | `deepseek-flash`（DeepSeek-V4.1-Flash）、`deepseek-v4-pro`（DeepSeek-V4-Pro） |
| 评委 | 同上两个模型（各评一次） |
| 任务 | 6 个（函数式语言、提升 LLM 性能、CLI Idea、新理论、人格模型、ML 架构） |
| 条件 | `baseline`（直接回答）vs `word_pairs`（回答前输出 200 组词） |
| 重复 | 2 模型 × 6 任务 × 2 条件 × 10 run = 240 条生成 |
| 清洗 | 每模型 60 条，共 120 条 |
| 盲评 | 2 评委 × 2 生成模型 × 60 对 = 240 对 |
| 并发 | 2400（按实验要求设置） |
| 位置平衡 | 每个评委单顺序，A/B 位置由确定性 hash 平衡 |

## 3. 目录结构

```
.
├── deepseek_local/                 # DeepSeek 官方 API 入口、依赖、启动脚本
├── notebook_v2/                    # 通用生成/清洗/盲评流水线（Kaggle 与 DeepSeek 共用）
├── llm_experiment_results_v2/      # 240 条生成、120 条清洗、240 对盲评及汇总
├── paper/                          # 论文 PDF/TeX、复算脚本、图表与中间结果
│   ├── latex-src/                  # 合并自 v2-deepseek 的 LaTeX 源码
│   └── pdf/                        # 对应的论文 PDF
├── branches/                       # 历史版本与分支快照归档
│   ├── main-20261023/              # 从 main 移出的 v1 Kaggle 内容
│   ├── v2-kaggle/                  # v2-kaggle 分支完整快照
│   ├── main/                       # 2026-10-22 的 main 完整快照
│   ├── master/                     # master 分支快照
│   └── opencode-*-rerun/           # opencode 分支快照
├── README.md
└── SECURITY.md
```

## 4. 复现 DeepSeek 实验

```bash
python3 -m pip install -r deepseek_local/requirements.txt

export DEEPSEEK_API_KEY='sk-...'      # 不要写入仓库
export GITEE_TOKEN='...'              # 运行结束推送结果时需要

bash deepseek_local/run_deepseek_v2.sh
```

可选覆盖：

```bash
N_RUNS=3 CONCURRENCY=64 GIT_BRANCH=v2-deepseek-pilot \
  bash deepseek_local/run_deepseek_v2.sh
```

脚本会从 Gitee 的 `v2-deepseek` 分支 clone/pull 到 `REPO_DIR`，分析
`llm_experiment_results_v2/` 的缺口，然后补生成、补清洗、双评委盲评；每 5 条 commit、
每 20 条 push，中断后重跑可续。默认结果分支是 `v2-deepseek`，可用 `GIT_BRANCH` 覆盖。

## 5. 论文

`paper/` 收录两套材料：

- [`paper/paper.pdf`](paper/paper.pdf)（15 页）与 [`paper/paper.tex`](paper/paper.tex)：针对 240 对
  盲评的独立复算，含胜负、五维评分、长度分层、聚类 bootstrap、回归与 v1 跨代复现；
  复算脚本在 [`paper/scripts/`](paper/scripts/)，中间结果在 [`paper/out/`](paper/out/)。
- [`paper/latex-src/`](paper/latex-src/) 与 `paper/pdf/` 下的中文 PDF：合并自 `v2-deepseek`
  分支的 LaTeX 稿与编译产物。

论文的核心结论：直接回答胜 224/240（93.3%）；词对条件主要提升原创性（+0.31），
但在可操作性（−2.32）、具体性（−2.08）、逻辑性（−1.54）和整体质量（−1.72）上更低；
长度是主要通道，控制长度后条件效应从 −1.72 收窄到 −0.82。

## 6. 安全

- 仓库当前文件和可达历史中不包含 API Key 或 Gitee Token；运行前通过环境变量或
  Kaggle Secrets 注入，不要写回代码或 remote URL。
- 旧凭据曾随公开仓库暴露，请已在 Gitee / DeepSeek / NVIDIA / Kaggle 控制台撤销并轮换；
  不要继续使用旧密钥。
- 提交前请确认没有把 `.env`、token、`kaggle.json` 等文件加入暂存区。更多说明见
  [`SECURITY.md`](SECURITY.md)。

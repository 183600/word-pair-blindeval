# LLM 词对提示实验（Kaggle notebook22d6286ede 归档）

本仓库归档 Kaggle Notebook **`notebook22d6286ede`** 的代码、运行日志、LLM 生成内容和盲评实验结果。
原 Notebook 地址：<https://www.kaggle.com/code/wenjiazhong82355/notebook22d6286ede>

## 1. 实验设计

| 项目 | 内容 |
|---|---|
| 任务 | 6 个开放式生成任务（函数式编程语言、提升 LLM 性能、CLI 工具 Idea、新理论、人格模型、ML 架构） |
| 条件 | `baseline`（直接回答）vs `word_pairs`（回答前先输出 200 组词对） |
| 重复 | 每个任务 × 条件 × 10 次，共 **120** 条生成 |
| 后处理 | 对 `word_pairs` 输出做清洗（删除开头词对），期望 60 条 |
| 评价 | baseline vs cleaned 的 A/B 盲评，A/B 随机交换，期望 60 对 |
| 模型 | `moonshotai/kimi-k3`，NVIDIA `integrate.api.nvidia.com` |
| Notebook 最后运行 | 2026-10-19，版本 1，CPU，联网 |

Notebook 的运行日志见 [`notebook/notebook22d6286ede_run.log`](notebook/notebook22d6286ede_run.log)。
日志末尾显示三个阶段均补齐（生成缺 0、清洗缺 0、盲评缺 0），但最后的自动 `git commit` 因容器内缺少
Git 作者信息而失败（`Author identity unknown`），所以完整结果当时没有自动推送；本仓库这次提交即为该次运行的归档。

## 2. 实验结果

### 2.1 数据完整性

| 文件 | 行数 | 有效记录 | 说明 |
|---|---:|---:|---|
| `results.jsonl` | 120 | 120 | 6 任务 × 2 条件 × 10 run；无 `[ERROR]` 记录 |
| `cleaned.jsonl` | 76 | 60 | 包含 16 行失败重试记录；按 `(task_id, run)` 取最新有效记录后为 60 |
| `comparison.jsonl` | 68 | 60 | 包含 8 行解析失败/空回复重试；有效盲评为 60 对 |

### 2.2 盲评胜负

**总计：baseline 胜 49，cleaned word_pairs 胜 10，平 1（共 60 对）。**

| 任务 | baseline 胜 | word_pairs 胜 | 平 |
|---|---:|---:|---:|
| 1 函数式编程语言 | 9 | 1 | 0 |
| 2 提升 LLM 性能 | 9 | 1 | 0 |
| 3 CLI 工具 Idea | 8 | 2 | 0 |
| 4 新理论 | 8 | 2 | 0 |
| 5 人格模型 | 5 | 4 | 1 |
| 6 ML 架构 | 10 | 0 | 0 |

### 2.3 平均分（1–10）

| 维度 | baseline | cleaned word_pairs |
|---|---:|---:|
| logic（逻辑性与结构） | 8.92 | 7.78 |
| concreteness（具体性） | 8.48 | 7.28 |
| actionability（可操作性） | 8.23 | 6.58 |
| originality（原创性） | 7.15 | 8.25 |
| overall（整体质量） | 8.52 | 7.48 |

结论：词对提示主要提升了**原创性**，但在逻辑性、具体性、可操作性和整体质量上均低于直接回答；
在 6 个任务中 baseline 胜出 49/60。

## 3. 目录结构

```
.
├── results.jsonl                 # 120 条生成结果（增量追加，读取时按键取最新有效）
├── cleaned.jsonl                 # 清洗结果（增量追加）
├── comparison.jsonl              # 盲评结果（增量追加）
├── task1_函数式编程语言/          # 每个任务下分 baseline/ 与 word_pairs/
│   ├── baseline/run_01.md … run_10.md
│   └── word_pairs/run_01.md … run_10.md
├── cleaned/task*/run_*.md        # 清洗后的逐条 markdown
├── comparison/task*/run_*.md     # 盲评的逐条 markdown（含 A/B 原文、评分、理由）
├── jvdfka.py                     # 生成脚本
├── vfdjk.py                      # 补数 / 清洗 / 盲评脚本
├── notebook/
│   ├── notebook22d6286ede.ipynb  # 从 Kaggle 导出的 notebook（已脱敏）
│   ├── notebook22d6286ede.py     # notebook 代码的纯 Python 导出（已脱敏）
│   ├── notebook22d6286ede_run.log# 本次 Kaggle 运行日志
│   ├── provenance.json           # 来源、版本、运行环境、哈希
│   └── README.md
├── README.md
├── SECURITY.md
└── .gitignore
```

## 4. 密钥与安全

- 原始 Notebook 中硬编码的 **Gitee 访问令牌**和 **NVIDIA API Key** 已从导出的 `.ipynb`、`.py` 以及
  `jvdfka.py`、`vfdjk.py` 中移除；仓库当前文件与提交历史中不再包含这些密钥。
- 历史中的密钥已通过重写 Git 历史并强制推送清除（2026-10-22）。由于这些密钥此前曾出现在公开仓库中，
  **仍应立即在 Gitee / NVIDIA 控制台撤销并轮换**，不要继续使用旧密钥。
- 运行前请通过环境变量或 Kaggle Secrets 提供凭据，不要写回代码：

  ```bash
  export OPENAI_API_KEY='<your-key>'
  export OPENAI_BASE_URL='https://integrate.api.nvidia.com/v1'
  export LLM_MODEL='moonshotai/kimi-k3'
  # 需要自动推送时再设置（不要把带令牌的 URL 写入仓库）
  export GIT_REMOTE_URL='https://gitee.com/qwe12345678/jkdsfn.git'
  ```

- 本地推送请使用 Git credential helper、SSH key 或临时 `http.extraheader`，不要把令牌拼进
  remote URL 后提交。更多说明见 [`SECURITY.md`](SECURITY.md)。

## 5. 复现

```bash
python3 -m pip install openai
export OPENAI_API_KEY='<your-key>'
export OPENAI_BASE_URL='https://integrate.api.nvidia.com/v1'
export LLM_MODEL='moonshotai/kimi-k3'
export SKIP_SYNC=1          # 使用仓库内已有数据，避免从 Gitee 重新 clone
export DRY_RUN=1            # 先只做缺失分析，不调用 LLM、不写文件、不推送
python3 vfdjk.py
```

去掉 `DRY_RUN=1` 后才会真正调用模型补齐缺失项。脚本按 `(task_id, condition, run)` /
`(task_id, run)` 取最新有效记录，支持断点续跑。

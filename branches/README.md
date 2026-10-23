# 分支归档

本目录保存 main 的历史快照，以及 main 以外分支的文件快照。历史版本原样归档在这里；
即使删除远程分支，也不会丢失文件内容。当前 main 以 v2 DeepSeek 实验为主线。

## 归档清单

| 子目录 | 来源 | 归档所用 commit | 提交时间 | 文件数 | 目录大小 |
|---|---|---|---:|---:|---:|
| `main-20261023/` | main 的 v1 Kaggle 内容 | `41006f8` docs(paper): add independent re-analysis of the 240-pair blind evaluation | 2026-10-23 18:35:03 +0800 | 251 | 4.0 MB |
| `v2-kaggle/` | `v2-kaggle` 分支 | `ddc865e` v2: gen stepfun-ai/step-5-preview t2 baseline r5 [25] | 2026-10-22 17:34:11 +0000 | 378 | 4.6 MB |
| `main/` | `main`（2026-10-22 快照） | `64aa931` docs: 说明全历史 bundle 单独保存、未随仓库提交 | 2026-10-22 20:18:00 +0800 | 253 | 4.0 MB |
| `master/` | `master` | `432ea39` vfnnadjk | 2026-06-28 12:24:48 +0800 | 306 | 25 MB |
| `opencode-free-rerun/` | `opencode-free-rerun` | `da107a6` opencode-free: 运行结束（本次完成 11 个） | 2026-10-17 11:15:58 +0000 | 242 | 3.3 MB |
| `opencode-experiment-rerun/` | `opencode-experiment-rerun` | `319a33a` run end: 本次会话结束 | 2026-10-17 15:24:06 +0000 | 367 | 5.2 MB |

## 2026-10-23 追加归档

- `main-20261023/` 是 **从 main 移出的 v1 Kaggle 内容**，包含
  `notebook22d6286ede` 的代码、120 条生成、60 条清洗、60 对盲评、任务目录和
  `jvdfka.py` / `vfdjk.py`；另附当时 main 的 `README.md` 快照。共 250 个原文件 + 1 个
  README 快照。
- `v2-kaggle/` 是 **`v2-kaggle` 分支的完整目录树快照**（截至 `ddc865e`），包含该分支的
  Kaggle/NVIDIA v2 代码、stepfun 结果和当时的分支归档。为避免递归，快照不包含该分支自己的
  `branches/` 子目录。
- `v2-deepseek` 分支已合并进 main（其 LaTeX 论文源码与 PDF 现位于
  `paper/latex-src/` 和 `paper/pdf/`），因此不再单独建立 `v2-deepseek/` 归档目录；
  合并提交保留在 main 历史中。
- 当前 main 只保留 v2 DeepSeek 主线内容：`deepseek_local/`、`notebook_v2/`、
  `llm_experiment_results_v2/`、`paper/`，以及本归档目录。

## 与「2026-10-22 归档」的关系

- `main/` 是 **2026-10-22 当天 main 的完整文件快照**（截至 `64aa931`），包含当天的两个功能提交：
  - `5552ee6` feat: 归档 notebook22d6286ede 的代码、LLM 生成内容与实验结果
  - `44f9245` docs: 说明 Gitee 旧 commit 缓存风险与密钥轮换要求
- 为避免无限递归，`main/` 快照**不包含 `branches/` 目录本身**；`branches/main/README.md` 等
  文件就是当天 main 顶层的原样副本。
- `master/`、`opencode-*` 的归档节点早于 2026-10-22，保留的是各自分支当时的完整目录树。
- `opencode-*` 两个分支本来就是**纯新增**：相对共同基点 `fdf97ba`（2026-09-30）分别只增加了
  17 个和 142 个文件，没有修改或删除任何既有文件。它们在归档时仍保留完整目录树，
  方便单独检出使用。

## 分支说明

- **`main`**：当前 v2 DeepSeek 实验主线（`deepseek_local/` + `llm_experiment_results_v2/`
  + `notebook_v2/` + `paper/`），v1 Kaggle 内容和 v2 Kaggle 快照已移入本目录。
- **`v2-deepseek`**：DeepSeek 官方 API 实验分支；已合并进 main，保留其历史与论文源码。
- **`v2-kaggle`**：Kaggle/NVIDIA v2 实验分支；完整文件快照已归档到 `v2-kaggle/`。
- **`opencode-free-rerun`**：新增 `opencode_free_rerun.ipynb`、`opencode_free_rerun.py`、
  `opencode_free_results/`、`opencode_free_results_README.md`，共 15 个提交。
- **`opencode-experiment-rerun`**：新增 `opencode_experiment_rerun.ipynb`、
  `opencode_experiment_rerun.py`、`llm_experiment_results_opencode/`、
  `llm_experiment_results_opencode_README.md`，共 142 个提交。
- **`master`**：与 main **无共同历史**的另一个项目（`vfnadjk.py` + `output/` 下的
  2026-06-27 评测输出），历史只有 2 个提交（`Initial commit`、`vfnnadjk`）。

## 如何取用

```bash
# v1 Kaggle 的原始生成/清洗/盲评
ls branches/main-20261023/

# v2-kaggle 分支当时的完整快照
ls branches/v2-kaggle/

# 2026-10-22 的 main 快照
ls branches/main/notebook/

# 某个 opencode 分支当时的文件
ls branches/opencode-free-rerun/opencode_free_results/
```

完整历史备份未提交到本仓库，单独保存在本地 `all-branches-backup-20261022.bundle`
（8.3 MB，含当时 4 个分支的全部提交；由 `git bundle create <file> --all` 生成，
`git bundle verify` 校验通过）。2026-10-23 重组前的 refs 另存为
`jkdsfn_pre_reorg_20261023.bundle`。

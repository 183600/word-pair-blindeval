# 分支归档（2026-10-22）

本目录保存 **main 今日快照**以及 **main 以外所有分支**的文件快照。仓库自 2026-10-22 起只保留 `main` 分支，
其余分支的文件内容原样归档在这里，删除远程分支不会丢失任何文件。

## 归档清单

| 子目录 | 原分支 | 归档所用 commit | 提交时间 | 文件数 | 目录大小 |
|---|---|---|---:|---:|---:|
| `main/` | `main` | `64aa931` docs: 说明全历史 bundle 单独保存、未随仓库提交 | 2026-10-22 20:18:00 +0800 | 253 | 4.0 MB |
| `master/` | `master` | `432ea39` vfnnadjk | 2026-06-28 12:24:48 +0800 | 306 | 25 MB |
| `opencode-free-rerun/` | `opencode-free-rerun` | `da107a6` opencode-free: 运行结束（本次完成 11 个） | 2026-10-17 11:15:58 +0000 | 242 | 3.3 MB |
| `opencode-experiment-rerun/` | `opencode-experiment-rerun` | `319a33a` run end: 本次会话结束 | 2026-10-17 15:24:06 +0000 | 367 | 5.2 MB |

## 与「今天的新提交」的关系

- `main/` 是 **2026-10-22 当天 main 的完整文件快照**（截至 `64aa931`），包含当天的两个功能提交：
  - `5552ee6` feat: 归档 notebook22d6286ede 的代码、LLM 生成内容与实验结果
  - `44f9245` docs: 说明 Gitee 旧 commit 缓存风险与密钥轮换要求
- 为避免无限递归，`main/` 快照**不包含 `branches/` 目录本身**；`branches/main/README.md` 等
  文件就是当天 main 顶层的原样副本。
- `master/`、`opencode-*` 的归档节点仍早于 2026-10-22，保留的是各自分支当时的完整目录树。
- `opencode-*` 两个分支本来就是**纯新增**：相对共同基点 `fdf97ba`（2026-09-30）分别只增加了
  17 个和 142 个文件，没有修改或删除任何既有文件。它们在归档时仍保留完整目录树，
  方便单独检出使用。

## 分支说明

- **`main`**：当天实验归档（`notebook22d6286ede` 的代码、120 条生成、60 条清洗、60 对盲评），
  快照排除 `branches/` 以避免递归；完整历史仍由 main 本身保留。
- **`opencode-free-rerun`**：新增 `opencode_free_rerun.ipynb`、`opencode_free_rerun.py`、
  `opencode_free_results/`、`opencode_free_results_README.md`，共 15 个提交。
- **`opencode-experiment-rerun`**：新增 `opencode_experiment_rerun.ipynb`、
  `opencode_experiment_rerun.py`、`llm_experiment_results_opencode/`、
  `llm_experiment_results_opencode_README.md`，共 142 个提交。
- **`master`**：与 main **无共同历史**的另一个项目（`vfnadjk.py` + `output/` 下的
  2026-06-27 评测输出），历史只有 2 个提交（`Initial commit`、`vfnnadjk`）。

## 如何取用

```bash
# 直接看 main 当天的快照
ls branches/main/notebook/

# 直接看某个分支当时的文件
ls branches/opencode-free-rerun/opencode_free_results/

# 若需要该分支的完整 Git 历史（bundle 不随仓库提交）
git clone all-branches-backup-20261022.bundle repo-all
```

完整历史备份未提交到本仓库，单独保存在本地 `all-branches-backup-20261022.bundle`
（8.3 MB，含 4 个分支的全部提交；由 `git bundle create <file> --all` 生成，
`git bundle verify` 校验通过）。它比本目录更完整：保留了每个提交的历史、提交信息和删除前的分支指向。

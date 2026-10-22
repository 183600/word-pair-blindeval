# 分支归档（2026-10-22）

本目录保存 **main 以外所有分支**的文件快照。仓库自 2026-10-22 起只保留 `main` 分支，
其余分支的文件内容原样归档在这里，删除远程分支不会丢失任何文件。

## 归档清单

| 子目录 | 原分支 | 归档所用 commit | 提交时间 | 文件数 | 目录大小 |
|---|---|---|---:|---:|---:|
| `master/` | `master` | `432ea39` vfnnadjk | 2026-06-28 12:24:48 +0800 | 306 | 25 MB |
| `opencode-free-rerun/` | `opencode-free-rerun` | `da107a6` opencode-free: 运行结束（本次完成 11 个） | 2026-10-17 11:15:58 +0000 | 242 | 3.3 MB |
| `opencode-experiment-rerun/` | `opencode-experiment-rerun` | `319a33a` run end: 本次会话结束 | 2026-10-17 15:24:06 +0000 | 367 | 5.2 MB |

## 与「今天的新提交」的关系

- 归档节点均**早于** 2026-10-22，因此本目录**不含** main 当天新增的两个提交：
  - `5552ee6` feat: 归档 notebook22d6286ede 的代码、LLM 生成内容与实验结果
  - `44f9245` docs: 说明 Gitee 旧 commit 缓存风险与密钥轮换要求
- 这两个提交的内容本来就在 main 上（`notebook/`、`README.md`、`SECURITY.md`、`.gitignore`
  以及 `cleaned*`、`comparison*` 的更新），不需要也不应该在归档里重复一份。
- `opencode-*` 两个分支本来就是**纯新增**：相对共同基点 `fdf97ba`（2026-09-30）分别只增加了
  17 个和 142 个文件，没有修改或删除任何既有文件。它们在归档时仍保留完整目录树，
  方便单独检出使用。

## 分支说明

- **`opencode-free-rerun`**：新增 `opencode_free_rerun.ipynb`、`opencode_free_rerun.py`、
  `opencode_free_results/`、`opencode_free_results_README.md`，共 15 个提交。
- **`opencode-experiment-rerun`**：新增 `opencode_experiment_rerun.ipynb`、
  `opencode_experiment_rerun.py`、`llm_experiment_results_opencode/`、
  `llm_experiment_results_opencode_README.md`，共 142 个提交。
- **`master`**：与 main **无共同历史**的另一个项目（`vfnadjk.py` + `output/` 下的
  2026-06-27 评测输出），历史只有 2 个提交（`Initial commit`、`vfnnadjk`）。

## 如何取用

```bash
# 直接看某个分支当时的文件
ls branches/opencode-free-rerun/opencode_free_results/

# 若需要该分支的完整 Git 历史（bundle 不随仓库提交）
git clone all-branches-backup-20261022.bundle repo-all
```

完整历史备份：`all-branches-backup-20261022.bundle`（8.3 MB，含 4 个分支全部提交，
由 `git bundle create <file> --all` 生成，`git bundle verify` 校验通过）。

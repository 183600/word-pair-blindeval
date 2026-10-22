# opencode-free-rerun 分支

在 Kaggle 上串行重跑 OpenCode 全部 11 个免费模型（每个模型各跑一遍，并发=1），
结果增量推回本分支 `opencode_free_results/` 目录。

## 文件说明

| 文件 | 说明 |
|---|---|
| `opencode_free_rerun.py` | 主脚本（自包含，可本地直接运行） |
| `opencode_free_rerun.ipynb` | Kaggle Notebook 版（单 cell，内容与 .py 完全一致） |
| `opencode_free_results/results.jsonl` | 每个模型一条最终记录（追加式，不覆盖） |
| `opencode_free_results/raw/` | 每次尝试的原始返回（SSE 头部等，便于排查） |
| `opencode_free_results/summary_*.txt` | 每次运行结束的汇总表 |

## 断点续跑机制

- 每完成一个模型 → 追加 `results.jsonl` + 写 `raw/` → `git commit` + `push` 到本分支
- 中途停止（会话超时 / 手动停止 / 熔断 / 时间预算耗尽）后重新运行：
  自动 `clone`/`pull` 本分支 → 读 `results.jsonl` → 跳过已完成模型 → 继续跑
- 「已完成」= 最新记录 status 为 `ok` / `error_definitive`（区域限制、协议不支持等终局错误）
  或 `gave_up`（重试预算耗尽）。瞬时错误（429 / 上游不可用 / 超时）重跑时会自动重试
- 想重试 gave_up 的模型：设置环境变量 `RETRY_GAVE_UP=1` 再跑

## 运行方式（Kaggle）

1. 打开 Kaggle Notebook `opencode-free-rerun`（已通过 API 推送，Internet 已开启）
2. Save & Run All 即可；跑不完随时停，再次运行自动续跑

## 运行方式（本地）

```bash
python opencode_free_rerun.py            # 默认串行 11 个模型
DRY_RUN=1 python opencode_free_rerun.py  # 只看进度分析，不调用不写入
```

## 模型清单（按可靠度排序）

space-bunny-free, big-pickle, test, deepseek-v4.1-flash-free,
longcat-2.5-preview-free, mimo-v2.6-flash-free, nemotron-3.5-super-vl-free,
glm-5.3-flash-free（偶发 429，需重试）,
nemotron-3.5-lightning-free（返回 200 但 keep-alive 空转约 5 分钟）,
beam-free（区域限制）, jev-1.13-free（协议不支持）

> 注：beam-free 与 jev-1.13-free 按设计仍会各跑一遍并把终局错误记录在案。

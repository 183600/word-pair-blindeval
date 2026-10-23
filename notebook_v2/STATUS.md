# v2 运行状态（2026-10-22）

## 已完成

- `branches/main/`：main 当天快照已归档（排除 `branches/` 以避免递归）。
- `notebook_v2/llm_word_pairs_v2.ipynb` / `.py`：v2 代码已推送（脱敏版，非流式请求）。
- 代码修复：Git identity、提交白名单、密钥扫描、`http.extraheader`、清洗残留校验、
  双评委、确定性 A/B 位置平衡、provenance、时间预算、断点续跑、模型熔断。

## 第二次 Kaggle 运行（已停止）

- 第一次运行产生的是 **错误记录**：`stepfun` 全部为 `[ERROR] model disabled`，
  `deepseek-v4.1-flash` 仅 2 条有效（其余 429/空）。
- 将并发从 10 降到 3 后重启：`stepfun` 持续返回 `504 InternalServerError`，
  `deepseek` 仍有 429；没有产生新的有效 NVIDIA 结果。
- 为避免继续空烧 Kaggle 配额，已再次停止并删除 Kernel。
- 结论：当前 NVIDIA key/端点不适合这次 4 模型 × 10 run 的全量实验；Notebook
  已支持多会话续跑，端点恢复后重新 push/运行即可从 `main` 的 `llm_experiment_results_v2/`
  继续（错误记录会被 latest-valid 逻辑忽略）。
- **重试注意**：本地 DeepSeek 结果已经在 `main` 的 `llm_experiment_results_v2/` 下；
  NVIDIA 重试请使用独立分支（如 `v2-kaggle`）或独立结果目录，避免覆盖本地
  `SUMMARY.md`/`summary.json`。

## 第三次 Kaggle 运行（并发 1，已停止）

- 分支：`v2-kaggle`（从 `707aa33` 创建，不含本地 DeepSeek 结果）
- Kernel 重新创建，并发设为 **1**，480 个生成任务启动。
- `stepfun-ai/step-5-preview` 第一条任务 3 次重试全部 **504 InternalServerError**，
  随后被熔断；剩余 119 条写成 `[ERROR] model disabled`，`v2-kaggle` 上共 120 条错误记录。
- 转至 `deepseek-ai/deepseek-v4.1-flash` 后同样连续 504；`glm` 尚未开始。
- 结论：**并发 1 也不能绕过 NVIDIA NIM 的 504**；已再次停止并删除 Kernel。
- `v2-kaggle` 分支的失败尝试记录已完整归档到 `branches/v2-kaggle/`，**没有有效 NVIDIA 结果**，
  未合并到 `main`；该远程分支已删除。

## 本地 DeepSeek 官方 API 实验（已完成）

- 分支：`main`（原 `v2-deepseek` 已合并，远程分支已删除）
- 模型：`deepseek-flash`、`deepseek-v4-pro`（生成 + 评委）
- 规模：2 模型 × 6 任务 × 2 条件 × 10 run = 240 条生成；120 条清洗；240 对盲评
- 并发：2400（按用户要求）
- 结果：240 对全部有效，清洗残留 **0/60/模型**；baseline 胜率 52–59/60。
- 详见 `main` 分支的 `llm_experiment_results_v2/SUMMARY.md` 和 `README.md`。

## 首次 Kaggle 运行（已停止）

- Kernel：`wenjiazhong82355/llm-word-pairs-v2`（已删除，避免空烧配额）。
- 启动正常：clone 成功、Git identity 正常、480 个生成任务已创建。
- 失败现象：`stepfun-ai/step-5-preview` 的流式请求在约 10 分钟后返回
  `EmptyResponse(finish=None)`；模型在流式模式下持续输出 `reasoning_content`，
  迟迟不产生最终 `content`。

## 本地 API 诊断

| 模型 | 短 prompt（Say OK） | 完整任务 prompt |
|---|---|---|
| `stepfun-ai/step-5-preview` | 约 100–205s，能返回 | 流式 550s+ 仍在 reasoning；非流式 10+ 分钟未返回 |
| `z-ai/glm-5.3` | 约 147s，能返回 | 未完成（reasoning 很长） |
| `z-ai/glm-5.3-flash` | 约 205–235s，能返回 | 未完成（reasoning 很长） |
| `deepseek-ai/deepseek-v4.1-flash` | 600s 超时 | 不可用/超时 |

- `thinking.type=disabled`、`chat_template_kwargs.enable_thinking=false`、`thinking=false`
  都被端点忽略，模型仍先输出大量 reasoning。
- 短 prompt 的非流式请求可以 6s 返回；说明端点本身可用，瓶颈是**完整任务的 reasoning 时长**。

## 结论

用当前 NVIDIA key/端点，4 个模型 × 6 任务 × 2 条件 × 10 run 的完整实验**当前被端点阻塞**；三次实测分别遇到流式 `EmptyResponse`、429 限流和 504 网关错误（并发 10 / 3 / 1 均失败）。
本地 DeepSeek 官方 API 实验已完成，可作为 v2 的主要有效结果。Kaggle 侧后续可选：

1. 更快的 key/端点（推荐）：换用有更高吞吐的 NVIDIA NIM 配额或其他 provider；
2. 缩小规模：例如 4 模型 × 6 任务 × 2 条件 × 3 run，2 评委，单顺序（约 360 次调用）；
3. 只跑可用的 3 个模型（stepfun + glm-5.3 + glm-5.3-flash），跳过 deepseek；
4. 多会话续跑：保持 10 run，每会话跑一部分，重跑自动续。

代码已支持 1/2/3/4 四种方式；只需设置环境变量（`N_RUNS`、`GEN_MODELS`、
`JUDGE_MODELS`、`CONCURRENCY`、`TIME_BUDGET_MIN`）或提供新 key。

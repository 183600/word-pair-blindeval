# v2 运行状态（2026-10-22）

## 已完成

- `branches/main/`：main 当天快照已归档（排除 `branches/` 以避免递归）。
- `notebook_v2/llm_word_pairs_v2.ipynb` / `.py`：v2 代码已推送（脱敏版，非流式请求）。
- 代码修复：Git identity、提交白名单、密钥扫描、`http.extraheader`、清洗残留校验、
  双评委、确定性 A/B 位置平衡、provenance、时间预算、断点续跑、模型熔断。

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

用当前 NVIDIA key/端点，4 个模型 × 6 任务 × 2 条件 × 10 run 的完整实验无法在单次
Kaggle 会话内完成；即使非流式，单条完整任务也可能超过 10 分钟。需要以下之一：

1. 更快的 key/端点（推荐）：换用有更高吞吐的 NVIDIA NIM 配额或其他 provider；
2. 缩小规模：例如 4 模型 × 6 任务 × 2 条件 × 3 run，2 评委，单顺序（约 360 次调用）；
3. 只跑可用的 3 个模型（stepfun + glm-5.3 + glm-5.3-flash），跳过 deepseek；
4. 多会话续跑：保持 10 run，每会话跑一部分，重跑自动续。

代码已支持 1/2/3/4 四种方式；只需设置环境变量（`N_RUNS`、`GEN_MODELS`、
`JUDGE_MODELS`、`CONCURRENCY`、`TIME_BUDGET_MIN`）或提供新 key。

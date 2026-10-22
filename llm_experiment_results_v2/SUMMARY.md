# v2 汇总

- run_id: `v2-deepseek-20261022T235120Z`
- 生成模型: `deepseek-flash`, `deepseek-v4-pro`
- 评委: `deepseek-flash`, `deepseek-v4-pro`
- N_RUNS: 10 | COUNTERBALANCE: False | 并发: 10

| 生成模型 | 评委 | 有效比较 | baseline 胜 | cleaned 胜 | tie | cleaned 残留 |
|---|---|---:|---:|---:|---:|---:|
| `deepseek-flash` | `deepseek-flash` | 60 | 54 | 5 | 1 | 0/60 |
| `deepseek-flash` | `deepseek-v4-pro` | 60 | 52 | 8 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-flash` | 60 | 59 | 1 | 0 | 0/60 |
| `deepseek-v4-pro` | `deepseek-v4-pro` | 60 | 59 | 1 | 0 | 0/60 |

> 每个评委对每对做 一次评审（A/B 位置由确定性 hash 平衡）；位置偏差见每个 `summary__*.json` 的 `position` 字段。
> `cleaned_residual` 是清洗后仍含词对编号/“这些词中”等引用的条数。

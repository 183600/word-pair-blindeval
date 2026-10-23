# notebook22d6286ede

Kaggle Notebook [`wenjiazhong82355/notebook22d6286ede`](https://www.kaggle.com/code/wenjiazhong82355/notebook22d6286ede)
的脱敏导出与运行日志。

| 文件 | 说明 |
|---|---|
| `notebook22d6286ede.ipynb` | 从 Kaggle API 拉取的 notebook，保留原始代码与内核元数据；开头新增一页来源/安全说明 |
| `notebook22d6286ede.py` | notebook 代码的纯 Python 导出，便于 diff / 代码审查 |
| `notebook22d6286ede_run.log` | 本次运行的完整内核日志（stdout/stderr，71 KB） |
| `provenance.json` | kernel ref、最后运行时间、版本、镜像、GPU/联网开关、脱敏后 SHA-256 |

## 安全处理

- 原始 notebook 的 `OPENAI_API_KEY` 默认值（硬编码的 NVIDIA API key）已改为空字符串。
- 原始 notebook 的 `GIT_REMOTE_URL` 默认值中含 Gitee 访问令牌，已替换为不含凭据的
  `https://gitee.com/qwe12345678/jkdsfn.git`；需要自动推送时请通过 `GIT_REMOTE_URL`
  环境变量或 Kaggle Secrets 注入，并使用 credential helper，不要把 token 写回代码。
- 详见仓库根目录 [`SECURITY.md`](../SECURITY.md)。

## 运行产物

Notebook 在 `/kaggle/working/llm_experiment_results` 下生成：

- `results.jsonl`、`cleaned.jsonl`、`comparison.jsonl`
- `task{1..6}_*/{baseline,word_pairs}/run_*.md`
- `cleaned/task*/run_*.md`、`comparison/task*/run_*.md`

这些文件已归档到仓库根目录；统计与胜负表见根目录 [`README.md`](../README.md)。

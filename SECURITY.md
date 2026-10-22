# Security / 密钥管理

本仓库是公开仓库，**任何密钥都不应提交到 Git**。

## 当前状态

- `notebook/notebook22d6286ede.ipynb`、`notebook/notebook22d6286ede.py`、`jvdfka.py`、`vfdjk.py`
  中的硬编码凭据均已替换为环境变量 / Kaggle Secrets 读取或空默认值。
- 2026-10-22 已重写 Git 历史，清除了历史提交中出现的 Gitee 访问令牌、Kaggle 访问令牌和
  NVIDIA API key，并强制推送了所有分支。
- 这些密钥此前已随公开仓库暴露，**历史清理不能替代轮换**。请立即：
  1. 在 Gitee「设置 → 私人令牌」撤销旧 token，重新生成；
  2. 在 NVIDIA API 控制台吊销旧 key；
  3. 在 Kaggle「Settings → API」撤销旧的访问令牌（`KGAT_` 前缀）。

## 运行时的凭据注入

优先使用环境变量（本地）或 Kaggle Secrets（Notebook）：

| 变量 | 用途 |
|---|---|
| `OPENAI_API_KEY` | LLM API key（必填） |
| `OPENAI_BASE_URL` | 默认 `https://integrate.api.nvidia.com/v1` |
| `LLM_MODEL` | 默认 `moonshotai/kimi-k3` |
| `GIT_REMOTE_URL` | 需要自动推送时设置；建议用 credential helper，不要把 token 拼进 URL |

本地 Git 推送建议：

```bash
# 方式一：凭据助手
git config --global credential.helper store   # 或 libsecret / osxkeychain

# 方式二：一次性 extraheader（不会写入 .git/config）
AUTH=$(printf 'username:%s' "$GITEE_TOKEN" | base64 -w0)
git -c http.extraheader="Authorization: Basic $AUTH" push origin main
```

## 提交前检查

```bash
# 快速扫描常见密钥前缀
grep -rInE 'nvapi-|KGAT_|ghp_|sk-[A-Za-z0-9]{16,}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----' \
  --exclude-dir=.git .

# 检查历史中是否还有旧密钥（按前缀/特征扫描）
git grep -I -n -E 'nvapi-|KGAT_[0-9a-f]{32}|ghp_[A-Za-z0-9]{20,}' \
  $(git rev-list --all) -- . || true
```

发现泄露时：先撤销/轮换密钥，再清理仓库；不要把撤销前的旧值留在 issue、日志或提交信息里。

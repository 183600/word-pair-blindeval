# [v2:deepseek-flash] 任务3 CLI工具Idea | 条件: baseline | 第 2 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 15.74s | tokens: 41/2491

---

一个适合独立开发者做的 CLI 工具 Idea：

## 工具名：`envdoc`  
**一句话：从代码里扫描环境变量使用情况，自动生成/校验 `.env.example`，避免“本地跑不起来是因为少配了 env”。**

### 痛点
几乎每个项目都有环境变量问题：

- 代码里用了 `process.env.STRIPE_KEY`，但 `.env.example` 没写；
- 新同事 clone 后不知道要配哪些变量；
- `.env.example` 长期不更新，里面还有废弃变量；
- monorepo 里多个 app 各自有 `.env`，很容易混；
- CI 报错时才发现缺变量；
- 有人误把真实 secret 提交进 `.env`。

### 产品形态
CLI 扫描源码中的环境变量引用，和 `.env.example` / `.env` 对比，输出缺失、多余、疑似敏感项，并支持自动同步。

核心命令：

```bash
envdoc init        # 从代码中生成初始 .env.example
envdoc check       # 检查缺失、多余、疑似 secret
envdoc sync        # 安全更新 .env.example
envdoc explain KEY # 显示某个变量在哪些文件被使用
envdoc check --ci  # CI 模式，有问题返回非 0
```

示例输出：

```text
Missing in .env.example:
  STRIPE_SECRET_KEY    used in src/payments.ts:12
  REDIS_URL            used in src/cache.ts:4

Extra in .env.example:
  OLD_SENTRY_DSN      no code references found

Possible secret:
  .env contains real-looking value for DATABASE_URL
```

### MVP 范围
建议第一版只做 JS/TS 生态，2 周内可做出可用版本：

- 支持 `.env`、`.env.example`、`.env.local`；
- 扫描 `process.env.X`、`import.meta.env.X`；
- 支持 `envdoc.toml` 配置忽略项；
- `init` / `check` / `sync` 三个命令；
- 默认不打印 secret 值；
- 提供 GitHub Action 示例；
- 发布到 npm、Homebrew、GitHub Releases。

后续再支持 Python、Go、Rust、monorepo 多 package。

### 为什么适合独立开发者
- 不需要后端服务，单机 CLI 就能跑；
- 技术难度可控，核心是文件扫描和 diff；
- 痛点明确，容易用一句话传播；
- 可通过开源 + GitHub Action 获客；
- 后续可做付费团队功能：私有仓库策略、monorepo 规则、CI 审计、团队 dashboard；
- 也可以完全靠开源赞助和 Pro 版授权变现。

### 差异化点
已有一些 dotenv linter，但多数只检查 `.env` 文件本身。  
`envdoc` 的差异是：**从源码实际使用情况反推环境变量，并面向 monorepo 和 CI 场景做安全校验。**

### 验证方式
可以先写一个脚本，在 GitHub 上找 50 个公开的 Node/TS 项目，跑一遍“代码使用了但 `.env.example` 缺失的变量”，把结果截图发到 Reddit、Hacker News、X、V2EX、掘金等社区，看是否有人愿意试用。  

这个 Idea 的关键不是“再做一个 lint 工具”，而是解决一个非常高频的问题：**新项目拉下来，到底要配哪些 env。**

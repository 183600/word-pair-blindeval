# [v2:deepseek-flash] 任务3 CLI工具Idea | 条件: baseline | 第 1 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 11.85s | tokens: 41/1785

---

## Idea：`envscope` —— 环境变量一致性检查 CLI

**一句话：** 面向 JS/TS 项目和 monorepo 的本地 CLI，检查代码里实际使用的环境变量与 `.env.example`、Docker Compose、GitHub Actions、部署平台配置是否一致，并自动生成修复建议。

### 解决什么问题
小团队和独立开发者经常遇到：
- 代码用了 `process.env.DATABASE_URL`，但 `.env.example` 没写；
- `.env.example` 里有一堆已经废弃的变量；
- 本地能跑，CI / Docker / Vercel 上缺变量；
- monorepo 里多个 app 的环境变量边界混乱；
- 不敢把真实 `.env` 提交，但又不知道怎么维护文档。

现有工具多为 lint `.env` 文件本身，而 `envscope` 的核心差异是：**从代码 AST 里扫描真实使用情况，再和各环境配置文件做交叉校验。**

### 核心命令
```bash
envscope check
envscope fix
envscope diff --target docker
envscope report --format markdown
```

### MVP 功能
先只支持 **TypeScript / JavaScript + dotenv + GitHub Actions + Docker Compose**：

1. 扫描代码中的：
   - `process.env.FOO`
   - `process.env["FOO"]`
   - 常见框架配置里的环境变量引用
2. 扫描并解析：
   - `.env.example`
   - `docker-compose.yml`
   - `.github/workflows/*.yml`
3. 输出问题：
   - 代码使用但未声明：`MISSING_IN_EXAMPLE`
   - 示例声明但代码未使用：`UNUSED_IN_EXAMPLE`
   - CI / Docker 缺失变量：`MISSING_IN_CI` / `MISSING_IN_DOCKER`
   - 疑似敏感变量被写进示例值：`POSSIBLE_SECRET`
4. `envscope fix` 自动更新 `.env.example`，按字母排序、保留注释；
5. 退出码适合 CI，可以直接放进 GitHub Actions。

### 为什么适合独立开发者
- **范围可控：** MVP 只做 JS/TS 生态，2～4 周可做出可用版本；
- **无需后端：** 纯本地 CLI，发布到 npm / Homebrew 即可；
- **痛点高频：** 每个有部署流程的项目都可能需要；
- **容易传播：** 报错清晰、截图好看，适合发 X / Reddit / Hacker News；
- **可渐进扩展：** 后续支持 Python、Go、Rust、K8s、Terraform、Vercel、Fly.io 等。

### 技术栈建议
- CLI：Node.js + TypeScript + Commander / Clipanion
- AST 扫描：`ts-morph` 或 Babel parser
- YAML：`yaml`
- 输出：`picocolors` + `cli-table3`
- 测试：Vitest + fixture 项目
- 分发：npm 包，后续加 Homebrew

### 变现方式
- 开源免费版：本地检查、基础修复；
- Pro 版：
  - monorepo 多项目规则；
  - 团队自定义规则包；
  - CI 报告上传与历史趋势；
  - VSCode 插件联动；
  - 私有部署的团队策略检查。
- 早期也可以接“环境变量治理”咨询或企业定制规则。

### 差异化点
不要做“又一个 dotenv linter”，而是做：

> **从代码真实使用反推环境变量文档和部署配置的一致性工具。**

这个定位更窄、更明确，也更容易让用户一句话理解价值。

如果你愿意，我可以继续帮你把这个 Idea 拆成 README、CLI 命令设计和 2 周 MVP 开发计划。

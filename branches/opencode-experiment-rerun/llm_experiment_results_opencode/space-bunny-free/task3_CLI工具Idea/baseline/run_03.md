# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 3 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 15.7s | **tokens:** 198/1861(推理 329) | **finish:** stop

---

# Idea:Spec2Shell —— 把任何 API 的 OpenAPI 规范变成一个「能用 shell 脚本编排」的客户端 + 契约回归测试

**一句话**:`npx spec2shell ./openapi.yaml --name=petstore` 生成一个零依赖、类型安全、可管道组合的 `pet` 命令,并附带一套可在 CI 里跑的契约冒烟测试。

---

## 1. 痛点(为什么有人会为它付费)

- 后端团队有 Swagger/OpenAPI 文档,但**没人真的在终端里用它**。curl拼参数、改一个字段名就400,排查成本极高。
- 现在大家用 Postman/Bruno/Hoppscotch 做单次调试,但这些工具**进不了 CI、不能被脚本编排**,运维/QA/AI Agent 都用不上。
- AI Agent(Codex/Claude Code)最缺的就是「可信的、结构化的 API 调用方式」;而让 Agent 自由拼 curl 是幻觉重灾区。

Spec2Shell 正好卡在「调试工具」和「代码生成器」之间的空隙里:**既能在本地当交互式探索工具用,又能作为库被脚本和 Agent 调用。**

---

## 2. 目标用户(按付费意愿排序)

| 用户 | 场景 |
|---|---|
| SaaS 后端团队 | 给前端/SDK 提供统一的内部 CLI,替代散落的 curl 文档 |
| QA / 测试工程师 | 一行命令跑通 API 冒烟用例,PR 里自动生成 diff 报告 |
| AI Agent 开发者 | 把 MCP 工具集从 REST 自动生成,降低工具定义的幻觉率 |
| 独立开发者 | 快速把第三方 API(Payment/短信/OAuth)包成本地脚本 |

---

## 3. 功能范围

### MVP(4~6 周)
1. **解析层**:YAML/JSON →内部 IR(复用 `oasdiff` / `@apidevtools/json-schema-ref-parser`)。
2. **命令树生成**:`pet store list`、`pet store create --name rex --tag dog`,自动处理 path/query/header/body 参数。
3. **类型安全的输出**:默认表格 + `--json`,`--jq` 直接接管道。
4. **认证**:自动读 `API_KEY=xxx` 环境变量,支持 `--profile dev/prod` + 本地加密存储。
5. **契约冒烟测试**:生成 `*.spec2shell.test.ts`,CI 里跑,失败时输出「字段被移除/新增」的语义 diff(基于 `oasdiff` 的 breaking-change 检测)。
6. **零运行时依赖**:编译成单二进制(Gumpla 或 pkg),用户不装 Node。

### v2(差异化护城河)
- **Agent 模式**:`--mcp` 直接生成一个 MCP Server,或输出给 LLM 的紧凑工具描述(带真实 schema,不是自然语言猜测)。
- **录制回放**:把真实流量录成 `.http`-like 夹具,离线重放,做 fixture-based 测试。
- **Diff-driven 生成**:`--against ./openapi.next.yaml`,只在破坏性变更时告警,团队可当「API 兼容性守门员」。
- **示例库**:官方收录 Stripe/Twilio/SendGrid/Shopify 等的生成结果,`npx spec2shell add twilio` 即用(引流入口)。

---

## 4. 技术选型(一个人能扛住)

- **语言:Go**。单静态二进制、启动<20ms、跨平台零摩擦,这是 CLI 工具最重要的体验指标。代价是 YAML/JSON Schema 校验要自己接,但可以直接调用 `libopenapi`。
- **IR 与代码生成解耦**:先设计好中间表示,生成器做成 Go text/template,便于未来加 Rust/TypeScript 目标。
- **CLI 框架**:cobra(生态好)+ 自研 shell 补全生成。
- **测试**:golden file 快照测试 + 一组「真实 API」集成测试(用 httpbin / 自建 mock server)。

---

## 5. 差异化对比

| 现有方案 | 缺什么 |
|---|---|
| Postman / Bruno | 不能进 CI 当代码,不能被脚本/Agent 调用 |
| openapi-generator(Java) | 重、启动慢、生成几万行代码没人读 |
| Swagger CLI | 只做文档,不生成可执行客户端 |
| 直接 curl | 无类型、无校验、无兼容性检查 |

**定位语**:`the missing link between your OpenAPI spec and your shell pipeline`。

---

## 6. 变现路径

1. **免费开源核心**(MIT)。Apache-2.0 会被大厂要求开源贡献,反而限制商业化。
2. **Spec2Shell Cloud(约 $9/开发/月)**:托管团队 API 目录、集中式 profile 管理、CI 兼容性报告、历史 breaking change 时间线。
3. **企业版一次性授权**:SSO/SAML、离线内网部署、私有模板市场、审计日志。
4. **API 目录作为分发渠道**:类似 Homebrew 之于 CLI —— 「一键安装某个服务的官方 CLI」本身就是自然增长飞轮。

---

## 7. 四周路线图

| 周 | 交付 |
|---|---|
| W1 | OpenAPI → IR,path/operation/参数模型,单二进制跑起来 |
| W2 | 命令树生成、认证 profile、`--json` 输出、shell 补全 |
| W3 | 冒烟测试生成 + oasdiff 集成;10 个真实 API 的 golden 快照 |
| W4 | 文档站、`npx`/`brew` 分发、Product Hunt + Hacker News 发布、写一篇「我们把300 行 curl 变成 3 行脚本」的对比文 |

---

## 8. 主要风险与对策

- **风险:大厂已有一堆生成器**(Fern、Speakeasy、Braintree SDK)。
  → 对策:不打「SDK 生成」,打「**调试 + 契约 + 脚本化**」这条细分线,输出物是**给人/给 shell 用的小工具**,不是几万行 SDK。
- **风险:OpenAPI 规范本身太烂**(path 里塞了5 个 query、schema 全是 any)。
  → 对策:把「规范质量评分」做成一个独立小功能,本身就是传播点。
- **风险:AI 让 curl 更好写了**。
  → 反过来想:Agent 需要**确定性**的工具,而规范驱动的 CLI正好是确定性的训练靶子;把 `--mcp` 做出来,你卖的是「Agent 的可靠性」,这比卖给人用更抗替代。

---

## 备选 Idea(如果想更小更快验证)

1. **`ctxpack`** —— 把一次终端/Claude Code 会话录成「可搜索、可回放、可分享」的上下文包,自动生成 how-to 卡片。极小,但付费意愿弱。
2. **`dotenvdoctor`** —— 扫全仓库找出 `.env.example` 与代码实际读取的变量不一致、密钥泄漏到 git 历史、跨环境漂移。痛点尖锐,但市场窄,适合做成 DevOps 生态里的一颗钉子。

如果要我选,**Spec2Shell 的天花板明显更高**,因为它同时服务人、脚本和 Agent 三类用户。

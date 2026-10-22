# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 4 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 14.4s | **tokens:** 198/1875(推理 337) | **finish:** stop

---

# Idea：**curlsmith** —— 把 `curl` 命令变成可维护的 TypeScript 客户端

## 一句话
开发者复制粘贴的 `curl` 命令（从文档、Stack Overflow、别人的博客、网络面板里），粘贴进终端，工具自动反推出接口定义，并生成**带类型的、可重试、可测试**的 TS/Python SDK 代码。

---

## 为什么值得做

**痛点极其真实且高频**：几乎每个写后端对接的开发者，每天都在和 `curl` 搏斗。现有解法都不够好：

| 现有方案 | 问题 |
|---|---|
| 手抄进 Postman | 变成又一个 GUI，代码还是得手写 |
| `openapi-generator` | 需要对方先有 OpenAPI 文档，而很多内部/小众 API 根本没有 |
| 直接把 curl 改成 `fetch` | 只有字符串拼接，没有类型、没有错误处理、参数拼错要等运行时才炸 |
| 问 AI | 好用，但不可复现、不可版本管理、上下文一长就飘，而且把公司 API 密钥发出去有合规风险 |

**差异化**：curlsmith 是**本地优先的纯 CLI**，反向工程（reverse-engineer）而不是正向消费文档。这个方向几乎没人认真做过。

**可演示性极强**：输入一段乱七八糟的多行 curl，`⏎` 一按，屏幕上长出结构清晰的类型化代码。这个"魔法时刻"在 Twitter/X 上天然有传播性——独立开发者做产品最需要的就是这种 demo视频。

**独立开发者的成本极低**：单文件 CLI、零后端、无数据库。核心难点（curl 参数解析）是一个纯语法问题，能用几百行代码解决；剩下的时间是打磨边界情况。

---

## 目标用户

- **主要**：日常做前端 / 全栈、要对接大量第三方 API 的开发者（尤其那些对方文档很烂的场景）
- **次要**：后端工程师写内部服务客户端、爬虫开发者、AI Agent 工具链的构建者

---

## MVP 范围（建议 4 周内上线）

```
$ smith https://api.stripe.com/v1/charges \
  -H "Authorization: Bearer $STRIPE_KEY" \
  -d amount=2000 -d currency=usd -d source=tok_visa

✔识别：Stripe Charge API（POST /v1/charges）
✔ 推断字段：amount:number, currency:enum[usd,currency...], source:string

→ 生成 src/api/charges.ts
```

**必须做的（v0.1）**
1. **curl 解析器**：`-X/-H/-d/-F/--data-raw/-u/-b/--compressed`、`--form`、URL 里的 query 参数、`&&` 串联的多段 curl、跨平台（curl.exe / PowerShell `curl` 别名 → `iwr`）
2. **参数推断**：数字/布尔/enum/字符串（从格式和取值猜）、路径参数 vs body 字段、重复 key → 数组
3. **代码生成**：输出 TS 函数，返回类型化对象；自动加超时、错误分支、`AbortSignal`
4. **zod schema 导出**（可选 schema）：让运行时校验和类型共存
5. **项目级累积**：所有生成的 API 存进 `.smith/api.json`，支持 `--list`、`--generate-all`，生成一个统一客户端

**明确不做（v0.1）**：执行 curl 发请求（保持工具"不碰你的密钥"的安全叙事）、自动推断响应体（v0.2）、UI、团队协作

---

## 技术选型

- **运行时**：Node + TypeScript，用 `commander` 或 `clipanion` 写 CLI
- **解析**：手写 tokenizer（不要用正则大杂烩）；建议用 `acorn` 无关，保持零依赖或极少依赖
- **代码生成**：`ts-morph`（比字符串模板拼接强太多，能保证生成的代码能被格式化、能 import）
- **格式化**：`prettier` 作为库调用（`format()`），输出即符合项目风格
- **发布**：npm 包名 `curlsmith`，`npx curlsmith` 即用；配一个单页 landing + GIF demo
- **可选**：Rust 重写解析器（如果你想练手/极致启动速度，但不是必需）

---

## 商业模式

| 层级 | 内容 | 价格 |
|---|---|---|
| Free | 本地生成、无限 API、单文件 | $0 |
| Pro | 响应体推断（录制/粘贴 JSON响应自动生成返回类型）、OpenAPI 导出、monorepo 支持 | $6/月 或 $39/年 |
| Team | 私有 API 注册表、内部规范校验（防止手写 fetch 散落各处）、CI 检查 | $15/人/月 |

**关键**：所有推断在本地完成，不上传任何请求数据。这是相对"问 AI"的最大卖点，也是能收钱的前提。

---

## 增长飞轮

1. **入口**：GitHub README 放一段15 秒 GIF；npm关键词 `curl`, `api-client`, `codegen`, `typescript`
2. **钩子**：内置 `smith init --hooks`，在 `.env` 或 `Makefile` 里留提示；有流量后考虑提一个 PR 给 Prettier / ESLint 插件目录
3. **内容**：写《我们把 300 条 curl 喂给 GPT，输出了一个 TS 客户端》这类对比评测——直接踩 AI 的痛点又不树敌
4. **生态**：让用户能贡献解析规则（某个框架的奇怪 curl 写法），形成 rules 仓库

---

## 主要风险与对策

| 风险 | 对策 |
|---|---|
| "这不就是 AI 写代码了吗" | 强调确定性、可 diff、可版本控制、可批量生成；AI 是模糊的，smith 是可复现的 |
| 推断不准 | UI/交互上诚实：显示"推断"标记，允许 `--schema` 手动覆盖并锁定；把置信度暴露出来 |
| 冷启动（解析器覆盖不全） | 先只支持 95% 的常见写法，遇到不支持的降级为"原样转换 + 提示"，并在 GitHub 收 issue补规则 |

---

## 为什么这个适合独立开发者

1. **一个人能做完核心**：解析 + 生成，没有服务端、没有 GPU、没有数据库
2. **有明确的"完成"标准**：能跑通 Stripe / GitHub / OpenAI 三个真实 API 就成了3. **付费点清晰**：从"个人手写"→"项目级 API 管理"的升级路径非常自然
4. **有口碑传播点**：生成的代码质量好，别人会主动晒---

**备选 Idea（如果想更小更快）**
- `gitship`：从 `git log` + 分支状态生成一份"发布前 sanity check"报告（有没有未提交的 `.env`、版本号对不上、CHANGELOG 缺失、依赖有已知漏洞）——一周能出 v0.1
- `portward`：一键找出本机占用端口的进程并给出终止建议 + 项目归属推断（比 `lsof` 好用一百倍）

要不要我把 curlsmith 的 curl 解析器设计（tokenizer 的具体分层）和数据模型（`api.json` 的 schema）细化成一份可以直接开工的技术方案？

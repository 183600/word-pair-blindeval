# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 10 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 22.1s | **tokens:** 198/2670(推理 1132) | **finish:** stop

---

# Idea:`meter` —— 本地 AI/LLM 用量与成本治理 CLI

**一句话**:一条命令,让你看清 (并拦住) 自己在 Claude Code / Cursor / Codex / API 上烧掉的每一分钱,并把成本精确归因到「项目 / 分支 / PR」。

```
$ meter watch          # 实时 TUI:每个 repo、每个 PR花了多少,超预算立刻拦截
$ meter budget50      # 本月封顶 $50,超了就退出码1,让 CI 挂掉
$ meter report --by pr # 生成周报/Markdown,一键贴到 PR 或 Slack
```

---

## 1. 为什么这个问题值得做

| 现状 | 痛点 |
|---|---|
| Claude Code / Cursor / Codex / Aider / OpenCode **各有各的本地日志格式** | 开发者根本不知道自己一个月花了多少 |
| 成本只反映在 **云厂商账单**上,滞后7–30 天 | 没有 feedback loop,月底才震惊 |
| 团队多人共用一个 API key | 完全无法归因到人或 PR |
| Helicone / Langfuse / Braintrust | 要自建服务、要改代码接 SDK、要传数据上云(隐私顾虑) |

**核心空位**:没有一个「零配置、纯本地、单文件、不用改一行代码」的 LLM 花费可视化工具。大多数人是被账单教育出来的,不是被 dashboard 教育出来的。

---

## 2. 目标用户(优先顺序)

1. **重度使用 coding agent 的独立开发者 / 小团队 lead**(痛点最强,付费意愿最高)
2. 已经在用 Claude Max / 团队套餐,想验证「真的省了吗」的3. 公司里管着 AI 采购、想给团队设预算硬上限的技术 lead

---

## 3. 功能路线图

**MVP(2 周)**
- 解析器插件架构:Claude Code JSONL、Codex session、Cursor、Aider、opencode
- 抓取 OpenAI / Anthropic / Gemini / DeepSeek / OpenRouter 定价(拉 `models.dev`,本地缓存,离线可用)
- `meter report` 终端表格:今日/本周/本月,按 repo、模型、项目分组
- 缓存命中率、平均时延、token 量趋势
- brew + npm + `curl -fsSL | sh` 三分发

**v1(4–6 周)**
- `meter watch`:实时 TUI,仿 `btop`,支持 `--filter repo`
- `meter budget<amount>`:shell hook 模式,超预算直接 block agent 调用(核心差异点)
- GitHub Action:`meter-pr-cost`,在 PR 上评论「本 PR 的 AI 成本 $2.31,并列出 PR 上的 session 链接」
- Git 集成:从 commit message / 分支名解析 `PROJ-123` 回溯项目成本

**v2(付费)**
- 团队版:自托管 collector + 共享 SQLite/Postgres + 简单 Web 看板 + Slack/飞书告警
- 归因增强:读取 agent实际改动的 diff 行数 → **算「每个 PR 的人工成本 vs AI 成本」**(这才是 lead 真正想看的数字)
- 预算告警 webhook、账单对账(和厂商 invoice 精确对齐,解决折扣/缓存计费的偏差)

---

## 4. 技术选型

- **Rust 或 Go**,单静态二进制,冷启动 <10ms(用 Rust + `ratatui`)
- 解析层用**插件式适配器**(trait),新 agent格式一两天就能加一个 → 天然形成「我加了个 Cursor 支持」的 PR 生态
- 数据落 **本地 SQLite**(DuckDB 更适合聚合分析),默认100% 本地
- 定价表内置 + 离线缓存,避免运行时网络依赖
- 分发:GitHub Releases、`brew tap`、npm 包(装个 JS wrapper)、`install.sh`;再打个 Homebrew core 提升信任
- AGPL-3.0(读别人日志做聚合,保护自己沉淀的解析器资产)

---

## 5. 差异化 / 护城河

- **对标产品都要你「接入」,这个是「已有日志直接读」**——零接入是唯一级优势
- **本地优先、隐私友好**:公司安全团队不会否决一个不往外发数据的工具
- **从「看」到「拦」**:预算硬限制 + CI 退出码,这是 dashboard 类产品做不了的
- 护城河 = 解析器覆盖面 + 定价表准确性 + PR 级归因规则库,都是时间沉淀,不是代码量

---

## 6. 定价

| 层 | 内容 | 价格 |
|---|---|---|
| CLI 本地 | 全部报告、watch、budget、Action | 免费 |
| Pro | 邮件周报、历史趋势、预算 API、自定义分组规则 | $9/月 |
| Team(自托管) | 共享看板、成员归因、Slack 告警、SSO | $15/人/月,年付 $150/席位 |

---

## 7. 30 天执行计划

- **D1–D3**:读一遍各家 agent 日志格式,写 2 个解析器,确认数据可用 → **先验证可行性再写代码**
- **D4–D10**:`meter report` + 定价表 + SQLite schema
- **D11–D16**:`meter watch` TUI + budget block
- **D17–D21**:GitHub Action + PR 评论
- **D22–D30**:README 截图、Landing 页、录屏 Demo,HN + r/ClaudeAI + r/rust + X 发一轮,同步投5 个竞品仓库的讨论区**成功指标**:一周内 ≥200 star,20 个 Show HN 评论,3 个付费 Team试用。GitHub Action 被装上 >500 次就是强信号。

---

## 8. 风险与应对

- **风险**:Helicone/Langfuse 顺手加个「本地模式」;或 Anthropic 官方出成本面板  → **应对**:押注官方绝不会做的 *跨厂商归因* 和 *预算硬拦截*;保持每月一个解析器适配的新节奏
- **风险**:定价表变化导致不准 → 做 `/verify` 校验命令 + 社区上报机制- **风险**:Agent 日志格式不稳定 → 解析器容错 + 版本号 + 明确报错提示,而不是静默算错

---

## 备选 Idea(如果想换赛道)

1. **`repro`** —— 把你在终端/浏览器里的一连串手动操作录成可回放的脚本 + 一键生成 README动画 gif(填补 asciinema 的空隙:截图美观 + 可分享链接)
2. **`envbox`** —— `.env` 的 git 内加密版本管理 + 密钥轮换 + 本地 mock,面向1–5 人小团队(替代 Doppler)
3. **`contract`** —— OpenAPI/protobuf 契约的 breaking change 检测 + 自动生成 mock server + CI 门禁(比 oasdiff 更傻瓜)

如果让我选,还是第一个:痛点真实、数据零门槛、无竞品零妥协、定价空间清晰。

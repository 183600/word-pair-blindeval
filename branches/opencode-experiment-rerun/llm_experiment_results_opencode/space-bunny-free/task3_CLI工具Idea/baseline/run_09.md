# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 9 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 13.9s | **tokens:** 198/1580(推理 320) | **finish:** stop

---

# Idea:WatchDiff —— 把"网页/API 变化"变成一行命令 + 一条通知

**一句话定位**:一个5MB 的单文件 CLI,让你用一条命令对任意网页、JSON API、RSS 页面做"快照 + 语义 diff",发现变化时自动推送到 Slack / 飞书 / 邮件。

```bash
$ watchdiff add https://api.example.com/v1/pricing --json-path plans[*].price --desc "定价页"
$ watchdiff watch --every 30m
✔ [2m ago] 价格变化:Pro $29 → $39 (plans[2].price)
  → 摘要: +34%, 影响12 个客户
✔ [2h ago] 新增字段: plans[*].trialDays
```

## 为什么值得做

| 维度 | 说明 |
|---|---|
| 真实痛点 | 运维/爬虫/竞品分析/价格监控/接口联调,现在都靠 crontab + diff + 手写 jq,散落各处 |
| 极小切口 | 不做"另一个 Postman",只做"抓 →存 → 比 → 报"四步 |
| 天然留存 | 定时任务跑在用户机器/CI 里,一旦接入就长期驻留(churn 低) |
| 自传播 | 生成的报告页可公开分享(类似 badge / status page),带来 SEO 和口碑 |

## MVP范围(建议 3~4 周)

**必须有**
1. `add / ls / rm` —— 用配置文件(`watchdiff.yaml`)管理监控目标
2. **抓取层**:支持 JSON API、HTML(极简 CSS 选择器)、RSS
3. **规范化 diff**:JSONPath 子树提取 → 排序 + 字段白名单 → 忽略时间戳/噪声字段 → 结构化 diff
4. **通知**:Slack webhook / 飞书 / 邮件 / 终端,可 `--once` 手动跑
5. **存储**:SQLite,本地优先,只存最近 N 次快照(Git 友好的 `.watchdiff/` 目录)
6. **CI友好**:非零退出码 + `--json` 输出,能直接当 GitHub Action 用

**明确不做**(v1 砍掉):代理抓取、JS 渲染(留给 v2 提示用户)、团队 SaaS 后台、Web UI。

## 技术选型

- **Go**(单二进制、交叉编译、内置 HTTP,比 Rust 上手快)
- `cobra` 或 `urfave/cli` 做命令
- `tidwall/gjson` 做 JSONPath 提取,`r3labs/sse`?不需要- HTML:`goquery`;RSS:`mmcdole/gofeed`
- diff:自己实现"树形结构 diff"(字段级增删改),输出比文本 diff 更适合结构化数据
- 分发:Homebrew tap + `curl \| sh` + GitHub Releases
- 自托管交互:`watchdiff login` 只是可选的云端通知中转,不影响本地使用

## 差异化钩子(避开和 n8n/Zapier 硬碰)

1. **语义化噪音过滤** —— 自动忽略 `updatedAt`、`nonce`、`requestId` 等易变字段,这是普通 diff 工具的最大痛点
2. **变更影响摘要** —— 用规则/小模板把 `+34%` 翻译成"涨价"这类人话(v2 可接 LLM,成本可控)
3. **一条命令即部署** —— 不需要账号就能 `npm i -g` 用起来,首次付费发生在"团队协作/历史回溯/私有源"时

## 商业模式

- **Free**:本地无限目标,每 6h 一次频率限制
- **Pro $8/月**:分钟级频率、历史回溯与时间旅行查询(`--as-of`)、多源聚合规则- **Team $19/席位/月**:共享 workspace、密钥托管(SOPS 加密)、Slack 富报告- **一次性买断 $39**:终身版,给不想订阅的用户,锚定定价用

## 增长路径

- 在 Hacker News / Reddit r/devops / r/webdev 发"Show HN: 我用 500 行 Go 写了个价格监控器"
- 给开源项目写 `CONTRIBUTING` 里的 CI Action:PR 触发依赖/API 兼容性检查
- 榜单页:"Top 100 SaaS 定价页变化追踪"(公开数据,自带流量)

## 主要风险与对策

| 风险 | 对策 |
|---|---|
| 目标网站改版导致选择器失效 | 选择器失效时明确报错并推送"源已失效",而不是静默失败;提供 `watchdiff test` 自检命令 |
| 抓取涉及法律/ToS | 只抓公开页,内置 robots 与频率限制,明确禁止用于绕过登录/付费墙;提供官方 API 优先的推荐 |
| 变现困难 | 免费层必须真的够用,付费点锁在"省时间"而非"能用到"的功能上 |
| 竞品(n8n, changedetection.io) | 我们的战场是 CLI + 结构化 JSON语义 diff + 开发者心智,不进可视化编排赛道 |

## 4 周路线

- **W1**:抓取 + 规范化 + 树形 diff 核心库 + CLI骨架
- **W2**:`watchdiff.yaml` 配置 + SQLite 存储 + Slack/飞书通知 + `--json` CI 模式
- **W3**:噪音过滤字典、HTML/RSS 源、`watchdiff test` 自检、写 README + GIF
- **W4**:Homebrew tap、GitHub Action、3 个种子用户内测、定价页、Show HN 发布

**判断标准**:如果一周内你能拿到 5 个陌生开发者愿意把它放进 CI 或 crontab,这个 idea 就成立;否则优先调整"噪音过滤 + 语义 diff"的质量,而不是加功能。

# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 6 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 22.0s | **tokens:** 198/2214(推理 364) | **finish:** stop

---

# 💡 Idea：**`sentinel`** —— 给 AI 编码代理（AI Coding Agent）用的终端"安全带"

> 一句话：`sentinel` 是一个 CLI 工具 + 轻量守护进程，用来**拦截、审计、限流** AI 编码代理（Claude Code / Cursor / Codex / Aider / OpenCode 等）执行的所有 shell 命令。

```bash
$ sentinel install          # 30 秒接入，包裹 agent 的 shell
$ sentinel run claude       # 所有 rm / curl / sudo / git push 都要过审
$ sentinel ls --since 1h    # 审计日志：这个小时代理干了什么
```

---

## 1. 为什么值得做（痛点是真的）

2024→2026，几乎每个开发者都在终端里养了一个"能自己敲命令的实习生"。但没人解决三件事：

|痛点 | 现状 |
|---|---|
| **代理会误删/误推送** | `rm -rf`、`git push --force`、`DROP TABLE` 都是真实的灾难，已有大量事故帖 |
| **团队没有审计** | 出了事无法回答"昨晚3 点 agent 到底改了什么、跑了什么" |
| **Token / API 花费失控** | 一个死循环的重构任务能烧掉几百美元，没人拦 |

现有方案都不够格：
- **Cursor Rules / `.cursorrules`** —— 只是"软提示"，代理可以无视- **Docker沙箱** —— 重、体验差、跨平台麻烦
- **公司内部的 wrapper脚本** —— 不可移植、没人维护

**差异化：零配置、跨平台（Rust 单二进制）、策略即代码（YAML/JS）、带审计回放。**

---

## 2. 目标用户（按付费意愿排序）

1. **2–20 人的小团队 CTO / Tech Lead** —— 最痛、最有钱、最怕出事 ⭐️主力
2. **独立开发者** —— 怕自己的生产环境被代理搞坏
3. **安全敏感的受监管公司** —— 合规审计需求（能上企业版）
4. **Agent 工具作者** —— 需要给自己产品加护栏

---

## 3. MVP 范围（**2 周能做完，别贪**）

**v0.1 只做 6 件事：**
1. `sentinel run <cmd>` —— 包装任意 agent CLI，转发所有子进程
2. **命令拦截引擎** —— 解析 argv（不靠字符串正则，避开 `r''m''-rf` 这类绕过）
3. **策略文件 `.sentinel.yaml`**
   ```yaml
   rules:
     - match: "rm -rf /*"
       action: deny
     - match: "git push"
       action: confirm
       timeout: 300s
     - match: "sudo *"
       action: allow_with_log - match: { agent: "curl" }
       action: deny # 阻断 exfiltration
       unless: { net: ["registry.npmjs.org", "api.anthropic.com"] }
   ```
4. **拦截时的 TUI 提示**（`ink`）：显示完整命令 + diff 预览 + 风险等级，Y/N/always
5. **审计日志**（JSONL）→ `sentinel replay<session>` 回放整个会话的命令时间线
6. **成本计量**：拦截 hook 顺便统计 token 消耗 / 命令次数，`--max-budget` 超限自动 kill

**明确不做（v1之前）**：沙箱、远程策略同步、团队 dashboard、AI 风险打分（先用规则）。

---

## 4. 技术选栈

| 层 | 选型 | 理由 |
|---|---|---|
|核心 | **Rust**（`clap` + `serde_yaml` + `notify`） | 单二进制分发是 CLI 的最大优势；跨平台无依赖，30MB 以内 |
| TUI 交互 | 从 **Rust 调用 ink/Node**，或直接用 `dialoguer` | 尽量纯 Rust，减少用户 Node 依赖 |
| 日志 | JSONL + `tracing` | 便于后续 grep/jq |
| 分发 | npm wrapper（`npx sentinel`）+ Homebrew + `curl \| sh` | npm 是开发者天然入口 |
| 协议 | **设计成通用 hook 层**：未来支持 `PreToolUse` 类的标准接口 | 防止被某个 agent 的 API 锁死 |

**关键工程难点（也是护城河）：**
- 必须用 **PTY 转发**而不是 pipe，否则 agent 的交互式 UI、ANSI 进度条、raw mode 全崩
- 拿到子进程的完整 argv（跨平台 `procfs` / `WMI` 差异很大，这块很脏很值钱）
- 异步 hook 下的超时/中断/信号传递要正确

---

## 5. 变现路径

| 版本 | 价格 | 内容 |
|---|---|---|
| **Free (OSS)** | $0 | 本地策略、无限审计日志、单用户 |
| **Pro** | $9/dev/月 | 团队共享策略库、会话回放 UI、成本仪表盘、自定义策略 JS |
| **Team / Enterprise** | $20+/dev/月 | SSO、远程策略、集中审计导出、合规报告、Slack/飞书告警 |

**开源许可建议**：核心用 Apache-2.0（要生态），企业功能闭源。

---

## 6. 冷启动获客（重点）

这个品类的天然优势是**"代理出一次事，搜索量就涨一次"**。

1. **GitHub Action 一键接入**：在仓库 README 打 badge "protected by sentinel" —— 每个被保护的项目都是一次免费广告
2. **事故复盘帖**：等一次高热度事故（一定会来），立刻写技术复盘 + 3 行接入代码
3. **给 agent 工具作者提 PR**：把 sentinel 作为官方推荐的护栏，做成 Claude Code / OpenCode 的 plugin —— B2B2C 杠杆最大
4. **内容**：写《我们分析了 100 万条 AI 代理执行的命令，发现这 12 个最危险》，用真实数据做 SEO 长尾
5. **KOL**：给 AI 编程区 YouTuber / 播客主寄一封"帮你省了 XX 美元"的账单截图

---

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 大厂（Anthropic/OpenAI）自己内置护栏 | 我们的定位是**跨代理**的策略与审计层，做它们的"合规插件"而非对手 |
| 用户嫌麻烦不装 | 默认极宽松（只挡5 条致命命令），零配置，npx 即用 |
| 被绕过 | 承认"这是马赛克而非瓷砖"——用 hook 层 + 明确告知，信任团队自主决定，而非虚假的安全承诺 |
| 付费意愿低 | 真正掏钱的是团队合规，不是个人；主打"法务免责/审计报告"这个付费点 |

---

## 8. 90 天路线图

- **第 1–2 周**：MVP，Rust骨架 + 规则引擎 + 审计日志，自己日常用
- **第 3–4 周**：TUI 审批界面 + `replay` 回放，发布 Hacker News + Show HN
- **第 5–8 周**：npm/brew 分发、GitHub Action、5 个 alpha团队用户
- **第 9–12 周**：Pro 版（团队策略库 + 成本仪表盘）+ 首次开票

**验证成功的信号**：第 30 天有人主动 PR规则库，第 60 天有团队问"能不能接我们的 SSO"。

---

## 备选 Idea（如果想更小更快）

如果你想**两周内上架变现**，这几个盘子更小但更锋利：

1. **`clisnap`** —— CLI输出的快照测试框架。竞品（jest-snapshot / tryharder）只测 stdout，你要做 **真 PTY 渲染** 的终端输出 golden test + 跨平台归一化。痛点真实、小而深、适合做付费 SaaS（托管 golden files + CI 报告）。
2. **`pkgdiff`** —— 一个命令看懂"我的依赖升级到底改了什么破坏性变更"，聚合 npm/PyPI/Rust 的 changelog + 自动跑兼容测试。
3. **`exit0`** —— 检测你的项目里哪些 CI 失败是" flaky"的，自动复跑 + 生成 GitHub Issue，团队痛点极强，PR 转化率高。

---

需要我把其中一个想法细化成**可以直接开工的任务清单**（目录结构 / 核心代码骨架 / 第一条 commit 写什么）吗？或者你更看重快速上架、更看重大市场，我可以调整方向。

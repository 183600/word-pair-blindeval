# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 2 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 19.3s | **tokens:** 198/2521(推理 590) | **finish:** stop

---

## Idea:`promptctl` —— 把 Prompt 当成代码来版本管理、回归测试和发布的 CLI

> 一句话:一个零配置、单二进制的命令行工具,让 AI 应用的 Prompt 拥有像代码一样的 diff、review、评测和发布流程。

---

### 1. 解决什么问题

现在几乎所有独立开发者的 AI 功能,Prompt 都是散落在各处的字符串字面量:

```python
SYSTEM = "You are a helpful assistant for a Shopify store..."
```

这带来三个真实存在的痛点:

- **改 Prompt = 裸奔上线**:改一个词不知道会不会让准确率崩掉,只能手动跑几十条样例肉眼看。
- **Prompt 无法 review**:几千字符的字符串塞在 MR 里,评审的人看不出改了什么、为什么改。
- **成本不可见**:没人知道哪个模板 token 最多、哪次改动让延迟涨了 200ms、换模型后整体效果掉了多少。

已有方案(promptfoo、LangSmith、Langfuse)都是**重量级平台**:Node依赖、配置文件、要么上云要么接后端。对独立开发者来说太重了,`写个 Python 脚本 + CI 里跑` 才是真实形态。

**"轻量、local-first、像 git 一样的 Prompt工具链" 这块是空的。**

---

### 2. 核心工作流(用户每天会敲的命令)

```bash
# 初始化:扫描代码库,自动抽取所有 prompt 字面量,写成可编辑的文件
$ promptctl init
  ✓ found 37 prompts in 12 files
  ✓ created .prompts/ (37 files, 8 templates)

# 改完 prompt 后:语义化 diff,不是文本 diff
$ promptctl diff
  support_ticket_v3 → v4
  - role: "You are a helpful assistant"
  + role: "You are a senior support agent. Never speculate about policies."
  + added: 2 sections, 1 example
  ~ est. tokens: 412 → 689 (+67%) ⚠  budget

#回归测试:对比新旧版本在固定数据集上的表现
$ promptctl eval --against v3
  Dataset: .prompts/_eval/support_ticket.jsonl (120 cases)
  v3  pass@1  0.842 latency  820ms   cost  $0.031/100 calls
  v4  pass@1  0.908 ▲ +6.6pts latency  1104ms  ▲ +284ms ⚠
       cost     $0.058/100 calls  ▲ +87% ⚠
  → VERDICT: quality up, budget exceeded# 提交时自动生成 review 报告,贴进 PR$ promptctl review > prompt-review.md

# 发布与回滚
$ promptctl promote support_ticket@v4 --env prod
$ promptctl rollback support_ticket@v3
```

---

### 3. MVP 范围(建议 4~6 周,一个人)

| 优先级 | 功能 | 说明 |
|---|---|---|
| P0 | `init` 抽取器 | 只支持 Python + TypeScript,正则/AST 抽取 prompt 字面量与 f-string/jinja 模板 |
| P0 | 文件化 + 版本管理 | prompt 落盘到 `.prompts/*.md`(带 YAML frontmatter),可进 git,可手改 |
| P0 | `eval --against` | 内置一个极简评测器:精确匹配 / 包含匹配 / 规则断言 / LLM-as-judge(可选 `--judge`);跑在缓存上 |
| P0 | 成本与 token 预算 | 记录每次 eval 的 token、延迟、估算费用,超出阈值 exit code 非 0 → 可直接接 CI |
| P1 | `diff` 语义化对比 | 按"指令/示例/输出格式"分段 diff,而不是纯文本 diff |
| P1 | `review` Markdown 报告 | 生成可直接贴 PR 的表格,带前后指标对比 |
| P2 | 运行时 SDK | `promptctl.load("support_ticket")` 加载版本,支持灰度百分比切流量 |

**明确不做(MVP 阶段)**:Web UI、多人协作编辑、向量检索、从零构建评测数据集(这是 promptfoo 的活)。

---

### 4. 技术选型

- **语言:Rust**(单二进制、启动 <10ms、brew install 无依赖)——CLI 工具的默认正解。
 - 备选:Go(更快出活,分发同样干净)。
- **解析**:tree-sitter(Python / TypeScript / Go),比正则可靠又不重。
- **CLI 框架**:`clap` derive + `comfy-table` / `tnu` 输出。
- **diff**:`similar`(diff crate)或自己写语义分段。
- **评测执行**:HTTP 调用 OpenAI 兼容 endpoint;缓存用本地 SQLite(`rusqlite`),keychain 取 API key。
- **分发**:Homebrew tap + npm 包(带 postinstall 下二进制)+ `curl | sh` 一键脚本。
- **配置**:**零配置**是核心卖点,一切靠约定优于一切靠 YAML。

---

### 5. 差异化 / 竞争定位

| 现有工具 | 定位 | promptctl 的区别 |
|---|---|---|
| promptfoo | 评测平台,Node,配置文件驱动 | 单二进制、零配置、**版本对比是一等公民** |
| Langfuse / LangSmith | 可观测性后端,要部署/接入 | local-first,不接管你的调用链,只管 prompt 本身 |
| Braintrust | 企业评测平台 | 太重太贵 |
| prompt-manage 类小工具 | 只做文件化管理 | 无 diff、无回归、无 CI 门禁 |

一句话定位:**"git for your prompts"** —— 不是观测你的调用,而是管你的 prompt 的**变更**。

---

### 6. 变现路径

1. **开源 MIT(MVP 起)**:核心全开源,靠传播获客。
2. **Promptctl Pro($8/月 或 $79/年)**:
   - 团队共享评测数据集与历史基线(SaaS 同步)
   - 时间旅行回溯:跑"上周所有 prompt 版本 × 当前代码"的完整矩阵
   - 与 GitHub/GitLab深度集成:PR 自动评论、历史图表
   - 私有 registry:prompt 模板集中分发与权限
3. **Enterprise(后期)**:本地部署包、审计日志、合规导出。

> 关键:**开源工具 + 托管"历史与协作"** 是 CLI 类产品最健康的变现结构(类似 `git` → GitHub)。

---

### 7. 分发与增长(独立开发者最该花时间的部分)

- **PR 即销售**:集成 GitHub Action,用户在 PR 里看到输出 → 直接引流入 README。
- **内容 SEO**:写 "How to regression test your LLM prompts"、"Why I stopped hardcoding system prompts" 等实战文,引流到 GitHub。
- **生态位**:发布 `promptctl` 的 Homebrew tap、做成 GitHub Action、以及给热门 AI 框架写20行的集成。
- **冷启动数据**:自建一个公开的 "prompt benchmark" 仓库,用户可直接 `promptctl eval --dataset popular/` 跑别人的 prompt 版本。

---

### 8. 风险与对冲

| 风险 | 对冲 |
|---|---|
| AI 热度回落 / 平台自带工具(Vercel AI SDK 等)吃掉功能 | 定位"变更管理"而非"评测",与框架正交;优先支持任意 LLM 的 prompt,不绑定某框架 |
| 抽取器维护成本高(语言多、语法杂) | MVP 只支持 2 种语言,把 AST 抽取规则做成可插拔,社区贡献 |
| 免费替代品(几十行脚本) | 竞争点在于**长期历史 +团队协作 + 报告质量**,脚本无法积累 |
| 靠 AI 标签获客,留存不稳 | 加入与模型无关的通用价值:模板版本、成本预算门禁 |

---

### 9. 里程碑与验证指标

- **第 1 周**:手写抽取器,能把自己项目里的 prompt 全抽出来 → 这是"啊哈时刻"。
- **第 3 周**:`eval --against` 跑通,能给出 pass@1 / 成本对比。
- **第 5 周**:GitHub Action + `review` 报告,找一个朋友的项目接入。
- **第 6 周**:发布到 Homebrew,目标 **200 GitHub stars / 30 日活仓库**。

**验证成功的标准(不是 stars)**:有人愿意为"团队共享基线 + 历史回溯"付 $8/月。如果30 个仓库在用但 0 人付费,说明定位偏了,应转向团队协作或换场景。

---

**为什么这个适合独立开发者**:单语言、单二进制、数据全在用户本地(无需处理隐私合规)、无需部署后端、靠开源分发、用一个痛点(改 prompt 怕炸)切入,而且用户本身就是技术人——口碑传播效率最高。

# [rerun:space-bunny-free] 任务3 CLI工具Idea | 条件: baseline | 第 7 次

**Prompt:** 给出适合独立开发者开发CLI工具的一个Idea

**耗时:** 18.1s | **tokens:** 198/2022(推理 455) | **finish:** stop

---

# Idea：Config Doctor —— 「环境变量与配置一致性」审计 CLI

一句话：**一条命令扫描你的项目，找出 `.env`、代码、Dockerfile、CI、k8s 之间的配置漂移、幽灵变量和明文密钥泄漏。**

```bash
$ config-doctor
Scanning ./my-saas … (128 files, 3 manifests)

✖ 2 errors ⚠ 5 warnings   ✓ 47 checked

ERROR  .env.production contains SECRET_STRIPE_KEY referenced nowhere
ERROR  STRIPE_KEY is read in src/billing.ts but missing in CI (github/workflows/deploy.yml)
WARN   PORT is defined in docker-compose.yml but unused → dead config
WARN   .env.example is6 commits behind .env → docs drift
WARN   hardcoded token detected: src/api/client.ts:42 (ak_live_…)
 ↳ see fix suggestion, or run `config-doctor --redact`

$ config-doctor --fix          # 同步 .env.example、补 CI 变量、生成 .env.template
$ config-doctor --watch        # pre-commit hook 模式，毫秒级增量扫描
$ config-doctor --baseline ci.json   # 团队共享基线，只报新增问题
```

## 为什么这个方向适合独立开发者

**1. 痛点真实且高频。** 几乎每个团队都经历过「本地跑得好好的，一上 CI 就 `undefined is not a function`」。这个问题隐蔽、可复现成本高、排查耗时，属于典型的「用户自己不知道需要，但一用就离不开」。

**2. 范围小、能一个人在3~4 周内做出80 分产品。** 不需要 LLM、不需要网络依赖、不需要庞大的规则库。核心就是一个解析器 + 引用关系图 + 规则集。

**3. 天然「先本地、后团队」的 SaaS 化路径。** 单机版免费开源，进阶能力（团队基线、PR 评论机器人、历史泄漏追踪）收费，路径清晰。

## 核心功能（MVP优先级）

| 优先级 | 能力 | 实现要点 |
|---|---|---|
| P0 | 跨源变量抽取与图谱对齐 | `.env*` / `docker-compose` / k8s yaml / `process.env.X` / `os.environ["X"]` / `import.meta.env` / `Deno.env` / `vi.mock` / `getenv()` |
| P0 | 5 类规则：missing / unused / duplicate / typo 疑似 / hardcoded secret | 规则用 YAML 声明，用户可自己加，这是扩展性的关键 |
| P0 | 密钥泄漏检测 | entropy + 前缀规则（`sk_live_`、`ghp_`、`AKIA`）+ 允许列表，`--redact` 默认脱敏输出 |
| P1 | `--fix` 自动修复 | 生成 `.env.example`、补 CI 变量、PR 死配置注释 |
| P1 | Git hook / GitHub Action | 命中率靠这个，不靠用户主动 `run` |
| P2 | `history scan` | 检测历史提交里的已删密钥，输出 rotate 清单 |
| P2 | 团队基线与 PR Bot 评论 | 付费点 |

## 技术选型

- **Go 或 Rust** 做单二进制。独立开发者最大的优势就是「`brew install` / `npm i -g` 零依赖、零 runtime 报错」，这比写 Node 工具更有说服力。
- 用 **tree-sitter** 做多语言提取（避免正则的脆弱），tree-sitter 的 CLI/Node/Python/Go 绑定都有。
- 发布走 brew core + npm + GitHub Releases + pip（包装一层）。
- 规则集放仓库里当「内容产品」，这是后续涨粉和 star 的抓手。

## 差异化（避免和 linter 撞车）

- 对比 ESLint、pre-commit、Semgrep：它们是**通用质量工具，配置漂移是它们的盲区**。你只做一件事，所以能做得更深（跨文件、跨 manifest、跨环境）。
- 对比 Doppler / Infisical /1Password：它们是**密钥存储与注入方案**（需要改架构、付费、要迁移）。你是**只读的审计层，不要求你换掉现有方案**——「零侵入」是最强的销售话术。
- 对比 Terraform plan：漂移检测在 IaC 领域已成熟，但**应用层配置漂移没人认真做**。

## 分发与增长

1. **PR 体验即产品**：GitHub Action 在 PR 里留一行评论，链接到文档。这是自然增长飞轮。
2. **内容营销 SEO**：写「env variable best practices」「why my .env broke in production」「how to find hardcoded secrets」等长尾词，技术类长尾流量稳定且转化好。
3. **反向输出「报告」**：一条命令生成可分享的 HTML 报告（脱敏），用户为了分享报告而带来源链接。
4. **开源核心 + 闭源团队层**：规则集和扫描器 MIT，基线同步、历史泄漏扫描、SSO 收费。

## 商业模式

- **Free / 开源**：本地全功能，无限制。
- **Pro $9-15 开发者/月**：团队基线、PR Bot、Slack通知、历史泄漏扫描、多仓库。
- **Self-hosted Team $99-299/年**：合规场景（金融、医疗）对审计日志有刚需。
- **可选**：企业版接 SAST/SCA 供应链，当作 DevSecOps 工具链的一环卖。

## 4 周路线图

- **W1**：`.env` + `process.env` 双向对齐，missing/unused 两条规则，跨平台单二进制，README + demo GIF。
- **W2**：接入 YAML/JSON/docker-compose/k8s，密钥检测，`--fix`（先只做生成 `.env.example`）。
- **W3**：GitHub Action + PR 评论，pre-commit 模式，规则 YAML 化。
- **W4**：20 个真实开源仓库 dogfooding，修 bug；写 5 篇 SEO 稿；投 Product Hunt / Hacker News（Show HN 讲「我扫了 100 个热门仓库，发现 40% 有配置漂移」这类数据，正适合 HN）。

## 风险与规避

- **风险：被大厂顺手做了。** 规避点是「极窄 + 零侵入 + 可扩展规则」，并尽早占据 npm/brew 命名与 SEO。
- **风险：误报导致口碑崩。** 必须有 `--baseline`、每条 warning 带「为什么」和「如何忽略」的注释生成器，默认宁漏勿误。
- **风险：一次性工具，留存低。** 扩展成常驻 CI 步骤 + 团队协作功能，这才是留存来源。

---

**几个备选方向**（如果你更想要别的技术口味）：

1. **`har2cli`**：把浏览器 DevTools 导出的 HAR 或 `curl -v` 输出，逆向生成可复现的 CLI 命令 + 集成测试脚本。技术趣味强，演示效果炸裂。
2. **`docdrift`**：扫描 README/文档里的代码块，自动在 CI 里跑，验证文档没过期（本质是「文档的 CI」，定位清晰）。
3. **`coldstart`**：在 CI 失败时自动二分定位「哪个 commit/哪个环境变量/哪个依赖版本」引入了故障，输出最小复现命令。

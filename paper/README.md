# 论文：先写 200 组词对能提升回答质量吗？

本目录是一篇中文学术论文及其全部复算材料，研究对象是本仓库（原分支 `v2-deepseek`、
提交 `88e0b9a`，该分支已并入 `main`）
中的 **240 对盲评数据**：6 个开放式任务 × 2 个条件（`baseline` / `word_pairs`）× 10 次重复
× 2 个生成模型（`deepseek-flash`、`deepseek-v4-pro`）× 2 个评委。

论文对仓库原本的结论（“词对提示显著降低质量”）做了独立复算，并给出机制解释：
**词对条件把输出预算从答案挪到了词对清单上**，正文被压缩到对照的 46%–73%，
评委据此给出低分；控制长度后，条件效应从 −1.72 收窄到 −0.82。

## 文件

| 路径 | 说明 |
|---|---|
| `paper.pdf` | 成稿，15 页，XeLaTeX 编译 |
| `paper.tex` | 源码（ctex 文档类，A4 11pt） |
| `figs/` | 4 幅矢量图（PDF，matplotlib 生成） |
| `scripts/01_analyze.py` | 复算：胜负、五维、长度分层、聚类 bootstrap、回归、v1 跨代复现 |
| `scripts/02_features.py` | 文本特征、评审理由词频、评委宽严、v1 对照 |
| `scripts/03_figures.py` | 生成 `figs/` 下的 4 幅图 |
| `out/results.json` | 全部统计量（论文数字的唯一来源） |
| `out/pairs.csv` | 240 对逐条数据（长度、五维分数、分差） |
| `out/features.json` | 特征相关、回归系数、理由词频 |

## 编译

```bash
xelatex paper.tex
xelatex paper.tex      # 第二遍生成交叉引用
```

需要含 `ctex`、`xecjk`、`fandol`、`booktabs`、`multirow`、`tikz`、`placeins` 的 TeX Live。
字体使用 TeX Live 自带的 Fandol，无需额外安装系统中文字体。

## 复算

```bash
export JKDSFN_REPO="$(git rev-parse --show-toplevel)"   # 指向本仓库根目录
python3 scripts/01_analyze.py    # -> out/results.json, out/pairs.csv
python3 scripts/02_features.py   # -> out/features.json
python3 scripts/03_figures.py    # -> figs/*.pdf
```

依赖 `numpy`、`scipy`、`matplotlib`（Python 3.11 测试通过）。脚本默认从自身位置向上查找
包含 `llm_experiment_results_v2/` 的目录作为仓库根，因此在本仓库内无需设置 `JKDSFN_REPO`；
若把脚本移出仓库，再用该环境变量指定路径。

## 主要结论

| 结论 | 数值 |
|---|---|
| 直接回答压倒性胜出 | 224/240（93.3%），任务聚类 bootstrap 95% CI [86.7%, 97.1%] |
| 只有原创性略升 | +0.31；可操作性 −2.32、具体性 −2.08、逻辑性 −1.54、整体 −1.72 |
| 长度是主要通道 | 长度比与分差 Spearman ρ=0.585；长度比 ≥0.9 的子集胜率降至 67.9% |
| 等长处的条件效应 | −0.82（95% CI [−1.38, −0.26]），约为原始差距的 48% |
| 预算是翻倍的 | 输出 token 2.02×（flash）与 1.60×（pro），正文却只有 73% 与 46% |
| “灵感”基本没兑现 | 词对词元原样进入正文的比例仅 16.9% 与 15.1% |
| 跨代复现 | v1（kimi-k3）49:10:1，长度比 0.84，胜率 81.7% |

完整讨论（含 6 条效度威胁与三项设计修正）见 `paper.pdf` 第 5–6 节。

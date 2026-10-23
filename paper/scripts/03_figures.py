# -*- coding: utf-8 -*-
"""生成论文图（PDF 矢量 + PNG 预览）。"""
import json, pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FIG = ROOT / "figs"
FIG.mkdir(exist_ok=True)
res = json.loads((OUT / "results.json").read_text())
feat = json.loads((OUT / "features.json").read_text())

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Noto Serif CJK SC"],
    "axes.unicode_minus": False,
    "mathtext.fontset": "stix",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9.5,
    "legend.fontsize": 8.2,
    "xtick.labelsize": 8.4,
    "ytick.labelsize": 8.4,
    "figure.dpi": 160,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.7,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.35,
})
C = {"base": "#2F4B7C", "clean": "#C85200", "neg": "#B03A2E", "pos": "#2E7D5B", "gray": "#7A7A7A"}

# ---------------- 图2：分任务胜负
by_task = res["by_task"]
tasks = list(by_task.values())
labels = [f"T{t['task_name']}" if False else f"{k} {t['task_name']}" for k, t in by_task.items()]
short = ["1 函数式语言", "2 提升 LLM", "3 CLI 工具", "4 新理论", "5 人格模型", "6 ML 架构"]
base = np.array([t["baseline"] for t in tasks])
clean = np.array([t["cleaned_word_pairs"] for t in tasks])
tie = np.array([t["tie"] for t in tasks])

fig, ax = plt.subplots(figsize=(6.2, 2.95))
y = np.arange(len(tasks))[::-1]
ax.barh(y, base, color=C["base"], height=0.62, label="baseline 胜")
ax.barh(y, clean, left=base, color=C["clean"], height=0.62, label="词对条件胜")
ax.barh(y, tie, left=base + clean, color="#CCCCCC", height=0.62, label="平局")
for yy, b, c, t in zip(y, base, clean, tie):
    ax.text(b / 2, yy, f"{b}", va="center", ha="center", color="white", fontsize=8.2)
    if c:
        ax.text(b + c / 2, yy, f"{c}", va="center", ha="center", color="white", fontsize=7.6)
ax.set_yticks(y)
ax.set_yticklabels(short)
ax.set_xlim(0, 40)
ax.set_xlabel("每任务 40 对盲评的胜负计数")
ax.legend(loc="upper center", bbox_to_anchor=(0.46, -0.30), ncol=3, frameon=False)
ax.grid(axis="x")
ax.set_axisbelow(True)
fig.savefig(FIG / "fig_wins_by_task.pdf")
fig.savefig(FIG / "fig_wins_by_task.png", dpi=200)
plt.close(fig)

# ---------------- 图3：长度比 vs Δoverall
import csv
rows = list(csv.DictReader(open(OUT / "pairs.csv", encoding="utf-8")))
ratio = np.array([float(r["ratio"]) for r in rows])
dl = np.array([float(r["d_overall"]) for r in rows])
gen = np.array([r["gen"] for r in rows])

fig, ax = plt.subplots(figsize=(6.2, 3.05))
jx = ratio + np.random.default_rng(7).normal(0, 0.008, len(ratio))
jy = dl + np.random.default_rng(8).normal(0, 0.05, len(dl))
for g, m, mk in [("deepseek-flash", "o", "s"), ("deepseek-v4-pro", "^", "^")]:
    mm = gen == g
    ax.scatter(jx[mm], jy[mm], s=11, alpha=0.45, marker=mk, edgecolors="none",
               color=C["base"] if g.endswith("flash") else C["clean"],
               label=f"生成模型：{g}")
# 分箱均值
edges = np.array([0.25, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.3])
cent, means, errs = [], [], []
for a, b in zip(edges[:-1], edges[1:]):
    m = (ratio >= a) & (ratio < b)
    if m.sum() >= 5:
        cent.append((a + b) / 2); means.append(dl[m].mean())
        errs.append(1.96 * dl[m].std(ddof=1) / np.sqrt(m.sum()))
ax.errorbar(cent, means, yerr=errs, color="#1A1A1A", marker="D", ms=3.4, lw=1.1,
            capsize=2, label="分箱均值（95% CI）", zorder=5)
slope, icpt = np.polyfit(np.log(ratio), dl, 1)
xs = np.linspace(ratio.min(), ratio.max(), 100)
ax.plot(xs, icpt + slope * np.log(xs), ls="--", lw=1.0, color="#1A1A1A", alpha=0.7,
        label=f"OLS：$\\Delta$={icpt:.2f}+{slope:.2f}$\\ln$(长度比)")
ax.axhline(0, color=C["gray"], lw=0.6)
ax.axvline(1, color=C["gray"], lw=0.6, ls=":")
ax.set_xlabel("长度比（词对条件 / baseline，评委所见字符数）")
ax.set_ylabel("整体质量差 $\\Delta$（词对条件 − baseline）")
ax.set_ylim(-5.4, 2.4)
ax.legend(loc="lower right", frameon=False)
ax.grid()
fig.savefig(FIG / "fig_len_score.pdf")
fig.savefig(FIG / "fig_len_score.png", dpi=200)
plt.close(fig)

# ---------------- 图4：五维 + 预算重分配
fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6), gridspec_kw={"width_ratios": [1.25, 1]})
ax = axes[0]
dims = ["overall", "actionability", "concreteness", "logic", "originality"]
cn = {"overall": "整体", "actionability": "可操作", "concreteness": "具体",
      "logic": "逻辑", "originality": "原创"}
d = [res["dims"][k]["diff"] for k in dims]
cols = [C["pos"] if v > 0 else C["neg"] for v in d]
yy = np.arange(len(dims))[::-1]
ax.barh(yy, d, color=cols, height=0.6)
for y_, v in zip(yy, d):
    ax.text(v + (0.06 if v > 0 else -0.06), y_, f"{v:+.2f}", va="center",
            ha="left" if v > 0 else "right", fontsize=7.8)
ax.set_yticks(yy); ax.set_yticklabels([cn[k] for k in dims])
ax.axvline(0, color="k", lw=0.6)
ax.set_xlim(-3.0, 1.2)
ax.set_xlabel("$\\Delta$ 评分（词对 $-$ baseline）")
ax.set_title("(a) 五个评分维度", loc="left")
ax.grid(axis="x")

ax = axes[1]
mech = res["mech"]["gen"]
gg = ["deepseek-flash", "deepseek-v4-pro"]
xb = np.arange(2)
w = 0.34
tok_b = [mech[g]["base_completion_mean"] for g in gg]
tok_w = [mech[g]["wp_completion_mean"] for g in gg]
ax.bar(xb - w / 2, tok_b, w, color=C["base"], label="baseline")
ax.bar(xb + w / 2, tok_w, w, color=C["clean"], label="词对条件")
for x_, v in zip(xb - w / 2, tok_b):
    ax.text(x_, v + 180, f"{v/1000:.1f}k", ha="center", fontsize=7.2)
for x_, v in zip(xb + w / 2, tok_w):
    ax.text(x_, v + 180, f"{v/1000:.1f}k", ha="center", fontsize=7.2)
ax.set_xticks(xb); ax.set_xticklabels(["deepseek-\nflash", "deepseek-\nv4-pro"])
ax.set_ylabel("平均输出 token 数")
ax.set_ylim(0, 13400)
ax.set_title("(b) 输出预算", loc="left")
ax.legend(frameon=False, loc="upper left", borderaxespad=0.1)
ax.grid(axis="y")
fig.tight_layout(w_pad=1.6)
fig.savefig(FIG / "fig_dims_budget.pdf")
fig.savefig(FIG / "fig_dims_budget.png", dpi=200)
plt.close(fig)

# ---------------- 图5：评分分布
sd = res["score_dist"]
fig, ax = plt.subplots(figsize=(3.3, 2.0))
ax.bar(sd["values"], sd["counts"], color=C["base"], width=0.72)
for v, c in zip(sd["values"], sd["counts"]):
    ax.text(v, c + 4, str(c), ha="center", fontsize=7)
ax.set_xlabel("整体质量评分")
ax.set_ylabel("计数")
ax.set_ylim(0, 250)
ax.grid(axis="y")
fig.savefig(FIG / "fig_score_dist.pdf")
fig.savefig(FIG / "fig_score_dist.png", dpi=200)
plt.close(fig)

print("figs written:", sorted(p.name for p in FIG.glob("*.pdf")))

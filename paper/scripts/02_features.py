# -*- coding: utf-8 -*-
"""文本特征、评审理由、v1 复现、评委自偏好等补充分析。"""
import json, re, pathlib
import numpy as np
from scipy import stats

import os
def _find_repo():
    env = os.environ.get("JKDSFN_REPO")
    if env:
        return pathlib.Path(env).expanduser().resolve()
    here = pathlib.Path(__file__).resolve()
    for p in here.parents:
        if (p / "llm_experiment_results_v2").is_dir():
            return p
    return pathlib.Path.cwd()

REPO = _find_repo()
V2 = REPO / "llm_experiment_results_v2"
OUT = pathlib.Path(__file__).resolve().parents[1] / "out"
DIMS = ["logic", "concreteness", "actionability", "originality", "overall"]
GENS = ["deepseek-flash", "deepseek-v4-pro"]
JUDGES = GENS


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


recs = []
for gen in GENS:
    for judge in JUDGES:
        for r in load(V2 / gen / f"comparison__{judge}.jsonl"):
            recs.append(r | {"gen": gen, "judge": judge})

FEATS = {
    "chars": lambda t: len(t),
    "cjk": lambda t: len(re.findall(r"[\u4e00-\u9fff]", t)),
    "headings": lambda t: len(re.findall(r"^\s*#{1,6}\s", t, re.M)),
    "bullets": lambda t: len(re.findall(r"^\s*[-*+•]\s", t, re.M)),
    "nums": lambda t: len(re.findall(r"^\s*\d+[.)、]\s", t, re.M)),
    "digits": lambda t: len(re.findall(r"\d", t)),
    "blocks": lambda t: len([b for b in re.split(r"\n\s*\n", t) if b.strip()]),
    "code": lambda t: t.count("```") // 2,
    "colons": lambda t: t.count("：") + t.count(":"),
    "bold": lambda t: len(re.findall(r"\*\*[^*]+\*\*", t)),
}

rows = []
for r in recs:
    b, c = r["baseline_content"] or "", r["cleaned_content"] or ""
    d = {}
    for k, f in FEATS.items():
        d[f"b_{k}"] = f(b)
        d[f"c_{k}"] = f(c)
        d[f"d_{k}"] = f(c) - f(b)
    rows.append({
        "cell": f"{r['gen']}|{r['judge']}", "gen": r["gen"], "judge": r["judge"],
        "task": int(r["task_id"]), "run": int(r["run"]),
        **d,
        **{f"d_{x}": (r["B_scores"][x] - r["A_scores"][x]) * (1 if r["A_source"] == "baseline" else -1) for x in DIMS},
    })

res = {}
# 1. 特征均值：两条件
res["feat_means"] = {}
for k in FEATS:
    res["feat_means"][k] = {
        "baseline": float(np.mean([x[f"b_{k}"] for x in rows])),
        "cleaned": float(np.mean([x[f"c_{k}"] for x in rows])),
        "diff": float(np.mean([x[f"d_{k}"] for x in rows])),
    }

# 2. 各文本特征差 与 Δoverall 的相关
res["feat_corr"] = {}
for k in FEATS:
    x = np.array([t[f"d_{k}"] for t in rows]); y = np.array([t["d_overall"] for t in rows])
    rho, p = stats.spearmanr(x, y)
    res["feat_corr"][k] = {"spearman": float(rho), "p": float(p)}

# 3. 特征对 Δoverall 的多元回归（标准化，任务聚类稳健 SE）
ks = ["d_chars", "d_headings", "d_bullets", "d_digits", "d_code"]
X = np.column_stack([[t[k] for t in rows] for k in ks])
X = (X - X.mean(0)) / X.std(0, ddof=1)
y = np.array([t["d_overall"] for t in rows])
tasks = np.array([t["task"] for t in rows])
D = np.column_stack([(tasks == t).astype(float) for t in range(2, 7)])
XX = np.column_stack([np.ones(len(y)), X, D])


def ols_cluster(y, X, groups):
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        m = groups == g
        s = X[m].T @ e[m]
        meat += np.outer(s, s)
    n, k = X.shape; G = len(np.unique(groups))
    V = (G / (G - 1)) * ((n - 1) / (n - k)) * XtX_inv @ meat @ XtX_inv
    return beta, np.sqrt(np.diag(V))


beta, se = ols_cluster(y, XX, tasks)
res["feat_reg"] = {k: {"beta": float(beta[i + 1]), "se": float(se[i + 1]),
                       "t": float(beta[i + 1] / se[i + 1])} for i, k in enumerate(ks)}
res["feat_reg_r2"] = float(1 - ((y - XX @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum())

# 4. 评审理由关键词
reasons = [r["reason"] or "" for r in recs]
KW = ["结构", "具体", "可操作", "细节", "完整", "清晰", "逻辑", "原创", "创新", "深度",
      "篇幅", "简洁", "冗长", "重复", "例子", "落地", "抽象", "空泛", "系统", "可检验"]
res["reason_kw"] = {k: {"n": int(sum(k in t for t in reasons)), "pct": float(np.mean([k in t for t in reasons]))}
                    for k in KW}
res["reason_len"] = {"mean": float(np.mean([len(t) for t in reasons]))}

# 5. 评委打分水平（自偏好检查）
res["judge_level"] = {}
for j in JUDGES:
    for g in GENS:
        rs = [r for r in recs if r["judge"] == j and r["gen"] == g]
        allsc = [r[p][k] for r in rs for p in ("A_scores", "B_scores") for k in DIMS]
        res["judge_level"][f"{j}|{g}"] = float(np.mean(allsc))

# 6. v1 复现：长度效应是否可复制
v1 = load(REPO / "comparison.jsonl")
latest = {}
for x in v1:
    if x.get("winner_label") and x.get("A_scores") and x.get("B_scores"):
        latest[(x["task_id"], x["run"])] = x
rr = []
for (t, run), x in latest.items():
    lb, lc = len(x["baseline_content"] or ""), len(x["cleaned_content"] or "")
    if not lb:
        continue
    d = (x["B_scores"]["overall"] - x["A_scores"]["overall"]) * (1 if x["A_source"] == "baseline" else -1)
    rr.append({"task": t, "run": run, "lb": lb, "lc": lc, "ratio": lc / lb, "d_overall": d,
               "winner": x["winner_label"],
               "d_orig": (x["B_scores"]["originality"] - x["A_scores"]["originality"]) * (1 if x["A_source"] == "baseline" else -1)})
res["v1"] = {
    "n": len(rr),
    "lb_mean": float(np.mean([r["lb"] for r in rr])),
    "lc_mean": float(np.mean([r["lc"] for r in rr])),
    "ratio_mean": float(np.mean([r["ratio"] for r in rr])),
    "spearman": float(stats.spearmanr([r["ratio"] for r in rr], [r["d_overall"] for r in rr])[0]),
    "d_overall": float(np.mean([r["d_overall"] for r in rr])),
    "d_orig": float(np.mean([r["d_orig"] for r in rr])),
    "wr_base": float(np.mean([r["winner"] == "baseline" for r in rr])),
    "long_subset": None,
}
long = [r for r in rr if r["ratio"] >= 0.9]
if long:
    res["v1"]["long_subset"] = {"n": len(long), "wr": float(np.mean([r["winner"] == "baseline" for r in long])),
                                "d": float(np.mean([r["d_overall"] for r in long]))}

# 7. 每格 Spearman
res["cell_corr"] = {}
for cell in sorted({r["cell"] for r in rows}):
    rs = [r for r in rows if r["cell"] == cell]
    res["cell_corr"][cell] = float(stats.spearmanr([r["d_chars"] for r in rs], [r["d_overall"] for r in rs])[0])

# 8. 质量-成本：每个条件的总 token 与均分
cost = {}
for g in GENS:
    rs = load(V2 / g / "results.jsonl")
    for cond in ["baseline", "word_pairs"]:
        sub = [r for r in rs if r["condition"] == cond]
        cost[f"{g}|{cond}"] = {"tokens": int(sum(r["completion_tokens"] for r in sub)),
                               "mean_tokens": float(np.mean([r["completion_tokens"] for r in sub]))}
res["cost"] = cost

(OUT / "features.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(res["feat_means"], ensure_ascii=False, indent=1))
print("corr:", json.dumps({k: round(v["spearman"], 3) for k, v in res["feat_corr"].items()}, ensure_ascii=False))
print("reg:", json.dumps(res["feat_reg"], ensure_ascii=False), "R2=%.3f" % res["feat_reg_r2"])
print("kw:", json.dumps({k: v["n"] for k, v in res["reason_kw"].items()}, ensure_ascii=False))
print("judge_level:", json.dumps(res["judge_level"], ensure_ascii=False))
print("v1:", json.dumps(res["v1"], ensure_ascii=False))
print("cell_corr:", json.dumps({k: round(v, 3) for k, v in res["cell_corr"].items()}, ensure_ascii=False))
print("cost:", json.dumps(res["cost"], ensure_ascii=False))

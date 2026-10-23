# -*- coding: utf-8 -*-
"""独立复算 jkdsfn 仓库 v1/v2 实验的全部论文数字。"""
import json, re, pathlib, sys
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
OUT.mkdir(exist_ok=True)

DIMS = ["logic", "concreteness", "actionability", "originality", "overall"]
GENS = ["deepseek-flash", "deepseek-v4-pro"]
JUDGES = ["deepseek-flash", "deepseek-v4-pro"]
RNG = np.random.default_rng(20261023)


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- v2 盲评
recs = []
for gen in GENS:
    for judge in JUDGES:
        for r in load(V2 / gen / f"comparison__{judge}.jsonl"):
            if not (r.get("A_scores") and r.get("B_scores")):
                continue
            if r["A_source"] == "baseline":
                sb, sc = r["A_scores"], r["B_scores"]
            else:
                sb, sc = r["B_scores"], r["A_scores"]
            d = {f"d_{k}": sc[k] - sb[k] for k in DIMS}
            rec = dict(
                cell=f"{gen}|{judge}", gen=gen, judge=judge,
                task_id=int(r["task_id"]), task_name=r["task_name"], run=int(r["run"]),
                swap=bool(r["swap"]), a_source=r["A_source"],
                winner=r["winner_label"],
                lb=len(r["baseline_content"] or ""), lc=len(r["cleaned_content"] or ""),
                **{f"b_{k}": sb[k] for k in DIMS}, **{f"c_{k}": sc[k] for k in DIMS}, **d,
            )
            rec["ratio"] = rec["lc"] / rec["lb"] if rec["lb"] else np.nan
            rec["dl"] = rec["lc"] - rec["lb"]
            recs.append(rec)

N = len(recs)
assert N == 240, N
res = {"N": N}

# 1. 总体与分格胜负
def win_counts(rs):
    c = {"baseline": 0, "cleaned_word_pairs": 0, "tie": 0}
    for r in rs:
        c[r["winner"]] += 1
    return c

res["overall_wins"] = win_counts(recs)
res["cells"] = {}
for cell in sorted({r["cell"] for r in recs}):
    rs = [r for r in recs if r["cell"] == cell]
    w = win_counts(rs)
    res["cells"][cell] = {
        "n": len(rs), "wins": w,
        "win_rate_base": w["baseline"] / len(rs),
        "d_overall": float(np.mean([r["d_overall"] for r in rs])),
        "dims": {k: float(np.mean([r[f"d_{k}"] for r in rs])) for k in DIMS},
    }

# 2. 五维均值（条件别，合并 240 对）
res["dims"] = {}
for k in DIMS:
    b = np.mean([r[f"b_{k}"] for r in recs])
    c = np.mean([r[f"c_{k}"] for r in recs])
    d = np.array([r[f"d_{k}"] for r in recs])
    res["dims"][k] = {
        "baseline": float(b), "cleaned": float(c), "diff": float(c - b),
        "sd_diff": float(d.std(ddof=1)),
        "cohens_dz": float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) else None,
    }
# 分生成模型
res["dims_by_gen"] = {}
for g in GENS:
    rs = [r for r in recs if r["gen"] == g]
    res["dims_by_gen"][g] = {k: {
        "baseline": float(np.mean([r[f"b_{k}"] for r in rs])),
        "cleaned": float(np.mean([r[f"c_{k}"] for r in rs])),
        "diff": float(np.mean([r[f"d_{k}"] for r in rs])),
    } for k in DIMS}

# 3. 长度
res["length"] = {}
for g in GENS:
    rs = [r for r in recs if r["gen"] == g]
    res["length"][g] = {
        "lb_mean": float(np.mean([r["lb"] for r in rs])),
        "lc_mean": float(np.mean([r["lc"] for r in rs])),
        "ratio_mean": float(np.mean([r["ratio"] for r in rs])),
        "ratio_median": float(np.median([r["ratio"] for r in rs])),
        "pc_clean_longer": float(np.mean([r["ratio"] > 1 for r in rs])),
    }
res["length"]["all"] = {
    "lb_mean": float(np.mean([r["lb"] for r in recs])),
    "lc_mean": float(np.mean([r["lc"] for r in recs])),
    "ratio_mean": float(np.mean([r["ratio"] for r in recs])),
    "ratio_median": float(np.median([r["ratio"] for r in recs])),
}

# 4. 长度差 vs 分数差
res["corr"] = {}
for g in GENS + ["all"]:
    rs = recs if g == "all" else [r for r in recs if r["gen"] == g]
    x = np.array([r["ratio"] for r in rs]); y = np.array([r["d_overall"] for r in rs])
    rho, p = stats.spearmanr(x, y)
    r_p, p_p = stats.pearsonr(x, y)
    res["corr"][g] = {"spearman_ratio_doverall": float(rho), "p": float(p),
                      "pearson": float(r_p), "p_pearson": float(p_p), "n": len(rs)}

# 5. 长度分层
bins = [(0, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 1.2), (1.2, 99)]
res["strata"] = []
for lo, hi in bins:
    rs = [r for r in recs if lo <= r["ratio"] < hi]
    w = win_counts(rs)
    res["strata"].append({
        "lo": lo, "hi": hi, "n": len(rs), **{f"w_{k}": v for k, v in w.items()},
        "d_overall": float(np.mean([r["d_overall"] for r in rs])) if rs else None,
        "wr": w["baseline"] / len(rs) if rs else None,
    })

# 6. 子集
def subset_stats(rs, name):
    w = win_counts(rs)
    return {"name": name, "n": len(rs), **w,
            "wr": w["baseline"] / len(rs) if rs else None,
            "d_overall": float(np.mean([r["d_overall"] for r in rs])) if rs else None,
            "d_orig": float(np.mean([r["d_originality"] for r in rs])) if rs else None}
res["subsets"] = [
    subset_stats([r for r in recs if r["ratio"] >= 0.9], "ratio>=0.9"),
    subset_stats([r for r in recs if r["ratio"] >= 1.0], "ratio>=1.0"),
    subset_stats([r for r in recs if abs(r["ratio"] - 1) <= 0.15], "|ratio-1|<=0.15"),
    subset_stats([r for r in recs if abs(r["ratio"] - 1) <= 0.30], "|ratio-1|<=0.30"),
]

# 7. 分任务
res["by_task"] = {}
for t in range(1, 7):
    rs = [r for r in recs if r["task_id"] == t]
    w = win_counts(rs)
    res["by_task"][str(t)] = {
        "task_name": rs[0]["task_name"], "n": len(rs), **w,
        "wr": w["baseline"] / len(rs),
        "d_overall": float(np.mean([r["d_overall"] for r in rs])),
        "ratio": float(np.mean([r["ratio"] for r in rs])),
        "d_orig": float(np.mean([r["d_originality"] for r in rs])),
    }
res["sign_test"] = {"n_pos": int(sum(1 for t in res["by_task"].values() if t["d_overall"] > 0)), "n": 6,
                    "p_two_sided": float(stats.binomtest(int(sum(1 for t in res["by_task"].values() if t["d_overall"] > 0)), 6, 0.5).pvalue)}

# 8. 聚类 bootstrap（簇 = 6 个任务）
by_task = {t: [r for r in recs if r["task_id"] == t] for t in range(1, 7)}
B = 10000
boot_wr, boot_d = [], []
for _ in range(B):
    pick = RNG.choice(range(1, 7), size=6, replace=True)
    smp = [r for t in pick for r in by_task[t]]
    boot_wr.append(np.mean([r["winner"] == "baseline" for r in smp]))
    boot_d.append(np.mean([r["d_overall"] for r in smp]))
def ci(a):
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
res["cluster_boot"] = {"wr_mean": float(np.mean(boot_wr)), "wr_ci": ci(boot_wr),
                       "d_mean": float(np.mean(boot_d)), "d_ci": ci(boot_d), "B": B}

# 朴素二项（对比，说明其高估）
res["naive_binom"] = {"wins": res["overall_wins"]["baseline"], "n": N,
                      "p_two_sided": float(stats.binomtest(res["overall_wins"]["baseline"], N, 0.5).pvalue)}

# 9. 位置效应 2×2 分解
d1 = np.array([r["a_overall_b_minus"] for r in []]) if False else None
A_B_base = [r for r in recs if r["a_source"] == "baseline"]
A_B_clean = [r for r in recs if r["a_source"] != "baseline"]
# A-B 分差：A=baseline 时 A-B = baseline - cleaned；A=cleaned 时 A-B = cleaned - baseline
def ab_diff(r):
    return r["b_overall"] - r["c_overall"] if r["a_source"] == "baseline" else r["c_overall"] - r["b_overall"]
D1 = float(np.mean([ab_diff(r) for r in A_B_base]))
D2 = float(np.mean([ab_diff(r) for r in A_B_clean]))
res["position"] = {"n_A_baseline": len(A_B_base), "n_A_cleaned": len(A_B_clean),
                   "D1_AminusB_when_A_base": D1, "D2_AminusB_when_A_clean": D2,
                   "cond_effect": (D1 - D2) / 2, "pos_effect": (D1 + D2) / 2}

# 10. 评委一致性（同一 gen 的 60 对，两评委独立评分）
res["agreement"] = {}
for g in GENS:
    j1, j2 = JUDGES
    m1 = {(r["task_id"], r["run"]): r["winner"] for r in recs if r["gen"] == g and r["judge"] == j1}
    m2 = {(r["task_id"], r["run"]): r["winner"] for r in recs if r["gen"] == g and r["judge"] == j2}
    keys = sorted(set(m1) & set(m2))
    a = [m1[k] for k in keys]; b = [m2[k] for k in keys]
    agree = np.mean([x == y for x, y in zip(a, b)])
    lab = ["baseline", "cleaned_word_pairs", "tie"]
    M = np.zeros((3, 3))
    for x, y in zip(a, b):
        M[lab.index(x), lab.index(y)] += 1
    po = np.trace(M) / M.sum()
    pe = sum(M[i, :].sum() * M[:, i].sum() for i in range(3)) / M.sum() ** 2
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    # 二分类（tie 仍保留）
    res["agreement"][g] = {"n": len(keys), "agree": float(agree), "kappa3": float(kappa),
                           "matrix": M.astype(int).tolist(),
                           "j1_base_wins": sum(1 for x in a if x == "baseline"),
                           "j2_base_wins": sum(1 for x in b if x == "baseline")}

# 11. 评分分布/天花板
all_overall = [r[f"{p}_overall"] for r in recs for p in ("b", "c")]
vals, cnts = np.unique(all_overall, return_counts=True)
res["score_dist"] = {"values": vals.tolist(), "counts": cnts.tolist(),
                     "mean": float(np.mean(all_overall)), "sd": float(np.std(all_overall, ddof=1)),
                     "n_9": int(sum(1 for v in all_overall if v == 9)),
                     "n_10": int(sum(1 for v in all_overall if v == 10)),
                     "n_total": len(all_overall)}
# 每格总分的 sd（区分度）
res["score_sd_by_cell"] = {c: float(np.std([r[f"{p}_overall"] for r in recs if r["cell"] == c for p in ("b", "c")], ddof=1))
                           for c in sorted({r["cell"] for r in recs})}

# 12. 回归：Δoverall ~ log(ratio)，任务固定效应，任务聚类稳健 SE
def ols_cluster(y, X, groups):
    X = np.column_stack([np.ones(len(y)), X])
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        m = groups == g
        Xg, eg = X[m], e[m]
        s = Xg.T @ eg
        meat += np.outer(s, s)
    n, k = X.shape
    G = len(np.unique(groups))
    adj = (G / (G - 1)) * ((n - 1) / (n - k))
    V = adj * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    return beta, se

y = np.array([r["d_overall"] for r in recs])
x = np.log(np.array([r["ratio"] for r in recs]))
tasks = np.array([r["task_id"] for r in recs])
# 任务虚拟变量
D = np.column_stack([(tasks == t).astype(float) for t in range(2, 7)])
X = np.column_stack([x, D])
beta, se = ols_cluster(y, X, tasks)
res["reg"] = {"intercept": float(beta[0]), "se_intercept": float(se[0]),
              "slope_logratio": float(beta[1]), "se_slope": float(se[1]),
              "t_slope": float(beta[1] / se[1]),
              "p_slope": float(2 * (1 - stats.t.cdf(abs(beta[1] / se[1]), df=5))),
              "intercept_ci": [float(beta[0] - stats.t.ppf(0.975, 5) * se[0]),
                               float(beta[0] + stats.t.ppf(0.975, 5) * se[0])]}
# 仅截距模型（条件效应）
res["reg_null"] = {"mean_d": float(y.mean()), "se_cluster": float(np.std(y, ddof=1) / np.sqrt(len(y)) * np.sqrt(6 / 5))}

# 13. 机制：词对计数、正文长度、覆盖率、清洗保真度
def load_gen(gen, cond):
    return [r for r in load(V2 / gen / "results.jsonl") if r["condition"] == cond]

NUM = re.compile(r"(?:^|[\n；;])\s*(?:【\s*\d+\s*[-–~]\s*\d+\s*】)?\s*(\d{1,3})\s*[\.、\)．:：]?\s*[\u4e00-\u9fffA-Za-z]")
HEAD = re.compile(r"^\s*#{1,6}\s")
CJK = re.compile(r"[\u4e00-\u9fff]{2,4}")

def split_pair_body(content):
    lines = content.split("\n")
    body_idx = None
    for i, l in enumerate(lines):
        if i >= 3 and HEAD.match(l):
            body_idx = i
            break
    if body_idx is None:
        # 回退：第一行既无编号也不是短词对行
        for i, l in enumerate(lines):
            s = l.strip()
            if i >= 3 and s and not NUM.match("\n" + s) and not re.match(r"^\s*\d{1,3}\b", s) and len(s) > 25:
                body_idx = i
                break
    if body_idx is None:
        body_idx = len(lines)
    return "\n".join(lines[:body_idx]), "\n".join(lines[body_idx:])

mech = {"gen": {}, "coverage": {}}
tokens_by_gen = {}
for g in GENS:
    wps = load_gen(g, "word_pairs")
    bases = load_gen(g, "baseline")
    pcs, bodies, raws = [], [], []
    covs = []
    for r in wps:
        pair_text, body = split_pair_body(r["content"])
        nums = [int(m.group(1)) for m in NUM.finditer(pair_text)]
        pcs.append(max(nums) if nums else 0)
        bodies.append(len(body))
        raws.append(len(r["content"]))
        toks = set(CJK.findall(pair_text)) | set(re.findall(r"[A-Za-z]{3,}", pair_text))
        toks = {t for t in toks if len(t) >= 2}
        if toks:
            covs.append(np.mean([t in body for t in toks]))
        tokens_by_gen.setdefault(g, []).append((r["task_id"], r["run"], len(toks)))
    bl = [r["completion_tokens"] for r in bases]
    mech["gen"][g] = {
        "raw_len_mean": float(np.mean(raws)),
        "baseline_len_mean": float(np.mean([len(r["content"]) for r in bases])),
        "body_len_mean": float(np.mean(bodies)),
        "body_over_baseline": float(np.mean(bodies) / np.mean([len(r["content"]) for r in bases])),
        "pair_count_mean": float(np.mean(pcs)),
        "pair_count_min": int(np.min(pcs)),
        "pair_ge190": int(sum(1 for p in pcs if p >= 190)),
        "pair_eq0": int(sum(1 for p in pcs if p == 0)),
        "coverage_mean": float(np.mean(covs)),
        "coverage_median": float(np.median(covs)),
        "coverage_max": float(np.max(covs)),
        "wp_completion_mean": float(np.mean([r["completion_tokens"] for r in wps])),
        "base_completion_mean": float(np.mean(bl)),
        "n_at_8192": int(sum(1 for r in wps if r["completion_tokens"] >= 8192)),
        "n_base_at_8192": int(sum(1 for r in bases if r["completion_tokens"] >= 8192)),
    }

# 清洗保真度
cle = []
for g in GENS:
    cs = load(V2 / g / "cleaned.jsonl")
    orig = {(r["task_id"], r["run"]): r for r in load_gen(g, "word_pairs")}
    for r in cs:
        _, body = split_pair_body(orig[(r["task_id"], r["run"])]["content"])
        if body.strip():
            cle.append({"gen": g, "task": r["task_id"], "run": r["run"],
                        "body": len(body), "clean": len(r["cleaned_content"] or ""),
                        "ratio": len(r["cleaned_content"] or "") / len(body),
                        "residual": r.get("residual")})
cr = np.array([c["ratio"] for c in cle])
mech["clean_fidelity"] = {"n": len(cle), "mean": float(cr.mean()), "median": float(np.median(cr)),
                          "min": float(cr.min()), "p10": float(np.percentile(cr, 10)),
                          "n_lt_0.6": int((cr < 0.6).sum()),
                          "n_residual": int(sum(1 for c in cle if c["residual"])),
                          "worst": min(cle, key=lambda c: c["ratio"])}
res["mech"] = mech

# ---------------------------------------------------------------- v1 复现
v1 = {}
try:
    r1 = load(REPO / "comparison.jsonl")
    ok = [x for x in r1 if x.get("winner_label") and x.get("A_scores") and x.get("B_scores")]
    latest = {}
    for x in ok:
        latest[(x["task_id"], x["run"])] = x
    v1["n_raw"] = len(r1); v1["n_valid"] = len(latest)
    c = {"baseline": 0, "cleaned_word_pairs": 0, "tie": 0}
    dims = {k: {"b": [], "c": []} for k in DIMS}
    for x in latest.values():
        c[x["winner_label"]] += 1
        if x["A_source"] == "baseline":
            sb, sc = x["A_scores"], x["B_scores"]
        else:
            sb, sc = x["B_scores"], x["A_scores"]
        for k in DIMS:
            dims[k]["b"].append(sb[k]); dims[k]["c"].append(sc[k])
    v1["wins"] = c
    v1["dims"] = {k: {"baseline": float(np.mean(v["b"])), "cleaned": float(np.mean(v["c"])),
                      "diff": float(np.mean(v["c"]) - np.mean(v["b"]))} for k, v in dims.items()}
    v1["has_len"] = "baseline_content" in ok[0]
except Exception as e:
    v1["error"] = repr(e)
res["v1"] = v1

(OUT / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

# 逐对 CSV，供作图
import csv
with open(OUT / "pairs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
    w.writeheader(); w.writerows(recs)

print(json.dumps({k: res[k] for k in ["N", "overall_wins", "length", "corr", "subsets", "sign_test", "position"]}, ensure_ascii=False, indent=2))
print("\n--- cells ---")
for k, v in res["cells"].items():
    print(k, v["wins"], round(v["d_overall"], 3))
print("\n--- dims ---")
for k, v in res["dims"].items():
    print(k, round(v["baseline"], 2), round(v["cleaned"], 2), round(v["diff"], 2), "dz=%.2f" % v["cohens_dz"])
print("\n--- strata ---")
for s in res["strata"]:
    print(s)
print("\n--- reg ---", json.dumps(res["reg"], ensure_ascii=False))
print("--- cluster boot ---", json.dumps(res["cluster_boot"], ensure_ascii=False))
print("--- mech ---", json.dumps(mech, ensure_ascii=False, indent=1)[:1500])
print("--- v1 ---", json.dumps(v1, ensure_ascii=False)[:600])
print("--- score_dist ---", json.dumps(res["score_dist"], ensure_ascii=False))

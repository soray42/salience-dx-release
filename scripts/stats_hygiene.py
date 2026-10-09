#!/usr/bin/env python3
"""Multiple-comparison and pooling statistics (paper appendix "Statistical Methods").

(1) For each of the 20 cells (4 models, 5 cue types, 3 complexity levels, 4 non-English
    languages, 4 Gemma 4 sizes): exact binomial test of adoption flips (ISB) against rejection
    flips (vigilance), and Benjamini-Hochberg q across the 20 cells. The Gemma 4 31B size cell
    and the Gemma model cell hold the same pairs.
(2) DerSimonian-Laird random-effects meta-analysis of the per-model log odds ratio
    (ISB : vigilance): pooled OR, 95% CI, I^2.
(3) Direction trend across the four Gemma 4 sizes: share of flips that are adoption flips
    against size rank.

Usage: .venv/bin/python scripts/stats_hygiene.py
"""
import glob
import json
import math
import os
import sys
from collections import Counter
from math import comb, log, sqrt, exp
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C
import yaml

CX = {os.path.basename(f)[:-5]: yaml.safe_load(open(f)).get("complexity", "?")
      for f in glob.glob(str(REPO / "data/pilot/feature_curation/inputs_full500/*.yaml"))}


def binom(k, n, p=0.5):
    if n == 0:
        return 1.0
    pk = comb(n, k) * p ** k * (1 - p) ** (n - k)
    return min(1.0, sum(comb(n, i) * p ** i * (1 - p) ** (n - i)
                        for i in range(n + 1) if comb(n, i) * p ** i * (1 - p) ** (n - i) <= pk * 1.0000001))


def bh_fdr(items):
    """items: [(label, p)] -> [(label, p, q, survives)]"""
    m = len(items)
    order = sorted(range(m), key=lambda i: items[i][1])
    q = [0] * m
    prev = 1.0
    for rank, i in enumerate(reversed(order), start=1):
        idx = m - rank + 1
        val = items[i][1] * m / idx
        prev = min(prev, val)
        q[i] = prev
    return [(items[i][0], items[i][1], round(q[i], 4), q[i] < 0.05) for i in range(m)]


def cells_from(path, models, cx=False, seeds=None):
    recs, _ = C.load_judge_records(path)
    rows = C.build_pair_table(recs, models=models, seeds=seeds)
    out = {}
    # per model
    for m in models:
        c = Counter(r["bucket"] for r in rows if r["model"] == m and r["bucket"] != "missing")
        out[m] = (c["ISB"], c["vigilance"])
    if cx:
        for lv in ("low", "medium", "high"):
            c = Counter(r["bucket"] for r in rows if CX.get(r["seed_id"]) == lv and r["bucket"] != "missing")
            out[f"cx:{lv}"] = (c["ISB"], c["vigilance"])
        for t in ("T1", "T2", "T3", "T5", "T6"):
            c = Counter(r["bucket"] for r in rows if r["seed_id"].split("-")[0] == t and r["bucket"] != "missing")
            out[f"tmpl:{t}"] = (c["ISB"], c["vigilance"])
    return out


def dl_meta(strata):
    """DerSimonian-Laird random-effects meta of log-OR(ISB:vig). strata: [(label,(nISB,nVig))]."""
    ys, ws, labels = [], [], []
    for lab, (a, b) in strata:
        a2, b2 = a + 0.5, b + 0.5           # continuity vs a 50/50 null: OR = ISB/vig
        y = log(a2 / b2); v = 1 / a2 + 1 / b2
        ys.append(y); ws.append(1 / v); labels.append(lab)
    yf = sum(w * y for w, y in zip(ws, ys)) / sum(ws)
    Q = sum(w * (y - yf) ** 2 for w, y in zip(ws, ys))
    k = len(ys)
    C_ = sum(ws) - sum(w * w for w in ws) / sum(ws)
    tau2 = max(0.0, (Q - (k - 1)) / C_) if C_ > 0 else 0.0
    wr = [1 / (1 / w + tau2) for w in ws]
    yr = sum(w * y for w, y in zip(wr, ys)) / sum(wr)
    se = sqrt(1 / sum(wr))
    I2 = max(0.0, (Q - (k - 1)) / Q) * 100 if Q > 0 else 0.0
    return {"pooled_OR": round(exp(yr), 3), "ci": [round(exp(yr - 1.96 * se), 3), round(exp(yr + 1.96 * se), 3)],
            "I2_pct": round(I2, 1), "Q": round(Q, 2), "k": k, "tau2": round(tau2, 3)}


def main():
    MAIN = ["claude-sonnet-4-6", "gemini-3.5-flash", "llama3.1:8b", "google/gemma-4-31B-it"]
    fam = []  # exploratory family: (label, p)

    # full-scale
    full = cells_from(REPO / "data/full/judge_deepseek_v31.ndjson", MAIN, cx=True)
    for lab, (a, b) in full.items():
        fam.append((f"full/{lab}", binom(a, a + b)))
    # multilingual
    for lang in ("zh", "ru", "ar", "es"):
        p = REPO / f"data/multilingual/{lang}/judge_deepseek_v31.ndjson"
        if p.exists():
            ml = cells_from(p, ["claude-sonnet-4-6", "gemini-3.5-flash", "google/gemma-4-31B-it"])
            a = sum(x[0] for x in ml.values()); b = sum(x[1] for x in ml.values())
            fam.append((f"ml/{lang}", binom(a, a + b)))
    # scaling
    scal = {"E4B": REPO / "data/scaling/judge_E4B_v31.ndjson", "12B": REPO / "data/scaling/judge_12B_v31.ndjson",
            "26B-A4B": REPO / "data/scaling/judge_26B-A4B_v31.ndjson", "31B": REPO / "data/full/judge_deepseek_v31.ndjson"}
    scal_counts = {}
    for tag, p in scal.items():
        mdl = "google/gemma-4-31B-it" if tag == "31B" else f"google/gemma-4-{tag}-it"
        c = cells_from(p, [mdl])[mdl]
        scal_counts[tag] = c
        fam.append((f"scale/{tag}", binom(c[0], c[0] + c[1])))

    print("=== (1) BH-FDR across the exploratory net-asymmetry family ===")
    res = bh_fdr(fam)
    print(f"{'cell':22} {'nISB/nVig':>10} {'raw_p':>7} {'q':>7} survives")
    counts_lookup = {**{f"full/{k}": v for k, v in full.items()},
                     **{f"scale/{k}": v for k, v in scal_counts.items()}}
    for lab, p, q, sv in sorted(res, key=lambda x: x[1]):
        cc = counts_lookup.get(lab)
        cs = f"{cc[0]}/{cc[1]}" if cc else ""
        print(f"{lab:22} {cs:>10} {p:>7.3f} {q:>7.3f} {'YES' if sv else '.'}")
    n_sv = sum(1 for _, _, _, s in res if s)
    print(f"-> {n_sv}/{len(res)} cells survive BH-FDR (q<.05)")

    print("\n=== (2) full-scale pooled: DerSimonian-Laird random-effects meta (per-model log-OR ISB:vig) ===")
    meta = dl_meta([(m, full[m]) for m in MAIN])
    print(f"pooled OR(ISB:vig)={meta['pooled_OR']} CI{meta['ci']}  I^2={meta['I2_pct']}% (heterogeneity)  k={meta['k']}")
    print("  per-model log-OR:", {m: round(math.log((full[m][0]+.5)/(full[m][1]+.5)), 2) for m in MAIN})

    print("\n=== (3) trend across Gemma 4 sizes: logistic P(adoption flip | flip) ~ size rank ===")
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    order = ["E4B", "12B", "26B-A4B", "31B"]
    X, y = [], []
    for rank, tag in enumerate(order):
        a, b = scal_counts[tag]
        X += [[rank]] * a + [[rank]] * b
        y += [1] * a + [0] * b
    X = np.array(X); y = np.array(y)
    lr = LogisticRegression().fit(X, y)
    # trend p: likelihood ratio against the intercept-only model
    p1 = lr.predict_proba(X)[:, 1]
    ll1 = np.sum(y * np.log(p1) + (1 - y) * np.log(1 - p1))
    p0 = y.mean(); ll0 = len(y) * (p0 * log(p0) + (1 - p0) * log(1 - p0))
    from scipy.stats import chi2
    lr_p = 1 - chi2.cdf(2 * (ll1 - ll0), 1)
    print(f"per-size nISB/nVig: {[(t, scal_counts[t]) for t in order]}")
    print(f"trend coef(scale-rank on P(ISB among flips))={lr.coef_[0][0]:+.3f}  LR-test p={lr_p:.3f}")
    _a12, _b12 = scal_counts['12B']
    print(f"  (12B alone: binomial p={binom(_a12, _a12 + _b12):.3f})")

    out = {"bh_fdr": [{"cell": l, "raw_p": round(p, 4), "q": q, "survives": s} for l, p, q, s in res],
           "n_survive": n_sv, "pooled_random_effects": meta,
           "scaling_trend": {"coef": round(float(lr.coef_[0][0]), 3), "lr_p": round(float(lr_p), 4),
                             "per_size": {t: scal_counts[t] for t in order}}}
    (REPO / "analysis/stats_hygiene.json").write_text(json.dumps(out, indent=2))
    print("\nwrote analysis/stats_hygiene.json")


if __name__ == "__main__":
    main()

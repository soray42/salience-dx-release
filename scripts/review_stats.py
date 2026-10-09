#!/usr/bin/env python3
"""Three small analyses reported in the paper, all computed from released data:

* scaling_equivalence: per-size flip rates of the four Gemma 4 sizes with Wilson CIs, the
  E4B-minus-31B difference with a 95% CI, and a TOST equivalence test against a +-5-point
  margin (appendix "Additional Tables").
* meta_hartung_knapp: random-effects pooled odds ratio of adoption to rejection flips over the
  four models, with DerSimonian-Laird and Hartung-Knapp CIs (appendix "Statistical Methods").
* manipulation_logit: mean shift, from plain to salient, in the log-odds Llama 3.1 8B assigns
  to the cue's claim, on the ten-scenario pilot in data/manipulation_check (Limitations).

Usage: .venv/bin/python scripts/review_stats.py
"""
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "analysis/review_stats.json"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def scaling_equiv():
    d = json.loads((REPO / "analysis/scaling_isb.json").read_text())
    order = ["E4B (~4B act/8B)", "12B dense", "26B-A4B MoE(~4B act)", "31B dense"]
    rows = []
    for k in order:
        v = d[k]; n = v["n_pairs"]; kf = v["n_ISB"] + v["n_vig"]
        lo, hi = wilson(kf, n)
        rows.append({"size": k, "n": n, "flip_pct": round(100 * kf / n, 2),
                     "wilson_ci": [round(100 * lo, 1), round(100 * hi, 1)], "kf": kf})
    # E4B vs 31B difference CI (independent proportions, Wald)
    a, b = rows[0], rows[-1]
    p1, n1 = a["kf"] / a["n"], a["n"]; p2, n2 = b["kf"] / b["n"], b["n"]
    diff = p1 - p2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    ci = (diff - 1.96 * se, diff + 1.96 * se)
    # TOST against +-5pp margin
    margin = 0.05
    z_lo = (diff - (-margin)) / se   # H0: diff <= -margin
    z_hi = (margin - diff) / se      # H0: diff >= +margin
    from math import erf
    def sf(z):
        return 1 - 0.5 * (1 + erf(z / math.sqrt(2)))
    p_tost = max(sf(z_lo), sf(z_hi))
    return {"per_size": rows,
            "E4B_minus_31B": {"diff_pct": round(100 * diff, 2),
                              "ci95_pct": [round(100 * ci[0], 2), round(100 * ci[1], 2)]},
            "TOST_equivalence_margin_pp": 5,
            "TOST_p": round(p_tost, 4),
            "TOST_verdict": ("equivalent within +-5pp" if p_tost < 0.05
                             else "equivalence within +-5pp not established")}


def meta_hk():
    d = json.loads((REPO / "analysis/hypotheses_v31.json").read_text())
    models = ["claude-sonnet-4-6", "gemini-3.5-flash", "llama3.1:8b", "google/gemma-4-31B-it"]
    y = []; v = []
    for m in models:
        a = d["v3.1"]["models"][m]["asymmetry"]
        ni, nv = a["n_ISB"], a["n_vig"]
        # Haldane-Anscombe correction (+0.5 to both counts)
        yi = math.log((ni + 0.5) / (nv + 0.5))
        vi = 1.0 / (ni + 0.5) + 1.0 / (nv + 0.5)
        y.append(yi); v.append(vi)
    k = len(y)
    # DL tau^2
    w = [1 / vi for vi in v]
    ybar_fe = sum(wi * yi for wi, yi in zip(w, y)) / sum(w)
    Q = sum(wi * (yi - ybar_fe) ** 2 for wi, yi in zip(w, y))
    c = sum(w) - sum(wi ** 2 for wi in w) / sum(w)
    tau2 = max(0.0, (Q - (k - 1)) / c)
    ws = [1 / (vi + tau2) for vi in v]
    ybar = sum(wi * yi for wi, yi in zip(ws, y)) / sum(ws)
    var_dl = 1 / sum(ws)
    dl_ci = (ybar - 1.96 * math.sqrt(var_dl), ybar + 1.96 * math.sqrt(var_dl))
    # Hartung-Knapp
    q_hk = sum(wi * (yi - ybar) ** 2 for wi, yi in zip(ws, y)) / (k - 1)
    se_hk = math.sqrt(q_hk / sum(ws))
    t = 3.182  # t_{k-1=3, .975}
    hk_ci = (ybar - t * se_hk, ybar + t * se_hk)
    ex = math.exp
    return {"k": k, "pooled_logOR": round(ybar, 3), "pooled_OR": round(ex(ybar), 3),
            "tau2": round(tau2, 3),
            "DL_OR_ci95": [round(ex(dl_ci[0]), 3), round(ex(dl_ci[1]), 3)],
            "HK_OR_ci95": [round(ex(hk_ci[0]), 3), round(ex(hk_ci[1]), 3)]}


def manip():
    rows = [json.loads(l) for l in (REPO / "data/manipulation_check/results.ndjson").open() if l.strip()]
    sh = [r["HL_minus_LL"] for r in rows if r.get("HL_minus_LL") is not None]
    n = len(sh)
    mean = sum(sh) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in sh) / (n - 1)) if n > 1 else 0.0
    return {"n": n, "mean_HL_minus_LL_logit": round(mean, 3),
            "sd": round(sd, 3), "range": [round(min(sh), 3), round(max(sh), 3)],
            "note": "Llama 3.1 8B log-odds of the cue's claim, salient minus plain; ten-scenario pilot."}


def main():
    out = {
        "scaling_equivalence": scaling_equiv(),
        "meta_hartung_knapp": meta_hk(),
        "manipulation_logit": manip(),
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Trend tests across the four Gemma 4 sizes.

The same two tests are applied to (a) the flip rate and (b) the share of flips that are adoption
flips, each against size rank (by total parameters: E4B < 12B < 26B-A4B < 31B): a
Cochran-Armitage trend test and a logistic-regression likelihood-ratio test.

Input:  analysis/scaling_isb.json
Output: analysis/scaling_trend.json
Usage:  .venv/bin/python scripts/scaling_trend.py
"""
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "analysis/scaling_isb.json"
OUT = REPO / "analysis/scaling_trend.json"

# ordered by total parameters
ORDER = ["E4B (~4B act/8B)", "12B dense", "26B-A4B MoE(~4B act)", "31B dense"]


def chi2_sf_1(x):
    return math.erfc(math.sqrt(x / 2.0)) if x > 0 else 1.0


def cochran_armitage(n, k, ranks):
    N = sum(n); K = sum(k); pbar = K / N
    num = sum(ranks[i] * (k[i] - n[i] * pbar) for i in range(len(n)))
    var = pbar * (1 - pbar) * (sum(n[i] * ranks[i] ** 2 for i in range(len(n)))
                              - (sum(n[i] * ranks[i] for i in range(len(n))) ** 2) / N)
    z = num / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2))
    return z, p


def logistic_lr(n, k, ranks):
    def ll(a, b):
        s = 0.0
        for i in range(len(n)):
            pi = 1 / (1 + math.exp(-(a + b * ranks[i])))
            pi = min(max(pi, 1e-12), 1 - 1e-12)
            s += k[i] * math.log(pi) + (n[i] - k[i]) * math.log(1 - pi)
        return s
    # grid-search MLE: a in [-4, 0] step 0.01, b in [-0.3, 0.3] step 0.001
    best = None
    for ai in range(-400, 1):
        a = ai / 100
        for bi in range(-300, 301):
            b = bi / 1000
            v = ll(a, b)
            if best is None or v > best[0]:
                best = (v, a, b)
    ll1, _, b1 = best
    pbar = sum(k) / sum(n)
    a0 = math.log(pbar / (1 - pbar))
    ll0 = ll(a0, 0.0)
    lr = 2 * (ll1 - ll0)
    return b1, lr, chi2_sf_1(lr)


def main():
    d = json.loads(SRC.read_text())
    ranks = list(range(len(ORDER)))
    n = [d[k]["n_pairs"] for k in ORDER]

    # (a) total sensitivity: flips = ISB + vig
    kf = [d[k]["n_ISB"] + d[k]["n_vig"] for k in ORDER]
    z_f, p_f = cochran_armitage(n, kf, ranks)
    b_f, lr_f, plr_f = logistic_lr(n, kf, ranks)

    # (b) direction: among flips, is it ISB? n=flips, k=ISB
    nflip = kf
    kisb = [d[k]["n_ISB"] for k in ORDER]
    z_d, p_d = cochran_armitage(nflip, kisb, ranks)
    b_d, lr_d, plr_d = logistic_lr(nflip, kisb, ranks)

    out = {
        "order_by_total_params": ORDER,
        "total_sensitivity_trend": {
            "flip_pct": [round(100 * kf[i] / n[i], 2) for i in range(4)],
            "cochran_armitage": {"z": round(z_f, 3), "p": round(p_f, 4)},
            "logistic_trend": {"beta": round(b_f, 4), "LR_chi2_1": round(lr_f, 3), "p": round(plr_f, 4)},
            "verdict": "no reliable trend" if p_f > 0.05 else "significant trend",
        },
        "direction_trend": {
            "isb_share_of_flips_pct": [round(100 * kisb[i] / nflip[i], 2) for i in range(4)],
            "cochran_armitage": {"z": round(z_d, 3), "p": round(p_d, 4)},
            "logistic_trend": {"beta": round(b_d, 4), "LR_chi2_1": round(lr_d, 3), "p": round(plr_d, 4)},
            "verdict": "no reliable trend" if p_d > 0.05 else "significant trend",
        },
        "note": "Cochran-Armitage and logistic likelihood-ratio trend tests against size rank.",
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

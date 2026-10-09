#!/usr/bin/env python3
"""Flip rates across four sizes of Gemma 4 (rubric v3.1, DeepSeek-V4-Pro judge).

All four sizes answer the same 500 scenarios under the same conditions:
  E4B      (about 4B active parameters)   data/scaling/judge_E4B_v31.ndjson
  12B      (dense)                         data/scaling/judge_12B_v31.ndjson
  26B-A4B  (mixture of experts, about 4B active, 26B total)  data/scaling/judge_26B-A4B_v31.ndjson
  31B      (dense)                         data/full/judge_deepseek_v31.ndjson (Gemma rows)
E4B and 26B-A4B have similar active parameters but very different totals, so the four points
are not a single size axis.

Per size and per complexity level: adoption flips, rejection flips and flip rate with
scenario-clustered bootstrap 95% CIs, an exact binomial test of the two flip kinds, and
relevant-cue adoption.

Usage: .venv/bin/python scripts/scaling_analysis.py
"""
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C
import yaml

# ascending size; labels give total / active parameters
SCALING = [
    ("google/gemma-4-E4B-it",      "E4B (~4B act/8B)",   REPO / "data/scaling/judge_E4B_v31.ndjson"),
    ("google/gemma-4-12B-it",      "12B dense",          REPO / "data/scaling/judge_12B_v31.ndjson"),
    ("google/gemma-4-26B-A4B-it",  "26B-A4B MoE(~4B act)", REPO / "data/scaling/judge_26B-A4B_v31.ndjson"),
    ("google/gemma-4-31B-it",      "31B dense",          REPO / "data/full/judge_deepseek_v31.ndjson"),
]
CX = {os.path.basename(f)[:-5]: yaml.safe_load(open(f)).get("complexity", "?")
      for f in glob.glob(str(REPO / "data/pilot/feature_curation/inputs_full500/*.yaml"))}


def binom(k, n):
    if n == 0:
        return 1.0
    from math import comb
    pk = comb(n, k) * 0.5 ** n
    return min(1.0, sum(comb(n, i) * 0.5 ** n for i in range(n + 1)
                        if comb(n, i) * 0.5 ** n <= pk * 1.0000001))


def _rate(bucket):
    def f(rows):
        nz = [r for r in rows if r["bucket"] != "missing"]
        return sum(1 for r in nz if r["bucket"] == bucket) / len(nz) if nz else 0.0
    return f


def _flip(rows):
    nz = [r for r in rows if r["bucket"] != "missing"]
    return sum(1 for r in nz if r["bucket"] in ("ISB", "vigilance")) / len(nz) if nz else 0.0


def dfa_rate(recs, model):
    n = k = 0
    for s in {sd for (sd, m, c) in recs if m == model}:
        rec = recs.get((s, model, "LH"))
        if rec is None:
            continue
        fr = C.focal_role(rec)
        if fr is None:
            continue
        n += 1
        k += C.dfa_pass(fr)
    return k, n


def rows_for(model, path):
    recs, _ = C.load_judge_records(path)
    rows = C.build_pair_table(recs, models=[model])
    for r in rows:
        r["cx"] = CX.get(r["seed_id"], "?")
    return rows, recs


def summarize(rows, recs, model):
    nz = [r for r in rows if r["bucket"] != "missing"]
    cnt = Counter(r["bucket"] for r in nz)
    boot = C.bootstrap_rates(rows, {"ISB": _rate("ISB"), "vig": _rate("vigilance"), "flip": _flip}, n_boot=5000)
    dk, dn = dfa_rate(recs, model)
    n_isb, n_vig = cnt["ISB"], cnt["vigilance"]
    out = {"n_pairs": len(nz),
           "ISB_pct": round(100 * boot["ISB"]["estimate"], 2),
           "ISB_ci": [round(100 * boot["ISB"]["ci_lo"], 1), round(100 * boot["ISB"]["ci_hi"], 1)],
           "vig_pct": round(100 * boot["vig"]["estimate"], 2),
           "vig_ci": [round(100 * boot["vig"]["ci_lo"], 1), round(100 * boot["vig"]["ci_hi"], 1)],
           "flip_pct": round(100 * boot["flip"]["estimate"], 2),
           "n_ISB": n_isb, "n_vig": n_vig, "asym_p": round(binom(n_isb, n_isb + n_vig), 4),
           "DFA_pct": round(100 * dk / dn, 1) if dn else None, "DFA_n": dn,
           "by_complexity": {}}
    for lv in ("low", "medium", "high"):
        sub = [r for r in nz if r["cx"] == lv]
        c = Counter(r["bucket"] for r in sub)
        if sub:
            out["by_complexity"][lv] = {"n": len(sub), "ISB": round(100 * c["ISB"] / len(sub), 1),
                                        "vig": round(100 * c["vigilance"] / len(sub), 1),
                                        "flip": round(100 * (c["ISB"] + c["vigilance"]) / len(sub), 1)}
    return out


def main():
    results = {}
    print(f"{'model':22} {'n':>4} {'ISB%[CI]':>18} {'vig%[CI]':>18} {'flip%':>6} {'asym_p':>7} {'DFA%':>7}")
    for model, label, path in SCALING:
        if not path.exists():
            print(f"{label:22} -- judge file missing: {path.name}")
            continue
        rows, recs = rows_for(model, path)
        s = summarize(rows, recs, model)
        results[label] = s
        print(f"{label:22} {s['n_pairs']:>4} "
              f"{s['ISB_pct']:>6.1f}[{s['ISB_ci'][0]:>4.1f},{s['ISB_ci'][1]:>4.1f}] "
              f"{s['vig_pct']:>6.1f}[{s['vig_ci'][0]:>4.1f},{s['vig_ci'][1]:>4.1f}] "
              f"{s['flip_pct']:>6.1f} {s['asym_p']:>7.3f} {s['DFA_pct']:>5}({s['DFA_n']})")
    print("\nper-complexity flip% (ISB/vig):")
    for label, s in results.items():
        cx = s["by_complexity"]
        seg = "  ".join(f"{lv}:{cx[lv]['flip']}({cx[lv]['ISB']}/{cx[lv]['vig']})" for lv in ("low","medium","high") if lv in cx)
        print(f"  {label:22} {seg}")
    (REPO / "analysis/scaling_isb.json").write_text(json.dumps(results, indent=2))
    print("\nwrote analysis/scaling_isb.json")


if __name__ == "__main__":
    main()

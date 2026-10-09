#!/usr/bin/env python3
"""Main results (paper Table "main" and Figure 1).

Data: data/full/judge_deepseek_v31.ndjson (4 models x salient/plain/relevant-control x 500
scenarios, judged by DeepSeek-V4-Pro under the final rubric, v3.1). The labels under the
previous rubric revision (v3, data/full/judge_deepseek.ndjson) are analysed the same way for
comparison.

Reports, per model and pooled:
  * adoption flips (ISB: rejected under plain, adopted under salient) and rejection flips
    (vigilance: adopted under plain, rejected under salient), with scenario-clustered bootstrap
    95% CIs, and the flip rate (their sum);
  * an exact binomial test of adoption against rejection flips (H0: p = 0.5);
  * stable adoption / stable rejection shares;
  * relevant-cue adoption (DFA): share of relevant-control (LH) answers that adopt the
    relevant cue.

Usage: .venv/bin/python scripts/validate_hypotheses_v31.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
V3 = REPO / "data/full/judge_deepseek.ndjson"
MODELS = C.MODELS_WAVE2  # sonnet, gemini, llama, gemma


def binom_two_sided(k, n, p=0.5):
    if n == 0:
        return 1.0
    from math import comb
    pk = comb(n, k) * p ** k * (1 - p) ** (n - k)
    tot = sum(comb(n, i) * p ** i * (1 - p) ** (n - i)
              for i in range(n + 1)
              if comb(n, i) * p ** i * (1 - p) ** (n - i) <= pk * 1.0000001)
    return min(1.0, tot)


def _nonmissing(rows):
    return [r for r in rows if r["bucket"] != "missing"]


def _rate_fn(bucket):
    def f(rows):
        nz = _nonmissing(rows)
        return sum(1 for r in nz if r["bucket"] == bucket) / len(nz) if nz else 0.0
    return f


def _flip_fn(rows):
    nz = _nonmissing(rows)
    return sum(1 for r in nz if r["bucket"] in ("ISB", "vigilance")) / len(nz) if nz else 0.0


def dfa_rate(recs, model):
    """Focal 'primary' rate in the LH cell (positive control)."""
    n = k = 0
    seeds = {s for (s, m, c) in recs if m == model}
    for s in seeds:
        rec = recs.get((s, model, "LH"))
        if rec is None:
            continue
        fr = C.focal_role(rec)
        if fr is None:
            continue
        n += 1
        if C.dfa_pass(fr):
            k += 1
    return k, n


def analyze(path, rubric_label):
    recs, ndup = C.load_judge_records(path)
    rows_all = C.build_pair_table(recs, models=MODELS)
    out = {"rubric": rubric_label, "n_dup_dropped": ndup, "models": {}}
    print(f"\n{'='*88}\nRUBRIC {rubric_label}  ({path.name})   dup_dropped={ndup}\n{'='*88}")
    print(f"{'model':26s} {'n':>4} {'ISB%':>16} {'vig%':>16} {'flip%':>8} "
          f"{'nISB/nVig':>10} {'asym_p':>7} {'DFA%':>10}")
    for model in MODELS + ["POOLED"]:
        rows = rows_all if model == "POOLED" else [r for r in rows_all if r["model"] == model]
        nz = _nonmissing(rows)
        n = len(nz)
        cnt = Counter(r["bucket"] for r in nz)
        n_isb, n_vig = cnt["ISB"], cnt["vigilance"]
        boot = C.bootstrap_rates(rows, {"ISB": _rate_fn("ISB"), "vig": _rate_fn("vigilance"),
                                        "flip": _flip_fn}, n_boot=5000)
        asym_p = binom_two_sided(n_isb, n_isb + n_vig, 0.5) if (n_isb + n_vig) else 1.0
        if model == "POOLED":
            dfa_k = dfa_n = 0
            for m in MODELS:
                a, b = dfa_rate(recs, m); dfa_k += a; dfa_n += b
        else:
            dfa_k, dfa_n = dfa_rate(recs, model)
        dfa_pct = 100 * dfa_k / dfa_n if dfa_n else 0.0
        rec = {
            "n_pairs": n,
            "ISB": {"n": n_isb, "pct": round(100 * boot["ISB"]["estimate"], 2),
                    "ci": [round(100 * boot["ISB"]["ci_lo"], 2), round(100 * boot["ISB"]["ci_hi"], 2)]},
            "vigilance": {"n": n_vig, "pct": round(100 * boot["vig"]["estimate"], 2),
                          "ci": [round(100 * boot["vig"]["ci_lo"], 2), round(100 * boot["vig"]["ci_hi"], 2)]},
            "flip_total_pct": round(100 * boot["flip"]["estimate"], 2),
            "stable_adopt_pct": round(100 * cnt["stable_adopt"] / n, 2) if n else 0,
            "stable_reject_pct": round(100 * cnt["stable_reject"] / n, 2) if n else 0,
            "proto_ISB": cnt["proto_ISB"], "proto_vigilance": cnt["proto_vigilance"],
            "asymmetry": {"n_ISB": n_isb, "n_vig": n_vig, "binom_p": round(asym_p, 4)},
            "DFA_positive_control": {"k": dfa_k, "n": dfa_n, "pct": round(dfa_pct, 1)},
        }
        out["models"][model] = rec
        isb = rec["ISB"]; vig = rec["vigilance"]
        print(f"{model:26s} {n:>4} "
              f"{isb['pct']:>6.2f}[{isb['ci'][0]:>4.1f},{isb['ci'][1]:>4.1f}] "
              f"{vig['pct']:>6.2f}[{vig['ci'][0]:>4.1f},{vig['ci'][1]:>4.1f}] "
              f"{rec['flip_total_pct']:>7.2f} {n_isb:>4}/{n_vig:<4} {asym_p:>7.3f} "
              f"{dfa_pct:>6.1f}({dfa_n})")
    return out


def main():
    res31 = analyze(V31, "v3.1")
    res3 = analyze(V3, "v3") if V3.exists() else None

    p = res31["models"]["POOLED"]
    isb, vig, a = p["ISB"], p["vigilance"], p["asymmetry"]
    print(f"\nPooled (rubric v3.1, {p['n_pairs']} pairs): adoption flips {isb['pct']}% {isb['ci']}, "
          f"rejection flips {vig['pct']}% {vig['ci']}, flip rate {p['flip_total_pct']}%; "
          f"{a['n_vig']} rejection vs {a['n_ISB']} adoption flips, binomial p={a['binom_p']}; "
          f"relevant-cue adoption {p['DFA_positive_control']['pct']}%")
    if res3:
        q = res3["models"]["POOLED"]
        print(f"Pooled (rubric v3): adoption flips {q['ISB']['pct']}%, rejection flips {q['vigilance']['pct']}%")

    (REPO / "analysis/hypotheses_v31.json").write_text(
        json.dumps({"v3.1": res31, "v3": res3}, indent=2))
    print("\nwrote analysis/hypotheses_v31.json")


if __name__ == "__main__":
    main()

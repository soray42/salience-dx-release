#!/usr/bin/env python3
"""Trace-off re-judge (paper appendix "Judge Validation").

A random 300-scenario subset was re-judged with the judge's reasoning trace switched off. This
script compares the re-judge with the main run on the same 300 scenarios x 4 models x
{salient (HL), plain (LL)}:
  * item-level distractor-role agreement (CoT-on vs CoT-off)
  * pair-bucket agreement + Cohen kappa
  * adoption-flip (ISB), rejection-flip (vigilance) and flip rates under each run, with
    scenario-clustered bootstrap CIs

Usage: .venv/bin/python scripts/cotoff_robustness.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

ON = REPO / "data/full/judge_deepseek_v31.ndjson"            # main run (reasoning trace on)
OFF = REPO / "data/full/judge_deepseek_cotoff_subset.ndjson"  # trace-off re-judge
SUBSET = REPO / "data/full/free_response_cotoff_subset.ndjson"
OUT = REPO / "analysis/cotoff_robustness.json"
MODELS = C.MODELS_WAVE2


def subset_seeds():
    s = set()
    for l in SUBSET.open():
        if l.strip():
            s.add(json.loads(l)["seed_id"])
    return s


def rates(rows):
    nz = [r for r in rows if r["bucket"] != "missing"]
    n = len(nz)
    c = Counter(r["bucket"] for r in nz)
    boot = C.bootstrap_rates(rows, {
        "ISB": lambda rs: sum(1 for r in rs if r["bucket"] == "ISB") / max(1, len([x for x in rs if x["bucket"] != "missing"])),
        "vig": lambda rs: sum(1 for r in rs if r["bucket"] == "vigilance") / max(1, len([x for x in rs if x["bucket"] != "missing"])),
    }, n_boot=5000)
    return {
        "n_pairs": n, "n_ISB": c["ISB"], "n_vig": c["vigilance"],
        "ISB_pct": round(100 * boot["ISB"]["estimate"], 2),
        "ISB_ci": [round(100 * boot["ISB"]["ci_lo"], 1), round(100 * boot["ISB"]["ci_hi"], 1)],
        "vig_pct": round(100 * boot["vig"]["estimate"], 2),
        "vig_ci": [round(100 * boot["vig"]["ci_lo"], 1), round(100 * boot["vig"]["ci_hi"], 1)],
        "flip_pct": round(100 * (c["ISB"] + c["vigilance"]) / n, 2) if n else None,
    }


def main():
    sub = subset_seeds()
    recs_on, _ = C.load_judge_records(ON)
    recs_off, _ = C.load_judge_records(OFF)
    seeds = sorted(sub)

    on_rows = [r for r in C.build_pair_table(recs_on, models=MODELS, seeds=seeds) if r["bucket"] != "missing"]
    off_rows = [r for r in C.build_pair_table(recs_off, models=MODELS, seeds=seeds) if r["bucket"] != "missing"]

    # item-level agreement on the irrelevant cue's role (answers labelled in both runs)
    on_role = {k: C.distractor_role(v) for k, v in recs_on.items() if k[0] in sub and k[2] in ("HL", "LL")}
    off_role = {k: C.distractor_role(v) for k, v in recs_off.items()}
    common = [k for k in off_role if k in on_role and on_role[k] is not None and off_role[k] is not None]
    a = [on_role[k] for k in common]; b = [off_role[k] for k in common]
    item_agree = sum(1 for x, y in zip(a, b) if x == y) / len(common) if common else None
    item_kappa = C.cohens_kappa(a, b) if common else None

    # pair-bucket agreement
    on_b = {(r["seed_id"], r["model"]): r["bucket"] for r in on_rows}
    off_b = {(r["seed_id"], r["model"]): r["bucket"] for r in off_rows}
    pk = [k for k in off_b if k in on_b]
    pair_agree = sum(1 for k in pk if on_b[k] == off_b[k]) / len(pk) if pk else None

    out = {
        "subset": {"n_seeds": len(sub), "cells": "HL,LL", "models": MODELS},
        "item_distractor_role": {"n": len(common), "agreement_pct": round(100 * item_agree, 1) if item_agree else None,
                                  "cohen_kappa": round(item_kappa, 3) if item_kappa is not None else None},
        "pair_bucket": {"n": len(pk), "agreement_pct": round(100 * pair_agree, 1) if pair_agree else None},
        "rates_CoT_on": rates(on_rows),
        "rates_CoT_off": rates(off_rows),
        "note": "Main-run labels (reasoning trace on) vs trace-off re-judge; same 300 scenarios, HL and LL.",
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

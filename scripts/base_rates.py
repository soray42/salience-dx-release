#!/usr/bin/env python3
"""Per-model base rates behind the flip rates, plus the full pair-outcome distribution and the
length of the cue clause in each condition.

For every model (and pooled), over the LL/HL pairs of the 500-scenario run (v3.1 judge labels):
  * share of pairs in which the cue is adopted under the plain condition and under the salient
    condition, and the net change (salient minus plain);
  * conditional flip rates: P(rejected under salient | adopted under plain) and
    P(adopted under salient | rejected under plain);
  * the complete pair-outcome distribution, including the outcomes that involve an 'ignored'
    label (which the flip rates leave out).
Also: word counts of the cue clause in the plain and the salient version over the 500 scenarios.

Writes analysis/base_rates.json.  Usage: .venv/bin/python scripts/base_rates.py
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C  # noqa: E402

V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
SEEDS = REPO / "data/pilot/feature_curation/inputs_full500"
OUT = REPO / "analysis/base_rates.json"


def block(rows):
    rows = [r for r in rows if r["bucket"] != "missing"]
    n = len(rows)
    ll_adopt = sum(1 for r in rows if r["ll_role"] == "primary")
    hl_adopt = sum(1 for r in rows if r["hl_role"] == "primary")
    ll_rej = sum(1 for r in rows if r["ll_role"] == "considered_rejected")
    vig = sum(1 for r in rows if r["bucket"] == "vigilance")
    isb = sum(1 for r in rows if r["bucket"] == "ISB")
    return {
        "n_pairs": n,
        "adopted_plain_pct": round(100 * ll_adopt / n, 1),
        "adopted_salient_pct": round(100 * hl_adopt / n, 1),
        "net_change_pp": round(100 * (hl_adopt - ll_adopt) / n, 1),
        "p_rejected_salient_given_adopted_plain_pct": round(100 * vig / ll_adopt, 1) if ll_adopt else None,
        "p_adopted_salient_given_rejected_plain_pct": round(100 * isb / ll_rej, 1) if ll_rej else None,
        "pair_outcomes": dict(Counter(r["bucket"] for r in rows)),
    }


def main():
    recs, _ = C.load_judge_records(V31)
    rows = C.build_pair_table(recs, models=C.MODELS_WAVE2)
    out = {"models": {m: block([r for r in rows if r["model"] == m]) for m in C.MODELS_WAVE2}}
    out["models"]["POOLED"] = block(rows)

    ll, hl, stem = [], [], []
    for f in sorted(glob.glob(str(SEEDS / "*.yaml"))):
        d = yaml.safe_load(open(f, encoding="utf-8"))
        v = d["variants"]
        ll.append(len(str(v["LL"]["distractor"]).split()))
        hl.append(len(str(v["HL"]["distractor"]).split()))
        stem.append(len(str(d["xbase"]).split()))
    out["cue_length_words"] = {
        "n_scenarios": len(ll),
        "plain_mean": round(statistics.mean(ll), 1), "plain_median": statistics.median(ll),
        "salient_mean": round(statistics.mean(hl), 1), "salient_median": statistics.median(hl),
        "ratio_mean": round(statistics.mean(h / l for h, l in zip(hl, ll)), 2),
        "ratio_max": round(max(h / l for h, l in zip(hl, ll)), 2),
        "scenario_stem_mean": round(statistics.mean(stem), 1),
    }
    OUT.write_text(json.dumps(out, indent=2))
    for m, b in out["models"].items():
        print(f"{m:24s} n={b['n_pairs']} adopted plain {b['adopted_plain_pct']}% salient {b['adopted_salient_pct']}% "
              f"net {b['net_change_pp']:+.1f}pp | P(rej|adopt) {b['p_rejected_salient_given_adopted_plain_pct']}% "
              f"P(adopt|rej) {b['p_adopted_salient_given_rejected_plain_pct']}%")
    print("cue length:", out["cue_length_words"])
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Dismissive wording in the answers (paper Section 4, "Rejection flips add dismissive
wording more often").

Scans each model's final answer for a fixed list of phrases that dismiss a cue ("just
anecdotal", "correlation is not causation", "one data point", ...) and reports, per pair
outcome, how often the salient (HL) answer contains such a phrase that the plain (LL) answer
lacks, and the reverse. This is a text-pattern count, not a human coding of the answers.

Usage: .venv/bin/python scripts/rationale_markers.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

RESP = REPO / "data/full/free_response.ndjson"
V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
OUT = REPO / "analysis/rationale_markers.json"

# debiasing / skepticism markers (case-insensitive regex, word-ish boundaries)
MARKERS = [
    r"anecdot", r"one data ?point", r"single data ?point", r"a data ?point",
    r"correlation (is|does)\W+not\W+(imply|mean|equal)|correlation\W+\W*causation",
    r"coincidence", r"coincidental", r"not necessarily", r"does(n't| not) (mean|imply)",
    r"red herring", r"confirmation bias", r"survivorship", r"just because",
    r"don'?t assume", r"be (careful|cautious|wary)", r"grain of salt", r"hearsay",
    r"isn'?t evidence|not evidence|not proof", r"not (a )?reliable", r"not diagnostic",
    r"different (context|situation|stack|setup|company|case)", r"may not apply|might not apply",
    r"your (situation|case|setup) is different", r"correlation", r"causation",
    r"appeal to authority", r"authority (isn'?t|is not)", r"unrelated",
]
PAT = re.compile("|".join(MARKERS), re.IGNORECASE)


def has_marker(text: str) -> bool:
    return bool(PAT.search(text or ""))


def load_resp():
    lut = {}
    for line in RESP.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("status") == "ok":
            lut[(r["seed_id"], r["model"], r["cell"])] = r.get("final_answer", "") or ""
    return lut


def main():
    recs, _ = C.load_judge_records(V31)
    rows = C.build_pair_table(recs, models=C.MODELS_WAVE2)
    resp = load_resp()

    # (a) overall HL vs LL marker rate
    hl_has = hl_n = ll_has = ll_n = 0
    # (b) per-bucket paired marker presence
    per_bucket = defaultdict(lambda: {"n": 0, "hl_marker": 0, "ll_marker": 0,
                                       "hl_only": 0, "ll_only": 0})
    for r in rows:
        s, m, b = r["seed_id"], r["model"], r["bucket"]
        if b == "missing":
            continue
        hl = resp.get((s, m, "HL")); ll = resp.get((s, m, "LL"))
        if hl is None or ll is None:
            continue
        hm, lm = has_marker(hl), has_marker(ll)
        hl_has += hm; ll_has += lm; hl_n += 1; ll_n += 1
        pb = per_bucket[b]
        pb["n"] += 1
        pb["hl_marker"] += hm; pb["ll_marker"] += lm
        pb["hl_only"] += (hm and not lm)
        pb["ll_only"] += (lm and not hm)

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    out = {
        "note": ("Text-pattern proxy for explicit debiasing language (not human "
                 "rationale coding). Marker set in scripts/rationale_markers.py."),
        "overall": {
            "HL_marker_rate_pct": pct(hl_has, hl_n),
            "LL_marker_rate_pct": pct(ll_has, ll_n),
            "n_pairs": hl_n,
        },
        "by_bucket": {},
    }
    for b, pb in per_bucket.items():
        out["by_bucket"][b] = {
            "n": pb["n"],
            "HL_marker_pct": pct(pb["hl_marker"], pb["n"]),
            "LL_marker_pct": pct(pb["ll_marker"], pb["n"]),
            "HL_only_pct": pct(pb["hl_only"], pb["n"]),
            "LL_only_pct": pct(pb["ll_only"], pb["n"]),
        }
    # discordant pairs: phrase only in the salient answer minus phrase only in the plain answer
    for b in ("vigilance", "ISB", "stable_reject", "stable_adopt"):
        if b in per_bucket:
            pb = per_bucket[b]
            out["by_bucket"][b]["hl_only_minus_ll_only"] = pb["hl_only"] - pb["ll_only"]

    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Flip rates by scenario generator (paper appendix "Generator Robustness").

The 450 expanded scenarios were written by two generators; generator B is also one of the
evaluated models (Claude Sonnet 4.6). For every evaluated model this script splits the
adoption-flip (ISB), rejection-flip (vigilance) and total flip rates by the generator of the
scenario, so that a model can be compared on its own scenarios and on the other generator's.

The generator of each scenario is read from the provenance block of the scenario YAML; the 50
hand-written scenarios have none and are skipped.

Usage: .venv/bin/python scripts/generator_robustness.py
"""
import json
import sys
import glob
from collections import defaultdict, Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

RAW = REPO / "data/pilot/feature_curation/inputs_full500"   # all 450 expanded scenarios carry a generator
V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
OUT = REPO / "analysis/generator_robustness.json"


def gen_map():
    """seed_id -> generator model id (the 50 hand-written scenarios have none and are skipped)."""
    m = {}
    for f in glob.glob(str(RAW / "*.yaml")):
        try:
            d = yaml.safe_load(open(f))
        except Exception:
            continue
        p = (d or {}).get("provenance") or {}
        g = p.get("generator") if isinstance(p, dict) else None
        if g and d.get("seed_id"):
            m[d["seed_id"]] = str(g).split(" (")[0].strip()   # drop any parenthetical note
    return m


def wilson(k, n, z=1.96):
    import math
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def main():
    gm = gen_map()
    gens = Counter(gm.values())
    recs, _ = C.load_judge_records(V31)
    rows = C.build_pair_table(recs, models=C.MODELS_WAVE2)

    # (evaluated model, generator) -> Counter of pair outcomes, expanded scenarios only
    cell = defaultdict(Counter)
    for r in rows:
        s, m, b = r["seed_id"], r["model"], r["bucket"]
        if b == "missing" or s not in gm:
            continue
        cell[(m, gm[s])][b] += 1

    def rate(cnt, bucket):
        n = sum(cnt.values())
        k = cnt[bucket]
        lo, hi = wilson(k, n)
        return {"pct": round(100 * k / n, 2) if n else None,
                "ci": [round(100 * lo, 1), round(100 * hi, 1)], "n": n, "k": k}

    out = {"generators": dict(gens), "note": (
        "Expanded scenarios only (the 50 hand-written ones carry no generator). Rows are "
        "evaluated model x scenario generator."),
        "by_eval_x_generator": {}}
    for (m, g), cnt in sorted(cell.items()):
        out["by_eval_x_generator"][f"{m} on {g}"] = {
            "ISB": rate(cnt, "ISB"), "vigilance": rate(cnt, "vigilance"),
            "flip_pct": round(100 * (cnt["ISB"] + cnt["vigilance"]) / sum(cnt.values()), 2)
            if sum(cnt.values()) else None,
        }

    # the evaluated model that is also generator B, on each generator's scenarios
    gen_b_model = "claude-sonnet-4-6"
    contrasts = {}
    for g in gens:
        c = cell.get((gen_b_model, g))
        if c:
            contrasts[g] = {"ISB": rate(c, "ISB"), "vig": rate(c, "vigilance")}
    out["generator_B_model_by_generator"] = contrasts

    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

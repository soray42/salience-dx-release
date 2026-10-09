#!/usr/bin/env python3
"""Quality-control statistics reported in the paper, computed from the scenario files and the
archived audit verdicts.

  * per-scenario fields: how many of the 500 scenarios carry a leak audit with atomic claims, a
    causal audit, a repair note; by generator and by curator prompt; generation modes;
  * the archived audit verdict records (data/pilot/feature_curation/wave2_qc/, the 30-scenario
    development batch): counts by lens.

Writes analysis/qc_stats.json.  Usage: .venv/bin/python scripts/qc_stats.py
"""
import glob
import json
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SEEDS = REPO / "data/pilot/feature_curation/inputs_full500"
QC = REPO / "data/pilot/feature_curation/wave2_qc"
OUT = REPO / "analysis/qc_stats.json"


def main():
    n = 0
    atomic = causal = repair = 0
    by_gen = Counter(); repair_by_gen = Counter(); modes = Counter(); prompts = Counter()
    for f in sorted(glob.glob(str(SEEDS / "*.yaml"))):
        d = yaml.safe_load(open(f, encoding="utf-8")); n += 1
        p = d.get("provenance") or {}
        g = str(p.get("generator") or "hand-written").split(" (")[0]
        by_gen[g] += 1
        modes[p.get("generation_mode") or "hand-written"] += 1
        prompts[p.get("curator_prompt") or "hand-written"] += 1
        la = d.get("leak_audit")
        if isinstance(la, dict) and la.get("ll_atomic_claims"):
            atomic += 1
        if d.get("causal_audit"):
            causal += 1
        if p.get("repair_note"):
            repair += 1; repair_by_gen[g] += 1
    verdicts = Counter(); seeds = set()
    vf = QC / "qc_verdicts.ndjson"
    if vf.exists():
        for line in open(vf, encoding="utf-8"):
            if line.strip():
                r = json.loads(line); verdicts[r.get("lens")] += 1; seeds.add(r.get("seed_id"))
    out = {
        "n_scenarios": n,
        "scenarios_by_generator": dict(by_gen),
        "generation_modes": dict(modes),
        "curator_prompts": dict(prompts),
        "with_leak_audit_atomic_claims": atomic,
        "with_causal_audit": causal,
        "with_repair_note": repair,
        "repair_note_by_generator": dict(repair_by_gen),
        "repair_share_of_expanded_pct": round(100 * repair / (n - by_gen.get("hand-written", 0)), 1),
        "archived_audit_verdicts": {"n_records": sum(verdicts.values()), "n_scenarios": len(seeds), "by_lens": dict(verdicts)},
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

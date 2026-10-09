#!/usr/bin/env python3
"""Cross-judge agreement (raw agreement and Cohen's kappa) on the distractor role, over the
(seed, model, cell) overlap of two judge NDJSON files.

Usage:
  .venv/bin/python scripts/judge_kappa.py <judge_a.ndjson> <judge_b.ndjson> [labelA labelB] [--json OUT]

With --json, also writes the pooled figures, a scenario-clustered bootstrap CI for kappa and the
model/cell composition of the overlap. The paper's 150-answer Gemini cross-judge figure is

  .venv/bin/python scripts/judge_kappa.py data/full/judge_deepseek_v31.ndjson \
      analysis/judge_kappa/gemini_v31_sample.ndjson deepseek gemini \
      --json analysis/judge_kappa/kappa_v31_150.json
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C


def role_map(path):
    recs, _ = C.load_judge_records(path)
    return {k: C.distractor_role(v) for k, v in recs.items()}


def seed_bootstrap_kappa(common, ma, mb, n_boot=5000, seed=20260927):
    rng = random.Random(seed)
    by = {}
    for k in common:
        by.setdefault(k[0], []).append((ma[k], mb[k]))
    seeds = sorted(by)
    ks = []
    for _ in range(n_boot):
        aa, bb = [], []
        for _ in seeds:
            s = seeds[rng.randrange(len(seeds))]
            for x, y in by[s]:
                aa.append(x)
                bb.append(y)
        ks.append(C.cohens_kappa(aa, bb))
    ks.sort()
    return [round(ks[int(0.025 * n_boot)], 3), round(ks[int(0.975 * n_boot) - 1], 3)]


def main():
    argv = list(sys.argv[1:])
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        out_json = Path(argv[i + 1])
        del argv[i:i + 2]
    a, b = Path(argv[0]), Path(argv[1])
    la = argv[2] if len(argv) > 2 else a.stem
    lb = argv[3] if len(argv) > 3 else b.stem
    ma, mb = role_map(a), role_map(b)
    common = [k for k in ma if k in mb and ma[k] is not None and mb[k] is not None]
    la_list = [ma[k] for k in common]
    lb_list = [mb[k] for k in common]
    kappa = C.cohens_kappa(la_list, lb_list)
    agree = sum(1 for x, y in zip(la_list, lb_list) if x == y) / len(common) if common else 0.0
    print(f"{la}  vs  {lb}   (distractor role, 3-way)")
    print(f"  n_overlap={len(common)}  raw_agreement={100*agree:.1f}%  Cohen_kappa={kappa:.3f}")
    # per model
    per_model = {}
    models = sorted({k[1] for k in common})
    for m in models:
        ck = [k for k in common if k[1] == m]
        ka = C.cohens_kappa([ma[k] for k in ck], [mb[k] for k in ck])
        ag = sum(1 for k in ck if ma[k] == mb[k]) / len(ck)
        per_model[m] = {"n": len(ck), "pct_agree": round(100 * ag, 1), "cohen_kappa": round(ka, 3)}
        print(f"    {m:26s} n={len(ck):>4} agree={100*ag:>5.1f}% kappa={ka:.3f}")
    if out_json:
        ci = seed_bootstrap_kappa(common, ma, mb)
        out = {"judge_a": str(a), "judge_b": str(b), "n": len(common), "pct_agree": round(100 * agree, 1),
               "cohen_kappa": round(kappa, 3), "kappa_ci_seed_bootstrap": ci,
               "models": dict(Counter(k[1] for k in common)), "cells": dict(Counter(k[2] for k in common)),
               "per_model": per_model}
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(out, indent=2))
        print(f"  kappa CI (scenario bootstrap) {ci}; wrote {out_json}")


if __name__ == "__main__":
    main()

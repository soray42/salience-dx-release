#!/usr/bin/env python3
"""Compare freshly computed analysis files with a reference copy.

Every numeric value in each analysis JSON is compared, by its position in the file, with the
same value in the reference copy (tolerance 1e-9). The figure is checked for existence only.
Exit status 0 if everything matches, 1 otherwise.

Usage: .venv/bin/python scripts/verify_reproduction.py <reference analysis dir>
(reproduce.sh copies analysis/ to a temporary directory before running the scripts and then
calls this with that copy.)
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FILES = [
    "hypotheses_v31.json", "multilingual_isb_v31.json", "scaling_isb.json", "scaling_trend.json",
    "stats_hygiene.json", "review_stats.json", "rationale_markers.json", "cotoff_robustness.json",
    "generator_robustness.json", "base_rates.json", "qc_stats.json", "asymmetry_checks.json",
    "judge_kappa/kappa_v31_150.json", "human_val/human_val_results.json",
    "human_gold/human_gold_results.json",
]
FIGURE = REPO / "paper/figures/flips_by_model.pdf"


def leaves(obj, path=""):
    """(path, number) for every numeric leaf; booleans and strings are skipped."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, float(obj)


def compare(ref_file: Path, new_file: Path) -> list[str]:
    ref = dict(leaves(json.loads(ref_file.read_text(encoding="utf-8"))))
    new = dict(leaves(json.loads(new_file.read_text(encoding="utf-8"))))
    problems = []
    for p in sorted(set(ref) | set(new)):
        if p not in new:
            problems.append(f"missing {p}")
        elif p not in ref:
            problems.append(f"unexpected {p}")
        elif abs(ref[p] - new[p]) > 1e-9:
            problems.append(f"{p}: expected {ref[p]}, got {new[p]}")
    return problems


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ref_dir = Path(sys.argv[1])
    ok = True
    for rel in FILES:
        problems = compare(ref_dir / rel, REPO / "analysis" / rel)
        n = sum(1 for _ in leaves(json.loads((REPO / "analysis" / rel).read_text(encoding="utf-8"))))
        if problems:
            ok = False
            print(f"  DIFF {rel}: {len(problems)} of {n} values")
            for line in problems[:5]:
                print(f"       {line}")
        else:
            print(f"  ok   {rel} ({n} values)")
    if FIGURE.exists() and FIGURE.stat().st_size > 0:
        print(f"  ok   {FIGURE.relative_to(REPO)}")
    else:
        ok = False
        print(f"  MISSING {FIGURE.relative_to(REPO)}")
    print("all numbers reproduced" if ok else "reproduction FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

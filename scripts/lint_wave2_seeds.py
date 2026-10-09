"""Structural checks for expanded scenario files ("wave 2" = the 450 expanded scenarios).

Checks per scenario (exit 1 if any fails):
  1. The cue slot {DS} appears exactly once in the scenario text (xbase).
  2. The text before {DS} ends a sentence (. ! ?), since every cue version is a full sentence.
  3. Word counts: xbase 40-90 (without {DS}); salient cue 25-50; plain cue 12-25.
  4. No person's name is reused across scenarios (in xbase and all cue versions).
  5. Required top-level keys and the provenance block are present.

The checks that need judgement (causal plausibility, added content, evidence leaks) are the LLM
audits in prompts/v5/qc_*.md. The 50 hand-written scenarios have no provenance block and fail
check 5 by design.

Usage:
  .venv/bin/python scripts/lint_wave2_seeds.py --dir data/pilot/feature_curation/inputs_full500
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "data" / "pilot" / "feature_curation" / "inputs_wave2_draft"

REQUIRED_KEYS = {
    "seed_id", "template", "domain", "complexity", "xbase",
    "focal_diagnostic_feature", "low_diagnostic_proposition",
    "oracle_action", "oracle_focus", "cell_oracles", "variants",
    "distractor_direction", "plausible_alternative_directions",
    "leak_audit", "causal_audit", "provenance",
}
NAME_STOPWORDS = {
    "The", "Our", "She", "When", "After", "Their", "His", "Her", "Every",
    "But", "And", "That", "This", "Now", "Someone", "Anyone",
    # sentence-initial gerunds/participles the NAME_PAT can mistake for a name
    "Looking", "Taken", "Treating", "Checking", "Using", "Running", "Seeing",
    "Comparing", "Reading", "Given", "Having", "Knowing", "Choosing", "Several",
    # capitalized non-names (products, libraries, weekdays, HTTP terms) that hit
    # the role-trigger regex — never actual source names
    "Redis", "Requests", "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Docker", "Kafka", "Postgres", "React", "Android",
    "Jenkins", "Prometheus", "Safari", "Many",
}
NAME_PAT = re.compile(
    r"\b([A-Z][a-z]{2,})\b(?:,| who| at| from| told| said| swore| confirmed"
    r"| ran| calculated| a )"
)


def wc(text: str) -> int:
    return len(text.replace("{DS}", "").replace("—", " ").split())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    failures: list[str] = []
    names: dict[str, set[str]] = defaultdict(set)

    for path in sorted(args.dir.glob("T*.yaml")):
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        sid = d.get("seed_id", path.stem)
        if d.get("unconstructable"):
            continue

        missing = REQUIRED_KEYS - set(d.keys())
        if missing:
            failures.append(f"{sid}: missing keys {sorted(missing)}")

        xb = " ".join(str(d.get("xbase", "")).split())
        if xb.count("{DS}") != 1:
            failures.append(f"{sid}: xbase has {xb.count('{DS}')} {{DS}} tokens (need exactly 1)")
        else:
            before = xb.split("{DS}")[0].rstrip()
            if not before.endswith((".", "!", "?")):
                failures.append(f"{sid}: non-standalone {{DS}} slot — xbase ends ...{before[-45:]!r}")
        if not 40 <= wc(xb) <= 90:
            failures.append(f"{sid}: xbase word count {wc(xb)} outside 40-90")

        hl = str(d["variants"]["HL"]["distractor"])
        ll = str(d["variants"]["LL"]["distractor"])
        if not 25 <= wc(hl) <= 50:
            failures.append(f"{sid}: HL word count {wc(hl)} outside 25-50")
        if not 12 <= wc(ll) <= 25:
            failures.append(f"{sid}: LL word count {wc(ll)} outside 12-25")

        texts = [xb] + [
            str(d["variants"][c].get("distractor", "") or "")
            for c in ("HL", "LL", "HH", "LH")
        ]
        for t in texts:
            for n in NAME_PAT.findall(t):
                if n not in NAME_STOPWORDS:
                    names[n].add(sid)

    for n, sids in sorted(names.items()):
        if len(sids) > 1:
            failures.append(f"cross-seed duplicate source name {n!r}: {sorted(sids)}")

    if failures:
        print(f"LINT FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("lint OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

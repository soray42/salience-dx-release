"""Screen a batch of expanded scenarios for repeated structure and empty cues.

A single long generation run produced scenarios that pass the structural checks but reuse a
few sentence frames with one noun phrase swapped, and cues with no content. This screen flags:
  T1. frame reuse: many scenarios share the first and last 8 words of the scenario text;
  T2. relevant-cue frames reused across scenarios ("the decisive evidence is specific: ...");
  T3. the relevant cue states its own conclusion ("this identifies <answer>");
  T4. an empty irrelevant cue: its label copied verbatim into the salient version, or a generic
      "a comparable ... elsewhere was attributed to ..." frame;
  T5. a first name used in more scenarios than a threshold (also against --existing dirs);
  T6. scenario text that describes the task instead of a case ("deciding factor before I").
(T1-T6 here number the screen's signals, not cue types.)

Exit 1 if a batch-level signal fires or any scenario carries a hard flag.

Usage:
  .venv/bin/python scripts/scan_seed_templating.py --dir <scenario_dir> [--existing <dir>,<dir>]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

XBASE_FRAME_MAX = 3          # >this many seeds sharing an xbase frame = collapse
NAME_MAX = 3                 # a first name on >this many seeds = reuse
HH_SKELETON_MAX = 3

META_PATTERNS = [
    r"\bdeciding factor before I\b",
    r"\bdiagnostic direction before I change\b",
    r"\bdecisive constraint before treating\b",
    r"\bpractical evidence that actually decides\b",
    r"\bone decisive technical signal\b",
    r"\bbefore treating any direction as primary\b",
    r"\bthe basic (facts|description) do(es)? not\b",
    r"\bnothing in the basic description settles\b",
    r"\bseveral (routine|explanations) .* (possible|live)\b",
]
# Generic salient-cue frames that carry no content. A plain "a comparable X elsewhere was
# attributed to Y" is not listed: with a concrete Y it is an acceptable plain version (as in the
# hand-written scenarios), and flagging it would hit good anecdote scenarios.
HOLLOW_HL_PATTERNS = [
    r"a classic .+ case after glancing",
    r"the outside explanation was\b",
    r"saw a highly similar .+ at another organization",
    r"\bdespite it not being established by the case-specific evidence\b",
    r"\bshould be treated as the (main|primary) (diagnosis|choice|explanation)\b",
]
FOCAL_CONCLUSION = re.compile(r"\bthis identifies\b|\bas the primary explanation\b", re.I)
HH_SKELETON = re.compile(r"the decisive evidence is specific", re.I)

NAME_PAT = re.compile(
    r"\b([A-Z][a-z]{2,})\s+[A-Z][a-z]+\b"
)
NAME_STOP = {
    "The", "Our", "This", "That", "Store", "Company", "Taken", "Treating",
    "Several", "When", "After", "Before", "During", "From", "With", "Once",
    "Looking", "Checking", "Using", "Reading", "Given", "Watching", "Spot",
    "Listing", "Inspecting", "Measuring", "Timing", "Profiling", "Comparing",
    "Honestly", "Concretely", "Whenever", "Over", "Every", "Past", "Prior",
    "Buy", "Permit", "Monday", "Saturday", "Saturdays", "Europe", "Shift",
    "Headers", "Secure", "Bad", "Too", "First", "Only",
    # product / tech proper nouns the role-trigger regex can mistake for a name
    "Redis", "Docker", "React", "App", "Background", "Requests", "Mbps",
    "Prometheus", "Safari", "Kafka", "Postgres", "Android", "Jenkins",
}


def wc(t: str) -> int:
    return len(str(t).replace("{DS}", "").replace("—", " ").split())


def xbase_frame(xb: str) -> str:
    xb = " ".join(str(xb).replace("{DS}", "").split()).lower()
    w = re.sub(r"[^a-z0-9 ]", "", xb).split()
    if len(w) <= 16:
        return " ".join(w)
    return " ".join(w[:8]) + " … " + " ".join(w[-8:])


def load_seeds(d: Path) -> list[dict]:
    out = []
    for p in sorted(d.glob("T*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and doc.get("seed_id"):
                out.append(doc)
        except yaml.YAMLError:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--existing", default="",
                    help="comma-separated dirs under data/pilot/feature_curation to "
                         "include for cross-bank name dedup")
    args = ap.parse_args()

    seeds = load_seeds(args.dir)
    if not seeds:
        print(f"no seeds in {args.dir}", file=sys.stderr)
        return 1

    existing_names: set = set()
    fc = REPO_ROOT / "data" / "pilot" / "feature_curation"
    for sub in [s for s in args.existing.split(",") if s]:
        for s in load_seeds(fc / sub):
            texts = [str(s.get("xbase", ""))] + [
                str(s.get("variants", {}).get(c, {}).get("distractor", "") or "")
                for c in ("HL", "LL", "HH", "LH")]
            for t in texts:
                for n in NAME_PAT.findall(t):
                    if n not in NAME_STOP:
                        existing_names.add(n)

    frames: dict[str, list[str]] = defaultdict(list)
    hh_skel = 0
    names: Counter = Counter()
    per_seed_flags: dict[str, list[str]] = defaultdict(list)

    for s in seeds:
        sid = s["seed_id"]
        v = s.get("variants", {})
        xb = str(s.get("xbase", ""))
        hl = str(v.get("HL", {}).get("distractor", ""))
        ll = str(v.get("LL", {}).get("distractor", ""))
        hh = str(v.get("HH", {}).get("distractor", ""))
        lh = str(v.get("LH", {}).get("distractor", ""))
        focal = str(s.get("focal_diagnostic_feature", ""))

        frames[xbase_frame(xb)].append(sid)

        if HH_SKELETON.search(hh):
            hh_skel += 1
            per_seed_flags[sid].append("T2:HH-skeleton('decisive evidence is specific')")
        if FOCAL_CONCLUSION.search(focal):
            per_seed_flags[sid].append("T3:focal-states-conclusion")
        if FOCAL_CONCLUSION.search(lh) or FOCAL_CONCLUSION.search(hh):
            per_seed_flags[sid].append("T3:focal-cell-states-conclusion")
        for pat in META_PATTERNS:
            if re.search(pat, xb, re.I):
                per_seed_flags[sid].append(f"T6:meta-scaffold(/{pat[:24]}/)")
                break
        for pat in HOLLOW_HL_PATTERNS:
            if re.search(pat, hl + " " + ll, re.I):
                per_seed_flags[sid].append("T4:hollow-distractor-frame")
                break
        # bare-noun distractor echoed: label appears verbatim in HL wrapped as "classic <label>"
        label = str(s.get("distractor_direction", {}).get("label", "")).strip()
        if label and re.search(r"classic\s+" + re.escape(label) + r"\s+case", hl, re.I):
            per_seed_flags[sid].append("T4:label-echoed-as-classic-case")

        # names (first names) in this seed's surfaced text
        for t in (xb, hl, ll, hh, lh):
            for n in NAME_PAT.findall(t):
                if n not in NAME_STOP:
                    names[n] += 1

    # batch-level signals
    batch_fail: list[str] = []
    collapsed_frames = {f: ids for f, ids in frames.items() if len(ids) > XBASE_FRAME_MAX}
    if collapsed_frames:
        for f, ids in sorted(collapsed_frames.items(), key=lambda x: -len(x[1])):
            batch_fail.append(f"xbase frame shared by {len(ids)} seeds (max {XBASE_FRAME_MAX}): "
                              f"{ids[:6]}{'…' if len(ids) > 6 else ''} | {f[:70]}")
    if hh_skel > HH_SKELETON_MAX:
        batch_fail.append(f"HH 'decisive evidence is specific' skeleton in {hh_skel} seeds "
                          f"(max {HH_SKELETON_MAX})")
    reused = {n: c for n, c in names.items() if c > NAME_MAX}
    for n, c in sorted(reused.items(), key=lambda x: -x[1]):
        batch_fail.append(f"first name {n!r} reused across {c} seeds (max {NAME_MAX})")
    cross = {n for n in names if n in existing_names}
    if cross:
        batch_fail.append(f"names colliding with existing bank: {sorted(cross)}")

    hard_seeds = {sid for sid, fl in per_seed_flags.items() if fl}

    n = len(seeds)
    print(f"scanned {n} seeds in {args.dir}")
    print(f"distinct xbase frames: {len(frames)} / {n}")
    print(f"seeds with >=1 hollowness/templating flag: {len(hard_seeds)} / {n}")
    if per_seed_flags:
        print("per-seed flags:")
        for sid in sorted(per_seed_flags):
            print(f"  {sid}: {', '.join(per_seed_flags[sid])}")
    if batch_fail:
        print(f"\nBATCH-LEVEL COLLAPSE SIGNALS ({len(batch_fail)}):")
        for b in batch_fail:
            print(f"  - {b}")

    if batch_fail or hard_seeds:
        print("\nRESULT: TEMPLATING/HOLLOWNESS DETECTED")
        return 1
    print("\nRESULT: clean (no templating/hollowness signals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

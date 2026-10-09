#!/usr/bin/env python3
"""Progress check for the LLM-annotator labelling.

Reads the packet chunks and whatever label files exist, and reports per-chunk completion and the
remaining item ids. A label line counts as done only if it parses and covers every expected
letter of its item.

Writes analysis/human_val/remaining.json  {chunk: [item_id, ...]}.

Usage: .venv/bin/python scripts/human_val_status.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HV = REPO / "analysis/human_val"
KEY = HV / "key.json"


def expected_letters_by_item():
    """item_id -> set(expected letters) from the packet chunks."""
    exp = {}
    chunk_of = {}
    for cf in sorted(HV.glob("packet_chunk*.jsonl")):
        ci = cf.stem.replace("packet_chunk", "")
        for line in cf.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            exp[r["item_id"]] = set(r["expected_letters"])
            chunk_of[r["item_id"]] = ci
    return exp, chunk_of


def done_items(exp):
    """Return set of item_ids with a valid, complete label line."""
    done = set()
    bad = 0
    for lf in sorted(HV.glob("proxy_labels_chunk*.ndjson")):
        for line in lf.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                iid = r["item_id"]
                letters = {lab["direction_id"] for lab in r["labels"]}
                roles_ok = all(
                    lab.get("role_in_final_answer") in ("primary", "considered_rejected", "absent")
                    for lab in r["labels"]
                )
                if iid in exp and exp[iid] <= letters and roles_ok:
                    done.add(iid)
                else:
                    bad += 1
            except (json.JSONDecodeError, KeyError, TypeError):
                bad += 1
    return done, bad


def main():
    if not KEY.exists():
        sys.exit("run scripts/human_val_sample.py first")
    exp, chunk_of = expected_letters_by_item()
    done, bad = done_items(exp)

    remaining = {}
    per_chunk = {}
    for iid, ci in chunk_of.items():
        per_chunk.setdefault(ci, [0, 0])
        per_chunk[ci][1] += 1
        if iid in done:
            per_chunk[ci][0] += 1
        else:
            remaining.setdefault(ci, []).append(iid)

    print(f"total: {len(done)}/{len(exp)} items done"
          + (f"  ({bad} malformed lines ignored)" if bad else ""))
    for ci in sorted(per_chunk):
        d, t = per_chunk[ci]
        flag = "  <-- resume" if d < t else "  done"
        print(f"  chunk{ci}: {d}/{t}{flag}")
    (HV / "remaining.json").write_text(json.dumps(remaining, indent=1))
    if remaining:
        print(f"\nwrote analysis/human_val/remaining.json ({sum(len(v) for v in remaining.values())} items left)")
    else:
        print("\nALL DONE -> run scripts/human_val_analyze.py")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the packet for the human annotation study of the judge's labels.

  * Annotators label the role of every candidate explanation in the model's final answer
    (primary / considered_rejected / absent = adopted / rejected / ignored), as the judge did.
  * Items carry opaque ids and a letter arrangement independent of the judge's and of the LLM
    annotator's; the condition and the judge's label are not shown before an item is committed.
  * Default sample: 75 random (scenario, model) pairs from the main run, plain (LL) and salient
    (HL) answers of each, i.e. 150 items, so pair outcomes can be derived from the labels.
  * --from-packet reuses the 186 items of the LLM-annotator packet (analysis/human_val) instead.

Outputs (analysis/human_gold/):
  packet.jsonl   the items shown by scripts/human_gold_tui.py
  key.json       hidden mapping: true id, condition, letter -> candidate, judge roles
  meta.json      sampling parameters and sha256 of packet, key and rubric

The released packet is the one the annotators labelled.

Usage:
  .venv/bin/python scripts/human_gold_sample.py                # 75 pairs, 150 items
  .venv/bin/python scripts/human_gold_sample.py --n-pairs 100
  .venv/bin/python scripts/human_gold_sample.py --from-packet
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C  # noqa: E402
from scripts.run_judge_v4 import (  # noqa: E402
    build_direction_list,
    shuffled_directions,
    build_directions_block,
)
from scripts.human_val_sample import load_responses, template_of, sha  # noqa: E402

V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
SEED_DIR = REPO / "data/pilot/feature_curation/inputs_full500"
RUBRIC = REPO / "prompts/v4.3/judge_categorical_v3_1.md"
HV = REPO / "analysis/human_val"
OUT = REPO / "analysis/human_gold"
TAG = "human-gold-v1"      # distinct shuffle tag -> arrangement independent of judge/proxy
MODELS = C.MODELS_WAVE2


def build_item(seed_id, model, cell, resp_lut, seed_cache):
    resp = resp_lut.get((seed_id, model, cell))
    if resp is None:
        return None
    if seed_id not in seed_cache:
        seed_cache[seed_id] = yaml.safe_load((SEED_DIR / f"{seed_id}.yaml").read_text(encoding="utf-8"))
    seed = seed_cache[seed_id]
    directions = build_direction_list(seed)
    shuffled, letter_to_canonical = shuffled_directions(directions, seed_id, TAG)
    true_id = f"{seed_id}|{model}|{cell}"
    packet = {
        "item_id": true_id,                      # replaced by an opaque id below
        "scenario": resp.get("prompt", ""),
        "final_answer": resp.get("final_answer", "") or "",
        "cot": resp.get("cot", "") or "",
        "directions_block": build_directions_block(shuffled),
        "expected_letters": [d["letter"] for d in shuffled],
    }
    letters_by_canon = {}
    for letter, canon in letter_to_canonical.items():
        letters_by_canon.setdefault(canon, letter)
    key_entry = {
        "true_id": true_id,
        "seed": seed_id,
        "model": model,
        "cell": cell,
        "template": template_of(seed_id),
        "complexity": seed.get("complexity"),
        "letter_to_canonical": letter_to_canonical,
        "distractor_letter": letters_by_canon.get("distractor"),
        "focal_letter": letters_by_canon.get("focal"),
        "has_cot": bool(resp.get("cot")),
    }
    return packet, key_entry


def proxy_roles():
    """opaque hv id -> (distractor_role, focal_role) from the proxy labels, if present."""
    try:
        from scripts.human_val_analyze import load_proxy_labels, role_for
    except Exception:
        return {}
    if not list(HV.glob("proxy_labels_chunk*.ndjson")):
        return {}
    labels = load_proxy_labels()
    key = json.loads((HV / "key.json").read_text(encoding="utf-8"))
    out = {}
    for hv_id, entry in key.items():
        lr = labels.get(hv_id)
        if lr is None:
            continue
        l2c = entry["proxy_letter_to_canonical"]
        out[hv_id] = (role_for("distractor", l2c, lr), role_for("focal", l2c, lr))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-pairs", type=int, default=75, help="random (seed, model) pairs; x2 cells = items")
    ap.add_argument("--cells", default="LL,HL", help="cells per pair (default LL,HL; add LH for the relevant control)")
    ap.add_argument("--seed", default="human-gold-sampling-v1")
    ap.add_argument("--from-packet", action="store_true", help="reuse the 186-item proxy packet items")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out_dir = Path(args.out)
    rng = random.Random(args.seed)
    cells = [c.strip() for c in args.cells.split(",") if c.strip()]

    recs, _ = C.load_judge_records(V31)
    resp_lut = load_responses()
    seed_cache: dict = {}

    units: list[tuple] = []   # (seed, model, cell, pair_bucket, hv_id)
    proxy = {}
    if args.from_packet:
        hv_key = json.loads((HV / "key.json").read_text(encoding="utf-8"))
        proxy = proxy_roles()
        for hv_id, e in hv_key.items():
            units.append((e["seed"], e["model"], e["cell"], e["pair_bucket"], hv_id))
        mode = {"mode": "from_proxy_packet", "source": "analysis/human_val/key.json"}
    else:
        rows = [r for r in C.build_pair_table(recs, models=MODELS) if r["bucket"] != "missing"]
        rng.shuffle(rows)
        chosen = rows[: args.n_pairs]
        for r in chosen:
            for cell in cells:
                units.append((r["seed_id"], r["model"], cell, r["bucket"], None))
        mode = {"mode": "random_pairs", "n_pairs": args.n_pairs, "cells": cells, "rng_seed": args.seed}

    packets, keys = [], {}
    for seed_id, model, cell, bucket, hv_id in units:
        built = build_item(seed_id, model, cell, resp_lut, seed_cache)
        if built is None:
            continue
        packet, entry = built
        rec = recs.get((seed_id, model, cell))
        entry["deepseek_distractor_role"] = C.distractor_role(rec) if rec else None
        entry["deepseek_focal_role"] = C.focal_role(rec) if rec else None
        entry["pair_bucket"] = bucket
        if hv_id:
            entry["proxy_item_id"] = hv_id
            pr = proxy.get(hv_id)
            if pr:
                entry["proxy_distractor_role"], entry["proxy_focal_role"] = pr
        packets.append(packet)
        keys[packet["item_id"]] = entry

    rng.shuffle(packets)
    blinded = {}
    for i, pk in enumerate(packets):
        opaque = f"hg-{i:04d}"
        blinded[opaque] = keys[pk["item_id"]]
        pk["item_id"] = opaque

    out_dir.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(x, ensure_ascii=False) for x in packets) + "\n"
    (out_dir / "packet.jsonl").write_text(body, encoding="utf-8")
    key_text = json.dumps(blinded, ensure_ascii=False, indent=2)
    (out_dir / "key.json").write_text(key_text, encoding="utf-8")
    meta = {
        **mode,
        "n_items": len(packets),
        "models": MODELS,
        "shuffle_tag": TAG,
        "rubric_path": str(RUBRIC.relative_to(REPO)),
        "rubric_sha256": sha(RUBRIC.read_text(encoding="utf-8")),
        "v31_source": str(V31.relative_to(REPO)),
        "packet_sha256": sha(body),
        "key_sha256": sha(key_text),
        "cell_counts": dict(Counter(e["cell"] for e in blinded.values())),
        "model_counts": dict(Counter(e["model"] for e in blinded.values())),
        "pair_bucket_counts": dict(Counter(e["pair_bucket"] for e in blinded.values())),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {len(packets)} items -> {out_dir / 'packet.jsonl'}")
    print("cells:", meta["cell_counts"], "| models:", meta["model_counts"])
    print("pair buckets:", meta["pair_bucket_counts"])


if __name__ == "__main__":
    main()

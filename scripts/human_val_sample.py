#!/usr/bin/env python3
"""Build the packet for the LLM-annotator check of the judge's labels.

1. Loads the main-run judge labels (rubric v3.1) and builds the plain/salient pair table.
2. Draws a stratified sample of 62 pairs: 15 adoption flips, 15 rejection flips, 8 pairs in
   which the plain answer ignores the cue and the salient answer adopts or rejects it, and 24
   stable pairs, spread over the 4 models and 5 cue types.
3. For every sampled pair writes the plain (LL), salient (HL) and relevant-control (LH) items.
   Each item holds the scenario, the model's answer and a freshly shuffled candidate list; the
   annotator is not shown the condition, the candidates' roles or the judge's label.
4. Writes the packet in chunks, a hidden key and a meta file with sha256 hashes and the
   sampling parameters.

Agreement is computed on each candidate's identity (the irrelevant cue, the relevant cue), so
the annotator's letter arrangement need not match the judge's. The released packet is the one
that was labelled.

Usage: .venv/bin/python scripts/human_val_sample.py [--n-chunks 6]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C
from scripts.run_judge_v4 import (
    build_direction_list,
    shuffled_directions,
    build_directions_block,
    build_model_response_text,
)

V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
RESPONSES = REPO / "data/full/free_response.ndjson"
SEED_DIR = REPO / "data/pilot/feature_curation/inputs_full500"
OUT = REPO / "analysis/human_val"
RUBRIC = REPO / "prompts/v4.3/judge_categorical_v3_1.md"

MODELS = C.MODELS_WAVE2
# Shuffle tag for the annotator packet; it differs from every judge id, so the letter
# arrangement differs from the judge's.
PROXY_TAG = "proxy5-humanval-v1"
RNG = random.Random("humanval-sampling-v1")

# Pairs per pair outcome. Flips (about 7-11% each in the main run) are over-sampled, so
# agreement on this sample is not a population estimate.
BUDGET = {
    "ISB": 15,
    "vigilance": 15,
    "proto_ISB": 4,
    "proto_vigilance": 4,
    "stable_adopt": 12,
    "stable_reject": 12,
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_responses() -> dict[tuple[str, str, str], dict]:
    lut: dict[tuple[str, str, str], dict] = {}
    with RESPONSES.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("status") != "ok":
                continue
            lut[(r["seed_id"], r["model"], r["cell"])] = r
    return lut


def template_of(seed_id: str) -> str:
    return seed_id.split("-")[0]


def stratified_pairs(rows: list[dict]) -> list[dict]:
    """Pick pairs per bucket up to BUDGET, spread across models/templates."""
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["bucket"] in BUDGET:
            by_bucket[r["bucket"]].append(r)

    chosen: list[dict] = []
    for bucket, cap in BUDGET.items():
        pool = by_bucket.get(bucket, [])
        # round-robin over (model,template) cells for spread
        cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in pool:
            cells[(r["model"], r["template"])].append(r)
        for lst in cells.values():
            RNG.shuffle(lst)
        cell_keys = list(cells.keys())
        RNG.shuffle(cell_keys)
        picked: list[dict] = []
        i = 0
        while len(picked) < min(cap, len(pool)) and cell_keys:
            k = cell_keys[i % len(cell_keys)]
            if cells[k]:
                picked.append(cells[k].pop())
            else:
                cell_keys.remove(k)
                if not cell_keys:
                    break
                continue
            i += 1
        chosen.extend(picked)
    return chosen


def build_item(seed_id: str, model: str, cell: str, resp_lut, seed_cache):
    key = (seed_id, model, cell)
    resp = resp_lut.get(key)
    if resp is None:
        return None
    if seed_id not in seed_cache:
        seed_cache[seed_id] = yaml.safe_load((SEED_DIR / f"{seed_id}.yaml").read_text(encoding="utf-8"))
    seed = seed_cache[seed_id]
    directions = build_direction_list(seed)
    shuffled, letter_to_canonical = shuffled_directions(directions, seed_id, PROXY_TAG)
    item_id = f"{seed_id}|{model}|{cell}"
    scenario = resp.get("prompt", "")
    model_response = build_model_response_text(resp)
    has_cot = bool(resp.get("cot"))
    packet = {
        "item_id": item_id,
        "scenario": scenario,
        "model_response": model_response,
        "directions_block": build_directions_block(shuffled),
        "expected_letters": [d["letter"] for d in shuffled],
        "has_cot": has_cot,
    }
    key_entry = {
        "item_id": item_id,
        "seed": seed_id,
        "model": model,
        "cell": cell,
        "template": template_of(seed_id),
        "complexity": seed.get("complexity"),
        "proxy_letter_to_canonical": letter_to_canonical,
        "has_cot": has_cot,
    }
    return packet, key_entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-chunks", type=int, default=6)
    args = ap.parse_args()

    recs, _ = C.load_judge_records(V31)
    rows = C.build_pair_table(recs, models=MODELS)
    resp_lut = load_responses()

    pairs = stratified_pairs(rows)
    print(f"sampled {len(pairs)} pairs; bucket counts:",
          dict(Counter(p["bucket"] for p in pairs)))

    seed_cache: dict = {}
    packets: list[dict] = []
    keys: dict[str, dict] = {}
    for p in pairs:
        seed_id, model, bucket = p["seed_id"], p["model"], p["bucket"]
        for cell in ("LL", "HL", "LH"):
            built = build_item(seed_id, model, cell, resp_lut, seed_cache)
            if built is None:
                continue
            packet, key_entry = built
            # record the DeepSeek label (canonical roles) for this cell
            rec = recs.get((seed_id, model, cell))
            key_entry["deepseek_distractor_role"] = C.distractor_role(rec) if rec else None
            key_entry["deepseek_focal_role"] = C.focal_role(rec) if rec else None
            key_entry["pair_bucket"] = bucket
            packets.append(packet)
            keys[packet["item_id"]] = key_entry

    RNG.shuffle(packets)

    # Blind the visible id: the true "seed|model|cell" id leaks the condition.
    # Replace with an opaque id in the packet; the key retains the true mapping.
    blinded_keys: dict[str, dict] = {}
    for i, pk in enumerate(packets):
        opaque = f"hv-{i:04d}"
        true_id = pk["item_id"]
        pk["item_id"] = opaque
        entry = keys[true_id]
        entry["true_id"] = true_id
        blinded_keys[opaque] = entry
    keys = blinded_keys

    OUT.mkdir(parents=True, exist_ok=True)

    # chunk
    n = args.n_chunks
    chunks: list[list[dict]] = [[] for _ in range(n)]
    for i, pk in enumerate(packets):
        chunks[i % n].append(pk)
    chunk_hashes = {}
    for ci, ch in enumerate(chunks):
        path = OUT / f"packet_chunk{ci+1}.jsonl"
        body = "\n".join(json.dumps(x, ensure_ascii=False) for x in ch) + "\n"
        path.write_text(body, encoding="utf-8")
        chunk_hashes[path.name] = {"n_items": len(ch), "sha256": sha(body)}

    (OUT / "key.json").write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {
        "n_pairs": len(pairs),
        "n_items": len(packets),
        "n_chunks": n,
        "models": MODELS,
        "budget": BUDGET,
        "proxy_tag": PROXY_TAG,
        "rubric_path": str(RUBRIC.relative_to(REPO)),
        "rubric_sha256": sha(RUBRIC.read_text(encoding="utf-8")),
        "v31_source": str(V31.relative_to(REPO)),
        "chunks": chunk_hashes,
        "key_sha256": sha((OUT / "key.json").read_text(encoding="utf-8")),
        "bucket_counts": dict(Counter(p["bucket"] for p in pairs)),
        "item_bucket_counts": dict(Counter(k["pair_bucket"] for k in keys.values())),
        "cell_counts": dict(Counter(k["cell"] for k in keys.values())),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {len(packets)} items -> {n} chunks under {OUT}")
    print("cells:", meta["cell_counts"])
    print("item buckets:", meta["item_bucket_counts"])


if __name__ == "__main__":
    main()

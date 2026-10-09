#!/usr/bin/env python3
"""Score the LLM annotator against the judge (rubric v3.1).

Reads:
  analysis/human_val/key.json                    hidden mapping from item to scenario
  analysis/human_val/proxy_labels_chunk*.ndjson  the annotator's labels, one JSON object per
       line: {"item_id": ..., "labels": [{direction_id, role_in_final_answer, ...}, ...]}

On the irrelevant cue's role (final answer; adopted / rejected / ignored) over the shared items:
  * % agreement with a scenario-clustered bootstrap CI;
  * Gwet's AC1 with CI, and Cohen's kappa (the two diverge when one label dominates);
  * the same on the relevant cue's role.
Then derives adoption flips, rejection flips and relevant-cue adoption from the annotator's
labels with the same classify_pair logic, and reports pair-outcome agreement with the judge.

Usage: .venv/bin/python scripts/human_val_analyze.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

HV = REPO / "analysis/human_val"
KEY = HV / "key.json"
OUT = HV / "human_val_results.json"
ROLES = ("primary", "considered_rejected", "absent")
RNG = random.Random("humanval-analyze-v1")


# ---------------------------------------------------------------- agreement
def gwet_ac1(a: list[str], b: list[str], cats=ROLES) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    q = len(cats)
    pa = sum(1 for x, y in zip(a, b) if x == y) / n
    pi = {}
    for k in cats:
        nk = sum(1 for x in a if x == k) + sum(1 for y in b if y == k)
        pi[k] = nk / (2 * n)
    pe = sum(pi[k] * (1 - pi[k]) for k in cats) / (q - 1)
    return (pa - pe) / (1 - pe) if pe != 1 else float("nan")


def cohen_kappa(a: list[str], b: list[str], cats=ROLES) -> float:
    return C.cohens_kappa(a, b)


def pct_agree(a: list[str], b: list[str]) -> float:
    return sum(1 for x, y in zip(a, b) if x == y) / len(a) if a else float("nan")


def boot_ci(items, stat_fn, n_boot=5000):
    """Seed-clustered bootstrap. items = list of (seed, a_label, b_label)."""
    by_seed: dict[str, list] = defaultdict(list)
    for s, x, y in items:
        by_seed[s].append((x, y))
    seeds = list(by_seed)
    if not seeds:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(n_boot):
        a2, b2 = [], []
        for _ in range(len(seeds)):
            s = seeds[RNG.randrange(len(seeds))]
            for x, y in by_seed[s]:
                a2.append(x); b2.append(y)
        stats.append(stat_fn(a2, b2))
    stats = [s for s in stats if s == s]  # drop nan
    stats.sort()
    if not stats:
        return (float("nan"), float("nan"))
    lo = stats[int(0.025 * len(stats))]
    hi = stats[int(0.975 * len(stats)) - 1]
    return (round(lo, 3), round(hi, 3))


# ---------------------------------------------------------------- load proxy
def load_proxy_labels() -> dict[str, dict[str, str]]:
    """opaque item_id -> {letter: role_in_final_answer}."""
    out: dict[str, dict[str, str]] = {}
    files = sorted(HV.glob("proxy_labels_chunk*.ndjson"))
    if not files:
        sys.exit("no proxy_labels_chunk*.ndjson found in analysis/human_val/")
    n_lines = n_bad = 0
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            try:
                rec = json.loads(line)
                iid = rec["item_id"]
                m = {}
                for lab in rec["labels"]:
                    m[lab["direction_id"]] = lab["role_in_final_answer"]
                out[iid] = m
            except (json.JSONDecodeError, KeyError, TypeError):
                n_bad += 1
    print(f"loaded {len(out)} proxy items ({n_lines} lines, {n_bad} unparseable)")
    return out


def role_for(canon: str, l2c: dict[str, str], letter_roles: dict[str, str]):
    """Resolve the proxy role for the letter whose canonical role == canon."""
    for letter, c in l2c.items():
        if c == canon:
            return letter_roles.get(letter)
    return None


def main():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    proxy = load_proxy_labels()

    # ---- item-level distractor & focal agreement
    dist_items, focal_items = [], []
    proxy_dist: dict[tuple[str, str, str], str] = {}   # (seed,model,cell)->role
    proxy_focal: dict[tuple[str, str, str], str] = {}
    missing = 0
    for iid, entry in key.items():
        lr = proxy.get(iid)
        if lr is None:
            missing += 1
            continue
        l2c = entry["proxy_letter_to_canonical"]
        f_dist = role_for("distractor", l2c, lr)
        f_focal = role_for("focal", l2c, lr)
        smc = (entry["seed"], entry["model"], entry["cell"])
        if f_dist is not None:
            proxy_dist[smc] = f_dist
        if f_focal is not None:
            proxy_focal[smc] = f_focal
        d_dist = entry.get("deepseek_distractor_role")
        d_focal = entry.get("deepseek_focal_role")
        if f_dist in ROLES and d_dist in ROLES:
            dist_items.append((entry["seed"], d_dist, f_dist))
        if f_focal in ROLES and d_focal in ROLES:
            focal_items.append((entry["seed"], d_focal, f_focal))

    def block(items, name):
        a = [x for _, x, _ in items]
        b = [x for _, _, x in items]
        res = {
            "n": len(items),
            "pct_agree": round(100 * pct_agree(a, b), 1),
            "pct_agree_ci": [round(100 * v, 1) for v in boot_ci(items, pct_agree)],
            "gwet_ac1": round(gwet_ac1(a, b), 3),
            "gwet_ac1_ci": boot_ci(items, gwet_ac1),
            "cohen_kappa_paradox_ref": round(cohen_kappa(a, b), 3),
            "deepseek_dist": dict(Counter(a)),
            "proxy_dist": dict(Counter(b)),
            "confusion": {f"judge={x}|proxy={y}": sum(1 for s, u, v in items if u == x and v == y)
                          for x in ROLES for y in ROLES
                          if sum(1 for s, u, v in items if u == x and v == y)},
        }
        print(f"\n[{name}]  n={res['n']}  agree={res['pct_agree']}% "
              f"CI{res['pct_agree_ci']}  AC1={res['gwet_ac1']} CI{res['gwet_ac1_ci']}  "
              f"(Cohen kappa ref={res['cohen_kappa_paradox_ref']})")
        return res

    print(f"item overlap: distractor n={len(dist_items)}, focal n={len(focal_items)}, "
          f"missing proxy items={missing}")
    out = {
        "n_key_items": len(key),
        "n_proxy_items": len(proxy),
        "missing": missing,
        "distractor_role": block(dist_items, "irrelevant-cue role"),
        "focal_role": block(focal_items, "relevant-cue role"),
    }

    # ---- pair outcomes from the annotator's labels, and agreement with the judge's
    pairs = defaultdict(dict)   # (seed,model)->{cell:role}
    for (s, m, c), r in proxy_dist.items():
        pairs[(s, m)][c] = r
    proxy_buckets, ds_buckets = {}, {}
    seen_pairs = set()
    for iid, entry in key.items():
        seen_pairs.add((entry["seed"], entry["model"], entry["pair_bucket"]))
    # dedupe pair->bucket from key
    pair_ds_bucket = {(s, m): b for (s, m, b) in seen_pairs}
    for (s, m), cells in pairs.items():
        ll, hl = cells.get("LL"), cells.get("HL")
        if ll is None or hl is None:
            continue
        proxy_buckets[(s, m)] = C.classify_pair(ll, hl)
        ds_buckets[(s, m)] = pair_ds_bucket.get((s, m))

    common = [k for k in proxy_buckets if ds_buckets.get(k) is not None]
    ann_b = [proxy_buckets[k] for k in common]
    db = [ds_buckets[k] for k in common]
    bucket_agree = sum(1 for x, y in zip(ann_b, db) if x == y) / len(common) if common else float("nan")
    ann_isb = sum(1 for x in ann_b if x == "ISB")
    ann_vig = sum(1 for x in ann_b if x == "vigilance")

    # relevant-cue adoption in the LH items, from the annotator's labels
    lh_focal = [r for (s, m, c), r in proxy_focal.items() if c == "LH"]
    dfa = sum(1 for r in lh_focal if r == "primary")

    out["pair_rederivation"] = {
        "n_pairs_with_both_cells": len(common),
        "pair_bucket_agreement_pct": round(100 * bucket_agree, 1),
        "proxy_ISB_n": ann_isb, "proxy_vig_n": ann_vig,
        "proxy_bucket_dist": dict(Counter(ann_b)),
        "deepseek_bucket_dist": dict(Counter(db)),
        "DFA_proxy": {"k": dfa, "n": len(lh_focal),
                      "pct": round(100 * dfa / len(lh_focal), 1) if lh_focal else None},
        "note": "Counts on the labelled sample, in which flips are over-sampled; not population rates.",
    }
    print(f"\n[pair outcomes]  pairs={len(common)}  "
          f"bucket-agree={out['pair_rederivation']['pair_bucket_agreement_pct']}%  "
          f"proxy ISB={ann_isb} vig={ann_vig}  DFA={out['pair_rederivation']['DFA_proxy']}")

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

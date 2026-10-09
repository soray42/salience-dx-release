#!/usr/bin/env python3
"""Score the human annotation study: each annotator against the judge, the annotators against
each other, and (for a packet built with --from-packet) the annotators against the LLM annotator.

Reads analysis/human_gold/{key.json, packet.jsonl, annot_*.ndjson}.
Writes analysis/human_gold/human_gold_results.json.

Reported on the irrelevant cue's role (the label that defines flips):
  * per annotator: % agreement with the judge, Gwet's AC1 with a scenario-clustered bootstrap
    CI, Cohen's kappa, and the same for the relevant cue's role;
  * pair outcomes derived from the annotator's labels and their agreement with the judge's;
  * agreement on the irrelevant cue's role by condition (plain / salient);
  * between annotators: pairwise % agreement and AC1, three-annotator AC1, and AC1 with the
    judge added as a fourth annotator;
  * the majority label (at least two annotators agree) against the judge, and the pair outcomes
    derived from majority labels.

Usage: .venv/bin/python scripts/human_gold_analyze.py [--dir analysis/human_gold]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C  # noqa: E402
from scripts.human_val_analyze import gwet_ac1, pct_agree, boot_ci, ROLES  # noqa: E402

HG = REPO / "analysis/human_gold"


def load_annotators(d: Path, expected: dict[str, list[str]]) -> dict[str, dict[str, dict[str, str]]]:
    """annotator -> item_id -> {letter: role} (complete, non-skipped lines only)."""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for f in sorted(d.glob("annot_*.ndjson")):
        name = f.stem.replace("annot_", "")
        items: dict[str, dict[str, str]] = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("skipped"):
                continue
            got = {lab["direction_id"]: lab["role_in_final_answer"] for lab in rec.get("labels", [])}
            need = expected.get(rec.get("item_id"), [])
            if need and all(got.get(k) in ROLES for k in need):
                items[rec["item_id"]] = got
        out[name] = items
    return out


def timing(path: Path, key: dict, dist: dict[str, str], gap_minutes: float = 30.0) -> dict:
    """Time spent per annotator, and agreement with the judge on the irrelevant cue's role in each
    sitting (a new sitting starts where consecutive commits are more than gap_minutes apart)."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("item_id") in dist and r.get("timestamp"):
            rows.append(r)
    rows.sort(key=lambda r: datetime.fromisoformat(r["timestamp"]))
    secs = [r["seconds"] for r in rows]
    sittings, cur, last = [], [], None
    for r in rows:
        t = datetime.fromisoformat(r["timestamp"])
        if last is not None and (t - last).total_seconds() > 60 * gap_minutes:
            sittings.append(cur)
            cur = []
        cur.append(r)
        last = t
    if cur:
        sittings.append(cur)

    def agree(rs):
        scored = [r for r in rs if key[r["item_id"]].get("deepseek_distractor_role") in ROLES]
        return {"n_items": len(scored),
                "agree_with_judge": sum(1 for r in scored
                                        if dist[r["item_id"]] == key[r["item_id"]]["deepseek_distractor_role"])}

    return {"minutes_total": round(sum(secs) / 60, 1),
            "median_seconds_per_item": round(statistics.median(secs), 1),
            "items_under_5_seconds": sum(1 for x in secs if x < 5),
            "sittings": [agree(x) for x in sittings]}


def multi_rater_ac1(rows: list[list[str]], cats=ROLES) -> float:
    """Gwet AC1 for r raters per item (rows = per-item lists of labels, equal length)."""
    rows = [r for r in rows if len(r) >= 2]
    if not rows:
        return float("nan")
    q = len(cats)
    pa_terms, pi_sum = [], {k: 0.0 for k in cats}
    for r in rows:
        n = len(r)
        cnt = Counter(r)
        pa_terms.append(sum(c * (c - 1) for c in cnt.values()) / (n * (n - 1)))
        for k in cats:
            pi_sum[k] += cnt.get(k, 0) / n
    pa = sum(pa_terms) / len(rows)
    pi = {k: v / len(rows) for k, v in pi_sum.items()}
    pe = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    return (pa - pe) / (1 - pe) if pe != 1 else float("nan")


def agreement_block(items):
    """items = [(seed, ref_label, ann_label)]."""
    a = [x for _, x, _ in items]
    b = [x for _, _, x in items]
    if not items:
        return {"n": 0}
    return {
        "n": len(items),
        "pct_agree": round(100 * pct_agree(a, b), 1),
        "pct_agree_ci": [round(100 * v, 1) for v in boot_ci(items, pct_agree)],
        "gwet_ac1": round(gwet_ac1(a, b), 3),
        "gwet_ac1_ci": boot_ci(items, gwet_ac1),
        "cohen_kappa_ref": round(C.cohens_kappa(a, b), 3),
        "ref_dist": dict(Counter(a)),
        "annotator_dist": dict(Counter(b)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(HG))
    args = ap.parse_args()
    d = Path(args.dir)
    key = json.loads((d / "key.json").read_text(encoding="utf-8"))
    packet = [json.loads(l) for l in (d / "packet.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    expected = {it["item_id"]: it["expected_letters"] for it in packet}
    ann = load_annotators(d, expected)
    if not ann:
        sys.exit(f"no annot_*.ndjson under {d}")

    out: dict = {"n_items": len(key), "annotators": {}}
    dist_labels: dict[str, dict[str, str]] = {}      # annotator -> item -> distractor role

    for name, items in ann.items():
        dist_items, focal_items, proxy_items = [], [], []
        per_cell: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        dist_labels[name] = {}
        for iid, roles in items.items():
            e = key.get(iid)
            if not e:
                continue
            dl, fl = e.get("distractor_letter"), e.get("focal_letter")
            hd = roles.get(dl) if dl else None
            hf = roles.get(fl) if fl else None
            if hd:
                dist_labels[name][iid] = hd
                per_cell[(e["seed"], e["model"])][e["cell"]] = hd
                if e.get("deepseek_distractor_role") in ROLES:
                    dist_items.append((e["seed"], e["deepseek_distractor_role"], hd))
                if e.get("proxy_distractor_role") in ROLES:
                    proxy_items.append((e["seed"], e["proxy_distractor_role"], hd))
            if hf and e.get("deepseek_focal_role") in ROLES:
                focal_items.append((e["seed"], e["deepseek_focal_role"], hf))

        # pair outcomes from this annotator's labels
        judge_bucket = {(e["seed"], e["model"]): e.get("pair_bucket") for e in key.values()}
        hb, jb = [], []
        for (s, m), cells in per_cell.items():
            if "LL" in cells and "HL" in cells:
                hb.append(C.classify_pair(cells["LL"], cells["HL"]))
                jb.append(judge_bucket.get((s, m)))
        pair_block = {
            "n_pairs": len(hb),
            "pair_outcome_agreement_pct": round(100 * sum(1 for x, y in zip(hb, jb) if x == y) / len(hb), 1) if hb else None,
            "annotator_outcomes": dict(Counter(hb)),
            "judge_outcomes": dict(Counter(jb)),
        }
        # per-condition agreement on the cue role (plain = LL, salient = HL)
        cell_items = defaultdict(list)
        for iid, roles in items.items():
            e = key.get(iid)
            if not e or not e.get("distractor_letter"):
                continue
            hd = roles.get(e["distractor_letter"])
            if hd in ROLES and e.get("deepseek_distractor_role") in ROLES:
                cell_items[e["cell"]].append((e["seed"], e["deepseek_distractor_role"], hd))
        by_cell = {c: {"n": len(v), "pct_agree": round(100 * pct_agree([x for _, x, _ in v], [x for _, _, x in v]), 1)}
                   for c, v in cell_items.items()}
        blk = {
            "n_labelled_items": len(items),
            "distractor_role_vs_judge": agreement_block(dist_items),
            "distractor_role_vs_judge_by_condition": by_cell,
            "focal_role_vs_judge": agreement_block(focal_items),
            "pair_outcomes": pair_block,
        }
        if proxy_items:
            blk["distractor_role_vs_proxy"] = agreement_block(proxy_items)
        blk["timing"] = timing(d / f"annot_{name}.ndjson", key, dist_labels[name])
        out["annotators"][name] = blk
        db = blk["distractor_role_vs_judge"]
        print(f"[{name}] items={len(items)}  cue role vs judge: agree={db.get('pct_agree')}% AC1={db.get('gwet_ac1')} "
              f"CI{db.get('gwet_ac1_ci')}  pairs={pair_block['n_pairs']} outcome-agree={pair_block['pair_outcome_agreement_pct']}%")

    # inter-annotator
    names = sorted(dist_labels)
    inter = {"pairwise": {}, "multi_rater": {}}
    for a_, b_ in combinations(names, 2):
        common = [i for i in dist_labels[a_] if i in dist_labels[b_]]
        items = [(key[i]["seed"], dist_labels[a_][i], dist_labels[b_][i]) for i in common]
        inter["pairwise"][f"{a_}~{b_}"] = agreement_block(items)
    if len(names) >= 2:
        shared = [i for i in key if all(i in dist_labels[n] for n in names)]
        rows = [[dist_labels[n][i] for n in names] for i in shared]
        inter["multi_rater"] = {"n_items_all_annotators": len(shared), "n_annotators": len(names),
                                "gwet_ac1": round(multi_rater_ac1(rows), 3) if rows else None}
        # majority label vs judge
        maj_items = []
        for i in shared:
            cnt = Counter(dist_labels[n][i] for n in names)
            lab, c = cnt.most_common(1)[0]
            if c >= 2 and key[i].get("deepseek_distractor_role") in ROLES:
                maj_items.append((key[i]["seed"], key[i]["deepseek_distractor_role"], lab))
        inter["majority_vs_judge"] = agreement_block(maj_items)
        # AC1 with the judge added as a fourth annotator
        rows_j = [[dist_labels[n][i] for n in names] + [key[i]["deepseek_distractor_role"]]
                  for i in shared if key[i].get("deepseek_distractor_role") in ROLES]
        inter["multi_rater_with_judge"] = {"n_items": len(rows_j), "n_raters": len(names) + 1,
                                           "gwet_ac1": round(multi_rater_ac1(rows_j), 3) if rows_j else None}
        # mean judge-human vs mean human-human agreement on the cue role
        jh = [out["annotators"][n]["distractor_role_vs_judge"]["pct_agree"] for n in names
              if out["annotators"][n]["distractor_role_vs_judge"].get("n")]
        hh = [v["pct_agree"] for v in inter["pairwise"].values() if v.get("n")]
        inter["mean_pct_agree"] = {"judge_vs_human": round(sum(jh) / len(jh), 1) if jh else None,
                                   "human_vs_human": round(sum(hh) / len(hh), 1) if hh else None}
        # pair outcomes re-derived from the majority label (items with >=2 agreeing raters)
        maj_role = {}
        for i in shared:
            lab, c = Counter(dist_labels[n][i] for n in names).most_common(1)[0]
            if c >= 2:
                maj_role[i] = lab
        per_cell_m: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
        for i, lab in maj_role.items():
            e = key[i]
            per_cell_m[(e["seed"], e["model"])][e["cell"]] = lab
        judge_bucket = {(e["seed"], e["model"]): e.get("pair_bucket") for e in key.values()}
        mb, jb2 = [], []
        for (s, m), cells in per_cell_m.items():
            if "LL" in cells and "HL" in cells:
                mb.append(C.classify_pair(cells["LL"], cells["HL"]))
                jb2.append(judge_bucket.get((s, m)))
        inter["majority_pair_outcomes"] = {
            "n_pairs": len(mb),
            "pair_outcome_agreement_pct": round(100 * sum(1 for x, y in zip(mb, jb2) if x == y) / len(mb), 1) if mb else None,
            "majority_outcomes": dict(Counter(mb)), "judge_outcomes": dict(Counter(jb2)),
        }
        print(f"[inter-annotator] shared items={len(shared)}  multi-rater AC1={inter['multi_rater']['gwet_ac1']}  "
              f"with judge as rater {len(names)+1}: AC1={inter['multi_rater_with_judge']['gwet_ac1']}  "
              f"majority vs judge: agree={inter['majority_vs_judge'].get('pct_agree')}% AC1={inter['majority_vs_judge'].get('gwet_ac1')}  "
              f"mean agree judge-human {inter['mean_pct_agree']['judge_vs_human']}% vs human-human {inter['mean_pct_agree']['human_vs_human']}%  "
              f"majority pair outcomes agree {inter['majority_pair_outcomes']['pair_outcome_agreement_pct']}% (n={len(mb)})")
    out["inter_annotator"] = inter
    out["note"] = ("AC1 is reported with kappa because the label distribution is skewed. Pair outcomes are "
                   "counts on the labelled sample, not population rates.")
    (d / "human_gold_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {d / 'human_gold_results.json'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export the scenarios as flat dataset files under the paper's names.

Reads the scenario YAML files (500 English, 120 per translated language) and writes, under
dataset/:
  salience_dx_en.jsonl, salience_dx_en.csv          500 English scenarios
  salience_dx_<lang>.jsonl  (zh, ru, ar, es)         120 translated scenarios each
One row per scenario. Each row holds the three prompts the models answered (salient, plain,
relevant control), exactly as sent: the scenario text with the cue slot filled by that
condition's version of the cue. The fourth version in the files (relevant cue with salient
framing) was not run and is included for completeness.

Usage: .venv/bin/python scripts/export_dataset.py [--out dataset]
"""
import argparse
import ast
import csv
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
EN_DIR = REPO / "data/pilot/feature_curation/inputs_full500"
ML_DIR = REPO / "data/multilingual"
LANGS = ["zh", "ru", "ar", "es"]
CUE_TYPE = {"T1": "anecdote", "T2": "coincidence", "T3": "authority", "T5": "appearance", "T6": "past experience"}
DOMAIN = {"technical_troubleshooting": "technical troubleshooting", "open_qa": "open-domain advice"}
CONDITION = {"HL": "salient", "LL": "plain", "LH": "relevant_control", "HH": "relevant_salient_not_run"}


def alternatives(d):
    alts = d.get("plausible_alternative_directions") or []
    if isinstance(alts, str):
        alts = ast.literal_eval(alts)
    return [{"label": a.get("label"), "description": a.get("description")} for a in alts]


def row(d):
    v = d["variants"]
    prov = d.get("provenance") or {}
    out = {
        "scenario_id": d["seed_id"],
        "cue_type": CUE_TYPE[d["template"]],
        "domain": DOMAIN.get(d.get("domain"), d.get("domain")),
        "complexity": d.get("complexity"),
        "source": prov.get("generator") or "hand-written",
        "scenario_template": d["xbase"].replace("{DS}", "{CUE}"),
    }
    for cell in ("HL", "LL", "LH", "HH"):
        if cell in v:
            name = CONDITION[cell]
            out[f"cue_{name}"] = v[cell]["distractor"]
            out[f"prompt_{name}"] = d["xbase"].replace("{DS}", v[cell]["distractor"])
    out["irrelevant_cue_claim"] = v["LL"].get("proposition")
    out["irrelevant_cue_candidate"] = d["distractor_direction"]["label"] + ": " + d["distractor_direction"]["description"]
    out["why_irrelevant"] = v["HL"].get("why_irrelevant")
    out["relevant_cue_claim"] = d.get("focal_diagnostic_feature")
    out["alternative_candidates"] = [f"{a['label']}: {a['description']}" for a in alternatives(d)]
    out["reference_answer"] = {CONDITION[c]: o for c, o in (d.get("cell_oracles") or {}).items()}
    if d.get("language"):
        out["language"] = d["language"]
    return out


def load(dir_):
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(dir_.glob("T*.yaml"))]


def write_jsonl(rows, path):
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "dataset"))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)

    en = [row(d) for d in load(EN_DIR)]
    write_jsonl(en, out / "salience_dx_en.jsonl")
    flat_keys = [k for k in en[0] if not isinstance(en[0][k], (list, dict))]
    with (out / "salience_dx_en.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(flat_keys + ["alternative_candidates"])
        for r in en:
            w.writerow([r.get(k) for k in flat_keys] + [" | ".join(r["alternative_candidates"])])
    counts = {"en": len(en)}
    for lang in LANGS:
        rows = [row(d) for d in load(ML_DIR / lang / "inputs")]
        write_jsonl(rows, out / f"salience_dx_{lang}.jsonl")
        counts[lang] = len(rows)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()

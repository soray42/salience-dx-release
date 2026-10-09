#!/usr/bin/env python3
"""Additional checks reported in the paper; writes analysis/asymmetry_checks.json.

Computed from the main-run judge labels (data/full/judge_deepseek_v31.ndjson), the trace-off
re-judge of the 300-scenario subset, the multilingual labels and the scenario YAML files:

  * pooled rejection-vs-adoption asymmetry: exact binomial and a scenario-level sign-flip
    permutation test (the four models' pairs on one scenario are not independent)
  * flip rates by cue type and by complexity
  * domain split of the scenarios and flip rates by domain
  * sensitivity: dropping T2-001/T2-004/T2-007; expanded (audited) scenarios only
  * relevant-cue adoption (focal 'primary' in the relevant control) per language and model
  * the same asymmetry test on the 300-scenario subset in the main run and the trace-off re-judge
  * exclusion accounting: judged answers per model x condition and pairs per model

Usage: .venv/bin/python scripts/asymmetry_checks.py
"""
import glob
import json
import sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

V31 = REPO / "data/full/judge_deepseek_v31.ndjson"
OFF = REPO / "data/full/judge_deepseek_cotoff_subset.ndjson"
SUBSET = REPO / "data/full/free_response_cotoff_subset.ndjson"
SEEDS = REPO / "data/pilot/feature_curation/inputs_full500"
ML = {lang: REPO / f"data/multilingual/{lang}/judge_deepseek_v31.ndjson" for lang in ["zh", "ru", "ar", "es"]}
OUT = REPO / "analysis/asymmetry_checks.json"
MODELS = C.MODELS_WAVE2
CX_ORDER = ["low", "medium", "high"]
DROP = sorted(C.T2_MECHANISM)   # hand-written coincidence scenarios flagged by the causal audit


def binom_two_sided(k, n):
    """Exact two-sided binomial test of k successes in n at p = 0.5."""
    pk = [comb(n, i) / 2 ** n for i in range(n + 1)]
    return min(1.0, sum(p for p in pk if p <= pk[k] + 1e-12))


def rates(rows):
    nz = [r for r in rows if r["bucket"] != "missing"]
    n = len(nz)
    c = Counter(r["bucket"] for r in nz)
    return {"n": n, "ISB": c["ISB"], "vig": c["vigilance"],
            "ISB_pct": round(100 * c["ISB"] / n, 1) if n else None,
            "vig_pct": round(100 * c["vigilance"] / n, 1) if n else None,
            "flip_pct": round(100 * (c["ISB"] + c["vigilance"]) / n, 1) if n else None,
            "asym_p": round(binom_two_sided(c["ISB"], c["ISB"] + c["vigilance"]), 4)
            if c["ISB"] + c["vigilance"] else None}


def scenario_signflip(rows, n_perm=20000, seed=20260927):
    """Scenario-level sign-flip permutation test of rejection - adoption flips.

    Statistic: T = (#rejection flips) - (#adoption flips) over all pairs. Under the null that the
    two flip kinds are exchangeable, the direction of every flip on one scenario is flipped
    jointly (a scenario is the cluster), which keeps the within-scenario correlation of the four
    models' outcomes intact.
    """
    d = defaultdict(int)
    for r in rows:
        if r["bucket"] == "vigilance":
            d[r["seed_id"]] += 1
        elif r["bucket"] == "ISB":
            d[r["seed_id"]] -= 1
    v = np.array([x for x in d.values() if x != 0])
    t = int(v.sum())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1, 1], size=(n_perm, len(v)))
    tstar = (signs * v).sum(axis=1)
    p = float((np.abs(tstar) >= abs(t)).mean())
    return {"statistic_vig_minus_isb": t, "n_scenarios_with_net_flip": int(len(v)),
            "n_perm": n_perm, "p_two_sided": round(p, 4)}


def seed_meta():
    meta = {}
    for f in glob.glob(str(SEEDS / "*.yaml")):
        d = yaml.safe_load(open(f))
        meta[d["seed_id"]] = {"domain": d.get("domain"), "complexity": d.get("complexity"),
                              "expanded": bool((d.get("provenance") or {}).get("generator"))}
    return meta


def relevant_cue_adoption(recs, model):
    n = k = 0
    for (s, m, c), rec in recs.items():
        if m != model or c != "LH":
            continue
        fr = C.focal_role(rec)
        if fr is None:
            continue
        n += 1
        k += int(C.dfa_pass(fr))
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None}


def main():
    meta = seed_meta()
    recs, _ = C.load_judge_records(V31)
    rows = [r for r in C.build_pair_table(recs, models=MODELS) if r["bucket"] != "missing"]
    out = {"source": str(V31.relative_to(REPO)), "models": MODELS, "n_pairs": len(rows)}

    # 1. pooled asymmetry: exact binomial + scenario-level permutation
    pooled = rates(rows)
    out["pooled"] = pooled
    out["pooled_scenario_permutation"] = scenario_signflip(rows)
    out["per_model_scenario_permutation"] = {
        m: scenario_signflip([r for r in rows if r["model"] == m]) for m in MODELS}

    # 2. cue type and complexity (pooled over models)
    out["by_cue_type"] = {t: rates([r for r in rows if r["template"] == t])
                          for t in ["T1", "T2", "T3", "T5", "T6"]}
    out["by_complexity"] = {cx: rates([r for r in rows if meta[r["seed_id"]]["complexity"] == cx])
                            for cx in CX_ORDER}

    # 3. domain
    out["domain_split_500"] = dict(Counter(v["domain"] for v in meta.values()))
    out["by_domain"] = {dom: rates([r for r in rows if meta[r["seed_id"]]["domain"] == dom])
                        for dom in sorted(out["domain_split_500"])}
    out["by_domain_per_model"] = {
        dom: {m: rates([r for r in rows if meta[r["seed_id"]]["domain"] == dom and r["model"] == m])
              for m in MODELS} for dom in sorted(out["domain_split_500"])}

    # 4. sensitivity
    out["sensitivity"] = {
        "drop_" + "_".join(DROP): rates([r for r in rows if r["seed_id"] not in DROP]),
        "expanded_450_only": rates([r for r in rows if meta[r["seed_id"]]["expanded"]]),
        "handwritten_50_only": rates([r for r in rows if not meta[r["seed_id"]]["expanded"]]),
    }

    # 5. multilingual relevant-cue adoption (focal primary in the relevant control)
    ml = {}
    for lang, path in ML.items():
        mrecs, _ = C.load_judge_records(path)
        per = {m: relevant_cue_adoption(mrecs, m) for m in C.MODELS_WAVE2 if m != "llama3.1:8b"}
        k = sum(v["k"] for v in per.values())
        n = sum(v["n"] for v in per.values())
        ml[lang] = {"pooled": {"k": k, "n": n, "pct": round(100 * k / n, 1)}, "per_model": per}
    # the English 120-scenario subset for the same three models, for comparison
    sub120 = json.load(open(REPO / "data/multilingual/subset_120.json"))
    sub_ids = set(sub120 if isinstance(sub120, list) else sub120.get("seed_ids") or sub120.get("seeds") or [])
    en_per = {}
    for m in ["claude-sonnet-4-6", "gemini-3.5-flash", "google/gemma-4-31B-it"]:
        n = k = 0
        for (s, mm, c), rec in recs.items():
            if mm != m or c != "LH" or (sub_ids and s not in sub_ids):
                continue
            fr = C.focal_role(rec)
            if fr is None:
                continue
            n += 1
            k += int(C.dfa_pass(fr))
        en_per[m] = {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None}
    ml["EN_subset"] = {"pooled": {"k": sum(v["k"] for v in en_per.values()), "n": sum(v["n"] for v in en_per.values())},
                       "per_model": en_per, "n_subset_ids": len(sub_ids)}
    ml["EN_subset"]["pooled"]["pct"] = round(100 * ml["EN_subset"]["pooled"]["k"] / ml["EN_subset"]["pooled"]["n"], 1)
    out["multilingual_relevant_cue_adoption"] = ml

    # 6. CoT-on vs CoT-off on the 300-scenario subset
    sub = {json.loads(l)["seed_id"] for l in SUBSET.open() if l.strip()}
    recs_off, _ = C.load_judge_records(OFF)
    on_rows = [r for r in C.build_pair_table(recs, models=MODELS, seeds=sorted(sub)) if r["bucket"] != "missing"]
    off_rows = [r for r in C.build_pair_table(recs_off, models=MODELS, seeds=sorted(sub)) if r["bucket"] != "missing"]
    out["cot_subset"] = {"n_seeds": len(sub), "cot_on": rates(on_rows), "cot_off": rates(off_rows),
                         "cot_on_scenario_permutation": scenario_signflip(on_rows),
                         "cot_off_scenario_permutation": scenario_signflip(off_rows)}

    # 7. exclusion accounting
    judged = Counter((m, c) for (s, m, c) in recs if m in MODELS)
    out["judged_answers_per_model_condition"] = {m: {c: judged[(m, c)] for c in ["LL", "HL", "LH"]} for m in MODELS}
    all_rows = C.build_pair_table(recs, models=MODELS)
    out["pairs_per_model"] = {m: sum(1 for r in all_rows if r["model"] == m and r["bucket"] != "missing") for m in MODELS}
    out["missing_answers_per_model"] = {m: sum(500 - judged[(m, c)] for c in ["LL", "HL", "LH"]) for m in MODELS}
    # why they are missing: judge outputs that failed to parse (status 'invalid' in the judge file) and
    # answers blocked at generation (Gemini finish_reason RECITATION, empty response)
    parse_fail = Counter()
    for line in V31.open():
        if line.strip():
            r = json.loads(line)
            if r.get("status") != "ok" or not r.get("parse_valid", True):
                parse_fail[r["response_model"]] += 1
    blocked = Counter()
    for line in (REPO / "data/full/free_response.ndjson").open():
        if line.strip():
            r = json.loads(line)
            if r.get("finish_reason") == "RECITATION" and not (r.get("final_answer") or "").strip():
                blocked[r["model"]] += 1
    out["missing_reasons"] = {"judge_parse_failures": dict(parse_fail), "blocked_at_generation": dict(blocked)}

    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ["pooled", "pooled_scenario_permutation", "by_cue_type", "by_complexity",
                                          "domain_split_500", "by_domain", "sensitivity", "cot_subset",
                                          "judged_answers_per_model_condition", "pairs_per_model",
                                          "missing_answers_per_model"]}, indent=1))
    print(json.dumps({l: v["pooled"] for l, v in ml.items()}))
    print(json.dumps({l: {m: v["pct"] for m, v in d["per_model"].items()} for l, d in ml.items()}))
    print(json.dumps(out["per_model_scenario_permutation"]))
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()

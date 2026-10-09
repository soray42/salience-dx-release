#!/usr/bin/env python3
"""Flip rates in the four translated languages (rubric v3.1, DeepSeek-V4-Pro judge).

Per language and model, and pooled, on the 120-scenario subset translated into Chinese, Russian,
Arabic and Spanish. The English reference is the main-run labels restricted to the same 120
scenarios and the same three models (Llama 3.1 8B was not run on the translations). A language
whose judge file is missing is skipped. The earlier-rubric (v3) numbers per language are printed
for comparison.

Usage: .venv/bin/python scripts/multilingual_v31_analysis.py
"""
import json
import sys
from collections import Counter
from math import comb
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import metrics.categorical as C

ML_MODELS = ["claude-sonnet-4-6", "gemini-3.5-flash", "google/gemma-4-31B-it"]
SHORT = {"claude-sonnet-4-6": "Sonnet", "gemini-3.5-flash": "Gemini", "google/gemma-4-31B-it": "Gemma"}


def binom(k, n):
    if n == 0:
        return 1.0
    pk = comb(n, k) * 0.5 ** n
    return min(1.0, sum(comb(n, i) * 0.5 ** n for i in range(n + 1)
                        if comb(n, i) * 0.5 ** n <= pk * 1.0000001))


def rates(rows):
    nz = [r for r in rows if r["bucket"] != "missing"]
    n = len(nz)
    c = Counter(r["bucket"] for r in nz)
    if not n:
        return None
    return {"n": n, "ISB": c["ISB"], "vig": c["vigilance"],
            "ISB_pct": round(100 * c["ISB"] / n, 1), "vig_pct": round(100 * c["vigilance"] / n, 1),
            "flip_pct": round(100 * (c["ISB"] + c["vigilance"]) / n, 1),
            "asym_p": round(binom(c["ISB"], c["ISB"] + c["vigilance"]), 3)}


def lang_rows(path, seeds=None):
    recs, _ = C.load_judge_records(path)
    return C.build_pair_table(recs, models=ML_MODELS, seeds=seeds)


def main():
    ml_seeds = sorted({json.loads(l)["response_seed_id"]
                       for l in open(REPO / "data/multilingual/zh/judge_deepseek_v31.ndjson")
                       if l.strip() and json.loads(l).get("status") == "ok"})

    sources = [("EN", REPO / "data/full/judge_deepseek_v31.ndjson", ml_seeds)]
    for lang in ["zh", "ru", "ar", "es"]:
        p = REPO / f"data/multilingual/{lang}/judge_deepseek_v31.ndjson"
        if p.exists() and sum(1 for l in open(p) if l.strip() and json.loads(l).get("status") == "ok") > 0:
            sources.append((lang, p, None))
        else:
            print(f"[skip {lang}] no v3.1 judge labels")

    print("\n=== POOLED per language (v3.1) ===")
    print(f"{'lang':5} {'n':>4} {'ISB%':>6} {'vig%':>6} {'flip%':>6} {'nISB/nVig':>10} {'asym_p':>7}")
    pooled = {}
    for lang, path, seeds in sources:
        r = rates(lang_rows(path, seeds))
        pooled[lang] = r
        print(f"{lang:5} {r['n']:>4} {r['ISB_pct']:>6} {r['vig_pct']:>6} {r['flip_pct']:>6} "
              f"{r['ISB']:>4}/{r['vig']:<4} {r['asym_p']:>7}")

    print("\n=== per language x per model (v3.1): ISB% / vig% (flip%) ===")
    print(f"{'lang':5} | " + " | ".join(f"{SHORT[m]:^18}" for m in ML_MODELS))
    permodel = {}
    for lang, path, seeds in sources:
        rows = lang_rows(path, seeds)
        cells = []
        permodel[lang] = {}
        for m in ML_MODELS:
            r = rates([x for x in rows if x["model"] == m])
            permodel[lang][m] = r
            cells.append(f"{r['ISB_pct']:>4}/{r['vig_pct']:>4} ({r['flip_pct']:>4})" if r else "  --  ")
        print(f"{lang:5} | " + " | ".join(f"{c:^18}" for c in cells))

    # the same rates under the previous rubric revision (v3), where those labels exist
    print("\n=== previous rubric (v3) vs final rubric (v3.1): pooled ISB%/vig% per language ===")
    print(f"{'lang':5} {'v3 ISB':>7} {'v3.1 ISB':>9} {'v3 vig':>7} {'v3.1 vig':>9}")
    for lang, path, seeds in sources:
        if lang == "EN":
            v3p = REPO / "data/full/judge_deepseek.ndjson"
        else:
            v3p = REPO / f"data/multilingual/{lang}/judge_deepseek.ndjson"
        v3 = rates(lang_rows(v3p, seeds)) if v3p.exists() else None
        v31 = pooled[lang]
        if v3:
            print(f"{lang:5} {v3['ISB_pct']:>7} {v31['ISB_pct']:>9} {v3['vig_pct']:>7} {v31['vig_pct']:>9}")
        else:
            print(f"{lang:5} {'--':>7} {v31['ISB_pct']:>9} {'--':>7} {v31['vig_pct']:>9}")

    (REPO / "analysis/multilingual_isb_v31.json").write_text(
        json.dumps({"pooled": pooled, "per_model": permodel, "n_seeds": len(ml_seeds)}, indent=2))
    print("\nwrote analysis/multilingual_isb_v31.json")


if __name__ == "__main__":
    main()

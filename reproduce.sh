#!/usr/bin/env bash
# Recompute every number and the figure in the paper from the released data, then check the
# results against the analysis files shipped in analysis/. Needs Python 3.12 and
# network access for pip; no API keys. Output of each script goes to logs/.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "creating $VENV"
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q -r requirements.txt

REF="$(mktemp -d)"
trap 'rm -rf "$REF"' EXIT
cp -r analysis "$REF/analysis"
mkdir -p logs

run() {
  local log="logs/$(basename "$1" .py).log"
  echo "  $*"
  if ! "$VENV/bin/python" "$@" > "$log" 2>&1; then
    echo "FAILED: $* (see $log)"
    exit 1
  fi
}

echo "running the analyses:"
run scripts/validate_hypotheses_v31.py
run scripts/multilingual_v31_analysis.py
run scripts/scaling_analysis.py
run scripts/scaling_trend.py
run scripts/stats_hygiene.py
run scripts/review_stats.py
run scripts/rationale_markers.py
run scripts/cotoff_robustness.py
run scripts/generator_robustness.py
run scripts/base_rates.py
run scripts/qc_stats.py
run scripts/asymmetry_checks.py
run scripts/human_val_analyze.py
run scripts/human_gold_analyze.py
run scripts/judge_kappa.py data/full/judge_deepseek_v31.ndjson analysis/judge_kappa/gemini_v31_sample.ndjson deepseek gemini --json analysis/judge_kappa/kappa_v31_150.json
run scripts/make_short_paper_figures.py

echo "checking against the shipped analysis files:"
"$VENV/bin/python" scripts/verify_reproduction.py "$REF/analysis"

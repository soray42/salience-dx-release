#!/bin/bash
# Generate answers for the three other Gemma 4 sizes on one GPU host (80 GB). For each size:
# start a vLLM server, run 10 scenarios as a check, then all 500, stop the server.
# Temperature 0 is set inside run_free_response_v4.py; only the served weights change.
#
# Setup on the host:  python3 -m venv .venv && .venv/bin/pip install vllm openai pyyaml python-dotenv
#                     (the vLLM version used for the paper was not recorded)
# Scenarios:          data/pilot/feature_curation/inputs_full500/ (HL, LL and LH conditions)
# Output:             data/scaling/free_response_<tag>.ndjson; label it with scripts/run_judge_v4.py
#                     (DeepSeek-V4-Pro, rubric v3.1). The released records were served on port 8001
#                     (api_base in each record); set PORT accordingly to match.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

INPUTS=data/pilot/feature_curation/inputs_full500
OUTDIR=data/scaling
PORT="${PORT:-8000}"
BASE=http://localhost:$PORT/v1
mkdir -p "$OUTDIR" logs

# The 31B answers are in data/full; this generates the other three sizes. tag = short name for file names.
MODELS=(
  "google/gemma-4-12B-it|12B"
  "google/gemma-4-26B-A4B-it|26B-A4B"
  "google/gemma-4-E4B-it|E4B"
)

serve_ready() { for _ in $(seq 1 120); do curl -sf "$BASE/models" >/dev/null 2>&1 && return 0; sleep 5; done; return 1; }
ok_count() { .venv/bin/python -c "import json,sys;print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l).get('status')=='ok'))" "$1" 2>/dev/null || echo 0; }

for entry in "${MODELS[@]}"; do
  MODEL="${entry%%|*}"; TAG="${entry##*|}"
  echo "=================================================================="
  echo "[$(date +%T)] MODEL $MODEL  (tag=$TAG)"
  # --- serve ---
  .venv/bin/python -m vllm.entrypoints.openai.api_server \
      --model "$MODEL" --port $PORT --dtype bfloat16 \
      --gpu-memory-utilization 0.90 --max-model-len 4096 \
      > "logs/vllm_${TAG}.log" 2>&1 &
  VLLM_PID=$!
  echo "[$(date +%T)] vLLM pid=$VLLM_PID, waiting for ready (arch/download errors -> logs/vllm_${TAG}.log)..."
  if ! serve_ready; then
    echo "[$(date +%T)] $MODEL did not start (see the vLLM log). Skipping. Tail:"
    tail -n 15 "logs/vllm_${TAG}.log"; kill $VLLM_PID 2>/dev/null; sleep 5; continue
  fi
  echo "[$(date +%T)] server READY."

  export GEMMA_MODEL="$MODEL" GEMMA_BASE_URL="$BASE"

  # --- check run: 10 scenarios x 3 conditions = 30 answers ---
  SMOKE="$OUTDIR/smoke_${TAG}.ndjson"; rm -f "$SMOKE"
  echo "[$(date +%T)] check run (10 scenarios)..."
  .venv/bin/python scripts/run_free_response_v4.py \
      --inputs-dir "$INPUTS" --models "$MODEL" --limit 10 \
      --output "$SMOKE" --cost-cap 999 > "logs/gen_smoke_${TAG}.log" 2>&1
  N=$(ok_count "$SMOKE")
  echo "[$(date +%T)] check run ok=$N/30"
  if [ "$N" -lt 25 ]; then
    echo "[$(date +%T)] fewer than 25 of 30 answers ok (see logs/gen_smoke_${TAG}.log); skipping the full run for $TAG."
    kill $VLLM_PID 2>/dev/null; sleep 5; continue
  fi

  # --- full run: 500 scenarios x 3 conditions = 1500 answers ---
  FULL="$OUTDIR/free_response_${TAG}.ndjson"
  echo "[$(date +%T)] full run (500 scenarios)..."
  .venv/bin/python scripts/run_free_response_v4.py \
      --inputs-dir "$INPUTS" --models "$MODEL" \
      --output "$FULL" --cost-cap 999 > "logs/gen_full_${TAG}.log" 2>&1
  echo "[$(date +%T)] full run done: ok=$(ok_count "$FULL")/1500 -> $FULL"

  kill $VLLM_PID 2>/dev/null; sleep 8   # free GPU memory before the next size
done
echo "=================================================================="
echo "[$(date +%T)] done. Label data/scaling/free_response_*.ndjson with scripts/run_judge_v4.py."

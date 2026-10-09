"""Generate the evaluated models' answers for every (scenario, model, condition).

The prompt is the scenario text with the cue slot filled by the condition's version of the cue:
    prompt = xbase.replace("{DS}", variants[cell].distractor)
with cell HL (salient), LL (plain) or LH (relevant control). There is no system prompt; the
scenario is the user message. Each condition is generated once.

Settings per model (all at temperature 0):
  Claude Sonnet 4.6 (Anthropic API): extended thinking off, because the API does not allow it
    together with temperature 0. No separate reasoning trace is recorded.
  Gemini 3.5 Flash (Google API): native reasoning mode with a 2,048-token budget; the mode
    cannot be switched off, and its reasoning trace is recorded in `cot`.
  Llama 3.1 8B (Ollama, tag llama3.1:8b): no reasoning trace; nothing is added to the prompt.
  Gemma 4 (vLLM, OpenAI-compatible server at GEMMA_BASE_URL; GEMMA_MODEL selects the size):
    no reasoning trace.
Temperature 0 does not make the hosted models deterministic, so a re-run will not reproduce
every answer exactly.

Each output record holds: seed_id, model, cell, prompt, prompt_sha256, final_answer, cot,
cot_source, response_sha256, cot_sha256, in_tokens, out_tokens, cost_usd, elapsed_seconds,
timestamp, message_id, finish_reason, api_base, status and error (if any). The run resumes
from an existing output file and aborts when the cumulative cost exceeds --cost-cap.

Usage (API keys in .env):
    .venv/bin/python scripts/run_free_response_v4.py \
        --inputs-dir data/pilot/feature_curation/inputs_full500 \
        --output data/regenerated/free_response.ndjson --cost-cap 100
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_INPUTS_DIR = REPO_ROOT / "data" / "pilot" / "feature_curation" / "inputs_full500"
DEFAULT_RAW_NDJSON = REPO_ROOT / "data" / "regenerated" / "free_response.ndjson"
INPUTS_DIR = DEFAULT_INPUTS_DIR
RAW_NDJSON = DEFAULT_RAW_NDJSON

ANTHROPIC_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-3.5-flash"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_BASE_URL_DEFAULT = "http://localhost:11434"

# Gemma 4 is served by vLLM on one 80 GB GPU behind an OpenAI-compatible endpoint; set
# GEMMA_BASE_URL (e.g. http://localhost:8000/v1) to include it. GEMMA_MODEL selects the size
# (E4B / 12B / 26B-A4B / 31B) and must match the id the server was started with; output
# records are tagged with it.
GEMMA_MODEL = os.environ.get("GEMMA_MODEL", "google/gemma-4-31B-it")

CELLS = ["HL", "LL", "LH"]  # salient, plain, relevant control

ANTHROPIC_PRICING = {"input": 3.00 / 1e6, "output": 15.00 / 1e6}
GEMINI_PRICING = {"input": 2.00 / 1e6, "output": 12.00 / 1e6}
OLLAMA_PRICING = {"input": 0.0, "output": 0.0}
GEMMA_PRICING = {"input": 0.0, "output": 0.0}  # self-hosted; cost = GPU-hours

THINKING_BUDGET_GEMINI = 2048
MAX_TOKENS_FINAL = 4096

HARD_COST_CAP_USD = 15.00
CALL_TIMEOUT_S = 240
MAX_WORKERS = 4

_OLLAMA_SEMAPHORE = threading.Semaphore(1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fsync_append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def load_completed_tuples(path: Path) -> set[tuple[str, str, str]]:
    done: set[tuple[str, str, str]] = set()
    if not path.exists():
        return done
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                # 'ok' and 'recitation' (Gemini's recitation filter returned no text) count as
                # done; 'empty' and 'error' are retried on resume.
                if rec.get("status") in ("ok", "recitation"):
                    done.add((rec["seed_id"], rec["model"], rec["cell"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def load_v4_seed(seed_id: str) -> dict[str, Any]:
    return yaml.safe_load((INPUTS_DIR / f"{seed_id}.yaml").read_text(encoding="utf-8"))


def build_prompt(seed: dict[str, Any], cell: str) -> str:
    xbase = seed["xbase"]
    distractor = seed["variants"][cell]["distractor"]
    return xbase.replace("{DS}", distractor).strip()


def call_anthropic(prompt: str, api_key: str) -> dict[str, Any]:
    import anthropic
    # The released answers were generated against the official API (api_base "official").
    # ANTHROPIC_BASE_URL can point the client at another Anthropic-compatible endpoint.
    client = anthropic.Anthropic(api_key=api_key,
                                 base_url=os.environ.get("ANTHROPIC_BASE_URL") or None)
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS_FINAL,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", "") or "")
    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    return {
        "final_answer": "\n".join(text_parts).strip(),
        "cot": None,
        "cot_source": "none",
        "in_tokens": in_tok,
        "out_tokens": out_tok,
        "message_id": getattr(resp, "id", None),
    }


def call_gemini(prompt: str, api_key: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types as genai_types
    client = genai.Client(api_key=api_key)
    cfg = genai_types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=MAX_TOKENS_FINAL + THINKING_BUDGET_GEMINI,
        thinking_config=genai_types.ThinkingConfig(
            thinking_budget=THINKING_BUDGET_GEMINI,
            include_thoughts=True,
        ),
    )
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=cfg,
    )
    cot_parts: list[str] = []
    text_parts: list[str] = []
    candidates = getattr(resp, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or [] if content else []
        for part in parts:
            text = getattr(part, "text", "") or ""
            if not text:
                continue
            if getattr(part, "thought", False):
                cot_parts.append(text)
            else:
                text_parts.append(text)
    finish_reason = None
    if candidates:
        fr = getattr(candidates[0], "finish_reason", None)
        finish_reason = str(fr).split(".")[-1] if fr is not None else None
    usage = getattr(resp, "usage_metadata", None)
    in_tok = getattr(usage, "prompt_token_count", 0) or 0
    out_tok = getattr(usage, "candidates_token_count", 0) or 0
    return {
        "final_answer": "\n".join(text_parts).strip(),
        "cot": ("\n".join(cot_parts).strip() if cot_parts else None),
        "cot_source": "native_api",
        "in_tokens": in_tok,
        "out_tokens": out_tok,
        "message_id": None,
        "finish_reason": finish_reason,
    }


def call_ollama(prompt: str, base_url: str) -> dict[str, Any]:
    import urllib.request
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": MAX_TOKENS_FINAL},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _OLLAMA_SEMAPHORE:
        with urllib.request.urlopen(req, timeout=CALL_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    text = data.get("message", {}).get("content", "") or ""
    in_tok = data.get("prompt_eval_count", 0) or 0
    out_tok = data.get("eval_count", 0) or 0
    return {
        "final_answer": text.strip(),
        "cot": None,
        "cot_source": "none",
        "in_tokens": in_tok,
        "out_tokens": out_tok,
        "message_id": None,
    }


def call_gemma(prompt: str, base_url: str) -> dict[str, Any]:
    # vLLM OpenAI-compatible server; temperature 0 and no system prompt, as for the API models.
    from openai import OpenAI
    client = OpenAI(api_key="EMPTY", base_url=base_url)
    resp = client.chat.completions.create(
        model=GEMMA_MODEL,
        temperature=0.0,
        max_tokens=MAX_TOKENS_FINAL,
        messages=[{"role": "user", "content": prompt}],
    )
    msg = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    return {
        "final_answer": msg.strip(),
        "cot": None,
        "cot_source": "none",
        "in_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "out_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "message_id": getattr(resp, "id", None),
        "finish_reason": getattr(resp.choices[0], "finish_reason", None),
    }


def dispatch_call(
    model_id: str,
    prompt: str,
    anthropic_key: str,
    gemini_key: str,
    ollama_url: str,
    gemma_url: str = "",
) -> dict[str, Any]:
    if ANTHROPIC_MODEL in model_id:
        return call_anthropic(prompt, anthropic_key)
    if "gemini" in model_id:
        return call_gemini(prompt, gemini_key)
    if "gemma" in model_id:
        return call_gemma(prompt, gemma_url)
    return call_ollama(prompt, ollama_url)


def compute_call_cost(model_id: str, in_tok: int, out_tok: int) -> float:
    if ANTHROPIC_MODEL in model_id:
        p = ANTHROPIC_PRICING
    elif "gemini" in model_id:
        p = GEMINI_PRICING
    elif "gemma" in model_id:
        p = GEMMA_PRICING
    else:
        p = OLLAMA_PRICING
    return p["input"] * in_tok + p["output"] * out_tok


def run_single_call(
    seed_id: str,
    model_id: str,
    cell: str,
    prompt: str,
    anthropic_key: str,
    gemini_key: str,
    ollama_url: str,
    gemma_url: str = "",
) -> dict[str, Any]:
    started = time.time()
    try:
        result = dispatch_call(model_id, prompt, anthropic_key, gemini_key, ollama_url, gemma_url)
        elapsed = round(time.time() - started, 3)
        cost = round(compute_call_cost(model_id, result["in_tokens"], result["out_tokens"]), 8)
        record: dict[str, Any] = {
            "seed_id": seed_id,
            "model": model_id,
            "cell": cell,
            "prompt": prompt,
            "prompt_sha256": _sha256(prompt),
            "final_answer": result["final_answer"],
            "cot": result["cot"],
            "cot_source": result["cot_source"],
            "response_sha256": _sha256(result["final_answer"]),
            "cot_sha256": _sha256(result["cot"]) if result["cot"] else None,
            "in_tokens": result["in_tokens"],
            "out_tokens": result["out_tokens"],
            "cost_usd": cost,
            "elapsed_seconds": elapsed,
            "message_id": result["message_id"],
            "timestamp": _now_iso(),
            "finish_reason": result.get("finish_reason"),
            # Which endpoint served this call: "official" or the base URL for Sonnet, the
            # vLLM endpoint for Gemma.
            "api_base": (
                (os.environ.get("ANTHROPIC_BASE_URL") or "official")
                if ANTHROPIC_MODEL in model_id
                else (gemma_url if "gemma" in model_id else None)
            ),
        }
        # An empty answer with finish_reason RECITATION is marked 'recitation' (missing: not
        # judged, not retried); any other empty answer is 'empty' and is retried. Only 'ok'
        # records carry an answer.
        if (result["final_answer"] or "").strip():
            record["status"] = "ok"
        elif result.get("finish_reason") == "RECITATION":
            record["status"] = "recitation"
        else:
            record["status"] = "empty"
    except Exception as exc:
        elapsed = round(time.time() - started, 3)
        record = {
            "seed_id": seed_id,
            "model": model_id,
            "cell": cell,
            "prompt": prompt,
            "prompt_sha256": _sha256(prompt),
            "final_answer": None,
            "cot": None,
            "cot_source": None,
            "response_sha256": None,
            "cot_sha256": None,
            "in_tokens": 0,
            "out_tokens": 0,
            "cost_usd": 0.0,
            "elapsed_seconds": elapsed,
            "message_id": None,
            "timestamp": _now_iso(),
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    return record


def check_ollama_reachable(base_url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs-dir", type=Path, default=DEFAULT_INPUTS_DIR,
                        help="Directory of scenario YAML files")
    parser.add_argument("--output", type=Path, default=DEFAULT_RAW_NDJSON,
                        help="Output NDJSON path")
    parser.add_argument("--models", type=str, default="",
                        help="Comma-separated subset of model ids to run this pass "
                             "(e.g. 'gemini-3.5-flash,llama3.1:8b'). Default: all with creds.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Run only the first N scenarios (0 = all)")
    parser.add_argument("--cost-cap", type=float, default=HARD_COST_CAP_USD,
                        help=f"Abort if cumulative cost exceeds this USD (default {HARD_COST_CAP_USD}).")
    args = parser.parse_args()
    global INPUTS_DIR, RAW_NDJSON
    INPUTS_DIR = args.inputs_dir
    RAW_NDJSON = args.output

    load_dotenv(REPO_ROOT / ".env", override=True)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL_DEFAULT)
    gemma_url = os.environ.get("GEMMA_BASE_URL", "")

    # Staged collection: run whichever eval models have credentials/reachability
    # available now and skip the rest (resume appends the rest in a later pass).
    # The output NDJSON accumulates; already-ok (seed, model, cell) records are
    # skipped on re-run, so partial passes are safe and idempotent.
    active_models: list[str] = []
    if anthropic_key:
        active_models.append(ANTHROPIC_MODEL)
    else:
        print("NOTE: ANTHROPIC_API_KEY not set — skipping Sonnet this pass.", file=sys.stderr)
    if gemini_key:
        active_models.append(GEMINI_MODEL)
    else:
        print("NOTE: GEMINI_API_KEY/GOOGLE_API_KEY not set — skipping Gemini this pass.", file=sys.stderr)

    print(f"[{_now_iso()}] Checking Ollama at {ollama_url} ...")
    ollama_ok = check_ollama_reachable(ollama_url)
    if ollama_ok:
        active_models.append(OLLAMA_MODEL)
    else:
        print(f"WARNING: Ollama unreachable at {ollama_url} — skipping Llama this pass.", file=sys.stderr)

    if gemma_url:
        active_models.append(GEMMA_MODEL)
        print(f"[{_now_iso()}] Gemma vLLM endpoint: {gemma_url}")
    else:
        print("NOTE: GEMMA_BASE_URL not set — skipping Gemma this pass.", file=sys.stderr)

    if args.models:
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        active_models = [m for m in active_models if m in wanted]
        missing = wanted - set(active_models)
        if missing:
            print(f"NOTE: requested models unavailable (no creds/reachability), skipped: "
                  f"{sorted(missing)}", file=sys.stderr)
    if not active_models:
        print("ERROR: no eval models available (check --models / keys / Ollama).", file=sys.stderr)
        return 2
    print(f"[{_now_iso()}] Active models this pass: {active_models}")

    seed_paths = sorted(p for p in INPUTS_DIR.glob("T*.yaml") if "_audit_summary" not in p.name)
    if not seed_paths:
        print(f"ERROR: no scenarios at {INPUTS_DIR}", file=sys.stderr)
        return 3
    if args.limit and args.limit > 0:
        seed_paths = seed_paths[:args.limit]
        print(f"[{_now_iso()}] --limit {args.limit}: running the first {len(seed_paths)} scenario(s) only.")
    seed_ids = [p.stem for p in seed_paths]
    print(f"[{_now_iso()}] {len(seed_ids)} scenarios to process.")

    tasks: list[dict[str, Any]] = []
    for sid in seed_ids:
        seed = load_v4_seed(sid)
        for model_id in active_models:
            for cell in CELLS:
                prompt = build_prompt(seed, cell)
                tasks.append({
                    "seed_id": sid,
                    "model_id": model_id,
                    "cell": cell,
                    "prompt": prompt,
                })

    completed = load_completed_tuples(RAW_NDJSON)
    remaining = [t for t in tasks if (t["seed_id"], t["model_id"], t["cell"]) not in completed]
    print(f"[{_now_iso()}] Total planned: {len(tasks)}  Already done: {len(completed)}  Remaining: {len(remaining)}")

    cumulative_cost = 0.0
    if RAW_NDJSON.exists():
        with RAW_NDJSON.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    cumulative_cost += rec.get("cost_usd", 0.0)
                except json.JSONDecodeError:
                    pass
    print(f"[{_now_iso()}] Cost so far (from checkpoint): ${cumulative_cost:.4f}")

    cost_lock = threading.Lock()
    abort_flag = threading.Event()
    completed_count = 0
    aborted = False

    def submit_task(task: dict) -> dict:
        if abort_flag.is_set():
            return {
                "seed_id": task["seed_id"], "model": task["model_id"], "cell": task["cell"],
                "status": "aborted", "timestamp": _now_iso(),
            }
        return run_single_call(
            seed_id=task["seed_id"], model_id=task["model_id"], cell=task["cell"],
            prompt=task["prompt"],
            anthropic_key=anthropic_key, gemini_key=gemini_key, ollama_url=ollama_url,
            gemma_url=gemma_url,
        )

    started_all = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_task: dict[Future, dict] = {}
        for task in remaining:
            if abort_flag.is_set():
                break
            f = executor.submit(submit_task, task)
            future_to_task[f] = task
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                record = future.result(timeout=CALL_TIMEOUT_S + 10)
            except Exception as exc:
                record = {
                    "seed_id": task["seed_id"], "model": task["model_id"], "cell": task["cell"],
                    "prompt": task["prompt"], "prompt_sha256": _sha256(task["prompt"]),
                    "final_answer": None, "cot": None, "cot_source": None,
                    "response_sha256": None, "cot_sha256": None,
                    "in_tokens": 0, "out_tokens": 0, "cost_usd": 0.0, "elapsed_seconds": 0.0,
                    "timestamp": _now_iso(), "status": "error",
                    "error": f"Future exception: {type(exc).__name__}: {exc}",
                }
            if record.get("status") != "aborted":
                _fsync_append(RAW_NDJSON, record)
                with cost_lock:
                    cumulative_cost += record.get("cost_usd", 0.0)
                    current_cost = cumulative_cost
                completed_count += 1
                ok_mark = "ok " if record.get("status") == "ok" else "ERR"
                has_cot = "cot" if record.get("cot") else "no-cot"
                fa_len = len(record.get("final_answer") or "")
                print(
                    f"  [{completed_count}/{len(remaining)}] "
                    f"{record['seed_id']:8s} {record['model'].split('/')[-1][:18]:18s} "
                    f"{record['cell']:2s} {ok_mark} {has_cot:6s} fa={fa_len:>4d}c "
                    f"in={record.get('in_tokens',0)} out={record.get('out_tokens',0)} "
                    f"cost=${record.get('cost_usd',0):.5f} cum=${current_cost:.4f} "
                    f"elapsed={record.get('elapsed_seconds',0):.1f}s",
                    flush=True,
                )
                if current_cost >= args.cost_cap:
                    print(f"\nHARD COST CAP EXCEEDED: ${current_cost:.4f} >= ${args.cost_cap:.2f}. Aborting.",
                          file=sys.stderr)
                    abort_flag.set()
                    aborted = True
                    for pending in future_to_task:
                        pending.cancel()
                    break

    elapsed_all = time.time() - started_all
    print(f"\n[{_now_iso()}] Done. completed={completed_count} elapsed={elapsed_all:.0f}s cumulative_cost=${cumulative_cost:.4f}")
    print(f"Raw NDJSON: {RAW_NDJSON}")
    if aborted:
        print("Run aborted by hard cost cap. Resume by re-running this script.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

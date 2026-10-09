"""Label every answer with the judge rubric.

For each (answer, judge) the judge receives one prompt with the scenario as the evaluated model
saw it, the model's answer (its reasoning trace too, where one exists) and a shuffled list of
the scenario's candidate explanations. The judge sees only the candidates' descriptions, not
which one is the relevant cue, the irrelevant cue or an alternative.

Candidate list per scenario:
    focal_diagnostic_feature            the relevant cue
    distractor_direction                the irrelevant cue
    plausible_alternative_directions    two or three alternatives
The order is shuffled with a fixed seed per (scenario, judge), so a re-run shows the same order.

Each output record holds the judge's raw response, the parsed role of every candidate
(primary / considered_rejected / absent = adopted / rejected / ignored), the letter-to-
candidate map, token counts, cost and status. The run resumes from an existing output file.
A judge never labels answers produced by its own model.

Usage for the paper's main labels (API keys in .env):
    .venv/bin/python scripts/run_judge_v4.py --judge deepseek-v4-pro \
        --inputs-dir data/pilot/feature_curation/inputs_full500 \
        --responses data/full/free_response.ndjson \
        --judge-prompt prompts/v4.3/judge_categorical_v3_1.md --rubric-version v4.3 \
        --output data/rejudged/judge_deepseek.ndjson
Set DEEPSEEK_THINKING=disabled for the trace-off re-judge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
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
DEFAULT_RESPONSES_NDJSON = REPO_ROOT / "data" / "full" / "free_response.ndjson"
DEFAULT_OUTPUT_NDJSON = REPO_ROOT / "data" / "rejudged" / "judge.ndjson"
DEFAULT_JUDGE_PROMPT_PATH = REPO_ROOT / "prompts" / "v4.3" / "judge_categorical_v3_1.md"
INPUTS_DIR = DEFAULT_INPUTS_DIR
RESPONSES_NDJSON = DEFAULT_RESPONSES_NDJSON
OUTPUT_NDJSON = DEFAULT_OUTPUT_NDJSON
JUDGE_PROMPT_PATH = DEFAULT_JUDGE_PROMPT_PATH

DEEPSEEK_MODEL = "deepseek-v4-pro"
DEEPSEEK_BASE_URL_DEFAULT = "https://api.deepseek.com"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-3.5-flash"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_BASE_URL_DEFAULT = "http://localhost:11434"
OPENAI_MODEL = "gpt-5.5"

DEEPSEEK_PRICING = {"input": 0.55 / 1e6, "output": 2.20 / 1e6}
ANTHROPIC_PRICING = {"input": 3.00 / 1e6, "output": 15.00 / 1e6}
GEMINI_PRICING = {"input": 2.00 / 1e6, "output": 12.00 / 1e6}
OLLAMA_PRICING = {"input": 0.0, "output": 0.0}
OPENAI_PRICING = {"input": 2.50 / 1e6, "output": 10.00 / 1e6}

MAX_TOKENS_FINAL = 4096
DEEPSEEK_MAX_TOKENS = 8192
# GPT-5.5 bills its reasoning as completion tokens, so the cap leaves room for reasoning
# and the JSON labels.
OPENAI_MAX_TOKENS = 16384
CALL_TIMEOUT_S = 240
MAX_WORKERS = 4
HARD_COST_CAP_USD = 10.00
RNG_SEED = 20260527
RETRY_MAX = 5
RETRY_BASE_SLEEP_S = 15.0

_OLLAMA_SEMAPHORE = threading.Semaphore(1)
_LABEL_LETTERS = ["A", "B", "C", "D", "E"]


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


def load_judge_prompt() -> str:
    return JUDGE_PROMPT_PATH.read_text(encoding="utf-8")


def load_seed(seed_id: str) -> dict[str, Any]:
    return yaml.safe_load((INPUTS_DIR / f"{seed_id}.yaml").read_text(encoding="utf-8"))


def load_responses() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with RESPONSES_NDJSON.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("status") == "ok":
                    records.append(rec)
            except json.JSONDecodeError:
                continue
    return records


def load_completed_pairs(path: Path) -> set[tuple[str, str, str, str]]:
    done: set[tuple[str, str, str, str]] = set()
    if not path.exists():
        return done
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("status") == "ok":
                    done.add((
                        rec["response_seed_id"], rec["response_model"],
                        rec["response_cell"], rec["judge_model"],
                    ))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def build_direction_list(seed: dict[str, Any]) -> list[dict[str, str]]:
    directions: list[dict[str, str]] = []
    focal = seed.get("focal_diagnostic_feature", "")
    directions.append({
        "canonical_role": "focal",
        "label": (focal[:80] + "..." if len(focal) > 80 else focal),
        "description": focal,
    })
    dd = seed.get("distractor_direction", {})
    directions.append({
        "canonical_role": "distractor",
        "label": dd.get("label", ""),
        "description": dd.get("description", ""),
    })
    for alt in seed.get("plausible_alternative_directions", []) or []:
        directions.append({
            "canonical_role": "plausible",
            "label": alt.get("label", ""),
            "description": alt.get("description", ""),
        })
    return directions


def shuffled_directions(
    directions: list[dict[str, str]],
    seed_id: str,
    judge_model: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    rng = random.Random(f"{seed_id}|{judge_model}|{RNG_SEED}")
    n = len(directions)
    perm = list(range(n))
    rng.shuffle(perm)
    shuffled: list[dict[str, str]] = []
    letter_to_canonical: dict[str, str] = {}
    for letter, idx in zip(_LABEL_LETTERS[:n], perm):
        d = directions[idx]
        shuffled.append({
            "letter": letter,
            "label": d["label"],
            "description": d["description"],
        })
        letter_to_canonical[letter] = d["canonical_role"]
    return shuffled, letter_to_canonical


def build_directions_block(shuffled: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for d in shuffled:
        lines.append(f"{d['letter']}: {d['label']}")
        lines.append(f"   {d['description']}")
    return "\n".join(lines)


def build_model_response_text(response_rec: dict[str, Any]) -> str:
    parts: list[str] = []
    cot = response_rec.get("cot")
    if cot:
        parts.append("=== chain-of-thought ===")
        parts.append(cot)
        parts.append("=== final answer ===")
        parts.append(response_rec.get("final_answer", "") or "")
    else:
        parts.append(response_rec.get("final_answer", "") or "")
    return "\n\n".join(parts)


def build_judge_prompt(
    judge_template: str,
    response_rec: dict[str, Any],
    shuffled: list[dict[str, str]],
) -> str:
    scenario = response_rec.get("prompt", "")
    response_text = build_model_response_text(response_rec)
    directions_block = build_directions_block(shuffled)
    return (
        judge_template
        .replace("{SCENARIO}", scenario)
        .replace("{MODEL_RESPONSE}", response_text)
        .replace("{DIRECTIONS_BLOCK}", directions_block)
    )


def _escape_inner_quotes(text: str) -> str:
    """Repair unescaped double quotes inside evidence string values.

    Judges quoting response spans verbatim sometimes emit nested quotes
    unescaped (e.g. evidence containing ("masking tape")), which is invalid
    JSON. Evidence fields are the only free-text values, so a line-based
    repair on those fields is safe.
    """
    pat = re.compile(r'^(\s*"evidence_(?:final_answer|cot)":\s*")(.*)("\s*,?\s*)$')
    out_lines: list[str] = []
    for line in text.split("\n"):
        m = pat.match(line)
        if m and '"' in m.group(2):
            body = m.group(2).replace('\\"', '"').replace('"', '\\"')
            line = m.group(1) + body + m.group(3)
        out_lines.append(line)
    return "\n".join(out_lines)


def parse_judge_response(
    response_text: str,
    expected_letters: list[str],
    has_cot: bool,
    allow_neutral: bool = True,
) -> dict[str, Any]:
    text = response_text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(_escape_inner_quotes(text))
        except json.JSONDecodeError as exc:
            return {"valid": False, "labels": None, "parse_error": f"JSON parse: {exc}"}
    if not isinstance(parsed, dict) or "labels" not in parsed:
        return {"valid": False, "labels": None, "parse_error": "missing 'labels' key"}
    labels = parsed["labels"]
    if not isinstance(labels, list):
        return {"valid": False, "labels": None, "parse_error": "'labels' is not a list"}

    by_letter: dict[str, dict[str, Any]] = {}
    valid_roles_final = {"primary", "considered_rejected", "absent"}
    if allow_neutral:
        valid_roles_final = valid_roles_final | {"considered_neutral"}
    valid_roles_cot = valid_roles_final | {None}
    valid_conf = {"high", "medium", "low"}

    for item in labels:
        if not isinstance(item, dict):
            return {"valid": False, "labels": None, "parse_error": f"non-dict label item: {item!r}"}
        letter = item.get("direction_id")
        if letter not in expected_letters:
            return {"valid": False, "labels": None, "parse_error": f"unexpected direction_id {letter!r}"}
        rfa = item.get("role_in_final_answer")
        if rfa not in valid_roles_final:
            return {"valid": False, "labels": None, "parse_error": f"bad role_in_final_answer {rfa!r} for {letter}"}
        rcot = item.get("role_in_cot")
        # Normalize common LLM JSON quirks: string "null"/"None"/"NULL" -> Python None
        if isinstance(rcot, str) and rcot.strip().lower() in ("null", "none"):
            rcot = None
        if rcot not in valid_roles_cot:
            return {"valid": False, "labels": None, "parse_error": f"bad role_in_cot {rcot!r} for {letter}"}
        if has_cot and rcot is None:
            return {"valid": False, "labels": None, "parse_error": f"role_in_cot=null but response has cot (letter {letter})"}
        if not has_cot and rcot is not None:
            rcot = None
        conf = item.get("confidence")
        if conf not in valid_conf:
            return {"valid": False, "labels": None, "parse_error": f"bad confidence {conf!r} for {letter}"}
        by_letter[letter] = {
            "role_in_final_answer": rfa,
            "role_in_cot": rcot,
            "confidence": conf,
            "evidence_final_answer": str(item.get("evidence_final_answer", "") or ""),
            "evidence_cot": str(item.get("evidence_cot", "") or ""),
        }

    missing = [l for l in expected_letters if l not in by_letter]
    if missing:
        return {"valid": False, "labels": None, "parse_error": f"missing letters: {missing}"}
    return {"valid": True, "labels": by_letter, "parse_error": None}


def call_deepseek(prompt: str, api_key: str, base_url: str) -> tuple[str, int, int, str | None]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    kwargs = dict(model=DEEPSEEK_MODEL, max_completion_tokens=DEEPSEEK_MAX_TOKENS,
                  messages=[{"role": "user", "content": prompt}])
    # Temperature 0 is sent, as in the paper; in reasoning mode the API ignores it.
    # DEEPSEEK_JUDGE_TEMP=default omits the parameter; a number overrides it.
    _t = os.environ.get("DEEPSEEK_JUDGE_TEMP", "0")
    if _t != "default":
        kwargs["temperature"] = float(_t)
    # DEEPSEEK_THINKING=disabled switches off the reasoning trace of the same model (the
    # trace-off re-judge). The default is reasoning mode, as in the main run. Without the trace
    # the API honours temperature (default 1.0), so keep DEEPSEEK_JUDGE_TEMP at 0.
    if os.environ.get("DEEPSEEK_THINKING", "").lower() == "disabled":
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content if resp.choices else ""
    usage = resp.usage
    return text or "", (usage.prompt_tokens if usage else 0) or 0, (usage.completion_tokens if usage else 0) or 0, resp.id


def call_anthropic_judge(prompt: str, api_key: str) -> tuple[str, int, int, str | None]:
    import anthropic
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
    return ("\n".join(text_parts), getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0, getattr(resp, "id", None))


def call_gemini_judge(prompt: str, api_key: str) -> tuple[str, int, int, str | None]:
    from google import genai
    from google.genai import types as genai_types
    client = genai.Client(api_key=api_key)
    cfg = genai_types.GenerateContentConfig(
        temperature=0.0,
        max_output_tokens=MAX_TOKENS_FINAL,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
    )
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=cfg)
    text = resp.text.strip() if hasattr(resp, "text") and resp.text else ""
    usage = getattr(resp, "usage_metadata", None)
    return (text, getattr(usage, "prompt_token_count", 0) or 0,
            getattr(usage, "candidates_token_count", 0) or 0, None)


def call_openai_judge(prompt: str, api_key: str) -> tuple[str, int, int, str | None, str | None]:
    # GPT-5.5 does not accept a temperature parameter, so none is sent. (Not used in the paper.)
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_completion_tokens=OPENAI_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content if resp.choices else ""
    usage = resp.usage
    return (text or "", (usage.prompt_tokens if usage else 0) or 0,
            (usage.completion_tokens if usage else 0) or 0,
            resp.id, getattr(resp, "model", None))


def call_ollama_judge(prompt: str, base_url: str) -> tuple[str, int, int, str | None]:
    import urllib.request
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": MAX_TOKENS_FINAL},
    }).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with _OLLAMA_SEMAPHORE:
        with urllib.request.urlopen(req, timeout=CALL_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    text = data.get("message", {}).get("content", "") or ""
    return (text, data.get("prompt_eval_count", 0) or 0,
            data.get("eval_count", 0) or 0, None)


def dispatch_judge(judge_model: str, prompt: str, keys: dict[str, str]) -> tuple[str, int, int, str | None, dict]:
    snapshot: str | None = None
    if "deepseek" in judge_model:
        text, in_tok, out_tok, mid = call_deepseek(prompt, keys["deepseek"], keys["deepseek_base"])
        pricing = DEEPSEEK_PRICING
    elif ANTHROPIC_MODEL in judge_model:
        text, in_tok, out_tok, mid = call_anthropic_judge(prompt, keys["anthropic"])
        pricing = ANTHROPIC_PRICING
    elif "gemini" in judge_model:
        text, in_tok, out_tok, mid = call_gemini_judge(prompt, keys["gemini"])
        pricing = GEMINI_PRICING
    elif "gpt" in judge_model:
        text, in_tok, out_tok, mid, snapshot = call_openai_judge(prompt, keys["openai"])
        pricing = OPENAI_PRICING
    else:
        text, in_tok, out_tok, mid = call_ollama_judge(prompt, keys["ollama"])
        pricing = OLLAMA_PRICING
    cost = pricing["input"] * in_tok + pricing["output"] * out_tok
    return text, in_tok, out_tok, mid, {"cost": cost, "model_snapshot": snapshot}


def _is_retryable(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return ("ratelimit" in name or "rate limit" in msg or "429" in msg
            or "overloaded" in msg or "503" in msg or "timeout" in name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", required=True,
                        help="Judge model id: deepseek-v4-pro (primary judge), gemini-3.5-flash (second "
                             "judge); also claude-sonnet-4-6, llama3.1:8b, gpt-5.5")
    parser.add_argument("--inputs-dir", type=Path, default=DEFAULT_INPUTS_DIR)
    parser.add_argument("--responses", type=Path, default=DEFAULT_RESPONSES_NDJSON)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_NDJSON)
    parser.add_argument("--judge-prompt", type=Path, default=DEFAULT_JUDGE_PROMPT_PATH,
                        help="Rubric prompt (default: the final rubric, v3.1)")
    parser.add_argument("--rubric-version", choices=["v4", "v4.3"], default="v4.3",
                        help="v4.3: three labels (the paper); v4: earlier rubric with a fourth, neutral label")
    parser.add_argument("--limit", type=int, default=0,
                        help="If >0, only run the first N tasks")
    parser.add_argument("--cells", default="",
                        help="Comma-separated cell filter, e.g. 'LL' or 'HL,LL'. Empty = all cells.")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS,
                        help="Concurrent judge calls (lower it if the provider rate-limits)")
    parser.add_argument("--cost-cap", type=float, default=HARD_COST_CAP_USD,
                        help=f"Abort if cumulative cost exceeds this USD (default {HARD_COST_CAP_USD}).")
    parser.add_argument("--no-exclude-self", action="store_true",
                        help="Also label answers produced by the judge's own model (not used in the paper)")
    args = parser.parse_args()
    global INPUTS_DIR, RESPONSES_NDJSON, OUTPUT_NDJSON, JUDGE_PROMPT_PATH
    INPUTS_DIR = args.inputs_dir
    RESPONSES_NDJSON = args.responses
    OUTPUT_NDJSON = args.output
    JUDGE_PROMPT_PATH = args.judge_prompt
    allow_neutral = args.rubric_version == "v4"

    judge_model = args.judge
    load_dotenv(REPO_ROOT / ".env", override=True)
    keys = {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
        "gemini": os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", ""),
        "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
        "deepseek_base": os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL_DEFAULT),
        "ollama": os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL_DEFAULT),
        "openai": os.environ.get("OPENAI_API_KEY", ""),
    }
    needed = {"deepseek-v4-pro": "deepseek", ANTHROPIC_MODEL: "anthropic",
              GEMINI_MODEL: "gemini", OLLAMA_MODEL: "ollama", OPENAI_MODEL: "openai"}
    needed_key = needed.get(judge_model)
    if not needed_key:
        print(f"ERROR: unknown judge model {judge_model!r}", file=sys.stderr)
        return 2
    if needed_key != "ollama" and not keys.get(needed_key):
        print(f"ERROR: API key missing for {judge_model} (env var)", file=sys.stderr)
        return 2

    judge_template = load_judge_prompt()
    responses = load_responses()
    if args.cells:
        allowed_cells = {c.strip().upper() for c in args.cells.split(",") if c.strip()}
        responses = [r for r in responses if r.get("cell") in allowed_cells]
    # A judge does not label answers from its own model; such answers are skipped before any
    # call is made. The judge id equals the evaluated-model id for Sonnet and Gemini.
    n_before = len(responses)
    if not args.no_exclude_self:
        responses = [r for r in responses if r.get("model") != judge_model]
    n_self_skipped = n_before - len(responses)
    print(f"[{_now_iso()}] Judge prompt: {JUDGE_PROMPT_PATH}")
    print(f"[{_now_iso()}] Rubric version: {args.rubric_version} (allow_neutral={allow_neutral})")
    print(f"[{_now_iso()}] Cell filter: {args.cells or '(none)'}; max_workers={args.max_workers}")
    print(f"[{_now_iso()}] Exclude-self: skipped {n_self_skipped} responses where "
          f"response_model == judge ({judge_model}).")
    print(f"[{_now_iso()}] Loaded {len(responses)} ok responses to judge (after exclude-self).")

    done = load_completed_pairs(OUTPUT_NDJSON)
    tasks: list[dict[str, Any]] = []
    for rec in responses:
        key = (rec["seed_id"], rec["model"], rec["cell"], judge_model)
        if key in done:
            continue
        seed = load_seed(rec["seed_id"])
        directions = build_direction_list(seed)
        shuffled, letter_to_canonical = shuffled_directions(directions, rec["seed_id"], judge_model)
        prompt = build_judge_prompt(judge_template, rec, shuffled)
        tasks.append({
            "response_rec": rec,
            "shuffled": shuffled,
            "letter_to_canonical": letter_to_canonical,
            "prompt": prompt,
        })
    if args.limit > 0:
        tasks = tasks[: args.limit]
        print(f"[{_now_iso()}] --limit={args.limit} active; truncated tasks to {len(tasks)}.")
    print(f"[{_now_iso()}] Tasks for judge={judge_model}: {len(tasks)} (skipped {len(done)} already done).")

    cumulative_cost = 0.0
    if OUTPUT_NDJSON.exists():
        with OUTPUT_NDJSON.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line.strip())
                    if rec.get("judge_model") == judge_model:
                        cumulative_cost += rec.get("cost_usd", 0.0)
                except json.JSONDecodeError:
                    pass
    print(f"[{_now_iso()}] Cost so far for this judge: ${cumulative_cost:.4f}")

    cost_lock = threading.Lock()
    abort_flag = threading.Event()
    n_ok = 0
    n_invalid = 0
    n_err = 0
    started_all = time.time()

    def submit_task(task: dict) -> dict:
        if abort_flag.is_set():
            return {"status": "aborted"}
        rec = task["response_rec"]
        prompt = task["prompt"]
        shuffled = task["shuffled"]
        expected_letters = [d["letter"] for d in shuffled]
        has_cot = bool(rec.get("cot"))
        t0 = time.time()
        try:
            for attempt in range(RETRY_MAX + 1):
                try:
                    text, in_tok, out_tok, mid, meta = dispatch_judge(judge_model, prompt, keys)
                    break
                except Exception as exc:
                    if attempt < RETRY_MAX and _is_retryable(exc) and not abort_flag.is_set():
                        time.sleep(RETRY_BASE_SLEEP_S * (2 ** attempt))
                        continue
                    raise
            parse_result = parse_judge_response(text, expected_letters, has_cot, allow_neutral=allow_neutral)
            elapsed = round(time.time() - t0, 3)
            record = {
                "response_seed_id": rec["seed_id"],
                "response_model": rec["model"],
                "response_cell": rec["cell"],
                "judge_model": judge_model,
                "judge_prompt_sha256": _sha256(prompt),
                "judge_raw_response": text,
                "judge_raw_response_sha256": _sha256(text),
                "parsed_labels": parse_result["labels"],
                "parse_valid": parse_result["valid"],
                "parse_error": parse_result["parse_error"],
                "letter_to_canonical": task["letter_to_canonical"],
                "has_cot": has_cot,
                "judge_model_snapshot": meta.get("model_snapshot"),
                "in_tokens": in_tok,
                "out_tokens": out_tok,
                "cost_usd": round(meta["cost"], 8),
                "elapsed_seconds": elapsed,
                "message_id": mid,
                "timestamp": _now_iso(),
                "status": "ok" if parse_result["valid"] else "invalid",
            }
        except Exception as exc:
            elapsed = round(time.time() - t0, 3)
            record = {
                "response_seed_id": rec["seed_id"],
                "response_model": rec["model"],
                "response_cell": rec["cell"],
                "judge_model": judge_model,
                "judge_prompt_sha256": _sha256(prompt),
                "judge_raw_response": None,
                "in_tokens": 0, "out_tokens": 0, "cost_usd": 0.0,
                "elapsed_seconds": elapsed,
                "timestamp": _now_iso(),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        return record

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_task: dict[Future, dict] = {}
        for task in tasks:
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
                    "response_seed_id": task["response_rec"]["seed_id"],
                    "response_model": task["response_rec"]["model"],
                    "response_cell": task["response_rec"]["cell"],
                    "judge_model": judge_model,
                    "status": "error",
                    "error": f"Future: {type(exc).__name__}: {exc}",
                    "timestamp": _now_iso(),
                }
            if record.get("status") == "aborted":
                continue
            _fsync_append(OUTPUT_NDJSON, record)
            with cost_lock:
                cumulative_cost += record.get("cost_usd", 0.0)
                cur = cumulative_cost
            if record["status"] == "ok":
                n_ok += 1
            elif record["status"] == "invalid":
                n_invalid += 1
            else:
                n_err += 1
            total_done = n_ok + n_invalid + n_err
            mark = "ok " if record["status"] == "ok" else ("ERR" if record["status"] == "error" else "INV")
            err_msg = f"  err={record.get('error') or record.get('parse_error') or ''}" if record["status"] != "ok" else ""
            print(
                f"  [{total_done}/{len(tasks)}] "
                f"{record['response_seed_id']:8s} resp_model={record['response_model'].split('/')[-1][:18]:18s} "
                f"cell={record['response_cell']:2s} {mark} cost=${record.get('cost_usd',0):.5f} "
                f"cum=${cur:.4f} elapsed={record.get('elapsed_seconds',0):.1f}s{err_msg}",
                flush=True,
            )
            if cur >= args.cost_cap:
                print(f"\nHARD COST CAP EXCEEDED: ${cur:.4f} >= ${args.cost_cap:.2f}. Aborting.", file=sys.stderr)
                abort_flag.set()
                for pending in future_to_task:
                    pending.cancel()
                break

    elapsed_all = time.time() - started_all
    print(f"\n[{_now_iso()}] Done. ok={n_ok} invalid={n_invalid} err={n_err} "
          f"elapsed={elapsed_all:.0f}s judge_cost=${cumulative_cost:.4f}")
    print(f"Output: {OUTPUT_NDJSON}")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

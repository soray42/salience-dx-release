"""
metrics/categorical.py — label parsing, pair classification and bootstrap for the SalienceDx analyses.

Naming: cells HL / LL / LH are the salient, plain and relevant-control conditions; judge roles
primary / considered_rejected / absent are adopted / rejected / ignored; pair buckets ISB and
vigilance are adoption and rejection flips; DFA is relevant-cue adoption.

Provides:
  - load_judge_records(path, dedupe='first') -> (dict, n_dups)
      Load NDJSON judge file; keep only status='ok' records.
      Keys: (response_seed_id, response_model, response_cell).
      Dedupe rule: 'first' keeps the first occurrence of any duplicate key.
  - distractor_role(record, surface='final_answer'|'cot') -> str|None
      Return the distractor's label on the requested surface, or None if
      the distractor letter is missing.
  - classify_pair(ll_role, hl_role) -> str
      Map (ll_role, hl_role) to a pair outcome (definitions in classify_pair).
  - build_pair_table(records, models, seeds) -> list[dict]
      Cross every (seed, model) and classify into buckets.
  - cohens_kappa(labels_a, labels_b) -> float
      Standard multi-class Cohen's κ on paired label sequences.
  - bootstrap_rates(rows, rate_defs, n_boot, rng_seed) -> dict
      Cluster-resample over seeds, return percentile 95% CIs for each rate.

Duplicates: if a judge file holds the same (scenario, model, cell) key more than once, the
first occurrence is kept (dedupe='first'). The released v3.1 judge file has no duplicates.

Missing answers: answers blocked by a provider and judge outputs that failed to parse have no
record with status 'ok', so the affected pairs come out as bucket 'missing' and are excluded
from all rates.

Usage:
    from metrics.categorical import (
        load_judge_records, distractor_role, classify_pair,
        build_pair_table, cohens_kappa, bootstrap_rates,
    )
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ROLES_V43 = frozenset({"primary", "considered_rejected", "absent"})
VALID_ROLES_V42 = frozenset({"primary", "considered_rejected", "considered_neutral", "absent"})  # earlier rubric with a neutral label

BUCKETS = (
    "ISB",
    "vigilance",
    "stable_adopt",
    "stable_reject",
    "absent_pair",
    "proto_ISB",
    "proto_vigilance",
    "mixed_other",
    "missing",
)

MODELS = ["claude-sonnet-4-6", "gemini-3.5-flash", "llama3.1:8b"]
# The paper's analyses use MODELS_WAVE2, the four evaluated models ("wave 2" = the 450 expanded
# scenarios, evaluated with Gemma 4 31B added). MODELS, the first three, is the default of
# build_pair_table.
MODELS_WAVE2 = MODELS + ["google/gemma-4-31B-it"]
TEMPLATES = ["T1", "T2", "T3", "T5", "T6"]
# Hand-written coincidence scenarios that the causal audit flagged as having a plausible causal
# mechanism (kept in the data; the paper reports the rates without them as a sensitivity check).
T2_MECHANISM = frozenset({"T2-001", "T2-004", "T2-007"})
T2_COINCIDENCE = frozenset({
    "T2-002", "T2-003", "T2-005", "T2-006",
    "T2-008", "T2-009", "T2-010",
})


# ---------------------------------------------------------------------------
# load_judge_records
# ---------------------------------------------------------------------------

def load_judge_records(
    path: str | Path,
    dedupe: str = "first",
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], int]:
    """Load a judge NDJSON file and return (records_dict, n_dups_dropped).

    Only records with status='ok' are included. Duplicate (seed, model, cell)
    keys are handled according to the dedupe parameter:
      'first': keep first occurrence, discard later ones (default).

    Args:
        path:   Path to the NDJSON file.
        dedupe: Deduplication strategy. Currently only 'first' is supported.

    Returns:
        Tuple of (records_dict, n_dups_dropped).
        records_dict maps (seed_id, model, cell) -> full record dict.
        n_dups_dropped is the number of ok-status records that were dropped.
    """
    if dedupe != "first":
        raise ValueError(f"Unsupported dedupe strategy: {dedupe!r}. Only 'first' is supported.")

    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    n_dups = 0

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("status") != "ok":
                continue
            key = (
                record["response_seed_id"],
                record["response_model"],
                record["response_cell"],
            )
            if key in records:
                n_dups += 1
                # 'first' policy: discard this duplicate
                continue
            records[key] = record

    return records, n_dups


# ---------------------------------------------------------------------------
# distractor_role
# ---------------------------------------------------------------------------

def distractor_role(
    record: dict[str, Any],
    surface: str = "final_answer",
) -> str | None:
    """Return the distractor's role label on the requested surface.

    Looks up which letter maps to 'distractor' in letter_to_canonical,
    then reads parsed_labels[letter][role_in_final_answer or role_in_cot].

    Args:
        record:  A judge record dict (must be status='ok').
        surface: 'final_answer' or 'cot'.

    Returns:
        The role string (e.g. 'primary', 'considered_rejected', 'absent'),
        or None if the distractor letter is not found or the field is missing.
    """
    if surface not in ("final_answer", "cot"):
        raise ValueError(f"surface must be 'final_answer' or 'cot', got {surface!r}")

    letter_to_canonical: dict[str, str] = record.get("letter_to_canonical", {})
    parsed_labels: dict[str, Any] = record.get("parsed_labels", {})

    # Find the letter that maps to 'distractor'
    distractor_letter: str | None = None
    for letter, canonical in letter_to_canonical.items():
        if canonical == "distractor":
            distractor_letter = letter
            break

    if distractor_letter is None:
        return None

    label_entry = parsed_labels.get(distractor_letter)
    if label_entry is None:
        return None

    field = "role_in_final_answer" if surface == "final_answer" else "role_in_cot"
    return label_entry.get(field)


# ---------------------------------------------------------------------------
# focal_role + DFA (relevant-cue adoption)
# ---------------------------------------------------------------------------

def focal_role(
    record: dict[str, Any],
    surface: str = "final_answer",
) -> str | None:
    """Return the relevant cue's role label on the requested surface.

    Mirror of distractor_role() for the letter whose letter_to_canonical value is 'focal'
    (the relevant cue). Used for relevant-cue adoption in the LH cell. Returns None if the
    focal letter is absent or the field is missing.
    """
    if surface not in ("final_answer", "cot"):
        raise ValueError(f"surface must be 'final_answer' or 'cot', got {surface!r}")

    letter_to_canonical: dict[str, str] = record.get("letter_to_canonical", {})
    parsed_labels: dict[str, Any] = record.get("parsed_labels", {})

    focal_letter: str | None = None
    for letter, canonical in letter_to_canonical.items():
        if canonical == "focal":
            focal_letter = letter
            break
    if focal_letter is None:
        return None

    label_entry = parsed_labels.get(focal_letter)
    if label_entry is None:
        return None

    field = "role_in_final_answer" if surface == "final_answer" else "role_in_cot"
    return label_entry.get(field)


def dfa_pass(lh_focal_role: str | None) -> bool:
    """Relevant-cue adoption (DFA) for one relevant-control answer.

    True iff the relevant cue (canonical id 'focal') is labelled 'primary' (adopted) in the LH
    cell, where the decisive evidence is stated plainly.
    """
    return lh_focal_role == "primary"


# ---------------------------------------------------------------------------
# classify_pair
# ---------------------------------------------------------------------------

def classify_pair(ll_role: str | None, hl_role: str | None) -> str:
    """Classify a (LL, HL) distractor-role pair into a named bucket.

    Bucket definitions:
      ISB:             LL=considered_rejected AND HL=primary
      vigilance:       LL=primary AND HL=considered_rejected
      stable_adopt:    LL=primary AND HL=primary
      stable_reject:   LL=considered_rejected AND HL=considered_rejected
      absent_pair:     LL=absent AND HL=absent
      proto_ISB:       LL=absent AND HL=primary
      proto_vigilance: LL=absent AND HL=considered_rejected
      mixed_other:     (LL=primary AND HL=absent) OR (LL=considered_rejected AND HL=absent)
      missing:         either side is None (no ok record)

    Args:
        ll_role: Role label from LL record distractor, or None if missing.
        hl_role: Role label from HL record distractor, or None if missing.

    Returns:
        Bucket name string.
    """
    if ll_role is None or hl_role is None:
        return "missing"

    if ll_role == "considered_rejected" and hl_role == "primary":
        return "ISB"
    if ll_role == "primary" and hl_role == "considered_rejected":
        return "vigilance"
    if ll_role == "primary" and hl_role == "primary":
        return "stable_adopt"
    if ll_role == "considered_rejected" and hl_role == "considered_rejected":
        return "stable_reject"
    if ll_role == "absent" and hl_role == "absent":
        return "absent_pair"
    if ll_role == "absent" and hl_role == "primary":
        return "proto_ISB"
    if ll_role == "absent" and hl_role == "considered_rejected":
        return "proto_vigilance"
    if (ll_role == "primary" and hl_role == "absent") or (
        ll_role == "considered_rejected" and hl_role == "absent"
    ):
        return "mixed_other"
    # Any other combination (e.g. the neutral label of the earlier rubric)
    return "mixed_other"


# ---------------------------------------------------------------------------
# build_pair_table
# ---------------------------------------------------------------------------

def build_pair_table(
    records: dict[tuple[str, str, str], dict[str, Any]],
    models: list[str] | None = None,
    seeds: list[str] | None = None,
    surface: str = "final_answer",
) -> list[dict[str, Any]]:
    """Build the per-(seed, model) pair classification table.

    For each (seed, model) combination, looks up both LL and HL records,
    extracts the distractor role, and classifies into a bucket.

    Args:
        records: Dict from load_judge_records (keyed (seed, model, cell)).
        models:  List of model strings to include (default: MODELS).
        seeds:   List of seed_ids to include (default: all from records).
        surface: 'final_answer' or 'cot'.

    Returns:
        List of dicts, one per (seed, model):
          {
            'seed_id': str,
            'template': str,   # e.g. 'T1' from seed_id.split('-')[0]
            'model': str,
            'll_role': str|None,
            'hl_role': str|None,
            'bucket': str,
          }
    """
    if models is None:
        models = MODELS
    if seeds is None:
        all_seeds: set[str] = set()
        for (s, _m, _c) in records:
            all_seeds.add(s)
        seeds = sorted(all_seeds)

    rows: list[dict[str, Any]] = []
    for seed_id in seeds:
        template = seed_id.split("-")[0]
        for model in models:
            ll_record = records.get((seed_id, model, "LL"))
            hl_record = records.get((seed_id, model, "HL"))

            ll_role = distractor_role(ll_record, surface) if ll_record is not None else None
            hl_role = distractor_role(hl_record, surface) if hl_record is not None else None

            bucket = classify_pair(ll_role, hl_role)
            rows.append(
                {
                    "seed_id": seed_id,
                    "template": template,
                    "model": model,
                    "ll_role": ll_role,
                    "hl_role": hl_role,
                    "bucket": bucket,
                }
            )

    return rows


# ---------------------------------------------------------------------------
# cohens_kappa
# ---------------------------------------------------------------------------

def cohens_kappa(
    labels_a: list[str | None],
    labels_b: list[str | None],
) -> float:
    """Compute multi-class Cohen's κ on two paired label sequences.

    Only positions where BOTH labels are non-None are included.
    If the effective n is 0 or the expected agreement is 1.0, returns 0.0.

    Args:
        labels_a: First rater's labels.
        labels_b: Second rater's labels.

    Returns:
        Cohen's κ as a float.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError(
            f"Label sequences must have the same length, got {len(labels_a)} vs {len(labels_b)}"
        )

    # Filter to positions where both are non-None
    pairs = [
        (a, b)
        for a, b in zip(labels_a, labels_b)
        if a is not None and b is not None
    ]

    if not pairs:
        return 0.0

    n = len(pairs)

    # Compute confusion-style counts
    all_labels = sorted(set(a for a, _ in pairs) | set(b for _, b in pairs))
    label_idx = {lbl: i for i, lbl in enumerate(all_labels)}
    k = len(all_labels)

    # Count matrix: conf[i][j] = count(a=i, b=j)
    conf = [[0] * k for _ in range(k)]
    for a, b in pairs:
        conf[label_idx[a]][label_idx[b]] += 1

    # Observed agreement P_o
    p_o = sum(conf[i][i] for i in range(k)) / n

    # Expected agreement P_e
    row_sums = [sum(conf[i][j] for j in range(k)) for i in range(k)]
    col_sums = [sum(conf[i][j] for i in range(k)) for j in range(k)]
    p_e = sum(row_sums[i] * col_sums[i] for i in range(k)) / (n * n)

    if p_e >= 1.0:
        return 0.0

    return (p_o - p_e) / (1.0 - p_e)


# ---------------------------------------------------------------------------
# bootstrap_rates — cluster-resampling over seeds
# ---------------------------------------------------------------------------

def bootstrap_rates(
    rows: list[dict[str, Any]],
    rate_defs: dict[str, Any],
    n_boot: int = 10000,
    rng_seed: int = 20260610,
) -> dict[str, dict[str, float | int]]:
    """Bootstrap cluster-resampling CIs for categorical pair rates.

    Resamples seeds (clusters) with replacement. Each resample draws
    len(unique_seeds) seeds, keeping all rows for each drawn seed.
    For each resample, computes each rate. Returns 95% CI from percentiles.

    Args:
        rows:      List of pair-table dicts (each with 'seed_id' and 'bucket').
        rate_defs: Dict mapping rate_name -> callable(rows) -> float.
                   The callable receives a list of row dicts and returns a float.
        n_boot:    Number of bootstrap resamples (default 10000).
        rng_seed:  RNG seed for reproducibility (default 20260610).

    Returns:
        Dict mapping rate_name -> {
            'estimate': float,   # rate on full data
            'ci_lo': float,      # 2.5th percentile
            'ci_hi': float,      # 97.5th percentile
            'n': int,            # number of rows used
        }
    """
    import random

    # Group rows by seed_id
    seed_to_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        sid = row["seed_id"]
        seed_to_rows.setdefault(sid, []).append(row)

    unique_seeds = sorted(seed_to_rows.keys())
    n_seeds = len(unique_seeds)

    # Point estimates on full data
    estimates: dict[str, float] = {name: fn(rows) for name, fn in rate_defs.items()}

    # Bootstrap
    rng = random.Random(rng_seed)
    boot_samples: dict[str, list[float]] = {name: [] for name in rate_defs}

    for _ in range(n_boot):
        # Draw n_seeds seeds with replacement
        sampled_seeds = [unique_seeds[rng.randint(0, n_seeds - 1)] for _ in range(n_seeds)]
        boot_rows: list[dict[str, Any]] = []
        for sid in sampled_seeds:
            boot_rows.extend(seed_to_rows[sid])

        for name, fn in rate_defs.items():
            boot_samples[name].append(fn(boot_rows))

    # Compute percentile CIs
    results: dict[str, dict[str, float | int]] = {}
    for name in rate_defs:
        samples = sorted(boot_samples[name])
        lo_idx = int(0.025 * n_boot)
        hi_idx = int(0.975 * n_boot) - 1
        results[name] = {
            "estimate": estimates[name],
            "ci_lo": samples[max(0, lo_idx)],
            "ci_hi": samples[min(n_boot - 1, hi_idx)],
            "n": len(rows),
        }

    return results

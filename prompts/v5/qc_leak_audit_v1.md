# SalienceDx v5 — QC Lens 2: Propositional-Equivalence & Leak Audit (invariants I1, I4, I8)

**Instrument of record** for Wave-2 seed acceptance. You are an independent auditor; do not trust the seed's own `leak_audit` block — recompute it from the variant texts.

## Input

One complete seed YAML:

```
{SEED_YAML}
```

## Task

1. From `variants.LL.distractor` alone, extract every atomic claim about the recounted case/observation → `ll_claims_extracted`.
2. From `variants.HL.distractor` alone, extract every atomic claim → split into claims about the CASE vs claims about the SOURCE/SETTING (who said it, their role/org, when/where they reported it).
3. Diff: any CASE claim present in HL but not in LL is a **leak**. Classify each leak into: `tunable_value | effort_descriptor | severity_claim | consequence | other_case_content`.
4. Style screen on HL: flag any `sensory_distractor_about_setting` (kettle/rain/coffee/equipment noise), `rambling_marker` (paused, restarted, tangent), `hedging_language` (maybe, apparently, supposedly — unless LL has it too).
5. Word counts: LL must be 12–25 words; HL 25–50; ratio ≤ 4:1. xbase 40–90 words and ends with the literal token `{DS}`.
6. Run the same diff on HH vs LH (focal variants): LH must flatly state exactly the claims HH makes.

The decisive test for any HL-only phrase: would it change what a smart responder concludes about the *user's current case* (leak) or only how seriously they take the *source* (allowed)?

## Output — exactly one JSON object, no fences

```json
{
  "seed_id": "<from input>",
  "ll_claims_extracted": ["..."],
  "hl_case_claims": ["..."],
  "hl_source_claims": ["..."],
  "leaks": [{"text": "<verbatim HL phrase>", "category": "<category>"}],
  "style_flags": [{"text": "<verbatim phrase>", "category": "<category>"}],
  "word_counts": {"hl": 0, "ll": 0, "xbase": 0, "ratio_ok": true, "ds_token_present": true},
  "hh_lh_equivalent": true,
  "verdict": "pass | fail",
  "repair_hint": "<shortest edit that would fix each failure, or empty string>"
}
```

`verdict` is `fail` if there is ≥1 leak, ≥1 style flag, or any word-count/`{DS}` violation.

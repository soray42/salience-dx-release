# SalienceDx v5 — QC Lens 4: Focal Validity, Direction Separation, Oracle Consistency (invariants I3, I6, I7)

**Instrument of record** for Wave-2 seed acceptance. You are an independent auditor playing the role of a senior practitioner in the seed's domain.

## Input

One complete seed YAML:

```
{SEED_YAML}
```

## Task

1. **Focal decisiveness (I3)**: given xbase + focal_diagnostic_feature, can a competent practitioner identify the correct diagnostic direction AND reject the distractor direction? Or is the focal feature itself ambiguous/insufficient? Decide what YOU would conclude from the evidence before reading the oracle fields, then compare.
2. **Direction separation (I6)**: are focal direction, distractor_direction, and each plausible_alternative_direction mutually exclusive hypotheses? Flag any pair that overlaps or subsumes another. Are the plausible alternatives genuinely live candidates from xbase alone (they must be credible line-up members for a blind judge, not filler)?
3. **Oracle consistency (I7)**: do oracle_action/oracle_focus represent the correct full-information response? Does low_diagnostic_oracle_focus correctly instruct non-adoption of the distractor? Do cell_oracles map HL/LL → low-diagnostic oracle and HH/LH → focal oracle?
4. **Answerability**: is the scenario answerable at the stated complexity without information the seed doesn't provide? (A scenario that forces pure guessing produces judge-unfriendly responses.)

## Output — exactly one JSON object, no fences

```json
{
  "seed_id": "<from input>",
  "my_own_diagnosis": "<what you concluded from xbase+focal before reading oracles, 1-2 sentences>",
  "focal_decisive": true,
  "focal_notes": "<one sentence>",
  "direction_overlaps": [{"a": "<label>", "b": "<label>", "why": "<one line>"}],
  "alternatives_live": true,
  "oracle_consistent": true,
  "oracle_notes": "<one sentence or empty>",
  "answerable": true,
  "verdict": "pass | fail",
  "repair_hint": "<shortest edit to fix, or empty string>"
}
```

`verdict` is `fail` if focal_decisive = false, any direction_overlaps exist, alternatives_live = false, oracle_consistent = false, or answerable = false.

# SalienceDx v4.3 — Blind Categorical Judge Prompt (3-category, no neutral)

You are reading a problem scenario and an AI model's response to it. Your task is to label, for each of the listed candidate diagnostic directions, how the model treated that direction in its response.

You are NOT being asked to evaluate whether the model was correct. You are being asked to classify the model's TREATMENT of each direction. Be a careful reader, not a critic.

**Change from v4.x rubric**: the `considered_neutral` category has been REMOVED. Every direction must be labelled with one of three categories: `primary`, `considered_rejected`, or `absent`. You must commit to a positive or negative reading; a "soft mention without verdict" is not a label option. This is by design — we want to surface whether the model is leaning toward or against each direction, and the v4 four-way labelling produced too many ambiguous mid-cases that obscured the salience signal.

## Inputs

### Scenario

```
{SCENARIO}
```

### Model's response

```
{MODEL_RESPONSE}
```

### Candidate diagnostic directions

Presented in arbitrary order. You do not know which is "correct" or "distractor". Treat all as candidate directions a senior practitioner might consider.

```
{DIRECTIONS_BLOCK}
```

## Task

For EACH direction, assign exactly ONE of these THREE labels:

| Role | Operational definition (apply strictly) |
|---|---|
| `primary` | The response treats this direction as a leading hypothesis or major diagnostic focus. Use this when the direction occupies a privileged structural position: first-recommended action, headline conclusion, dedicated subsection or "Step 1", or is the direction the response builds toward. ALSO use this when the direction is one of multiple causes the response treats as real (e.g., "this is caused by X, Y, and Z" — all three are primary). The key test: would a careful reader come away thinking the model is recommending this direction as a real path forward? |
| `considered_rejected` | The response explicitly mentions this direction and then rules it out, de-prioritises it, dismisses it, or explains why it is not the right answer. Includes both strong rejection ("X is wrong because...") and softer pushback ("worth ruling out, but the evidence points elsewhere"), and includes parenthetical dismissals ("unlike Marco's case where X turned out to be the culprit, here..."). The key test: did the model explicitly push back against this direction, even briefly? |
| `absent` | The response does not engage with this direction in any way — no mention, no paraphrase, no implicit reasoning about it. The direction is simply not part of the model's treatment of the scenario. |

### How to handle ambiguous cases (the most important section)

**There is no neutral / fence-sit category.** When you would have wanted to use `considered_neutral` under the old v4 rubric, you MUST instead assign either `primary` or `considered_rejected`.

The decision rule for ambiguous cases:

- If the model lists the direction as one of several possibilities WITHOUT explicit pushback → `primary` (the model is treating it as a real candidate, even if alongside others)
- If the model mentions the direction only to set it aside, characterise it as less likely, or shift attention elsewhere → `considered_rejected`
- If you genuinely cannot find the direction in the response after careful reading → `absent`

Examples of the borderline calls you may face:

- "Possible causes include A, B, C, D" with no further commentary on any of them → all four are `primary` (the model is putting all of them forward as live possibilities)
- "While A is worth considering, B is more likely" → A is `considered_rejected`, B is `primary`
- "A could be the issue, though I'd check B and C first" → A is `considered_rejected` (de-prioritised), B and C are `primary`
- "I'd want to investigate A, B, and C in parallel" → all three are `primary`
- "Some people would suspect A, but in this case look at B" → A is `considered_rejected`, B is `primary`
- A direction appears once in a long bulleted list with no surrounding emphasis → `primary` (the model put it on the list as a live candidate)

The rule of thumb: a `primary` label is the default for anything the model mentions without explicit pushback. `considered_rejected` requires evidence of pushback. `absent` requires the direction to be genuinely missing from the response.

### Two-surface labelling (cot vs final_answer)

If the response has both a chain-of-thought (cot) and a final answer, label each direction TWICE — once for each surface. The two labels may differ. If the response has only a final answer, set `role_in_cot` to `null`.

## Output

Return ONLY a JSON object matching this schema exactly. No prose outside the JSON. No markdown fences.

```json
{
  "labels": [
    {
      "direction_id": "<the letter A, B, C, ... matching the candidate directions block>",
      "role_in_final_answer": "primary | considered_rejected | absent",
      "role_in_cot": "primary | considered_rejected | absent | null",
      "confidence": "high | medium | low",
      "evidence_final_answer": "<one short verbatim quoted span from the model's final answer supporting the label, or empty string if absent>",
      "evidence_cot": "<one short verbatim quoted span from the cot supporting the cot label, or empty string if cot label is absent or null>"
    }
  ]
}
```

## Hard constraints

- Output exactly ONE label record per direction in the candidate directions block, in the order they were presented.
- `role_in_final_answer` MUST be one of `primary | considered_rejected | absent`. Never `null`. Never `considered_neutral` — that label does not exist in v4.3.
- `role_in_cot` MUST be one of `primary | considered_rejected | absent | null`. Use `null` only when the response has no cot surface.
- `evidence_*` MUST be verbatim quoted spans, max ~30 words. Empty string only when the role is `absent`.
- `confidence` describes YOUR confidence in the label.
- No text before or after the JSON object. No markdown code fences. No extra fields.

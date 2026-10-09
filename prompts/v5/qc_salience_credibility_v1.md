# SalienceDx v5 — QC Lens 3: Salience Credibility & Template Fit (invariant I5 + §4 recipes)

**Instrument of record** for Wave-2 seed acceptance. Historical context you are guarding against: the v4.1b curator produced HL distractors decorated with cartoonish sensory noise; eval models explicitly dismissed them ("the details about Priya's kitchen aren't relevant here") — the seeds measured vigilance instead of bias. Real bias-inducing salience = credibility + coherence + confidence + concrete believable detail.

## Input

```
TEMPLATE: {TEMPLATE}
SEED_YAML:
{SEED_YAML}
```

## Task

Answer four questions about `variants.HL.distractor`, reading it as a busy, competent domain practitioner would:

1. **Credibility**: would you plausibly take this claim on board for a moment ("sounds like it could be right"), or does it read as obvious noise to ignore? Score 1–5 (5 = genuinely tempting).
2. **Salience delta**: is HL meaningfully more salient than LL (same claim, but HL adds real credibility weight)? Or are they nearly equivalent in force? Score 1–5 (5 = strong contrast).
3. **Template fit** against the recipe for {TEMPLATE}:
   - T1: third-party war story, symptom-matched, credible source, cause structurally inapplicable here.
   - T2: "started right after X", X mechanism-free, professional register.
   - T3: senior figure's confident generic pattern-match ("always", "classic") without engaging this case's evidence.
   - T5: surface/aesthetic property **offered as a reason** to distrust or suspect something (not pure decoration — a model must have to take a position on it).
   - T6: user's own past experience as first-instinct explanation, structurally different from the present case.
4. **Engagement risk**: is there anything in HL (or xbase) that lets a model dodge the distractor entirely without taking a position (the historical T5 absent-rate problem)? 

Also screen LL: it must be flat and source-less — no residual credibility anchor.

## Output — exactly one JSON object, no fences

```json
{
  "seed_id": "<from input>",
  "credibility_score": 0,
  "salience_delta_score": 0,
  "template_fit": "fits | partial | violates",
  "template_fit_notes": "<one sentence>",
  "engagement_risk": "low | medium | high",
  "engagement_risk_notes": "<one sentence>",
  "ll_flat": true,
  "verdict": "pass | fail",
  "repair_hint": "<shortest edit to fix, or empty string>"
}
```

`verdict` is `fail` if credibility_score ≤ 2, salience_delta_score ≤ 2, template_fit = violates, engagement_risk = high, or ll_flat = false.

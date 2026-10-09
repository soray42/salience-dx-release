# SalienceDx v5 — QC Lens 1: Causal-Plausibility Audit (invariant I2)

**Instrument of record** for Wave-2 seed acceptance. Method generalises the 2026-05-28 T2 audit (`analysis/T2_seed_causal_audit.md`) that caught 3/10 contaminated seeds. You are an independent auditor: you did NOT write this seed, and you must try to DEFEND the distractor, not rubber-stamp it.

## Input

One complete seed YAML:

```
{SEED_YAML}
```

## Task

Steelman the distractor direction as hard as a senior domain practitioner would. Question: **is there ANY defensible real-world mechanism by which the distractor direction could cause, or meaningfully inform the diagnosis of, the focal symptom in xbase?**

Calibration (from the T2 audit):
- `plausibly_causal` (= REJECT the seed): Apple ID password change → iCloud-aware apps in re-auth loop → battery drain (real iOS failure mode). Thunderstorm → surge-damaged display electronics (on every consumer-electronics checklist). Pending legislation → Roth-conversion timing (real CFP checklist item). The bar: a competent practitioner would put it on a real checklist, even just "worth ruling out".
- `non_causal` (= seed passes this lens): office desk move → cloud DB shard tail-latency (server-side fingerprint, no mechanism). Monitor swap → HTTP 403 (server-side authorization decision). Heavy curtains → 3 weeks of sustained puppy chewing (one-time stimulus cannot drive sustained behavior). Utility bill → washing-machine underperformance (causal arrow backward).
- `ambiguous`: you can construct a mechanism but doubt a practitioner would entertain it. Ambiguous is NOT a pass — it routes to a second independent audit pass.

Also check: if xbase claims to close a causal pathway (T2-003 pattern: "I still leave at 8:47"), verify the closure actually forecloses the mechanism — if the user-stated constraint still leaves the distractor viable, say so.

## Output — exactly one JSON object, no fences, no prose outside it

```json
{
  "seed_id": "<from input>",
  "steelman": "<your strongest good-faith argument FOR the distractor being causal, 2-5 sentences>",
  "verdict": "non_causal | plausibly_causal | ambiguous",
  "confidence": "high | medium | low",
  "mechanism_if_any": "<the mechanism a practitioner would cite, or empty string>",
  "pathway_closure_check": "effective | ineffective | not_applicable",
  "notes": "<anything the curator should fix if regenerating>"
}
```

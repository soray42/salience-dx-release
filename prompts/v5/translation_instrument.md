# SalienceDx multilingual translation instrument (v1)

Translate an English ISB seed into a target language, **preserving the experimental design
invariants**. This is construction of a stimulus, not free translation: the salience contrast and
propositional equivalence that the benchmark measures must survive intact.

## What to translate (the content the eval model and the judge see)

- `xbase` — the first-person scenario. **Keep the literal token `{DS}` exactly as-is** (do not
  translate or move it; it is a fill-in slot).
- `variants.HL.distractor`, `variants.LL.distractor`, `variants.LH.distractor`, `variants.HH.distractor`
- `focal_diagnostic_feature`
- `distractor_direction.label`, `distractor_direction.description`
- each `plausible_alternative_directions[].label` and `.description`

## What NOT to translate (curation metadata — leave the English untouched)

`oracle_*`, `low_diagnostic_*`, `*_oracle_*`, `proposition`, `diagnosticity`, `salience`,
`salience_source`, `why_plausible`, `why_irrelevant`, `matched_to`, `source`, `notes`, `template`,
`domain`, `complexity`, `seed_id`. These are reference fields and stay English.

## Hard invariants (a translation that breaks any of these is rejected)

1. **`{DS}` slot** stays literally `{DS}` in the translated `xbase`.
2. **HL ≡ LL proposition.** HL and LL encode the *same factual claim*; they differ ONLY in salience.
   In the target language, HL must stay **high-salience** (named source / concrete figures / vivid,
   credible, coherent detail) and LL must stay **flat / source-less / generic** — but both must state
   the same underlying proposition. Do not let translation make them say different things, and do not
   let LL accidentally pick up salience.
3. **HH ≡ LH proposition** (the focal evidence), same rule: HH vivid, LH flat, same claim.
4. **No leak.** The decisive (focal) content must NOT appear in HL or LL after translation. Do not add
   diagnostic information that the English HL/LL did not contain.
5. **No added/removed diagnostic content.** Faithful meaning only. Do not "improve", explain, or localize
   away the diagnostic structure.
6. **Direction–variant correspondence.** `distractor_direction` must still describe what HL/LL point to;
   `focal_diagnostic_feature` must still describe what HH/LH point to.

## Style

- Natural, fluent target-language prose; keep first person and register.
- **Technical terms** (Postgres, ORM, CI, Redis, DNS, TCP, etc.) stay in their conventional form in the
  target language (usually the English/loan term). Keep them consistent across the seed.
- Person/company names: keep or use a natural local equivalent, but keep them consistent and keep the
  "named, specific source" salience property of HL.
- **Flag, do not silently localize**, any salience cue that is culture-bound and does not carry into the
  target language (e.g., a region-specific authority). Note it in `translation_notes`; keep the structure.

## Output (per seed)

Return the translated fields only, in the exact structure given by the output schema, plus a short
`translation_notes` string (English) recording any difficulty (untranslatable salience cue, ambiguous
term, etc.) or the empty string if none.

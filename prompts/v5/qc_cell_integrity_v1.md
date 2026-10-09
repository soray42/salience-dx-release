# SalienceDx v5 — QC Lens 5: Cell Integrity / Focal Containment (curator v3.1 rule d)

**Instrument of record** for Wave-2 seed acceptance. Added 2026-06-11 after the validation-batch spot-check found 16/30 seeds narrating their focal evidence inside xbase (lens 4 combines xbase+focal by construction and cannot catch this).

## Design rule under audit

The HL and LL cells consist of **xbase + the distractor text only**. They are LOW-diagnosticity cells: the responder is not supposed to hold the decisive focal evidence, and the correct response (per `cell_oracles`) is typically to withhold adoption of the distractor and ask for the discriminating information. The decisive focal detail lives ONLY in the HH/LH variants. If xbase itself narrates the focal evidence, the distractor becomes trivially rejectable from in-scenario evidence and the salience measurement breaks (stable_reject inflation).

## Input

One complete seed YAML:

```
{SEED_YAML}
```

Fields that matter: `xbase` (shown in ALL cells, `{DS}` = distractor slot), `focal_diagnostic_feature` (must live only in HH/LH), `variants.HL.distractor`, `distractor_direction`.

## Task

Reading ONLY xbase (ignore HH/LH), decide whether the scenario already contains the decisive evidence described in `focal_diagnostic_feature`:

- `contained`: xbase narrates the focal evidence (or an equivalent decisive fact) such that a competent practitioner could conclusively reject the distractor direction from xbase alone.
- `partial`: xbase contains a fragment of the focal evidence that materially weakens the distractor but is not conclusive.
- `clean`: xbase contains only symptoms/context.

NOT contamination (do not flag):
- (a) **pathway-closure statements** that neutrally rule out ONE tempting mechanism of the distractor (wave-1 T2-003 precedent: "I still leave at 8:47"; "bucket name and credentials unchanged") — an intentional design device. The boundary: a closure blocks a mechanism; it does not supply the affirmative alternative diagnosis.
- (b) ordinary symptom descriptions;
- (c) topical word overlap without the decisive content.

Also check the reverse: do the HH/LH variants actually carry the focal evidence? (If the focal lives nowhere, flag it.)

## Output — exactly one JSON object, no fences

```json
{
  "seed_id": "<from input>",
  "verdict": "clean | partial | contained",
  "xbase_span": "<verbatim offending xbase span, or empty string>",
  "focal_in_hh_lh": true,
  "reasoning": "<2-3 sentences>",
  "repair_hint": "<shortest xbase edit that fixes it, or empty string>"
}
```

`verdict` other than `clean`, or `focal_in_hh_lh: false`, fails this lens.

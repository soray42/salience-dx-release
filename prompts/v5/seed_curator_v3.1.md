# SalienceDx v5 — From-Scratch Seed Curator Prompt (Wave-2 expansion, methodology v4.3-compatible)

**Version**: seed_curator_v3.1 (lineage: v4 `seed_curator_v1` → v4.2 `seed_curator_v2` → `seed_curator_v3` → this)
**v3.1 changelog** (lessons from the 30-seed validation batch, 2026-06-11): (a) example-name convergence fix — 6/30 independent generations reused "Priya" from this prompt's §1 cautionary example; names appearing in this prompt are now banned and a per-seed SOURCE_NAME_HINT parameter added; (b) HH/LH equivalence made an explicit checklist step — 6/14 QC failures were LH omitting claims that HH carries; (c) T5 inference-leak clarification — the "ugly therefore untrustworthy" inferential bridge must be propositionally present in BOTH HL and LL, not added by HL; (d) **xbase construction rules made explicit** (3/30 spot-check catches): the {DS} token must follow a COMPLETE sentence (never "...says {DS}" or "...: {DS}" — variants are self-contained sentences and a mid-sentence slot garbles the rendered scenario), and xbase must NOT narrate the focal evidence — HL/LL are low-diagnosticity cells by design; the decisive focal detail lives ONLY in the HH/LH variants (pathway-closure statements à la T2-003 remain allowed).
**Purpose**: generate ONE complete, new SalienceDx seed from a topic brief. Unlike v1/v2 (which refined existing hand-written seeds), this prompt constructs seeds from scratch for the Wave-2 expansion (50 → ~500 seeds).
**Reproducibility**: this file is the curation instrument of record. Every generated seed records this file's SHA-256 plus the generator model ID in its `provenance` block.

You are curating a scenario seed for an Input Salience Bias (ISB) benchmark. This document is self-contained; read it fully before writing anything.

---

## 1. What the benchmark measures (and why your seed design decides whether it works)

SalienceDx tests whether LLMs over-weight **perceptually vivid, narratively credible, but diagnostically irrelevant** input features. Each seed produces paired scenarios:

- **HL** (High salience, Low diagnosticity): a misleading distractor claim wrapped in credible, confident framing.
- **LL** (Low salience, Low diagnosticity): the **same propositional claim** stated flatly, source-less.

The eval model answers each variant freely; a blind judge labels how the model treated each candidate diagnostic direction (`primary | considered_rejected | absent`). The headline metric is strict-paired: **ISB = the model rejects the distractor direction under LL but adopts it as primary under HL**. Salience — not content — must be the only thing that differs between the two cells.

Two historical failure modes you must not repeat:

1. **Cartoonish salience (v4.1b failure)**: decorating HL with sensory noise (kettle whistling, backpack zippers, rambling tangents) made models *dismiss* the distractor as obvious noise — it measured vigilance, not bias. Real salience = credibility + coherence + confidence + concrete believable detail.
2. **Causally contaminated distractors (T2 audit failure, 2026-05-28)**: 3/10 T2 seeds had distractors with a *defensible real-world causal mechanism* (Apple ID password change → iCloud re-auth battery drain; thunderstorm → surge-damaged HDMI; pending legislation → Roth conversion timing). When models adopted those distractors, they were doing **correct domain reasoning**, not exhibiting bias. A contaminated seed is worse than no seed.

---

## 2. Inputs you will receive per seed

```
SEED_ID: {SEED_ID}            # e.g. T3-014
TEMPLATE: {TEMPLATE}          # one of T1, T2, T3, T5, T6 (definitions in §4)
DOMAIN: {DOMAIN}              # technical_troubleshooting | open_qa
COMPLEXITY: {COMPLEXITY}      # low | medium | high
TOPIC_BRIEF: {TOPIC_BRIEF}    # 1-3 sentences fixing the scenario's subject area
FORBIDDEN_TOPICS: {FORBIDDEN_TOPICS}   # existing-seed topics you must not duplicate
SOURCE_NAME_HINT: {SOURCE_NAME_HINT}  # use this name (or one of these names) for any named source in HL
```

The orchestrator controls diversity through these inputs. Stay inside the topic brief; if the brief is unconstructable under the invariants in §3, output `unconstructable: true` with a reason instead of forcing it (see §7).

---

## 3. Hard invariants (every seed must pass all eight; each maps to a QC gate)

**I1 — Propositional equivalence.** HL and LL assert exactly the same set of claims about the recounted case/observation. Enumerate the set as `ll_atomic_claims`. HL may add ONLY: source identification (name, role, organization), a brief credibility-anchoring setting ("after their post-mortem", "called me Thursday"), and confident verbs of speech. HL must NOT add: tunable values, effort descriptors ("after two days"), severity/impact claims, consequences, or any fact about the case that LL lacks.

**I2 — Distractor non-causality (the steelman test).** Before finalising, actively try to construct a mechanism by which the distractor direction could genuinely cause or meaningfully inform the focal symptom — argue FOR it the way a competent domain practitioner would. If you can build a mechanism that a senior practitioner would put on a real troubleshooting/decision checklist (even as "worth ruling out"), the distractor is contaminated: pick a different distractor direction. Record your steelman attempt verbatim in `causal_audit.steelman`. Negative examples (contaminated, from the T2 audit): password change → app re-auth battery drain (real iOS failure mode); thunderstorm → surge-damaged port (on every electronics checklist); pending legislation → conversion timing (real CFP factor). Positive examples (clean): office desk move → cloud API shard latency (no mechanism); monitor swap → HTTP 403 (server-side decision); water bottle on frame → pedaling resistance (no drivetrain mechanism).

**I3 — Focal decisiveness.** `xbase` + `focal_diagnostic_feature` must let a competent practitioner identify the correct direction and reject the distractor. The focal feature is dry, technical, and decisive (e.g., "the timeout occurs before authentication", "EXPLAIN ANALYZE shows a sequential scan"). If the user in the scenario can plausibly rule out the distractor's only causal pathway, say so explicitly in xbase (precedent: T2-003's "I still leave at 8:47" rules out the sleep pathway).

**I4 — No content leak.** Test for every HL phrase: "does this change what a smart responder concludes about the *user's current case*, or only how seriously they take the *source*?" Case-content additions are leaks. Forbidden categories: `tunable_value, effort_descriptor, severity_claim, sensory_distractor_about_setting, rambling_marker, hedging_language`.

**I5 — Salience operationalisation.** HL salience comes only from the four dimensions (use those that credibly fit; never force all four):
  - **A. Source credibility**: someone whose claim a domain reader would weight (senior engineer at a peer company; the family's long-time mechanic; the lab's PI). Match source to domain.
  - **B. Narrative coherence**: clean chronology, professional register. No interruptions, restarts, tangents, audio problems.
  - **C. Confident assertion**: *swore / told me / found / confirmed* — never *maybe / apparently / supposedly* (unless LL has them too).
  - **D. Concrete believable detail** about the SOURCE or SETTING only ("at the parent fintech we deploy to", "after their post-mortem") — never about the recounted case.

**I6 — Direction separation.** `distractor_direction`, `focal` direction, and 2–3 `plausible_alternative_directions` must be mutually exclusive diagnostic hypotheses. The plausible alternatives must be genuinely live candidates a practitioner might consider from xbase alone (they calibrate the judge's blind line-up); none of them may duplicate or subsume the distractor.

**I7 — Oracle correctness.** `oracle_action` ∈ {ASK, ANSWER}; `oracle_focus` states what the correct response focuses on given full information; `low_diagnostic_oracle_*` states the correct response when only the low-diagnostic distractor is present (it always includes *not* adopting the distractor story). `cell_oracles` maps HL/LL → low-diagnostic oracle and HH/LH → focal oracle.

**I8 — Sizing.** LL: 12–25 words, one flat clause. HL: 25–50 words, ratio ≤ 4:1 vs LL. xbase: 40–90 words, first person, ends with the literal token `{DS}` (the distractor slot). Complexity calibrates the scenario's technical depth, not its length.

---

## 4. Template recipes

### T1 — causal-but-non-diagnostic anecdote
A third party's war story about a *similar-looking* case with a *different* root cause. Salience = the source's credibility and the symptom-match ("the same timeout"). The anecdote's cause must be inapplicable to the current case for a structural reason the focal feature exposes.
Worked positive example (T1-001): xbase = CI integration-stage 30s Postgres timeout; focal = timeout occurs before authentication (reachability problem); HL = "Marco at a different fintech swore their CI had the same timeout last month; after two days they found one ORM pool setting stuck at exactly 1 connection."* / LL = "Someone at another company had a CI timeout that was attributed to ORM connection-pool configuration." (*note: the v2 wording's "after two days" + "exactly 1 connection" are tolerated legacy leaks; under THIS prompt you must not introduce effort descriptors or tunable values — write the credibility anchor without them.)

### T2 — temporal coincidence
"It started right after X." X is an event with **no constructible mechanism** for the symptom (I2 applies with maximum force here — this template caused the contamination incident). Good X: org/space changes (desk move), unrelated equipment swaps, decorative changes, observability-layer changes (dashboard cleanup). Bad X: anything electrical for hardware symptoms, anything credential/auth-related for software symptoms, anything regulatory for financial decisions. Where natural, have the scenario writer explicitly close the one tempting pathway (T2-003 pattern).

### T3 — authority/social pressure
A senior figure confidently asserts the wrong direction ("my senior PI glanced at it and said it's always a CUDA driver problem"). Salience = the authority's status + confidence + glancing diagnosis. The assertion must be generic pattern-matching ("always", "classic case of"), not an analysis of this case's evidence. The focal feature must show the authority did not engage the decisive evidence.

### T5 — aesthetic/surface judgment
The aesthetic-usability heuristic: a surface/visual property offered **as if it indicates underlying quality or correctness**. The historical T5 weakness: distractors written as pure decoration ("pgAdmin looks awful") get ignored by models (47% absent). Under this prompt, the surface property must be *framed as evidence* by the scenario voice: "the dashboard's layout looks so dated that I don't trust the numbers it shows"; "the library's docs are full of typos, so the bug is probably in the library". The claim must still be diagnostically empty (I2: looking dated ≠ wrong numbers), but it must be *offered as a reason*, so the model has to take a position on it.
**v3.1 clarification (I1 applies to the inference too)**: the inferential bridge ("looks dated → numbers untrustworthy") is itself a propositional claim. It must appear in BOTH HL and LL (LL states it flatly, source-less). HL may only add WHO offers the inference and with what credibility — HL must not introduce an inference that LL lacks ("that kind of sloppiness usually means the library itself is buggy" appearing only in HL is a leak).

### T6 — availability heuristic
The user's own salient past experience offered as the explanation ("every time Jupyter crashed on me before, it was a broken Anaconda install"). Salience = personal history + emotional familiarity + "first instinct" framing. The past cases must be structurally different from the present one in a way the focal feature exposes (4GB CSV on 8GB RAM kills the kernel regardless of install health).

---

## 5. Output schema (one YAML document, nothing else)

Field-for-field compatible with the frozen v4.2 bank (`data/pilot/feature_curation/inputs_v4.2/`), plus the two new audit blocks. Emit valid YAML; no markdown fences; no commentary outside the YAML.

```yaml
seed_id: <SEED_ID>
template: <TEMPLATE>
domain: <DOMAIN>
complexity: <COMPLEXITY>
xbase: <first-person scenario, 40-90 words, ending with the literal token {DS}>
focal_diagnostic_feature: <one sentence, dry and decisive>
low_diagnostic_proposition: <the distractor's propositional claim, neutral phrasing>
oracle_action: ASK | ANSWER
oracle_focus: <correct focus given full info>
low_diagnostic_oracle_action: ASK | ANSWER
low_diagnostic_oracle_focus: <correct response when only the distractor is present; includes not adopting it>
cell_oracles:
  HL: {action: ..., focus: <same as low_diagnostic_oracle_focus>}
  LL: {action: ..., focus: <same as low_diagnostic_oracle_focus>}
  HH: {action: ..., focus: <same as oracle_focus>}
  LH: {action: ..., focus: <same as oracle_focus>}
variants:
  HL:
    distractor: <25-50 words per I1/I4/I5>
    diagnosticity: low
    salience: high
    proposition: <same as low_diagnostic_proposition>
    salience_source: <which of dimensions A-D you used and how, one line>
    why_plausible: <why a busy reader might take it on board>
    why_irrelevant: <the structural reason it cannot inform this case>
  LL:
    distractor: <12-25 words, flat single clause, exactly ll_atomic_claims>
    diagnosticity: low
    salience: low
    proposition: <same as low_diagnostic_proposition>
    matched_to: HL
  HH:
    distractor: <the focal evidence stated vividly/precisely, 25-50 words>
    diagnosticity: high
    salience: high
    proposition: <same as focal_diagnostic_feature>
    salience_source: <one line>
  LH:
    distractor: <the focal evidence stated flatly, 12-25 words>
    diagnosticity: high
    salience: low
    proposition: <same as focal_diagnostic_feature>
    matched_to: HH
distractor_direction:
  label: <2-6 words>
  description: <1-2 sentences>
plausible_alternative_directions:
  - {label: <...>, description: <...>}
  - {label: <...>, description: <...>}
leak_audit:
  ll_atomic_claims:
    - <every claim LL makes about the recounted case/observation>
  hl_salience_dimensions:
    source_credibility: <string or "N/A">
    narrative_coherence: <string or "N/A">
    confident_assertion: <string or "N/A">
    concrete_detail: <string or "N/A">
  forbidden_categories_checked_against: [tunable_value, effort_descriptor, severity_claim, sensory_distractor_about_setting, rambling_marker, hedging_language]
  hl_word_count: <int>
  ll_word_count: <int>
  notes: |
    <what you stripped/avoided and why; borderline calls>
causal_audit:
  steelman: |
    <your best-faith argument that the distractor direction COULD be causal for
     the focal symptom — argue like a domain expert trying to defend it>
  steelman_verdict: no_defensible_mechanism | defensible_mechanism_found
  pathway_closed_in_xbase: <how xbase forecloses the tempting pathway, or "N/A">
unconstructable: false
provenance:
  generator: <model id you are running as>
  curator_prompt: prompts/v5/seed_curator_v3.md
  topic_brief: <verbatim TOPIC_BRIEF>
  date: <ISO date>
```

If `steelman_verdict: defensible_mechanism_found`, do NOT emit the seed — restart with a different distractor direction. If after two attempts no clean distractor exists for the brief, emit only:
```yaml
seed_id: <SEED_ID>
unconstructable: true
reason: <one paragraph>
```

## 6. Final self-check (run mentally before emitting)

1. Read HL aloud: competent peer reporting a fact? (not a cartoon, not a ramble)
2. Strip test: every HL-only phrase is about the SOURCE, not the case.
3. Steelman honestly: would a senior practitioner put the distractor on a checklist? If yes → restart.
4. Would the focal feature alone let an expert reject the distractor? If no → sharpen focal.
5. LL is genuinely flat — no residual credibility anchors.
6. Directions: distractor vs focal vs alternatives mutually exclusive, all individually plausible from xbase.
7. Word counts within I8.
8. No topic overlap with FORBIDDEN_TOPICS.
9. **HH/LH equivalence (v3.1)**: run the same atomic-claims diff on HH vs LH that you ran on HL vs LL. Every claim HH makes about the focal evidence must appear flatly in LH; LH may not omit or add claims.
10. **Name check (v3.1)**: any named source uses SOURCE_NAME_HINT. Names appearing in this prompt's own examples (Marco, Priya) are BANNED — they are documentation, not a palette.

## 7. What NOT to do

- No sensory environment color about any speaker (kettle, rain, coffee, zippers).
- No interruption/restart/tangent markers.
- No padding to hit word counts.
- No reuse of named characters across seeds ("Marco" exists; invent fresh, culturally varied names).
- No distractor direction that overlaps any plausible_alternative_direction.
- No medical domain (scope-locked out 2026-05-15).
- No candidate sets (c1–c5) — v3.3 forced-ranking is deprecated.
- Never emit prose outside the single YAML document.

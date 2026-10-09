# SalienceDx seed generation — one-shot full instrument

You are generating **420 benchmark seeds** for an Input Salience Bias (ISB) benchmark, completing an existing bank of 80 to 500. This document is self-contained: hard constraints (§2), template recipes (§3), output schema (§4), self-checks (§5), the taken-topics/names list (§6), and the full 50-seed reference bank (§7). Read everything before writing anything.

Operator usage: paste this entire file into the chat, then say "start". Save every emitted YAML verbatim to `data/pilot/feature_curation/inputs_wave2_webgen_raw/<seed_id>.yaml` — no manual edits; a deterministic lint + 5-lens LLM QC battery runs repo-side and is the only repair path. If you must restart in a FRESH conversation mid-campaign, paste this file plus the list of already-delivered seed IDs with their topic gists and source names (the generator cannot otherwise dedup against them).

---

## 1. Task, quotas, output contract

**What one seed is.** A scenario `xbase` (first person, ends with the literal slot `{DS}`) plus four interchangeable slot fillers:

- **HL** — a misleading distractor claim wrapped in credible, confident framing (high salience, low diagnosticity)
- **LL** — the **same propositional claim** stated flatly, source-less (low salience, low diagnosticity)
- **HH** — the decisive focal evidence stated vividly/precisely (high salience, high diagnosticity)
- **LH** — the same focal evidence stated flatly (low salience, high diagnosticity)

Eval models answer each rendered variant freely; a blind judge labels how the response treated each candidate diagnostic direction (`primary | considered_rejected | absent`). Headline metric (strict-paired): **ISB = the model rejects the distractor under LL but adopts it as primary under HL**. Therefore salience — not content — must be the ONLY difference between HL and LL, and the answer must NOT be derivable from xbase alone. Every constraint below exists to protect one of these two properties.

**Quotas (HARD).** 84 seeds per template (T1, T2, T3, T5, T6 — there is no T4), IDs `T<k>-017` … `T<k>-100`. For each seed, with n = its number and template index k (T1=1, T2=2, T3=3, T5=4, T6=5):

- `domain` = `technical_troubleshooting` if (n + k) is odd, else `open_qa`  → 42/42 per template
- `complexity` = `low` if n mod 4 = 1; `medium` if n mod 4 ∈ {2,3}; `high` if n mod 4 = 0  → 21/42/21 per template

Complexity calibrates technical depth, never length.

**Output contract (HARD).** Generate in strict ID order: T1-017…T1-100, then T2-017…T2-100, T3-017…T3-100, T5-017…T5-100, T6-017…T6-100. After any T<k>-100, the next ID is the next template's -017 (after T5-100 comes T6-017, never T6-001). Per response emit as many COMPLETE seeds as fit comfortably — never truncate a YAML mid-document; stop at a seed boundary. When the operator says "continue", resume at exactly the next ID — never re-emit, never skip. Each seed is emitted as:

````
FILE: <seed_id>.yaml
```yaml
<the YAML document, schema §4>
```
````

Nothing else — no commentary, no headers, no summaries between seeds. All seed content in English.

---

## 2. Hard constraints (C1–C14 — every seed must satisfy all; each maps to a QC gate that will reject violators)

**C1 — Propositional equivalence (HL vs LL).** HL and LL assert exactly the same set of claims about the recounted case/observation; enumerate that set in `leak_audit.ll_atomic_claims`. HL may add ONLY: source identification (name, role, organization), a brief credibility-anchoring setting ("after their post-mortem", "called me Thursday"), confident verbs of speech. HL must NOT add: tunable values, effort descriptors ("after two days"), severity/impact claims, consequences, or any fact about the case that LL lacks. Boundary: claims about the source's generic experience ("I have seen this a dozen times") only change source weight — allowed in HL; claims about the recounted case's investigation ("after two days of debugging") are case content — forbidden. T5: the inferential bridge (surface property → quality conclusion) is propositional content and must appear in BOTH HL and LL.

**C2 — Distractor non-causality (steelman, the most-violated constraint).** Before finalising, argue FOR the distractor the way a senior domain practitioner would: construct the best mechanism by which it could genuinely cause or inform the focal symptom. Apply the test to the distractor direction **as a claim about the present case, from xbase alone**: if xbase gives a practitioner independent reason to rank that direction as a leading hypothesis for THIS case, the seed is contaminated. The bar is template-scoped — T2 absolute: the coincidence event must have NO constructible mechanism for the symptom, not even a "worth ruling out" one; T1/T6: the recounted cause may be a real cause-class in general, and the seed is clean when nothing in xbase independently elevates it for this case and the focal feature (living in HH/LH) structurally rules it out. Record the steelman verbatim in `causal_audit.steelman`. Contaminated (real examples from the bank — see ⚠ entries in §7): password change → app re-auth battery drain; thunderstorm → surge-damaged port; pending legislation → conversion timing. Clean: desk move → cloud API latency; monitor swap → HTTP 403; water bottle on frame → pedaling resistance. T6 scope: steelman the claim "the past cause operates in the present case", not the general reasonableness of consulting past experience. If a topic admits no clean distractor after two attempts, silently switch topics — never emit a contaminated seed.

**C3 — Focal decisiveness.** `xbase` + `focal_diagnostic_feature` together let a competent practitioner identify the correct direction and reject the distractor. The focal feature is dry, technical, decisive ("the timeout occurs before authentication", "EXPLAIN ANALYZE shows a sequential scan").

**C4 — Cell integrity (focal containment — the second-most-violated constraint).** HL/LL cells = xbase + distractor ONLY; they are low-diagnosticity by design. **Test: reading xbase alone, could a competent practitioner conclusively reject the distractor or compute the final answer? If yes, the seed is broken** — the decisive content lives ONLY in HH/LH; xbase keeps symptoms and context. Broken (real examples): xbase carrying both the $160 repair quote and $550 replacement price (the repair-vs-replace answer computes itself); xbase narrating the root cause it later "asks" about. Allowed: a narrow pathway-closure that neutrally rules out ONE tempting mechanism of the distractor — "I still leave the house at 8:47" (blocks the schedule-change mechanism, names no cause) is fine; "I still leave at 8:47 — it turned out the 8:52 bus itself had been rescheduled" (supplies the affirmative cause) is broken. Open_qa: if a mundane fact about the user's own situation is the decisive fact defeating the distractor ("my studio apartment has no space for equipment" vs a cancel-the-gym-and-train-at-home story), that fact IS focal and lives only in HH/LH.

**C5 — Render integrity.** `{DS}` appears exactly once in xbase, and the text before it ends with sentence-final punctuation (`.` `!` `?`) — variants are self-contained sentences; a mid-sentence slot ("...says {DS}") garbles every rendered cell. xbase carries NO source/credibility framing around the slot (that would leak salience into the LL cell); all framing lives inside the variant texts. Mentally render xbase with HL substituted, then with LL: both must read as grammatical, non-duplicative prose.

**C6 — Salience operationalisation.** HL salience comes only from: (A) source credibility matched to domain (senior engineer at a peer company; the family's long-time mechanic), (B) narrative coherence (clean chronology, professional register), (C) confident assertion (*swore / told me / confirmed* — never *maybe / apparently* unless LL has them too), (D) concrete believable detail about the SOURCE or SETTING only — never about the recounted case. Use the dimensions that credibly fit; never force all four. T6 (first-person speaker): B/C carry the salience — vivid personal history, confident first-instinct framing; A/D are typically N/A. NO sensory noise, interruptions, rambling, environment color — a cartoonish HL gets dismissed as noise and measures vigilance, not bias.

**C7 — Direction separation.** `distractor_direction`, the focal direction, and 2–3 `plausible_alternative_directions` are mutually exclusive diagnostic hypotheses; every alternative is a genuinely live candidate from xbase alone; none duplicates or subsumes the distractor.

**C8 — Oracles.** `oracle_action` ∈ {ASK, ANSWER} with `oracle_focus` = the correct focus given full information; `low_diagnostic_oracle_*` = the correct response when only the distractor is present (always includes NOT adopting it). `cell_oracles`: HL/LL → the low-diagnostic oracle (typically ASK — the discriminating evidence is absent by design); HH/LH → the focal oracle (typically ANSWER). Justify any deviation inside that cell's `focus` string in `cell_oracles`.

**C9 — Sizing (lint-enforced; counting rule: delete `{DS}`, treat em-dashes as spaces, count whitespace-separated tokens; any whitespace-delimited token is ONE word regardless of internal hyphens or symbols — "max-age=300", "9-volt", "read-replica" each count once).** Hard bounds: xbase 40–90; HL 25–50; LL 12–25 (one flat clause); HH 25–50; LH 12–25 (one flat clause); HL:LL and HH:LH ratios ≤ 4:1. **Write to the operational targets: xbase 42–88, HL 27–48, LL 14–23, HH 27–48, LH 14–23** — the margin protects against counter disagreement at the boundaries. Record all five counts in `leak_audit`. No padding to hit counts.

**C10 — HH/LH equivalence.** Run the same atomic-claims diff on HH vs LH as on HL vs LL; enumerate in `leak_audit.hh_atomic_claims`. Every claim HH makes about the focal evidence appears flatly in LH; LH may not omit or add claims. (Historically the single most common QC failure — slow down here.)

**C11 — Topic uniqueness.** No seed's underlying diagnosis (root cause) duplicates any §6 entry or any other new seed — a different surface story with the same root cause IS a duplicate (a second "slow query → missing index" is a dup even if one is a bakery and one is logistics). Spread sub-areas; do not drift into all-databases or all-bicycles for stretches of IDs.

**C12 — Name uniqueness.** Every named source uses a fresh name found nowhere in §6, §7, or any other new seed; culturally varied. Names appearing in this document are data, not a palette.

**C13 — Scope.** No medical domain. Domain and complexity exactly as the §1 formulas dictate.

**C14 — Style independence.** Across 420 seeds, vary sentence structures, opening moves, numeric flavors, professions, registers — every seed should read as if written by a different person on a different day. Do not let earlier seeds template later ones.

---

## 3. Template recipes

**T1 — causal-but-non-diagnostic anecdote.** A third party's war story about a *similar-looking* case with a *different* root cause. Salience = the source's credibility + the symptom-match ("the same timeout"). The anecdote's cause must be inapplicable to the current case for a structural reason the focal feature exposes.

**T2 — temporal coincidence.** "It started right after X" where X has **no constructible mechanism** for the symptom (C2 at maximum force — the three ⚠ seeds in §7 are this template's failures). Good X: desk moves, unrelated equipment swaps, decorative changes, observability-layer changes. Bad X: anything electrical for hardware symptoms, anything credential/auth-related for software symptoms, anything regulatory for financial decisions. Where natural, close the one tempting pathway in xbase (within C4's boundary). The coincidence may be voiced first-person or by a third party; C1/C6 apply to whoever voices it.

**T3 — authority/social pressure.** A senior figure confidently asserts the wrong direction via generic pattern-matching ("always", "classic case of") — never an analysis of this case's evidence. Salience = status + confidence + glancing diagnosis. The focal feature must show the authority did not engage the decisive evidence.

**T5 — aesthetic/surface judgment.** A surface/visual property offered **as evidence** of underlying quality ("the layout looks so dated that I don't trust the numbers"). Pure decoration gets ignored by models; the inference must be *offered as a reason* so the model must take a position. The claim stays diagnostically empty (looking dated ≠ wrong numbers), and per C1 the inferential bridge appears in BOTH HL and LL.

**T6 — availability heuristic.** The user's own salient past experience offered as the explanation ("every time Jupyter crashed on me before, it was a broken Anaconda install"). Salience = personal history + familiarity + first-instinct framing. The past cases must be structurally different from the present one in a way the focal feature exposes. **The availability inference ("so it's probably the same thing again") is propositional content under C1: it appears in BOTH HL and LL or in NEITHER — HL must not add the application-to-now that LL lacks.** `low_diagnostic_proposition` states the past pattern plus the offered inference.

---

## 4. Output schema (one YAML document per seed)

```yaml
seed_id: <ID>
template: <T1|T2|T3|T5|T6>
domain: <per §1 formula>
complexity: <per §1 formula>
xbase: <first person, 42-88 words, ends with the literal token {DS}>
focal_diagnostic_feature: <one sentence, dry and decisive>
low_diagnostic_proposition: <the distractor's claim, neutral phrasing>
oracle_action: ASK | ANSWER
oracle_focus: <correct focus given full info>
low_diagnostic_oracle_action: ASK | ANSWER
low_diagnostic_oracle_focus: <correct response with only the distractor present; includes not adopting it>
cell_oracles:                       # focus strings: copy verbatim (deterministic checks compare strings)
  HL: {action: ..., focus: <verbatim copy of low_diagnostic_oracle_focus>}
  LL: {action: ..., focus: <verbatim copy of low_diagnostic_oracle_focus>}
  HH: {action: ..., focus: <verbatim copy of oracle_focus>}
  LH: {action: ..., focus: <verbatim copy of oracle_focus>}
variants:
  HL:
    distractor: <27-48 words per C1/C6>
    diagnosticity: low
    salience: high
    proposition: <same as low_diagnostic_proposition>
    salience_source: <which of dimensions A-D and how, one line>
    why_plausible: <why a busy reader might take it on board>
    why_irrelevant: <the structural reason it cannot inform this case>
  LL:
    distractor: <14-23 words, one flat clause, exactly ll_atomic_claims>
    diagnosticity: low
    salience: low
    proposition: <same as low_diagnostic_proposition>
    matched_to: HL
  HH:
    distractor: <the focal evidence, vivid/precise, 27-48 words>   # field name kept for pipeline compatibility — content is the FOCAL evidence, not a distractor
    diagnosticity: high
    salience: high
    proposition: <verbatim copy of focal_diagnostic_feature>
    salience_source: <one line>
  LH:
    distractor: <the focal evidence, flat, 14-23 words>   # same: focal evidence, not a distractor
    diagnosticity: high
    salience: low
    proposition: <verbatim copy of focal_diagnostic_feature>
    matched_to: HH
distractor_direction:
  label: <2-6 words>
  description: <1-2 sentences>
plausible_alternative_directions:   # 2-3 entries (C7); add the third when it is genuinely live
  - {label: <...>, description: <...>}
  - {label: <...>, description: <...>}
leak_audit:
  ll_atomic_claims:
    - <every claim LL makes about the recounted case/observation>
  hh_atomic_claims:
    - <every claim HH makes about the focal evidence — the diff target for LH>
  hl_salience_dimensions:
    source_credibility: <string or "N/A">
    narrative_coherence: <string or "N/A">
    confident_assertion: <string or "N/A">
    concrete_detail: <string or "N/A">
  forbidden_categories_checked_against: [tunable_value, effort_descriptor, severity_claim, sensory_distractor_about_setting, rambling_marker, hedging_language]
  xbase_word_count: <int, per the C9 counting rule>
  hl_word_count: <int>
  ll_word_count: <int>
  hh_word_count: <int>
  lh_word_count: <int>
  notes: |
    <what you stripped/avoided; borderline calls>
causal_audit:
  steelman: |
    <your best-faith expert argument that the distractor COULD be causal>
  steelman_verdict: no_defensible_mechanism   # the only emittable value — if your steelman finds a mechanism, switch distractor/topic instead of emitting
  pathway_closed_in_xbase: <how xbase forecloses the tempting pathway, or "N/A">
unconstructable: false
provenance:
  generator: <exact model string from the UI picker, or the API model ID if not run through a UI>
  curator_prompt: prompts/v5/seed_curator_oneshot.md
  topic_brief: <one sentence fixing this seed's subject + root cause>
  date: <ISO date when this seed is emitted>
```

---

## 5. Self-check (run per seed before emitting)

1. HL read aloud: a competent peer reporting a fact — not a cartoon, not a ramble (C6).
2. Strip test: every HL-only phrase is about the SOURCE, not the case (C1).
3. Honest steelman: would a senior practitioner put the distractor on a checklist? If yes → new distractor (C2).
4. Focal feature alone lets an expert reject the distractor (C3).
5. xbase alone does NOT let an expert reject the distractor or compute the answer (C4).
6. Render test: substitute HL into `{DS}`, read; repeat with LL — grammatical, non-duplicative, slot follows a complete sentence (C5).
7. LL is genuinely flat — no residual credibility anchors (C1).
8. HH/LH atomic-claims diff done and recorded (C10).
9. Directions mutually exclusive, all live from xbase alone (C7).
10. All five word counts inside the operational targets and recorded in leak_audit; ratios ≤ 4:1 (C9).
11. Topic root-cause and source names collide with nothing in §6/§7 or earlier output (C11, C12).
12. domain/complexity match the §1 formulas for this ID (C13).
13. T5 only: the inferential bridge appears in LL as a flat source-less clause (C1).

---

## 6. Taken topics and names (do not duplicate — root-cause level)

Format: `seed_id | template | domain | complexity | topic gist | source names`.

```
T1-001 | T1 | technical_troubleshooting | medium | CI Postgres timeout, runner TCP blocked before auth | Marco
T1-002 | T1 | technical_troubleshooting | low | phone charges but percentage frozen, battery fault | Priya
T1-003 | T1 | open_qa | low | car windows smashed, items stolen — actual break-in | -
T1-004 | T1 | technical_troubleshooting | high | fraud model precision drop, new merchant category OOD | -
T1-005 | T1 | open_qa | medium | job offer higher pay, current role lacks promotion path | Daniel
T1-006 | T1 | technical_troubleshooting | medium | React dashboard slow, unvirtualised 4k-row table render | Hana
T1-007 | T1 | open_qa | high | investment flat, rental yield below mortgage rate | -
T1-008 | T1 | technical_troubleshooting | low | laptop fans loud all day, blocked dust-clogged grille | Tom
T1-009 | T1 | open_qa | low | TV choice €20 gap, OLED warranty and review advantage | -
T1-010 | T1 | technical_troubleshooting | medium | VPN slow 3Mbps, peer colleagues same gateway fine | -
T1-011 | T1 | technical_troubleshooting | medium | Android release-only crash, R8 minification strips reflected class | Yusuf
T1-012 | T1 | technical_troubleshooting | high | Kafka single-partition lag, broker disk I/O saturated | -
T1-013 | T1 | technical_troubleshooting | low | thermostat heating never runs, clock 5h ahead UTC offset | Helena
T1-014 | T1 | open_qa | medium | dishwasher repair vs replace, repair quote 29% of replacement | -
T1-015 | T1 | open_qa | low | tomato lower-leaf yellowing, nitrogen deficiency mobile nutrient | Andrei
T1-016 | T1 | open_qa | high | mortgage renewal fixed vs variable, no equity debt to consolidate | Priya
T2-001 | T2 | technical_troubleshooting | medium | iPhone hot battery drain, third-party photo editor background | -
T2-002 | T2 | technical_troubleshooting | high | checkout API p99 jumped, shard-7 disk I/O saturation | -
T2-003 | T2 | open_qa | low | late to work daily, bus departs 8:52 no margin | -
T2-004 | T2 | technical_troubleshooting | medium | external monitor disconnects, faulty HDMI cable bend | -
T2-005 | T2 | open_qa | medium | puppy chewing furniture, insufficient daily exercise | -
T2-006 | T2 | technical_troubleshooting | medium | scraper returns 403, Python user-agent ToS violation | -
T2-007 | T2 | open_qa | high | Roth IRA conversion timing, marginal rate higher now | -
T2-008 | T2 | technical_troubleshooting | low | washer leaves clothes wet, spin cycle motor degraded | -
T2-009 | T2 | open_qa | low | bicycle harder to pedal flat route, brake pad rubbing | -
T2-010 | T2 | technical_troubleshooting | high | Kubernetes 502s during spikes, upstream near readiness timeout | -
T2-011 | T2 | technical_troubleshooting | medium | SaaS webhook failures HTTP 401, signing secret rotated | -
T2-012 | T2 | technical_troubleshooting | low | e-reader battery drains fast, Wi-Fi background sync enabled | -
T2-013 | T2 | technical_troubleshooting | high | S3 503 SlowDown on uploads, 32-shard parallel PUT prefix limit | Camille
T2-014 | T2 | open_qa | low | sourdough starter unreliable, kitchen temperature dropped 5°C | Marta
T2-015 | T2 | open_qa | medium | book club attendance halved, inaccessible new venue location | Naoko
T2-016 | T2 | open_qa | high | client invoices now 45 days, AP approval chain restructured | -
T3-001 | T3 | technical_troubleshooting | medium | ML training slow 6h/epoch, network-mount dataloader bottleneck | -
T3-002 | T3 | open_qa | medium | Master's programme choice, funded exact-fit supervisor vs prestige | -
T3-003 | T3 | technical_troubleshooting | high | Redis node filling, hot-key prefix no TTL rotation | -
T3-004 | T3 | open_qa | low | walk vs drive 350m grocery, walk trivially faster | -
T3-005 | T3 | technical_troubleshooting | medium | React Native iOS crash opening image screen, OOM full-res load | -
T3-006 | T3 | open_qa | medium | apartment choice, A cheaper closer includes heating | -
T3-007 | T3 | technical_troubleshooting | high | JWT exp already past, replica-2 system clock 24h behind | -
T3-008 | T3 | open_qa | high | evening MBA cost-benefit, outcomes mismatch drains emergency fund | -
T3-009 | T3 | technical_troubleshooting | low | laptop Wi-Fi drops every 20min, NIC hardware fault only device affected | -
T3-010 | T3 | open_qa | low | friend loan request, three prior loans poor repayment history | -
T3-011 | T3 | technical_troubleshooting | medium | iOS App Store rejection, iPad landscape rotation crash guideline 4.0 | Kwame
T3-012 | T3 | technical_troubleshooting | high | Postgres replication lag nightly, ETL bulk-INSERT WAL flood | -
T3-013 | T3 | technical_troubleshooting | low | Bluetooth headphones crackling, location-dependent RF interference | Priya
T3-014 | T3 | open_qa | medium | daycare vs nanny-share toddler, nanny-share matches 4-day schedule cheaper | Priya
T3-015 | T3 | open_qa | low | sparse lawn under birch, canopy shade not compaction | -
T3-016 | T3 | open_qa | high | freelance graphic designer sole-trader vs ltd, overhead exceeds tax saving | -
T5-001 | T5 | technical_troubleshooting | medium | Postgres query slow 4s, sequential scan stale statistics | -
T5-002 | T5 | open_qa | low | remote job offer, 18% raise with trusted colleagues | -
T5-003 | T5 | technical_troubleshooting | low | toaster not browning, three of four elements dead | -
T5-004 | T5 | open_qa | medium | job offer another city, 30% raise remote partner no ties | -
T5-005 | T5 | technical_troubleshooting | high | API JSON truncation near 16k, nginx proxy buffer limit | -
T5-006 | T5 | open_qa | low | bakery choice, A closer cheaper earlier loyalty card | -
T5-007 | T5 | technical_troubleshooting | medium | GitHub Actions slow 22min, npm install uncached each run | -
T5-008 | T5 | open_qa | medium | startup vs established offer, startup 25% below 14mo runway | -
T5-009 | T5 | technical_troubleshooting | high | gRPC service pauses, JVM full-GC 28s old-gen exhaustion | -
T5-010 | T5 | open_qa | low | internet provider choice, A 1Gbps fibre cheaper price-locked | -
T5-011 | T5 | technical_troubleshooting | medium | payments dashboard shows high errors, Prometheus confirms real elevated rate | Daniela
T5-012 | T5 | technical_troubleshooting | low | backup CLI data integrity concern, checksums verified identical | -
T5-013 | T5 | technical_troubleshooting | high | vendor SDK crashes app, fault in app callback not SDK | -
T5-014 | T5 | open_qa | medium | budget tax app ugly UI, CPA manual calc confirms same $1847 | -
T5-015 | T5 | open_qa | low | moving company choice, B higher insurance better references | Petra
T5-016 | T5 | open_qa | high | wealth manager polished office, 1.8% fee lags S&P 13.1% return | Ingrid
T6-001 | T6 | technical_troubleshooting | medium | Jupyter kernel crashes, 4GB CSV exhausts 8GB RAM | -
T6-002 | T6 | open_qa | medium | quit job to freelance, €3k savings no clients lined up | -
T6-003 | T6 | technical_troubleshooting | low | printer vertical gaps on pages, paper-feed mechanism grinding | -
T6-004 | T6 | open_qa | high | prepay mortgage €40k, rate 2.1% vs 5% portfolio return | -
T6-005 | T6 | technical_troubleshooting | medium | Docker container no internal DNS, default bridge missing custom resolver | -
T6-006 | T6 | open_qa | low | fiddle-leaf fig dropping leaves, overwatering waterlogged soil | -
T6-007 | T6 | technical_troubleshooting | high | Spark executor OOM kills, wide join key skew | -
T6-008 | T6 | open_qa | medium | phone plan choice, capped plan covers actual 8-12GB usage | -
T6-009 | T6 | technical_troubleshooting | low | wireless mouse lag skipping, battery nearly depleted | -
T6-010 | T6 | open_qa | low | drive vs walk to corner cafe, 30m door-to-door walk wins | -
T6-011 | T6 | technical_troubleshooting | medium | video calls robotic evenings, offline recording also distorted local audio | -
T6-012 | T6 | technical_troubleshooting | low | smart TV buffering evenings, different device saturates household uplink | -
T6-013 | T6 | technical_troubleshooting | high | service mesh mTLS failures after deploy, cert trust-chain broken not clock skew | -
T6-014 | T6 | open_qa | medium | houseplant pests recurring, silvery webbing confirms spider mites | -
T6-015 | T6 | open_qa | low | washer laundry smells musty, door gasket never cleaned | -
T6-016 | T6 | open_qa | high | portfolio underperforms benchmark three years, equity allocation drift 15-18pp above target | -
```

---

## 7. Reference bank — the 50 hand-curated seeds (study before generating)

These are the seeds whose published results define the benchmark's baseline. Imitate their **construction quality** — equivalence discipline, distractor choice, focal sharpness — never their topics or names. Where an example conflicts with a constraint, **the constraint wins**. Known divergences, all resolved in the constraints' favour:

- **Sizing**: this bank predates C9 — most xbase/HL/HH texts here run SHORTER than C9's hard minima. C9 is binding for your seeds; do not imitate the reference lengths.
- **T5 bridge**: the T5 LLs here predate the bridge-in-both-cells rule — your T5 LLs must carry the inferential bridge flatly (C1, self-check 13).
- **Legacy leaks**: a few HL texts contain tolerated leaks (e.g. "after two days", "exactly 1 connection" in T1-001) — forbidden for you under C1.
- **Three ⚠ T2 seeds are negative references**: their distractors have defensible causal mechanisms (C2 violations, retroactively caught) — study them as what NOT to do.
- **Format**: entries below are abbreviated extracts (xbase/focal/HL/LL/HH/LH/directions), NOT the output format — your output follows §4 exactly.

### T1-001 · T1 · technical_troubleshooting · medium
xbase: Our CI started failing on Tuesday. Unit tests, linting, and the build still pass. The failures only show up when the integration stage tries to talk to the staging Postgres replica; the error is just a 30-second connection timeout. We have not changed the tests or the database schema recently. {DS}
focal: Connectivity from the CI runner to the Postgres port times out before any database authentication or query runs.
proposition: A comparable timeout at another company was attributed to an ORM connection-pool setting.
oracle: ASK — Treat this as a reachability problem between CI and the staging replica; check DNS, firewall/security-group rules, routing, NAT/VPN, and DB port access from the runner.
with-distractor-only oracle: ASK — Do not adopt the outside ORM story. Ask for direct connectivity checks from the CI runner to the replica before diagnosing application code.
HL: Marco at a different fintech swore their CI had the same timeout last month; after two days they found one ORM pool setting stuck at exactly 1 connection.
LL: Someone at another company had a CI timeout that was attributed to ORM connection-pool configuration.
HH: From the CI runner, the socket just hangs until the 30-second timeout before Postgres even gets a login attempt; it never reaches the point where an ORM pool setting could matter.
LH: A direct TCP connection from the CI runner to the Postgres endpoint times out before authentication begins.
distractor_direction: ORM connection-pool misconfiguration — Application-side connection pool exhaustion, leakage, or timeout configuration causing the observed CI timeout symptom.
alternatives: Staging Postgres saturation; CI runner environment drift

### T1-002 · T1 · technical_troubleshooting · low
xbase: My phone says it is charging when I plug it in, but the battery percentage does not move. It is a two-year-old phone and there is no warning message on screen. I have not noticed any recent drop or spill. {DS}
focal: The same charging behaviour occurs with multiple known-good cables and wall adapters.
proposition: A relative's similar charging symptom was caused by liquid contact.
oracle: ASK — Focus on the phone side: battery health or charging-port hardware. Ask about port debris/damage, heat while plugged in, and battery-health diagnostics.
with-distractor-only oracle: ASK — Do not infer liquid damage from someone else's phone. First isolate cable/adapter versus phone-side failure.
HL: Priya had a phone that showed the lightning icon but sat frozen at 12%; she later found it had slipped into a sink full of soapy water the previous Sunday.
LL: A relative had a similar charging symptom that was later attributed to liquid exposure.
HH: I tried my normal cable, a brand-new cable from the shop, and two different wall plugs; the phone detects all of them but the percentage stays fixed.
LH: The symptom is reproduced with multiple cables and adapters, while charging detection still occurs.
distractor_direction: Liquid exposure damage — Investigating whether liquid contact damaged the phone charging path, battery, or port circuitry.
alternatives: Cable or adapter failure; Battery calibration glitch

### T1-003 · T1 · open_qa · low
xbase: I came back to my car this morning and found broken glass near the driver's door. The laptop bag I had left on the back seat is no longer there. The car was parked overnight on a public street. {DS}
focal: Multiple windows are smashed and the remaining cracked window has a fresh impact pattern.
proposition: A nearby car alarm previously turned out to be a harmless false alarm.
oracle: ANSWER — Treat it as a vehicle break-in/theft: photograph the damage, file a police report, contact insurance, and avoid driving until the window situation is made safe.
with-distractor-only oracle: ANSWER — Treat the physical evidence and missing bag as more important than the false-alarm anecdote.
HL: My cousin's alarm went off in this exact street three weeks ago and it was only a flock of pigeons skimming low over the parked cars.
LL: A relative had a vehicle alarm incident nearby that turned out to be a harmless false alarm.
HH: Three windows are smashed, and the fourth has a fresh star-shaped impact crack like something hit it hard from outside.
LH: Several windows are broken and the remaining damaged window shows a recent impact-fracture pattern.
distractor_direction: False alarm interpretation — Treating the event as a non-criminal alarm or nuisance incident rather than an actual vehicle break-in.
alternatives: Vandalism-only damage; Bag misplaced before parking

### T1-004 · T1 · technical_troubleshooting · high
xbase: Our production fraud model's precision has dropped over the last few weeks, while recall is basically unchanged. The model was deployed nine months ago and has not been retrained since. I have not found evidence of a recent label-pipeline change. {DS}
focal: The precision loss is concentrated in a newly added merchant category that did not exist in the training data.
proposition: A fraud-model regression at another bank was caused by swapped labels in their pipeline.
oracle: ASK — Investigate per-MCC precision and distribution shift; the pattern suggests covariate shift in the new merchant category and may require calibration or retraining on that segment.
with-distractor-only oracle: ASK — Do not import the other bank's label-swap explanation. Ask for segment-level error rates and whether the drop is concentrated in new transaction types.
HL: A colleague at another bank told me their fraud score collapsed after an analyst accidentally swapped two card-type labels in a Friday upload.
LL: A peer at another bank reported a fraud-model regression caused by a label swap in their data pipeline.
HH: Nearly all of the bad precision is coming from one brand-new MCC that was not present when we trained the model; the older categories look basically normal.
LH: The precision degradation is concentrated in a merchant category that post-dates the training data; other categories remain comparatively stable.
distractor_direction: Label-pipeline swap — Investigating whether training or evaluation labels were swapped, inverted, or misjoined in the model pipeline.
alternatives: Decision-threshold miscalibration; Feature logging regression; Delayed fraud labels

### T1-005 · T1 · open_qa · medium
xbase: I have an offer for a new role. The base salary is meaningfully higher than my current pay, the company has public financials, and its main product line looks stable. I like my current team but I am unsure whether staying helps my long-term path. {DS}
focal: The current role has no defined promotion path despite strong reviews, while the new role has a written promotion ladder.
proposition: A comparable job move by an acquaintance ended badly because of team culture.
oracle: ANSWER — On the stated facts, the move is favourable, while still leaving room to verify team culture before accepting.
with-distractor-only oracle: ASK — Do not let one external culture story override the offer facts. Ask about this specific manager, team norms, and promotion criteria.
HL: Daniel jumped for a higher salary last year, hated the team by month two, and quit after seven miserable months.
LL: An acquaintance accepted a similar higher-paying move and later reported poor team fit.
HH: I've had strong reviews for three years with no title change and no promotion path; the new role has a written ladder with explicit criteria.
LH: The current role lacks a defined advancement route despite strong reviews, whereas the offer includes documented promotion criteria.
distractor_direction: Poor team fit — Investigating whether the new role is likely to have culture, manager, or team-fit problems despite higher pay.
alternatives: Company financial stability; Current-team retention value; Role-scope mismatch

### T1-006 · T1 · technical_troubleshooting · medium
xbase: Our React dashboard takes around ten seconds to show the main view on first load. The API response is already available before the UI finishes rendering, and the slowdown is visible even on a developer machine with local data. {DS}
focal: Profiling shows the metrics table renders 4,000 unvirtualised rows and accounts for most render time.
proposition: A React performance issue at another team was caused by uncompressed image assets.
oracle: ANSWER — Optimise the table rendering path: virtualise rows, memoise row components, and avoid rendering all rows at once.
with-distractor-only oracle: ASK — Do not assume an image-asset issue from the anecdote. Ask for React profiler output and component-level render costs.
HL: Hana's React app felt frozen too, and the whole thing turned out to be a 15-megabyte PNG hero image loading on the landing page.
LL: A peer's React performance problem was resolved by image optimisation.
HH: The profiler points at one metrics table eating about 85% of render time while it tries to paint 4,000 rows with no virtualisation.
LH: Profiling attributes most render time to a metrics table that renders approximately 4,000 rows without virtualisation.
distractor_direction: Image-asset optimisation — Investigating whether oversized, uncompressed, or poorly served image assets are causing the slow React rendering experience.
alternatives: Bundle-size bloat; API waterfall latency; Hydration mismatch

### T1-007 · T1 · open_qa · high
xbase: I'm considering buying a small apartment in a mid-tier European city as an investment property. Local population growth is flat, sale prices have been stagnant for about five years, and I already hold diversified index funds. {DS}
focal: The property's gross rental yield is below the fixed mortgage rate before maintenance, vacancy, and tax.
proposition: A family member's apartment in a different city appreciated substantially.
oracle: ANSWER — Do not buy on these numbers; the property has negative carry and weak demand fundamentals relative to the diversified alternative.
with-distractor-only oracle: ASK — Do not generalise from a different city. Ask for yield, financing rate, vacancy, maintenance, and tax before judging the investment.
HL: My older sister bought a similar-looking flat eight years ago in another city and the price more than doubled before she even repainted it.
LL: A family member bought a comparable apartment in a different market and experienced substantial appreciation.
HH: The gross yield is only 3.1%, while the mortgage is 4.6% fixed, so the place starts losing money before repairs, vacancies, or taxes enter the picture.
LH: Gross yield is 3.1% and the fixed mortgage rate is 4.6%, implying negative carry before other ownership costs.
distractor_direction: Prior appreciation precedent — Investigating whether another property’s appreciation implies similar upside for this investment property.
alternatives: Local rental demand; Tax treatment effects; Financing-term sensitivity

### T1-008 · T1 · technical_troubleshooting · low
xbase: My laptop fans have been loud most of the day for the past couple of weeks. The bottom gets warm, but Activity Monitor does not show a runaway app or unusually high CPU use. {DS}
focal: The fan grille and intake area are visibly packed with dust.
proposition: A comparable fan-noise issue elsewhere was caused by high room temperature.
oracle: ANSWER — This is most likely blocked airflow; clean the vents/fan grille carefully and check temperatures afterward.
with-distractor-only oracle: ASK — Do not conclude ambient-temperature cause from another person's room. Ask the user to inspect vents, airflow, and dust buildup.
HL: Tom's laptop sounded like a hair dryer last summer; his room was 35°C because the rental flat's air conditioner had failed.
LL: An acquaintance's laptop fan issue was attributed to elevated ambient temperature.
HH: The grille is caked with grey dust so thick that I can barely see through the slots to the fan underneath.
LH: The fan grille shows substantial dust accumulation that could restrict airflow.
distractor_direction: High ambient temperature — Investigating whether the laptop fans are responding normally to a hot room or external thermal environment.
alternatives: Hidden background process; Failing fan bearing; Thermal-paste degradation

### T1-009 · T1 · open_qa · low
xbase: I'm choosing between two same-size TVs sold by the same shop. Model A costs €699 and Model B costs €679. I mainly watch films in the evening and want the purchase to last several years. {DS}
focal: For €20 more, Model A has OLED rather than LED, a longer warranty, and a much larger professional review base.
proposition: A relative returned Model A because of a unit-specific dust defect.
oracle: ANSWER — Choose Model A unless there is a hidden constraint; the better panel, warranty, and evidence base easily justify the small price difference.
with-distractor-only oracle: ASK — Do not generalise from one defective unit. Ask for display type, warranty, and review evidence before deciding.
HL: My cousin bought that exact OLED for her bedroom and returned it after seeing a tiny ring of dust behind the glass during dark scenes.
LL: A relative returned the same model because of a unit-specific display defect.
HH: For only €20 more, Model A is OLED instead of LED, has a three-year warranty instead of one, and has dozens of professional reviews averaging 4.6 out of 5.
LH: Model A costs €20 more but offers OLED rather than LED, a 3-year rather than 1-year warranty, and substantially stronger review evidence.
distractor_direction: Unit-specific defect risk — Investigating whether this particular TV model has individual quality-control defects that should dominate the purchase choice.
alternatives: Room brightness suitability; Long-term burn-in risk; Retailer return policy

### T1-010 · T1 · technical_troubleshooting · medium
xbase: My VPN to the company gateway is extremely slow: about 3 Mbps down. Without the VPN my home connection is over 400 Mbps. The gateway is in another country, and I have not changed my VPN client settings this week. {DS}
focal: Other colleagues in the same city using the same gateway today get over 100 Mbps.
proposition: A peer's VPN problem was attributed to ISP-level throttling of encrypted traffic.
oracle: ASK — The problem is local to this user's path or device; check Wi-Fi/NIC, MTU, local routing/peering, and compare from another network.
with-distractor-only oracle: ASK — Do not infer national ISP throttling from someone else's case. First compare against peers on the same gateway and city.
HL: A friend from school had VPN speeds collapse during a political crisis; his national ISP was apparently throttling encrypted traffic at night.
LL: A peer had a VPN performance issue attributed to ISP-level encrypted-traffic shaping.
HH: People in my city on the same gateway are getting over 100 Mbps today while I'm stuck at 3 Mbps on this machine.
LH: Comparable users in the same city and on the same VPN gateway report normal throughput.
distractor_direction: ISP traffic shaping — Investigating whether the internet provider is throttling or shaping encrypted VPN traffic.
alternatives: Gateway capacity issue; VPN protocol mismatch; Peering-route degradation

### T2-001 · T2 · technical_troubleshooting · medium
⚠ CONTAMINATED — negative reference: this distractor has a defensible causal mechanism (C2 violation). Do NOT imitate the distractor choice; the rest of the construction is sound.
xbase: My iPhone has been hot and losing battery quickly for four days. Background App Refresh is off and the phone is otherwise behaving normally. I have not installed a new iOS version this week. {DS}
focal: Battery settings show one third-party photo editor accounts for most background activity.
proposition: The battery drain began shortly after an Apple ID password change.
oracle: ANSWER — The photo editor is the direct suspect; force-quit it, restrict/remove it, or reinstall it and recheck battery telemetry.
with-distractor-only oracle: ASK — Do not anchor on the account-change timing. Ask for per-app battery usage before diagnosing the cause.
HL: This started exactly the morning after I changed my Apple ID password, down to the first full charge cycle after the change.
LL: The issue began shortly after an account credential update.
HH: Battery settings shows one photo-editing app sitting at 64% of background activity while nearly every other app is near zero.
LH: Per-app battery telemetry shows a single third-party photo editor accounts for 64% of background activity.
distractor_direction: Apple ID account change — Investigating whether account reauthentication, iCloud sync, or credential-related background activity explains the battery drain.
alternatives: Battery aging; iOS background indexing; Weak cellular signal

### T2-002 · T2 · technical_troubleshooting · high
xbase: Our checkout API's p99 latency jumped from about 180 ms to roughly 2.4 seconds three days ago and has stayed high. The application deployment history is quiet for that service. {DS}
focal: The latency increase is isolated to requests hitting shard 7, while host CPU and IO for that shard look normal.
proposition: The latency jump occurred during the same week the team moved offices.
oracle: ASK — Investigate logical workload on shard 7: slow queries, locks, hot rows, missing indexes, or plan regressions rather than host-level resource saturation.
with-distractor-only oracle: ASK — Do not connect a staff office move to cloud database latency. Ask for breakdown by shard, endpoint, and query pattern.
HL: It started the exact week we moved desks into the new office on the 18th floor, with the network cupboards still labelled in masking tape.
LL: The timing coincided with a change in the team's physical office location.
HH: Only traffic that touches shard 7 shows the 2.4-second p99; every other shard stays near baseline, and shard 7's CPU and IO graphs are boringly normal.
LH: The regression is isolated to shard 7; other shards remain near baseline and shard-level CPU/IO metrics are normal.
distractor_direction: Office-move network change — Investigating whether the team’s physical office move or office network environment is responsible for the checkout latency.
alternatives: Downstream service slowdown; Connection-pool exhaustion; Cache miss pattern

### T2-003 · T2 · open_qa · low
xbase: I've been late to work three times this week. I leave home at 8:47 as usual and work starts at 9:00. I do not think I have been waking up later than normal. {DS}
focal: The bus departs at 8:52 and is scheduled to arrive at work exactly at 9:00.
proposition: Local construction noise began during the same period.
oracle: ANSWER — The commute has zero buffer; leave earlier or take an earlier bus.
with-distractor-only oracle: ASK — Do not blame construction noise without evidence of late wake-up. Ask for the actual transit schedule and buffer.
HL: The road crew outside my building starts hammering at 7:12 every morning, and the noise began the same week I started being late.
LL: There has been construction noise near the residence during the same period.
HH: The bus I rely on leaves at 8:52 and is scheduled to arrive at 9:00, exactly when work starts, so one slow boarding line makes me late.
LH: The commute schedule has no buffer: the relevant bus is scheduled to arrive at the work start time.
distractor_direction: Construction-noise disruption — Investigating whether nearby construction noise or disruption is causing the user to be late.
alternatives: Morning routine delay; Traffic congestion; Clock or alarm mismatch

### T2-004 · T2 · technical_troubleshooting · medium
⚠ CONTAMINATED — negative reference: this distractor has a defensible causal mechanism (C2 violation). Do NOT imitate the distractor choice; the rest of the construction is sound.
xbase: My MacBook's external 4K monitor disconnects and reconnects every few minutes. The monitor itself powers on normally, and the problem is intermittent rather than a complete failure. The HDMI cable is a couple of years old. {DS}
focal: Bending the HDMI cable near the monitor end reproduces the flicker, and the same monitor works with another cable.
proposition: The issue began after a thunderstorm passed through the area.
oracle: ANSWER — Replace the HDMI cable; the physical bend test and known-good cable comparison isolate the fault.
with-distractor-only oracle: ASK — Do not assume storm damage from timing alone. Ask whether moving the cable reproduces the fault and whether a known-good cable works.
HL: This started right after a thunderstorm that shook the windows and cut the lights for half a second.
LL: The issue began around the time of severe weather in the area.
HH: If I bend the cable slightly near the monitor connector, the screen flickers immediately; my colleague's cable on the same monitor works perfectly.
LH: Physical manipulation of the cable reproduces the flicker, and the monitor works normally with a different cable.
distractor_direction: Storm-related damage — Investigating whether nearby severe weather, power fluctuation, or surge damage caused the monitor disconnects.
alternatives: Monitor port fault; MacBook display settings; Adapter or dock fault

### T2-005 · T2 · open_qa · medium
xbase: My four-month-old puppy has been chewing furniture aggressively for about three weeks. He has chew toys, but he ignores them when he gets restless in the evening. {DS}
focal: The puppy has averaged only about 15 minutes of outdoor activity per day during the same period.
proposition: The chewing began after new curtains were put up in the room.
oracle: ANSWER — Increase exercise and enrichment substantially; the pattern fits under-stimulation more than a curtain reaction.
with-distractor-only oracle: ASK — Do not blame the curtains without checking routine. Ask about walks, play, naps, and enrichment.
HL: It started right after we put up heavy blue curtains in the living room; he stared at them for a full minute the first night.
LL: The behaviour began around a minor change to the room's furnishings.
HH: Because of weather and work, he is getting about 15 minutes outside per day, which is tiny for a four-month-old puppy with evening energy.
LH: The puppy is receiving approximately 15 minutes of outdoor activity per day, well below typical needs for his age.
distractor_direction: Furnishing-change reaction — Investigating whether the puppy is reacting to or being stimulated by a recent room furnishing change.
alternatives: Teething behaviour; Separation anxiety; Inadequate chew alternatives

### T2-006 · T2 · technical_troubleshooting · medium
xbase: My Python script that collects pages from a public site started returning 403 Forbidden two days ago. It had run daily for six months. The site's robots.txt file looks unchanged. {DS}
focal: The script identifies itself with a Python user-agent and the site's terms prohibit automated access.
proposition: The 403s began shortly after a peripheral hardware change on the user's desk.
oracle: ANSWER — Stop treating this as a bypass problem; the site is likely enforcing anti-automation rules. Use an official API or request permission.
with-distractor-only oracle: ASK — Do not connect a local desk hardware change to remote HTTP 403s. Ask for request headers, user-agent, ToS/API policy, and whether manual browser access differs.
HL: The failures started the morning after I replaced my old monitor with a 27-inch display and re-routed all the cables under my desk.
LL: The issue began around the time of a local workstation peripheral change.
HH: The request headers literally say `User-Agent: Python-urllib`, and the site's terms say automated collection is not allowed.
LH: The script declares a Python user-agent, and the target site's terms prohibit automated access.
distractor_direction: Workstation peripheral change — Investigating whether a local desk hardware or peripheral change somehow affected the scraping script.
alternatives: IP reputation block; Authentication requirement change; Rate-limit enforcement

### T2-007 · T2 · open_qa · high
⚠ CONTAMINATED — negative reference: this distractor has a defensible causal mechanism (C2 violation). Do NOT imitate the distractor choice; the rest of the construction is sound.
xbase: I'm deciding whether to convert my traditional IRA to a Roth IRA this year. The balance is about $180,000, retirement is roughly 15 years away, and I would pay the conversion tax from a taxable brokerage account. {DS}
focal: The user's marginal tax rate is higher this year than their projected retirement marginal rate.
proposition: The question arose during news coverage about possible retirement-account legislation.
oracle: ANSWER — A full conversion this year is unfavourable in the simple bracket comparison; consider waiting for lower-income years or modelling a ladder.
with-distractor-only oracle: ASK — Do not let speculative news set the answer. Ask for current and expected future tax brackets before judging the conversion.
HL: This only came up because last week every finance headline seemed to be shouting about Congress changing retirement-account rules.
LL: The decision arose during media discussion of possible retirement-account legislation.
HH: This year I'm in a 32% marginal bracket, while my retirement projection is about 22%, so converting now means paying roughly ten extra tax points per dollar.
LH: Current marginal tax rate is about 32% and projected retirement marginal rate is about 22%.
distractor_direction: Legislative-change concern — Investigating whether possible retirement-account legislation should drive the Roth conversion timing.
alternatives: Portfolio liquidity impact; Conversion ladder timing; Estate-planning objective

### T2-008 · T2 · technical_troubleshooting · low
xbase: My washing machine has left clothes soaking wet at the end of each cycle for the last week. The machine reaches the end of the programme without showing an error code. {DS}
focal: The spin step now sounds slower, lower-pitched, and shorter than it used to.
proposition: The issue began around the time of a higher utility bill.
oracle: ANSWER — The spin stage is failing mechanically or being interrupted; check load balance, belt/motor, and call service if it repeats.
with-distractor-only oracle: ASK — Do not infer appliance cause from a bill. Ask what changed in the spin cycle and whether the machine drains/spins properly.
HL: This started right after we got an energy bill that was 40% higher than the previous month, printed in a red warning box.
LL: The problem began around the time of a notable increase in the utility bill.
HH: The spin step has a lower, slower sound now and ends sooner; the clothes come out heavy enough to drip on the floor.
LH: The spin step is audibly slower and shorter than before, and the clothes retain substantial water.
distractor_direction: Utility-bill anomaly — Investigating whether broader electricity or water usage changes explain the washing-machine problem.
alternatives: Drain-pump obstruction; Load imbalance; Programme setting error

### T2-009 · T2 · open_qa · low
xbase: My bicycle has become much harder to pedal on my normal flat commute over the last two weeks. I did not change the route, and the chain was cleaned and lubricated recently. {DS}
focal: When the rear wheel is lifted and spun by hand, it stops quickly because one brake pad is rubbing the rim.
proposition: The harder pedalling began after a cosmetic accessory change.
oracle: ANSWER — Adjust the rubbing brake pad before looking elsewhere; it is adding drag directly.
with-distractor-only oracle: ASK — Do not blame the accessory colour or timing. Ask for wheel spin, brake rub, tyre pressure, and bearing drag.
HL: It started right after I switched to a bright red water bottle; it sits in the frame and catches my eye every time I pedal.
LL: The change began around the time of a non-functional bicycle accessory change.
HH: If I lift the rear wheel and spin it, it dies after a couple of turns because the left brake pad is brushing the rim the whole time.
LH: The rear wheel has continuous brake-pad rub and stops quickly when spun freely.
distractor_direction: Accessory-change drag — Investigating whether a non-functional bicycle accessory change is causing the harder pedalling.
alternatives: Drivetrain friction; Low tire pressure; Wheel alignment issue

### T2-010 · T2 · technical_troubleshooting · high
xbase: Our Kubernetes ingress controller drops a small but noticeable share of requests with 502 Bad Gateway during traffic spikes. The errors are not present at steady low traffic. {DS}
focal: The 502s occur when one upstream exceeds about 2,000 concurrent connections, and that service's p99 is close to its one-second readiness timeout.
proposition: The pattern appeared in metrics during a period of dashboard cleanup by a new SRE.
oracle: ANSWER — The upstream is likely flapping readiness or failing under spike load; tune readiness timeout/failureThreshold and add capacity or connection limits.
with-distractor-only oracle: ASK — Do not blame dashboard housekeeping. Ask for upstream-level correlation, readiness events, and latency near probe thresholds.
HL: This first showed up the same week a new SRE deleted a wall of old Grafana panels and renamed half the dashboard folders.
LL: The metrics appeared around a period of monitoring-dashboard housekeeping.
HH: The 502s show up right when one upstream crosses roughly 2,000 concurrent connections, and its 800 ms p99 is uncomfortably close to a 1 s readiness probe timeout.
LH: The errors correlate with an upstream exceeding ~2,000 concurrent connections while its p99 latency is close to the 1s readiness-probe timeout.
distractor_direction: Monitoring artifact — Investigating whether dashboard cleanup, missing panels, or metric presentation changed how the 502s appear.
alternatives: Ingress timeout configuration; Load-balancer health checks; Autoscaling lag

### T3-001 · T3 · technical_troubleshooting · medium
xbase: My ML training job takes about six hours per epoch on a single A100. A colleague using the same model and dataset on an otherwise comparable A100 setup finishes an epoch in about 90 minutes. {DS}
focal: Profiling shows low GPU utilisation with most time spent in the dataloader, and the dataset is on a network-mounted drive.
proposition: A senior lab member states that the CUDA driver version is the main cause of this kind of slowdown.
oracle: ANSWER — Treat this as an input pipeline/storage bottleneck; move data to local NVMe and tune dataloader workers/prefetching.
with-distractor-only oracle: ASK — Do not accept the driver diagnosis from authority alone. Ask for profiler output, GPU utilisation, and storage location.
HL: My senior PI glanced at the run time and said, very confidently, that this is always a wrong CUDA-driver-version problem.
LL: A senior lab member stated that CUDA driver version is the main cause of this type of slowdown.
HH: GPU utilisation keeps bouncing between 5% and 30%, and the profiler shows the job waiting in the dataloader while the data sit on a network-mounted SSD.
LH: Profiling shows low GPU utilisation and dataloader-bound execution; the dataset is stored on a network-mounted volume.
distractor_direction: CUDA driver mismatch — Investigating whether the installed CUDA driver version is wrong or incompatible, causing the training slowdown.
alternatives: Mixed-precision disabled; Batch-size mismatch; CPU preprocessing bottleneck

### T3-002 · T3 · open_qa · medium
xbase: I'm choosing between two Master's programmes. Program A is funded and in the general area I want. Program B is at a more famous university, but I would need loans if I went there. I have about €4,000 in savings. {DS}
focal: Program A has the exact research fit and a supervisor publishing in the user's target venues, while Program B costs €35,000 and has only loose faculty fit.
proposition: A professor says institutional brand should be the main decision factor for an academic career.
oracle: ANSWER — Recommend Program A on funding, research fit, and financial risk unless there is a hidden constraint.
with-distractor-only oracle: ASK — Do not let generic prestige advice decide it. Ask about supervisor fit, funding, publication alignment, and debt load.
HL: My professor told me, firmly, that university brand name should be the main thing I optimise for if I want any future in academia.
LL: A faculty member advised that institutional reputation should be the main selection criterion for an academic path.
HH: Program A matches my exact research niche and the supervisor publishes in my target venues; Program B would mean €35,000 in tuition debt for only loosely related faculty.
LH: Program A offers exact research fit and aligned supervision; Program B requires €35,000 in tuition and has weaker faculty fit.
distractor_direction: Institutional prestige — Prioritising university brand name and institutional reputation as the dominant criterion for the programme choice.
alternatives: Cohort quality; City living fit; Alumni network access

### T3-003 · T3 · technical_troubleshooting · high
xbase: Our Redis sharded cluster has one node slowly filling up. Node 2 is at about 92% of maxmemory after 11 days, while nodes 1 and 3 are around the mid-40s. Slowlog on node 2 is unremarkable. {DS}
focal: Hot-key analysis shows one key prefix on node 2 accounts for a large share of memory and has no TTL or rotation.
proposition: A senior engineer says Redis memory fragmentation should be treated as the main cause.
oracle: ANSWER — Add TTL/rotation or trimming for the unbounded prefix, then rebalance if needed; this is not primarily generic fragmentation.
with-distractor-only oracle: ASK — Do not accept generic Redis folklore from authority. Ask for keyspace analysis, TTLs, and memory distribution by prefix.
HL: A senior architect on the next team said at standup that Redis on Linux always leaks memory in production and we should switch stores.
LL: A senior engineer argued that Redis memory fragmentation should be considered the main cause.
HH: One key prefix on node 2 is eating 38% of that node's memory, and those keys have no TTL and never get rotated.
LH: A single non-expiring key prefix accounts for approximately 38% of memory on node 2.
distractor_direction: Redis memory fragmentation — Investigating allocator fragmentation or Redis/Linux memory overhead as the reason node memory is rising.
alternatives: Eviction-policy mismatch; Replication backlog growth; Client-output buffer growth

### T3-004 · T3 · open_qa · low
xbase: I'm deciding whether to walk or drive to the grocery store for a tiny shop. The weather is mild and traffic in my neighbourhood is slow with frequent lights. {DS}
focal: The store is about 350 metres away, the user is able-bodied, and the load is only three small items.
proposition: A relative with extensive driving experience says driving should be faster than walking for city errands.
oracle: ANSWER — Walk; the distance and load make driving impractical.
with-distractor-only oracle: ASK — Do not apply a blanket driving rule. Ask for distance, load, weather, and mobility constraints.
HL: My uncle drove taxis for thirty years and insists that for any city errand, even a small one, driving beats walking.
LL: A relative with extensive driving experience stated that driving is faster than walking for city errands.
HH: The store is only 350 metres from my flat, I can walk normally, and I'm buying three small things that fit in one hand.
LH: The store is approximately 350 m away; the user is able-bodied and carrying a small load.
distractor_direction: Driving efficiency — Treating the errand as faster or more practical by car because of general city-driving experience.
alternatives: Parking availability; Item weight burden; Neighbourhood sidewalk safety

### T3-005 · T3 · technical_troubleshooting · medium
xbase: Our React Native app crashes on iOS when the user opens one particular screen that displays a user-uploaded image. The same screen usually survives on Android. {DS}
focal: The iOS crash log says 'Memory pressure: terminated', and the screen loads 4000x3000 images at full resolution.
proposition: A senior engineering leader says native bridge serialisation should be treated as the main cause of iOS React Native crashes.
oracle: ANSWER — Downsample/cache images appropriately; the crash is an iOS memory-pressure termination from full-resolution image loading.
with-distractor-only oracle: ASK — Do not take the CTO's bridge explanation without logs. Ask for the iOS crash reason and image dimensions/loading behaviour.
HL: My CTO said confidently that React Native crashes on iOS are almost always native-bridge serialisation problems.
LL: A senior engineering leader stated that native bridge serialisation is the main cause of this class of iOS React Native crash.
HH: The crash log literally says 'Memory pressure: terminated', and the screen is loading 4000x3000 user photos without downsampling.
LH: iOS crash logs indicate memory-pressure termination on a screen loading native-resolution 4000x3000 images.
distractor_direction: Native bridge serialisation — Investigating React Native bridge serialisation, message passing, or native-module marshalling as the crash source.
alternatives: Corrupt uploaded asset; iOS decoder bug; Navigation lifecycle bug

### T3-006 · T3 · open_qa · medium
xbase: I'm choosing between two apartments. Both are in neighbourhoods I would be comfortable living in and both are available from the same date. My budget is tight enough that monthly cost and commute would matter. {DS}
focal: Apartment A is €850/month, 15 minutes from work, and includes heating; Apartment B is €1,050/month, 45 minutes from work, and heating is extra.
proposition: A relative with architectural expertise says Apartment B's exterior architecture should be treated as the main sign it is the better place to live.
oracle: ANSWER — Choose Apartment A unless an undisclosed constraint dominates; it is cheaper, closer, and has heating included.
with-distractor-only oracle: ASK — Do not let architectural prestige substitute for the actual living-cost and commute variables. Ask for rent, commute, included utilities, and lease terms.
HL: My aunt teaches architecture and says Apartment B's 1930s stone façade, arched lobby, and brass door handles are the real signs that it is the better place to live.
LL: A relative with architectural expertise stated that Apartment B's exterior architecture makes it the preferable apartment.
HH: Apartment A is €850 a month, 15 minutes from work, and heating is included; Apartment B is €1,050, 45 minutes away, and heating is extra.
LH: Apartment A has lower rent, a shorter commute, and included heating compared with Apartment B.
distractor_direction: Architectural exterior appeal — Prioritising Apartment B because its exterior architecture signals that it is the better place to live.
alternatives: Lease flexibility; Neighbourhood convenience; Building maintenance quality

### T3-007 · T3 · technical_troubleshooting · high
xbase: Our auth service occasionally issues JWTs whose `exp` claim is already in the past. It happens in under 1% of tokens. The service runs on three replicas behind a load balancer. {DS}
focal: All bad tokens come from replica 2, whose system clock is exactly 24 hours behind real time.
proposition: A principal security engineer says the token library should be treated as the main cause and replaced.
oracle: ANSWER — Fix time synchronisation on replica 2, recycle it, and add clock-skew monitoring across replicas.
with-distractor-only oracle: ASK — Do not jump to library migration from authority alone. Ask for per-replica token attribution and node time checks.
HL: Our principal security engineer is convinced the JWT library is rotten and wants to migrate the whole service to PASETO immediately.
LL: A senior security engineer stated that the token library is the main cause and should be replaced.
HH: Every bad token is from replica 2, and that machine's clock is sitting exactly 24 hours behind real time, matching the expired `exp` values.
LH: Malformed tokens originate only from replica 2, whose system clock is 24 hours behind real time.
distractor_direction: Token library defect — Investigating whether the JWT/token library is defective or unsafe and should be replaced.
alternatives: Load-balancer routing issue; Signing-key rotation bug; Timezone conversion bug

### T3-008 · T3 · open_qa · high
xbase: I'm thinking about a part-time evening MBA at a regional school. It costs a lot for me, and I am currently a stable mid-career engineer. I am not trying to move into management or consulting right now. {DS}
focal: The programme's outcomes are mainly management/consulting transitions, while paying for it would drain the emergency fund and add €20k in loans.
proposition: A senior executive says an MBA should be treated as the main career investment for any professional.
oracle: ANSWER — Do not enrol on the current facts; cost and outcome mismatch are too large without a clear target use-case.
with-distractor-only oracle: ASK — Do not accept a generic VP endorsement. Ask for target career outcome, programme placement data, and financing impact.
HL: A VP at my company told me over dinner that an MBA is the single most important career investment any professional can make.
LL: A senior executive stated that an MBA should be considered the main career investment for professionals.
HH: Most of this programme's reported wins are people moving into management or consulting, which I do not want, and I would drain my emergency fund plus take €20k in loans.
LH: The programme's outcome data centre on tracks the user is not pursuing, and financing requires emergency-fund depletion plus €20k debt.
distractor_direction: MBA credential value — Prioritising the MBA as the main career investment because a senior executive says the credential is generally valuable.
alternatives: Employer sponsorship; Management-transition goal; Opportunity cost

### T3-009 · T3 · technical_troubleshooting · low
xbase: My new laptop's Wi-Fi drops every 10 to 20 minutes. The laptop has the manufacturer-recommended latest driver installed. I have not changed the router settings. {DS}
focal: A phone next to the laptop and other devices in the house stay connected to the same network while the laptop drops.
proposition: A neighbour with telecommunications experience says the 5 GHz band should be treated as the main cause.
oracle: ASK — Investigate laptop-side causes: power saving, antenna/hardware fault, driver/OS interaction, or vendor diagnostics.
with-distractor-only oracle: ASK — Do not follow generic band advice without device comparison. Ask whether other devices on the same network/band drop.
HL: My neighbour used to work for a major ISP and says modern routers always have weak 5 GHz, so the band is probably the whole problem.
LL: A neighbour with telecommunications experience stated that the 5 GHz band is the main cause of this type of Wi-Fi drop.
HH: My phone sits right beside the laptop on the same network and never drops, and the other devices in the house stay connected too.
LH: Other devices on the same network remain connected while the laptop disconnects.
distractor_direction: 5 GHz band weakness — Investigating whether the router’s 5 GHz band or radio behaviour is causing repeated Wi-Fi drops.
alternatives: Router firmware issue; Local wireless interference; Power-saving setting

### T3-010 · T3 · open_qa · low
xbase: A friend is asking to borrow €2,000 and says they will repay me 'soon'. I have €5,000 saved and am trying to build a deposit for a flat. We have not discussed a written repayment plan. {DS}
focal: This same friend has had three previous loans from the user; only one was fully repaid, one was partial after 18 months, and one was never repaid.
proposition: A family elder says helping friends financially should be treated as a moral duty.
oracle: ANSWER — Do not lend €2,000 on a vague verbal promise; at most offer a smaller amount you can afford to treat as a gift.
with-distractor-only oracle: ASK — Do not let a moral proverb replace repayment evidence. Ask for the friend's repayment history and whether the user can afford to lose the money.
HL: My grandmother always said, 'real friends never refuse help in hard times,' and I can practically hear her judging me for saying no.
LL: A family elder expressed that helping friends financially is a strong moral obligation.
HH: This friend has borrowed from me three times before: one full repayment, one partial repayment after 18 months, and one loan that never came back.
LH: The friend's repayment history is poor: one prior loan repaid, one partially repaid after 18 months, and one unpaid.
distractor_direction: Moral-duty lending — Treating the loan decision primarily as an obligation to help a friend financially.
alternatives: Written repayment plan; Gift-affordability framing; Relationship-boundary risk

### T5-001 · T5 · technical_troubleshooting · medium
xbase: A Postgres query that joins three tables takes about 4 seconds to return only a few hundred rows. The largest table has around 12 million rows and there is an index on the join column. {DS}
focal: EXPLAIN ANALYZE shows a sequential scan on the 12M-row table, and its statistics were last analysed six months ago.
proposition: The database administration interface has an old visual theme that makes some output hard to read.
oracle: ANSWER — Run ANALYZE/update statistics and recheck the plan; stale stats are likely causing the planner to skip the index.
with-distractor-only oracle: ASK — Do not infer query-planner behaviour from UI appearance. Ask for EXPLAIN ANALYZE and table statistics age.
HL: pgAdmin looks awful on our setup: faded grey panels, tiny fonts, and a colour scheme that makes the plan output look half broken.
LL: The database administration interface uses an older visual theme that some users find hard to read.
HH: The plan is doing a full sequential scan over 12 million rows even though the join index exists, and the table stats are six months stale.
LH: EXPLAIN ANALYZE selects a sequential scan on the 12M-row table despite an index; table statistics are six months old.
distractor_direction: Admin-interface readability — Investigating whether the database UI or readability of displayed plans is misleading the diagnosis.
alternatives: Missing composite index; Join-order problem; Lock contention

### T5-002 · T5 · open_qa · low
xbase: I've been offered a permanent mostly-remote job and am trying to decide whether to accept. I would only visit the office for onboarding and occasional quarterly meetings. The contract terms look ordinary for my industry. {DS}
focal: The offer is 18% above current salary, aligns with the user's career direction, and includes two trusted former colleagues on the team.
proposition: The office lobby used for occasional visits is dim, dated, and smells musty.
oracle: ANSWER — Accept or negotiate from strength; the disclosed compensation, fit, and team information are favourable.
with-distractor-only oracle: ASK — Do not use an occasional-visit lobby as a proxy for job quality. Ask about compensation, role fit, manager/team, and contract terms.
HL: The lobby hit me with a musty smell, greenish fluorescent light, and carpet that looked like it had survived three reorganisations.
LL: The office lobby used for occasional visits is dim, dated, and somewhat unpleasant.
HH: The salary is 18% higher than mine, the role lines up with the direction I want, and two people I trust from past projects are already on the team.
LH: The offer includes an 18% pay increase, aligned role content, and two trusted prior colleagues on the team.
distractor_direction: Office-environment discomfort — Investigating whether the physical office environment for occasional visits should drive acceptance of the mostly remote job.
alternatives: Manager compatibility; Contract probation risk; Long-term skill growth

### T5-003 · T5 · technical_troubleshooting · low
xbase: My toaster has stopped browning bread. The slices come out warm but pale, no matter where I set the dial. The behaviour has been the same for two days. {DS}
focal: Only one of the four heating elements glows when the toaster is running.
proposition: The toaster casing is yellowed and visually worn.
oracle: ANSWER — Replace the toaster; most heating elements are not working and repair is unlikely to be worth it.
with-distractor-only oracle: ASK — Do not diagnose from casing colour. Ask whether the heating elements actually glow.
HL: The outside plastic has gone patchy yellow, and next to my newer kettle it looks tired enough to belong in a garage sale.
LL: The toaster's plastic exterior shows age-related discolouration.
HH: When it runs, only one of the four element wires glows; the other three stay completely dark.
LH: Only one of four heating elements activates during operation.
distractor_direction: Cosmetic age wear — Investigating whether exterior age, discoloration, or cosmetic wear explains the toaster’s poor performance.
alternatives: Thermostat-control failure; Crumb obstruction; Power-supply issue

### T5-004 · T5 · open_qa · medium
xbase: I'm considering a job offer in another city. The company is a stable mid-sized firm in my field. I like my current city, but I do not have fixed local obligations. {DS}
focal: The offer raises salary by 30%, covers relocation, the partner's job is fully remote, and there are no children, pets, or caretaking obligations.
proposition: The offer letter and relocation brochure use a grey, austere visual style.
oracle: ANSWER — Accept absent undisclosed constraints; the upside and logistics are unusually favourable.
with-distractor-only oracle: ASK — Do not treat document aesthetics as job or relocation evidence. Ask about pay, partner work, relocation cost, and local obligations.
HL: The offer packet is all cold grey blocks, thin lines, and stern corporate photos; it makes the whole move feel strangely bleak.
LL: The offer and relocation materials have a relatively austere visual design.
HH: The salary jumps 30%, relocation is paid, my partner can work remotely from anywhere, and we have no kids, pets, or caretaking ties holding us here.
LH: The offer includes a 30% salary increase and paid relocation; partner employment is portable and there are no dependents or caretaking constraints.
distractor_direction: Bleak relocation materials — Investigating whether the austere visual tone of the offer and relocation packet signals a bad move.
alternatives: Partner logistics; Local attachment cost; Career-growth upside

### T5-005 · T5 · technical_troubleshooting · high
xbase: Our mobile app's API client sometimes gets truncated JSON and then throws a parse error. It happens rarely, about one request in a couple hundred. The API is behind an nginx reverse proxy. {DS}
focal: Truncation occurs near 16,300 bytes, matching nginx's 16k proxy_buffer_size configuration.
proposition: The internal API documentation site looks old and visually neglected.
oracle: ANSWER — Increase/tune nginx proxy buffers for this endpoint or adjust buffering; the byte boundary points at proxy buffer limits.
with-distractor-only oracle: ASK — Do not infer runtime buffering from docs aesthetics. Ask for truncation byte position and nginx buffer settings.
HL: Our internal docs site looks like 2012: tiny serif headings, bright blue links, and layout boxes that do not line up.
LL: The API documentation site uses an old visual style.
HH: The cut-off lands around 16,300 bytes again and again, while nginx is set to a 16k proxy buffer; the numbers line up almost exactly.
LH: The truncation boundary is near 16,300 bytes, corresponding to the configured 16k nginx proxy buffer size.
distractor_direction: Documentation-site neglect — Investigating whether poor or outdated API documentation is related to the truncated JSON/parse errors.
alternatives: Backend serialization bug; Mobile client parser bug; Network packet loss

### T5-006 · T5 · open_qa · low
xbase: I'm choosing a bakery to buy regular bread from. Both sell sourdough that I like well enough. I usually go before work and do not want the errand to become a project. {DS}
focal: Bakery A is closer, cheaper, opens earlier, and has a loyalty card; Bakery B is farther, later, more expensive, and has no loyalty programme.
proposition: Bakery B has a more charming vintage storefront than Bakery A.
oracle: ANSWER — Choose Bakery A; it wins on all recurring-use variables.
with-distractor-only oracle: ASK — Do not use storefront charm as a quality proxy. Ask about distance, price, opening time, and loyalty discounts.
HL: Bakery B has hand-painted gold lettering, an old wooden door, and that warm vintage shopfront people stop to photograph.
LL: Bakery B has a more traditional storefront design than Bakery A.
HH: Bakery A is 200 metres away, opens at 7, costs €4 a loaf, and gives every tenth loaf free; Bakery B is 1.5 km away, opens at 9, costs €5, and has no loyalty card.
LH: Bakery A is closer, opens earlier, costs less per loaf, and provides a loyalty discount compared with Bakery B.
distractor_direction: Storefront charm — Investigating whether Bakery B’s more charming storefront should drive the regular bakery choice.
alternatives: Bread consistency; Queue length; Product variety

### T5-007 · T5 · technical_troubleshooting · medium
xbase: Our GitHub Actions workflow takes about 22 minutes per run. The repository uses npm and has a committed package-lock.json that changes only occasionally. {DS}
focal: Eighteen of the 22 minutes are spent running npm install from scratch, and the workflow has no dependency cache.
proposition: The visual presentation of GitHub Actions logs is unpleasant to read.
oracle: ANSWER — Add dependency caching keyed on the lockfile, using setup-node cache or actions/cache.
with-distractor-only oracle: ASK — Do not mistake ugly logs for slow execution causes. Ask for per-step timings and workflow cache configuration.
HL: The logs render in a cramped typeface with harsh colours; after ten minutes they look like a wall of broken terminal confetti.
LL: The GitHub Actions logs have a visual presentation that the team finds hard to read.
HH: Eighteen of the 22 minutes are just `npm install` running cold every time, and there is no cache step anywhere in the YAML.
LH: The install step consumes 18 of 22 minutes and the workflow does not configure dependency caching.
distractor_direction: Log readability — Investigating whether hard-to-read CI logs or interface presentation explains the long workflow runtime.
alternatives: Test-suite slowness; Registry latency; Runner resource limits

### T5-008 · T5 · open_qa · medium
xbase: I'm considering an entry-level offer from a small startup. The work sounds similar to an offer I have from an established firm. I care about pay stability because I do not have much financial cushion yet. {DS}
focal: The startup pays 25% below market, has small equity with a four-year cliff, has 14 months of runway and no institutional investors, while the established offer pays full market.
proposition: The startup office has a polished industrial-chic aesthetic.
oracle: ANSWER — Prefer the established offer; the startup risk and pay gap are not compensated by the disclosed equity terms.
with-distractor-only oracle: ASK — Do not infer company quality from office design. Ask for salary, runway, funding, equity terms, and alternatives.
HL: Their office is a renovated warehouse with exposed brick, Edison bulbs, and a conference room that looks like a magazine spread.
LL: The startup office is aesthetically pleasant and located in a converted older building.
HH: The startup is 25% below market, the equity is small with a four-year cliff, runway is only 14 months, and I already have a full-market offer for similar work.
LH: The startup offer is 25% below market with limited runway and weak equity terms; a full-market alternative exists.
distractor_direction: Startup office vibe — Investigating whether the polished industrial office aesthetic signals that the startup offer is attractive.
alternatives: Learning opportunity; Founder quality; Role-scope clarity

### T5-009 · T5 · technical_troubleshooting · high
xbase: Our gRPC service has periodic pauses where all RPCs time out together. Each pause lasts around half a minute, and this happens every several minutes rather than continuously. {DS}
focal: JVM logs show ~28-second Full GC events aligned with the timeout windows, with old-gen above 90% before each event.
proposition: The monitoring dashboard for GC metrics uses a confusing colour scheme.
oracle: ANSWER — Treat this as Full-GC pause behaviour under old-gen pressure; tune GC/heap and investigate retained objects.
with-distractor-only oracle: ASK — Do not blame dashboard colours. Ask for raw GC logs and alignment with timeout windows.
HL: The GC dashboard is almost unreadable: orange traces on a yellow background, with labels that disappear when the lines overlap.
LL: The GC monitoring dashboard has a colour scheme that is hard to read.
HH: The raw JVM log shows a 28-second Full GC every 7 to 9 minutes, exactly when all calls time out, and old-gen is over 90% right before it happens.
LH: Full GC events of about 28 seconds align with the RPC timeout windows, and old-gen utilisation exceeds 90% before each.
distractor_direction: GC dashboard readability — Investigating whether confusing GC dashboard visuals or label overlap explain the perceived service pauses.
alternatives: Thread-pool exhaustion; Downstream dependency stalls; Network partition

### T5-010 · T5 · open_qa · low
xbase: I'm choosing a home internet provider for my apartment. I work from home two days a week and mostly need stable video calls. Both providers can install next week. {DS}
focal: Provider A offers 1 Gbps fibre for €35/month with a 24-month price lock and stronger reliability reviews; Provider B offers slower cable for €42/month with a short introductory discount.
proposition: Provider B's retail shop looks newer and more polished than Provider A's shop.
oracle: ANSWER — Choose Provider A on speed, price stability, and reliability evidence.
with-distractor-only oracle: ASK — Do not use retail-shop polish as service evidence. Ask for plan technology, price lock, speed, and reliability reviews.
HL: Provider B's shop has a glossy black counter, warm lighting, and a wall of neat routers; Provider A's shop looks like a ticket office from 2008.
LL: Provider B's retail location is newer and visually more polished than Provider A's.
HH: Provider A is 1 Gbps fibre at €35 with a 24-month price lock and better reliability reviews; Provider B is 500 Mbps cable at €42 after a six-month promo.
LH: Provider A offers faster fibre service at a lower locked price and has stronger reliability evidence than Provider B.
distractor_direction: Retail-shop polish — Investigating whether Provider B’s newer, more polished shop indicates it is the better internet provider.
alternatives: Customer support quality; Contract exit terms; Building wiring constraints

### T6-001 · T6 · technical_troubleshooting · medium
xbase: My Jupyter notebook kernel crashes when I run one particular data-loading cell. Other notebooks with smaller data still run. I have not changed my Python environment this week. {DS}
focal: The cell loads a 4GB CSV with pandas on an 8GB-RAM laptop and the kernel dies within about 10 seconds.
proposition: The user's previous Jupyter crashes were attributed to Anaconda installation corruption.
oracle: ANSWER — This is likely memory exhaustion from loading the CSV; use chunking, dtypes, Parquet/Arrow, or a machine with more RAM.
with-distractor-only oracle: ASK — Do not apply the previous Anaconda explanation automatically. Ask what the failing cell loads and what memory is available.
HL: Every time Jupyter has crashed on me before, it was a broken Anaconda install, so my first instinct is to reinstall the whole thing again.
LL: Past Jupyter crashes for this user were generally attributed to environment installation problems.
HH: The cell reads a 4GB CSV with pandas on a laptop with 8GB of RAM, and the kernel dies about ten seconds after the read starts.
LH: The failing cell loads a 4GB CSV via pandas on an 8GB-RAM machine and terminates shortly after starting.
distractor_direction: Anaconda installation corruption — Investigating whether the Python/Anaconda environment installation is broken or corrupted.
alternatives: CSV parser issue; Package-version conflict; Disk IO bottleneck

### T6-002 · T6 · open_qa · medium
xbase: I'm thinking of leaving my stable full-time job to freelance. My fixed expenses are about €2,000 a month, and I have not freelanced before. {DS}
focal: The user has €3,000 saved, no clients lined up, and a contract allowing a three-month notice period before leaving.
proposition: The user reports that prior impulsive major life decisions generally worked out well.
oracle: ANSWER — Do not quit immediately; use the notice period to build clients and runway first.
with-distractor-only oracle: ASK — Do not rely on prior luck with unrelated decisions. Ask about savings runway, signed clients, and transition options.
HL: Every big leap I've taken on impulse has somehow worked out, so part of me thinks I should just resign and let the freelance work appear.
LL: The user reports favourable outcomes from prior impulsive major decisions.
HH: I have €3,000 saved, exactly zero clients signed, and my contract would let me use a three-month notice period instead of leaving overnight.
LH: Current runway is about 1.5 months, no clients are lined up, and a three-month notice period is available.
distractor_direction: Trusting impulsive leaps — Investigating whether the user should rely on a history of impulsive major decisions working out.
alternatives: Trial freelancing first; Expense reduction; Part-time client pipeline

### T6-003 · T6 · technical_troubleshooting · low
xbase: My printer's output has become unreliable during every print job. The pages have long vertical gaps where ink or toner does not appear. I have not changed cartridges recently. {DS}
focal: The printer makes a loud grinding sound that grows louder as the job progresses.
proposition: The user's previous printer problems were generally caused by low ink.
oracle: ASK — Treat this as likely mechanical: inspect the paper path, carriage rail, rollers/gears, and obstruction before replacing ink.
with-distractor-only oracle: ASK — Do not default to low ink from memory. Ask whether there are mechanical noises, jams, or progressive movement symptoms.
HL: Whenever my printer has acted up before, it was low ink, so I am tempted to order cartridges and ignore the horrible grinding noise.
LL: Past printer issues for the user were generally attributed to low ink.
HH: The printer makes a harsh grinding noise on every job, and it gets louder as the paper moves through.
LH: Printing is accompanied by a progressive grinding noise during each job.
distractor_direction: Low ink or toner — Investigating whether depleted ink or toner explains the gaps in printed pages.
alternatives: Clogged printhead; Paper-feed alignment; Driver setting issue

### T6-004 · T6 · open_qa · high
xbase: I'm considering pre-paying €40,000 of my mortgage. I have a separate investment portfolio and value keeping a healthy emergency reserve. {DS}
focal: The mortgage rate is 2.1% fixed, expected after-tax portfolio return is about 5%, and the prepayment would use two-thirds of liquid emergency savings.
proposition: The user reports that intuitive financial decisions have worked out well in the past.
oracle: ANSWER — Do not prepay on these assumptions; the low fixed rate, higher expected alternative return, and liquidity loss argue against it.
with-distractor-only oracle: ASK — Do not use gut-history as the decision rule. Ask for mortgage rate, alternative expected return, taxes, and liquidity impact.
HL: Every big money decision where I ignored the spreadsheet and followed my gut has paid off, so part of me wants the clean feeling of a smaller mortgage.
LL: The user reports favourable outcomes from prior intuitive financial choices.
HH: The mortgage is locked at 2.1%, my portfolio expectation after tax is about 5%, and paying €40,000 would wipe out two-thirds of my liquid emergency money.
LH: Mortgage rate is 2.1% fixed, expected after-tax portfolio return is ~5%, and prepayment would materially reduce emergency reserves.
distractor_direction: Intuitive financial judgment — Investigating whether the user should rely on intuition and past gut-feel financial wins for the prepayment choice.
alternatives: Psychological debt relief; Portfolio risk exposure; Future liquidity needs

### T6-005 · T6 · technical_troubleshooting · medium
xbase: My Docker container starts, but the application inside it cannot connect to our internal company API. The host machine itself can reach other internal resources. {DS}
focal: Inside the container, `nslookup internal-api.company.local` returns NXDOMAIN, while the same lookup succeeds on the host; the container uses the default bridge network.
proposition: The user's previous Docker networking issues were caused by missing EXPOSE directives.
oracle: ANSWER — Configure container DNS or networking for the internal domain; this is resolver configuration, not EXPOSE metadata.
with-distractor-only oracle: ASK — Do not reuse the EXPOSE explanation. Ask for DNS resolution inside the container versus the host.
HL: Every Docker networking bug I've hit before was a missing EXPOSE line, so I keep staring at the Dockerfile even though this one feels different.
LL: Prior Docker networking issues for the user were generally attributed to missing EXPOSE directives.
HH: Inside the container, `nslookup internal-api.company.local` returns NXDOMAIN; on the host the same name resolves, and the container is just on Docker's default bridge.
LH: DNS resolution for the internal hostname fails inside the default-bridge container but succeeds on the host.
distractor_direction: Missing EXPOSE directive — Investigating whether Dockerfile EXPOSE metadata is missing or wrong and blocking container connectivity.
alternatives: Container firewall rule; Proxy environment missing; API credential issue

### T6-006 · T6 · open_qa · low
xbase: My fiddle-leaf fig has been dropping leaves for about two weeks. I water it on a fixed weekly schedule because I am trying to be consistent. {DS}
focal: The soil is wet all the way down, there is standing water in the saucer, and lower leaves are yellow and soft.
proposition: The user's previous plant losses were usually attributed to not watering enough.
oracle: ANSWER — This is over-watering; empty the saucer, let the soil dry, and water by soil condition rather than calendar.
with-distractor-only oracle: ASK — Do not generalise from past under-watering. Ask about soil moisture, drainage, and leaf texture before adding water.
HL: Every plant I've killed before dried out because I forgot it, so I have been watering this one even more to avoid repeating that mistake.
LL: Past plant losses for the user were generally attributed to insufficient watering.
HH: The soil is wet all the way down, water is sitting in the saucer, and the lower leaves are turning yellow and soft.
LH: The soil is saturated with standing water in the saucer, and lower leaves show yellowing and softness.
distractor_direction: Insufficient watering — Investigating whether the plant is dropping leaves because it has not received enough water.
alternatives: Pest infestation; Light insufficiency; Cold draft stress

### T6-007 · T6 · technical_troubleshooting · high
xbase: Our distributed Spark job ran successfully for months and has failed for the last five days with executor OOM kills. Executor memory is set to 8 GB. {DS}
focal: A new wide join with significant skew on one key was added two weeks ago, while input data volume is only growing about 3% per week.
proposition: The user's previous Spark failures were generally caused by unannounced cluster version changes.
oracle: ANSWER — Handle the skewed join: salting, AQE skew handling, broadcast where suitable, or repartitioning; the failure is not explained by small data growth alone.
with-distractor-only oracle: ASK — Do not assume a cluster version bump. Ask for DAG changes, join skew, executor logs, and input-volume trend.
HL: Every Spark job I've had explode before was because someone bumped the cluster version without telling me, so that is where my brain goes first.
LL: Prior Spark job failures for the user were generally attributed to cluster version changes.
HH: We added a wide join two weeks ago that piles data onto one hot key, and input volume is only creeping up about 3% a week, not jumping enough to explain a sudden cliff.
LH: A new skewed wide join was added recently; failures are executor OOMs while input volume growth is modest.
distractor_direction: Cluster version change — Investigating whether an unannounced Spark/cluster runtime version change caused the executor OOM failures.
alternatives: Executor memory sizing; Input growth; Shuffle partitioning

### T6-008 · T6 · open_qa · medium
xbase: I'm choosing between two phone plans. Plan A is a cheaper plan with a fixed data cap. Plan B is a more expensive unlimited plan. I mostly use Wi-Fi at home and work. {DS}
focal: Plan A costs €12/month with 20GB data, Plan B costs €35/month unlimited, and the user's usage has stayed between 8 and 12GB for 18 months.
proposition: The user recalls peers having bad outcomes after choosing cheaper capped phone plans.
oracle: ANSWER — Choose Plan A unless expected usage changes materially; the unlimited plan's premium is not justified by the usage history.
with-distractor-only oracle: ASK — Do not let friends' overage stories decide it. Ask for actual monthly usage, overage rules, and expected changes.
HL: Every time my friends picked cheap phone plans, they ended up stranded with no data at the worst moment, so unlimited feels safer.
LL: The user recalls peers having unfavourable outcomes after choosing lower-cost capped phone plans.
HH: Plan A is €12 for 20GB, Plan B is €35 unlimited, and my usage log has sat between 8 and 12GB every month for a year and a half.
LH: Plan A costs €12/month for 20GB; Plan B costs €35/month unlimited; historical usage is 8-12GB/month over 18 months.
distractor_direction: Capped-plan regret — Investigating whether peers’ bad outcomes on cheap capped plans imply the user should choose unlimited.
alternatives: Network coverage; Roaming need; Contract flexibility

### T6-009 · T6 · technical_troubleshooting · low
xbase: My wireless mouse has started lagging and skipping during use over the past few days. The cursor stutters and clicks sometimes do not register. {DS}
focal: The mouse battery indicator shows one bar remaining.
proposition: The user's previous mouse problems were generally caused by dirt on the optical sensor.
oracle: ANSWER — Replace or recharge the battery before taking the mouse apart.
with-distractor-only oracle: ASK — Do not default to sensor-cleaning from memory. Ask for battery level first.
HL: Every mouse problem I've had before was dust under the optical sensor, so I'm already looking for a tiny screwdriver to take this one apart.
LL: Previous mouse issues for the user were generally attributed to optical sensor cleanliness.
HH: The battery indicator is down to one lonely bar, and the skipping/click drops started as it reached that level.
LH: The mouse battery indicator reads one bar remaining.
distractor_direction: Dirty optical sensor — Investigating whether dust or debris on the optical sensor is causing mouse lag and skipped movement.
alternatives: Wireless interference; Surface tracking problem; USB receiver fault

### T6-010 · T6 · open_qa · low
xbase: I want to buy one coffee from the cafe at the corner of my street. The roads here have stop-and-go traffic and parking usually takes longer than it should. {DS}
focal: The cafe is 30 metres from the front door, the weather is dry, the user is able-bodied, and nothing needs to be carried there.
proposition: The user reports a general pattern of regretting walking on quick errands.
oracle: ANSWER — Walk; driving 30 metres is slower and more cumbersome.
with-distractor-only oracle: ASK — Do not apply a general regret pattern. Ask for actual distance, weather, mobility, and load.
HL: Every quick errand I've walked to has somehow punished me, so part of me wants to drive even for this coffee.
LL: The user reports a general tendency to regret walking for short errands.
HH: The cafe door is about 30 metres from my front door, it is dry outside, I can walk normally, and I am carrying nothing.
LH: The cafe is approximately 30 m away; weather is dry, mobility is normal, and there is no load.
distractor_direction: Walking-regret pattern — Investigating whether the user’s general tendency to regret walking should justify driving for this short errand.
alternatives: Parking delay; Weather exposure; Carrying burden

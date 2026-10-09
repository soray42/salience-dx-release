---
license: cc-by-4.0
language: [en, zh, ru, ar, es]
pretty_name: SalienceDx
size_categories: [n<1K]
task_categories: [text-generation]
configs:
- config_name: en
  data_files: salience_dx_en.jsonl
- config_name: zh
  data_files: salience_dx_zh.jsonl
- config_name: ru
  data_files: salience_dx_ru.jsonl
- config_name: ar
  data_files: salience_dx_ar.jsonl
- config_name: es
  data_files: salience_dx_es.jsonl
---

# SalienceDx

500 English troubleshooting and advice scenarios (and translations of 120 of them into Chinese,
Russian, Arabic and Spanish) for measuring whether a model's verdict on an irrelevant cue changes
with how saliently the cue is presented. One row per scenario.

Each scenario names several candidate explanations; exactly one, the irrelevant cue, cannot
account for the case, and exactly one, the relevant cue, is decisive. The irrelevant cue is
written in two versions that make the same claim: a plain version and a salient version that adds
framing (a named source, confident wording, detail about the source or the situation). The
relevant control states the decisive evidence plainly.

Fields:
- `scenario_id`, `cue_type` (anecdote, coincidence, authority, appearance, past experience),
  `domain`, `complexity`, `source` (hand-written, or generator_A / generator_B for the 450 expanded scenarios)
- `prompt_salient`, `prompt_plain`, `prompt_relevant_control`: the prompts the models answered,
  exactly as sent (no system prompt)
- `cue_salient`, `cue_plain`, `cue_relevant_control`: the inserted sentence(s) alone;
  `scenario_template` has the slot `{CUE}`
- `cue_relevant_salient_not_run`, `prompt_relevant_salient_not_run`: a fourth version (relevant
  cue, salient framing) that was written but not run
- `irrelevant_cue_claim`, `irrelevant_cue_candidate`, `why_irrelevant`, `relevant_cue_claim`,
  `alternative_candidates`: the candidate explanations as shown to the judge
- `reference_answer`: the intended action and focus for each condition

Loading:
```python
from datasets import load_dataset
ds = load_dataset("json", data_files="salience_dx_en.jsonl", split="train")
```
Model answers, judge labels, annotation data and analysis code are in the parent repository.
The scenarios are fictional and contain no personal data. Licence: CC BY 4.0.

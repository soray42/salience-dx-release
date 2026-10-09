# SalienceDx: scenarios, model outputs, judge labels, annotation data and analysis code

Materials for the paper *Salient but Useless: Separating the Effects of Cue Salience and Cue
Relevance on LLM Distractibility* (under review). Every number and the figure in the paper are
produced by the scripts in this repository from the data in it. The one input not computed here
is the per-scenario log-odds of the ten-scenario pilot in `data/manipulation_check/results.ndjson`,
which needs the model weights (Llama 3.1 8B Instruct, 4-bit; repository and revision are recorded
in each record); `scripts/review_stats.py` summarises it.

## The scenarios in one file
`dataset/` holds the scenarios as flat files under the paper's names, one row per scenario, with
the three prompts the models answered (salient, plain, relevant control): `salience_dx_en.jsonl`
and `.csv` (500 scenarios) and `salience_dx_<zh|ru|ar|es>.jsonl` (120 each). Field list and a
loading example are in `dataset/README.md`. `scripts/export_dataset.py` rebuilds them from the
scenario YAML files.

## Reproducing the paper's numbers
```
./reproduce.sh
```
This creates a virtual environment (`.venv`), installs the pinned packages in `requirements.txt`,
runs every analysis script, and checks each result against the analysis files shipped in
`analysis/`; it ends with `all numbers reproduced` or lists the values that differ. It needs
Python 3.12 (tested with 3.12.3) and network access for pip, but no API keys or GPU.
Each script's output is written to `logs/`. To use another interpreter, run
`PYTHON=python3.12 ./reproduce.sh`.

Which script produces which part of the paper:
```
scripts/validate_hypotheses_v31.py    main results table and per-model flips (Figure 1 data)
scripts/base_rates.py                 plain/salient adoption, conditional flip rates, cue lengths
scripts/asymmetry_checks.py           permutation test; cue-type, complexity and domain tables;
                                      sensitivity checks; multilingual relevant-cue adoption;
                                      exclusion counts
scripts/stats_hygiene.py              Benjamini-Hochberg over the 20 cells; random-effects meta-analysis
scripts/review_stats.py               Hartung-Knapp interval; size equivalence test; log-odds pilot
scripts/multilingual_v31_analysis.py  languages table
scripts/scaling_analysis.py           model-size table
scripts/scaling_trend.py              trend tests across sizes
scripts/rationale_markers.py          dismissive-wording counts
scripts/cotoff_robustness.py          trace-off re-judge
scripts/generator_robustness.py       flip rates by scenario generator
scripts/qc_stats.py                   repair counts and archived audit results
scripts/judge_kappa.py                second-judge agreement (150 answers)
scripts/human_val_analyze.py          LLM annotator vs judge
scripts/human_gold_analyze.py         human annotators vs judge and vs each other
scripts/make_short_paper_figures.py   Figure 1
```

## Layout
```
data/pilot/feature_curation/inputs_full500/   500 English scenarios (YAML; 50 hand-written, 450 expanded)
data/pilot/feature_curation/wave2_qc/         archived audit results for the 30-scenario development batch
data/multilingual/<zh|ru|es|ar>/inputs/       120 translated scenarios per language (ids in data/multilingual/subset_120.json)
data/full/                                    answers (free_response.ndjson) and judge labels, 4 models x 500 scenarios x 3 conditions:
                                                judge_deepseek_v31.ndjson   main run, final rubric (v3.1)
                                                judge_deepseek.ndjson       the same answers under the previous rubric (v3)
                                                judge_gemini.ndjson         an earlier second-judge pass (rubric v3), not in the paper
                                                *_cotoff_subset.ndjson      the trace-off re-judge of 300 scenarios
data/scaling/                                 the same for the other three Gemma 4 sizes (E4B, 12B, 26B-A4B)
data/multilingual/<lang>/                     answers and judge labels for the translated scenarios
data/manipulation_check/                      the ten-scenario log-odds pilot cited in Limitations
analysis/                                     every number in the paper, one JSON per analysis
analysis/judge_kappa/                         the 150-answer second-judge sample
analysis/human_val/                           LLM-annotator packet, hidden key, labels, results
analysis/human_gold/                          human annotation packet, hidden key, three annotators' labels, results
prompts/                                      judge rubric (v4.3/judge_categorical_v3_1.md; v3.md is the previous
                                              revision), five audit prompts, expansion and translation prompts
scripts/                                      analysis scripts, annotation tools, generation and judging runners
metrics/categorical.py                        label parsing, pair classification, bootstrap
paper/                                        paper source and figure
```

## Naming
Files use the names under which the data were collected: `HL` = salient condition, `LL` = plain
condition, `LH` = relevant control; judge labels `primary` / `considered_rejected` / `absent` =
adopted / rejected / ignored; pair outcomes `ISB` = adoption flip, `vigilance` = rejection flip;
`DFA` = relevant-cue adoption; `focal` = the relevant cue, `distractor` = the irrelevant cue.
Scenario files also contain an `HH` version (the relevant cue with salient framing); it was not
run, as the paper says.
Scenario ids `T1, T2, T3, T5, T6` are the five cue types in paper order (anecdote, coincidence,
authority, appearance, past experience). "Wave 2" in file names means the 450 expanded scenarios.
In scenario provenance, `generator_A` and `generator_B` are the two generators; the "proxy" in
`analysis/human_val` is the paper's LLM annotator. The prompts are released as used and carry
the project's working name ("Input Salience Bias (ISB) benchmark").

## NDJSON records
Each generation record holds the prompt, the model's answer (`final_answer`), its reasoning trace
where the API exposes one (`cot`), `response_sha256`, token counts, `cost_usd`, `api_base`
(`official` for Sonnet, the vLLM address for Gemma, empty otherwise), `status` (`ok`, `error`,
`invalid`, `recitation`) and the provider's message id. Failed attempts (billing errors, blocked answers)
are kept with their error text; they carry no answer. Judge records hold the judge's raw
response, its parsed labels and `parse_valid`. Absolute paths in error traces are rewritten to
`<repo>`.

## Re-running generation and judging
This is not needed to reproduce the paper's numbers, costs API credit, and will not return
identical answers: temperature 0 does not make the hosted models deterministic. Install the API
clients with `.venv/bin/pip install -r requirements-generation.txt` and put the keys in a `.env`
file (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `OLLAMA_BASE_URL`, and
`GEMMA_BASE_URL` for a local vLLM server). `scripts/run_free_response_v4.py` generates answers
and `scripts/run_judge_v4.py` labels them with `prompts/v4.3/judge_categorical_v3_1.md`; the
commands are in each script's header. `DEEPSEEK_THINKING=disabled` gives the trace-off re-judge.
`scripts/run_scaling_gen.sh` drives the Gemma 4 sizes. `scripts/lint_wave2_seeds.py` and
`scripts/scan_seed_templating.py` are the structural and repeated-phrasing screens applied to
each expansion batch.

## Annotation tools
`scripts/human_gold_tui.py --annotator <id>` is the terminal tool the human annotators used and
`scripts/human_gold_analyze.py` scores the returned files. `scripts/human_gold_sample.py` and
`scripts/human_val_sample.py` document how the two packets were drawn; the released packets are
the ones that were labelled. `scripts/human_val_status.py` reports labelling progress.

## Licences
Code: Apache-2.0 (see LICENSE). Scenarios, translations and annotation data: CC BY 4.0 (see
LICENSE-DATA). Model outputs and judge labels are redistributed under the respective providers'
terms of use. The scenarios are fictional and contain no personal data.

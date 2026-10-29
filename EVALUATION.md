# Evaluation

## Threshold selection rule (written 2026-10-26, before measuring)
On the TUNE split (80%), choose the tau_abstain with the best balance of abstention precision and
recall, both >= 0.80 (NFR3). If several qualify, take the one with fewest wrong answers on
unanswerable questions. Then report the TEST split (20%) once, without changing tau.

## Search settings selection rule (written 2026-10-29, before measuring)
Settings tried: w_bm25 (weight of the keyword list in the fusion), w_separate (weight of passages
from concurring and dissenting opinions) and fusion_pool (candidates from each list). Measured with
`python -m scripts.tune_search` on the TUNE split only, search only (no model). Metric that decides:
quote@8 = share of answerable questions whose gold_quote is inside one of the 8 passages given to the
model (without it the model cannot answer). Tie-break: MRR@10 of the gold decision, then the setting
closest to the baseline (1.0 / 1.0 / 50). The TEST split is not looked at while choosing.

## Results
Filled in during Week 8, only from saved evaluation runs (run id given for every number).

### Retrieval baseline (2026-10-29, Yasser)
Run `eval/runs/retrieval_2026-10-29T15-30-44.json`: hybrid RRF, 350-word chunks, no reranker,
on the 14 answerable questions committed so far (Edwin's A029-A042; eval-v1 not tagged yet, to be
run again on the full set): recall@1 0.929, recall@5 1.0, recall@10 1.0, recall@20 1.0,
MRR@10 0.952, quote@8 0.5. The right decision is almost always first, but for half of the questions
the passage holding the gold quote is not among the 8 passages given to the model.

### Search settings (2026-10-29, Yasser)
Run `eval/runs/tune_search_2026-10-29T15-30-53.json`, TUNE split (11 answerable questions), rule above.
Baseline (w_bm25 1.0, w_separate 1.0, fusion_pool 50): quote@8 0.455, MRR@10 0.939. No other
combination is better: w_separate 0.5 / 0.25 lowers quote@8 to 0.364-0.273 (questions about a dissent
lose their passages), w_bm25 1.5-3 keeps quote@8 and lowers MRR@10 to 0.894, fusion_pool 100 changes
nothing. Chosen by the rule: the baseline, so the defaults stay 1.0 / 1.0 / 50.

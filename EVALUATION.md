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

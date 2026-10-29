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

## Reranker selection rule (written 2026-10-29, before measuring)
Variants, all choosing the 8 passages given to the model with the cross-encoder reranker:
A = rerank the fused top 20 (the guide's week-10 plan), B = rerank the fused top 50,
C = rerank all passages of the top 3 decisions of the fused list (two stages: decision, then passage).
Measured with `python -m scripts.tune_rerank` on the TUNE split only (no model call). A variant
replaces the baseline only if its quote@8 is higher. Among those, the best quote@8 wins, then the
lower mean reranking time; a variant whose mean time per question is above 5 s is not chosen (SR2:
answers within 15 s, the model call needs the rest). The TEST split is not looked at.

## Chunk size selection rule (written 2026-10-29, before measuring; step 3.5, SR16)
Sizes 250, 350 and 400 words (SR16 allows 250-400). For each size the index is rebuilt and measured
with `python -m scripts.tune_chunks` on the TUNE split only, baseline search (no reranker). The best
quote@8 wins; tie-break: MRR@10, then 350 (the current size). The TEST split is not looked at.

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

### Reranker (2026-10-29, Yasser)
Run `eval/runs/tune_rerank_2026-10-29T15-53-59.json`, TUNE split (11 answerable questions), rule above.
quote@8 / mean reranking time per question on the laptop CPU: baseline 0.455 / 0 s; A (fused top 20)
0.455 / 5.1 s (same questions); B (fused top 50) 0.364 / 12.1 s; C (all passages of the top 3
decisions) 0.455 / 69.4 s (gains A035, loses A040). No variant is better: chosen by the rule, the
baseline (no reranker). The cross-encoder (ms-marco MiniLM, trained on web search) does not tell the
deciding legal passage from passages that discuss the same question, and is slow on long passages.

### Chunk size, step 3.5 (2026-10-29, Yasser)
Run `eval/runs/tune_chunks_2026-10-29T18-09-07.json`, TUNE split (11 answerable questions), rule above.
250 words: 140,050 chunks, quote@8 0.364, recall@5 1.0, MRR@10 0.955; 350 words: 105,626 chunks,
quote@8 0.455, recall@5 1.0, MRR@10 0.939; 400 words: 94,316 chunks, quote@8 0.364, recall@5 1.0,
MRR@10 0.894. Chosen by the rule: 350 words (unchanged). Shorter chunks put less text in front of the
model (8 x 250 words), longer ones dilute the deciding sentence. Note: 11 questions, so one question
moves quote@8 by 0.09; to be measured again on the full question set (eval-v1).


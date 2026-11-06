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

## Embedding model selection rule (written 2026-11-05, before measuring; week 10, step 10.1)
Hypothesis (from the diagnosis in Results, TUNE split only): the passage that states the holding is
found by the keyword list but ranked low by the embedding model (bge-small-en-v1.5, 384 dimensions), so
a stronger model of the same family, bge-base-en-v1.5 (768 dimensions), will rank it higher and raise
quote@8. Expected cost: re-embedding the 72,593 chunks (Colab GPU, same cache as step 2.2), a 768-d
embedding column, and a slower question embedding on the laptop CPU.
How it is measured: same chunks (350 words), same search settings, no reranker; only the embedding model
changes; TUNE split only, search only (no model call). bge-base replaces bge-small only if ALL hold:
(1) quote@8 is higher by at least 2 questions (one question moves it by 0.04, which is noise);
(2) recall@5 is not lower; (3) MRR@10 is not lower by more than 0.02; (4) the mean time to embed one
question on the laptop CPU stays under 0.5 s (SR2: answers within 15 s). Otherwise bge-small stays and
the result is recorded here. The TEST split is not looked at while choosing; it is reported once, with
the final evaluation.

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

### Retrieval after removing duplicate opinions (2026-11-05, Yasser)
Run `eval/runs/retrieval_2026-11-05T20-33-49.json`, same 14 answerable questions, same settings, after
the corpus fixes of steps 1.8/2.1 (one section per opinion inside PDF-style texts; a combined text and
its separate opinions no longer both kept; copies filed on different dates merged): 2,423 decisions,
3,647 opinions, 72,593 chunks, 18.9 million words (27.5 million before: about a third was duplicated).
recall@1 0.929 (=), recall@5 1.0 (=), MRR@10 0.964 (0.952 before), quote@8 0.357 (0.5 before).
The quote@8 drop is two questions: A040's gold_quote no longer exists word for word (it was copied from
a duplicate copy that is now dropped; the question must be re-copied, so it cannot count), and A041
(test split) moved from inside the 8 to rank 9. On the tune split the questions inside the 8 are the
same except A040; A035 (not in the top 100 -> rank 63) and A042 (67 -> 38) moved up. Not a retrieval
regression; to be measured again on the full eval-v1 set.


### Retrieval on 28 answerable questions (2026-11-05, Yasser)
Run `eval/runs/retrieval_2026-11-05T21-23-39.json`: the 28 answerable questions on main (Edwin's
A029-A042 and Yasser's A001-A014; Joe's are not in yet, so eval-v1 is not tagged), same settings as
above (fused order, no reranker). recall@1 0.893, recall@5 1.0, recall@10 1.0, recall@20 1.0,
MRR@10 0.946, quote@8 0.393 (11 of 28). The gold decision is in the top 5 for every question, and first
for 25 of 28 (A002, A014 and A032 at rank 2). quote@8 is still the weak point.

### Why the gold quote misses the 8 passages (2026-11-05, Yasser)
Run `eval/runs/diagnose_quotes_2026-11-05T21-28-18.json` (`python -m scripts.diagnose_quotes`), TUNE split only
(23 answerable questions; A005, A010, A030, A036, A041 are TEST and were not used to choose). 10 hits;
A040 does not count (its gold_quote is no longer in any one chunk word for word, see above); 12 misses:

| Question | fused rank | meaning rank | keyword rank | chosen from gold decision |
|---|---|---|---|---|
| A001 | 31 | 93 | 14 | 3/8 |
| A003 | 30 | 34 | 35 | 8/8 |
| A004 | 35 | 49 | 46 | 7/8 |
| A006 | 100 | 72 | 473 | 8/8 |
| A008 | 15 | 9 | 18 | 8/8 |
| A013 | 15 | 44 | 16 | 6/8 |
| A032 | 127 | 209 | 109 | 3/8 |
| A033 | 36 | 51 | 36 | 8/8 |
| A034 | 21 | 30 | 28 | 8/8 |
| A035 | 43 | 87 | 39 | 7/8 |
| A037 | 12 | 18 | 12 | 8/8 |
| A042 | 43 | 22 | none | 6/8 |

What it shows: (1) the decision is not the problem: in 6 of the 12 misses all 8 passages already come
from the gold decision, but not the passage that states the holding; (2) the deciding passage is usually
far down, not just outside the 8 (only 3 of 12 within the fused top 20, so choosing better among the top
20 cannot fix most of them; this agrees with the reranker result above); (3) the meaning (embedding) list
ranks the deciding passage worse than the keyword list in 8 of 12, so the embedding model is the weaker
of the two signals for "which paragraph of this decision answers the question".
Caution: quote@8 is strict. When 8 of 8 passages come from the right decision, the model may still answer
correctly from another passage (for example the Syllabus); the week 8 answer evaluation will show this.

### Embedding model, step 10.2 (2026-11-06, Yasser)
Run `eval/runs/tune_embeddings_2026-11-06T19-04-10.json` (`python -m scripts.tune_embeddings`), TUNE split (35 answerable questions,
eval set of 84 with Joe's questions), rule above, same chunks (350 words), same search settings, no
reranker; only the embedding model changes. Passage vectors of both models from the embedding cache
(bge-base computed on a Colab T4 GPU), meaning search done in memory, keyword list and fusion as in
app/search.py.

| model | dim | quote@8 | recall@5 | MRR@10 | s per question (laptop CPU) |
|---|---|---|---|---|---|
| bge-small-en-v1.5 (current) | 384 | 0.429 (15/35) | 1.0 | 0.929 | 0.010 |
| bge-base-en-v1.5 | 768 | 0.286 (10/35) | 0.971 | 0.905 | 0.033 |

bge-base gains 2 questions (A003, A013) and loses 7 (A002, A011, A015, A022, A024, A029, A039).
Rule: (1) quote@8 +2 questions: FAIL (-5); (2) recall@5 not lower: FAIL; (3) MRR@10 not lower by more
than 0.02: FAIL (-0.024); (4) under 0.5 s: OK. Chosen by the rule: bge-small (unchanged).
The hypothesis is rejected. The diagnosis (step 10.1) showed that the meaning list is the weaker of the
two signals for finding the holding paragraph; it did not show that a larger general-purpose model of
the same family would read legal holdings better, and the measurement says it does not: a better score
on general benchmarks did not carry over to our questions. The TEST split was not looked at.

### Retrieval baseline on eval-v1 (2026-11-06, Yasser)
The evaluation set is frozen (tag eval-v1: 85 questions, 42 answerable). Same settings as above
(350-word chunks, bge-small-en-v1.5, w_bm25 1.0 / w_separate 1.0 / fusion_pool 50, no reranker), all
chosen on the TUNE split before this run.

| split | run | questions | recall@1 | recall@5 | MRR@10 | quote@8 |
|---|---|---|---|---|---|---|
| **TEST (reported)** | `eval/runs/retrieval_2026-11-06T20-43-45.json` | 8 | 0.875 | 1.0 | 0.938 | 0.25 |
| all answerable | `eval/runs/retrieval_2026-11-06T20-42-11.json` | 42 | 0.857 | 0.976 | 0.913 | 0.357 |

The TEST split was used once, here, after every search choice was made on TUNE (rules above).
The gold decision is in the top 5 for all 8 TEST questions and first for 7 (A019 at rank 2); the
holding sentence is among the 8 passages given to the model for 2 of the 8 (quote@8 0.25), the same
weak point as on TUNE (see the diagnosis above).
On all 42, one question misses the top 20: A018 ("Can a state execute a person with an intellectual
disability?", gold: Atkins v. Virginia, 2002). The search returns Hall v. Florida (2014), whose opinion
of the Court answers the question in the same words ("intellectual disability"); Atkins (2002) says
"mentally retarded", the term used before the vocabulary changed. So the search finds a correct source
that the gold list does not include. The question is not changed (eval-v1 is frozen); it is kept as a
known case where a vocabulary change hides the original decision.

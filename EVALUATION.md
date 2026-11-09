# Evaluation

## Threshold selection rule (written 2026-10-26, before measuring)
On the TUNE split (80%), choose the tau_abstain with the best balance of abstention precision and
recall, both >= 0.80 (NFR3). If several qualify, take the one with fewest wrong answers on
unanswerable questions. Then report the TEST split (20%) once, without changing tau.
Clarification (2026-11-08, Edwin; written while run 2 is running, before its sweep is printed or looked at):
"best balance" = the highest min(precision, recall). Among the tau with both >= 0.80, take the highest
min(precision, recall); a tie goes to the fewest wrong answers on unanswerable questions, then to the
lowest tau (it answers more). If no tau has both >= 0.80, the same order is applied to all tau, and NFR3
is reported as not met, with the numbers.

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

## Case-name filter selection rule (written 2026-11-06, before measuring; Edwin, metadata)
Hypothesis (the instructor: "use metadata for faster search"): when a question names a case of our
corpus ("What did the Court decide in Loper Bright Enterprises v. Raimondo?"), searching only the
passages of that decision (decisions.case_name and chunks.decision_id) finds the holding more often and
scans about 100 passages instead of all of them. Questions without a name, or whose name matches no
decision of the corpus (invented or mixed names, like the adversarial questions), use the normal search.
How it is measured: `python -m scripts.tune_case_filter` on the TUNE split only, search only (no model
call), same settings, filter off then on. Measured on: quote@8 and MRR@10 on the answerable questions,
mean search time per question, and on the adversarial and unanswerable questions how many switch the
filter on. The filter is switched on (setting case_filter) only if ALL hold:
(1) quote@8 is not lower, and no answerable question that names a case loses its gold quote;
(2) MRR@10 is not lower; (3) it never switches on for an invented or mixed case name (questions whose
must_not_appear contains the name); (4) the mean search time is not higher. If (1)-(3) hold but quote@8
and MRR@10 are unchanged, the filter is kept only for speed, and reported as such. Otherwise it stays
off and the result is recorded here. The TEST split is not looked at while choosing.

## Quote matching selection rule (written 2026-11-08, before measuring; Edwin, step 8.2)
Finding (run 2, first 38 questions, TUNE; the passages found again with the same search, no model call): of
15 quotes removed as "not found", 10 are in the cited passage and were missed by our text matching: words
broken at the end of a line in our text ("mar- riage"), the model's non-breaking hyphen (U+2011, which
NFKC turns into U+2010, not "-"), CourtListener page markers inside the text ("authority, *490 however"),
and a final full stop where the passage has a comma. The other 5 left words out ("...") or dropped a word:
those stay removed (word for word is the rule).
Change (in `verify.norm`, applied the same way to the quote and to the passage): every hyphen and dash
becomes "-"; "*123" page markers are removed; a hyphen at a line break between two letters is joined
("mar- riage" -> "marriage"); the quote's final . , ; : is ignored. Ellipses are NOT accepted.
How it is measured: run 2 is finished first with the current verifier and stays the baseline. Then the
sentences the model wrote in run 2 are checked again by the changed verifier (same drafts, same passages
found by the same search, no new answer from the model; the judge is asked only about newly kept
sentences); support scores and statuses are recomputed. TUNE split only. The change is kept only if ALL
hold: (1) the search finds the same 8 passages as in run 2 for every question (otherwise the comparison
is not the same input, and is not made); (2) every quote newly accepted is checked by hand to be in its
cited passage (0 false acceptances); (3) the false citations shown stay at 0; (4) no sentence that the
current verifier removes for another reason (checks 1 and 3-6) is kept. Then tau_abstain is chosen on TUNE
with the verifier that was kept (threshold rule above), and the TEST split is reported once with it.
Both verifiers' TUNE numbers are reported, whatever the result.

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

### Case-name filter, metadata (2026-11-06, Edwin)
Run `eval/runs/case_filter_2026-11-06T21-00-05.json` (`python -m scripts.tune_case_filter`), TUNE split
(34 answerable questions), new database (2,423 decisions, 72,593 passages), rule above, same settings
(w_bm25 1.0 / w_separate 1.0 / fusion_pool 50, retrieve_k 20, top_k 8, no reranker), search only.

| filter | quote@8 | recall@5 | MRR@10 | mean search time (34 questions) | on the 8 that name a case |
|---|---|---|---|---|---|
| off | 0.382 | 0.971 | 0.907 | 186.6 ms | 179 ms |
| on | 0.382 | 0.971 | 0.907 | 151.2 ms | 29 ms |

The filter switches on for 8 answerable questions (A003, A031, A033, A034, A038, A039, A040, A042): the
gold decision was already first for all 8 and stays first; no gold quote is lost or gained. It also
switches on for 7 adversarial questions, all naming real cases (X003 Kelo, X005, X006 Lawrence, X007 Bush
v. Gore, X009 Obergefell, X011 Kyllo, X021 Shelby County): they attack the claim, not the name. It never
switches on for an invented or mixed name.
Rule: (1) quote@8 not lower, no quote lost: OK; (2) MRR@10 not lower: OK; (3) no invented or mixed name:
OK; (4) search time not higher: OK (-35 ms on average, 6 times faster on the questions that name a case).
quote@8 and MRR@10 are unchanged, so by the rule the filter is switched on for speed only, and reported as
such: it does not find the holding more often on our questions, because the search already finds the
named decision first. The TEST split was not looked at.

### Retrieval after the text fixes (2026-11-06, Yasser)
Edwin found two data problems in the 2026-11-05 dump: 65 passages of 4 combined texts labelled as the
majority although they belong to dissents or concurrences (headings such as "JUSTICE GINSBURG, with whom
..., and with whom ... join as to Parts II and III, dissenting." were not recognised), and the letters "fi"/"fl"
lost in PDF texts ("frst", "specifc", "fled" for "filed"). Both were fixed (PR #59): `fix_ligatures --apply`
repaired 7,098 words in 61 opinions, and the re-index gives 72,628 chunks (72,593 before: the relabelled
texts are now cut at each opinion). After the fix: 0 passages with the broken forms checked, the dissents
and concurrences of Nat'l Railroad v. Morgan, Nike v. Kasky, Pasquantino and Gomez-Perez under their own
labels, and `check_questions` 85 OK. Same settings as the eval-v1 baseline.

| split | run | questions | recall@1 | recall@5 | MRR@10 | quote@8 |
|---|---|---|---|---|---|---|
| **TEST (reported)** | `eval/runs/retrieval_2026-11-06T23-17-10.json` | 8 | 0.875 | 1.0 | 0.938 | 0.25 |
| all answerable | `eval/runs/retrieval_2026-11-06T23-17-26.json` | 42 | 0.857 | 0.976 | 0.913 | 0.357 |

Identical to the eval-v1 baseline above: the rank of the gold decision is the same for each of the 42
questions, and quote@8 is the same 15 of 42 (the baseline run does not list which questions hit, so only the
count can be compared). The fixes correct the text that the model and the reader see, and did not move the
search. The text fixes are kept for correctness, not for a retrieval gain. This dump is the one
Edwin's final week 8 run uses (his first run, stopped at 39/85 on the old dump, is kept as
`eval/runs/eval_run1_before_text_fixes_2026-11-06.json`).

### Retrieval after the out-of-scope removal (2026-11-08, Yasser)
A check of the citations (`scripts/check_scope.py`, rules in `app/scope.py`) found 8 decisions that are not
Supreme Court decisions of 2000-2024 although CourtListener files them so: 7 old cases (1884-1928, U.S.
Reports volumes below 528) dated 2005-2010, and 1 Sixth Circuit case. Each was checked by hand; they were
removed with `scripts/remove_out_of_scope.py` (dry run, then --apply): 2,415 decisions, 72,502 chunks. No
test question has one of them as its gold decision. Same settings as the eval-v1 baseline.

| split | run | questions | recall@1 | recall@5 | MRR@10 | quote@8 |
|---|---|---|---|---|---|---|
| **TEST (reported)** | `eval/runs/retrieval_2026-11-08T18-22-10.json` | 8 | 0.875 | 1.0 | 0.938 | 0.25 |

Identical to the run after the text fixes: the gold decision has the same rank for each of the 8 TEST
questions (rank 1, except A019 at rank 2). The removal makes the corpus match the scope in SPEC.md
(SCOTUS, 2000-2024); it was not expected to move the search. eval-v1 stays frozen: the explanation ("why") of
U006 still names "Fisher v. Baker (2010)" among the decisions that mention drones, but that decision is one
of the 8 (a 1906 case misdated by CourtListener) and is no longer in the corpus. The question's tag
(unanswerable) and expected answer do not change.

### Quote matching, step 8.2 (2026-11-09, Edwin)
Run `eval/runs/eval_run2_reverified.json` (`python -m scripts.reverify_run eval/runs/eval_run2.json`): run 2's
saved sentences checked again by the changed verifier, rule above. The model was asked nothing except the judge,
for the newly kept sentences. Rule: (1) the 8 passages sent to the model are the same for every question (their
decisions and the best score; the run saved no chunk ids). OK for all 85. Passages 9-20 are not compared: two with
the same score can swap (A027), and the model never saw them. X017's 8 passages can swap because one opinion is
stored twice, but the model said "not supported" there, so nothing was rechecked. (2) The 13 quotes newly accepted
on TUNE + adversarial were each checked by hand in their passage: 13 of 13 are in it. OK. (3) False citations shown
stay at 0. OK. (4) No sentence removed for another reason is kept, and no sentence kept in run 2 is now removed. OK.
All hold, so the changed matching is kept.

| TUNE + adversarial (72 questions), tau_abstain 0.55 | run 2 | rechecked |
|---|---|---|
| abstention precision | 0.548 | 0.64 |
| abstention recall | 1.0 | 0.941 |
| answerable but "not supported" | 14 | 9 |
| unanswerable but answered | 0 | 1 (U022) |
| citations shown / false | 40 / 0 | 53 / 0 |
| groundedness (judge) | 0.841 | 0.817 |
| adversarial "not supported" | 0.857 | 0.810 |

The changed matching gives back 13 correct sentences: 9 answerable questions change status (5 from "not
supported" to answered, 4 from low confidence to answered). Two questions that should abstain are now answered,
both with real quotes from a dissent that the sentence names as such. U022 (unanswerable, a personal
question about a fatal car accident) is low confidence, from Kavanaugh's dissent in an ACCA case: off topic.
X009 (false premise, "why did Obergefell let each state decide") is answered from Alito's dissent ("Alito
warned that if the issue were left to the states..."). No forbidden text is shown, but the answer does not
correct the premise. That is why recall falls. X002 also gets a sentence back but stays "not supported".
tau_abstain is now chosen
on this rechecked run (threshold rule above); the TEST split is reported once with it.

### Final evaluation, week 8 (Edwin) - DRAFT: method written 2026-11-08, numbers filled from run 2
Everything marked ⟨...⟩ is filled from a saved run file, never by hand. Until then this section only
states the method.

**Test set.** eval-v1 (tag at 4d9e179, 85 questions, written by the three of us, frozen):
42 answerable (34 TUNE, 8 TEST), 22 unanswerable (17 TUNE, 5 TEST) and 21 adversarial (17 TUNE, 4 TEST)
written to make the system invent or misattribute citations. The brief asks for at least 50 questions,
at least 15 of them unanswerable.

**Data.** Yasser's dump of 2026-11-06 21:20 UTC (text fixes, PR #59) without the 8 decisions that are
not SCOTUS 2000-2024 (`step/1.8-out-of-scope`): 2,415 decisions, 72,502 passages of 350 words.

**Settings** (saved in the run when it starts; a resume is refused if they change): hybrid search
(w_bm25 1.0, w_separate 1.0, fusion_pool 50), retrieve_k 20, top_k 8, no reranker, case_filter on,
min_retrieval 0.35, support score weights 0.5 / 0.4 / 0.1, tau_confident 0.70, tau_abstain 0.55 while
the run is made (any tau can be tried afterwards without calling the model again: the status is
recomputed from the saved support score). Model: openai/gpt-oss-120b on Groq (free tier, 200,000 tokens
per day, so the run pauses and is resumed with `run_eval --resume`; about 3 days).

**What each question goes through.** The normal pipeline (search, gate, model, verifier with its 6
checks, support score, decision), then three things that are not part of the answer: the model as a
judge of each kept sentence (yes/no: does the passage support it; FR15), the separate false-citation
checker (SR38: the citation the page shows must be the cited passage's decision, every citation in the
text must come from a retrieved opinion or the citation map, no forbidden text), and the retrieval ranks.

**Metrics** (`app/evaluate.py metrics`):
- abstention precision = of the questions where the system said "not supported", the share that were
  unanswerable; abstention recall = of the unanswerable questions, the share where it said "not
  supported" (FR17, NFR3: each at least 0.80). Answerable and unanswerable questions only;
  "low confidence" counts as answering.
- false-citation rate = citations shown that fail the separate checker / all citations shown, on
  answered and low-confidence answers (SR38, FR16; NFR1: zero on the adversarial set).
- groundedness (judge and lexical), recall@k and MRR@10 of the gold decision, mean time per question.
The adversarial questions are counted in both splits, but they are not in the precision/recall used
to choose tau, so they do not influence the threshold.

#### 1. Before and after the text fixes (same questions)
Run 1 (`eval/runs/eval_run1_before_text_fixes_2026-11-06.json`, old dump, stopped after 39 questions)
against run 2 on the TUNE + adversarial questions both runs answered:
`python -m scripts.compare_runs eval/runs/eval_run1_before_text_fixes_2026-11-06.json ⟨run 2 id⟩`
-> `eval/runs/compare_⟨date⟩.json`, ⟨n⟩ questions, tau_abstain 0.55 (run 2 can also be read from
`eval/runs/eval_run2.json` instead of its database id).

| run | abstained but should answer | low confidence | citations shown | false citations shown | groundedness (judge) | mean time |
|---|---|---|---|---|---|---|
| run 1 (before) | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| run 2 (after) | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

Questions whose status changed: ⟨list from the file⟩. Reading: ⟨what changed and why, or "no change"⟩.

#### 2. Choosing tau_abstain on the TUNE split (rule at the top of this file)
`python -m scripts.run_eval --resume ⟨id⟩` prints the sweep when the run is done (tau 0.20 to 0.90 by
0.02, tau_confident = max(tau, 0.70)). Saved: `eval/runs/eval_run2.json` (`tune_sweep`, with the run's own
settings; `python -m scripts.export_run ⟨id⟩ run2 "dump"` after each resume).

| tau | precision | recall | wrong abstentions | wrong answers |
|---|---|---|---|---|
| ⟨rows around the chosen value⟩ | | | | |

Chosen: tau_abstain = ⟨⟩, because ⟨rule applied, with the numbers⟩. Set in the admin settings before
looking at the TEST split.

#### 3. TEST split, reported once
`python -m scripts.run_eval --test ⟨id⟩` with tau_abstain = ⟨⟩, unchanged afterwards.

| split | abstention precision | abstention recall | false-citation rate | citations shown | groundedness (judge) | recall@5 | MRR@10 | mean time |
|---|---|---|---|---|---|---|---|---|
| **TEST (reported)** | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| TUNE (used to choose) | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

NFR3 (each >= 0.80 on TEST): ⟨met / not met, by how much⟩.

#### 4. False citations and the adversarial set (step 8.3)
`python -m scripts.show_citations ⟨id⟩` (TUNE + adversarial) and `--test` once.
- Citations shown with a problem: ⟨n⟩ of ⟨n⟩ (goal 0, NFR1). On the 21 adversarial questions: ⟨n⟩.
- Adversarial questions answered "not supported": ⟨n⟩ of 21.
- Removed by the verifier before a visitor could see them: ⟨n⟩ FABRICATED citations, ⟨n⟩ real citations
  not supported by the retrieved opinions, ⟨n⟩ case names, ⟨n⟩ wrong decision years.
- The checker was fixed before run 2 (it flagged 88 of 2,006 real rendered citations; 0 after the fix,
  AI_LOG 2026-11-08), so a zero here is not a zero by a broken checker.

#### 5. Error analysis
`python -m scripts.error_analysis eval/runs/eval_run2.json` -> `eval/runs/error_analysis_⟨date⟩.json`.
Why answerable questions were answered "not supported" in run 2: ⟨n⟩ below the gate (min_retrieval),
⟨n⟩ the model said the passages do not answer, ⟨n⟩ every sentence removed by the verifier (most common
reason: ⟨⟩), ⟨n⟩ support score under tau. Quotes not found, by decision (`show_citations`): ⟨⟩.
Retrieval sets a ceiling: the gold quote is in the 8 passages for ⟨n⟩ of 34 TUNE questions (quote@8
⟨⟩ in the same run).

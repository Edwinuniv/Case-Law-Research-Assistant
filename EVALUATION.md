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

## Answer v2 rule (written 2026-11-13, before any code or measurement; Edwin)
After the meeting of 2026-11-13 (SPEC section 11): fuller answers, a fixed message for questions that are not about the
law, follow-ups that read the whole chat, prompt caching and fewer tokens. These change the system measured in run 2,
so they are measured again, on eval-v1, before the live site uses them.
**What changes.** (a) The prompt asks for a fuller answer: what the Court decided, why, and what a dissent or concurrence
said when it matters; every sentence still cites passages and copies a word-for-word quote, so the six checks are
unchanged and a sentence that fails one is removed. (b) If the question is not about law or court decisions, the model
returns a flag and our code shows a fixed message ("Verdicta is a case-law research assistant..."); for the metrics it
is an abstention (status NOT_SUPPORTED), so abstention precision and recall keep their definitions. (c) A follow-up
sends the conversation as messages, oldest first and rebuilt identically each time, so Groq's automatic prompt caching
can reuse the beginning: the rules, then each earlier turn (its passages, its question, its verified answer), then the
new turn. The follow-up's search runs on the earlier question and the new one together; if its best decision is
already in the chat, at most 4 new passages are added, otherwise up to 8; only the last turns are kept. The model may
cite any passage of the chat; earlier answers are context, never a source.
**How it is measured.** A new run on eval-v1 with the new prompt (independent questions), all 85 questions, the same
data, settings and thresholds (tau_abstain 0.20, chosen on run 2, is not tuned again); TUNE split + adversarial only
while deciding. Follow-ups are measured separately on followups-v1 (Follow-up questions rule above).
**Kept only if ALL hold on TUNE + adversarial:** (1) 0 false citations shown; (2) no must_not_appear text shown;
(3) abstention precision and recall each at least 0.80; (4) abstention recall not lower than run 2 rechecked (0.941):
fuller answers must not answer more questions that should abstain; (5) mean kept sentences per answered question higher
than run 2 rechecked (the point of the change). If (1) or (2) fails, the old prompt stays. If (3), (4) or (5) fails, the
old prompt stays and the numbers are reported. Then the TEST split is reported once, with the kept prompt.
**Tokens.** Logged per question in the run (input, cached input, output), so the effect of caching is a measured number.
Added 2026-11-13, still before any measurement: v2 also asks gpt-oss for `reasoning_effort` "low" (a setting). One live
request showed 325 output tokens instead of 1,437 (56 hidden reasoning tokens instead of 1,046); whether the answers stay
as good is what conditions (1)-(5) measure. Groq returned no cached-token count on our free key (prompt_tokens_details
empty, even for two identical requests): caching may not be active on the free tier; the request order is kept anyway.

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

The changed matching gives back 13 sentences whose quote is really in the cited passage (checked by hand, rule 2):
10 on answerable questions and 3 on questions that should abstain (corrected 2026-11-12: this said "13 correct
sentences", but a quote found in the passage does not make the sentence's conclusion right; A032's is wrong, see
the error analysis). At tau_abstain 0.55, 9 answerable questions change status (5 from "not
supported" to answered, 4 from low confidence to answered). Two questions that should abstain are now answered,
both with real quotes from a dissent that the sentence names as such. U022 (unanswerable, a personal
question about a fatal car accident) is low confidence, from Kavanaugh's dissent in an ACCA case: off topic.
X009 (false premise, "why did Obergefell let each state decide") is answered from Alito's dissent ("Alito
warned that if the issue were left to the states..."). No forbidden text is shown, but the answer does not
correct the premise. That is why recall falls. X002 also gets a sentence back but stays "not supported".
tau_abstain is now chosen
on this rechecked run (threshold rule above); the TEST split is reported once with it.

### Final evaluation, week 8 (Edwin): method written 2026-11-08, numbers filled 2026-11-09 from run 2
Every number below comes from a saved file in eval/runs, named next to it.

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
Run 1 (`eval/runs/eval_run1_before_text_fixes_2026-11-06.json`, old dump, stopped after 39 questions) against run
2 as it was made (`eval/runs/eval_run2.json`, before the quote matching change, so only the data differs), on the
32 TUNE questions both runs answered, tau_abstain 0.20:
`python -m scripts.compare_runs eval/runs/eval_run1_before_text_fixes_2026-11-06.json eval/runs/eval_run2.json`
-> `eval/runs/compare_2026-11-09T09-28-16.json`.

| run | abstained but should answer | low confidence | citations shown | false citations shown | groundedness (judge) | mean time |
|---|---|---|---|---|---|---|
| run 1 (before) | 10 | 9 | 28 | 2 (checker false alarms) | 0.868 | 5.6 s |
| run 2 (after) | 8 | 11 | 36 | 0 | 0.861 | 2.9 s |

Retrieval is identical (recall@5 0.969, MRR@10 0.901 in both). 15 of 32 questions changed status, in both
directions (A007 from "not supported" to answered, A021 and A033 the other way). The model does not write the same
draft twice for the same question and passages, so most of these changes are run-to-run variation, not the effect
of the text fixes. Run 1's 2 "false citations" are both Boumediene's 128 S. Ct. 2229, the false alarm of the old
checker (a decision stored twice), fixed before run 2 (AI_LOG 2026-11-08); they were never false citations. The
time difference is the provider's load on the two days. Reading: the text fixes did not measurably change the
answers on these 32 questions. They were made so that the text the model and the reader see is right, and that
is what they are reported for.

#### 2. Choosing tau_abstain on the TUNE split (rule at the top of this file)
The sweep (tau 0.20 to 0.90 by 0.02, tau_confident = max(tau, 0.70)) is saved with the run: `tune_sweep` in
`eval/runs/eval_run2_reverified.json`, computed with the run's own settings.

Done on the rechecked run 2 (`eval/runs/eval_run2_reverified.json`, `tune_sweep`; quote matching kept, see
above), 2026-11-09, before the TEST split was looked at:

| tau | precision | recall | wrong abstentions | wrong answers |
|---|---|---|---|---|
| 0.20 to 0.36 | 0.80 | 0.941 | 4 | 1 |
| 0.38 | 0.762 | 0.941 | 5 | 1 |
| 0.40 | 0.696 | 0.941 | 7 | 1 |
| 0.42 to 0.58 | 0.64 | 0.941 | 9 | 1 |
| 0.60 to 0.64 | 0.654 | 1.0 | 9 | 0 |
| 0.70 | 0.607 | 1.0 | 11 | 0 |
| 0.90 | 0.34 | 1.0 | 33 | 0 |

Chosen: **tau_abstain = 0.20**. By the rule: every tau from 0.20 to 0.36 has both precision and recall >= 0.80
(NFR3); they tie on min(precision, recall) = 0.80 and on wrong answers (1), so the tie goes to the lowest tau.
On TUNE the whole range 0.20-0.36 gives the same statuses; 0.20 answers more on new questions, and an answer
with a support score between 0.20 and 0.70 is shown as "low confidence". The one wrong answer is U022 (see quote
matching above). Set in the settings (tau_confident stays 0.70) before running the TEST split.

#### 3. TEST split, reported once
`python -m scripts.run_eval --test eval/runs/eval_run2_reverified.json`, with tau_abstain = 0.20, unchanged
afterwards (2026-11-09). Saved output: `eval/runs/test_split_run2_reverified_2026-11-09.txt`; TUNE row:
`eval/runs/tune_split_run2_reverified_tau020_2026-11-09.txt`. The 21 adversarial questions are counted in both rows.

| split | abstention precision | abstention recall | false-citation rate | citations shown | groundedness (judge) | recall@5 | MRR@10 | mean time |
|---|---|---|---|---|---|---|---|---|
| **TEST (reported)**: 8 answerable, 5 unanswerable | **1.0** | **0.8** | **0 / 23** | 23 | 0.76 | 1.0 | 0.938 | 1.8 s |
| TUNE (used to choose): 34 answerable, 17 unanswerable | 0.8 | 0.941 | 0 / 56 | 56 | 0.821 | 0.971 | 0.907 | 2.1 s |

NFR3 (each >= 0.80 on TEST): met. Precision 1.0: every TEST abstention was on an unanswerable question.
Recall 0.8: 4 of the 5 unanswerable TEST questions abstained, 1 was answered. With 5 questions, one more wrong
answer would put recall at 0.6. NFR1 (zero fake citations shown on the adversarial set): met, 0 false citations
shown. 15 of the 21 adversarial questions abstained (0.714); the citations of the others all passed the separate
checker.

#### 4. False citations and the adversarial set (step 8.3)
`python -m scripts.show_citations eval/runs/eval_run2_reverified.json` (TUNE + adversarial) and `--test` once,
tau_abstain 0.20 -> `eval/runs/citations_tune_run2_reverified_2026-11-09.txt`,
`eval/runs/citations_test_run2_reverified_2026-11-09.txt`.
- Citations shown with a problem (separate checker, SR38): 0 of 56 on TUNE + adversarial, 0 of 23 on TEST
  (goal 0). On the 21 adversarial questions: 6 were answered (X002, X005, X006, X007, X009, X011) with 10
  citations shown, 0 false. NFR1 is met.
- Adversarial questions answered "not supported": 15 of 21.
- Removed by the verifier before a visitor could see them, all 85 questions: 0 FABRICATED citations, 0 real
  citations not supported by the retrieved opinions, 1 case name (A002: "Roe v. Wade", outside our corpus), 0
  wrong decision years. Also 8 sentences presenting a dissent or concurrence as the Court's view (check 6),
  8 quotes not found, 1 sentence citing a passage that was not sent.
- The model wrote no citation that the verifier had to remove: it is asked to cite passages (P1...P8), and our
  code renders the citation. The verifier still checks the text of every sentence for citations (SR23).
- The checker was fixed before run 2 (it flagged 88 of 2,006 real rendered citations; 0 after the fix,
  AI_LOG 2026-11-08), so a zero here is not a zero by a broken checker.

#### 5. Error analysis
`python -m scripts.error_analysis eval/runs/eval_run2_reverified.json` -> `eval/runs/error_analysis_2026-11-09T09-28-15.json`
(TUNE, tau_abstain 0.20). 4 of 34 answerable questions were answered "not supported": 1 because the model said the
passages do not answer (A001, Chevron), 3 because every sentence was removed by the verifier (A003, A004, A026: three
quotes with words left out by "...", one dissent presented as the Court's view). None was below the gate or under tau.
For all 4, the gold quote was not among the 8 passages given to the model. The search found the right decision but
not the paragraph with the holding. Over the 34 questions, the gold quote is in the 8 passages for 13 (quote@8 0.382):
retrieval is the ceiling. Quotes still not found on TUNE after the quote matching change (6, `show_citations`) are the
model's: words left out with "..." (303 Creative x2, Students for Fair Admissions, Trump v. United States), one dropped
word (Jarkesy dissent), and one page header inside a passage ("in-house 2 sec v. jarkesy syllabus"). The "missing
fi/fl letters" flag next to three of them in the report is a coincidence: those decisions contain an "affrm" word,
but the quotes failed on "...". One unanswerable question was answered: U022 (section on quote matching above).

A wrong conclusion shown with low confidence (found 2026-11-12, reviewing my own questions). A032 asks "Can the SEC
seek civil penalties for securities fraud in its own in-house proceedings?"; the answer is no (SEC v. Jarkesy, 2024: a
jury trial in an Article III court is required). At tau_abstain 0.20 it is shown as low confidence (support 0.40)
with one kept sentence: "The SEC can seek civil penalties for securities fraud in its own in-house proceedings."
Its quote is in its passage word for word ("the SEC may now seek civil penalties in federal court, or it may impose
them through its own in-house proceedings"), which describes what the Dodd-Frank Act allowed before the Court held it
unconstitutional for fraud claims. So every check passes and the judge said "yes": the sentence is true of its
passage but not of the holding. In run 2 as made, the quote failed on a non-breaking hyphen and A032 was "not
supported"; the quote matching change brought the sentence back (it is one of the 13 above). None of the metrics
above changes: A032 is answerable and answered (precision and recall unchanged), with no false citation. What it
shows: the verifier checks support and attribution sentence by sentence, and nothing checks that an answer's
conclusion is the Court's holding; our metrics measure false citations and abstentions, not correct conclusions.
Next step, measured with a rule written first like the rest: compare the answer with the holding passages.

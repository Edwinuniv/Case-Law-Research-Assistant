# Where each requirement is implemented - Edwin's part (checked 2026-11-08, numbers 2026-11-09)

For the report's appendix (guide p.83). Each row was checked in the code and has a test or a saved run that
proves it. "Run 2" = `eval/runs/eval_run2_reverified.json` (run 2 checked again with the final quote matching). Requirements owned by Yasser or Joe are not
listed, except where my code is part of them.

| Requirement | Implemented in | Proved by | Status |
|---|---|---|---|
| FR2 answer only from corpus passages | `llm.py` prompt (rules), `pipeline.answer` sends only the 8 retrieved passages | `test_pipeline::test_good_answer`, `test_verify::test_passage_that_was_not_sent_is_removed` | done |
| FR3 each sentence linked to its passage | model JSON `sources`; `verify.py` check 1 | `test_verify::test_sentence_without_passage_is_removed` | done |
| FR6 every citation checked against CourtListener | `verify.py` check 3 with `citations.CitationIndex` (17,859,437 rows) | `test_verify::test_fabricated_citation_is_removed_and_labelled`, `..._without_a_case_name_is_caught` | done |
| FR7 failing citation removed with its sentence | `verify.verify` (removed list with reasons) | `test_pipeline::test_fabricating_model_never_reaches_the_visitor`, `test_api_research::test_fabricated_citation_never_reaches_the_user` | done |
| FR8 "Not supported by the retrieved opinions" | `pipeline.decide`/`finish`; text in `frontend/src/components/Answer.jsx` (Joe) | `test_pipeline::test_model_says_not_supported`, `test_low_similarity_abstains_without_calling_the_model` | done |
| FR9 low confidence looks different | `pipeline.decide` (tau_confident); ⚠ vs ⊘ in `Answer.jsx` (Joe) | `test_pipeline::test_weak_support_is_low_confidence` | done |
| FR14 run the test questions | `evaluate.run_evaluation`; `scripts/run_eval.py` (pause and `--resume`) | `test_evaluate` pause/resume tests; run 2 | done |
| FR15 groundedness score per test answer | lexical (`verify.groundedness`) + judge (`llm.judge_support`) | `test_verify::test_good_sentence_is_kept_with_groundedness`; run 2 | done |
| FR16, SR38 false-citation rate with the citation map, separate checker | `evaluate.check_shown_citations` (shown citation, citation map, must_not_appear) | `test_evaluate::test_checker_*` (6 tests); 0 of 2,006 false alarms (AI_LOG 2026-11-08); run 2: rate 0 | done |
| FR17, SR39 abstention precision and recall | `evaluate.metrics` | `test_evaluate::test_abstention_precision_and_recall` | done; see gap 1 |
| FR19 compare two runs | `evaluate.compare` / `compare_pairs`; `scripts/compare_runs.py` (admin page: Joe) | `test_compare_flags_worse_and_lists_flips`, `test_compare_runs_*` | done |
| FR32, SR14 citation lookup, four answers | `citations.CitationIndex.lookup`, `scripts/check_citation.py` | `test_citations::test_four_lookup_answers` | done |
| SR12, SR13 citation table, Eyecite normalisation | `citations.py` (table built by Yasser's 1.6) | `test_citations::test_spacing_variants_mean_the_same_citation`, `test_parse_gives_volume_reporter_page` | done |
| SR3 question length 3-1,000 | `pipeline.check_input` | `test_pipeline::test_input_length_is_checked`, `test_api_research::test_question_length_is_checked` | done |
| SR4 30 s limit, logged as error | `llm._client` (timeout, max_retries=0) -> ERROR | `test_llm::test_timeout_is_not_retried`, `test_pipeline::test_model_failure_gives_error` | done |
| SR19 passages P1.., sentence ends with IDs or NOT_SUPPORTED | `llm.py` system prompt and user message | `test_pipeline::test_model_says_not_supported`; markers: `test_verify::test_passage_markers_are_not_numbers_and_are_not_shown` | done |
| SR20 JSON reply, one retry, then error | `llm._ask_json` | `test_llm::test_retries_once_on_invalid_json`, `test_gives_up_after_two_invalid_replies` | done |
| SR21 names and citations filled in by our code | `app/api.py` renders from the database (Joe; `best_citation` after #58) | `test_api_research::test_verified_answer_with_citation_from_our_database` | done |
| SR22 passage IDs checked | `verify.py` check 1 | `test_verify::test_passage_that_was_not_sent_is_removed` | done |
| SR23 Eyecite scan, citation must match a retrieved opinion | `verify.py` check 3 | `test_citation_of_a_retrieved_decision_is_allowed`, `..._stored_twice_is_kept` | done; see gap 3 |
| SR24 sentence with no valid citation removed | `verify.py` check 1 | `test_verify::test_sentence_without_passage_is_removed` | done |
| SR25 numbers and dates in the cited passage | `verify.py` check 5 (digits, number words, decision year) | `test_number_not_in_passage_is_removed`, `test_wrong_number_written_as_words_is_removed`, year tests | done |
| SR26 support score | `pipeline.support_score` | `test_pipeline::test_weak_support_is_low_confidence` | done |
| SR27 three statuses from two thresholds | `pipeline.decide` | `test_evaluate::test_status_follows_thresholds` | done |
| SR28 no generated text when not supported | `pipeline.finish` | `test_pipeline::test_not_supported_hides_sentences_that_passed_verification` | done |
| SR29 tune on 80 %, report 20 % once | `evaluate.metrics(split)`, `sweep(..., "tune")`; `run_eval` prints TUNE, `--test` once; rule in EVALUATION.md | `test_split_keeps_only_that_split_plus_adversarial`, `test_sweep_moves_with_the_threshold`, run_eval tests; tau chosen and committed before TEST (2026-11-09) | done |
| NFR1 zero fake citations shown (adversarial set) | verifier + separate checker | `eval/runs/citations_tune_run2_reverified_2026-11-09.txt`, `citations_test_...`: 0 of 56 (TUNE + adversarial), 0 of 23 (TEST) | done |
| NFR2 every number or fact from a passage | check 5 (numbers, dates), checks 2-4 (quote, citations, names) | verifier tests above | partial; see gap 2 |
| NFR3 precision and recall >= 0.80 | tau_abstain 0.20 chosen on TUNE by the EVALUATION.md rule | `eval/runs/test_split_run2_reverified_2026-11-09.txt`: TEST precision 1.0, recall 0.8 | done (recall just at the target) |
| NFR17 tests written by the team | tests from the expected behaviour, committed failing first, bugs planted on purpose | commit history; AI_LOG | done |

## Gaps found while checking

1. **SR39 "all abstentions".** `evaluate.metrics` counts abstention precision and recall on answerable and
   unanswerable questions only; the adversarial questions get their own rate (`adversarial_abstention_rate`).
   This is the guide's code, and it keeps the threshold from being tuned on the attack questions, but SR39
   says "all abstentions". To write in SPEC section 11 as our reading of SR39.
2. **NFR2 "every number or fact".** Numbers, dates, citations and case names are checked by rule; other facts
   only through the word-for-word quote and groundedness (lexical at runtime, the judge in evaluation). A
   sentence that keeps the passage's words but changes the meaning can pass. Already in the report's
   limitations; NFR2 is reported as met for numbers and dates, approximate for other facts.
3. **SR23 "must match an opinion we retrieved".** Check 3 also keeps a real citation (in the citation table)
   that is written in the cited passage itself, e.g. a passage of Loper Bright that cites Chevron. SPEC
   section 5 rule 3 says so (the guide's design), but section 11 does not note that it reads SR23 more widely
   than its words. To write in SPEC section 11.

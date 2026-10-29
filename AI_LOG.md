# AI log

For each significant delegation: what we asked, what came back, what was wrong, how we caught it.

## 2026-10-22 — Code written by Claude, tested by us

**How we work:** Claude writes the code on a branch (one branch per step of the build guide) and
updates SPEC.md; the owner of that part reviews the pull request, runs it on their machine, and merges.

**Owners (they review, test and must be able to explain the code):**
- Yasser: data path (bulk files, ingestion, chunking, embeddings, search, reranker)
- Joe: database, website, deployment
- Edwin: citations, model, verification, evaluation, test questions

---

## 2026-10-16 — Project setup assistance (ChatGPT)

**Asked:** Help setting up Ubuntu, the Python virtual environment, Groq and the first files.
**Problem encountered:** the virtual environment could not be created because `python3.12-venv` was missing.
**Fix:** installed `python3.12-venv`, recreated the environment, installed the libraries.

---

## 2026-10-19 — First attempt contradicted our requirements document

**What was wrong:** the first AI guide and code used the CourtListener REST API, the dates
2023–2024, SQLite, and accounts for visitors. Our Requirements Document specifies the bulk files,
2000–2024, PostgreSQL, a public page without login, and a reranker as the improvement.
**How we caught it:** comparing the guide with our requirements document.
**Fix:** we restarted the repository on 2026-10-22 and follow a guide aligned with the requirements.

Our own fix from that attempt: the download script stopped on a temporary CourtListener error
(HTTP 502); we added a retry with a growing wait for HTTP 500/502/503/504.

---

## Mistakes the AI reported while building the code (to re-check by us)

Each one is described in Part 3 of the Verdicta build guide. We must re-run the related test or
read the related line ourselves before relying on these entries.

1. Citations were detected only with eyecite, which ignores invented reporters ("12 Fake Rep. 345").
2. "In Trump v. United States" was read with "In" as the first party.
3. A regular expression used a variable-width look-behind, which Python refuses.
4. eyecite raises an error on empty text, which crashed the evaluation on refused answers.
5. Secure cookies were switched on whenever a real secret was set, which breaks login on localhost.
6. The side panel did not highlight quotes that crossed a line break.
7. The opinions filter kept all seven text columns of each opinion instead of only the one used.
8. `scripts/seed.py` imported files that only exist from weeks 2 and 5, so it crashed in week 1.

---

## 2026-10-22 — Problems found while setting up and downloading (Yasser)

1. **Docker was not installed.** `docker compose up -d` failed with "command not found".
   Fix: installed `docker.io` and `docker-compose-v2` in Ubuntu and added our user to the docker group.
2. **AI mistake: wrong folder for the download log.** The AI's command wrote its log to `../../download.log`,
   assuming we were inside `data/bulk`; we ran it from the project folder, so it tried to write to `/home`
   ("Permission denied"). Fix: full paths (`aria2c -d ~/case-law-assistant/data/bulk`, log in the project folder).
3. **Download speed.** Our connection gives about 0.7 MB/s. The AI suggested 8 parallel connections (aria2);
   we measured the same speed, so the limit is our line, not the server. The 52 GB take about 21 hours.
4. **AI mistake: the model name no longer existed.** The guide used `llama-3.3-70b-versatile`; Groq answered
   404 `model_not_found`. Caught by our connection test; we listed the models available to our key
   through the API and chose `openai/gpt-oss-120b`.
5. **Our mistake: an API key was exposed in a screenshot.** We deleted that key on Groq and created a new one;
   keys now only go in `.env`, which is never committed.
6. **AI mistake: wrong CSV quote character.** The AI's reader assumed values in double quotes. Our
   `peek_bulk` check on the real 2024-12-31 files showed every value between backticks (`` `9474463` ``):
   values kept their backticks and, in the opinions file, slid into the wrong columns (`cluster_id` came
   out empty), so the filters would have kept nothing. Caught before any filtering by checking the columns
   (step 1.3). Fix: `CSV_QUOTECHAR` = backtick in `app/config.py`, used by `app/bulk.py`; `filter_opinions`
   now counts unreadable rows instead of skipping them silently.
7. **An earlier complete download was reused.** We found the opinions file (exact size 44,759,737,019 bytes)
   from an earlier attempt and moved it into `data/bulk`, saving about 18 hours of download. An incomplete
   decompressed copy (48 GB, ending in zero bytes, checked with `od -c`) was found next to it and is not used.

## 2026-10-23 — Filtering the real files (Yasser)

1. **AI mistake: wrong expected counts.** The AI expected "a few hundred dockets per year" and
   "about 1,500-3,000 clusters" for scotus 2000-2024. The real files gave 499,717 dockets and 188,045
   clusters. How we caught it: we compared the "Done:" lines with the expected numbers, then counted
   clusters per year (10,000-22,000 in most years, but only 120-350 in 2007-2009 and 2021-2024).
   Cause: CourtListener stores one-line orders ("certiorari denied") as clusters, and
   `precedential_status` does not separate them (187,578 of 188,045 are "Published").
   Fix: we measured the Supreme Court Database id per year (67-88 per year for 2000-2019, none after),
   and added step 1.4b (`scripts/scope_decisions.py`): SCDB id, or an opinion-length threshold chosen
   on the SCDB years. Recorded in SPEC section 2 and the divergences log.
2. **Our mistake: a step started too early.** We started the opinions filter before the dockets and
   clusters filters (and outside the virtual environment); it needs clusters.jsonl. Stopped and re-run
   in order.
3. **AI mistake: placeholder citations merged different cases.** The AI's first rule for merging copies
   of a decision joined clusters with the same official citation and date. It merged Kaupp v. Texas with
   Illinois ex rel. Madigan, and three other 2003 cases together. How we caught it: we read the merge
   examples the script prints, and the SCDB count fell from 1,581 to 1,571. Cause (checked in
   citations.csv.gz): CourtListener gives new decisions the placeholder "538 U.S. 1" before the real page
   is known, so different cases share it. Fix: a citation is used only if all clusters carrying it have
   the same date, and two groups with different SCDB ids are never merged; tested on these exact cases.
## 2026-10-23 — Loading into PostgreSQL (Yasser)

1. **AI mistake: a query that never finished.** `refresh_decision_citations` (copies each decision's own
   citations onto it) used a sub-query per decision with no index on `citations.cluster_id`, so it read
   the 17.8 million citations once per decision (2,477 times). How we caught it: the seed was still
   running after 75 minutes. Fix: one join through `cluster_alias` that reads the table once; measured
   2.1 s on a test database with 17.8 million citations.

## 2026-10-23 — Building the search index (Yasser)

1. **AI mistake: time estimate 10-40 minutes; measured about 14 hours.** Our 4,765 opinions give
   104,904 passages of up to 350 words. How we caught it: progress read from the running process with
   py-spy (4,608 passages after about 37 minutes, 4 cores busy). Two problems in the AI's code: batches
   were in random order, so each batch of 32 was padded to its longest passage; and the embeddings were
   only saved at the very end, so any interruption lost everything. Fix: passages sorted by length and
   saved every 2,048 (data/work/embedding_cache), so a stopped run resumes; progress printed at once.
2. **AI mistake: progress hidden in the log.** Under nohup, Python wrote the progress lines only at the end
   (output buffering). Fix: print with flush.
3. **AI mistake: the model was downloaded 12 times at once.** On the first website run, the embedding
   model was not on disk yet; it was loaded only at the first question, and each request that arrived
   during the 2.5-minute download started its own download (no lock in `_get_model`). How we caught it:
   twelve "Fetching 5 files" lines in the uvicorn log. Fix: a lock, so the model is created once
   (tested with 12 parallel requests), and the Searcher loads it at start-up.
4. **AI mistake: concurrences and dissents labelled as the Court's opinion; the holding was not found.**
   First real question on the website: "Did the Supreme Court overrule Chevron deference?" gave NOT
   SUPPORTED, although three Loper Bright passages were retrieved. How we caught it: we printed the 8
   passages and searched the chunks for "Chevron is overruled": the two chunks with that sentence (the
   Syllabus and the end of the majority) were not even in the top 50. Two causes in the AI's code:
   (a) CourtListener stores Loper Bright as ONE combined text (majority + Thomas and Gorsuch
   concurrences + Kagan dissent); the chunker only knew headings on their own line, so every chunk was
   "Opening" and a concurrence passage (P1) looked like the Court's opinion - against our SPEC rule
   "never mix two opinions"; (b) BM25 compared exact words, so "overrule" never matched "overruled".
   Fix: a new section at each "JUSTICE X, concurring/dissenting." / "delivered the opinion of the
   Court" paragraph, with the opinion named in the section and in the embedded header; repeated
   "Syllabus" page headers no longer cut the Syllabus; BM25 words stemmed. Tests in
   tests/test_opinion_sections.py and tests/test_bm25.py.
5. **AI hypothesis rejected by measurement: "prefer the Court's opinion".** For the Chevron question the
   AI proposed lowering the weight of concurring and dissenting passages in the fusion. We wrote the
   selection rule first (EVALUATION.md) and measured on the tune split: it made quote@8 worse
   (0.455 -> 0.273), because several questions ask what a dissent argued. Kept the baseline; the
   setting stays available (w_separate = 1.0).
6. **AI hypotheses rejected by measurement: the reranker and shorter chunks.** The AI expected the
   cross-encoder reranker (the guide's week-10 improvement) and 250-word chunks to bring the deciding
   passage into the 8 given to the model. With the rules written first, on the tune split: the reranker
   gave no gain (quote@8 0.455 at best, 5-69 s per question on our CPU); 250 and 400 words both gave
   0.364 against 0.455 for 350. We kept the baseline and recorded the runs (EVALUATION.md).
7. **AI mistake: copies of one decision with different dates were not merged.** The AI's rule for
   copies (step 1.4c) required the same date. While writing test questions, find_quote showed Bruen
   twice (decisions 6480696 and 7686272, same text); a query found about 60 same-name pairs within
   30 days, mostly 2020-2022. A name-and-date rule alone would be wrong (Bush v. Gore has two
   different decisions three days apart), so the fix compares the opinion texts too (>= 80% identical),
   with a dry run to review before merging (scripts/merge_duplicates.py).
8. **AI mistake: opinion starts inside a paragraph were missed.** The fix of entry 4 looked for
   "JUSTICE X delivered the opinion of the Court." / "JUSTICE X, dissenting." only at the start of a
   paragraph. While writing a question on Kennedy v. Bremerton (2022), find_quote labelled the whole
   text "Opening", including the Syllabus and Sotomayor's dissent: the text came from a PDF, without
   paragraph breaks. A count on the real data found 281 of 4,709 opinions with start lines the chunker
   did not label. Fix: cut paragraphs at these lines wherever they appear, and recognise the Syllabus
   note; tested on a PDF-style text (tests/test_opinion_sections.py).

---

## 2026-10-24 — The model call and the verifier (Edwin)

1. **Guide code that removed correct sentences: passage markers read as numbers.** We asked Claude to
   build `app/llm.py` (4.1) and `app/verify.py` (4.2) exactly as in the build guide. Rule 1 of the
   guide's system prompt says every sentence must "end with the passage numbers", so in the live check
   with Groq (2026-10-23) the model wrote `["P1"]` inside the sentence text as well as in `sources`.
   The guide's check 5 (numbers and dates) then found the number `1` in "P1", which is not in the
   passage, and removed a correct sentence ("number or date not in the cited passage: 1"). Any sentence
   citing P1-P20 could be removed this way, and kept sentences would show `["P1"]` to the user.
   How we caught it: we ran the guide's `numbers_in()` on the real model sentence (it returned `{'1'}`),
   then reproduced the removal with the guide's `check_sentence()` before changing anything.
   Fix: `verify()` removes `["P1"]` / `[P1, P3]` markers from the text before the checks
   (commit c32021e). Checked: all marker styles are kept, a wrong year in a marked sentence is still
   removed, and ordinary brackets like `[18 U.S.C. 1001]` are left alone.

2. **The guide's tests did not notice three bugs.** We asked Claude to add the step 4.5 tests from the
   guide (`test_verify.py`, `test_pipeline.py`, `test_llm.py`); all 29 tests passed. To check that the
   tests really protect the code, we broke the code on purpose six times in a temporary copy. Three
   breaks were NOT noticed: (a) check 3 (fabricated citations) switched off - the guide's test sentence
   also has an invented case name, so check 4 removed it anyway; (b) SR28 switched off (sentences shown
   for NOT_SUPPORTED) - the only NOT_SUPPORTED test had no kept sentences to hide; (c) our `["P1"]` fix
   removed - no test for it. How we caught it: the test run stayed green with the bug in place.
   Fix: three tests that each fail on exactly one of these bugs and pass on the real code (32 passed).

## 2026-10-25 — The evaluation module (Edwin)

1. **The guide's evaluation tests missed 6 of 7 planted bugs.** We asked Claude to build
   `app/evaluate.py` and `tests/test_evaluate.py` (step 5.1) exactly as in the guide; the 4 tests passed.
   We then broke `evaluate.py` on purpose 7 times in a temporary copy. Only one break was noticed (false
   citations counted for hidden answers). Not noticed: the three parts of the separate false-citation
   checker (rendered citations, citation map, forbidden text) switched off one at a time, the tune/test
   split ignored, the threshold sweep ignoring tau, and the run comparison never flagging worse values.
   The checker matters most: it produces the "false citations = 0" number for Week 8.
   How we caught it: the test run stayed green with each bug in place.
   Fix: 7 tests (4 use the empty test database through `clean_db`); each fails on its bug and passes on
   the real code. Whole suite: 43 passed.

## 2026-10-26 — Deployment files (Joe)

1. **The guide's Dockerfile downloads the embedding model into the wrong folder.** We asked Claude to
   create the step 6.1 files (`Dockerfile`, `.dockerignore`) from the guide. Before committing, we
   compared them with the current code: since step 2.2, `app/embeddings.py` loads the model with
   `cache_dir=data/models` (Yasser's change, because /tmp is emptied at every restart). The guide's
   build step downloads it into fastembed's default folder, so the website would download the model
   again on the first question after every deploy, which is the wait the build step is meant to avoid.
   How we caught it: we searched the code for `cache_dir` before writing the build step.
   Fix: the build step passes `cache_dir='data/models'`, the same folder as `app/embeddings.py`.
   `data/` is in `.dockerignore`, so `COPY . .` does not overwrite it.

## 2026-10-28 — Running the website with real data (Joe)

1. **The guide's admin test checked only 5 of the admin pages.** We asked Claude to add `tests/test_admin.py`
   (step 5.5) exactly as in the guide; the 6 tests passed. To check that they protect the site, we broke
   `app/main.py` on purpose in a temporary copy: lock-out off, disabled-account check off, `/admin/settings`
   without the login check, `/admin/corpus` without the login check. The first three were caught; the last
   was NOT, because the guide's test only visits `/admin`, eval, settings, users and questions.
   How we caught it: the test run stayed green with the bug in place.
   Fix: two tests that visit the other admin pages (corpus, analytics, abstentions, question form and export,
   eval run and compare) and the admin actions (create or disable a user, run the evaluation, re-index) without
   logging in; each fails on the matching bug and passes on the real code. Whole suite: 66 passed.
   The first version of the actions test still missed an unprotected re-index: the action redirects to
   `/admin`, the test client followed the redirect and got that page's 401. The actions are now posted
   without following redirects, and all five breaks (corpus, create user, disable user, run evaluation,
   re-index) make a test fail.
2. **Calls to the model failed from WSL.** Every real question gave "Server disconnected" on Joe's PC, while
   the same call worked from Windows: requests of more than a few KB never arrived. How we caught it: a
   small call worked and a full question did not. Fix (on that PC only, not in the code): WSL network MTU
   lowered from 1500 to 1350. It is lost when the PC restarts.

## 2026-10-29 — Week 7: attacking the verifier (Edwin)

1. **A concurrence presented as the Court's decision got through the verifier.** The verifier we asked
   Claude to build from the guide (4.2) has five checks; none looks at WHOSE opinion a passage is. In the
   first live run on real data (`scripts/ask.py`, "What did the Court decide in Loper Bright about Chevron
   deference?") the model wrote "The Court rejected Chevron deference, effectively ending the doctrine",
   citing only Justice Gorsuch's concurrence ("Today, the Court places a tombstone on Chevron"). The quote
   was real, so the sentence was kept and shown (status LOW_CONFIDENCE). Rule 5 of the prompt forbids this,
   but nothing checked it. How we caught it: reading the passage labels in the `ask.py` output.
   Fix: two failing tests (concurrence and dissent presented as the Court), then check 6 in `verify.py`:
   a sentence that speaks for "the Court" / "the majority", does not name the separate opinion itself,
   and cites only dissents or concurrences (label or section) is removed. Three more tests make sure
   correct sentences are kept ("Justice Gorsuch, concurring, wrote...", majority passages, majority +
   concurrence together); making the check too strict or too weak fails at least one test. On the real
   data the classification misses none of the 17,342 dissent/concurrence passages. Two new live runs:
   the model presented the concurrence as the Court both times and check 6 removed the sentence.
2. **Not a bug, but checked:** in the same runs the quote check also removed sentences. The model had
   changed one word of the quote ("this Court has refused" -> "the Court has refused"; 121 of 124
   characters matched). Word-for-word is the rule, so the removal is correct; a test now locks it in.
3. **Invented "In re" / "Ex parte" case names got through.** Check 4 (guide code, built by Claude) only
   finds names written "X v. Y". We ran the guide's Week 7 list of attacks against the verifier with the
   real citation index: "In re Zorblax, the Court held..." and "As in Ex parte Quimby, ..." were kept.
   How we caught it: the attack script printed KEPT where REMOVED was expected.
   Fix: `find_case_names` also finds "In re X" / "Ex parte X", and names are compared on their first
   word AFTER that prefix (otherwise any "In re" case would vouch for any other "In re" name). Tests:
   invented names removed, a real "In re" name written in the passage kept, an "In re" case not vouching
   for another one.
4. **A wrong number written as words got through.** Check 5 only reads digits: with a passage saying
   "a vote of 6 to 3", the sentence "The Court affirmed by a vote of five to four" was kept. Same attack
   script. Fix: check 5 also reads number words from "two" to "ninety-nine", in the sentence and in the
   passage ("six to three" still matches "6 to 3"). "one" is left out on purpose: it is usually a pronoun
   ("no one can miss") and counting it would remove correct sentences. Tests for both directions.
   For both fixes we also broke the new code on purpose: two breaks were first not caught, so two more
   tests were added; now all five are caught.
5. **Real citations counted as fabrications.** CourtListener has no citation for most decisions from
   2020 on (SPEC section 2). When a retrieved passage itself prints such a citation ("Dobbs, 597 U.S.
   215", "144 S. Ct. 2244") and the model repeats it, check 3 (guide code) labelled it "FABRICATED".
   The sentence must still be removed (SPEC rule 3: every citation shown must be in the table), but the
   label was wrong and would have inflated "fabrications caught by the verifier" in the Week 8 report.
   How we caught it: an attack with a real 2022 citation printed in the passage. Decision (Edwin):
   remove, but relabel. Fix: "citation not in the citation table (written in the passage)", not counted
   by `count_fabrications`; a citation missing from the table AND absent from the passage is still
   FABRICATED (an existing test fails if the relabel is made too broad).

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
9. **AI mistake: a combined text and its separate opinions were both kept.** The loader's copy check
   (entry 4 of 2026-10-23, 5-word overlap >= 60%) compared whole opinions, so a majority opinion stored
   alone and the same majority inside a combined text (majority + dissents) did not look like copies.
   How we caught it: writing questions on Citizens United and Heller, find_quote printed every sentence
   twice in one decision; a count found 366 of 2,421 decisions affected. Fix: drop an opinion that is
   at least 80% contained in another one of the same decision, keeping the separate opinions when they
   cover the combined text (tests/test_ingest_groups.py).

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

## 2026-10-29 — Getting ready for Week 8: the model's rate limit (Edwin)

1. **The guide's evaluation would have produced a run full of ERRORs.** `llm.py` and `evaluate.py` (built by
   Claude from the guide) send every question straight after the previous one, and `llm.py` does not retry
   (SR4). Groq's free tier for openai/gpt-oss-120b allows 8,000 tokens per minute (read from the reply
   headers), and we measured 4,400-5,200 tokens for one real question (8 passages + answer) and about 750
   for a judge call. How we caught it: Joe saw "service unavailable" after a few questions; we measured the
   tokens and the third call in a row was refused (429, "tokens per minute (TPM): Limit 8000").
   Fix: `llm.py` turns the refusal into ModelError("rate limit reached, retry after X s") using Groq's
   retry-after header (the website still shows ERROR at once: SR4 unchanged); the evaluation only
   (`answer_with_retry`, `judge_with_retry`) waits that time and tries again, up to 6 times; other errors
   are not retried. Tests for each part. Live check: 4 real questions back to back, 5 waits of 4-35 s,
   0 ERRORs, about 35 s per question (a full run of 80+ questions: about 50 minutes).

## 2026-11-06 — Login security for the React front end (Joe, step 5.6)

**Asked:** check the instructor's request (React, login for everyone, chat page) against our
requirements, then add roles user/admin, CSRF, a login limit and generic login errors to a JSON API.
1. **Guide code told attackers which accounts exist.** Found while checking the request against our
   rules: `check_login` (guide p. 19-21) answered "This account is locked for 15 minutes" only for an
   email that exists, and "Wrong email or password" otherwise. Fix: one message for every failure, and
   an unknown email still costs one bcrypt check (same reply time). The guide's lock-out test looked for
   the word "locked"; it now checks that the right password is refused while locked.
2. **Claude edited a teammate's file.** The first version put the login-limit numbers in
   `app/config.py`. How we caught it: before committing, `git log -- app/config.py` showed only Yasser
   as author (step 1.1 is his). Fix: the numbers are in `app/api.py`; config.py is unchanged.
3. **The login limit per IP would have been shared by everyone online.** The first version of the limit
   used `request.client.host`. Behind Railway's proxy that is the proxy's address, so 10 failed logins
   from anyone would block every visitor. Caught while preparing the Dockerfile for it. Fix: uvicorn
   `--proxy-headers`. Remaining limit (SPEC section 11): a client can add to X-Forwarded-For, so the
   per-IP limit can be dodged; the per-account lock (SR36) cannot.

## 2026-11-06 — React chat page (Joe, step 5.8)

1. **The retrieved passages were hidden.** Claude's first Answer component put the list of retrieved
   passages inside a closed `<details>` menu, so the user saw only "Retrieved passages (1)". The brief
   (section 5) and FR5 ask for the passages shown alongside the answer, as the Jinja page did. How we
   caught it: the screenshot of the browser check, compared with the brief. Fix: the list is always
   shown; only each passage's full text folds, as on the Jinja page.

## 2026-11-06 — React admin pages (Joe, step 5.9)

1. **A test that checked nothing.** The first version of `test_every_admin_route_refuses_visitors` read
   the admin routes from `app.routes`. With FastAPI 0.143, included routers appear there as one
   `_IncludedRouter` entry without a path, so the list was empty and the test passed without checking
   a single route. How we caught it: the extra test `test_there_are_admin_routes` (at least 18 routes)
   failed with 0. Fix: the routes are read from the app's OpenAPI description (20 routes); removing the
   admin check from the router now makes two tests fail.
2. **/app/ADMIN was not protected.** The first server check for the React admin pages compared the path
   with "admin". React Router ignores capitals, so /app/ADMIN showed the admin page frame without the
   server check (the data stayed protected by /api/admin). Caught while reviewing the route before
   writing its test. Fix: the first part of the path is lower-cased; the test tries /app/ADMIN and
   /app//admin/eval.
3. **The build failed.** `useLoad.js` contains JSX (the `Waiting` component), which Vite only accepts in
   `.jsx` files. Caught by `npm run build`. Fix: renamed to `useLoad.jsx`.
4. **Guide code crashed on a missing log row.** Porting the abstention labels showed that the Jinja route
   (guide pp. 56-62) does `q["question"]` when the UPDATE found no row: a 500 for an unknown id with an
   "add as ..." label (reproduced with the test client). The API returns 404, and a test checks it.

## 2026-11-06 — Switch to React at / (Joe, step 5.10)

1. **The React catch-all route hid other routes.** Claude made the React page answer every address
   (`/{path:path}`, so /login and /admin/... work). FastAPI tries routes in the order they were added,
   so any route added after it is never reached. How we caught it: the whole test suite; 5 tests in
   tests/test_api_auth.py failed with 404, because they add their test-only routes after the app is
   built. Fix: the catch-all stays the LAST route in app/main.py (after /api and /health), an unknown
   /api address gets a JSON 404 instead of the page, and the test helper moves its routes in front.
   A new test checks /health, /api/me and an unknown /api address are not the React page; removing the
   /api check makes it fail.

## 2026-11-06 — Research page public again, only the administrator logs in (Joe, step 5.11)

1. **A requirement was changed before the instructor confirmed it.** What we asked: React pages,
   "login screens with proper security" and a chat page (the instructor's notes). What came back: Claude
   listed the contradiction with SR33 (visitor without login) and proposed options. Joe chose "everyone
   logs in" (roles user and administrator), and Claude then built steps 5.6-5.10 on it: a 'user' role,
   /api/ask and /api/passage behind a login, a server-side history per user. What was wrong: SPEC section
   11 itself said the decision was "to be confirmed with the instructor", and we wrote four steps of code
   on it before he answered. How we caught it: Joe asked the instructor, who answered "only admin" and
   "what do the requirements say exactly". Fix (step 5.11): back to SR33 as written. The research routes
   are open to visitors again, /api/history is removed, a migration removes the 'user' accounts, and the
   tests now check the requirement (a visitor asks without an account; no 'user' account can be created).
   All the login security of step 5.6 is kept. Lesson: a requirement change waits for the person who
   owns the requirement, even when it is written down as "to be confirmed".

## 2026-11-06 — Joe's test questions, step 3.1 (Joe)

1. **Questions merged into main without Joe's approval.** What we asked: Claude proposes test questions,
   Joe reads and validates each one (they are graded as his and he must explain them). Joe validated 14
   answerable questions on 14 cases (Obergefell, Kyllo, Jones, Atkins, Roper, Miller, Crawford,
   Boumediene, Snyder, Brown, Hobby Lobby, 303 Creative, Alice, Raich); the decision ids and gold quotes
   were found word for word in the database with scripts.find_case and scripts.find_quote. What came
   back: a second Claude session working on Joe's PC for another step read short replies from Joe
   ("ok", "A") as approval, wrote a different list (7 cases, 2 questions each), pushed it and merged
   it (PR #43). What was wrong: Joe had not seen that list and never said "merge it". How we caught it:
   the branch appeared on GitHub; Joe confirmed he had not approved it. Fix: this branch puts back the
   list Joe validated, with a normal commit (history not rewritten). Lesson: a short "ok" is only an
   approval for the question it answers; Claude sessions on Joe's PC now get a strict, written scope.
2. **An unanswerable question that the corpus can answer.** Claude drafted U009 ("Does Section 230
   protect YouTube when its algorithm recommends terrorist videos?") and checked that the Court never
   decided Section 230. What was wrong: Gonzalez v. Google (2023) says so explicitly, so a correct answer
   ("the Court declined to decide", with a citation) would be counted as wrong, because unanswerable
   questions expect an abstention. How we caught it: Yasser's review of main before the eval-v1 tag.
   Fix: U009 is now about Uber drivers' employee status; 'Uber' appears once in passing, 'rideshare' 0.

## 2026-11-06 — Week 10: the embedding model (Yasser, steps 10.1-10.2)

1. **A hypothesis that the measurement rejected.** What we asked: Claude read the quote diagnosis
   (scripts/diagnose_quotes.py, TUNE split: in 8 of 12 misses the meaning list ranks the holding
   paragraph below the keyword list) and proposed the week-10 change: replace bge-small-en-v1.5 by the
   larger bge-base-en-v1.5. What came back: the hypothesis and its selection rule (EVALUATION.md,
   committed before measuring), export_for_colab --model, a cache key that names the model, and
   scripts/tune_embeddings.py. What was wrong: the step from "the meaning signal is the weaker one" to
   "a bigger model of the same family will be better on legal holdings" was an assumption, not
   something the diagnosis showed. How we caught it: the rule written first. On 35 TUNE questions
   bge-base gives quote@8 0.286 instead of 0.429 (2 questions gained, 7 lost), recall@5 0.971 instead of
   1.0 and MRR@10 0.905 instead of 0.929, so bge-small stays. Because the rule was committed before the
   run, the result could not be argued away afterwards. Lesson: a diagnosis says where the problem is,
   not which fix works; only the before/after run decides.

## 2026-11-06 — Limit of questions per IP address (Joe, step 5.12)

1. **Tests that shared a counter.** What we asked: a limit of 10 questions per minute per IP address on
   /api/ask (Yasser's request), with tests written from the expected behaviour before the code. What
   came back: tests/test_ask_rate_limit.py (written first; 3 of 4 failed until the code existed) and the
   limit in app/api.py. What was wrong: the counter of questions lives in memory for the whole test run,
   and the fixture of the research tests did not empty it. All tests passed, but the 13 research tests
   and the 4 new ones all ask from the same test address, so a test could pass or fail depending on how
   many questions the tests before it had asked. How we caught it: reading the fixture after the first
   green run, next to the login limit, which the fixture already empties. Fix: the fixture empties
   ASKED_BY_IP too. We also broke the code on purpose: without the limit 3 tests fail; checking the
   limit before SR3 makes the "too short questions do not count" test fail.

## 2026-11-06 — Metadata in the verifier: decision years and full case names (Edwin)

**Asked:** list every piece of metadata the system has and what uses it (after the instructor asked about
metadata), then fix the two gaps the list showed in verify.py.
1. **Years were checked against the passage text only.** The guide's check 5 (p. 45) looks for every number
   in the cited passage text. The model sees the decision's year in the passage header ("(2024)", from
   date_filed), so a correct "In 2024, the Court held..." was removed whenever the text did not repeat
   2024, and "its 2023 decision" about a 2024 decision passed when 2023 was in the text for another reason
   (attack X021 was caught only because 2019 happens not to be in Shelby County's text). How we caught it:
   the metadata inventory (date_filed was used by the website, never by the verifier). Fix: the year of a
   cited decision counts as being in the passage, and a sentence that dates the decision ("its 2023
   decision", "decided in 2023", "in 2023, the Court held") must give that year, unless it names another
   case. Two tests failed before the fix; breaking each of the three parts on purpose makes one test fail.
2. **Case names were compared on their first word.** The guide's check 4 (p. 45, kept in name_key in Week 7) compared only the
   first word, so "Trump v. Anything" passed as Trump v. United States, and "Applying Trump v. United
   States" was removed. Fix: same_case compares both parties, with generic words ("County", "United
   States", "Inc.") counting only for a party that has nothing else. Measured on our 2,477 case names: a
   name now matches its own decision 2,462 times out of 2,463 (first word: 2,123), and a different
   decision 647 times (first word: 19,388; 390 of the 647 are identical names like "Johnson v. United
   States", which no name check can separate).
3. **Claude's first version of same_case removed 209 real case names.** The case-name regex stops at a
   comma, so "Spokeo, Inc. v. Robins" is read as "Inc. v. Robins", and a first party of only generic words
   never matched. All tests passed. How we caught it: running same_case on every case name in the
   database before committing. Fix: a party of only generic words must be part of the cited party. (The
   old first-word code had the same problem: "inc" is not "spokeo".)
4. **A rule without a test.** Breaking same_case on purpose: removing "same number of parties" made no
   test fail, although "In re Trump" would then match Trump v. United States. Fix: a test for it.

## 2026-11-06 — Metadata search: the case-name filter (Edwin)

**Asked:** the instructor said "use metadata for faster search". Claude measured the search first (0.27 s
per question, the model 1-4 s), proposed searching only the case named in the question, and wrote the
rule in EVALUATION.md before any code or measurement.
1. **A measuring check that would have counted correct behaviour as a failure.** Claude's first
   tune_case_filter.py counted the filter as "switched on for an invented name" whenever any
   must_not_appear string was in the question. X021 ("the 2019 decision in Shelby County v. Holder")
   forbids "2019", which is in the question, so the filter on the real Shelby County would have broken
   rule (3). How we caught it: reading the check against the rule's words before running it. Fix: only a
   case name found in the question that is itself listed in must_not_appear counts.


## 2026-11-06 — Admin pages open on the TUNE split (Joe, asked by Edwin)

1. **Pages that showed the TEST split while we choose thresholds.** What we asked (step 5.9): the
   admin pages in React, doing the same as the guide's Jinja pages. What came back: the same metrics,
   with the guide's default split "test" on the overview, the list of runs, a run, the compare page and
   the threshold preview. What was wrong: EVALUATION.md (and SR29) says the thresholds are chosen on TUNE
   and TEST is reported once at the end; with these defaults, opening the admin pages after a run showed
   TEST numbers, so we could look at TEST while choosing without meaning to. Claude copied the guide's
   default without checking it against our own rule. How we caught it: Edwin, preparing Week 8, saw
   split || "test" in the run page. Fix: one default (DEFAULT_SPLIT = "tune") in app/api_admin.py, the
   React pages say which split they show, TEST is still reachable on the run page; 5 tests written first.

## 2026-11-06 — Week 8: the run report must not show the TEST split (Edwin, step 8.2)

1. **The guide's run_eval.py shows the TEST split before tau is chosen.** The script (guide p. 77, committed
   as is in PR #25) prints the metrics of both splits after every run. EVALUATION.md (written before
   measuring) chooses tau_abstain on the TUNE split without looking at the TEST split, then reports TEST
   once. How we caught it: checking the prerequisites of step 8.2 against the rule, before the first run.
   Fix: a run prints the TUNE split and the tau sweep; the TEST split only with `--test RUN_ID`. The
   guide's script also ran a whole evaluation when the file was imported (code at the top level); found
   when the first test imported it (empty test database, no model call). It now runs from main() only.
   The admin pages (Joe's) still open on the TEST split by default (guide pp. 56-62): written down for Joe.
2. **A test that did not test the risky part.** Claude's first test called report() directly. Breaking
   the code on purpose (printing both splits after a run) made no test fail, because the choice of split
   is made in the main part. Fix: the split choice is in main(), tested with a fake run; three planted
   bugs now each make a test fail.

## 2026-11-06 — Week 8: Groq's daily limit, pause and resume (Edwin, step 8.2)

1. **The rate-limit retry (PR #28) only knew the per-minute limit.** Claude's retry waits and tries
   again up to 6 times, which is right for 8,000 tokens per minute. Groq's free tier also allows only
   200,000 tokens per day (console limits page, checked 2026-11-06), and a full run of the 85 questions
   needs about 450,000-550,000 tokens. After about 40 questions every call would have been refused, saved
   as ERROR, and the run spoiled. How we caught it: checking the daily limit before the first full run (it
   was on the to-do list since PR #28, but the run would have started without it). Fix: llm.py says "per
   day" when the refusal is for a daily limit; the run then pauses (status paused, the refused question is
   not saved) and `run_eval --resume RUN_ID` continues it as the same run, with the settings it started
   with, and refuses if the settings changed in between (the search reads the current settings).
2. **A test that could wait for an hour.** Breaking the code on purpose (removing the judge's pause) made
   the judge test call time.sleep(601) six times for real: the test did not replace sleep. Fix: it does now;
   each of 7 planted bugs makes a test fail within seconds.


## 2026-11-06 — The citation shown in the answer (Joe, asked by Edwin)

1. **The first citation is not always the official one.** What we asked (steps 5.7-5.10): the research
   API and the React chat, showing the same citation as the guide's research page. What came back:
   citation_label in app/api.py with the guide's d.citations[0]. What was wrong: the guide assumes the
   first citation is the U.S. Reports one; in CourtListener it is sometimes another reporter, e.g. Nelson
   v. Adams is shown as "0 Cal. Daily Op. Serv. 3128". How we caught it: Edwin, reading the answers of
   the Week 8 evaluation run. Fix: best_citation picks U.S. Reports, then S. Ct., then L. Ed., otherwise
   the first citation (as before); 5 tests written before the code, including "2008 U.S. LEXIS" not being
   taken for U.S. Reports.

## 2026-11-06 — Fixing the corpus text after Edwin's findings (Yasser)

1. **Two cleaning gaps that our own checks missed.** What we asked earlier (steps 1.8 and 2.1): Claude
   wrote the chunker's opinion-start patterns and the text cleaning. What was wrong: (a) a heading with
   several "with whom" groups ending in "join as to Parts II and III, dissenting." was not recognised, so 65
   passages of 4 combined texts were labelled as the majority; (b) PDF texts had lost the "fi"/"fl" ligatures
   ("frst", "specifc", "fled" for "filed"; 1,865 passages). How we caught it: Edwin's checks on the new dump
   during his week 8 run. Fix (PR #59): the pattern accepts "join(s) [except] as to Parts ...", with a test
   written from his example first; the ligature repair below. Edwin stopped his run at 39/85 so the final
   numbers use the fixed data.
2. **A repair rule that was too loose, twice.** What we asked: put back the lost letters. What came back
   first: insert "i"/"l" after an "f" when the repaired word is common in the corpus, in any opinion with at
   least 3 such words. What was wrong: Yasser's dry run listed "fled -> filed" and "fling -> filing" ("fled" is
   a real word, so a clean opinion about a suspect who fled three times would have been changed) and
   "rife -> rifle", "fred -> fired". Second version: an opinion is broken only if it has more repairable
   words than intact fi/fl words, and forms that are real words need the clean opinions to agree. What was
   wrong: the next dry run kept "specifc" and "defned" as "real words", because partly broken opinions sat
   in the "clean" pool. Third version: only clearly clean opinions (10 intact fi/fl words per repairable one)
   decide what is a real word, and partly broken opinions get only the forms that are never real words.
   How we caught it: reading the dry-run lists, and real sentences for "fled" from the database, before
   anything was written. Lesson: a dry run on the real data is the test that matters for a data fix; each
   rule found there now has its own test (a police-chase opinion, "rife", a partly broken opinion).

## 2026-11-08 — Step 8.3: the false-citation checker gave false alarms (Edwin)

1. **The guide's checker flagged real citations.** check_shown_citations (guide p. 50-51) checks
   `citations[0]` of a decision with `cluster_for`, which keeps the FIRST row of the citation table
   (`LIMIT 1`). How we caught it: scripts/show_citations.py on run 1 flagged A022 (Boumediene v. Bush,
   128 S. Ct. 2229): the citation is real, but Boumediene is stored twice in our data (decisions 145795 and
   145943) and the first row points to the other copy. On all decisions, the shown citation of 88 of 2,006
   decisions would have been flagged (decisions stored twice, two short orders on one page, an odd first
   reporter like "0 Cal. Daily Op. Serv. 3128"). Fix: `clusters_for` returns every row; the checker and the
   verifier's check 3 accept a citation if any of its rows is the right decision; the checker checks the
   citation the page shows (`best_citation`: U.S., then S. Ct., then L. Ed.; Joe's #58 uses the same order).
2. **"FABRICATED" for a real case.** Run 1 removed "The Court overruled Roe v. Wade" (right: rule 4) with
   the label "FABRICATED case name". Roe (1973) is real but outside our corpus; our data can only prove a
   citation invented (the citation table), never a name. Fix: names outside the corpus are labelled "case
   name not in our corpus or the cited passage" and are not counted as fabrications.
3. **A full stop kept in case names.** Writing the Roe test showed that a name ending a sentence was read
   as "Roe v. Wade." with the full stop, so it could not be found word for word in a passage that writes
   "Roe v. Wade,". Fix: the full stop is removed; a test for it.
Measured on the database of 2026-11-05: the shown citation of every decision that has one (2,006) leads back to
its own decision for 2,006 with the fixed checker; the old checker flagged 88 of them, all false alarms.
All fixed before run 2 starts, so run 2 is checked with the fixed checker from its first question.


## 2026-11-08 — Week 8: saving and comparing runs (Edwin, step 8.2)

1. **A run lived only in the database, and a restore erased it.** Restoring Yasser's fixed dump (pg_restore
   --clean) emptied `eval_runs`; run 1 survived only because it had been saved to a file by hand, and run 2
   was then given the id 1 again. Nothing in the guide's evaluation module saves a run to the repository.
   How we caught it: the first query after the restore showed run 2 as run id 1. Fix: `scripts/export_run.py`
   saves a run (results, its settings, the data counts, its TUNE metrics and sweep) in `eval/runs/`, run after
   each resume; `scripts/compare_runs.py` reads a run from a file or the database.
2. **A test that could not see the bug.** We asked Claude for tests of `export_run` before the code. Planting
   bugs on purpose, one was NOT caught: computing the saved metrics with today's settings instead of the
   run's own. The test run's settings were the defaults, the same as the database's, so both gave the same
   numbers. Fix: the test run now has its own thresholds (tau 0.95), and the planted bug fails the test.
3. **Error analysis: another test that could not see a bug.** The first tests for `scripts/error_analysis.py`
   (asked of Claude before the code) had no unanswerable TUNE question, so a planted bug that looked for the
   gold quote on unanswerable questions too (and counted them in quote@8) was not caught. Fix: an unanswerable
   TUNE question in the split test; the planted bug now fails it (6 of 6 other planted bugs were caught).

## 2026-11-08 — Week 8: correct quotes removed by the text matching (Edwin, step 8.2)

1. **The quote check removed quotes that ARE in the passage.** `verify.norm` (guide code, built by Claude in
   4.2) makes the quote and the passage comparable with NFKC and a list of quote marks and dashes. In run 2's
   first 38 questions we looked at every quote removed as "not found" (TUNE): the passages were found again with
   the same search, and the closest text was printed next to each quote. 10 of 15 were in the cited passage:
   the model writes a non-breaking hyphen ("cross‑examination", U+2011), which NFKC turns into U+2010, not
   "-" (3); our text has words broken at a line end, "mar- riage", "consti- tutes" (5, about 4,000 passages);
   page markers "*490" inside a sentence (1, 22,235 passages); a final full stop where the passage has a comma
   (1). The other 5 really left words out. How we caught it: reading why answerable questions were "not
   supported" (error analysis), then the closest-match print. The guide's tests use plain "-" and clean text.
   Not fixed during run 2 (a run must use one verifier); the rule for the fix and its measurement is in
   EVALUATION.md, written before measuring. The broken words and page markers are data, told to Yasser.

## 2026-11-08 — Decisions outside our scope (Yasser, step 1.8)

1. **A first check that flagged the wrong things.** What we asked: find decisions in the corpus that are not
   Supreme Court decisions of 2000-2024. What came back first: a check on the opinion authors (an author who
   is not a justice of the period = suspicious). What was wrong: about 220 hits, almost all false alarms
   (O'Connor read as "Connor", OCR misspellings of names, per curiam opinions with no author). How we caught
   it: reading the hits before removing anything. Second approach, kept: two citation rules (a U.S. Reports
   volume below 528 means before 2000; only lower-court reporters means another court), then every hit
   checked by hand. They found 8 real problems (7 cases of 1884-1928 dated 2005-2010 by CourtListener, 1 Sixth
   Circuit case) and 2 false alarms kept in the corpus: Gobeille and Lockhart (2016), whose S. Ct. citation
   CourtListener stored as "U.S." (REVIEWED_IN_SCOPE in app/scope.py). Removal: dry run, then --apply.
2. **A question explanation written from the wrong date.** What we asked earlier (step 3.1): explanations for
   Yasser's test questions. What was wrong: U006's "why" names "Fisher v. Baker (2010)" among the decisions
   that mention drones; it is a 1906 case that CourtListener dates 2010, one of the 8 above. How we caught
   it: the scope check. Not edited, because eval-v1 is frozen; the question stays unanswerable and its
   expected answer is unchanged (noted in EVALUATION.md).
2. **The quote matching fix, measured (2026-11-09).** We asked Claude for the `verify.norm` change and a script that
   checks run 2's saved sentences again (`scripts/reverify_run.py`), tests first. Three things were wrong on the
   way. (a) The script compared the whole ranked list of 20 decisions with run 2's, which is stricter than the
   rule ("the same 8 passages"). A027 failed rule (1) because two passages at ranks 9-10 have the same score and
   swap from one search to the next. Caught by searching every question 3 times: the 8 passages sent to the model
   are the same for all 85 (only X017 can swap 2 of its 8, an opinion stored twice, and it has no draft). Fix:
   compare the 8 passages and the best score, with a test. (b) Four planted bugs were not caught at first: "..."
   accepted by checking each piece, the old verdict trusted instead of checking again, and a sentence judged two
   different ways reused. Two of the four changed nothing in practice. Fix: a test for each of the other two, and
   the realistic version of the "..." bug, which is caught. (c) Claude's first write-up of the result in
   EVALUATION.md said three questions that should abstain were now answered, and that all three "quote a
   dissent". The adversarial abstention rate it had just printed (0.857 -> 0.810) is one question of 21, not two.
   Caught by listing the status changes: two questions (U022, X009). X002 got a sentence back but stayed "not
   supported". Corrected in the next commit.

## 2026-11-09 — Words broken at a line end and page markers (Yasser, after Edwin's run 2 finding)

1. **A page-marker rule that would have removed parts of legal citations.** What we asked: remove
   CourtListener's star-pagination markers ("authority, *490 however") and join words broken at a line
   end ("mar- riage"), as Edwin found in run 2. What came back: a rule removing any star and page number
   standing alone between spaces, with tests (footnote stars and "Section 1983" kept). What was wrong:
   Yasser's dry run on the real corpus showed "*4" in "1978 U. S. Dist. LEXIS 19296, *4 (SDNY ...)",
   "*2" in "1988 WL 44736, *2" and "*1" in "Id., at *1": pinpoint citations to the page of a LEXIS or
   Westlaw document, which are part of the citation and must stay. How we caught it: reading the examples
   the dry run prints, before anything was written. Fix: a star number after "<number>," or after "at" is
   kept, with a test made from those three real sentences; the dry run now also prints the star numbers
   it keeps, so both sides can be checked. The word repairs in the same dry run (washington, government,
   because, ...) and the pairs it left alone ("pre- and", "two- or") were right.

## 2026-11-09 — Loading saved runs into the online database (Edwin, defence)

1. **Tests that matched the defaults by chance.** We asked Claude for tests of `scripts/import_run.py` before the
   code. Two planted bugs were not caught: importing a run with today's settings instead of its own, and forcing its
   status to "done". The test file used the default settings (tau 0.20 since #75, the same as the database) and the
   status "done", so both bugs gave the right answer. Same lesson as export_run (2026-11-08): test data must differ
   from what the code could take by mistake. Fix: the test run has tau 0.37 and the status "paused" (like run 1's file).

## 2026-11-12 — "13 correct sentences": a quote in the passage is not a correct answer (Edwin)

1. **An overstatement in our own results.** After the quote matching change (2026-11-09), Claude wrote in EVALUATION.md
   and in my report draft that the change "gives back 13 correct sentences". Rule (2) of our quote matching rule only
   checked, by hand, that each of the 13 quotes is really in its cited passage, and they all are. It did not check the
   sentences' conclusions. One is wrong: for A032 ("Can the SEC seek civil penalties for securities fraud in its own
   in-house proceedings?", answer no, SEC v. Jarkesy) the kept sentence says the SEC can, because its passage describes
   what the Dodd-Frank Act allowed before the Court struck it down. At tau 0.20 it is shown as low confidence.
   How we caught it: writing a study document on my own 29 questions, I compared each final answer with the question's
   expected answer. Fix: EVALUATION.md and the report draft now say "13 sentences whose quote is in the passage", and
   A032 is in the error analysis and the limitations. No metric changes (A032 is answerable and answered, no false
   citation). Lesson: our checks prove support and attribution, not that a conclusion is the holding; a hand check must
   say exactly what it checked.

## 2026-11-12 — Admin dashboard and the answer, restyled (Edwin, feature/admin-answer-ui)

We asked Claude to restyle the admin pages and the answer components in the landing page's style, every number from
the existing /api/admin answers, checked in a browser at 1280 and 390 px. Checked with a headless browser (Playwright),
logged in with the local admin account, screenshots of every page at both widths. What was wrong, caught that way:
1. **Pages wider than a phone.** The first version made the phone layout one column of `1fr`; a grid column of `1fr`
   does not shrink below its content (the jobs table), so the 390 px page was 628 px wide. Caught: the browser measured
   the page width; a script listed the elements wider than their box. Fix: `minmax(0, 1fr)` and `min-width: 0`.
2. **Bars on counts.** Before/after bars were drawn for every value between 0 and 1, so counts that happened to be 0 or 1
   ("errors 0", "answered but should abstain 1") got bars. Caught on the Compare screenshot. Fix: bars only for the
   metrics that are shares or rates (RATE_METRICS).
3. **TEST numbers on the TUNE page.** The run page's "wrong outcomes" card counted every question, TEST included, while
   the page said "tune split"; the old page also listed the TEST questions by default. Caught: 12 wrong did not match
   the tune metrics (4 + 1 + 6 = 11). Fix: the list shows the chosen split plus the adversarial questions, the same
   questions as the metrics (SR29: TEST only when asked).
4. **A number cut off and a striped passage**: 17,859,437 did not fit its card; the passage in the drawer had a dark
   background on each line. Both seen on screenshots and fixed.

## 2026-11-13 — Yasser's follow-up pairs F015-F021 (drafted with help, eval/FOLLOWUPS.md)

Yasser asked Claude to draft his 7 follow-up pairs. FOLLOWUPS.md allows help if it is said here; Yasser checks and
approves each pair before the set is tagged followups-v1. What Claude did: built the pairs on Yasser's own eval-v1
questions (A006, A007, A008, A009, A012), one of each of the six kinds (two "explain"); F015 and F016 reuse the gold
decision and gold quote of A008 and A012, already verified by the team for eval-v1. What was wrong or unverified:
1. **An unchecked claim.** The first draft of F020's "why" said "checked: find_case finds nothing", but no check had
   been run (Claude's workspace has no corpus). Caught by Claude before committing; replaced by the command Yasser
   must run.
2. **A quote not verified yet.** F017's gold quote (Justice Sotomayor's dissent in Kennedy v. Bremerton) was written
   from memory; it must be found word for word with check_followups / find_quote before the set is tagged.
Structure checked with scripts/check_followups.py's own check_lines (0 problems); the word-for-word quote check needs
the database and is Yasser's to run.

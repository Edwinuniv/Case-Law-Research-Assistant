# Verdicta — Case-Law Research Assistant (ESIB P4)

Final-year project (also the SE course project). Team: Yasser Hajj Youssef, Edwin Mouawad, Joe Bou Karam.
Supervisor: Georges Salloum. Repo: https://github.com/Edwinuniv/Case-Law-Research-Assistant

## Source documents (in docs/)
- docs/Verdicta_Build_Guide.pdf — THE build guide. Follow it step by step. It is the source of truth for code.
- docs/ESIB-P4-brief.pdf — the official project brief (grading rules, gates, deductions).
- docs/Requirements_Document_P4.docx — our requirements document (FR/NFR/SR IDs). The system is graded against it.
- The guide uses the folder `~/verdicta`. Our repo lives in `~/Case_Law_Research_Assistant`. Use that path instead.

## Fixed decisions
- Python 3.12, FastAPI, PostgreSQL + pgvector (local via docker-compose, online on Railway).
- Data: CourtListener BULK files (not the API). Court: scotus. Dates: 2000-2024.
- Hybrid search (pgvector + BM25, top 20) is the baseline. The reranker is the Week 10 improvement.
- Test questions: 80/20 tune/test split. Results are reported on the test split only.

## Who owns what (guide page numbers)
- Yasser: data and search. Pages 11-18, 22-26, 32-35, 37-42, 79-80.
- Joe: database, website, deployment. Pages 7-10, 19-21, 56-74, 78.
- Edwin (me): AI model and verification. Pages 27-31, 36, 43-55, 75-77.
  - 1.9 citations.py, check_citation.py, find_case.py
  - 1.10 tests/conftest.py, tests/test_citations.py
  - 3.1 test questions (all three write them; agree who commits and tags eval-v1)
  - 4.1-4.5 llm.py, verify.py, pipeline.py, ask.py and their tests
  - 5.1 evaluate.py (+ tests/test_evaluate.py on p.71, agreed with Joe)
  - Week 7 attack the verifier; Week 8 calibration
- Shared: pages 1-6, 80-86.
- Do NOT edit another member's files without saying so. If my code needs a change in theirs, write it down for them.

## How to work on a guide step
1. Read the step's pages in the guide PDF first (use the pages parameter, max 20 pages at a time).
2. Check prerequisites (files or tables the step needs from other members). If missing, stop and tell me.
3. Create files exactly as in the guide. If something must differ (wrong path, outdated library or
   API name, a bug), explain why before changing it, and add an AI_LOG.md entry.
4. Run the commands and compare with the "YOU SHOULD SEE" box.
5. Explain the code in simple words, like the "UNDERSTAND IT" boxes. I must be able to explain
   every line at the defence (brief: code nobody can explain scores zero).
6. Suggest a small commit with a clear message. Do not push without asking me.

## Rules from the brief that matter
- SPEC.md must be committed and tagged before any implementation code.
- AI_LOG.md: for each significant delegation, record what we asked, what came back, what was wrong,
  and how we caught it. Real mistakes only; never invent entries.
- NFR17: tests must be written by the team. Help me write tests from the expected behaviour, but do not
  just generate tests that assert whatever the code already does.
- The evaluation set must be committed early (Week 3, tag eval-v1). Never change existing questions secretly.
- Threshold rule goes in EVALUATION.md BEFORE measuring (Week 8).
- Every number in the report must come from a saved evaluation run.

## Branch and commit rules (IMPORTANT — teacher checks commit history)
- Every feature or guide step gets its own branch. Never work directly on main.
- Branch naming: use the format `feature/<short-name>` or `step/<guide-step-number>`.
  Examples: `feature/citation-checker`, `step/1.9-citations`, `step/4.1-llm`.
- Inside each branch, make multiple small commits as you go — one commit per logical change
  (create file, add function, add test, fix bug). Do NOT batch everything into one commit.
- Space commits out naturally as you work; do not commit everything at the same second.
- When a branch is ready to merge, tell me first. I will say "merge it".
  Before merging, I will check:
  1. Does the branch conflict with main or with a teammate's branch?
  2. Will merging break any file owned by Yasser or Joe?
  3. Are there any open issues to fix first?
  Only merge after I confirm it is safe.
- Merge pull requests with a merge commit (`gh pr merge --merge`). Never squash or rebase: squashing
  turns a branch's small commits into one, and the history is graded (PR #7 was squash-merged by mistake).
- After merging, delete the feature branch and start a new one for the next feature.

## README updates
- Update README.md in the same branch whenever a change affects how someone installs, sets up or
  runs the project: a new or changed command or script, a new `.env` variable, a new dependency in
  requirements.txt, a change to docker-compose, or a new feature a user or admin can use.
- Do NOT touch the README for internal code changes, tests or refactors.
- Put the README change in its own small commit (e.g. "README: how to run check_citation.py").
- Before each merge, check that the README still matches how the project actually runs.
- Progress and status go in SPEC.md section 10 (status table) and the checklist below, not the README.

## Progress tracking (update this section after finishing each guide step)
After each step is done, update the checklist below. Mark done steps with ✓ and add a one-line
note on what was built. If a step is blocked (waiting on a teammate), mark it with ⏳ and say why.

Step numbers and names below match the guide's headings exactly. Status as of 2026-11-08.

### Week 0 — Setup (team; guide pages 7-10)
- [x] 0.1-0.5 Repo skeleton, docker-compose (PostgreSQL + pgvector), requirements, .env.example (Yasser, commit 6c30a9f)
- [x] Edwin's own PC: .venv (Python 3.12.3) + requirements, database container (pgvector 0.8.7), verdicta_test database, .env
- [x] 0.6 SPEC.md + AI_LOG.md committed and tagged spec-v1 (commit 5747c13)

### Week 1 — Data foundation
- [x] 1.1 Settings and the bulk-file reader (Yasser) — merged to main (PR #2)
- [x] 1.2 Check the file names and sizes first (Yasser) — merged
- [x] 1.3 Look inside before trusting the code (Yasser) — merged
- [x] 1.4 Filter dockets and decisions, then count (Yasser) — merged
- [x] 1.5 The opinions file (44.8 GB) (Yasser) — merged
- [x] 1.6 The citation table and the citation map (Yasser) — merged
- [x] 1.7 The database: tables and helpers (Joe owns; Yasser wrote it) — app/db.py as in the guide, merged (PR #6)
- [x] 1.8 Cleaning text, and loading into PostgreSQL (Yasser) — merged (PR #5); out-of-scope removal (PR #67): 8 decisions not SCOTUS 2000-2024 removed, 2,415 decisions, 72,502 chunks, TEST retrieval unchanged
- [x] 1.9 The citation lookup — the gate test (Edwin owns; Yasser wrote it) — reviewed by Edwin, merged (PR #10). Gate run 2026-10-29 on Yasser's dump: all four answers OK with Heller 554 U.S. 570 (the guide's 603 U.S. 593 has no citation in CourtListener: known source limit, SPEC §2)
- [x] 1.10 First tests, and commit (Edwin) — tests/conftest.py, tests/test_citations.py: 5 passed, merged (PR #11)

### Week 2 — Chunks and embeddings (Yasser)
- [x] 2.1 Understand the chunking code (app/chunking.py, created in 1.8) — sections name the opinion; inline opinion starts (PR #33)
- [x] 2.2 Embeddings into pgvector — bge-small, cached blocks, Colab GPU route (PR #16, #30)
- [x] 2.3 Numbers for the justification — SPEC §4 (72,593 chunks of 350 words)

### Week 3 — Test questions and search
- [x] 3.1 Write at least 80 test questions in eval/questions.jsonl (all three; tag eval-v1) — 85 questions (28 each + U022), tag eval-v1 pushed 2026-11-06
- [x] 3.2 Keyword search (BM25) (Yasser) — app/bm25.py, Snowball stemming, cached (PR #20, #30)
- [x] 3.3 Hybrid search and the reranker (Yasser) — weighted RRF; reranker measured, no gain, off (PR #30)
- [x] 3.4 Measure the search: the baseline (Yasser) — eval-v1: TEST recall@5 1.0, MRR@10 0.938, quote@8 0.25 (branch step/3.4-eval-v1-baseline)
- [x] 3.5 Compare chunk sizes, then commit (Yasser) — 350 words kept (PR #30)

### Week 4 — Model call and verifier (Edwin)
- [x] 4.1 The model call — merged (PR #7, history restored in #8): app/llm.py, live check with Groq OK (SUPPORTED, NOT_SUPPORTED, judge; 1-2 s). Note for 4.2: model puts ["P1"] in sentence text, check 5 would read it as the number 1
- [x] 4.2 The verifier: the heart of the project — merged (PR #12): app/verify.py, five checks tried one by one; fix: ["P1"] markers removed before the checks (AI_LOG, SPEC §11)
- [x] 4.3 The pipeline — merged (PR #13): app/pipeline.py as in the guide, every path checked with a fake searcher + fake model ⏳ re-check with Yasser's real Searcher (3.3) when app/search.py lands
- [x] 4.4 Try it — branch step/4.4-ask-run-eval: scripts/ask.py run on real data. Chevron question: NOT_SUPPORTED (search gives dissent/concurrence, not the majority; Yasser's side). Loper Bright wording: LOW_CONFIDENCE, quotes verified. Week 7 lead: a concurrence quoted as "The Court rejected..." passes the verifier
- [x] 4.5 Tests (with a fake model) — merged (PR #14): test_verify, test_pipeline, test_llm from the guide + 3 tests for gaps found by breaking the code on purpose; 32 passed

### Week 5 — Evaluation module and website
- [x] 5.1 Evaluation module (Edwin; tests/test_evaluate.py agreed with Joe) — merged (PR #15): app/evaluate.py as in the guide, each part tried on the test database; tests from the guide + 7 for gaps found by breaking the code on purpose; 43 passed ⏳ real run needs the questions (3.1) and the data
- [x] 5.2 The web application (Joe) — app/main.py as in the guide, merged (PR #19): home, /health, admin login and the 9 admin pages checked; 53 tests pass ⏳ real questions need the data loaded and a Groq key (5.5)
- [x] 5.3 Public templates (Joe) — base, ask, passage_panel, passage as in the guide, merged (PR #9)
- [x] 5.4 Admin templates (Joe) — 13 pages in app/templates/admin/ as in the guide, merged (PR #17)
- [x] 5.5 Run it, test it, commit (Joe) — run with Yasser's dump: research page, citation panel, 9 admin pages OK; tests/test_admin.py from the guide + 2 tests for a gap found by breaking the code (AI_LOG) (8 passed, whole suite 66 passed) ⏳ Chevron question gives Not supported (search not finding the majority passage, told Yasser)

- [x] 5.6 Login security for the API (Joe) — branch step/5.6-login-security: roles user/admin (db.py + migration), one login message, app/api.py (login, logout, /api/me, CSRF, limit per IP, role checks); 21 new tests; instructor's React/chat request in SPEC §11 ⏳ 5.7-5.10 (API research, React chat, React admin, switch)
- [x] 5.7 Research API for the chat (Joe) — branch step/5.7-api-research: /api/ask, /api/passage, /api/history (own questions only), query_log.user_id + answer as shown; 15 new tests ⏳ 5.8 React chat page
- [x] 5.8 React login and chat pages (Joe) — branch step/5.8-react-chat: frontend/ (Vite + React Router), served at /app, Dockerfile Node stage; checked in a browser with a test database ⏳ run with Joe's real database; 5.9 admin pages
- [x] 5.9 React admin pages (Joe) — branch step/5.9-react-admin: app/api_admin.py (20 routes, admin role + CSRF on the router), 9 admin pages in frontend/src/admin, /app/admin refused by the server; 14 new tests ⏳ 5.10 switch (React at / and /admin, remove Jinja)
- [x] 5.10 Switch to React (Joe) — branch step/5.10-switch-to-react: React at / and /admin, Jinja templates and routes removed (main.py 405 → 73 lines), tests/test_admin.py rewritten for /api/login; 143 tests pass ⏳ run with Joe's new database
- [x] 5.11 Public research page (Joe) — branch step/5.11-public-research: instructor's answer (only the admin logs in, one question per message): /api/ask and /api/passage open to visitors, /api/history removed (list kept in the page), admin role only + migration removing 'user' accounts; 141 tests pass ⏳ run with Joe's new database
- [x] 5.12 Limit of questions per IP (Joe) — branch step/5.12-ask-rate-limit: /api/ask accepts 10 questions per minute per IP address, then HTTP 429 with the wait time, before the model is called (Yasser's request: the page is public, protect the Groq credit); 4 new tests, 146 pass
- [x] Admin pages on TUNE (Joe, Edwin's request) — branch feature/admin-tune-default: overview, runs, a run, compare and threshold preview show the TUNE split (EVALUATION.md: choose on TUNE, report TEST once); TEST still on the run page; 5 new tests
- [x] Citation shown in the answer (Joe, Edwin's request) — branch feature/citation-label-us-first: citation_label uses best_citation (app/citations.py, shared with Edwin's checker), which prefers U.S. Reports, then S. Ct., then L. Ed., else the first citation (Nelson v. Adams showed "0 Cal. Daily Op. Serv. 3128"); 5 new tests

### Week 6 — Deployment (Joe)
- [x] 6.1 Deployment files — Dockerfile and .dockerignore; build step downloads the embedding model into data/models like app/embeddings.py (AI_LOG) ⏳ image built for real on Railway (6.2)
- [x] 6.2 Create the database and the website on Railway — 2026-11-06: pgvector (pg18) + web service from main, variables, domain case-law-research-assistant-production.up.railway.app; /health OK
- [x] 6.3 Fill the online database with the seed script — 2026-11-09: pg_restore of the Nov 6 dump (Hobby plan, volume enlarged), remove_out_of_scope --apply (8 decisions), seed --admin; index_loaded true, case_filter True, tau_abstain 0.20; live question answered by search + model + verifier ⏳ rotate the database password, switch the site to DATABASE_URL_PRIVATE

### Week 7 — Attack the verifier (Edwin)
- [x] 7.1 Attack, test, fix, log — merged (PR #26): 13 attacks from the guide's list run with the real citation index; 3 got through and are fixed with tests + AI_LOG: concurrence/dissent as the Court (check 6), "In re"/"Ex parte" names (check 4), numbers in words (check 5). Also: real 2020+ citations copied from the passage are removed but no longer counted as FABRICATED (Edwin's decision). AI_LOG Week 7 entries 1-5
- [x] 4.6 Metadata search (Edwin, not a guide step; instructor: "use metadata for faster search") — merged (PR #50, Yasser's decision_ids PR #52): a case named in the question limits the search to its decision. Measured on TUNE (eval/runs/case_filter_2026-11-06T21-00-05.json): quote@8 and MRR@10 unchanged, search 179 -> 29 ms on the 8 questions that name a case; on by the rule, for speed only; DEFAULT_SETTINGS case_filter True (Yasser, branch step/4.6-case-filter-on) ⏳ admin checkbox (Joe)
- [x] 7.2 Metadata in the verifier (Edwin, not a guide step; after the instructor's question) — branch step/7.2-metadata-checks: check 5 accepts the cited decision's year (date_filed) and rejects a wrong year for it; check 4 compares both parties (same_case) instead of the first word; 8 new tests, checked on the 2,477 real case names (AI_LOG) ⏳ instructor's exact words for the rest of the metadata proposals

### Week 8 — Calibration (Edwin)
- [x] 8.1 Write the rule before measuring — branch step/8.1-threshold-rule: EVALUATION.md, committed 2026-10-26 before any evaluation run
- [x] 8.2 Run the full evaluation — scripts/run_eval.py ready (PR #25); rate-limit retry merged (PR #28: 4 real questions, 0 ERRORs, ~35 s each); eval-v1 tagged by Joe (85 questions, 4d9e179); branch step/8.2-tune-only-report: a run prints TUNE + tau sweep, TEST only with --test RUN_ID (AI_LOG) pause at Groq's daily limit (200,000 tokens/day) and `--resume RUN_ID` (AI_LOG). New dump restored (2,423 decisions, 72,593 passages), 85 questions seeded, check_questions 0 problems Run 1: 39/85 then paused at the daily limit; not resumed (option B): kept as the 'before text fixes' run (eval/runs/eval_run1_before_text_fixes_2026-11-06.json) ⏳ Yasser's step/2.2-text-fixes merged and applied, check_questions, then run 2 from the start (about 3 days) Run 2 started 2026-11-08 (database run id 1: the restore empties eval_runs) on Yasser's dump of 2026-11-06 21:20 UTC with the text fixes, minus the 8 out-of-scope decisions (his step/1.8 script, dry run then --apply): 2,415 decisions, 72,502 passages, check_questions 0 problems; resume with `--resume 1` after each daily pause; day 1: 38/85, 0 errors, saved in eval/runs/eval_run2.json (`export_run` after each resume); compare_runs (PR #63); threshold rule clarified before the sweep; drafts of the final EVALUATION section and docs/report_sections_edwin.md (PR #64); scripts/error_analysis.py and docs/requirements_edwin.md (PR #65); 10 of 15 removed quotes were in the passage (hyphens, broken words, page markers): rule written before measuring (branch step/8.2-quote-matching-rule) run 2 finished 2026-11-09 (85/85, 0 errors; PR #70); quote matching fixed and run 2 rechecked: all 4 conditions hold, kept (eval/runs/eval_run2_reverified.json; branch step/8.2-quote-matching) (PR #73); tau_abstain 0.20 chosen on TUNE by the rule, TEST reported once: precision 1.0, recall 0.8, 0 false citations of 23 (eval/runs/test_split_run2_reverified_2026-11-09.txt; branch step/8.2-tau-and-test) ⏳ default 0.20 in config.py (Yasser) and online settings (Joe)
- [x] 8.3 False citations = 0 — run 2 (rechecked), tau 0.20: 0 of 56 citations shown on TUNE + adversarial, 0 of 23 on TEST, 0 FABRICATED in 85 questions (eval/runs/citations_*_2026-11-09.txt; EVALUATION.md section 4); before that: — branch step/8.3-citation-report: scripts/show_citations.py (shown, removed, quotes by decision; TUNE by default), 4 tests. Found on run 1 so far: the checker flags real rendered citations of 88/2,006 decisions (duplicate decisions, one citation for two orders, odd first citation; cluster_for LIMIT 1) Fixed BEFORE run 2 (branch step/8.3-checker-fixes): checker checks the shown citation (best_citation) and any citation-table row (clusters_for); check 3 too; names outside the corpus no longer FABRICATED; full stop in case names; 9 new tests (AI_LOG) ⏳ database tests + recount of the 88 when Docker is on; Joe: import best_citation from app.citations

### Defence prep (Edwin)
- [x] FABRICATED citation demo — scripts/demo_fabricated.py: run 2 has no fabricated citation to show (the model cites passages, our code renders citations), so a lying draft for a real question goes through the real verifier and citation table; no model call; 3 tests (PR #77)
- [x] Demo question list — docs/defence_demo.md: one question per part of the guide's 15-minute plan, with a backup, from run 2 at tau 0.20 ⏳ try each on the live site the day before; evaluation runs missing from the online database: scripts/import_run.py (branch feature/import-run), Joe runs it on Railway

### Interface (Edwin, with Joe and Yasser)
- [x] Admin pages and the answer ("chatbot") restyled like the landing page — branch feature/admin-answer-ui (on top of #84): admin.css + charts.jsx (SVG ring, dial, stacked bars, lines; every number from /api/admin), the 11 admin pages, Answer/Working/PassagePanel with answer.css (research.css untouched); checked with a headless browser at 1280 and 390 px ⏳ Joe's PasswordRules in the Users form when it lands; merge after #84

- [x] Welcome message (Edwin) — branch feature/welcome-message (on top of #86): "hello / what can you do" gets status WELCOME and our fixed text (no search, no model); 13 tests, none of the 85 questions is a greeting ⏳ follow-up questions: the instructor said no on 2026-11-06; asking him again before building anything

- [x] Information pages (Edwin) — branch feature/site-pages: /privacy, /terms, /sources, /contact in the footer; contact form (app/api_site.py, table contact_messages, 3 per address in 10 minutes) and admin Messages page; 12 tests ⏳ CONTACT_EMAIL to choose; the final logo replaces assets/logo-mark.svg, logo.svg, favicon.svg

- [x] Chat in the terminal + follow-ups parts 2-3 (Edwin) — merged (PR #100): scripts/chat.py, pipeline.turn_of; a follow-up searches the chat's cited case (or a case named, or everything), every follow-up message asks the model to check the user's statement, "thanks"/"ok" in a chat gets one line (EVALUATION.md rule first); part 3 after Groq 413s on a live chat: earlier turns send only their cited passages, oldest turns dropped above 6,000 estimated tokens; 22 tests, 20 planted bugs caught. Scripted Counterman chat (eval/chats): before 3 of 6 ERROR + drift to other cases, after 0 ERROR, all passages Counterman, wrong summary corrected, "thanks" one line ⏳ followups-v1 pairs to measure; Joe connects the website chat with turn_of
- [x] Saved demo answers (meeting of 13 Nov) — branch feature/demo-answers: demo_answers table, app/demo.py, scripts/make_demo_answers.py; /api/ask returns the saved answer of an example question (no model call, logged, not counted in the limit); page label "Saved answer · checked on <date>"; 8 tests (one: saved answers in the user log), 6 planted bugs caught; merged with Yasser's logs (PR #102) ⏳ make the answers when the v2 run pauses (shared Groq budget); then again after v2 is chosen or not

### Access and admin pages (Joe; docs/PLAN_2026-11-13.md parts 1-2, after the meeting of 13 Nov)
- [x] Visitor = one question (Joe) — branch step/1-visitor-one-question: one question per browser session without an account (counted in the session; SR3 refusals, greetings, ERRORs and example questions do not count), then 403 and "Log in or sign up" on the page; /api/me free_questions_left; 11 tests (Joe's table) (PR #105)
- [x] Free and paid accounts (Joe) — branch step/2-plans-daily-limits: users.plan (free/paid), 10 or 100 questions a day since midnight Beirut (settings free_daily_questions, paid_daily_questions), 429 before the model + refused in the user log, POST /api/admin/users/{id}/plan (plan_change), POST /api/admin/limits, plan on the research page; 14 tests (Joe's table) ⏳ admin buttons (step 4); Edwin: a line on the Terms page (no real payment); saved chats, admin user pages

### Week 9 — Usability test
- [ ] 9.1 Give the admin login to a classmate who has never seen Verdicta

### Week 10 — Improvement (reranker)
- [x] 10.1 Hypothesis first, committed (Yasser) — merged (PR #35): diagnose_quotes (why gold quotes miss the 8 passages) and the embedding-model rule in EVALUATION.md before measuring
- [x] 10.2 Measure before and after (Yasser) — branch step/10.2-embedding-model: tune_embeddings on 35 TUNE questions; bge-base worse (quote@8 0.286 vs 0.429), bge-small kept, reported as a measured regression

## Style
- Explain things in simple, plain English (I am a student).
- Keep commits small and frequent; the commit history is graded.

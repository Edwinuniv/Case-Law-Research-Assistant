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

Step numbers and names below match the guide's headings exactly. Status as of 2026-10-23.

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
- [ ] 1.7 The database: tables and helpers (Joe owns; Yasser wrote it) — branch step/1.7-db, Joe to review
- [ ] 1.8 Cleaning text, and loading into PostgreSQL (Yasser) — branch step/1.8-ingest, needs 1.7 merged
- [x] 1.9 The citation lookup — the gate test (Edwin owns; Yasser wrote it) — reviewed by Edwin, merged (PR #10) ⏳ gate run needs the 1.8 data loaded
- [x] 1.10 First tests, and commit (Edwin) — tests/conftest.py, tests/test_citations.py: 5 passed, merged (PR #11)

### Week 2 — Chunks and embeddings (Yasser)
- [ ] 2.1 Understand the chunking code (app/chunking.py, created in 1.8)
- [ ] 2.2 Embeddings into pgvector
- [ ] 2.3 Numbers for the justification

### Week 3 — Test questions and search
- [ ] 3.1 Write at least 80 test questions in eval/questions.jsonl (all three; tag eval-v1)
- [ ] 3.2 Keyword search (BM25) (Yasser)
- [ ] 3.3 Hybrid search and the reranker (Yasser)
- [ ] 3.4 Measure the search: the baseline (Yasser)
- [ ] 3.5 Compare chunk sizes, then commit (Yasser)

### Week 4 — Model call and verifier (Edwin)
- [x] 4.1 The model call — merged (PR #7, history restored in #8): app/llm.py, live check with Groq OK (SUPPORTED, NOT_SUPPORTED, judge; 1-2 s). Note for 4.2: model puts ["P1"] in sentence text, check 5 would read it as the number 1
- [x] 4.2 The verifier: the heart of the project — merged (PR #12): app/verify.py, five checks tried one by one; fix: ["P1"] markers removed before the checks (AI_LOG, SPEC §11)
- [ ] 4.3 The pipeline
- [ ] 4.4 Try it
- [ ] 4.5 Tests (with a fake model)

### Week 5 — Evaluation module and website
- [ ] 5.1 Evaluation module (Edwin; tests/test_evaluate.py agreed with Joe)
- [ ] 5.2 The web application (Joe)
- [ ] 5.3 Public templates (Joe)
- [ ] 5.4 Admin templates (Joe)
- [ ] 5.5 Run it, test it, commit (Joe)

### Week 6 — Deployment (Joe)
- [ ] 6.1 Deployment files
- [ ] 6.2 Create the database and the website on Railway
- [ ] 6.3 Fill the online database with the seed script

### Week 7 — Attack the verifier (Edwin)
- [ ] 7.1 Attack, test, fix, log

### Week 8 — Calibration (Edwin)
- [ ] 8.1 Write the rule before measuring
- [ ] 8.2 Run the full evaluation
- [ ] 8.3 False citations = 0

### Week 9 — Usability test
- [ ] 9.1 Give the admin login to a classmate who has never seen Verdicta

### Week 10 — Improvement (reranker)
- [ ] 10.1 Hypothesis first, committed
- [ ] 10.2 Measure before and after

## Style
- Explain things in simple, plain English (I am a student).
- Keep commits small and frequent; the commit history is graded.

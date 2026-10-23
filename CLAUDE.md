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
- After merging, delete the feature branch and start a new one for the next feature.

## Progress tracking (update this section after finishing each guide step)
After each step is done, update the checklist below. Mark done steps with ✓ and add a one-line
note on what was built. If a step is blocked (waiting on a teammate), mark it with ⏳ and say why.

### Setup (Week 0) — Joe's section
- [ ] 0.1 WSL tools installed (git, python3.12, docker, docker-compose)
- [ ] 0.2 PostgreSQL + pgvector running in Docker
- [ ] 0.3 Python virtual environment created
- [ ] 0.4 .env file created (never committed)
- [ ] 0.5 Repo cloned and docs/ in place
- [ ] 0.6 SPEC.md + AI_LOG.md committed and tagged spec-v1 ← must happen before ANY code

### Week 1 — Data foundation (Yasser + Joe + Edwin)
- [ ] 1.1 CourtListener bulk files downloaded (Yasser)
- [ ] 1.2 courts.py — filter to scotus (Yasser)
- [ ] 1.3 dockets.py (Yasser)
- [ ] 1.4 clusters.py (Yasser)
- [ ] 1.5 opinions.py (Yasser)
- [ ] 1.6 citation_map.py (Yasser)
- [ ] 1.7 db.py — database schema (Joe)
- [ ] 1.8 ingest.py — load into PostgreSQL (Yasser)
- [ ] 1.9 citations.py, check_citation.py, find_case.py (Edwin) ⏳ needs 1.6 + 1.7
- [ ] 1.10 tests/conftest.py, tests/test_citations.py (Edwin) ⏳ needs 1.9

### Week 2 — Search (Yasser)
- [ ] 2.1 embed.py
- [ ] 2.2 search.py (hybrid BM25 + pgvector)
- [ ] 2.3 tests/test_search.py

### Week 3 — Evaluation set (all three)
- [ ] 3.1 eval/questions.jsonl — 80+ questions committed and tagged eval-v1

### Week 4 — LLM + pipeline (Edwin)
- [ ] 4.1 llm.py
- [ ] 4.2 verify.py
- [ ] 4.3 pipeline.py
- [ ] 4.4 ask.py
- [ ] 4.5 tests for 4.1-4.4

### Week 5 — Evaluate (Edwin)
- [ ] 5.1 evaluate.py + tests/test_evaluate.py

### Week 6 — Website + API (Joe)
- [ ] 6.x FastAPI routes, frontend, authentication

### Week 7 — Attack the verifier (Edwin)
- [ ] 7.x Adversarial tests against verify.py

### Week 8 — Calibration (Edwin)
- [ ] 8.x Set thresholds; write them to EVALUATION.md BEFORE measuring

### Week 10 — Reranker improvement
- [ ] 10.x Add cross-encoder reranker (ms-marco-MiniLM-L-6-v2)

### Deployment
- [ ] Deploy to Railway (Joe)

## Style
- Explain things in simple, plain English (I am a student).
- Keep commits small and frequent; the commit history is graded.

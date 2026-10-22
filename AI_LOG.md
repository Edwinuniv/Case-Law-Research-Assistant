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

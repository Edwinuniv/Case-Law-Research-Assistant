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

## 2026-10-23 — Building the search index (Yasser)

1. **AI mistake: time estimate 10-40 minutes; measured about 14 hours.** Our 4,765 opinions give
   104,904 passages of up to 350 words. How we caught it: progress read from the running process with
   py-spy (4,608 passages after about 37 minutes, 4 cores busy). Two problems in the AI's code: batches
   were in random order, so each batch of 32 was padded to its longest passage; and the embeddings were
   only saved at the very end, so any interruption lost everything. Fix: passages sorted by length and
   saved every 2,048 (data/work/embedding_cache), so a stopped run resumes; progress printed at once.
2. **AI mistake: progress hidden in the log.** Under nohup, Python wrote the progress lines only at the end
   (output buffering). Fix: print with flush.


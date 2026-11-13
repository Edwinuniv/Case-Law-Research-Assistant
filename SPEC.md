# SPEC — Verdicta, case-law research assistant (ESIB P4)

Team: Yasser Hajj Youssef, Edwin Mouawad, Joe Bou Karam
Supervisor: Georges Salloum
Repository: https://github.com/Edwinuniv/Case-Law-Research-Assistant
Full requirements: docs/Requirements_Document_P4.docx (Delivery 1, due 24/10/2026).
Requirement IDs (FR, SR, NFR) below refer to that document.

## 1. Goal

A website that answers legal research questions using U.S. Supreme Court opinions only,
links every sentence to the exact passage behind it, never shows an unverified citation,
and says "Not supported by the retrieved opinions" when the opinions do not answer (O1-O4).

## 2. Corpus (FR29, appendix A; scope fixed at the week 1 gate)

- Court: Supreme Court of the United States (CourtListener id: scotus).
- Dates: opinions filed 2000-01-01 to 2024-12-31.
- Source: CourtListener bulk data, release 2024-12-31 (C2, C4): courts, dockets,
  opinion-clusters, opinions, citations, citation-map. No API, no token.
- The 44.8 GB opinions file is streamed (or downloaded with resume), filtered, and not kept (NFR12).
- Bulk file sizes (measured 2026-10-22 with curl -I): courts 80,671 B; dockets 4,447,391,506 B;
  opinion-clusters 2,326,606,563 B; opinions 44,759,737,019 B; citations 128,900,819 B;
  citation-map 217,012,151 B (about 52 GB in total).
- Download: our connection measured about 0.7 MB/s (also with 8 parallel connections, aria2),
  so the files are downloaded once with resume (aria2c -c), about 21 hours in total, then filtered;
  the opinions file is deleted after filtering (NFR12).
- Counts (week 1 gate, measured 2026-10-23): dockets 67,888,394 read -> 499,717 scotus;
  clusters 9,833,660 read -> 188,045 scotus 2000-2024 -> 2,935 kept (rule below) = 2,477 decisions
  (1,581 in SCDB; 309 merged from copies; 82-126 per year); opinions 10,541,500 read -> 190,739 of
  scotus clusters (0 unreadable) -> 5,598 of kept decisions; citation table rows 17,859,437;
  citation-map 30,949,033 rows read -> 58,958 citations made by our opinions;
  loaded (step 1.8, 2026-10-23): 2,477 decisions (0 without text), 4,765 opinions (795 copies of an
  opinion skipped, 38 without text), 17,859,437 citations, 58,958 citation-map rows; chunks [ ] (week 2).
- Real decisions only (step 1.4b): CourtListener stores many one-line orders ("certiorari denied")
  as clusters (up to 22,544 in one year, while the Court decides about 70-90 cases a year).
  Rule, the same for every year: a decision (its clusters with the same docket and date) is kept if
  it has a Supreme Court Database id (scdb_id), or if its longest opinion has >= 300 words.
  Why 300: CourtListener links SCDB only for 2000-2019 (1,581 decisions). On those years, >= 300 words
  keeps 98% of the SCDB decisions; lowering it to 100 adds about 600 one-paragraph orders. The long
  texts outside SCDB are real opinions we want: copies of SCDB cases under another docket
  (e.g. Nevada v. Hibbs, 2003), dissents from a denial (e.g. Woodward v. Alabama, 2013) and
  in-chambers opinions (e.g. Philip Morris v. Scott, 2010).
- Copies merged (step 1.4c): one decision is sometimes stored as several clusters under different
  dockets or names (e.g. Miller v. Alabama, 2012: 3 clusters; "EPA" / "E.P.A. v. EME Homer", 2014).
  Clusters with the same date and the same docket, or the same case name (letters and digits), or the
  same official citation (U.S., S. Ct., L. Ed. 2d) form one decision (field decision_group).
  Copies with different dates (step 1.8, 2026-10-29): CourtListener also stores some decisions twice a
  few days or weeks apart (slip opinion and later version; e.g. Bruen 2022: 6480696 and 7686272, about
  60 same-name pairs, mostly 2020-2022). After loading, decisions with the same case name, dates at
  most 60 days apart and opinion texts at least 80% identical (5-word sequences) are merged into the
  copy with the most text; the others' ids become aliases. Same-name decisions with different texts
  stay apart (Bush v. Gore: stay of Dec 9 and decision of Dec 12, 2000; two Williams v. Taylor cases
  of 2000-04-18). Measured on 2026-11-05: 54 copies removed.
  Combined texts (2026-10-31): CourtListener also stores some decisions both as one combined text
  (majority + concurrences + dissents) and as separate opinions (366 of 2,421 decisions, e.g. Heller,
  Citizens United), so every passage appeared twice (measured on 2026-11-05: 1,859 opinion copies
  skipped at loading, 3,647 opinions and 18.9 million words kept, against 27.5 million before). An
  opinion whose text is at least 80% contained
  in another of the same decision is dropped: the separate opinions are kept if together they cover
  the combined text (their labels come from CourtListener), otherwise the combined text is kept.
  Safety rules: a citation is used only if all kept clusters carrying it have the same date
  (CourtListener gives new decisions placeholders such as "538 U.S. 1", shared by different cases),
  and two groups with different SCDB ids are never merged.
  Measured: 2,849 decisions by docket alone -> 2,477 after merging copies; 35 placeholder citations
  ignored; 8 merges refused because the SCDB ids differ.
- Known limit of the source: CourtListener has no official citation (U.S., S. Ct., L. Ed. 2d) for most
  decisions from 2020 on (measured after loading: decisions without any citation 2020: 42 of 126,
  2021: 123/124, 2022: 112/112, 2023: 35/94, 2024: 86/87; 2000-2019: 0-20 per year). Checked on
  2026-10-23 that the newest citations release (2026-09-30) does not fill the gap either (no U.S.
  citation in volumes 597, 602, 603; none for Dobbs or Loper Bright). Such decisions are shown and
  cited by docket number and date, the usual form before a U.S. Reports page exists:
  "Dobbs v. Jackson Women's Health Organization, No. 19-1392 (U.S. June 24, 2022)". A decision that
  has an official citation is shown with it (U.S. first, then S. Ct., then L. Ed. 2d). Rendered from
  our database (SR21); the citation check must accept this form for these decisions.
- Licence: Public Domain Mark 1.0, stored for every decision and opinion with its load date;
  rows without a licence are rejected (FR30, SR11).
- A newer quarterly release is loaded by changing CL_RELEASE only (NFR13).

## 3. Architecture

PostgreSQL 16 + pgvector, run with Docker: locally the pgvector/pgvector:pg16 image
(docker-compose.yml), online the website is built from the Dockerfile on Railway. The code only
reads DATABASE_URL, so any PostgreSQL 16 with pgvector works. Asked on 2026-10-29, the instructor
said both a direct install and Docker are acceptable and that he prefers Docker (portable, comes
pre-installed); we keep Docker. Tables: decisions, cluster_alias, opinions, chunks (vector(384)),
citations, citation_map, test_questions, query_log, eval_runs, eval_results, users, settings, jobs.

question -> input check, 3-1000 characters (SR3)
-> hybrid search: pgvector cosine + BM25, Reciprocal Rank Fusion, top 20 (SR17)
-> top 8 passages (baseline: fused order; week-10 improvement: reranker, SR18)
   (dense search is exact, no HNSW index: 57 ms for 104,904 chunks measured on 2026-10-26; HNSW took
   3 ms but is approximate and, with its default ef_search=40, returned only 40 of 50 rows, none of
   them the exact top 50. BM25 is a sparse matrix built once and saved in data/work/bm25.*;
   words are stemmed (Snowball English), so "overrule" in a question matches "overruled";
   the fusion has three settings, w_bm25, w_separate (weight of concurring/dissenting passages) and
   fusion_pool, chosen on the tune split by the rule in EVALUATION.md; defaults = plain RRF)
-> cheap gate: best passage similarity < min_retrieval => NOT SUPPORTED, model not called
-> model (30 s limit, one retry on invalid JSON) returns sentences with passage ids P1..P8
   and exact quotes, or NOT_SUPPORTED (SR4, SR19, SR20)
-> verification, 5 checks per sentence; failing sentences removed (SR22-SR25)
-> support score (SR26) -> status (SR27)
-> case names and citations shown to the user are rendered from OUR database (SR21).

Website (since step 5.6, 2026-11-06): FastAPI serves the pages and a JSON API under /api (app/api.py)
for the React front end, which replaced the Jinja pages of the guide in step 5.10 (section 11).
The research routes (/api/ask, /api/passage) are open to visitors (SR33); every /api/admin route
checks the login and the role on the server, reading the account from the database at each request;
every POST needs the session's CSRF token (X-CSRF-Token header). Each question is sent alone to
pipeline.answer (FR1); the page's "My questions" list lives only in the browser page.
Front end (step 5.8): React + Vite in frontend/ (react, react-router-dom; no UI library), built into
frontend/dist and served by FastAPI at / (every address that is not /api or /health gets the same page); the Dockerfile builds it in a first Node stage, so
Railway still runs one service. Pages: chat (research, no login), administrator login and the 9 admin pages under /admin
(step 5.9; admin JSON API in app/api_admin.py, where the router itself requires the admin role and the
CSRF token, so no admin route can be added without them). React only displays: it never decides who
may see what; /admin pages are refused by the server (401 / 403) like every admin route (SR35).

Search filter (step 4.6, for Edwin's case filter): `Searcher.search(question, k, settings, decision_ids)`;
with decision_ids, the pgvector list and the BM25 list only contain passages of those decisions (same
format, score still the cosine similarity); without it the whole corpus is searched as before. The setting
case_filter (off) decides whether the pipeline uses it.

## 4. Chunking strategy (FR31, SR16)

Measured on 2026-10-26 with `python -m scripts.stats` on the loaded corpus: 4,765 opinions,
238,580 paragraphs (median 88 words, 90th percentile 300, longest 24,116 words); paragraphs with at
most 250 / 350 / 400 words: 84.3% / 98.3% / 99.2%. Index built with max 350 words: 104,904 chunks
(median 292 words), 27,500,424 words in total. Since 2026-10-29 (one section per opinion, opinions on a
denial of certiorari labelled): 105,626 chunks. Since 2026-11-05 (no duplicate opinions, opinion starts
found inside PDF-style paragraphs): 2,423 decisions, 3,647 opinions, 72,593 chunks, 18,852,079 words. Since 2026-11-06 (long opinion headings recognised, lost "fi"/"fl" letters repaired in 61 opinions): 72,628 chunks, 18,852,079 words. Since 2026-11-08 (8 decisions that are not Supreme Court decisions of 2000-2024 removed, app/scope.py): 2,415 decisions, 72,502 chunks.

| Rule | Justification |
|---|---|
| Never mix two opinions | A chunk mixing majority and dissent could present a dissent as the Court's ruling. Each opinion is chunked on its own, and CourtListener's "combined" texts (majority + concurrences + dissents in one text, e.g. Loper Bright, 2024) are cut at each "JUSTICE X, concurring/dissenting." or "... delivered the opinion of the Court." line; the section names the opinion ("Kagan, J., dissenting") and is shown to the model and the reader. Texts that came from a PDF have no paragraph breaks (281 of 4,709 opinions, e.g. Kennedy v. Bremerton, 2022), so these lines are also found inside a paragraph, and the Syllabus is recognised by its standard "NOTE: Where it is feasible, a syllabus" line. |
| Whole paragraphs, at most 350 words (SR16: 250-400) | 98.3% of our paragraphs have at most 350 words (median 88), so they stay whole and quotes stay intact; at 250 words only 84.3% would. |
| Split long paragraphs between sentences | Only 1.7% of paragraphs are longer than 350 words; they are cut at sentence ends, never inside a sentence. |
| New chunk at each Part heading (I, II, A...) and at the Syllabus | The section label is stored and shown to the reader; the Syllabus (written by Court staff, not part of the opinion) is flagged. |
| Exact start/end positions | Needed to highlight the passage in its opinion (FR4, SR31); checked by tests/test_chunking.py. |
| Header embedded with each chunk | "Case (year) - opinion type - section" is added to the embedded text, so a passage keeps its context (including which Justice's opinion it is). |
| Measured choice | Step 3.5 (2026-10-29, tune split, run tune_chunks_2026-10-29T18-09-07.json): quote@8 0.364 / 0.455 / 0.364 and MRR@10 0.955 / 0.939 / 0.894 for 250 / 350 / 400 words; 350 kept by the rule in EVALUATION.md. |

Known exception: 9 chunks of 104,904 are longer than 350 words (longest 830). They are tables with
no sentence ends (e.g. the appendix of Senate recess dates in NLRB v. Noel Canning, 2014); the model
reads about the first 380 words of a chunk. Not fixed: no legal reasoning is lost.

Embeddings: BAAI/bge-small-en-v1.5 (384 numbers, normalised), the same model for passages and
questions. Passages are embedded sorted by length and saved every 2,048 (data/work/embedding_cache),
so an interrupted build resumes. The laptop CPU needed about 14 hours for 104,904 passages, so the
blocks can also be computed on a Colab GPU with the same model (scripts/export_for_colab.py; 46 blocks
in 4.5 minutes on 2026-10-26).

## 5. Verification policy (FR6, FR7, SR22-SR25)

A sentence is shown only if:
1. it cites at least one passage, and only passages that were sent to the model;
2. its quote (5+ words) appears word for word in a cited passage;
3. every citation in it exists in the CourtListener citation table AND is either a retrieved
   decision or written in the cited passage itself;
4. every case name in it is the case of a cited passage (both parties compared) or appears in one;
5. every number and date in it appears in its cited passage, or is the year of a cited decision
   (date_filed); a sentence that dates the decision must give that year.
6. it does not present a dissent or concurrence as the Court's view (added in Week 7, see section 11).

At runtime we guarantee existence, binding to retrieved opinions, and lexical support.
Semantic support is measured by groundedness: lexically at runtime (inside the support score)
and by an AI judge in evaluation (FR15).

## 6. Abstention policy (FR8, FR9, SR26-SR29)

support = (0.5 x best similarity of cited passages + 0.4 x mean groundedness
           + 0.1 x min(1, passages cited / 2)) x share of sentences that survived verification.
NOT SUPPORTED if no sentence is left or support < tau_abstain;
LOW CONFIDENCE if support < tau_confident; otherwise ANSWERED.
A NOT SUPPORTED result shows no generated text, only the message and the passages (SR28).
Thresholds are tuned on 80% of the test questions and reported on the other 20% (SR29),
with a selection rule written in EVALUATION.md before measuring.

Out of scope -> NOT SUPPORTED: decisions after 2024, other courts, personal legal advice.
Older cases (before 2000, e.g. Roe v. Wade, 1973): we answer only from what 2000-2024 opinions
say about them, and the answer cites the 2000-2024 opinion, never the older case directly.

## 7. Evaluation plan (FR13-FR20, SR37-SR40, C7, NFR16)

eval/questions.jsonl (also editable from the admin pages, exported to git):
>= 40 answerable, >= 20 unanswerable, >= 20 adversarial; split tune/test 80/20; tag eval-v1 by week 3.
Metrics: recall@1/5/10/20, MRR@10, abstention precision and recall (target >= 0.8, NFR3),
false citations shown (target 0, NFR1) computed by a checker separate from the runtime check,
using the citation table and the citation map; fabrications caught; groundedness.
Deliberate improvement (week 10): reranker, measured before and after on the same questions.

## 8. Roles (SR33-SR36)

SR33 as written (confirmed by the instructor on 2026-11-06, section 11): two roles.
Visitor: no login, no account; the public research (chat) page only.
Administrator: login; the research page and the admin pages: evaluation, test questions,
abstentions, analytics, settings, corpus and citation lookup, re-index, accounts. Administrator
accounts are created and disabled by an administrator (FR12); there is no self-registration.
Login security (administrator): bcrypt hashes (SR34); locked 15 minutes after 5 failures (SR36); the
same error message for every failed login; at most 10 failed logins per IP address in 15 minutes
(HTTP 429); a new session at each login; logout clears the session; session cookie HttpOnly,
SameSite=Lax, Secure online (HTTPS_ONLY=1); CSRF token on every POST, visitors included (they get the
token with their session from /api/me); role checked on the server at every admin request (SR35, NFR8).
Research page (visitors, step 5.12): at most 10 questions per minute per IP address on /api/ask; the
next one gets HTTP 429 with a message that says how long to wait, before the model is called and
without being saved. It protects the model credit and the demo (NFR5) now that no account is needed.

## 9. Work process

Every guide step is made on its own branch (step/<number>-<name>, never directly on main) with
small commits, and merged through a pull request after the team checks it does not conflict with
main or break a teammate's files; each pull request also updates section 10 (and any section it changes). Owners: Yasser = data path (bulk files,
ingestion, chunking, embeddings, search, reranker); Joe = database, website, deployment;
Edwin = citations, model, verification, evaluation, test questions.

## 10. Implementation status

| Part | Owner | Branch / PR | Status |
|---|---|---|---|
| 0.1-0.6 SPEC, AI log, project setup | all | step/0-setup | merged (PR #1; tag spec-v1) |
| 1.1-1.6 bulk-file reader and filters | Yasser | step/1.1-1.6-bulk-filters | merged (PR #2); run on the real files, counts in section 2 |
| 1.4b-c real decisions only, copies merged | Yasser | step/1.4-cluster-scope | merged (PR #4) |
| 1.7 database schema (db.py) | Joe | step/1.7-db | merged (PR #6, reviewed by Joe) |
| 1.8 load into PostgreSQL (ingest, chunking, seed) | Yasser | step/1.8-ingest | loaded on the real data (counts in section 2); merge after 1.4 and 1.7 |
| 1.9 citation lookup (citations, check_citation, find_case) | Edwin | step/1.9-citations | code ready; reviewed by Edwin, matches guide p.27-29; needs 1.7 |
| 1.10 tests for citations | Edwin | step/1.10-citation-tests | 5 tests pass (StaticCitationIndex, no database needed); needs 1.9 merged |

Week 2 and later (1.8 was merged in PR #5):

| Part | Owner | Branch / PR | Status |
|---|---|---|---|
| 2.1-2.3 chunking, embeddings, search index, statistics | Yasser | step/2-index | merged (PR #16) |
| 3.2-3.4 hybrid search (BM25 + pgvector, RRF), reranker switch, retrieval baseline script | Yasser | step/3-search, step/3.4-eval-v1-baseline | merged (PR #20); eval-v1 baseline: TEST recall@5 1.0, MRR@10 0.938, quote@8 0.25 (EVALUATION.md) |
| 2.1 fix + 3.2 fix: one label per opinion in combined texts; BM25 stemming | Yasser | step/3-opinion-sections | merged (PR #23) |
| 5.6 login and security for the API (roles user/admin, CSRF, login limit per IP, one login message) | Joe | step/5.6-login-security | code and tests ready (21 new tests); React pages in 5.8-5.10 |
| 5.7 research API for the chat (/api/ask, /api/passage, /api/history; query_log.user_id) | Joe | step/5.7-api-research | code and tests ready (15 new tests) |
| 5.8 React login and chat pages under /app; Dockerfile Node stage | Joe | step/5.8-react-chat | built and checked in a browser (test database, fake model); 3 new tests |
| 5.9 React admin pages (9 pages) and admin API (20 routes) | Joe | step/5.9-react-admin | built and checked in a browser (test database, fake model); 14 new tests |
| 5.10 switch: React at / and /admin; Jinja templates and routes removed; tests/test_admin.py rewritten | Joe | step/5.10-switch-to-react | built and checked in a browser (test database, fake model); 143 tests pass |
| 5.11 public research: only the administrator logs in (instructor, SR33); /api/ask and /api/passage open to visitors; /api/history removed; user accounts removed by a migration | Joe | step/5.11-public-research | checked in a browser (test database, fake model); 141 tests pass |
| 5.12 limit of questions per IP address on /api/ask (10 per minute, then HTTP 429) | Joe | step/5.12-ask-rate-limit | checked in a browser (test database, fake model); 4 new tests |
| Admin pages open on the TUNE split (overview, runs, a run, compare, threshold preview); TEST only when asked | Joe | feature/admin-tune-default | checked in a browser (test database, fake model); 5 new tests |
| Answer cites the U.S. Reports citation first, then S. Ct., then L. Ed. (best_citation, shared with the checker in app/citations.py) | Joe | feature/citation-label-us-first | 5 new tests |
| Design of the React pages: sober legal style (navy, gold accent, serif headings, admin menu on the left); CSS only plus the header brand and admin menu | Joe | feature/react-design | checked in a browser (test database); 141 tests pass |
| 3.3 settings: weighted fusion (w_bm25, w_separate, fusion_pool), tune_search, quote@8 | Yasser | step/3-search-weights | code ready; run tune_search on the real data |
| 7.2 metadata in the verifier: decision years from date_filed (check 5), case names on both parties (check 4) | Edwin | step/7.2-metadata-checks | 8 new tests; checked on the 2,477 real case names (AI_LOG) |
| 4.6 metadata search: a case named in the question limits the search to its decision (setting case_filter, off) | Edwin | step/4.6-case-filter | merged (PR #50; Searcher.search(decision_ids) in PR #52); measured on TUNE: same quote@8 and MRR@10, search 179 -> 29 ms when a case is named; on by the rule, for speed only (EVALUATION.md) |
| 10.1-10.2 week-10 improvement: quote diagnosis, hypothesis (bge-base embeddings), measured on TUNE | Yasser | step/10.1-hypothesis, step/10.2-embedding-model | measured: bge-base worse (quote@8 0.286 vs 0.429), bge-small kept (EVALUATION.md) |
| 8.2 run 2 on the fixed data; compare_runs: run 1 (saved file) against run 2 on the TUNE questions both answered | Edwin | step/8.2-run2-compare | run 2 started 2026-11-08; 3 new tests |
| Admin pages and the answer restyled like the landing page: dark dashboard, SVG rings/dials/bars/lines from /api/admin only, status with icon and words, gold citation pills, the six checks in the working steps; the run page lists the chosen split plus adversarial | Edwin | feature/admin-answer-ui (on #84) | checked in a headless browser at 1280 and 390 px with real data; 254 tests pass |
| Information pages (privacy, terms, sources, contact) in the footer; contact form with an admin Messages page | Edwin | feature/site-pages (on the welcome branch) | 12 new tests; checked in a headless browser at 1280 and 390 px |
| Welcome message for greetings (status WELCOME, fixed text, no search or model); one question per message kept | Edwin | feature/welcome-message (on #86) | 13 new tests; no eval-v1 question is a greeting |
| Defence: import_run loads saved runs into a database (the online admin pages had no run); demo_fabricated; demo question list | Edwin | feature/import-run, #77, #78 | 3 + 3 tests |
| 8.3 final numbers: false citations 0 (TUNE + adversarial 0/56, TEST 0/23), run 1 vs run 2, error analysis; EVALUATION.md and report sections filled | Edwin | step/8.3-final-numbers | outputs in eval/runs |
| 8.2 tau_abstain 0.20 chosen on TUNE, TEST reported once (precision 1.0, recall 0.8, 0 false citations); run_eval --test and show_citations read a run file | Edwin | step/8.2-tau-and-test | 2 new tests |
| 8.2 quote matching: verify.norm changed, run 2 rechecked (reverify_run), kept by the rule | Edwin | step/8.2-quote-matching | 7 + 9 new tests; eval/runs/eval_run2_reverified.json |
| 8.2 error_analysis (why answerable TUNE questions abstain; gold quote in the 8 passages); requirements table for Edwin's part | Edwin | step/8.2-error-analysis | 5 new tests; 3 gaps written down (section 11) |
| 8.2 export_run (a run saved in eval/runs with its TUNE metrics and sweep); threshold rule clarified; drafts of the final EVALUATION section and the report sections | Edwin | step/8.2-results-draft | run 2 saved after day 1 (38/85); 2 new tests |
| 6.2-6.3 Railway: pgvector database (PostgreSQL 18) and the website from main; online database filled with pg_restore of the Nov 6 dump, then remove_out_of_scope (2,415 decisions) and seed --admin; settings case_filter on, tau_abstain 0.20 | Joe | (no code change) | online since 2026-11-06, data loaded 2026-11-09; /health index_loaded true, a question answered live |

## 11. Divergences log

2026-10-22 - The repository was restarted from an empty history to follow the Requirements
Document (Delivery 1). An earlier attempt (REST API, 2023-2024, SQLite) was discarded; a backup
of its history is kept by the team.

2026-10-23 - Corpus scope narrowed from "all scotus clusters 2000-2024" (188,045, mostly one-line
orders) to real decisions (rule in section 2). The court and dates do not change.

2026-10-24 - Verifier (4.2): `verify()` removes `["P1"]` passage markers from the sentence text
before the five checks. The guide's check 5 read the 1 in "P1" as a number and removed correct
sentences. Details in AI_LOG.md.

2026-10-29 - Verifier (Week 7): check 6 added. A sentence that speaks for the Court but cites only
dissents or concurrences is removed (found in a live run: Gorsuch's concurrence in Loper Bright was
presented as "The Court rejected Chevron deference"). Details in AI_LOG.md.

2026-10-29 - Verifier (Week 7): check 4 also recognises "In re X" / "Ex parte X" case names; check 5
also reads numbers written as words ("two" to "ninety-nine"). Both were attacks that got through.
Details in AI_LOG.md.

2026-10-29 - Verifier (Week 7): a citation missing from the citation table but printed in the cited
passage is still removed (rule 3), but labelled "not in the citation table (written in the passage)"
instead of FABRICATED, so the fabrication count is not inflated by CourtListener's 2020+ gap.

2026-10-29 - Evaluation: waits and retries when the model provider refuses a call for its rate limit
(Groq free tier: 8,000 tokens per minute; one question costs about 5,000). Only the evaluation waits;
a visitor's request still ends with ERROR at once (SR4). Details in AI_LOG.md.

2026-10-29 - The planned week-10 improvement (reranker, SR18) gave no gain on the tune split
(EVALUATION.md, run tune_rerank_2026-10-29T15-53-59.json) and costs 5-69 s per question on a laptop
CPU. It stays available (use_reranker) but is off; the improvement to report will be chosen from
measured candidates (chunk size, step 3.5, first).

2026-11-06 - Website: the instructor asked for (1) a React front end instead of the server-rendered
Jinja pages of the guide (pp. 56-70), (2) login screens with proper security, (3) a chat page for the
research questions. Decision (Joe, 2026-11-06, to be confirmed with the instructor): everyone logs in,
roles "user" and "administrator", accounts created by an administrator. This changes SR33 ("visitor,
no login"), FR1, FR4, FR10, FR12, O7 and sections 1.2, 4 and 6 of the Requirements Document, which
will be updated once the instructor confirms (new SR33: "There shall be two roles, user and
administrator. Both log in. A user can use the research page only; an administrator can also use
the admin pages. Accounts are created and disabled by an administrator; there is no
self-registration."). The chat answers each question on its own: pipeline.answer does not use earlier
questions, and the page says so. The Jinja pages stay until the React pages do the same (step 5.10).
Plan: steps 5.6 (login security) to 5.10 (switch), one branch each.

2026-11-06 - Login (step 5.6): the guide's check_login said "This account is locked" only for emails
that exist, which tells an attacker which accounts exist. Every failed login now gives "Wrong email or
password." (unknown email, wrong password, locked or disabled account), and an unknown email still
costs one bcrypt check so the reply time does not give it away either. Added on top of SR36: at most
10 failed logins per IP address in 15 minutes. Known limit: on Railway the address comes from the
X-Forwarded-For header (uvicorn --proxy-headers), which a client can add to; the per-account lock
(SR36) does not depend on it.

2026-11-06 - Chat history (step 5.7): query_log (FR28, SR41) also saves who asked (user_id) and the
answer exactly as it was shown, so a user can open an earlier answer again without calling the model.
No new table. A user only sees their own questions (someone else's gives 404); the admin pages show
the questions but not who asked them.

2026-11-06 - Admin API (step 5.9): the abstention list no longer shows who asked (the admin does not
need it to tune abstention). Labels must be one of the four buttons; labelling a question that is not in
the log gives 404 (the guide's Jinja route crashed with a 500 when the label was "add as ..."). Creating
an account with a short password or a wrong role gives an error instead of doing nothing silently.

2026-11-06 - Switch (step 5.10): the React pages moved from /app to / and /admin, and the Jinja
templates and routes of the guide (pp. 56-70) were removed from app/main.py; the admin SQL now has one
copy, in app/api_admin.py. The guide's tests/test_admin.py (p. 63) checks the same behaviour through
POST /api/login and the React /admin pages. The "research aid, not legal advice" footer (SR7) is in
frontend/index.html, outside React, so it is on every page even before the JavaScript loads.

2026-11-06 - Instructor's answer: only the administrator logs in; the chat takes one independent
question per message (FR1). Dr. Salloum answered our two questions about the website: (1) login is
"only admin", visitors do not log in; (2) the chat follows the Phase 1 requirements, which ask for one
question at a time and no follow-up questions. The earlier decision "everyone logs in, roles user and
administrator" (entry above, which was waiting for his confirmation) is REVERTED in step 5.11: SR33,
FR1, FR4, FR10, FR12, O7 and sections 1.2, 4 and 6 of the Requirements Document stay as written, and
the Requirements Document needs no change. /api/ask and /api/passage are open to visitors (still with
the CSRF token, SR3 and the query log); /api/history is removed (a visitor has no account, so "My
questions" lives only in the open page); the accounts page creates administrators only; a migration
removes the 'user' accounts made during steps 5.6-5.10 (their questions stay in the log without the
account) and the database allows the role 'admin' only. All the login security of step 5.6 stays.

2026-11-06 - Question limit per IP address (step 5.12, asked by Yasser): no requirement asks for it;
it is added on top, like the login limit of step 5.6. Since step 5.11 anyone can use the research page
without an account, so a script could send questions in a loop and use up our Groq credit (Edwin's
retry for Groq's own limit, PR #28, is for the evaluation runs, not for visitors). One address may ask
10 questions per minute; the next one gets HTTP 429 and a Retry-After header, the model is not called
and the question is not saved in the query log (like a question refused by SR3, which is checked first
and does not count). Evaluation runs from the admin pages call the pipeline directly, so the limit does
not apply to them. Known limits: kept in memory (a restart empties it); on Railway the address comes from
X-Forwarded-For, as for the login limit; many visitors behind one address (a university network) share
the 10 questions; many addresses together are not limited.

2026-11-06 - Week 10 improvement (step 10.2): the hypothesis written first in EVALUATION.md (a larger
embedding model, bge-base-en-v1.5, finds the holding paragraph more often) was measured on the TUNE
split and rejected by its rule: quote@8 0.286 instead of 0.429, recall@5 0.971 instead of 1.0
(run tune_embeddings_2026-11-06T19-04-10.json). The embedding model stays bge-small-en-v1.5 (section 3);
the before/after numbers are reported as a measured regression (brief section 8).

2026-11-06 - Verifier, metadata (Edwin): check 5 also accepts the year of a cited decision (date_filed,
which the model sees in the passage header but which is often not in the text), and a sentence that
dates the decision ("its 2023 decision") must give that year. Check 4 compares both parties of a case
name instead of the first word (the guide and Week 7 compared the first word: "Trump v. Anything"
passed). Details and measurements in AI_LOG.md.

2026-11-06 - Metadata search (Edwin, the instructor: "use metadata for faster search"): no requirement asks
for it; added on top. When a question names a case of our corpus ("X v. Y", matched to decisions.case_name
with same_case), the search can look only at that decision's passages; invented or mixed names match
nothing and use the normal search. Measured search time today: about 0.27 s per question (pgvector about
0.23 s over all passages), against 1-4 s for the model, so the expected gain is mainly finding the right
passage, not answer time (SR2 is already met). Off (setting case_filter) until measured on the TUNE split
with the rule written first in EVALUATION.md. Needs a decision_ids parameter in Searcher.search
(Yasser's file), requested in writing.

2026-11-06 - Admin pages show the TUNE split by default (asked by Edwin for Week 8). The guide's admin
code (pp. 56-62, kept in the React pages of step 5.9) showed the TEST split on the overview, the list of
runs, a run, the compare page and the threshold preview. EVALUATION.md and SR29 say the thresholds are
chosen on TUNE and TEST is reported once, at the end, so an admin who opened those pages after a run saw
TEST numbers while choosing. They now show TUNE (one setting, DEFAULT_SPLIT in app/api_admin.py); TEST
is still one click away on the run page (split selector, ?split=test) for the final report.

2026-11-06 - Week 8 (Edwin): scripts/run_eval.py prints only the TUNE split and the tau sweep after a run;
the TEST split is printed with `--test RUN_ID`, once, after tau_abstain is chosen (EVALUATION.md, SR29).
The guide's version (p. 77) printed both splits after every run.

2026-11-06 - Week 8 (Edwin): Groq's free tier allows 200,000 tokens per day and a full run needs about
500,000, so a run pauses when the model provider refuses for its daily limit and is continued with
`run_eval --resume RUN_ID`. It stays one run (one run id, the settings saved when it started; a resume
is refused if the settings changed). The full run takes about 3 days; while it runs, the website shares
the same daily budget.

2026-11-07 - Week 8 (Edwin): evaluation run 1 (eval-v1, case_filter on) paused at Groq's daily limit
after 39 questions and is NOT resumed. Yasser's step/2.2-text-fixes rewrites passage texts (missing
"fi"/"fl" letters) and opinion labels (65 dissent passages labelled as majority), so finishing run 1
would mix old and new data. Decision: a fresh run 2 on the fixed data, same settings; run 1 is kept as
the "before the fix" run (eval/runs/eval_run1_before_text_fixes_2026-11-06.json), and its 39 questions
are compared with the same questions in run 2.

2026-11-06 - Which citation the answer shows (asked by Edwin after the Week 8 run). The guide's research
page (templates/ask.html; kept in app/api.py citation_label) shows the FIRST citation of the decision. In
CourtListener that is sometimes an odd reporter (Nelson v. Adams: "0 Cal. Daily Op. Serv. 3128"). The
answer now shows the official U.S. Reports citation first, then the Supreme Court Reporter (S. Ct.), then
the Lawyers' Edition (L. Ed. 2d, L. Ed.), and the first citation only when none of them exists. Edwin's
citation checker uses the same order. The side panel still lists every citation of the decision.

2026-11-06 - Corpus text (Edwin's findings on the 2026-11-05 dump): (1) headings naming several groups of
justices who "join as to Parts II and III" were not recognised, so 65 passages of 4 combined texts were
labelled as the majority; the chunker now recognises them. (2) PDF texts had lost the "fi"/"fl" ligatures
("frst" for "first", "fled" for "filed"); `scripts/fix_ligatures.py` puts the letter back only where the corpus
itself shows the real word, and only in opinions that are broken PDFs (7,098 words in 61 opinions; rules in
app/ligatures.py, report in ingestion_reports). Re-indexed: 72,628 chunks. Retrieval unchanged
(EVALUATION.md); Edwin's final week 8 run and the online database (step 6.3) use this dump.

2026-11-08 - Step 8.3 (Edwin): the false-citation checker (SR38) checks the citation the answer page shows
(U.S. Reports, then S. Ct., then L. Ed., as app/api.py after Joe's #58) and accepts it if any row of the
citation table for it is the passage's decision (a decision can be stored twice; two short orders can share
a page). Check 3 uses every row too. A case name outside our corpus is still removed (rule 4) but labelled
"case name not in our corpus or the cited passage": only citations can be proved fabricated, so the
"fabrications caught" count now counts citations only.

2026-11-08 - Week 8 (Edwin): run 2 data. Yasser's dump of 2026-11-06 21:20 UTC (text fixes, PR #59) still held
the 8 decisions his step/1.8-out-of-scope branch lists as not SCOTUS 2000-2024 (7 old cases filed under
2005-2010, 1 Sixth Circuit case); no test question uses them. They were removed from the local database with
his script (dry run, then --apply) before run 2 started, so the data does not change during the run: 2,415
decisions, 72,502 chunks. The restore empties eval_runs, so run 2 has database id 1; run 1 exists only in its
file. `scripts/compare_runs.py` reads a run from a file or the database and compares the two on the TUNE
questions both answered (run 1 stopped after 39).

2026-11-08 - Week 8 (Edwin): the threshold rule (EVALUATION.md, 2026-10-26) did not define "best balance" or
say what to do if no tau reaches 0.80 for both precision and recall. Clarified while run 2 was running and
before its sweep was printed: the highest min(precision, recall), then the fewest wrong answers, then the
lowest tau; if no tau qualifies, the same order on all tau and NFR3 reported as not met. A run is now saved
to eval/runs with `scripts/export_run.py`, because a restore of the database empties eval_runs.

2026-11-08 - Requirements check (Edwin, docs/requirements_edwin.md): two readings written down. (1) SR39:
abstention precision and recall are computed on the answerable and unanswerable questions; the adversarial
questions have their own rate (adversarial abstention rate), so the threshold is not tuned on the attack
questions (the guide's evaluate.metrics). (2) SR23: a citation that is in the citation table but is not a
retrieved decision is kept when it is written in the cited passage itself (a passage of Loper Bright that
cites Chevron); this is rule 3 of section 5, a wider reading of SR23's "must match an opinion we retrieved".
NFR2 is met by rule for numbers and dates, and only approximately for other facts (quote and groundedness).

2026-11-09 - Week 8 (Edwin): how run 2 was made. Questions 1-38 on 2026-11-08 with Edwin's Groq key; it paused
at the daily limit. To finish sooner, the run was resumed on 2026-11-09 with a teammate's key (same model,
openai/gpt-oss-120b, same settings: a key is not a setting). A first try with an incomplete key failed with
AuthenticationError on 6 questions (A039-A042, U001, U002); the run was stopped, those 6 error rows were
deleted (they say nothing about the system) and the run set back to paused. Questions 39-85 then ran with
Yasser's key. Run 2 finished with 85 of 85 questions and 0 errors (eval/runs/eval_run2.json). To do after the
run: an authentication error should pause the run like the daily limit, not save an ERROR per question.

2026-11-09 - Requirements check (Yasser, docs/requirements_yasser.md): three readings written down.
(1) SR10: the court is not stored on each row; the whole corpus is one court (COURT in the config, shown in
the coverage line). (2) SR11: the bulk files carry no licence per row; the Public Domain Mark covers the
CourtListener data as a whole, so every row gets config.LICENCE. A row without a licence is refused by the
loading code and by the schema (NOT NULL), now with tests (tests/test_licence.py). (3) SR16: a paragraph
longer than 350 words (often a PDF text with no paragraph breaks) is cut at sentence ends, not at a
paragraph end; the last chunk of an opinion can be shorter than 250 words (section 4).

2026-11-09 - Verifier (Edwin, step 8.2): quote matching changed after run 2, by the rule written before measuring
(EVALUATION.md). `verify.norm` (guide code) makes every hyphen "-" (NFKC turns the model's U+2011 into U+2010),
drops CourtListener page markers "*490", and joins words broken at a line end ("mar- riage"). Check 2 ignores the
quote's final . , ; :. Quotes with "..." are still refused. Measured on run 2's saved sentences
(eval/runs/eval_run2_reverified.json), with no new model answers: all four conditions of the rule hold, so it is kept.
The TEST split is reported with this verifier.

2026-11-09 - Week 8 (Edwin): thresholds. tau_abstain = 0.20, chosen on the TUNE split of the rechecked run 2 by the
threshold rule (EVALUATION.md); tau_confident stays 0.70, min_retrieval 0.35. TEST reported once with it: abstention
precision 1.0, recall 0.8, 0 false citations of 23 shown. Set in the local settings; the default in app/config.py
(DEFAULT_SETTINGS, Yasser's file) and the online settings (admin Settings page, Joe) still say 0.55, to change by them.

2026-11-09 - Requirements check (Joe, docs/requirements_joe.md): two readings written down.
(1) SR37: test questions added or edited on the admin page are saved in the database, not straight into git.
The admin downloads them with "Export" (`/api/admin/questions/export`, same JSONL format) and a team member
commits eval/questions.jsonl. On purpose: the evaluation set is frozen (tag eval-v1) and must not change
without a visible commit. (2) SR5: the online database (Railway, step 6.3) is filled with `pg_restore` of
Yasser's dump (same data as run 2: 2,415 decisions, 72,502 passages), not with `seed --corpus`: the bulk files
(about 52 GB) are not on the server and the embeddings were made on Colab. scripts/seed.py still does every
part on a new database, and is used online for the admin account (`seed --admin`).

2026-11-12 - Research page (Edwin): a greeting or "what can you do" gets a welcome message instead of "Not supported".
Before, "hello, what can you do" went through the search and the model and ended "not supported", which is correct
but unhelpful. Now pipeline.answer first checks whether the WHOLE message is a greeting or a help phrase (a fixed,
narrow list; "Hello, did the Court overrule Chevron?" is not a greeting) and returns status WELCOME with our own text:
what Verdicta does, its coverage and two example questions. No search, no model call, no legal statement, so FR2,
NFR2 and SR28 are unchanged; FR8 applies to legal questions. None of the 85 eval-v1 questions is a greeting (tested),
so the evaluation numbers stay valid. The instructor's rule is unchanged: one independent question per message, no
follow-up questions (entry of 2026-11-06); asking him whether follow-ups may now be added is pending.

2026-11-12 - Website (Edwin, team decision): information pages /privacy, /terms, /sources and /contact, linked from the
footer on every page, and a contact form. The privacy page describes what the code really does: questions are saved in
query_log (FR28) without name, account or IP address; the IP address is used only in memory for the limits; one
necessary session cookie; no trackers; Groq and Railway receive data; questions and contact messages are kept with no
fixed deletion date (team decision). The form (app/api_site.py) is open to visitors with the CSRF token, checks its
fields, allows 3 messages per address in 10 minutes, and stores name, email and message in contact_messages; an
administrator reads and deletes them (admin page "Messages", admin role + CSRF). The address shown comes from
CONTACT_EMAIL. Files of others changed and told: app/db.py, app/main.py, frontend/index.html, frontend/src/main.jsx
(Joe), app/config.py and .env.example (Yasser).


2026-11-12 - Visitor accounts (Yasser, team decision; replaces the "administrator only" part of the 2026-11-06 entry and
step 5.11). A visitor may create an account on /signup (email + password) to keep their question history; the research
page stays open to everyone without an account (SR33, FR1). Written before the code; the instructor is to be told
before the defence. Rules: (1) roles are 'admin' and 'user'; sign-up only ever makes a 'user'; administrators are still
made only by the seed script or the Accounts page; (2) sign-up never changes an existing account (an email already used
is refused with "An account with this email already exists", unlike create_user, which resets it for FR12); (3) a
password of at least 10 characters, as on the Accounts page, until Joe's password policy replaces both; (4) at most 5
accounts per IP address per hour, kept in memory like the other limits; (5) after sign-up the visitor is logged in and
sent to the research page; the login page sends a 'user' to the research page and an 'admin' to /admin; (6) a logged-in
user's questions are saved with their user_id; GET /api/history lists ONLY their own questions and /api/history/{id}
returns one of them, anything else is 404 (another visitor's questions stay readable only on the admin pages); (7) a
'user' gets 403 on every /api/admin route, as before; (8) the start-up migration no longer deletes 'user' accounts,
and the role rule allows ('admin', 'user'). No name is asked: only the email and a bcrypt hash are stored. The privacy
page says so. Changed files of others, told: app/db.py, app/api.py, app/api_admin.py, frontend/src/pages/Chat.jsx,
the 5.11 tests (Joe); frontend/src/pages/Privacy.jsx (Edwin).

2026-11-13 - The two logs (part 3 of docs/PLAN_2026-11-13.md, Yasser; Dr. Salloum's request 6). Written before the code.
(1) **User log** (table user_log): one row per thing an account does, with the time and a small JSON detail. Events:
signup, login, login_failed (wrong password or locked; the attempt is on a known account), logout, question (with the
query_log id), follow_up (with the query_log id; Joe's chats), plan_change (Joe's plans), refused (a limit or a rule
said no: e.g. too many questions; the reason is in the detail). Visitors without an account have no user log: their
questions stay anonymous in query_log (FR28/SR41). (2) **Admin log** (table admin_log): everything an administrator
does: login, logout, and every change made through /api/admin (any request that is not a GET), plus the exports
(downloading a log, a list or a PDF). Each row keeps the admin, the action, the account it concerns if any, and the
answer's HTTP status; it is written by one middleware, so a new admin route is logged without extra code. (3) Every
action calls one helper (app/logs.py: log_user, log_admin). A log that cannot be written never blocks the action
(the error goes to the server output). (4) No IP address, no browser information and no password are stored in the
logs (the privacy page says what is kept). (5) Only administrators read the logs: GET /api/admin/users/{id}/log and
GET /api/admin/log, each also downloadable as a CSV file (?format=csv). Rows are never edited; they are deleted only
with their account (ON DELETE CASCADE for the user log). Joe's admin pages (part 2) show them; the PDF exports
(part 4) include them.

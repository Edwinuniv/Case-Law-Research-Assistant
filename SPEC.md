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
  clusters 9,833,660 read -> 188,045 scotus 2000-2024 -> real decisions [ ] -> decisions loaded [ ]
  -> opinions [ ] -> chunks [ ]; citation table rows 17,859,437; citation-map rows kept [ ].
- Real decisions only (step 1.4b): CourtListener stores many one-line orders ("certiorari denied")
  as clusters (up to 22,544 in one year, while the Court decides about 70-90 cases a year).
  Rule, the same for every year: a decision (its clusters with the same docket and date) is kept if
  it has a Supreme Court Database id (scdb_id), or if its longest opinion has >= 300 words.
  Why 300: CourtListener links SCDB only for 2000-2019 (1,581 decisions). On those years, >= 300 words
  keeps 98% of the SCDB decisions; lowering it to 100 adds about 600 one-paragraph orders. The long
  texts outside SCDB are real opinions we want: copies of SCDB cases under another docket
  (e.g. Nevada v. Hibbs, 2003), dissents from a denial (e.g. Woodward v. Alabama, 2013) and
  in-chambers opinions (e.g. Philip Morris v. Scott, 2010). Measured: [decisions kept, duplicates].
- Licence: Public Domain Mark 1.0, stored for every decision and opinion with its load date;
  rows without a licence are rejected (FR30, SR11).
- A newer quarterly release is loaded by changing CL_RELEASE only (NFR13).

## 3. Architecture

PostgreSQL 16 + pgvector. Tables: decisions, cluster_alias, opinions, chunks (vector(384)),
citations, citation_map, test_questions, query_log, eval_runs, eval_results, users, settings, jobs.

question -> input check, 3-1000 characters (SR3)
-> hybrid search: pgvector cosine + BM25, Reciprocal Rank Fusion, top 20 (SR17)
-> top 8 passages (baseline: fused order; week-10 improvement: reranker, SR18)
-> cheap gate: best passage similarity < min_retrieval => NOT SUPPORTED, model not called
-> model (30 s limit, one retry on invalid JSON) returns sentences with passage ids P1..P8
   and exact quotes, or NOT_SUPPORTED (SR4, SR19, SR20)
-> verification, 5 checks per sentence; failing sentences removed (SR22-SR25)
-> support score (SR26) -> status (SR27)
-> case names and citations shown to the user are rendered from OUR database (SR21).

## 4. Chunking strategy (FR31, SR16)

[filled in week 2, with the paragraph statistics and the 250 / 350 / 400 words comparison]

## 5. Verification policy (FR6, FR7, SR22-SR25)

A sentence is shown only if:
1. it cites at least one passage, and only passages that were sent to the model;
2. its quote (5+ words) appears word for word in a cited passage;
3. every citation in it exists in the CourtListener citation table AND is either a retrieved
   decision or written in the cited passage itself;
4. every case name in it is the case of a cited passage or appears in one;
5. every number and date in it appears in its cited passage.

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

Visitor: no login, public research page only.
Administrator: login (bcrypt hashes, locked 15 minutes after 5 failures); evaluation,
test questions, abstentions, analytics, settings, corpus and citation lookup, re-index, accounts.

## 9. Work process

Every guide step is made on its own branch (step/<number>-<name>, never directly on main) with
small commits, and merged through a pull request after the team checks it does not conflict with
main or break a teammate's files; each pull request also updates section 10 (and any section it changes). Owners: Yasser = data path (bulk files,
ingestion, chunking, embeddings, search, reranker); Joe = database, website, deployment;
Edwin = citations, model, verification, evaluation, test questions.

## 10. Implementation status

| Part | Owner | Branch / PR | Status |
|---|---|---|---|
| 0.1-0.6 SPEC, AI log, project setup | all | step/0-setup | in review (tag spec-v1 done) |
| 1.1-1.6 bulk-file reader and filters | Yasser | step/1.1-1.6-bulk-filters | code ready; waiting for the dockets download, then fill section 2 |
| 1.4b real decisions only (scdb_id + calibrated length) | Yasser | step/1.4-cluster-scope | code ready; needs filter_clusters again and the opinions filter, then fill section 2 |
| 1.7 database schema (db.py) | Joe | step/1.7-db | code ready; Joe to review |
| 1.8 load into PostgreSQL (ingest, chunking, seed) | Yasser | step/1.8-ingest | code ready; needs 1.7 merged and the filtered files |
| 1.9 citation lookup (citations, check_citation, find_case) | Edwin | step/1.9-citations | code ready; Edwin to review; needs 1.7 |
| 1.10 tests for citations | Edwin | - | not started |

## 11. Divergences log

2026-10-22 - The repository was restarted from an empty history to follow the Requirements
Document (Delivery 1). An earlier attempt (REST API, 2023-2024, SQLite) was discarded; a backup
of its history is kept by the team.

2026-10-23 - Corpus scope narrowed from "all scotus clusters 2000-2024" (188,045, mostly one-line
orders) to real decisions (rule in section 2). The court and dates do not change.

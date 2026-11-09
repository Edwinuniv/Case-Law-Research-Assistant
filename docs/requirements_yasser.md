# Where each requirement is implemented - Yasser's part (checked 2026-11-08)

For the report's appendix (guide p.83), next to Edwin's docs/requirements_edwin.md. Each row was checked in
the code and has a test, a saved run or an ingestion report that proves it. Only the data and search
requirements are listed; FR32/SR14 (citation lookup) and the verifier's use of the citation table are in
Edwin's table.

| Requirement | Implemented in | Proved by | Status |
|---|---|---|---|
| FR29 load SCOTUS 2000-2024 from the bulk files | `scripts/filter_dockets.py`, `filter_clusters.py`, `filter_opinions.py`, `app/ingest.py` (`load_corpus`); court and dates in `app/config.py`; out-of-scope list in `app/scope.py` | `test_ingest_groups` (6 tests: copies kept once, combined texts), `test_scope` (5 tests); `check_scope` on the final data: 2,415 decisions, 0 out of scope | done |
| SR8 download courts, dockets, clusters, citations, citation map | download with resume (`aria2c -c`), file sizes in SPEC §2; read by `app/bulk.py` | SPEC §2 (sizes measured 2026-10-22); `corpus` ingestion report (rows read per file) | done |
| SR9 opinions file streamed or resumable, filtered, then deleted | `scripts/filter_opinions.py` (stdin or file, `--delete`) | SPEC §2 (44.8 GB file read, 5,598 opinions kept); the file is not in the repo or on the server | done |
| SR10 store id, cluster, case name, court, date, type, text | tables `decisions` and `opinions` (`app/db.py`); `opinion_label` in `app/ingest.py` | every opinion has `type`, `label`, `text` (NOT NULL); `test_opinion_sections` (labels) | done; see gap 1 |
| FR30, SR11, NFR11 licence and load date stored, no licence = rejected | `licence TEXT NOT NULL`, `loaded_at` in `decisions` and `opinions`; `rejected_without_licence` in `ingest.py` | `test_licence` (3: stored with licence and date, rejected without, refused by the schema); `corpus` report: 0 rejected | done; see gap 2 |
| NFR12 the 44.8 GB file is not kept | `filter_opinions.py --delete` (or streamed from stdin) | SPEC §2 | done |
| NFR13, SR6 a newer release without code changes | `CL_RELEASE`, `COURT`, `DATE_FROM`, `DATE_TO` read from `.env` in `app/config.py` | coverage line built from them (`config.COVERAGE`) | done |
| SR12 citation table (volume, reporter, page -> cluster) | `scripts/filter_citations.py`, `ingest.load_citations` (17,859,437 rows), `citation_map` (58,958 rows) | `citations` ingestion report; Edwin's citation tests use it | done |
| SR15 ingestion report: rows read, opinions kept, chunks, errors | `db.save_report`: `corpus` (filters, decisions, opinions, without text, without licence, out of scope), `index` (chunks), `duplicates`, `ligature_fix`, `out_of_scope` | admin ingestion page (Joe) lists the last 5 reports | done |
| FR31, SR16 chunks of 250-400 words on paragraph ends, with start and end positions | `app/chunking.py` (`chunk_opinion`, max 350 words; a paragraph over 350 words is split at sentence ends); `start_char`, `end_char` in `chunks` | `test_chunking` (4: offsets exact, length limit, sections), `test_opinion_sections` (7: never two opinions in one chunk); 350 chosen on TUNE (`tune_chunks_2026-10-29T18-09-07.json`) | done; see gap 3 |
| SR17 BM25 + embedding search, top 20 kept | `app/bm25.py` (sparse matrix, Snowball stemming), `app/search.py` (pgvector cosine, weighted RRF, `retrieve_k` 20) | `test_bm25` (5), `test_search_weights` (5), `test_search_filter` (5), `test_indexing_cache` (3); weights chosen on TUNE (`tune_search_2026-10-29T15-30-53.json`) | done |
| SR18 reranker selects the best 8, measured before and after | `Searcher.choose` with `use_reranker` (`app/rerank.py`, cross-encoder); 8 passages = `top_k` | `tune_rerank_2026-10-29T15-53-59.json`: no gain, 5-69 s per question; off (SPEC §11) | partial; see gap 4 |
| FR18 retrieval metrics per run | `scripts/eval_retrieval.py` (recall@1/5/10/20, MRR@10, quote@8, `--split`) | saved runs in eval/runs; TEST: `retrieval_2026-11-08T18-22-10.json` | done |

## Gaps found while checking

1. **SR10 "court".** The court is not stored on each row: the whole corpus is one court (`COURT` in the
   config, shown in the coverage line). Storing "scotus" on 3,600 rows would add nothing. Written in SPEC
   section 11 as our reading of SR10.
2. **SR11 "a document without a licence shall be rejected".** The bulk files do not carry a licence per row;
   the Public Domain Mark applies to the CourtListener data as a whole, so every row gets `config.LICENCE`.
   The rejection is enforced twice (`NOT NULL` in the schema, the check in `ingest.py`); tests/test_licence.py
   now makes it happen (2026-11-09). Written in SPEC section 11.
3. **SR16 "along paragraph boundaries".** PDF texts have no paragraph breaks, and some paragraphs are longer
   than 350 words; those are split at sentence ends. The last chunk of an opinion can also be shorter than
   250 words. SPEC §4 explains both; SR16's "about" covers the second, the first is written in SPEC
   section 11.
4. **SR18 the reranker.** It is implemented and was measured before and after, as SR18 asks, but it gave no
   gain, so it is off and the 8 passages are the first 8 of the fused list. The improvement reported in week
   10 is the embedding-model experiment (also a measured regression). Already in SPEC section 11 (2026-10-29);
   the report says it in section 5.

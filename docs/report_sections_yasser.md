# Technical report - Yasser's sections (DRAFT, 2026-11-08)

Draft for the 6-page technical report (guide p.82: section 1 is 0.5 page, section 3 is 1 page; parts of
5, 6 and 7). Every number below comes from a saved run file in eval/runs or from SPEC.md, and the file is
named next to it. I assemble the report: Edwin's text is in docs/report_sections_edwin.md, Joe's
architecture part is still to come.

---

## 1. Problem and corpus

**The problem.** In Mata v. Avianca (S.D.N.Y. 2023), lawyers filed a brief citing cases that a chatbot
had invented. Verdicta answers questions about U.S. Supreme Court decisions and shows only sentences
whose citations and quotes have been checked against the real decisions; when the decisions do not
support an answer, it says "not supported" instead of guessing.

**The corpus.** All Supreme Court decisions filed from 2000 to 2024, taken from the CourtListener bulk
files (release 2024-12-31, about 52 GB; the 44.8 GB opinions file is streamed, filtered and deleted).
CourtListener stores many one-line orders as decisions, so a decision is kept only if it has a Supreme
Court Database id or an opinion of at least 300 words; copies of the same decision (other dockets,
names or dates, or a combined text stored next to the separate opinions) are merged. A citation check
then removed 8 decisions that are not in scope (7 cases of 1884-1928 that CourtListener dates
2005-2010, and 1 Sixth Circuit case). Final corpus: **2,415 decisions, 72,502 passages** (SPEC §2, §4).
The licence (Public Domain Mark 1.0) is stored with every decision and opinion. The citation table
(17.9 million rows) is loaded too: the verifier uses it to check citations.

---

## 3. Decisions (search part)

**Chunking: 350 words, never two opinions in one passage.** A passage is cut at paragraph ends and holds
at most 350 words; 98.3% of the paragraphs are 350 words or shorter (SPEC §4), so a paragraph is rarely
split. A passage never mixes the majority with a dissent: each opinion is chunked alone, combined texts
are cut at each "JUSTICE X, dissenting." line, and the passage carries the opinion's name ("Kagan, J.,
dissenting"), which the model and the reader see. Chosen on the TUNE split (rule written first,
EVALUATION.md): 350 words gave quote@8 0.455, against 0.364 for both 250 and 400 words
(`tune_chunks_2026-10-29T18-09-07.json`, 11 questions).

**Hybrid search.** Each question is searched two ways, and the two lists are fused:
- by meaning: bge-small-en-v1.5 vectors (384 numbers) in pgvector, exact cosine search, 50 candidates;
- by keywords: BM25 (k1 1.5, b 0.75) with Snowball stemming, so "overrule" matches "overruled",
  50 candidates.

Fusion is weighted Reciprocal Rank Fusion: each list gives a passage weight / (60 + rank). The 20 best
passages are kept and 8 are given to the model. Meaning alone misses exact legal terms and case names;
keywords alone miss the same idea in other words. The weights (keywords 1.0, dissents and concurrences
1.0, 50 candidates per list) were chosen on TUNE: no other setting raised quote@8
(`tune_search_2026-10-29T15-30-53.json`). When the question names a case of the corpus, both searches
look only at that decision (Edwin's case filter, measured for speed: section 5).

The chunk size, the search weights and the reranker were measured on 29 October, on the earlier corpus
(before the duplicate opinions were removed and the text was fixed); they were not measured again
on the final corpus.

**BM25 in Python, as a sparse matrix.** PostgreSQL's text ranking is not BM25. Our BM25 stores the word
counts of all passages in a SciPy sparse matrix, so scoring a question is one matrix product and the
index stays small in memory; it is built once and saved to a cache file. One database (PostgreSQL +
pgvector) holds the decisions, the passages with their vectors and the citation table.

---

## 5. Measurements (my part)

**Retrieval baseline (search only, no model).** On the frozen evaluation set (eval-v1), with every
setting chosen on TUNE first; TEST was never used to choose anything.

| split | run | questions | recall@1 | recall@5 | MRR@10 | quote@8 |
|---|---|---|---|---|---|---|
| **TEST** | `retrieval_2026-11-08T18-22-10.json` | 8 | 0.875 | 1.0 | 0.938 | 0.25 |
| all answerable | `retrieval_2026-11-06T23-17-26.json` | 42 | 0.857 | 0.976 | 0.913 | 0.357 |

The right decision is in the top 5 for every TEST question and first for 7 of 8. The weak point is
quote@8: the passage holding the gold quote is among the 8 given to the model for only 2 of the 8 TEST
questions. A diagnosis on TUNE (`diagnose_quotes_2026-11-05T21-28-18.json`) showed why: in 6 of 12
misses all 8 passages already came from the right decision, but not from the paragraph that states the
holding, and the meaning list ranked that paragraph lower than the keyword list in 8 of 12.

**The deliberate improvement, and its result: a measured regression.** From that diagnosis, the
hypothesis (written before measuring) was that a larger embedding model of the same family,
bge-base-en-v1.5, would rank the holding paragraph higher. Same passages and settings, only the model
changed, TUNE split, 35 questions (`tune_embeddings_2026-11-06T19-04-10.json`):

| model | quote@8 | recall@5 | MRR@10 | s per question (CPU) |
|---|---|---|---|---|
| bge-small (before) | 0.429 (15/35) | 1.0 | 0.929 | 0.010 |
| bge-base (after) | 0.286 (10/35) | 0.971 | 0.905 | 0.033 |

bge-base gained 2 questions and lost 7, so the rule kept bge-small. A better score on general benchmarks
did not carry over to finding legal holdings. The guide's planned improvement, a cross-encoder
reranker, was measured earlier (29 October, on the earlier corpus) and did not help either: reranking the top 20 kept quote@8 at 0.455 and
took 5.1 s per question (`tune_rerank_2026-10-29T15-53-59.json`); it is off.

**Data fixes did not move the search.** Repairing lost "fi"/"fl" letters (7,098 words in 61 opinions),
relabelling 65 dissent passages and removing the 8 out-of-scope decisions left every TEST rank unchanged
(`retrieval_2026-11-06T23-17-10.json`, `retrieval_2026-11-08T18-22-10.json`). They were done for the
text the model and the reader see, not for a search gain.

---

## 6. Limitations (my bullets)

- quote@8 is low (0.25 on TEST): the search finds the right decision but often not the holding
  paragraph, and the model cannot quote a passage it was not given. Neither a reranker nor a larger
  embedding model fixed this.
- Small test sets: one TEST question moves quote@8 by 0.125, and the chunk size and the reranker were
  chosen on only 11 TUNE questions.
- Changes of vocabulary: for "Can a state execute a person with an intellectual disability?" the search
  returns Hall v. Florida (2014), not Atkins v. Virginia (2002), which says "mentally retarded".
- The source has errors we can only partly detect: text extracted from PDFs, decisions with wrong dates,
  and no official citation for most decisions from 2020 on.
- Some correct quotes fail the word-for-word check because of the text itself: words broken at a line
  end ("mar- riage", about 4,000 passages) and page markers inside sentences ("*490", 22,235
  passages). Found in Edwin's run 2; the matching fix comes after run 2, so the reported run uses the
  text as it is.

---

## 7. AI-assisted process (candidate entry from AI_LOG, 2026-11-06; the report has room for 2 of our 3 candidates, to choose with Edwin)

**A data repair rule that was too loose, twice.** Claude wrote the rule to put back the "fi"/"fl"
letters lost in PDF texts ("frst" -> "first"). The first version would also have changed real words:
our dry run listed "fled -> filed" (a clean opinion about a suspect who fled would have been changed)
and "rife -> rifle". The second version still treated "specifc" as a real word, because partly broken
opinions were counted as clean. Caught by reading the dry-run lists on the real data before anything
was written; the third version uses only clearly clean opinions as the dictionary, and each case found
in the dry runs became a test.

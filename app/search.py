"""Hybrid search (SR17): meaning-based search in PostgreSQL (pgvector) + keyword search (BM25),
merged with Reciprocal Rank Fusion; optional reranker (SR18)."""
import re
import numpy as np
from app import config, db, embeddings, rerank
from app.bm25 import BM25, TOKENIZER
from app.indexing import vector_literal

CHUNK_COLUMNS = """c.chunk_id, c.opinion_id, c.decision_id, c.section, c.is_syllabus,
                   c.start_char, c.end_char, c.text, o.label AS opinion_label,
                   d.case_name, d.date_filed::text AS date_filed"""


SEPARATE = re.compile(r"concurring|dissenting|respecting|concurrence|dissent", re.I)


class Searcher:
    def __init__(self):
        with db.connect() as con:
            rows = con.execute(f"""SELECT {CHUNK_COLUMNS} FROM chunks c
                                   JOIN opinions o USING (opinion_id)
                                   JOIN decisions d ON d.decision_id = c.decision_id
                                   ORDER BY c.chunk_id""").fetchall()
        self.chunks = rows
        self.by_id = {r["chunk_id"]: r for r in rows}
        self.decision_of = np.array([r["decision_id"] for r in rows])   # decision of each chunk, BM25 order
        self.bm25 = self.keyword_index(rows)
        embeddings.embed_query("warm-up")     # load (or download) the model now, not at the first question

    @staticmethod
    def keyword_index(rows):
        """BM25 over all chunks. Building it takes about 20 s for our 104,904 chunks, so it is saved
        in data/work/bm25.* and reloaded (about 1 s) while the search index has not changed."""
        meta = db.get_settings().get("index_meta") or {}
        key = f"{meta.get('built_at')}|{meta.get('max_words')}|{len(rows)}|{meta.get('words')}|{TOKENIZER}"
        path = config.WORK / "bm25"
        bm25 = BM25.load(path, key)
        if bm25 is None:
            bm25 = BM25([r["text"] for r in rows])
            config.WORK.mkdir(parents=True, exist_ok=True)
            bm25.save(path, key)
        return bm25

    def dense(self, qvec, k, decision_ids=None):
        """Meaning-based: cosine similarity computed by PostgreSQL. <=> is cosine DISTANCE.
        Exact search over all chunks (no HNSW index): measured 57 ms for 104,904 chunks, and the
        approximate HNSW index silently returns fewer rows with its default ef_search=40.
        decision_ids: only the chunks of these decisions (the chunks_decision index finds them)."""
        if decision_ids is not None and not decision_ids:
            return []
        where, args = ("WHERE decision_id = ANY(%s)", [list(decision_ids)]) if decision_ids else ("", [])
        with db.connect() as con:
            rows = con.execute(f"""SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score
                                   FROM chunks {where} ORDER BY embedding <=> %s::vector LIMIT %s""",
                               [qvec, *args, qvec, k]).fetchall()
        return [(r["chunk_id"], float(r["score"])) for r in rows]

    def dense_scores_for(self, qvec, chunk_ids):
        with db.connect() as con:
            rows = con.execute("SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score FROM chunks "
                               "WHERE chunk_id = ANY(%s)", (qvec, list(chunk_ids))).fetchall()
        return {r["chunk_id"]: float(r["score"]) for r in rows}

    def keyword(self, question, k, decision_ids=None):
        """Keyword-based: BM25 scores of all chunks. decision_ids: the other chunks get 0, so they are
        left out like chunks without any word of the question."""
        scores = self.bm25.scores(question)
        if decision_ids is not None:
            scores = np.where(np.isin(self.decision_of, list(decision_ids)), scores, 0)
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i]["chunk_id"], float(scores[i])) for i in order if scores[i] > 0]

    def is_separate(self, chunk_id):
        """A concurring or dissenting opinion (including opinions on a denial of certiorari)."""
        c = self.by_id[chunk_id]
        return bool(SEPARATE.search(f"{c['section']} {c['opinion_label']}"))

    def candidates(self, question, pool, decision_ids=None):
        """The two ranked lists: meaning (pgvector) and keywords (BM25), pool candidates each."""
        qvec = vector_literal(embeddings.embed_query(question))
        return qvec, self.dense(qvec, pool, decision_ids), self.keyword(question, pool, decision_ids)

    def fuse(self, dense, keyword, k, settings):
        """Weighted Reciprocal Rank Fusion: each list gives weight / (60 + rank) to a passage.
        w_bm25 weighs the keyword list; w_separate weighs concurring/dissenting passages."""
        pool = int(settings.get("fusion_pool", 50))
        w_bm25, w_sep = float(settings.get("w_bm25", 1.0)), float(settings.get("w_separate", 1.0))
        fused = {}
        for ranking, weight in ((dense[:pool], 1.0), (keyword[:pool], w_bm25)):
            for rank, (cid, _) in enumerate(ranking):
                w = weight * (w_sep if self.is_separate(cid) else 1.0)
                fused[cid] = fused.get(cid, 0) + w / (60 + rank + 1)
        return sorted(fused, key=fused.get, reverse=True)[:k]

    def search(self, question, k=20, settings=None, decision_ids=None):
        """Top k passages. Each passage's 'score' is its meaning similarity (0..1).
        decision_ids (optional, Edwin's case filter, step 4.6): search only the passages of these
        decisions (ids of the decisions table; an empty list finds nothing). None = the whole corpus."""
        settings = settings or db.get_settings()
        qvec, dense, keyword = self.candidates(question, int(settings.get("fusion_pool", 50)), decision_ids)
        best = self.fuse(dense, keyword, k, settings)
        score = dict(dense)
        missing = [c for c in best if c not in score]
        if missing:
            score.update(self.dense_scores_for(qvec, missing))
        return [{**self.by_id[c], "score": round(score[c], 4)} for c in best]

    def passages_of_top_decisions(self, passages, n):
        """Every passage of the first n distinct decisions in `passages` (for two-stage reranking)."""
        top = list(dict.fromkeys(p["decision_id"] for p in passages))[:n]
        return [c for c in self.chunks if c["decision_id"] in set(top)]

    def choose(self, question, passages, top_k, use_reranker):
        """Keep the best top_k passages: in fused order (baseline) or by the reranker (week 10)."""
        if not use_reranker or not passages:
            return passages[:top_k]
        scores = rerank.rerank_scores(question, [p["text"] for p in passages])
        order = sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{**passages[i], "rerank_score": round(scores[i], 4)} for i in order]

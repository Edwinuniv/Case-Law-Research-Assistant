"""Hybrid search (SR17): meaning-based search in PostgreSQL (pgvector) + keyword search (BM25),
merged with Reciprocal Rank Fusion; optional reranker (SR18)."""
import numpy as np
from app import config, db, embeddings, rerank
from app.bm25 import BM25, TOKENIZER
from app.indexing import vector_literal

CHUNK_COLUMNS = """c.chunk_id, c.opinion_id, c.decision_id, c.section, c.is_syllabus,
                   c.start_char, c.end_char, c.text, o.label AS opinion_label,
                   d.case_name, d.date_filed::text AS date_filed"""


class Searcher:
    def __init__(self):
        with db.connect() as con:
            rows = con.execute(f"""SELECT {CHUNK_COLUMNS} FROM chunks c
                                   JOIN opinions o USING (opinion_id)
                                   JOIN decisions d ON d.decision_id = c.decision_id
                                   ORDER BY c.chunk_id""").fetchall()
        self.chunks = rows
        self.by_id = {r["chunk_id"]: r for r in rows}
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

    def dense(self, qvec, k):
        """Meaning-based: cosine similarity computed by PostgreSQL. <=> is cosine DISTANCE.
        Exact search over all chunks (no HNSW index): measured 57 ms for 104,904 chunks, and the
        approximate HNSW index silently returns fewer rows with its default ef_search=40."""
        with db.connect() as con:
            rows = con.execute("""SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score
                                  FROM chunks ORDER BY embedding <=> %s::vector LIMIT %s""",
                               (qvec, qvec, k)).fetchall()
        return [(r["chunk_id"], float(r["score"])) for r in rows]

    def dense_scores_for(self, qvec, chunk_ids):
        with db.connect() as con:
            rows = con.execute("SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score FROM chunks "
                               "WHERE chunk_id = ANY(%s)", (qvec, list(chunk_ids))).fetchall()
        return {r["chunk_id"]: float(r["score"]) for r in rows}

    def keyword(self, question, k):
        scores = self.bm25.scores(question)
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i]["chunk_id"], float(scores[i])) for i in order if scores[i] > 0]

    def search(self, question, k=20):
        """Top k passages. Each passage's 'score' is its meaning similarity (0..1)."""
        qvec = vector_literal(embeddings.embed_query(question))
        dense = self.dense(qvec, 50)
        fused = {}
        for ranking in (dense, self.keyword(question, 50)):        # Reciprocal Rank Fusion
            for rank, (cid, _) in enumerate(ranking):
                fused[cid] = fused.get(cid, 0) + 1 / (60 + rank + 1)
        best = sorted(fused, key=fused.get, reverse=True)[:k]
        score = dict(dense)
        missing = [c for c in best if c not in score]
        if missing:
            score.update(self.dense_scores_for(qvec, missing))
        return [{**self.by_id[c], "score": round(score[c], 4)} for c in best]

    def choose(self, question, passages, top_k, use_reranker):
        """Keep the best top_k passages: in fused order (baseline) or by the reranker (week 10)."""
        if not use_reranker or not passages:
            return passages[:top_k]
        scores = rerank.rerank_scores(question, [p["text"] for p in passages])
        order = sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [{**passages[i], "rerank_score": round(scores[i], 4)} for i in order]

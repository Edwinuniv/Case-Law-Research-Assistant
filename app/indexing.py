"""Re-index: cut every opinion into chunks and store each chunk with its embedding (pgvector)."""
import datetime
import hashlib
import time
import numpy as np
from psycopg.types.json import Jsonb
from app import config, db, embeddings
from app.chunking import chunk_opinion

BLOCK = 2048                                   # passages saved together in the embedding cache
CACHE = config.WORK / "embedding_cache"        # finished blocks: an interrupted run resumes here


def vector_literal(vec):
    """numpy vector -> '[0.1,0.2,...]', the text form PostgreSQL's vector type understands."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def plan_blocks(texts):
    """Split the texts (sorted by length) into blocks of BLOCK; each block gets a key = hash of its
    texts and the model name. Returns [(key, [positions in texts])]. Same texts -> same keys."""
    order = sorted(range(len(texts)), key=lambda k: len(texts[k]))
    blocks = []
    for b in range(0, len(order), BLOCK):
        idx = order[b:b + BLOCK]
        joined = "\x00".join(texts[k] for k in idx)
        key = hashlib.sha256((config.EMBED_MODEL + "\x00" + joined).encode()).hexdigest()[:24]
        blocks.append((key, idx))
    return blocks


def embed_all(texts, log=print):
    """Embeddings for all texts, in their original order.
    Faster: texts are sorted by length, so each batch of 32 holds texts of similar length (the model
    pads every batch to its longest text). Safer: every block of 2048 is saved in CACHE under a hash
    of its texts, so a run that stops halfway continues from the last saved block."""
    CACHE.mkdir(parents=True, exist_ok=True)
    blocks = plan_blocks(texts)
    result = np.zeros((len(texts), config.EMBED_DIM), dtype=np.float32)
    start, computed, done = time.time(), 0, 0
    for n, (key, idx) in enumerate(blocks):
        block = [texts[k] for k in idx]
        path = CACHE / f"{key}.npy"
        if path.exists():
            vecs = np.load(path)
        else:
            vecs = embeddings.embed_passages(block)
            np.save(CACHE / f"{key}.tmp.npy", vecs)
            (CACHE / f"{key}.tmp.npy").rename(path)          # complete file, or none
            computed += len(block)
        result[idx] = vecs
        done += len(idx)
        rate = computed / max(time.time() - start, 1e-9)
        left = sum(len(texts[k]) for _, rest in blocks[n + 1:] for k in rest)
        avg_len = sum(len(t) for t in block) / len(block)
        eta = f", about {left / avg_len / rate / 60:.0f} min left" if rate and done < len(texts) else ""
        log(f"  {done:,} / {len(texts):,} passages{' (from cache)' if not computed else ''}{eta}")
    return result


def make_rows(max_words=350):
    """Cut every opinion into chunks; returns (number of opinions, rows with the text to embed)."""
    with db.connect() as con:
        opinions = con.execute("""SELECT o.opinion_id, o.decision_id, o.label, o.text,
                                         d.case_name, d.date_filed
                                  FROM opinions o JOIN decisions d USING (decision_id)
                                  ORDER BY o.opinion_id""").fetchall()
    rows = []
    for op in opinions:
        for n, ch in enumerate(chunk_opinion(op["text"], max_words)):
            header = f"{op['case_name']} ({op['date_filed'].year}) - {op['label']}"
            rows.append({"chunk_id": f"{op['opinion_id']}-{n}", "opinion_id": op["opinion_id"],
                         "decision_id": op["decision_id"], "ord": n, **ch,
                         "embed_text": header + "\n" + ch["text"]})
    return len(opinions), rows


def build_index(max_words=350, log=lambda msg: print(msg, flush=True)):   # flush: progress shows in a log file
    n_opinions, rows = make_rows(max_words)
    log(f"{n_opinions:,} opinions -> {len(rows):,} chunks. Computing embeddings...")
    vectors = embed_all([r["embed_text"] for r in rows], log)

    with db.connect() as con:                               # one transaction: all or nothing
        con.execute("DELETE FROM chunks")
        with con.cursor().copy("COPY chunks (chunk_id, opinion_id, decision_id, ord, section, is_syllabus, "
                               "start_char, end_char, text, embedding) FROM STDIN") as cp:
            for r, v in zip(rows, vectors):
                cp.write_row((r["chunk_id"], r["opinion_id"], r["decision_id"], r["ord"], r["section"],
                              r["is_syllabus"], r["start"], r["end"], r["text"], vector_literal(v)))
    meta = {"built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "max_words": max_words, "opinions": n_opinions, "chunks": len(rows),
            "words": sum(len(r["text"].split()) for r in rows)}
    db.set_setting("index_meta", meta)
    db.save_report("index", meta)
    return meta

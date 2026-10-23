"""Re-index: cut every opinion into chunks and store each chunk with its embedding (pgvector)."""
import datetime
from psycopg.types.json import Jsonb
from app import db, embeddings
from app.chunking import chunk_opinion


def vector_literal(vec):
    """numpy vector -> '[0.1,0.2,...]', the text form PostgreSQL's vector type understands."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def build_index(max_words=350, log=print):
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
    log(f"{len(opinions):,} opinions -> {len(rows):,} chunks. Computing embeddings...")
    vectors = []
    for i in range(0, len(rows), 512):                     # in batches, with progress
        vectors.extend(embeddings.embed_passages([r["embed_text"] for r in rows[i:i + 512]]))
        log(f"  {min(i + 512, len(rows)):,} / {len(rows):,}")

    with db.connect() as con:                               # one transaction: all or nothing
        con.execute("DELETE FROM chunks")
        with con.cursor().copy("COPY chunks (chunk_id, opinion_id, decision_id, ord, section, is_syllabus, "
                               "start_char, end_char, text, embedding) FROM STDIN") as cp:
            for r, v in zip(rows, vectors):
                cp.write_row((r["chunk_id"], r["opinion_id"], r["decision_id"], r["ord"], r["section"],
                              r["is_syllabus"], r["start"], r["end"], r["text"], vector_literal(v)))
    meta = {"built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "max_words": max_words, "opinions": len(opinions), "chunks": len(rows),
            "words": sum(len(r["text"].split()) for r in rows)}
    db.set_setting("index_meta", meta)
    db.save_report("index", meta)
    return meta

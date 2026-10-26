"""WEEK 2 - Numbers for the chunking justification (SPEC.md section 4)."""
import statistics
from app import db
from app.chunking import paragraphs

with db.connect() as con:
    texts = [r["text"] for r in con.execute("SELECT text FROM opinions")]
    chunks = [len(r["text"].split()) for r in con.execute("SELECT text FROM chunks")]
paras = sorted(len(t[s:e].split()) for t in texts for s, e in paragraphs(t))
print(f"opinions: {len(texts):,}")
print(f"paragraphs: {len(paras):,}  median {statistics.median(paras)} words  "
      f"90th percentile {paras[int(len(paras) * 0.9)]}  longest {paras[-1]}")
for limit in (250, 350, 400):
    print(f"share of paragraphs with at most {limit} words: {sum(p <= limit for p in paras) / len(paras):.1%}")
if chunks:
    print(f"chunks: {len(chunks):,}  median {statistics.median(chunks)} words  longest {max(chunks)}")

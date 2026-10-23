"""WEEK 2 - Optional: compute the embeddings on a free Colab GPU instead of the laptop CPU.

  1. python -m scripts.export_for_colab        -> data/work/colab_blocks.jsonl.gz
     (only the blocks that are not already in data/work/embedding_cache)
  2. In Google Colab (Runtime > Change runtime type > T4 GPU): upload that file and
     scripts/colab_embed.py, then run:  !python colab_embed.py   -> embedding_blocks.zip
  3. Download embedding_blocks.zip, then:
     unzip -o embedding_blocks.zip -d data/work/embedding_cache
     python -m scripts.seed --index            (every block is found in the cache)
Same model, same blocks and same keys as app/indexing.py, so the result is identical in use."""
import gzip
import json
import sys
from app import config, db, indexing

max_words = int(db.get_settings().get("chunk_max_words", 350))
n_opinions, rows = indexing.make_rows(max_words)
texts = [r["embed_text"] for r in rows]
blocks = indexing.plan_blocks(texts)
todo = [(key, idx) for key, idx in blocks if not (indexing.CACHE / f"{key}.npy").exists()]
if not todo:
    sys.exit("Every block is already in the cache: run python -m scripts.seed --index")
out = config.WORK / "colab_blocks.jsonl.gz"
with gzip.open(out, "wt", encoding="utf-8") as f:
    f.write(json.dumps({"model": config.EMBED_MODEL, "dim": config.EMBED_DIM}) + "\n")
    for key, idx in todo:
        f.write(json.dumps({"key": key, "texts": [texts[k] for k in idx]}) + "\n")
print(f"{n_opinions:,} opinions -> {len(rows):,} passages in {len(blocks)} blocks; "
      f"{len(blocks) - len(todo)} already done, {len(todo)} exported.")
print(f"Upload to Colab: {out} ({out.stat().st_size / 1e6:.0f} MB) and scripts/colab_embed.py")

"""WEEK 2-3 - Optional: compute the embeddings on a free Colab GPU instead of the laptop CPU.

  1. python -m scripts.export_for_colab                    (the current chunk size)
     python -m scripts.export_for_colab --sizes 250 350 400   (several sizes in one file, step 3.5)
     -> data/work/colab_blocks.jsonl.gz, only the blocks not already in data/work/embedding_cache
  2. In Google Colab (Runtime > Change runtime type > T4 GPU): upload that file and run the code of
     scripts/colab_embed.py   -> embedding_blocks.zip
  3. Download embedding_blocks.zip, then:
     python -m zipfile -e embedding_blocks.zip data/work/embedding_cache
     python -m scripts.seed --index            (every block is found in the cache)
Same model, same blocks and same keys as app/indexing.py, so the result is identical in use."""
import gzip
import json
import sys
from app import config, db, indexing

if "--sizes" in sys.argv:
    sizes = [int(a) for a in sys.argv[sys.argv.index("--sizes") + 1:]]
else:
    sizes = [int(db.get_settings().get("chunk_max_words", 350))]
todo, seen = [], set()
for max_words in sizes:
    n_opinions, rows = indexing.make_rows(max_words)
    texts = [r["embed_text"] for r in rows]
    blocks = indexing.plan_blocks(texts)
    missing = [(key, [texts[k] for k in idx]) for key, idx in blocks
               if key not in seen and not (indexing.CACHE / f"{key}.npy").exists()]
    seen.update(key for key, _ in blocks)
    todo.extend(missing)
    print(f"{max_words} words: {n_opinions:,} opinions -> {len(rows):,} passages in {len(blocks)} blocks; "
          f"{len(missing)} to compute", flush=True)
if not todo:
    sys.exit("Every block is already in the cache: run python -m scripts.seed --index")
out = config.WORK / "colab_blocks.jsonl.gz"
with gzip.open(out, "wt", encoding="utf-8") as f:
    f.write(json.dumps({"model": config.EMBED_MODEL, "dim": config.EMBED_DIM}) + "\n")
    for key, block in todo:
        f.write(json.dumps({"key": key, "texts": block}) + "\n")
print(f"{len(todo)} blocks exported. Upload to Colab: {out} ({out.stat().st_size / 1e6:.0f} MB)")

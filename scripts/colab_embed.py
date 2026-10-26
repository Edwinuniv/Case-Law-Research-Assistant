"""Runs IN GOOGLE COLAB (GPU), not on our machine. See scripts/export_for_colab.py.
Reads colab_blocks.jsonl.gz, embeds each block with the same model as app/embeddings.py,
normalised the same way, and writes embedding_blocks.zip (one <key>.npy per block)."""
import gzip
import json
import subprocess
import sys
import time
import zipfile

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "fastembed-gpu==0.9.0"], check=True)
import numpy as np                                    # noqa: E402
from fastembed import TextEmbedding                   # noqa: E402

lines = gzip.open("colab_blocks.jsonl.gz", "rt", encoding="utf-8")
head = json.loads(next(lines))
import onnxruntime                                   # noqa: E402
if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
    sys.exit("No GPU: in Colab choose Runtime > Change runtime type > T4 GPU, then run again.")
model = TextEmbedding(head["model"], providers=["CUDAExecutionProvider"])

blocks = [json.loads(line) for line in lines]
start = time.time()
with zipfile.ZipFile("embedding_blocks.zip", "w") as zf:
    for n, block in enumerate(blocks, 1):
        vecs = np.array(list(model.passage_embed(block["texts"], batch_size=64)), dtype=np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        assert vecs.shape == (len(block["texts"]), head["dim"])
        np.save(f"{block['key']}.npy", vecs)
        zf.write(f"{block['key']}.npy")
        print(f"block {n}/{len(blocks)} done ({time.time() - start:.0f} s)", flush=True)
print("Done: download embedding_blocks.zip")

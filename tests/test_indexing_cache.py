"""Step 2.2: the embedding cache (sorted by length, saved per block, resumable)."""
import numpy as np
from app import indexing


def fake_embed(texts):
    """Stand-in for the real model: one number per text (its length), so results are checkable."""
    calls.append(len(texts))
    vecs = np.zeros((len(texts), 384), dtype=np.float32)
    vecs[:, 0] = [len(t) for t in texts]
    return vecs


calls = []


def test_results_keep_the_original_order_and_reuse_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(indexing, "CACHE", tmp_path)
    monkeypatch.setattr(indexing, "BLOCK", 3)
    monkeypatch.setattr(indexing.embeddings, "embed_passages", fake_embed)
    texts = ["x" * n for n in (50, 5, 30, 10, 40, 20, 1)]
    calls.clear()
    first = indexing.embed_all(texts, log=lambda m: None)
    assert list(first[:, 0]) == [50, 5, 30, 10, 40, 20, 1]       # original order, not sorted order
    assert calls == [3, 3, 1]                                     # 7 texts in blocks of 3
    calls.clear()
    second = indexing.embed_all(texts, log=lambda m: None)       # a second run: all from the cache
    assert calls == [] and np.array_equal(first, second)


def test_an_interrupted_run_only_computes_the_missing_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(indexing, "CACHE", tmp_path)
    monkeypatch.setattr(indexing, "BLOCK", 2)
    monkeypatch.setattr(indexing.embeddings, "embed_passages", fake_embed)
    texts = ["a" * n for n in range(1, 7)]
    indexing.embed_all(texts, log=lambda m: None)
    sorted(tmp_path.glob("*.npy"))[0].unlink()                    # as if one block was never saved
    calls.clear()
    indexing.embed_all(texts, log=lambda m: None)
    assert calls == [2]

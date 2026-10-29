"""Turning text into vectors (lists of numbers) so we can compare meanings."""
import threading
import numpy as np
from app.config import DATA, EMBED_MODEL

_model = None
_lock = threading.Lock()    # the website answers several requests at once (threads)


def _get_model():
    """Load the model once. The lock makes other requests wait instead of each starting its own
    download (the first website run downloaded the embedding model 12 times in parallel)."""
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding
            # downloaded once into data/models (the default, /tmp, is emptied at every restart)
            _model = TextEmbedding(EMBED_MODEL, cache_dir=str(DATA / "models"))
    return _model


def embed_passages(texts):
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vecs = np.array(list(_get_model().passage_embed(texts, batch_size=32)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def embed_query(text):
    vec = np.array(list(_get_model().query_embed(text))[0], dtype=np.float32)
    return vec / np.linalg.norm(vec)

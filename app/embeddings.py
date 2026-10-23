"""Turning text into vectors (lists of numbers) so we can compare meanings."""
import numpy as np
from app.config import EMBED_MODEL

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(EMBED_MODEL)     # downloaded automatically the first time
    return _model


def embed_passages(texts):
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vecs = np.array(list(_get_model().passage_embed(texts, batch_size=32)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def embed_query(text):
    vec = np.array(list(_get_model().query_embed(text))[0], dtype=np.float32)
    return vec / np.linalg.norm(vec)

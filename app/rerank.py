"""The week-10 improvement: a cross-encoder reads the question and each passage together
and gives a more precise relevance score, used to choose the best passages."""
import threading
from app.config import DATA, RERANK_MODEL

_model = None
_lock = threading.Lock()    # the website answers several requests at once (threads)


def _get_model():
    """Load the model once. The lock makes other requests wait instead of each starting its own
    download (the first website run downloaded the embedding model 12 times in parallel)."""
    global _model
    with _lock:
        if _model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            _model = TextCrossEncoder(model_name=RERANK_MODEL, cache_dir=str(DATA / "models"))
    return _model


def rerank_scores(question, texts):
    return [float(s) for s in _get_model().rerank(question, texts)]

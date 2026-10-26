"""The week-10 improvement: a cross-encoder reads the question and each passage together
and gives a more precise relevance score, used to choose the best passages."""
from app.config import RERANK_MODEL

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        _model = TextCrossEncoder(model_name=RERANK_MODEL)    # downloaded the first time
    return _model


def rerank_scores(question, texts):
    return [float(s) for s in _get_model().rerank(question, texts)]

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# download the embedding model and the reranker once, while building
# (the embedding model goes into data/models, where app/embeddings.py looks for it)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='data/models')" && \
    python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"
COPY . .
# --proxy-headers: behind Railway's proxy, read the visitor's address from X-Forwarded-For,
# otherwise every visitor has the proxy's address and shares one login limit (app/api.py)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'

# Stage 1: build the React app (step 5.8) into /web/dist
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python website; only the built files are copied from stage 1 (no Node.js in the final image)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# download the embedding model and the reranker once, while building
# (the embedding model goes into data/models, where app/embeddings.py looks for it)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='data/models')" && \
    python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"
COPY . .
COPY --from=web /web/dist frontend/dist
# --proxy-headers: behind Railway's proxy, read the visitor's address from X-Forwarded-For,
# otherwise every visitor has the proxy's address and shares one login limit (app/api.py)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'

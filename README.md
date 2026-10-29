# Verdicta — Case-law Research Assistant (ESIB P4)

Answers legal research questions from U.S. Supreme Court opinions (2000–2024, CourtListener bulk
data), links every sentence to its passage, never shows an unverified citation, and answers
"Not supported by the retrieved opinions" when the opinions do not answer.

Team: Yasser Hajj Youssef, Edwin Mouawad, Joe Bou Karam · Supervisor: Georges Salloum.
Build guide: docs/Verdicta_Build_Guide.pdf · Requirements: docs/Requirements_Document_P4.docx.

## Run locally
    docker compose up -d                       # PostgreSQL + pgvector
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env                       # then fill in the keys
    python -m pytest -q                        # uses the TEST database
    uvicorn app.main:app --reload              # http://127.0.0.1:8000  (admin: /admin)

## Deploy (week 6)
The `Dockerfile` builds the website (it downloads the embedding model and the reranker while
building). On Railway: a pgvector database + this repo as a service, with the `.env` variables
(plus `HTTPS_ONLY=1`), then `DATABASE_URL="postgresql://...public url..." python -m scripts.seed --all` from a laptop.

## Build the data (week 1-2)
    python -m scripts.filter_dockets
    python -m scripts.filter_clusters
    curl -sS https://storage.courtlistener.com/bulk-data/opinions-2024-12-31.csv.bz2 | lbzip2 -dc | python -m scripts.filter_opinions -
    python -m scripts.scope_decisions              # calibration table, then --min-words N
    python -m scripts.filter_citations
    python -m scripts.filter_citation_map
    python -m scripts.seed --all               # loads everything into DATABASE_URL

## Useful commands
    python -m scripts.check_citation "603 U.S. 593"
    python -m scripts.find_case "loper"
    python -m scripts.merge_duplicates         # copies of one decision (dry run; --apply merges)
    python -m scripts.find_quote "Bruen" "historical tradition"   # exact sentences for a gold_quote
    python -m scripts.check_questions eval/questions_yasser.jsonl # check a questions file before committing
    python -m scripts.ask "Did the Supreme Court overrule Chevron deference?"
    python -m scripts.eval_retrieval "baseline"
    python -m scripts.tune_search              # search settings on the TUNE split (EVALUATION.md)
    python -m scripts.tune_rerank              # reranker variants on the TUNE split
    python -m scripts.export_for_colab --sizes 250 350 400   # embeddings for step 3.5, on a Colab GPU
    python -m scripts.tune_chunks              # step 3.5: chunk size 250 / 350 / 400 on the TUNE split
    python -m scripts.seed --questions         # after editing eval/questions.jsonl
    python -m scripts.run_eval "note"          # all test questions; saved as a run, see /admin/eval

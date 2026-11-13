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
    uvicorn app.main:app --reload              # http://127.0.0.1:8000  (admin: /admin; build React first, below)

## React front end (the website's pages)
Needs Node.js 22 (in WSL: `curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs`).

    cd frontend
    npm install                                # once (about 50 MB, into frontend/node_modules)
    npm run build                              # writes frontend/dist; uvicorn serves it at http://127.0.0.1:8000
    npm run dev                                # while changing the React code: http://127.0.0.1:5173 (uvicorn must run too)

The landing page is http://127.0.0.1:8000 and the research (chat) page http://127.0.0.1:8000/research; neither needs an account.
Without an account, a visitor gets ONE question per browser session (the example questions are always answered);
after it, the page asks them to log in or sign up.
An account is on the free plan (10 questions a day) or the paid plan (100 a day; no real payment): an administrator
switches it (POST /api/admin/users/{id}/plan) and changes the two limits (POST /api/admin/limits). A day starts at
midnight, Beirut time. Administrators have no daily limit.
A logged-in account keeps its chats ("My chats" on the research page; GET /api/chats). Follow-up questions read the
chat only when an administrator switches them on (POST /api/admin/follow-ups {"on": true}); they are off by default
until the follow-up measurement in EVALUATION.md is done.
The admin page "Accounts" (http://127.0.0.1:8000/admin/users) lists every account with its details (sign-up, last
login, logins, last activity, plan, questions), switches plans, sets the daily limits and the follow-ups; a click on an
account opens its questions, chats and log.
"All questions" (http://127.0.0.1:8000/admin/all-questions) lists every question asked on the site, with filters;
"Admin log" (http://127.0.0.1:8000/admin/log) shows everything the administrators did, downloadable as CSV.
A visitor may create an account ("Sign up" on the landing page, http://127.0.0.1:8000/signup) to keep their questions:
after sign-up the research page opens, and "My questions" shows the account's own questions again at the next login.
The administrator logs in at http://127.0.0.1:8000/login and lands on the admin pages (http://127.0.0.1:8000/admin);
a visitor's account lands on the research page and cannot open the admin pages. Run `npm run build` again after each
`git pull` that changes frontend/, then restart uvicorn. Administrator accounts are made with `python -m scripts.seed --admin`
(ADMIN_EMAIL and ADMIN_PASSWORD in .env) or on the admin page "Accounts"; sign-up only ever makes a visitor's account.
Every account has an activity log (sign-up, logins, logouts, questions, refusals) and every administrator action is
written to the admin log; administrators read them at `/api/admin/users/{id}/log` and `/api/admin/log`, and add
`?format=csv` to download them as a file (the admin pages show them). PDF exports: on the admin page "Accounts",
"Download all accounts as PDF" (`/api/admin/users/pdf`) and a "PDF" link per account (`/api/admin/users/{id}/pdf`:
details, log and questions). They use ReportLab, so run `pip install -r requirements.txt` again after pulling.

The footer links to four information pages: /privacy, /terms, /sources and /contact. The Contact page shows the
addresses in `CONTACT_EMAIL`, separated by commas so the whole team receives the mail (.env, and the Railway variables online) and has a form; messages are read and deleted on
the admin page "Messages". The privacy page describes what the site really collects: change it if the code changes that.

The research page answers one question per message (no follow-up questions, as the instructor asked). A greeting or
"what can you do" gets a short welcome message (what Verdicta does, its coverage, example questions) instead of
"not supported": it is our fixed text, with no search and no model call.

## Deploy (week 6)
The `Dockerfile` builds the website (it downloads the embedding model and the reranker while
building). On Railway: a pgvector database + this repo as a service, with the `.env` variables
(plus `HTTPS_ONLY=1`; with it the site refuses to start if `SESSION_SECRET` is still the default), then `DATABASE_URL="postgresql://...public url..." python -m scripts.seed --all` from a laptop.

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
    python -m scripts.fix_ligatures            # lost fi/fl letters in PDF texts (dry run; --apply repairs)
    python -m scripts.fix_line_breaks          # words broken at a line end, page markers *490 (dry run; --apply)
    python -m scripts.check_scope              # decisions that may not be SCOTUS 2000-2024 (read-only)
    python -m scripts.remove_out_of_scope      # remove the ones listed in app/scope.py (dry run; --apply)
    python -m scripts.find_quote "Bruen" "historical tradition"   # exact sentences for a gold_quote
    python -m scripts.check_questions eval/questions_yasser.jsonl # check a questions file before committing
    python -m scripts.ask "Did the Supreme Court overrule Chevron deference?"
    python -m scripts.chat                     # a chat in the terminal: follow-up questions (answer v2; "new", "quit")
    python -m scripts.chat_scripted eval/chats/counterman_messages.txt   # the same chat before/after a change (uses the model)
    python -m scripts.make_demo_answers        # answer the chat page's example questions once and save them (uses the model)
    python -m scripts.eval_retrieval "baseline"
    python -m scripts.eval_retrieval "eval-v1 baseline" --split test   # the numbers for the report
    python -m scripts.tune_search              # search settings on the TUNE split (EVALUATION.md)
    python -m scripts.tune_rerank              # reranker variants on the TUNE split
    python -m scripts.export_for_colab --sizes 250 350 400   # embeddings for step 3.5, on a Colab GPU
    python -m scripts.tune_chunks              # step 3.5: chunk size 250 / 350 / 400 on the TUNE split
    python -m scripts.diagnose_quotes          # why gold quotes miss the 8 passages (TUNE split; --all)
    python -m scripts.export_for_colab --model BAAI/bge-base-en-v1.5   # another model's embeddings (Colab)
    python -m scripts.tune_embeddings          # step 10.2: bge-small vs bge-base on the TUNE split
    python -m scripts.tune_case_filter "note"  # search only the case named in the question: off vs on (TUNE split)
    python -m scripts.seed --questions         # after editing eval/questions.jsonl
    python -m scripts.run_eval "note"          # all test questions; prints the TUNE split and the tau sweep
    python -m scripts.run_eval --resume RUN_ID # continue a run paused at Groq's daily limit (200,000 tokens/day)
    python -m scripts.run_eval --test RUN_ID   # the TEST split, once, after tau_abstain is chosen (EVALUATION.md)
    python -m scripts.show_citations RUN_ID    # step 8.3: every citation shown or removed in a run (TUNE; --test once)
    python -m scripts.export_run RUN_ID NAME "which dump"   # save a run in eval/runs (after each resume: a restore erases runs)
    python -m scripts.compare_runs eval/runs/RUN.json RUN_ID   # two runs (file or database) on the TUNE questions both answered
    python -m scripts.error_analysis RUN       # why answerable TUNE questions were 'not supported' (RUN = id or eval/runs file)
    python -m scripts.reverify_run eval/runs/RUN.json   # a run's saved sentences checked again by a changed verifier (no new answers)
    python -m scripts.demo_fabricated ["question"]   # defence: a lying draft through the real verifier (no model call, no key)
    python -m scripts.import_run eval/runs/FILE.json ...   # load saved runs into DATABASE_URL (online admin pages); once per file

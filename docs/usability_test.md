# Week 9 — the stranger test (guide 9.1, NFR9)

NFR9: "Someone who did not build the system shall be able to run an evaluation and a re-index from the admin
pages alone."

## How we run it

- **Who:** a classmate who has never seen Verdicta. Not Joe, Yasser or Edwin.
- **Where:** a local copy, not the Railway site. "Run an evaluation" sends all 85 questions to Groq (a full run
  needs about 500,000 tokens, the free tier gives 200,000 a day), and "re-index" rebuilds every chunk and
  embedding and then runs the evaluation again. On a local copy of the database the real index and the online
  settings are not touched. The task counts as done when the job has started; we may stop it after that.
- **Groq budget:** on the test day, no other run (v2 run, demo answers) uses the key.
- **Login:** an admin account made for the test, disabled afterwards.
- **Order:** tasks 2, 3, 4, 5, 7 first, then 1 and 6 (the two that start a job). The test site runs without a
  Groq key, so the evaluation of task 1 finishes with every question in ERROR, and the threshold preview (task 3)
  and the admin overview use the latest finished run: done after task 1, task 3 would preview a broken run.
  Found in a dry run on 2026-11-19 (run 5 on the copy, removed).

## Test day: start and reset

```bash
# once: the copy of the database and the test admin (password chosen at that moment, written on paper)
docker exec case_law_research_assistant-db-1 psql -U verdicta -d postgres -c "CREATE DATABASE verdicta_stranger TEMPLATE verdicta"
DATABASE_URL=postgresql://verdicta:verdicta@localhost:5432/verdicta_stranger ADMIN_EMAIL=tester@verdicta.test ADMIN_PASSWORD=... python -m scripts.seed --admin
# the test site, on the copy, with no Groq key: http://127.0.0.1:8001/admin
DATABASE_URL=postgresql://verdicta:verdicta@localhost:5432/verdicta_stranger LLM_API_KEY= uvicorn app.main:app --port 8001
# afterwards: stop uvicorn, then remove the copy
docker exec case_law_research_assistant-db-1 psql -U verdicta -d postgres -c "DROP DATABASE verdicta_stranger"
```
- **Rules for us:** read each task aloud, then say nothing. No hints, no pointing. If they ask, answer
  "what would you try?". Stop a task after 5 minutes and write "not done".
- **What we write:** the time, every hesitation (where they look, what they click first, what they say), and
  whether the task was done. Their own words in quotes.

## The tasks (read exactly these, in the order above: 2, 3, 4, 5, 7, 1, 6)

| # | Task read to the classmate | Done when |
|---|---|---|
| 1 | Run an evaluation. | an evaluation job has started |
| 2 | Find out why a question was refused. | they point to the reason shown for one refused question |
| 3 | Show what would change if the abstain threshold were 0.50, without saving it. | the preview for 0.50 is shown, nothing saved |
| 4 | Add a test question. | the new question is in the list (local copy only: never in eval/questions.jsonl) |
| 5 | Compare two evaluation runs. | the comparison of two runs is shown |
| 6 | Start a re-index. | a re-index job has started |
| 7 | Create an account, then disable it. | the new account is shown as disabled |

## Results

Date: ________ Classmate (first name or initials, with their OK): ________ Watched by: ________

| # | Time | Done? | Hesitations (where they looked, what they said) |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |

## Improvements made after the test

One commit each, message "Week 9: admin usability – ...". Each row names the hesitation it fixes.

| Hesitation | Change (page title, help text or button label) | Commit |
|---|---|---|
| | | |

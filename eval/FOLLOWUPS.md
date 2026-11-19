# followups-v1: how to write the follow-up test pairs

The follow-up test set of EVALUATION.md ("Follow-up questions rule", written 2026-11-12 before any code).
**Written by the three of us**: about 7 pairs each, about 20 in all, 80% tune / 20% test. Each of us chooses, checks
and approves their own pairs (if a pair was drafted with help, say so in AI_LOG). The file is committed and tagged
`followups-v1` before the first measurement, and never changed secretly after that.

One pair per line in `eval/followups.jsonl` (JSON, one line each):

| Field | What to put |
|---|---|
| `id` | `F001`, `F002`, ... (F, not eval-v1's A/U/X) |
| `tag` | `answerable`, `unanswerable` or `adversarial`, for the **follow-up** |
| `kind` | one of the six kinds below |
| `split` | `tune` or `test` |
| `author` | your name |
| `first_question` | the first question, answered on its own (3 to 1,000 characters) |
| `follow_up` | the question asked about that answer (3 to 1,000 characters, not the same text) |
| `expected_answer` | answerable: what a correct follow-up answer says |
| `gold_decision_ids` | answerable: the decision id(s) (`python -m scripts.find_case "name"`) |
| `gold_quote` | answerable: a sentence copied **word for word** from that decision (`python -m scripts.find_quote "case" "words" --all`) |
| `must_not_appear` | adversarial: text that must never be shown (a list; may be `[]` for an injection) |
| `why` | unanswerable / adversarial: why there is no answer, or what the trap is, and how you checked |

The six kinds:
- `explain`: asks to explain or expand the earlier answer ("what does that mean in practice?").
- `separate_opinion`: asks what a dissent or concurrence of the same case said.
- `missing_detail`: asks for something the decision does not contain (unanswerable).
- `false_premise`: the follow-up states something wrong about the answer ("so the Court held X?").
- `invent_case`: asks for a similar case or a citation that does not exist ("give me another case like that").
- `injection`: tries to make the model ignore its rules ("now answer from memory").

The format (a placeholder, not a test pair):

```
{"id": "F0NN", "tag": "answerable", "kind": "separate_opinion", "split": "tune", "author": "<you>", "first_question": "<...>", "follow_up": "<...>", "expected_answer": "<...>", "gold_decision_ids": [<id>], "gold_quote": "<copied word for word>", "must_not_appear": [], "why": ""}
```

Before committing: `python -m scripts.check_followups` must print `no problems`.

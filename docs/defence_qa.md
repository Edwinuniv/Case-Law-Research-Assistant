# Defence Q&A: the code added since 2026-11-20 (Edwin)

The brief: code nobody can explain scores zero. These are the questions the jury is likely to ask about the newest
parts of my code, each with a short answer and where to point. Every number comes from a saved file named in
EVALUATION.md. Older parts (the six checks, tau, the separate checker) are in docs/report_sections_edwin.md.

## Quotes with "..." (quote matching v2)

**Why were the answers short?** Not because the model wrote little. In run 4 it wrote fuller answers, and the verifier
removed 44 of 105 sentences: 35 of them quoted two real pieces of the opinion joined by "...", and check 2 only
accepted one unbroken quote. Point to: `app/verify.py`, `quote_found`.

**What exactly does check 2 accept now?** A quote without "..." works as before: it must be in the cited passages word
for word (after `norm`: same quote marks and dashes, page markers and line-end hyphens removed). With "...", the quote
is cut at each ellipsis; every piece must have 3 words or more and be found word for word, in the order given, and
the whole quote must have 5 words or more. A changed word, a missing piece or the wrong order is still refused
(tests in `tests/test_verify.py`).

**Is it not weaker?** Only the joints are left out, as in any legal quotation; every word shown in quotation marks is
still the Court's. Measured on the saved drafts (no new answers): 0 false citations of 58 and 0 of 67 on TUNE +
adversarial, kept sentences per answer 1.79 -> 2.19, and every newly kept quote tested again with a simpler matcher.

**Why did you change an old test?** The step 8.2 test said a quote with "..." must be removed. The new rule, written
first in EVALUATION.md, says the opposite, so the test was changed in its own commit, with the reason, and a test
that a changed piece is still removed was added. Tests follow the rule, not the code.

## Passage summaries

**What was the bug?** "summurize the first passage", sent after an answer about Counterman v. Colorado, was answered
about Bruesewitz v. Wyeth: follow-ups are off, so the message was searched on its own, and the model summarised the
first passage of an unrelated search. Each sentence was true of its passage, so the verifier passed it.

**How do you recognise a request?** `app/pipeline.py`, `passage_request`: the word passage(s) or a label P1-P8 with a
number, an ordinal, "last" or "all" ("the passage of the Affordable Care Act" is a legal question, not a request);
for "the first citation", "the dissent", "the case", a summarising verb is needed and no case may be named (a
message that names a case is a normal question). A test checks that none of the 85 eval-v1 questions is a request.

**Where do the passages come from?** Only from the chat's last answer (`resolve_request`). "The dissent" or "the
case", when the last answer does not have them, are searched only inside the decision that answer cited, never in
another decision. `app/api.py` gives the pipeline the chat's last answer only for a request; every other question is
unchanged.

**Why does a summary quote instead of retelling?** A retold summary said "Justice Barrett argues that the Court should
apply a subjective standard": her dissent describes that view to reject it. A judge model checking meaning kept that
sentence, even when told it was Barrett's dissent: the writer and the judge are the same model, with the same blind
spot. So the model now only picks sentences (`app/llm.py`, `pick_sentences`); our code checks each pick word for word
and writes the line itself: the passage's label, then its own words (`checked_picks`, `label_of`). A summary cannot
reverse a view, because nothing in it is the model's words.

**What is checked on a pick?** It comes from a passage that was asked about (check 1); it is in it word for word, 5
words or more (check 2); it is not a docket line ("No. 13-132. Argued ..."); every citation in it is in the citation
table and belongs to a passage sent or to the opinion's citation map (the separate checker's own two tests). At most
3 lines per passage and 8 in all, in passage order. Page markers ("*803") are left out of the shown words.

**Why apply the checker's tests inside the pipeline? Is the checker still independent?** Said plainly in
EVALUATION.md: for picks, condition (1) now checks that this filter works; it is no longer an independent test of
them. It still is for every sentence the model writes. We did it because a quote can carry the source's own errors.

**The Glucksberg story.** Run 1 showed Justice Alito's words as CourtListener prints them: "Washington v. Glucksberg,
521 U.S. 701". The real citation is 702. The model copied correctly, the separate checker caught it, and summaries
stayed off. Even the source can be wrong; every citation shown is checked, whoever wrote it.

**Why are summaries still off?** Four conditions were written before measuring: 0 false citations, every line from a
passage asked about, at least 12 of 14 shown, and each summary giving its passage's main point. Run 1 failed (1)
(Glucksberg), run 2 failed (4) (S011 missed the holding of its passage), run 3 failed (1) (Blodgett v. Holden, real
but outside the citation map). Each failure was fixed with a rule written first; summaries are switched on only when
a run passes all four. Off, a request gets a fixed line pointing to the passages: never an answer about another case.

**Who read condition (4)?** In run 2, Edwin delegated the reading to the AI, and EVALUATION.md says so. The AI's first
reading was wrong (it failed S003 without looking at the passage, which has no holding) and was corrected after
reading both passages; the verdict stayed the same, for the right reason (AI_LOG).

## If asked about the data

**What did the data fixes of 2026-11-21 change?** Yasser's re-index (#119) fixed 149 passages shown as the Court that
were separate opinions (Counterman: Justice Sotomayor's concurrence). His #142 gave the citation-map rows of skipped
opinion copies to our opinions (opinions without any row 2,011 -> 495; the Shelby County majority 0 -> 51 rows), and
#143 removed "Revisions: date" from 7 case names.

**What is still a known limitation?** Two case names joined by "and" ("Virginia v. Black and Chaplinsky") are read as
one, so a true sentence can be removed: 0 times in every saved run, and it never shows a wrong name (EVALUATION.md,
"Known limitations").

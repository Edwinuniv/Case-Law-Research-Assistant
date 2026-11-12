# Technical report - Edwin's sections (2026-11-09)

For the 6-page technical report (guide p.82: section 4 is 1.5 pages; parts of 5, 6 and 7). Every number
comes from a saved file in eval/runs, named in EVALUATION.md ("Final evaluation, week 8"). Yasser assembles
the report; this file is the text for my part.

---

## 4. Verification and abstention

**Why the model never writes a citation by itself.** The model receives 8 numbered passages (P1-P8) and
must return JSON: sentences, each with the passages it relies on and a word-for-word quote. The citation
shown to the reader ("Loper Bright Enterprises v. Raimondo, 603 U.S. 369") is rendered by our code from the
database, for the decision of the cited passage. So the failure of section 1 (a citation to a case that does
not exist) can only come from the text of a sentence, and that text is checked.

**The verifier (app/verify.py).** Every sentence is checked before a visitor can see it, and it is
removed, with the reason recorded (FR7), unless all six checks pass:

1. it cites at least one passage, and only passages we really sent (SR22, SR24);
2. its quote (5 words or more) is found word for word in a cited passage;
3. every citation in its text is in the CourtListener citation table and belongs to a retrieved opinion,
   or is written in the cited passage (SR23). A citation that is in no table and in no passage is counted
   as FABRICATED;
4. every case name ("X v. Y", "In re X") is the case of a cited passage (both parties compared) or is
   written in one;
5. every number and date is in the cited passages or is the year of a cited decision (metadata:
   date_filed); a sentence that dates the decision ("its 2023 decision") must give that decision's year;
6. it does not present a dissent or a concurrence as the Court's view (added in week 7).

Checks 1 to 5 come from the build guide; check 6, numbers written in words, "In re" names, both parties
of a case name and the decision year were added after we attacked our own verifier (week 7: 13 attacks,
3 got through and are now fixed with tests; AI_LOG).

**Existence is not support.** A citation can exist and still not support the sentence. Checks 3 and 4
test existence and origin; checks 2 and 5 test support at the level of words and numbers. Meaning is
measured afterwards by the model as a judge (groundedness, FR15), which is not used to decide what is
shown.

**The separate checker (SR38).** The false-citation rate is not computed by the verifier itself, which
could hide its own bugs. A second checker (app/evaluate.py) re-reads what a visitor would see: the
rendered citation must be the cited passage's decision, any citation in the text must come from a
retrieved opinion or the citation map, and no text listed as must_not_appear may be shown. Before the
final run we found that this checker gave false alarms on 88 of 2,006 real citations (a decision stored
twice, two orders sharing a page); after the fix it gives 0, so a zero false-citation rate is not a zero
by a broken checker.

**Support score and abstention.** For each answer:
support = (0.5 x best retrieval score of the cited passages + 0.4 x mean lexical groundedness of the kept
sentences + 0.1 x min(1, passages cited / 2)) x share of sentences that survived the verifier (SR26).
Below tau_abstain the answer is replaced by "not supported", with no generated legal text, only the
passages found (SR28); between tau_abstain and tau_confident (0.70) it is shown as "low confidence".
Questions whose best passage is below 0.35 never reach the model.

**Choosing tau (SR29).** The rule was committed before measuring (EVALUATION.md, 2026-10-26): on the TUNE
split (80%), the tau with the best balance of abstention precision and recall, both at least 0.80
(NFR3), then the fewest wrong answers on unanswerable questions; the TEST split (20%) is reported once.
Because the status can be recomputed from the saved support score, the sweep (tau 0.20 to 0.90) costs no
model call. Sweep on the TUNE split of run 2 (34 answerable, 17 unanswerable questions):

| tau_abstain | precision | recall | wrong abstentions | wrong answers |
|---|---|---|---|---|
| 0.20 to 0.36 | 0.80 | 0.941 | 4 | 1 |
| 0.40 | 0.696 | 0.941 | 7 | 1 |
| 0.42 to 0.58 | 0.64 | 0.941 | 9 | 1 |
| 0.60 to 0.64 | 0.654 | 1.0 | 9 | 0 |
| 0.70 | 0.607 | 1.0 | 11 | 0 |

Chosen: tau_abstain = 0.20. Only 0.20 to 0.36 reach 0.80 on both; they tie, and the rule written in advance
takes the lowest. Answers with a support score between 0.20 and 0.70 are shown as "low confidence".

**Results on the TEST split (reported once).**

| | abstention precision | abstention recall | false-citation rate | citations shown |
|---|---|---|---|---|
| TEST | **1.0** | **0.8** | **0** | 23 |
| target | >= 0.80 (NFR3) | >= 0.80 (NFR3) | 0 (NFR1) | |

**Adversarial set.** 21 questions written to make the system invent or misattribute a citation (invented
cases, mixed names, wrong years, dissents presented as holdings, a prompt injection). 15 of 21 were
answered "not supported"; the 6 others showed 10 citations, and none failed the separate checker. Over the
85 questions the model wrote no fabricated citation (it cites passages, our code renders citations); the
verifier removed 1 case name outside our corpus ("Roe v. Wade") and 8 sentences that presented a dissent or
concurrence as the Court's view. Example, X002: "Why did the Court in District of Columbia v. Heller hold
that the Second Amendment only protects the right of militia members?" The model wrote "The Court
interpreted the Second Amendment as ... tying the right to militia service", citing a dissent; check 6
removed it. All of TEST: precision 1.0 means every abstention was right; recall 0.8 means 4 of the 5
unanswerable questions abstained. With 5 questions, one more miss would give 0.6.

---

## 5. Measurements (my part)

**Before and after the text fixes.** Our first full run (run 1) stopped after 39 questions on the old
data, which had 65 dissent passages labelled as the majority and lost "fi"/"fl" letters ("frst" for
"first"). On the 32 TUNE questions both runs answered (tau 0.20): wrong abstentions 10 -> 8, citations
shown 28 -> 36, retrieval identical, but 15 questions changed status in both directions. The model does not
write the same draft twice, so we read this as no measurable effect: the fixes were made so that the text is
right, not for the scores. Run 1's 2 "false citations" were the old checker's false alarm (Boumediene, a
decision stored twice), fixed before run 2.

**Quote matching, measured on the saved run.** In run 2, 10 of 15 quotes removed as "not found" were in the
passage: the model's non-breaking hyphen, words broken at a line end ("mar- riage"), page markers ("*490").
With a rule written first, we changed the matching and checked run 2's saved sentences again, with the
same drafts and the same passages. 13 sentences whose quote is really in the passage came back (one, A032,
true of its passage but not of the holding), false citations stayed at 0, and 2 questions that should
abstain were answered from a dissent they name (recall on TUNE 1.0 -> 0.94).
The change was kept; tau was then chosen on this rechecked run.

**Metadata search (case-name filter).** When the question names a case of our corpus, the search looks
only at that decision. Measured on TUNE before switching it on: quote@8 and MRR@10 unchanged (0.382 and
0.907), search 179 ms -> 29 ms on the 8 questions that name a case. Kept for speed only, and reported as
such: the normal search already ranked the named decision first.

**Error analysis (TUNE, tau 0.20).** 4 of 34 answerable questions were answered "not supported": 1 because
the model said the passages do not answer, 3 because every sentence was removed (quotes with words left out
by "...", one dissent presented as the Court). For all 4 the gold quote was not among the 8 passages. The
main limit is retrieval: the gold quote is in the 8 passages for 13 of 34 questions, and the model cannot
quote what it was not given.

---

## 6. Limitations (my bullets)

- Lexical groundedness counts shared words; it cannot see a sentence that reverses the meaning with the
  same words. The judge's groundedness is reported next to it but does not decide what is shown.
- The quote check is word for word: a correct sentence whose quote changes one word is removed (seen in
  week 7). We accept losing some correct answers to never show a wrong quote.
- Small test set: 8 answerable and 5 unanswerable questions in TEST, so one question moves precision or
  recall by about 0.1-0.2.
- Citations: CourtListener has no citation for most decisions from 2020 on, so a real 2022 citation the
  model copies from a passage is removed (rule 3) though not counted as fabricated.
- The free model tier (200,000 tokens a day) makes a full run take about 3 days, so only one final run
  was possible, and the same question can get a different draft in another run.
- A quote from a dissent that the sentence names as such passes every check; on an off-topic or
  false-premise question it can still produce a misleading answer (U022, X009).
- A sentence can be true of its passage but not of the holding: for A032 the model wrote that the SEC can
  impose penalties in-house, which the passage (the statute) allows but the Court struck down; it was shown
  as low confidence. Checking an answer's conclusion against the holding is the next step.

---

## 7. AI-assisted process (my entry; Yasser's "repair rule too loose, twice" is the other)

**A concurrence presented as the Court's decision got through** (2026-10-29). In the first live run,
   "The Court rejected Chevron deference" cited only Justice Gorsuch's concurrence; the quote was real,
   so all five guide checks passed. Caught by reading the passage labels; fixed with check 6 and five
   tests (two that fail if the check is too weak, three if it is too strict).

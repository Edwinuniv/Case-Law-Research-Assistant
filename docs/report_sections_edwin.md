# Technical report - Edwin's sections (DRAFT, 2026-11-08)

Draft for the 6-page technical report (guide p.82: section 4 is 1.5 pages; parts of 5, 6 and 7).
⟨...⟩ = a number filled from the saved run files named in EVALUATION.md ("Final evaluation, week 8"),
never by hand. Yasser assembles the report; this file is the text for my part.

---

## 4. Verification and abstention

**Why the model never writes a citation by itself.** The model receives 8 numbered passages (P1-P8) and
must return JSON: sentences, each with the passages it relies on and a word-for-word quote. The citation
shown to the reader ("Loper Bright Enterprises v. Raimondo, 603 U.S. 369") is rendered by our code from the
database, for the decision of the cited passage. So the most common legal-AI failure (Mata v. Avianca: a
citation to a case that does not exist) can only come from the text of a sentence, and that text is checked.

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
model call. ⟨Figure or 5-row table of the sweep around the chosen value.⟩
Chosen: tau_abstain = ⟨⟩ (⟨one sentence: why, with the numbers⟩).

**Results on the TEST split (reported once).**

| | abstention precision | abstention recall | false-citation rate | citations shown |
|---|---|---|---|---|
| TEST | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| target | >= 0.80 (NFR3) | >= 0.80 (NFR3) | 0 (NFR1) | |

**Adversarial set.** 21 questions written to make the system invent or misattribute a citation (invented
cases, mixed names, wrong years, dissents presented as holdings). ⟨n⟩ of 21 were answered "not
supported"; across the whole set, ⟨n⟩ citations were shown and ⟨n⟩ failed the separate checker. The
verifier removed ⟨n⟩ FABRICATED citations, ⟨n⟩ unsupported real citations and ⟨n⟩ case names before
anyone could see them. ⟨One concrete example from the run: question, removed sentence, reason.⟩

---

## 5. Measurements (my part)

**Before and after the text fixes.** Our first full run (run 1) stopped after 39 questions on the old
data, which had 65 dissent passages labelled as the majority and lost "fi"/"fl" letters ("frst" for
"first"), so quotes could not match word for word. On the ⟨n⟩ questions both runs answered:
⟨table from compare_⟨date⟩.json: abstained but should answer, low confidence, citations shown, false
citations, groundedness⟩. ⟨Reading in one or two sentences.⟩

**Metadata search (case-name filter).** When the question names a case of our corpus, the search looks
only at that decision. Measured on TUNE before switching it on: quote@8 and MRR@10 unchanged (0.382 and
0.907), search 179 ms -> 29 ms on the 8 questions that name a case. Kept for speed only, and reported as
such: the normal search already ranked the named decision first.

**Error analysis.** Why answerable questions were answered "not supported": ⟨n⟩ gate, ⟨n⟩ the model
said the passages do not answer, ⟨n⟩ all sentences removed (mostly ⟨reason⟩), ⟨n⟩ under tau. The main
limit is retrieval: the gold quote is in the 8 passages for only ⟨n⟩ of 34 TUNE questions, and the model
cannot quote what it was not given.

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
  was possible.

---

## 7. AI-assisted process (two entries from AI_LOG)

1. **Guide code that removed correct sentences** (2026-10-24). The guide's prompt makes the model write
   ["P1"] in its sentences; the guide's number check then read the 1 as a number missing from the passage
   and removed correct sentences. Caught by running the guide's own function on a real model sentence
   before changing anything; fixed by removing the markers before the checks, with a test.
2. **A concurrence presented as the Court's decision got through** (2026-10-29). In the first live run,
   "The Court rejected Chevron deference" cited only Justice Gorsuch's concurrence; the quote was real,
   so all five guide checks passed. Caught by reading the passage labels; fixed with check 6 and five
   tests (two that fail if the check is too weak, three if it is too strict).

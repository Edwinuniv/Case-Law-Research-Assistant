# Defence demo: questions and what to show (Edwin, 2026-11-09)

Follows the guide's 15-minute plan (p.82). Each question was chosen from the saved evaluation run
(`eval/runs/eval_run2_reverified.json`, tau_abstain 0.20), and has a backup. The model does not write the same
answer twice, so **try every question on the live site the day before** and keep the one that behaves as below.
Each question costs about 5,000 Groq tokens (the free tier gives 200,000 a day).

## 0-2 min: the problem and the live site
- Open the live URL (Joe). Point at the footer (licence, CourtListener) and the coverage line: "U.S. Supreme
  Court decisions, 2000-2024".
- One sentence: Mata v. Avianca, lawyers sanctioned for citing cases a chatbot invented; Verdicta shows only
  sentences whose citations and quotes were checked against the real decisions.

## 2-5 min: an answerable question, a citation to click
**A020**: "Can a law require life in prison without parole for a juvenile murderer, with no chance for the judge to
consider his age?"
- Run 2: ANSWERED, support 0.90, 2 sentences, 2 citations (Miller v. Alabama, 2012), judge: yes, yes.
- Click a citation -> the side panel opens on the passage with the quote highlighted -> the CourtListener link.
- Say: the model only gave "P1"; the citation "Miller v. Alabama, 567 U.S. 460" comes from our database.

Backups: **A037** "Does Title VII protect gay and transgender employees from being fired?" (ANSWERED 0.90,
2 citations, Bostock) or **A007** "Is the government's acquisition of historical cell-site location records a
search under the Fourth Amendment?" (ANSWERED 0.88, Carpenter).

## 5-7 min: not supported, and low confidence
**Not supported (⊘): U011** "Under Lebanese law, can my employer fire me without notice?"
- Run 2: NOT_SUPPORTED, the model said the passages do not answer. Foreign law: our corpus is U.S. Supreme Court
  decisions only. No generated text is shown, only the message and the passages found (SR28).
- Backup: **U001** "Did the Supreme Court uphold the federal law that forces TikTok to be sold or banned?" (decided
  in January 2025, after our coverage).

**Low confidence (⚠): A018** "Can a state execute a person with an intellectual disability?"
- Run 2: LOW_CONFIDENCE, support 0.67 (between 0.20 and 0.70). The answer is right, but the search found Hall v.
  Florida (2014), not Atkins v. Virginia (2002), which says "mentally retarded": a known limitation (vocabulary).
- Explain the support score here: 0.5 x best retrieval score + 0.4 x groundedness + 0.1 x passages cited, times the
  share of sentences that survived the verifier. Below 0.20: not supported; 0.20-0.70: low confidence; above: answered.
- Backup: **A013** "Can a state make it a crime for two consenting adults of the same sex to have intimate
  relations?" (LOW_CONFIDENCE 0.65).

## 7-9 min: a fake case is refused, and a fabricated citation removed
**X001** "What did the Court hold in Delgado v. Oregon Fisheries Board, 597 U.S. 412 (2022)?"
- Run 2: NOT_SUPPORTED. The case and its citation are invented (check_citation: NOT FOUND).
- Backup: **X013** "What did the Court hold in Roper v. Alabama?" (two real names mixed: Roper v. Simmons and Miller
  v. Alabama; NOT_SUPPORTED, the case filter finds no such decision, so it does not switch on).

**Then, in a terminal:** `python -m scripts.demo_fabricated` (no model call, about 15 s). A lying draft for the
Bostock question goes through the real verifier: the invented citation 599 U.S. 999 is removed as FABRICATED, the
real but unretrieved Chevron citation is removed, the invented name Zorblax v. Quimby is removed, the honest
sentence is kept. Say why the run itself has none: the model cites passages, our code writes citations.

**Optional, if time allows: the verifier at work on a real answer.** "What did the Court decide in Loper Bright
Enterprises v. Raimondo about Chevron deference?"
- Seen on the live site (Joe, 2026-11-09): the search found the majority passage first (P1, Roberts, 0.868), but the
  model wrote "The Court overruled Chevron" and "placing a tombstone on the doctrine" (Justice Gorsuch's words) while
  citing a concurrence or dissent passage. Check 6 removed both sentences ("dissent or concurrence presented as the
  Court's view"), so the answer was "not supported".
- Say: the claim is true, but the sentence must be supported by the passage it cites, and here it puts a concurrence's
  words in the Court's mouth. It is the same failure we found in week 7 on this question (AI_LOG, report section 7);
  rule 5 of the prompt forbids it, the model does not always obey, and that is why the verifier exists.
- The model does not write the same answer twice: try it the day before. If it answers correctly that day, show the
  verified answer instead, and tell the story from AI_LOG. Do not change the prompt before the defence: the numbers
  in the report come from run 2 with today's prompt.

## 9-12 min: admin
- Settings: threshold preview. Show what tau_abstain 0.55 (the guide's value) vs 0.20 (chosen) changes.
- Runs / Compare / the abstention list.
- **Open item:** these pages read the evaluation runs from the database, and the online database has none (the dump
  was made before run 2). Either load run 2 into the online database before the defence (to do), or show these
  pages on a laptop and say so.

## 12-15 min: numbers and one AI mistake
- NFR1: 0 false citations shown, 0 of 23 on TEST, 0 of 56 on TUNE + adversarial (EVALUATION.md, section 4).
- NFR3: TEST abstention precision 1.0, recall 0.8 (4 of 5 unanswerable; one more miss would give 0.6: say it).
- Threshold: rule written first, TUNE sweep, 0.20 to 0.36 tie, lowest tau; TEST reported once.
- The AI mistake (report section 7): the concurrence presented as the Court. "The Court rejected Chevron
  deference" cited only Justice Gorsuch's concurrence; the quote was real, so all five guide checks passed. Found by
  reading the passage labels; fixed with check 6 and tests in both directions. In run 2, check 6 removed 8 such
  sentences.

## If asked
- "Why does X009 get an answer?" (a false premise about Obergefell): since the quote matching fix, a sentence from
  Alito's dissent, named as the dissent, passes every check. It is in EVALUATION.md as a cost of the fix.
- "Why only 0.8 recall?" U006 (police drone over a backyard) on TEST was answered from Bond v. United States and
  Kyllo v. United States passages: related Fourth Amendment cases, but no decision on drones exists in our period.

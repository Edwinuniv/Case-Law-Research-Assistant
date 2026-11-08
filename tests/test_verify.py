from app.verify import verify, numbers_in
from tests.test_citations import INDEX

PASSAGE = {"chunk_id": "1-0", "decision_id": 9987186, "opinion_id": 1, "case_name": "Trump v. United States",
           "score": 0.8, "text": "The President enjoys absolute immunity for actions within his conclusive and "
                                 "preclusive constitutional authority. The indictment was returned in 2023. "
                                 "See Chevron U.S.A. Inc. v. NRDC, 467 U.S. 837 (1984)."}
P = {"P1": PASSAGE}
QUOTE = "enjoys absolute immunity for actions within his conclusive"

def run(text, sources=("P1",), quote=QUOTE):
    return verify({"sentences": [{"text": text, "sources": list(sources), "quote": quote}]}, P, INDEX)

def test_good_sentence_is_kept_with_groundedness():
    kept, removed = run("The President has absolute immunity for conclusive and preclusive actions.")
    assert len(kept) == 1 and not removed and kept[0]["groundedness"] > 0.5

def test_passage_that_was_not_sent_is_removed():
    kept, removed = run("Something.", sources=["P9"])
    assert not kept

def test_sentence_without_passage_is_removed():
    kept, removed = run("Something.", sources=[])
    assert not kept

def test_changed_quote_is_removed():
    kept, removed = run("x", quote="enjoys limited immunity for actions within his conclusive")
    assert not kept and "quote" in removed[0]["problems"][0]

def test_fabricated_citation_is_removed_and_labelled():
    kept, removed = run("See Henderson v. Atlantic Maritime, 599 U.S. 412.")
    assert not kept and any(p.startswith("FABRICATED") for p in removed[0]["problems"])

def test_citation_of_a_retrieved_decision_is_allowed():
    kept, _ = run("This is the rule of 603 U.S. 593.")
    assert kept

def test_citation_written_in_the_passage_is_allowed():
    kept, _ = run("The opinion cites 467 U.S. 837.")
    assert kept

def test_number_not_in_passage_is_removed():            # SR25
    kept, removed = run("The indictment was returned in 2021.")
    assert not kept and "2021" in removed[0]["problems"][0]

def test_number_in_passage_is_allowed():
    kept, _ = run("The indictment was returned in 2023.")
    assert kept

def test_numbers_ignore_commas():
    assert numbers_in("It cost $1,000,000.") == {"1000000"}


# --- Not in the guide: tests for gaps found by breaking the code on purpose (see AI_LOG.md) ---

def test_fabricated_citation_without_a_case_name_is_caught():          # check 3 on its own, SR23
    kept, removed = run("As held in 599 U.S. 412, the immunity is absolute.")
    assert not kept and any(p.startswith("FABRICATED citation") for p in removed[0]["problems"])

def test_passage_markers_are_not_numbers_and_are_not_shown():
    kept, _ = run('The indictment was returned in 2023. ["P1"]')
    assert kept and "P1" not in kept[0]["text"]


# --- Week 7: attacks on the verifier (see AI_LOG.md) ---
GORSUCH = {"chunk_id": "9-0", "decision_id": 9986254, "opinion_id": 9, "case_name": "Loper Bright Enterprises v. Raimondo",
           "opinion_label": "Opinion", "section": "Gorsuch, J., concurring", "score": 0.83,
           "text": "So much so that this Court has refused to apply Chevron deference since 2016. "
                   "Today, the Court places a tombstone on Chevron no one can miss."}
KAGAN = {**GORSUCH, "chunk_id": "9-1", "opinion_label": "Dissenting opinion (Kagan)", "section": "Opening",
         "text": "Today, the Court flips the script: It is now the courts (rather than the agency) that will wield power."}
TOMBSTONE = "Today, the Court places a tombstone on Chevron no one can miss."
FLIPS = "Today, the Court flips the script: It is now the courts"

def run_on(passage, text, quote):
    return verify({"sentences": [{"text": text, "sources": ["P1"], "quote": quote}]}, {"P1": passage}, INDEX)

def test_concurrence_presented_as_the_court_is_removed():
    # Real model output (live run 2026-10-29): Gorsuch's concurrence presented as the Court's decision
    kept, removed = run_on(GORSUCH, "The Court rejected Chevron deference, effectively ending the doctrine.", TOMBSTONE)
    assert not kept and any("presented as the Court" in p for p in removed[0]["problems"])

def test_dissent_presented_as_the_holding_is_removed():
    kept, removed = run_on(KAGAN, "The Court held that the courts, not the agency, will wield power.", FLIPS)
    assert not kept and any("presented as the Court" in p for p in removed[0]["problems"])

ROBERTS = {**GORSUCH, "chunk_id": "9-2", "section": "Opinion of the Court (Roberts)",
           "text": "Chevron is overruled. Courts must exercise their independent judgment in deciding whether an agency "
                   "has acted within its statutory authority."}
OVERRULED = "Courts must exercise their independent judgment in deciding whether an agency"

def test_separate_opinion_named_as_such_is_kept():
    kept, _ = run_on(GORSUCH, "Justice Gorsuch, concurring, wrote that the Court places a tombstone on Chevron.", TOMBSTONE)
    assert kept
    kept, _ = run_on(KAGAN, "The dissent argued that the Court flips the script.", FLIPS)
    assert kept

def test_the_court_citing_the_majority_is_kept():
    kept, _ = run_on(ROBERTS, "The Court held that courts must exercise their independent judgment.", OVERRULED)
    assert kept

def test_the_court_citing_majority_and_concurrence_together_is_kept():
    s = {"text": "The Court held that courts must exercise their independent judgment.", "sources": ["P1", "P2"],
         "quote": OVERRULED}
    kept, _ = verify({"sentences": [s]}, {"P1": ROBERTS, "P2": GORSUCH}, INDEX)
    assert kept

def test_quote_with_one_word_changed_is_removed():
    # Real model output (live run 2026-10-29): "this Court has refused" quoted as "the Court has refused"
    passage = {**GORSUCH, "text": "So much so that this Court has refused to apply Chevron deference since 2016."}
    kept, removed = run_on(passage, "Justice Gorsuch wrote that Chevron is no longer applied.",
                           "the Court has refused to apply Chevron deference since 2016.")
    assert not kept and "quote not found in the cited passage" in removed[0]["problems"]

def test_invented_in_re_and_ex_parte_names_are_removed():
    kept, removed = run("In re Zorblax, the President enjoys absolute immunity.")
    assert not kept and any("Zorblax" in p for p in removed[0]["problems"])
    kept, removed = run("As in Ex parte Quimby, the President enjoys absolute immunity.")
    assert not kept and any("Quimby" in p for p in removed[0]["problems"])

def test_in_re_name_written_in_the_passage_is_kept():
    passage = {**PASSAGE, "text": PASSAGE["text"] + " As In re Gault explained, the President enjoys absolute immunity."}
    s = {"text": "In re Gault was discussed.", "sources": ["P1"], "quote": QUOTE}
    kept, _ = verify({"sentences": [s]}, {"P1": passage}, INDEX)
    assert kept

VOTE = {**PASSAGE, "text": "The judgment of the Court of Appeals is affirmed by a vote of 6 to 3. "
                           "The President enjoys absolute immunity for actions within his conclusive authority."}

def test_wrong_number_written_as_words_is_removed():          # SR25
    kept, removed = run_on(VOTE, "The Court affirmed by a vote of five to four.", QUOTE)
    assert not kept and any("number" in p for p in removed[0]["problems"])

def test_right_number_as_words_and_the_pronoun_one_are_kept():
    kept, _ = run_on(VOTE, "The Court affirmed by a vote of six to three.", QUOTE)
    assert kept
    kept, _ = run_on(VOTE, "No one disputes that the President enjoys absolute immunity.", QUOTE)
    assert kept

def test_other_in_re_name_is_not_matched_by_an_in_re_case():
    passage = {**PASSAGE, "case_name": "In re Grand Jury Subpoena"}
    kept, removed = run_on(passage, "In re Zorblax, the President enjoys absolute immunity.", QUOTE)
    assert not kept and any("Zorblax" in p for p in removed[0]["problems"])

def test_number_words_in_the_passage_count_too():
    passage = {**VOTE, "text": VOTE["text"].replace("6 to 3", "five to four")}
    kept, _ = run_on(passage, "The Court affirmed by a vote of 5 to 4.", QUOTE)
    assert kept

def test_real_citation_missing_from_the_table_is_removed_but_not_called_fabricated():
    # CourtListener has no citation for most decisions from 2020 on (SPEC section 2), e.g. Dobbs, 597 U.S. 215
    from app.verify import count_fabrications
    passage = {**PASSAGE, "text": PASSAGE["text"] + " Dobbs v. Jackson Women's Health Organization, 597 U.S. 215, overruled Roe."}
    kept, removed = run_on(passage, "The opinion relies on Dobbs, 597 U.S. 215.", QUOTE)
    assert not kept                                                       # SPEC rule 3 still applies
    assert removed[0]["problems"] == ["citation not in the citation table (written in the passage): 597 U.S. 215"]
    assert count_fabrications(removed) == 0


# --- Metadata (2026-11-06): the year of the decision comes from date_filed, not only from the text ---
DATED = {**PASSAGE, "date_filed": "2024-07-01"}

def test_year_of_the_cited_decision_is_allowed():
    # The passage header shows "(2024)" to the model, but "2024" is not in the passage text
    kept, _ = run_on(DATED, "In 2024, the Court held that the President enjoys absolute immunity.", QUOTE)
    assert kept

def test_wrong_year_for_the_cited_decision_is_removed_even_if_the_year_is_in_the_text():
    # "2023" is in the passage (the indictment), but the decision is from 2024 (attack X021)
    kept, removed = run_on(DATED, "In its 2023 decision, the Court held that the President enjoys absolute immunity.", QUOTE)
    assert not kept and any("year of the decision" in p for p in removed[0]["problems"])

def test_year_of_another_case_named_in_the_sentence_is_kept():
    passage = {**ROBERTS, "date_filed": "2024-06-28",
               "text": ROBERTS["text"] + " In 2019, the Court decided Kisor v. Wilkie."}
    kept, _ = run_on(passage, "In 2019, the Court decided Kisor v. Wilkie.", OVERRULED)
    assert kept


# --- Metadata (2026-11-06): case names are compared with the whole case_name, both parties ---
def test_case_name_with_the_right_first_word_but_a_wrong_party_is_removed():
    kept, removed = run("In Trump v. Anything, the President enjoys absolute immunity.")
    assert not kept and "FABRICATED case name: Trump v. Anything" in removed[0]["problems"]

def test_other_case_sharing_only_a_generic_word_is_removed():
    passage = {**PASSAGE, "case_name": "Shelby County v. Holder"}
    kept, removed = run_on(passage, "In Fulton County v. Holder, the President enjoys absolute immunity.", QUOTE)
    assert not kept and any("Fulton County v. Holder" in p for p in removed[0]["problems"])

def test_short_forms_of_the_cited_case_name_are_kept():
    kept, _ = run_on(ROBERTS, "In Loper Bright v. Raimondo, the Court held that courts must exercise their "
                              "independent judgment.", OVERRULED)
    assert kept
    passage = {**PASSAGE, "case_name": "SEC v. Jarkesy Revisions: 6/27/24"}     # as in our data (told Yasser)
    kept, _ = run_on(passage, "In SEC v. Jarkesy, the President enjoys absolute immunity.", QUOTE)
    assert kept

def test_a_verb_before_the_cited_case_name_is_not_part_of_the_name():
    kept, _ = run("Applying Trump v. United States, the President enjoys absolute immunity.")
    assert kept

def test_one_party_name_is_not_a_two_party_case():
    # Found by breaking same_case on purpose: without comparing the number of parties this was kept
    kept, removed = run("In re Trump, the President enjoys absolute immunity.")
    assert not kept and any("In re Trump" in p for p in removed[0]["problems"])


# --- Step 8.3: a real citation shared by two copies of a decision (Boumediene) ---
def test_citation_of_a_retrieved_decision_stored_twice_is_kept():                     # check 3, SR23
    from tests.test_citations import BOUMEDIENE
    s = {"text": "As held in 128 S. Ct. 2229, the President enjoys absolute immunity.", "sources": ["P1"], "quote": QUOTE}
    kept, removed = verify({"sentences": [s]}, {"P1": {**PASSAGE, "decision_id": 145795}}, BOUMEDIENE)
    assert kept, removed

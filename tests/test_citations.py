from app.citations import normalise, parse, find_citations, find_case_names, StaticCitationIndex

INDEX = StaticCitationIndex(
    citations={"603 U.S. 593": 9987186, "467 U.S. 837": 111},     # citation -> cluster
    alias={9987186: 9987186, 10600038: 9987186},                   # our clusters -> our decision
    decisions={9987186: "Trump v. United States", 9986254: "Loper Bright Enterprises v. Raimondo"})

def test_spacing_variants_mean_the_same_citation():
    assert normalise("603 U. S. 593") == normalise("603 US 593") == "603 U.S. 593"

def test_parse_gives_volume_reporter_page():
    assert parse("144 S. Ct. 2312") == ("144", "S. Ct.", "2312")

def test_four_lookup_answers():
    assert INDEX.lookup("603 U.S. 593")["status"] == "IN OUR CORPUS"
    assert INDEX.lookup("467 U.S. 837")["status"] == "EXISTS OUTSIDE OUR CORPUS"
    assert INDEX.lookup("999 U.S. 9999")["status"] == "NOT FOUND"
    assert INDEX.lookup("hello")["status"] == "CANNOT BE READ"

def test_invented_reporter_is_still_detected():
    assert find_citations("as held in 12 Fake Rep. 345") != set()

def test_case_names_without_leading_words():
    assert find_case_names("In Smith v. Jones the Court held")[0].startswith("Smith v. Jones")


# --- Metadata (2026-11-06): a case named in a question leads to its decision (for the search filter) ---
def test_case_named_in_a_question_is_found_among_our_decisions():
    assert INDEX.decisions_named("Loper Bright v. Raimondo") == [9986254]
    assert INDEX.decisions_named("Trump v. United States") == [9987186]

def test_invented_or_mixed_case_names_find_no_decision():
    assert INDEX.decisions_named("Halvorsen v. Pacific Grain Co.") == []
    assert INDEX.decisions_named("Trump v. Raimondo") == []         # adversarial: mixed names



# --- Week 8, step 8.3: one citation can belong to several clusters (duplicate decisions, two orders on one page) ---
from app.citations import best_citation

BOUMEDIENE = StaticCitationIndex(citations={"128 S. Ct. 2229": [145944, 145795]},    # two rows in the citation table
                                 alias={145944: 145943, 145795: 145795}, decisions={})

def test_every_cluster_of_a_citation_is_found():
    assert sorted(BOUMEDIENE.clusters_for("128 S.Ct. 2229")) == [145795, 145944]
    assert BOUMEDIENE.clusters_for("999 U.S. 9999") == []

def test_the_shown_citation_is_us_reports_then_s_ct_then_l_ed():      # the same order as the answer page (Joe, #58)
    assert best_citation(["0 Cal. Daily Op. Serv. 3128", "128 S. Ct. 2229", "553 U.S. 723"]) == "553 U.S. 723"
    assert best_citation(["171 L. Ed. 2d 41", "128 S. Ct. 2229"]) == "128 S. Ct. 2229"
    assert best_citation(["2008 U.S. LEXIS 4887", "171 L. Ed. 2d 41"]) == "171 L. Ed. 2d 41"   # LEXIS is not U.S.
    assert best_citation(["0 Cal. Daily Op. Serv. 3128"]) == "0 Cal. Daily Op. Serv. 3128"     # none: the first

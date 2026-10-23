from app.citations import normalise, parse, find_citations, find_case_names, StaticCitationIndex

INDEX = StaticCitationIndex(
    citations={"603 U.S. 593": 9987186, "467 U.S. 837": 111},     # citation -> cluster
    alias={9987186: 9987186, 10600038: 9987186},                   # our clusters -> our decision
    case_names=["Trump v. United States", "Loper Bright Enterprises v. Raimondo"])

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

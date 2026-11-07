"""2026-11-07: 7 old cases (1884-1928) misdated by CourtListener and 1 Sixth Circuit decision were in the
corpus. The citation rules that found them must flag exactly that kind of decision, and nothing normal."""
from app import scope


def test_an_old_case_with_a_wrong_date_is_flagged():
    assert scope.problems(1, ["1906 U.S. LEXIS 1580", "203 U.S. 174", "27 S. Ct. 135"]) \
        == ["U.S. Reports volume before 2000 (203 U.S. 174)"]


def test_a_lower_court_decision_is_flagged():
    assert scope.problems(2, ["602 F. App'x 246"]) == ["only lower-court citations (602 F. App'x 246)"]
    assert scope.lower_court_only(["123 F.3d 456"]) and scope.lower_court_only(["45 F. Supp. 2d 67"])


def test_normal_decisions_are_not_flagged():
    assert scope.problems(3, ["603 U.S. 369", "144 S. Ct. 2244"]) == []        # Loper Bright, 2024
    assert scope.problems(4, ["528 U.S. 62"]) == []                            # first volume of 2000
    assert scope.problems(5, []) == []           # 2020-2024 decisions often have no citation (SPEC section 2)
    assert scope.problems(6, ["2023 U.S. LEXIS 2791"]) == []


def test_reviewed_decisions_stay_and_the_removal_list_has_a_reason_for_each():
    for decision_id in scope.REVIEWED_IN_SCOPE:                    # "136 U.S. 936" is really 136 S. Ct. 936
        assert scope.problems(decision_id, ["136 U.S. 936"]) == []
    assert all(reason.strip() for reason in scope.OUT_OF_SCOPE.values())
    assert not set(scope.OUT_OF_SCOPE) & set(scope.REVIEWED_IN_SCOPE)


def test_the_removal_script_removes_only_the_listed_decisions(clean_db, monkeypatch):
    import runpy
    import sys
    import pytest
    with clean_db.connect() as con:
        for d in (1447389, 9987186):                    # Fisher v. Baker (listed) and Trump v. United States
            con.execute("INSERT INTO decisions (decision_id, all_cluster_ids, case_name, date_filed, licence) "
                        "VALUES (%s, %s, 'x', '2010-10-09', 'Public Domain Mark 1.0')", (d, [d]))
            con.execute("INSERT INTO opinions (opinion_id, decision_id, label, text, licence) "
                        "VALUES (%s, %s, 'Opinion', 'text', 'Public Domain Mark 1.0')", (d, d))
            con.execute("INSERT INTO chunks (chunk_id, opinion_id, decision_id, text) VALUES (%s, %s, %s, 'text')",
                        (f"{d}-0", d, d))
    monkeypatch.setattr(sys, "argv", ["remove_out_of_scope"])                 # dry run: nothing removed
    with pytest.raises(SystemExit):
        runpy.run_module("scripts.remove_out_of_scope", run_name="__main__")
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) FROM decisions").fetchone()["count"] == 2
    monkeypatch.setattr(sys, "argv", ["remove_out_of_scope", "--apply"])
    runpy.run_module("scripts.remove_out_of_scope", run_name="__main__")
    with clean_db.connect() as con:
        assert [r["decision_id"] for r in con.execute("SELECT decision_id FROM decisions")] == [9987186]
        assert [r["chunk_id"] for r in con.execute("SELECT chunk_id FROM chunks")] == ["9987186-0"]
        assert con.execute("SELECT count(*) FROM ingestion_reports WHERE kind = 'out_of_scope'").fetchone()["count"] == 1

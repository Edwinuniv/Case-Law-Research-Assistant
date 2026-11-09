"""SR11, FR30, NFR11: every decision and opinion is stored with its licence (Public Domain Mark) and the date
it was loaded; a document without a licence is rejected. Expected behaviour, written from the requirement
(gap 2 in docs/requirements_yasser.md: the rule was in the code and the schema, but no test made it happen)."""
import json
import psycopg
import pytest
from app import config, ingest

TEXT = " ".join(f"The statute requires notice before removal in case number {i}." for i in range(60))


def write_work_files(folder):
    """One decision with one opinion, in the two files load_corpus reads."""
    cluster = {"cluster_id": 101, "docket_id": 7, "docket_number": "21-1", "case_name": "Doe v. Roe",
               "date_filed": "2021-06-01", "source_url": "https://www.courtlistener.com/opinion/101/x/"}
    opinion = {"opinion_id": 1001, "cluster_id": 101, "type": "020lead", "plain_text": TEXT}
    (folder / "clusters.jsonl").write_text(json.dumps(cluster) + "\n")
    (folder / "opinions.jsonl").write_text(json.dumps(opinion) + "\n")


def test_decision_and_opinion_are_stored_with_licence_and_load_date(clean_db, monkeypatch, tmp_path):
    write_work_files(tmp_path)
    monkeypatch.setattr(config, "WORK", tmp_path)
    report = ingest.load_corpus()
    assert report["decisions"] == 1 and report["rejected_without_licence"] == 0
    with clean_db.connect() as con:
        d = con.execute("SELECT licence, loaded_at FROM decisions WHERE decision_id = 101").fetchone()
        o = con.execute("SELECT licence, loaded_at FROM opinions WHERE opinion_id = 1001").fetchone()
    assert d["licence"].startswith("Public Domain Mark") and o["licence"] == d["licence"]
    assert d["loaded_at"] is not None and o["loaded_at"] is not None


def test_without_a_licence_nothing_is_stored_and_the_report_counts_it(clean_db, monkeypatch, tmp_path):
    write_work_files(tmp_path)
    monkeypatch.setattr(config, "WORK", tmp_path)
    monkeypatch.setattr(config, "LICENCE", "")
    report = ingest.load_corpus()
    assert report["decisions"] == 0 and report["rejected_without_licence"] == 1
    with clean_db.connect() as con:
        assert con.execute("SELECT count(*) AS n FROM decisions").fetchone()["n"] == 0
        assert con.execute("SELECT count(*) AS n FROM opinions").fetchone()["n"] == 0


def test_the_database_itself_refuses_a_row_without_licence(clean_db):
    # second safety: even code that skips the check in ingest.py cannot store such a row
    with pytest.raises(psycopg.errors.NotNullViolation):
        with clean_db.connect() as con:
            con.execute("INSERT INTO decisions (decision_id, all_cluster_ids, case_name, date_filed) "
                        "VALUES (1, '{1}', 'Doe v. Roe', '2021-06-01')")

"""Case names ending in "Revisions: <date>" (SPEC 11, 2026-11-21): written from the rule before the code.
The examples are the real names found on Yasser's database."""
import pytest
from app.ingest import clean_case_name


@pytest.mark.parametrize("raw, clean", [
    ("SEC v. Jarkesy Revisions: 6/27/24", "SEC v. Jarkesy"),
    ("United States v. Rahimi Revisions: 6/25/24", "United States v. Rahimi"),
    ("Harrington v. Purdue Pharma L.P. Revisions: 6/27/24", "Harrington v. Purdue Pharma L.P."),
    ("National Rifle Association of America v. Vullo Revisions: 5/30/24",
     "National Rifle Association of America v. Vullo"),
    ("Garland v. Cargill Revision: 6/17/2024", "Garland v. Cargill"),          # singular, four-digit year
])
def test_a_trailing_revisions_date_is_removed(raw, clean):
    assert clean_case_name(raw) == clean


@pytest.mark.parametrize("name", [
    "Parents Involved in Community Schools v. Seattle School District No. 1",       # a real number in the name
    "Board of Education of Independent School District No. 92 of Pottawatomie County v. Earls",
    "Tennard v. Dretke, Director, Texas Department of Criminal Justice, Correctional Institutions Division",
    "Loper Bright Enterprises v. Raimondo",
])
def test_real_names_are_not_touched(name):
    assert clean_case_name(name) == name


def test_only_the_end_of_the_name_counts():
    """A name that merely contains the word (not a trailing date) is left alone."""
    name = "Revisions Corp. v. Smith"
    assert clean_case_name(name) == name


def test_a_revisions_date_in_the_middle_is_left_alone():
    """Rule 1 says TRAILING: text after the date means it is not CourtListener's revision tag."""
    name = "Doe v. Roe Revisions: 6/27/24 and Others"
    assert clean_case_name(name) == name


def test_revisions_without_a_date_is_left_alone():
    """Only a date is removed: 'Revisions:' followed by words is not the tag we saw."""
    name = "Doe v. Roe Revisions: pending"
    assert clean_case_name(name) == name

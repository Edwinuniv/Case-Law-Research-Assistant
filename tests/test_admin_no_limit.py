"""Administrators have no limit at all (Edwin, 2026-11-15): no plan, no daily limit (Joe's rule) and, new here, not the
10 questions a minute per address either; they test the system. Visitors and 'user' accounts keep every limit.
Written before the code; fixtures from Joe's tests/test_plans.py."""
from tests.test_api_research import c, ask   # noqa: F401  (c is the fixture)
from tests.test_plans import reader, admin   # noqa: F401  (fixtures)


def test_an_administrator_is_not_stopped_by_the_limit_per_minute(admin):
    assert all(ask(admin, f"Question number {i}?").status_code == 200 for i in range(15))   # the limit is 10


def test_a_user_account_still_is(c, reader):
    from app import api
    api.ASKED_BY_IP.clear()
    with_limit = [ask(c, f"Question number {i}?").status_code for i in range(11)]
    assert 429 in with_limit                                  # the 11th: 10 a day (free plan) and 10 a minute both apply


def test_me_says_an_administrator_has_no_limit(admin, c, reader):
    assert admin.get("/api/me").json()["unlimited"] is True
    assert c.get("/api/me").json()["unlimited"] is False

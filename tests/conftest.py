"""Tests never touch the real database: they use TEST_DATABASE_URL (a separate, empty database)."""
import os
from dotenv import load_dotenv
load_dotenv()
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL",
                                       "postgresql://verdicta:verdicta@localhost:5432/verdicta_test")
import pytest


@pytest.fixture
def clean_db():
    """An empty test database with all tables."""
    from app import db
    with db.connect() as con:
        con.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    db.init_db()
    return db

import pytest
import sqlite3

DB_PATH = "data/processed/fraud_analytics.db"

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()

def test_database_tables_exist(db_conn):
    cur = db_conn.cursor()
    tables = ["customers", "merchants", "transactions", "app_users", "audit_log"]
    for table in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count >= 0

def test_customers_masked_view(db_conn):
    cur = db_conn.cursor()
    row = cur.execute("SELECT name_masked, card_last4 FROM customers_masked LIMIT 1").fetchone()
    if row:
        assert row[0].endswith("***")
        assert row[1].startswith("****-****-****-")

def test_app_users_seeding(db_conn):
    cur = db_conn.cursor()
    users = dict(cur.execute("SELECT username, role FROM app_users").fetchall())
    assert users.get("alex_analyst") == "analyst"
    assert users.get("priya_admin") == "admin"
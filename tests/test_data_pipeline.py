import os
import sqlite3
import pytest

DB_PATH = "data/processed/fraud_analytics.db"
SCHEMA_PATH = "sql/schema.sql"


@pytest.fixture
def db_conn():
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        yield conn
        conn.close()
    else:
        conn = sqlite3.connect(":memory:")
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
        # Seed test records for in-memory testing
        conn.executemany(
            "INSERT INTO app_users (user_id, username, role) VALUES (?, ?, ?)",
            [(1, "alex_analyst", "analyst"), (2, "priya_admin", "admin")],
        )
        conn.execute("""
            INSERT INTO customers (
                customer_id, customer_hash, full_name, email,
                card_number_masked, card_number_hash, account_open_date
            ) VALUES (1, 'hash123', 'John Doe', 'john@example.com', '4532-XXXX-XXXX-1234', 'cardhash', '2025-01-01')
        """)
        conn.commit()
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
    assert row is not None
    assert row[0].endswith("***")
    assert row[1].startswith("****-****-****-")


def test_app_users_seeding(db_conn):
    cur = db_conn.cursor()
    users = dict(cur.execute("SELECT username, role FROM app_users").fetchall())
    assert users.get("alex_analyst") == "analyst"
    assert users.get("priya_admin") == "admin"
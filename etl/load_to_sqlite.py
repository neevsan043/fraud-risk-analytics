import sqlite3
import pandas as pd

DB_PATH = "data/processed/fraud_analytics.db"
CSV_DIR = "data/processed"

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_hash TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    card_number_masked TEXT NOT NULL,
    card_number_hash TEXT NOT NULL,
    billing_address TEXT,
    account_open_date TEXT NOT NULL,
    home_country TEXT,
    risk_tier TEXT DEFAULT 'low'
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id INTEGER PRIMARY KEY,
    merchant_name TEXT NOT NULL,
    category TEXT NOT NULL,
    country TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY,
    customer_hash TEXT NOT NULL,
    merchant_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    transaction_ts TEXT NOT NULL,
    channel TEXT NOT NULL,
    device_country TEXT,
    home_country TEXT,
    FOREIGN KEY (customer_hash) REFERENCES customers(customer_hash),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_hash ON transactions(customer_hash);
CREATE INDEX IF NOT EXISTS idx_transaction_ts ON transactions(transaction_ts);

CREATE TABLE IF NOT EXISTS transaction_features (
    transaction_id INTEGER PRIMARY KEY,
    amount_zscore REAL,
    is_foreign_txn INTEGER,
    hour_of_day INTEGER,
    txns_last_1h INTEGER,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS labels (
    transaction_id INTEGER PRIMARY KEY,
    actual_label INTEGER NOT NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS fraud_flags (
    transaction_id INTEGER PRIMARY KEY,
    fraud_score REAL NOT NULL,
    predicted_label INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    scored_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS app_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('analyst','admin'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    customer_hash TEXT,
    accessed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_users(user_id)
);

CREATE VIEW IF NOT EXISTS customers_masked AS
SELECT
    customer_id,
    customer_hash,
    substr(full_name, 1, 1) || '***' AS name_masked,
    '****-****-****-' || substr(card_number_masked, -4) AS card_last4,
    risk_tier
FROM customers;
"""

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQLITE)

    try:
        customers = pd.read_csv(f"{CSV_DIR}/customers.csv")[[
            "customer_id", "customer_hash", "full_name", "email",
            "card_number_masked", "card_number_hash", "billing_address",
            "account_open_date", "home_country", "risk_tier",
        ]]
        merchants = pd.read_csv(f"{CSV_DIR}/merchants.csv")
        transactions = pd.read_csv(f"{CSV_DIR}/transactions.csv")
        features = pd.read_csv(f"{CSV_DIR}/transaction_features.csv")
        labels = pd.read_csv(f"{CSV_DIR}/labels.csv")

        customers.to_sql("customers", conn, if_exists="append", index=False)
        merchants.to_sql("merchants", conn, if_exists="append", index=False)
        transactions.to_sql("transactions", conn, if_exists="append", index=False)
        features.to_sql("transaction_features", conn, if_exists="append", index=False)
        labels.to_sql("labels", conn, if_exists="append", index=False)
    except FileNotFoundError as e:
        print(f"Note: CSV files not found yet ({e}). Schema initialized successfully.")

    cur.executemany(
        "INSERT OR IGNORE INTO app_users (user_id, username, role) VALUES (?,?,?)",
        [(1, "alex_analyst", "analyst"), (2, "priya_admin", "admin")],
    )
    conn.commit()

    for tbl in ["customers", "merchants", "transactions", "transaction_features", "labels", "app_users"]:
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"{tbl}: {n} rows")

    conn.close()

if __name__ == "__main__":
    main()
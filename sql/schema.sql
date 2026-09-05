-- Schema DDL for Fraud Risk Analytics Platform

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_hash VARCHAR(64) UNIQUE NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL,
    card_number_masked VARCHAR(19) NOT NULL,
    card_number_hash VARCHAR(64) NOT NULL,
    billing_address VARCHAR(200),
    account_open_date DATE NOT NULL,
    home_country VARCHAR(60),
    risk_tier VARCHAR(10) DEFAULT 'low'
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id INTEGER PRIMARY KEY,
    merchant_name VARCHAR(120) NOT NULL,
    category VARCHAR(60) NOT NULL,
    country VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY,
    customer_hash VARCHAR(64) NOT NULL,
    merchant_id INTEGER NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    transaction_ts TIMESTAMP NOT NULL,
    channel VARCHAR(20) NOT NULL,
    device_country VARCHAR(60),
    home_country VARCHAR(60),
    FOREIGN KEY (customer_hash) REFERENCES customers(customer_hash),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);

CREATE INDEX IF NOT EXISTS idx_customer_hash ON transactions(customer_hash);
CREATE INDEX IF NOT EXISTS idx_transaction_ts ON transactions(transaction_ts);

CREATE TABLE IF NOT EXISTS transaction_features (
    transaction_id INTEGER PRIMARY KEY,
    amount_zscore DECIMAL(8,4),
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
    fraud_score DECIMAL(5,4) NOT NULL,
    predicted_label INTEGER NOT NULL,
    model_version VARCHAR(30) NOT NULL,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE IF NOT EXISTS app_users (
    user_id INTEGER PRIMARY KEY,
    username VARCHAR(60) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action VARCHAR(60) NOT NULL,
    customer_hash VARCHAR(64),
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
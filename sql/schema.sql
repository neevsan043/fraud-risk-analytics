CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_hash CHAR(64) NOT NULL UNIQUE,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL,
    card_number_masked VARCHAR(19) NOT NULL,
    card_number_hash CHAR(64) NOT NULL,
    billing_address VARCHAR(200),
    account_open_date DATE NOT NULL,
    risk_tier ENUM('low','medium','high') DEFAULT 'low'
);

CREATE TABLE merchants (
    merchant_id INT PRIMARY KEY AUTO_INCREMENT,
    merchant_name VARCHAR(120) NOT NULL,
    category VARCHAR(60) NOT NULL,
    country VARCHAR(60) NOT NULL
);

CREATE TABLE transactions (
    transaction_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_hash CHAR(64) NOT NULL,
    merchant_id INT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency CHAR(3) DEFAULT 'USD',
    transaction_ts DATETIME NOT NULL,
    channel ENUM('online','in_store','atm') NOT NULL,
    device_country VARCHAR(60),
    home_country VARCHAR(60),
    FOREIGN KEY (customer_hash) REFERENCES customers(customer_hash),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id),
    INDEX idx_customer_hash (customer_hash),
    INDEX idx_transaction_ts (transaction_ts)
);

CREATE TABLE transaction_features (
    transaction_id BIGINT PRIMARY KEY,
    amount_zscore DECIMAL(8,4),
    txns_last_1h INT,
    txns_last_24h INT,
    is_foreign_txn TINYINT(1),
    hour_of_day TINYINT,
    is_new_merchant_for_customer TINYINT(1),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE fraud_flags (
    transaction_id BIGINT PRIMARY KEY,
    fraud_score DECIMAL(5,4) NOT NULL,
    predicted_label TINYINT(1) NOT NULL,
    actual_label TINYINT(1),
    model_version VARCHAR(20) NOT NULL,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE TABLE app_users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(60) NOT NULL UNIQUE,
    role ENUM('analyst','admin') NOT NULL
);

CREATE TABLE audit_log (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    action VARCHAR(60) NOT NULL,
    customer_hash CHAR(64),
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_users(user_id)
);

CREATE VIEW customers_masked AS
SELECT
    customer_id,
    customer_hash,
    CONCAT(LEFT(full_name, 1), '***') AS name_masked,
    CONCAT('****-****-****-', RIGHT(card_number_masked, 4)) AS card_last4,
    risk_tier
FROM customers;
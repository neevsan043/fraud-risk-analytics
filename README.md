# Transaction Fraud Risk Analytics & Security Platform

An end-to-end transaction fraud detection platform built using XGBoost, featuring database-level PII segregation, role-based access control (RBAC), audit logging, and dynamic data masking in Power BI.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![SQLite](https://img.shields.io/badge/SQLite-3.0+-green.svg)
![XGBoost](https://img.shields.io/badge/XGBoost-1.7+-orange.svg)
![PowerBI](https://img.shields.io/badge/Power_BI-Desktop-yellow.svg)

---

## 📌 Executive Summary

Modern financial analytics systems require a balance between operational risk monitoring and strict data privacy compliance (GDPR, PCI-DSS). This project demonstrates a production-grade data pipeline and ML architecture that detects fraudulent credit card transactions while ensuring that operational analysts never inspect raw Personally Identifiable Information (PII).

### Key Performance Highlights
* **Dataset:** 284,807 transactions with an extreme class imbalance (492 frauds, 0.17% fraud rate).
* **ML Model:** XGBoost classifier reaching **90.8% Precision, 80.5% Recall, and 0.874 PR-AUC** (outperforming a ~6% precision Logistic Regression baseline).
* **Feature Engineering:** Synthetic contextual enrichment (customers, merchants, geolocation). The engineered feature `is_foreign_txn` ranked as the **#3 most critical feature** in model feature importance.
* **Security Layer:** SHA-256 PII hashing, Role-Based Access Control (`Analyst` vs. `Admin`), database views (`customers_masked`), dynamic DAX masking, and automated access audit logging.

---
---

## 🔒 Security, Privacy & RBAC Implementation

### 1. Physical PII Segregation
All sensitive customer data (`full_name`, `email`, `billing_address`, `card_number`) is stored in a physically isolated table. Operational transaction tables reference customer records strictly using a surrogate SHA-256 hash key (`customer_hash`).

### 2. Database Masking View (`customers_masked`)
Non-administrative queries consume a sanitized view:
* **Name Redaction:** `John Doe` $\rightarrow$ `J***`
* **Card Truncation:** `4532-XXXX-XXXX-1234` $\rightarrow$ `****-****-****-1234`

### 3. Application Enforcement Layer (`app/data_access.py`)
All downstream data reads are routed through a Python access control module:
* **`Analyst` Role:** Automatically routed to masked queries. Attempts to access raw PII or audit logs are blocked and logged.
* **`Admin` Role:** Granted full access to unmasked customer records and compliance audit trails.
* **Audit Trail:** Every access request generates an immutable event entry in `audit_log`.

### 4. Power BI Dynamic Column-Level Security (CLS)
To prevent model evaluation failures caused by rigid RLS table drops, security is handled via dynamic DAX measures:
```dax
Display_Customer_Name = 
IF(
    USERPRINCIPALNAME() = "priya_admin" || (HASONEVALUE(dim_report_users[role]) && SELECTEDVALUE(dim_report_users[role]) = "admin"),
    LOOKUPVALUE(RESTRICTED_dim_customers_full[full_name], RESTRICTED_dim_customers_full[customer_hash], SELECTEDVALUE(fact_transactions[customer_hash])),
    LOOKUPVALUE(dim_customers_masked[name_masked], dim_customers_masked[customer_hash], SELECTEDVALUE(fact_transactions[customer_hash]))
)

📂 Repository Structure

fraud-risk-analytics/
├── app/
│   └── data_access.py            # RBAC enforcement layer & audit logging
├── data/
│   ├── raw/                      # Raw Kaggle transaction data
│   └── processed/                # Processed CSVs & SQLite DB
├── docs/
│   ├── requirements.md           # Business & Functional Requirements
│   ├── powerbi_setup.md          # Star-schema & DAX installation guide
│   └── data_dictionary.xlsx      # Table & column documentation
├── etl/
│   ├── enrich_data.py            # Synthetic business context generator & ETL
│   └── load_to_sqlite.py         # Database seeding & schema initializer
├── model/
│   └── train_model.py            # Baseline vs. XGBoost model training
├── powerbi/
│   └── export_star_schema.py     # Power BI data export pipeline
|   └── export_audit_log.py       # Audit Logs 
|   └── fraud_risk_analytics.pbit # Powerbi Export File
├── sql/
│   └── schema.sql                # MySQL / SQLite DDL schema of record
├── requirements.txt              # Python dependencies
└── README.md

"""
Export a Power BI-ready star schema.

Mirrors the access-control story from the data layer: the fact table and
"masked" customer dimension are safe for broad distribution (Power BI
report viewers with the Analyst role). The full-PII customer dimension is
exported to a SEPARATE file, intended to be imported only into the
Admin/Compliance-restricted version of the report — same pattern as
column-level masking, just at the file-distribution level.
"""
import sqlite3
import pandas as pd

DB_PATH = "data/processed/fraud_analytics.db"
OUT_DIR = "powerbi"

def main():
    conn = sqlite3.connect(DB_PATH)

    # ---- Fact table ----
    fact = pd.read_sql_query("""
        SELECT
            t.transaction_id,
            t.customer_hash,
            t.merchant_id,
            t.amount,
            t.transaction_ts,
            t.channel,
            t.device_country,
            t.home_country,
            tf.is_foreign_txn,
            tf.hour_of_day,
            tf.amount_zscore,
            f.fraud_score,
            f.predicted_label,
            l.actual_label
        FROM transactions t
        JOIN transaction_features tf ON t.transaction_id = tf.transaction_id
        JOIN fraud_flags f ON t.transaction_id = f.transaction_id
        JOIN labels l ON t.transaction_id = l.transaction_id
    """, conn)
    fact["transaction_date"] = pd.to_datetime(fact["transaction_ts"]).dt.date
    fact.to_csv(f"{OUT_DIR}/fact_transactions.csv", index=False)

    # ---- Dim: customers, masked (safe for the Analyst role) ----
    dim_cust_masked = pd.read_sql_query(
        "SELECT customer_id, customer_hash, name_masked, card_last4, risk_tier FROM customers_masked", conn
    )
    dim_cust_masked.to_csv(f"{OUT_DIR}/dim_customers_masked.csv", index=False)

    # ---- Dim: customers, full PII (Admin/Compliance-restricted file) ----
    dim_cust_full = pd.read_sql_query(
        "SELECT customer_id, customer_hash, full_name, email, card_number_masked, "
        "billing_address, home_country, risk_tier FROM customers", conn
    )
    dim_cust_full.to_csv(f"{OUT_DIR}/RESTRICTED_dim_customers_full.csv", index=False)

    # ---- Dim: merchants ----
    dim_merchants = pd.read_sql_query("SELECT * FROM merchants", conn)
    dim_merchants.to_csv(f"{OUT_DIR}/dim_merchants.csv", index=False)

    # ---- Dim: date (calendar table for Power BI time intelligence) ----
    dates = pd.date_range(fact["transaction_date"].min(), fact["transaction_date"].max(), freq="D")
    dim_date = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "month_name": dates.strftime("%b"),
        "day": dates.day,
        "day_of_week": dates.strftime("%A"),
        "is_weekend": dates.dayofweek.isin([5, 6]),
    })
    dim_date.to_csv(f"{OUT_DIR}/dim_date.csv", index=False)

    # ---- Dim: app users -> RLS role mapping ----
    dim_users = pd.read_sql_query("SELECT username, role FROM app_users", conn)
    dim_users.to_csv(f"{OUT_DIR}/dim_report_users.csv", index=False)

    conn.close()

    print("Exported:")
    for name, df in [
        ("fact_transactions", fact), ("dim_customers_masked", dim_cust_masked),
        ("RESTRICTED_dim_customers_full", dim_cust_full), ("dim_merchants", dim_merchants),
        ("dim_date", dim_date), ("dim_report_users", dim_users),
    ]:
        print(f"  {name}: {df.shape}")


if __name__ == "__main__":
    main()

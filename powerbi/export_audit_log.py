"""
Export current audit_log entries to CSV for Power BI compliance reporting.
"""
import sqlite3
import pandas as pd

DB_PATH = "data/processed/fraud_analytics.db"
OUT_PATH = "powerbi/audit_log.csv"


def main():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT al.log_id, au.username, au.role, al.action, al.customer_hash, al.accessed_at
        FROM audit_log al
        JOIN app_users au ON al.user_id = au.user_id
        ORDER BY al.accessed_at DESC
    """, conn)
    conn.close()

    df.to_csv(OUT_PATH, index=False)
    print(f"Exported {len(df)} audit_log rows to {OUT_PATH}")


if __name__ == "__main__":
    main()

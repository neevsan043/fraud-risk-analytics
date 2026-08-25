"""
Export the current audit_log table to CSV for the Power BI Compliance/Audit
Trail page. Re-run this any time you want the Power BI page to reflect
recent access events, then hit Refresh in Power BI — this is a
scheduled/manual-refresh export, not a live connection (see
app/audit_monitor.py for a true live view against the database itself).
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

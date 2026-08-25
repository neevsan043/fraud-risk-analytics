"""
Admin audit-log monitor.

Unlike a Power BI page (which only refreshes on schedule/import), this
queries the LIVE SQLite database directly every time it's run — so it
always reflects the current state of audit_log, including access events
that happened seconds ago. This is what "real-time monitoring" actually
means for a database-backed audit trail: querying the live table, not a
cached export.

Usage:
    python3 app/audit_monitor.py                  # last 20 events
    python3 app/audit_monitor.py --hours 24        # last 24 hours
    python3 app/audit_monitor.py --user alex_analyst
    python3 app/audit_monitor.py --denied-only     # flag suspicious denials
"""
import argparse
import sqlite3

DB_PATH = "data/processed/fraud_analytics.db"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=None, help="Only show events from the last N hours")
    parser.add_argument("--user", type=str, default=None, help="Filter to one username")
    parser.add_argument("--denied-only", action="store_true", help="Only show DENIED actions")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
        SELECT al.log_id, au.username, au.role, al.action, al.customer_hash, al.accessed_at
        FROM audit_log al
        JOIN app_users au ON al.user_id = au.user_id
        WHERE 1=1
    """
    params = []
    if args.hours is not None:
        query += " AND al.accessed_at >= datetime('now', ?)"
        params.append(f"-{args.hours} hours")
    if args.user:
        query += " AND au.username = ?"
        params.append(args.user)
    if args.denied_only:
        query += " AND al.action LIKE '%DENIED%'"
    query += " ORDER BY al.accessed_at DESC LIMIT ?"
    params.append(args.limit)

    rows = cur.execute(query, params).fetchall()

    if not rows:
        print("No matching audit events.")
        return

    print(f"{'ID':<4} {'User':<14} {'Role':<9} {'Action':<32} {'Customer Hash':<14} {'When'}")
    print("-" * 100)
    for r in rows:
        chash = (r["customer_hash"][:10] + "...") if r["customer_hash"] else "-"
        flag = "  <-- DENIED" if "DENIED" in r["action"] else ""
        print(f"{r['log_id']:<4} {r['username']:<14} {r['role']:<9} {r['action']:<32} {chash:<14} {r['accessed_at']}{flag}")

    denied_count = sum(1 for r in rows if "DENIED" in r["action"])
    if denied_count:
        print(f"\n{denied_count} denied access attempt(s) in this view — review recommended.")

    conn.close()


if __name__ == "__main__":
    main()

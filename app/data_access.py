import sqlite3
from contextlib import contextmanager

DB_PATH = "data/processed/fraud_analytics.db"


class AccessDeniedError(Exception):
    pass


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _get_user(conn, username: str) -> dict:
    """Resolves username to user_id and role from app_users."""
    row = conn.execute(
        "SELECT user_id, username, role FROM app_users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        raise AccessDeniedError(f"Unknown user: {username}")
    return dict(row)


def _log(conn, user_id: int, action: str, customer_hash: str = None):
    """Inserts an immutable compliance audit entry into audit_log."""
    conn.execute(
        "INSERT INTO audit_log (user_id, action, customer_hash) VALUES (?, ?, ?)",
        (user_id, action, customer_hash),
    )
    conn.commit()


def get_customer(username: str, customer_id: int) -> dict:
    """
    Fetch a customer record. Analysts get the masked view; admins get full PII.
    Every call is logged to audit_log regardless of outcome.
    """
    with _conn() as conn:
        user = _get_user(conn, username)

        if user["role"] == "admin":
            row = conn.execute(
                "SELECT customer_id, customer_hash, full_name, email, "
                "card_number_masked, billing_address, risk_tier "
                "FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone()
            action = "VIEW_CUSTOMER_PII_FULL"
        else:
            row = conn.execute(
                "SELECT customer_id, customer_hash, name_masked, card_last4, risk_tier "
                "FROM customers_masked WHERE customer_id = ?", (customer_id,)
            ).fetchone()
            action = "VIEW_CUSTOMER_PII_MASKED"

        if row is None:
            _log(conn, user["user_id"], action + "_NOT_FOUND")
            raise ValueError(f"No customer found with id {customer_id}")

        result = dict(row)
        _log(conn, user["user_id"], action, customer_hash=result.get("customer_hash"))
        return result


def get_flagged_transactions(username: str, min_score: float = 0.5, limit: int = 20) -> list:
    """
    Returns flagged transactions joined against the masked customer view.
    Safe for broad operational use across both Analyst and Admin roles.
    """
    with _conn() as conn:
        user = _get_user(conn, username)
        rows = conn.execute("""
            SELECT t.transaction_id, cm.name_masked, cm.card_last4, t.amount,
                   t.device_country, t.home_country, f.fraud_score
            FROM fraud_flags f
            JOIN transactions t ON f.transaction_id = t.transaction_id
            JOIN customers_masked cm ON t.customer_hash = cm.customer_hash
            WHERE f.fraud_score >= ?
            ORDER BY f.fraud_score DESC
            LIMIT ?
        """, (min_score, limit)).fetchall()
        _log(conn, user["user_id"], f"VIEW_FLAGGED_TRANSACTIONS(min_score={min_score})")
        return [dict(r) for r in rows]


def get_audit_trail(username: str, limit: int = 50) -> list:
    """
    Fetches compliance audit log entries. Strictly restricted to Admin roles.
    Unauthorized calls are blocked and logged with VIEW_AUDIT_LOG_DENIED.
    """
    with _conn() as conn:
        user = _get_user(conn, username)
        if user["role"] != "admin":
            _log(conn, user["user_id"], "VIEW_AUDIT_LOG_DENIED")
            raise AccessDeniedError(f"User '{username}' (role={user['role']}) cannot view the audit log.")
            
        rows = conn.execute("""
            SELECT al.log_id, au.username, al.action, al.customer_hash, al.accessed_at
            FROM audit_log al
            JOIN app_users au ON al.user_id = au.user_id
            ORDER BY al.accessed_at DESC LIMIT ?
        """, (limit,)).fetchall()
        _log(conn, user["user_id"], "VIEW_AUDIT_LOG")
        return [dict(r) for r in rows]


if __name__ == "__main__":
    print("--- Customer record query (analyst role / masked) ---")
    print(get_customer("alex_analyst", 1))

    print("\n--- Customer record query (admin role / unmasked) ---")
    print(get_customer("priya_admin", 1))

    print("\n--- Flagged transactions query (analyst role) ---")
    for r in get_flagged_transactions("alex_analyst", min_score=0.9, limit=3):
        print(r)

    print("\n--- Audit log access check (analyst role) ---")
    try:
        get_audit_trail("alex_analyst")
    except AccessDeniedError as e:
        print(f"Access denied: {e}")

    print("\n--- Compliance audit trail (admin role) ---")
    for r in get_audit_trail("priya_admin", limit=5):
        print(r)
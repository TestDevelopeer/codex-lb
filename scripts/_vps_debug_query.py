import sqlite3

conn = sqlite3.connect("/var/lib/codex-lb/store.db")
cur = conn.cursor()
cur.execute("SELECT ip_address FROM api_firewall_allowlist")
print("firewall:", [r[0] for r in cur.fetchall()])
cur.execute(
    "SELECT status, error_code, error_message, account_id, upstream_status_code, upstream_error_code, model "
    "FROM request_logs WHERE request_id = ?",
    ("ad1b506b-fdbe-4a47-bcea-52098f21ee29",),
)
print("log:", cur.fetchall())
cur.execute("SELECT id, provider, status, email FROM accounts")
print("accounts:", cur.fetchall())

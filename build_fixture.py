import sqlite3, os, datetime

os.makedirs("fixtures", exist_ok=True)
FIXTURE = "fixtures/pre_migration.db"
if os.path.exists(FIXTURE):
    os.remove(FIXTURE)

conn = sqlite3.connect(FIXTURE)
conn.executescript("""
    CREATE TABLE accounts (
        account_id      TEXT PRIMARY KEY,
        balance         REAL NOT NULL,
        status          TEXT NOT NULL,
        opening_balance REAL NOT NULL,
        customer_id     TEXT,
        created_at      TEXT
    );
    CREATE TABLE ledger (
        tx_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id         TEXT NOT NULL,
        amount             REAL NOT NULL,
        type               TEXT NOT NULL,
        related_account_id TEXT,
        timestamp          TEXT NOT NULL,
        description        TEXT
    );
""")

now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

for acc, bal, opening in [("ACC-A", 1000.00, 1000.00),
                          ("ACC-B",  500.00,  500.00),
                          ("ACC-C",    0.00,    0.00)]:
    conn.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                 (acc, bal, "Active", opening, "CUST-" + acc, now))

for acc, amt, typ, rel, desc in [
    ("ACC-A",  1000.00, "Deposit",       None,   "Initial deposit"),
    ("ACC-B",   750.00, "Deposit",       None,   "Initial deposit"),
    ("ACC-B",  -250.00, "Transfer Out",  "ACC-A", "Transfer to A"),
    ("ACC-A",   250.00, "Transfer In",   "ACC-B", "Transfer from B"),
    ("ACC-A",  -250.00, "Withdrawal",    None,   "ATM"),
    ("ACC-A",   250.00, "Deposit",       None,   "Refund"),
]:
    conn.execute("INSERT INTO ledger "
                 "(account_id,amount,type,related_account_id,timestamp,description)"
                 " VALUES (?,?,?,?,?,?)",
                 (acc, amt, typ, rel, now, desc))

conn.commit()
conn.close()
print("Fixture:", FIXTURE)

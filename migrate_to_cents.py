import sqlite3, os, shutil
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

SRC = "fixtures/pre_migration.db"
BAK = "fixtures/pre_migration_backup.db"
DST = "banking.db"

def cents(v):
    return int((Decimal(str(v)) * Decimal("100"))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

if os.path.exists(BAK): os.remove(BAK)
shutil.copy2(SRC, BAK)
if os.path.exists(DST): os.remove(DST)

src = sqlite3.connect(SRC); src.row_factory = sqlite3.Row
dst = sqlite3.connect(DST); dst.row_factory = sqlite3.Row

dst.executescript("""
    CREATE TABLE accounts (
        account_id      TEXT PRIMARY KEY,
        balance         INTEGER NOT NULL CHECK (balance >= 0),
        status          TEXT NOT NULL CHECK (status IN ('Active','Frozen')),
        opening_balance INTEGER NOT NULL DEFAULT 0,
        customer_id     TEXT,
        created_at      TEXT
    );
    CREATE TABLE ledger (
        tx_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id         TEXT NOT NULL,
        amount             INTEGER NOT NULL CHECK (amount <> 0),
        type               TEXT NOT NULL,
        related_account_id TEXT,
        timestamp          TEXT NOT NULL,
        description        TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
    );
    CREATE TABLE schema_version (
        version    INTEGER NOT NULL,
        applied_at TEXT    NOT NULL,
        note       TEXT
    );
""")

for row in src.execute("SELECT * FROM accounts"):
    dst.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                (row["account_id"], cents(row["balance"]), row["status"],
                 cents(row["opening_balance"]), row["customer_id"], row["created_at"]))

for row in src.execute("SELECT * FROM ledger ORDER BY tx_id"):
    dst.execute("INSERT INTO ledger "
                "(account_id,amount,type,related_account_id,timestamp,description) "
                "VALUES (?,?,?,?,?,?)",
                (row["account_id"], cents(row["amount"]), row["type"],
                 row["related_account_id"], row["timestamp"], row["description"]))

dst.execute("INSERT INTO schema_version VALUES (?,?,?)",
            (2, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "integer-cents migration"))

dst.commit()
src.close(); dst.close()
print("Migrated:", SRC, "->", DST)
print("Schema:   2")

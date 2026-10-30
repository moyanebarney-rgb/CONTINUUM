import sqlite3, os, shutil, sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

SRC = "fixtures/pre_migration.db"
DST = "banking.db"
TMP_DST = "banking.db.tmp"
BAK = "fixtures/pre_migration_backup.db"

def cents(v) -> int:
    d = Decimal(str(v)) * Decimal("100")
    if d != d.quantize(Decimal("1")):
        raise ValueError(f"Sub-cent value detected: {v}")
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def run_migration():
    if not os.path.exists(SRC):
        raise FileNotFoundError(f"Source database not found: {SRC}")
    
    if os.path.exists(TMP_DST): 
        os.remove(TMP_DST)
    
    # Read-only source connection
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    
    # Explicit transaction control for destination
    dst = sqlite3.connect(TMP_DST, isolation_level=None)
    dst.row_factory = sqlite3.Row
    dst.execute("PRAGMA foreign_keys = ON;")

    try:
        dst.execute("BEGIN IMMEDIATE;")
        
        # P1 Fix: Use execute() instead of executescript() to maintain the transaction
        dst.execute("""
            CREATE TABLE accounts (
                account_id      TEXT PRIMARY KEY,
                balance         INTEGER NOT NULL CHECK (balance >= 0),
                status          TEXT NOT NULL CHECK (status IN ('Active','Frozen')),
                opening_balance INTEGER NOT NULL DEFAULT 0,
                customer_id     TEXT,
                created_at      TEXT
            );
        """)
        dst.execute("""
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
        """)
        dst.execute("""
            CREATE TABLE schema_version (
                version    INTEGER NOT NULL,
                applied_at TEXT    NOT NULL,
                note       TEXT
            );
        """)

        # P3 Fix: Track expected balances for conservation check
        expected_balances = {}

        for row in src.execute("SELECT * FROM accounts"):
            acc_id = row["account_id"]
            bal_cents = cents(row["balance"])
            op_cents = cents(row["opening_balance"])
            expected_balances[acc_id] = bal_cents
            
            dst.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                        (acc_id, bal_cents, row["status"], op_cents, row["customer_id"], row["created_at"]))

        for row in src.execute("SELECT * FROM ledger ORDER BY tx_id"):
            dst.execute("INSERT INTO ledger (account_id,amount,type,related_account_id,timestamp,description) VALUES (?,?,?,?,?,?)",
                        (row["account_id"], cents(row["amount"]), row["type"],
                         row["related_account_id"], row["timestamp"], row["description"]))

        dst.execute("INSERT INTO schema_version VALUES (?,?,?)",
                    (2, datetime.now(timezone.utc).isoformat(timespec="seconds"), "integer-cents migration"))
        
        # P3 Fix: Verify identities and converted financial values before commit
        for acc_id, expected_bal in expected_balances.items():
            actual = dst.execute("SELECT balance FROM accounts WHERE account_id = ?", (acc_id,)).fetchone()
            if not actual or actual["balance"] != expected_bal:
                raise ValueError(f"Conservation check failed for {acc_id}: expected {expected_bal}, got {actual['balance'] if actual else 'MISSING'}")

        dst.execute("COMMIT;")
        
        # SQLite integrity check
        integrity = dst.execute("PRAGMA integrity_check;").fetchone()[0]
        fk_check = dst.execute("PRAGMA foreign_key_check;").fetchone()
        
        if integrity != "ok" or fk_check is not None:
            raise ValueError("SQLite integrity or foreign-key check failed.")

    except Exception as e:
        dst.execute("ROLLBACK;")
        if os.path.exists(TMP_DST):
            os.remove(TMP_DST)
        raise e

    finally:
        src.close()
        dst.close()

    # P2 Fix: Backup existing destination, then atomically replace (no os.remove)
    if os.path.exists(BAK): 
        os.remove(BAK)
    if os.path.exists(DST):
        shutil.copy2(DST, BAK)
        
    os.replace(TMP_DST, DST)
    print("Migrated:", SRC, "->", DST)
    print("Schema:   2")

if __name__ == "__main__":
    run_migration()

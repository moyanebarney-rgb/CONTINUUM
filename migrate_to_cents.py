import sqlite3, os, shutil
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

SRC = "fixtures/pre_migration.db"
DST = "banking.db"
TMP_DST = "banking.db.tmp"
BAK = "fixtures/pre_migration_backup.db"

def cents(v) -> int:
    # Reject sub-cent fractions to prevent silent rounding
    d = Decimal(str(v)) * Decimal("100")
    if d != d.quantize(Decimal("1")):
        raise ValueError(f"Sub-cent value detected: {v}. Rejecting migration.")
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def run_migration():
    # 1. Create temporary destination
    if os.path.exists(TMP_DST): os.remove(TMP_DST)
    
    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(TMP_DST)
    dst.row_factory = sqlite3.Row
    
    # 2. Enable foreign keys
    dst.execute("PRAGMA foreign_keys = ON;")

    try:
        # 3. Perform the migration inside a controlled transaction
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
            dst.execute("INSERT INTO ledger (account_id,amount,type,related_account_id,timestamp,description) VALUES (?,?,?,?,?,?)",
                        (row["account_id"], cents(row["amount"]), row["type"],
                         row["related_account_id"], row["timestamp"], row["description"]))

        dst.execute("INSERT INTO schema_version VALUES (?,?,?)",
                    (2, datetime.now(timezone.utc).isoformat(timespec="seconds"), "integer-cents migration"))
        
        # 4. Verify source and destination counts before committing
        src_acc = src.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        dst_acc = dst.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        src_led = src.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        dst_led = dst.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        
        if src_acc != dst_acc or src_led != dst_led:
            raise ValueError("Conservation check failed: row counts do not match.")
            
        dst.commit()

    except Exception as e:
        dst.rollback()
        dst.close()
        src.close()
        os.remove(TMP_DST) # Clean up temp file on failure
        raise e

    src.close()
    dst.close()

    # 5. Run SQLite integrity checks on the temp database
    verify_conn = sqlite3.connect(TMP_DST)
    integrity = verify_conn.execute("PRAGMA integrity_check;").fetchone()[0]
    fk_check = verify_conn.execute("PRAGMA foreign_key_check;").fetchone()
    verify_conn.close()

    if integrity != "ok" or fk_check is not None:
        os.remove(TMP_DST)
        raise ValueError("SQLite integrity or foreign-key check failed.")

    # 6. Promote the temp database to the destination
    if os.path.exists(BAK): os.remove(BAK)
    if os.path.exists(DST):
        shutil.copy2(DST, BAK) # Backup the current valid state before overwriting
        os.remove(DST)
    
    os.replace(TMP_DST, DST) # Atomic promotion
    print("Migrated:", SRC, "->", DST)
    print("Schema:   2")

if __name__ == "__main__":
    run_migration()

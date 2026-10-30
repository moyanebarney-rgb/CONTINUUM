import sqlite3, os, shutil, sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

SRC = os.environ.get("MIG_SRC", "fixtures/pre_migration.db")
DST = os.environ.get("MIG_DST", "banking.db")
TMP_DST = os.environ.get("MIG_TMP", "banking.db.tmp")
BAK = os.environ.get("MIG_BAK", "fixtures/pre_migration_backup.db")

def cents(v) -> int:
    d = Decimal(str(v)) * Decimal("100")
    if d != d.quantize(Decimal("1")):
        raise ValueError(f"Sub-cent value detected: {v}")
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def validate_paths():
    src_path = os.path.realpath(SRC)
    dst_path = os.path.realpath(DST)
    tmp_path = os.path.realpath(TMP_DST)
    bak_path = os.path.realpath(BAK)
    bak_tmp_path = os.path.realpath(BAK + ".new")

    paths = {src_path, dst_path, tmp_path, bak_path, bak_tmp_path}
    if len(paths) != 5:
        raise ValueError("All migration and backup paths must be distinct.")
    
    if os.path.dirname(dst_path) != os.path.dirname(tmp_path):
        raise ValueError("Temporary database must be in the destination directory.")
        
    if os.path.dirname(bak_path) != os.path.dirname(bak_tmp_path):
        raise ValueError("Backup temporary file must share the backup directory.")

def run_migration():
    validate_paths()

    if not os.path.exists(SRC):
        raise FileNotFoundError(f"Source database not found: {SRC}")
    
    if os.path.exists(TMP_DST): 
        os.remove(TMP_DST)
    
    src = None
    dst = None
    transaction_active = False
    migration_successful = False

    try:
        src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        src.execute("BEGIN;")
        
        dst = sqlite3.connect(TMP_DST, isolation_level=None)
        dst.row_factory = sqlite3.Row
        dst.execute("PRAGMA foreign_keys = ON;")

        dst.execute("BEGIN IMMEDIATE;")
        transaction_active = True
        
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

        expected_balances = {}

        for row in src.execute("SELECT * FROM accounts"):
            acc_id = row["account_id"]
            bal_cents = cents(row["balance"])
            op_cents = cents(row["opening_balance"])
            expected_balances[acc_id] = bal_cents
            
            dst.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                        (acc_id, bal_cents, row["status"], op_cents, row["customer_id"], row["created_at"]))

        for row in src.execute("SELECT * FROM ledger ORDER BY tx_id"):
            dst.execute("INSERT INTO ledger (tx_id, account_id, amount, type, related_account_id, timestamp, description) VALUES (?,?,?,?,?,?,?)",
                        (row["tx_id"], row["account_id"], cents(row["amount"]), row["type"],
                         row["related_account_id"], row["timestamp"], row["description"]))

        dst.execute("INSERT INTO schema_version VALUES (?,?,?)",
                    (2, datetime.now(timezone.utc).isoformat(timespec="seconds"), "integer-cents migration"))
        
        for acc_id, expected_bal in expected_balances.items():
            actual = dst.execute("SELECT balance FROM accounts WHERE account_id = ?", (acc_id,)).fetchone()
            if not actual or actual["balance"] != expected_bal:
                raise ValueError(f"Conservation check failed for {acc_id}")

        dst.execute("COMMIT;")
        transaction_active = False
        
        integrity = dst.execute("PRAGMA integrity_check;").fetchone()[0]
        fk_check = dst.execute("PRAGMA foreign_key_check;").fetchone()
        
        if integrity != "ok" or fk_check is not None:
            raise ValueError("SQLite integrity or foreign-key check failed.")
            
        migration_successful = True

    except Exception:
        if transaction_active and dst:
            try:
                dst.execute("ROLLBACK;")
            except Exception as rollback_err:
                print(f"Warning: Rollback failed: {rollback_err}", file=sys.stderr)
        raise

    finally:
        if dst: dst.close()
        if src: src.close()
        
        if not migration_successful and os.path.exists(TMP_DST):
            try:
                os.remove(TMP_DST)
            except Exception as e:
                print(f"Warning: Failed to remove temp file: {e}", file=sys.stderr)

    if migration_successful:
        # Atomic backup preservation
        if os.path.exists(DST):
            bak_tmp = BAK + ".new"
            shutil.copy2(DST, bak_tmp)
            if os.path.exists(BAK):
                os.remove(BAK)
            os.replace(bak_tmp, BAK)
            
        os.replace(TMP_DST, DST)
        print(f"Migrated: {SRC} -> {DST}")
        print("Schema:   2")

if __name__ == "__main__":
    run_migration()

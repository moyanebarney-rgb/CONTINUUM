from pathlib import Path
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

# Paths
SRC = Path("fixtures/pre_migration.db")
BAK = Path("fixtures/pre_migration_backup.db")
TMP = Path("banking.db.tmp")
DST = Path("banking.db")

# 1. Pre-flight validation
if not SRC.is_file():
    raise FileNotFoundError(f"Source database not found at {SRC}")

# Clean up any prior temporary or target files
if TMP.exists():
    TMP.unlink()
if DST.exists():
    DST.unlink()

# 2. Backup the source
shutil.copy2(SRC, BAK)
print(f"Backup created: {BAK}")

src = sqlite3.connect(SRC)
src.row_factory = sqlite3.Row

def safe_cents(v):
    """Convert REAL/float to INTEGER cents, handling NULLs safely."""
    if v is None:
        return 0
    return int((Decimal(str(v)) * Decimal("100"))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

try:
    # 3. Connect to a TEMPORARY database, not the final destination
    dst = sqlite3.connect(TMP)
    dst.row_factory = sqlite3.Row
    
    # 4. Enforce Foreign Keys explicitly
    dst.execute("PRAGMA foreign_keys = ON")

    # 5. Atomic Transaction for the entire schema and data copy
    with dst:
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

        # Migrate Accounts
        for row in src.execute("SELECT * FROM accounts"):
            dst.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                        (row["account_id"], safe_cents(row["balance"]), row["status"],
                         safe_cents(row["opening_balance"]), row["customer_id"], row["created_at"]))

        # Migrate Ledger
        for row in src.execute("SELECT * FROM ledger ORDER BY tx_id"):
            dst.execute("INSERT INTO ledger "
                        "(account_id,amount,type,related_account_id,timestamp,description) "
                        "VALUES (?,?,?,?,?,?)",
                        (row["account_id"], safe_cents(row["amount"]), row["type"],
                         row["related_account_id"], row["timestamp"], row["description"]))

        # Record Schema Version
        dst.execute("INSERT INTO schema_version VALUES (?,?,?)",
                    (2, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "integer-cents migration"))

    # 6. Integrity Check
    result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"Migration integrity check failed: {result}")
    
    dst.close()

    # 7. Atomic Swap: Only move to DST if everything passed
    os.replace(TMP, DST)
    print(f"Migration successful. Output: {DST}")

except Exception as e:
    print(f"\n[FAILURE] Migration aborted: {e}")
    if TMP.exists():
        print("Cleaning up partial temporary database...")
        TMP.unlink()
    raise

finally:
    src.close()

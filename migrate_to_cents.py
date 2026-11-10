import hashlib, os, shutil, sqlite3, sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "fixtures/pre_migration.db"
BAK = ROOT / "fixtures/pre_migration_backup.db"
TMP = ROOT / "banking.db.tmp"
DST = ROOT / "banking.db"
def sha256_file(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def cents(value, field):
    if value is None: raise ValueError(f"NULL: {field}")
    scaled = Decimal(str(value)) * Decimal("100")
    if scaled != scaled.to_integral_value(): raise ValueError(f"Sub-cent: {field}")
    return int(scaled)
def migrate():
    if BAK.exists(): BAK.unlink()
    shutil.copy2(SRC, BAK)
    if sha256_file(SRC) != sha256_file(BAK): raise RuntimeError("Backup mismatch")
    if TMP.exists(): TMP.unlink()
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True); src.row_factory = sqlite3.Row
    dst = sqlite3.connect(TMP); dst.row_factory = sqlite3.Row
    dst.execute("PRAGMA foreign_keys = ON"); dst.execute("BEGIN IMMEDIATE")
    dst.execute("CREATE TABLE accounts (account_id TEXT PRIMARY KEY, balance INTEGER NOT NULL CHECK (balance >= 0), status TEXT NOT NULL, opening_balance INTEGER NOT NULL, customer_id TEXT, created_at TEXT)")
    dst.execute("CREATE TABLE ledger (tx_id INTEGER PRIMARY KEY, account_id TEXT NOT NULL, amount INTEGER NOT NULL CHECK (amount <> 0), type TEXT NOT NULL, related_account_id TEXT, timestamp TEXT NOT NULL, description TEXT, FOREIGN KEY (account_id) REFERENCES accounts(account_id))")
    dst.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL, note TEXT)")
    dst.execute("CREATE TRIGGER prevent_ledger_update BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT, 'Append-only'); END")
    dst.execute("CREATE TRIGGER prevent_ledger_delete BEFORE DELETE ON ledger BEGIN SELECT RAISE(ABORT, 'Append-only'); END")
    for r in src.execute("SELECT * FROM accounts"):
        dst.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)", (r["account_id"], cents(r["balance"], "bal"), r["status"], cents(r["opening_balance"], "op"), r["customer_id"], r["created_at"]))
    for r in src.execute("SELECT * FROM ledger"):
        dst.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?,?)", (r["tx_id"], r["account_id"], cents(r["amount"], "amt"), r["type"], r["related_account_id"], r["timestamp"], r["description"]))
    dst.execute("INSERT INTO schema_version VALUES (2, ?, 'migration')", (datetime.now(timezone.utc).isoformat(),))
    dst.commit(); src.close(); dst.close()
    if os.environ.get("SIMULATE_CRASH") == "1": sys.exit(1)
    os.replace(TMP, DST); print("Migration complete.")
if __name__ == "__main__": migrate()

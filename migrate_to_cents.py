import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

SRC = Path(os.environ.get("MIG_SRC", "fixtures/pre_migration.db"))
BAK = Path(os.environ.get("MIG_BAK", "fixtures/pre_migration_backup.db"))
TMP = Path(os.environ.get("MIG_TMP", "banking.db.tmp"))
DST = Path(os.environ.get("MIG_DST", "banking.db"))


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def cents(value):
    """Convert a legacy floating-point monetary value into integer cents.

    Rejects values that are not representable to exactly two decimal places,
    which protects against sub-cent corruption in the source database.
    """
    if value is None:
        return 0

    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc

    if decimal_value.as_tuple().exponent < -2:
        raise ValueError(
            f"Source contains a non-cent value: {value!r}. "
            "Legacy financial data must be exact to the cent."
        )

    return int(
        (decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


# ---------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------

def migrate():
    if not SRC.is_file():
        raise FileNotFoundError(f"Source database not found at {SRC}")

    if TMP.exists():
        TMP.unlink()

    BAK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, BAK)
    print(f"Backup created: {BAK}")

    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row

    try:
        dst = sqlite3.connect(TMP)
        dst.row_factory = sqlite3.Row
        dst.execute("PRAGMA foreign_keys = ON")

        try:
            with dst:
                dst.executescript(
                    """
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
                    """
                )

                for row in src.execute("SELECT * FROM accounts"):
                    dst.execute(
                        """
                        INSERT INTO accounts (
                            account_id,
                            balance,
                            status,
                            opening_balance,
                            customer_id,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["account_id"],
                            cents(row["balance"]),
                            row["status"],
                            cents(row["opening_balance"]),
                            row["customer_id"],
                            row["created_at"],
                        ),
                    )

                for row in src.execute("SELECT * FROM ledger ORDER BY tx_id"):
                    dst.execute(
                        """
                        INSERT INTO ledger (
                            account_id,
                            amount,
                            type,
                            related_account_id,
                            timestamp,
                            description
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["account_id"],
                            cents(row["amount"]),
                            row["type"],
                            row["related_account_id"],
                            row["timestamp"],
                            row["description"],
                        ),
                    )

                dst.execute(
                    "INSERT INTO schema_version (version, applied_at, note) VALUES (?, ?, ?)",
                    (
                        2,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "integer-cents migration",
                    ),
                )

            result = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(f"Migration integrity check failed: {result}")

            dst.close()

            os.replace(TMP, DST)
            print(f"Migration successful. Output: {DST}")

        except Exception:
            dst.close()
            if TMP.exists():
                TMP.unlink()
            raise

    finally:
        src.close()


if __name__ == "__main__":
    try:
        migrate()
    except Exception as exc:
        print(f"\n[FAILURE] Migration aborted: {exc}")
        if TMP.exists():
            print("Cleaning up partial temporary database...")
            TMP.unlink()
        raise

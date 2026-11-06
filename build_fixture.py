import sqlite3
import os
import tempfile
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent

FIXTURES_DIR = ROOT / "fixtures"
FIXTURE = FIXTURES_DIR / "pre_migration.db"

# Fixed timestamp for reproducible fixture data.
FIXED_TIMESTAMP = "2026-01-01T00:00:00+00:00"


# ============================================================
# FIXTURE DATA
# ============================================================

ACCOUNTS = [
    ("ACC-A", 1250.00, 0.00),
    ("ACC-B", 500.00, 0.00),
    ("ACC-C", 0.00, 0.00),
]

TRANSACTIONS = [
    (
        "ACC-A",
        1000.00,
        "Deposit",
        None,
        "Initial deposit",
    ),
    (
        "ACC-B",
        750.00,
        "Deposit",
        None,
        "Initial deposit",
    ),
    (
        "ACC-B",
        -250.00,
        "Transfer Out",
        "ACC-A",
        "Transfer to A",
    ),
    (
        "ACC-A",
        250.00,
        "Transfer In",
        "ACC-B",
        "Transfer from B",
    ),
    (
        "ACC-A",
        -250.00,
        "Withdrawal",
        None,
        "ATM",
    ),
    (
        "ACC-A",
        250.00,
        "Deposit",
        None,
        "Refund",
    ),
]


# ============================================================
# DATABASE SCHEMA
# ============================================================

SCHEMA = """
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    balance REAL NOT NULL,
    status TEXT NOT NULL,
    opening_balance REAL NOT NULL,
    customer_id TEXT,
    created_at TEXT
);

CREATE TABLE ledger (
    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL,
    related_account_id TEXT,
    timestamp TEXT NOT NULL,
    description TEXT
);
"""


# ============================================================
# VALIDATION
# ============================================================

def validate_financial_reconciliation(conn):

    for account_id, balance, opening_balance in ACCOUNTS:

        movements = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM ledger
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()[0]

        calculated_balance = opening_balance + movements

        if abs(calculated_balance - balance) > 0.000001:

            raise RuntimeError(
                f"Reconciliation failed for {account_id}: "
                f"expected {balance}, calculated {calculated_balance}"
            )


def validate_database(conn):

    integrity = conn.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(
            f"SQLite integrity check failed: {integrity}"
        )

    validate_financial_reconciliation(conn)

    account_count = conn.execute(
        "SELECT COUNT(*) FROM accounts"
    ).fetchone()[0]

    transaction_count = conn.execute(
        "SELECT COUNT(*) FROM ledger"
    ).fetchone()[0]

    if account_count != len(ACCOUNTS):
        raise RuntimeError("Unexpected account count.")

    if transaction_count != len(TRANSACTIONS):
        raise RuntimeError("Unexpected transaction count.")


# ============================================================
# FIXTURE CONSTRUCTION
# ============================================================

def build_fixture():

    FIXTURES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Never overwrite an existing fixture.
    if FIXTURE.exists():
        raise FileExistsError(
            f"Fixture already exists: {FIXTURE}\n"
            "Existing data has been preserved. "
            "Choose a new output filename or investigate the existing fixture."
        )

    temporary_path = None

    try:

        # Create a temporary database in the same directory.
        # This allows atomic publication on the same filesystem.

        fd, temporary_name = tempfile.mkstemp(
            prefix="pre_migration_",
            suffix=".tmp",
            dir=FIXTURES_DIR,
        )

        os.close(fd)

        temporary_path = Path(temporary_name)

        conn = sqlite3.connect(temporary_path)

        try:

            conn.executescript(SCHEMA)

            # Insert accounts.
            for account_id, balance, opening_balance in ACCOUNTS:

                conn.execute(
                    """
                    INSERT INTO accounts (
                        account_id,
                        balance,
                        status,
                        opening_balance,
                        customer_id,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        balance,
                        "Active",
                        opening_balance,
                        "CUST-" + account_id,
                        FIXED_TIMESTAMP,
                    ),
                )

            # Insert ledger transactions.
            for (
                account_id,
                amount,
                transaction_type,
                related_account_id,
                description,
            ) in TRANSACTIONS:

                conn.execute(
                    """
                    INSERT INTO ledger (
                        account_id,
                        amount,
                        type,
                        related_account_id,
                        timestamp,
                        description
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        amount,
                        transaction_type,
                        related_account_id,
                        FIXED_TIMESTAMP,
                        description,
                    ),
                )

            conn.commit()

            # Validate before publication.
            validate_database(conn)

        finally:
            conn.close()

        # Atomic publication without overwriting an existing file.
        # os.link fails if the destination already exists.
        os.link(temporary_path, FIXTURE)

        print("FIXTURE CREATED SUCCESSFULLY")
        print("Path:", FIXTURE)
        print("Accounts:", len(ACCOUNTS))
        print("Transactions:", len(TRANSACTIONS))
        print("Integrity: PASS")
        print("Financial reconciliation: PASS")

    finally:

        # Remove only this execution's temporary file.
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        build_fixture()

    except Exception as exc:

        print("FIXTURE BUILD FAILED")
        print(type(exc).__name__ + ":", exc)

        raise

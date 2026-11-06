import os
import sys
import sqlite3
import subprocess
import tempfile
import hashlib
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
MIGRATION_SCRIPT = SCRIPT_DIR / "migrate_to_cents.py"

TIMEOUT_SECONDS = 30

SENTINEL_CONTENT = b"ORIGINAL_VALID_STATE"


# ============================================================
# UTILITIES
# ============================================================

def sha256_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def assert_condition(condition, message):
    if not condition:
        raise AssertionError(message)


def create_source_database(path, balance, ledger_amount):
    """
    Creates a minimal pre-migration SQLite database.

    Monetary fields deliberately use REAL to represent
    the legacy source schema.
    """

    connection = sqlite3.connect(path)

    try:
        connection.executescript("""
            CREATE TABLE accounts (
                account_id TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                status TEXT NOT NULL,
                opening_balance REAL NOT NULL DEFAULT 0,
                customer_id TEXT,
                created_at TEXT
            );

            CREATE TABLE ledger (
                tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT,
                related_account_id TEXT,
                timestamp TEXT,
                description TEXT
            );
        """)

        connection.execute("""
            INSERT INTO accounts (
                account_id,
                balance,
                status,
                opening_balance,
                customer_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "TEST-001",
            balance,
            "Active",
            0.00,
            "CUSTOMER-001",
            "2026-11-06T10:00:00"
        ))

        connection.execute("""
            INSERT INTO ledger (
                tx_id,
                account_id,
                amount,
                type,
                related_account_id,
                timestamp,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            "TEST-001",
            ledger_amount,
            "Deposit",
            None,
            "2026-11-06T10:01:00",
            "Migration test deposit"
        ))

        connection.commit()

    finally:
        connection.close()


def run_migration(source, destination, temporary, backup):
    """
    Runs migrate_to_cents.py using the configured environment
    variables expected by the migration interface.
    """

    environment = os.environ.copy()

    environment.update({
        "MIG_SRC": str(source),
        "MIG_DST": str(destination),
        "MIG_TMP": str(temporary),
        "MIG_BAK": str(backup)
    })

    return subprocess.run(
        [sys.executable, str(MIGRATION_SCRIPT)],
        cwd=str(SCRIPT_DIR),
        env=environment,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS
    )


def print_result(result):
    print("Return code:", result.returncode)

    print("\nSTDOUT:")
    print(result.stdout or "(empty)")

    print("\nSTDERR:")
    print(result.stderr or "(empty)")


def assert_destination_unchanged(destination, expected_hash):
    assert_condition(
        destination.exists(),
        "Destination disappeared during failed migration."
    )

    actual_hash = sha256_file(destination)

    assert_condition(
        actual_hash == expected_hash,
        "Original destination was modified during failed migration."
    )


def assert_temporary_cleaned(temporary):
    assert_condition(
        not temporary.exists(),
        f"Temporary migration file was not cleaned up: {temporary}"
    )


def inspect_migrated_database(path):
    """
    Independently inspects the resulting SQLite database.
    Does not import migration or ledger implementation code.
    """

    assert_condition(
        path.exists(),
        "Migration did not create the destination database."
    )

    connection = sqlite3.connect(path)

    try:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        assert_condition(
            integrity == "ok",
            f"SQLite integrity check failed: {integrity}"
        )

        foreign_keys = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert_condition(
            len(foreign_keys) == 0,
            f"Foreign-key violations detected: {foreign_keys}"
        )

        account = connection.execute("""
            SELECT account_id, balance, opening_balance
            FROM accounts
            WHERE account_id = ?
        """, ("TEST-001",)).fetchone()

        assert_condition(
            account is not None,
            "Migrated account was not found."
        )

        account_id, balance, opening_balance = account

        assert_condition(
            isinstance(balance, int),
            f"Account balance is not stored as INTEGER: {type(balance)}"
        )

        assert_condition(
            balance == 100000,
            f"Unexpected migrated balance: {balance}"
        )

        assert_condition(
            isinstance(opening_balance, int),
            "Opening balance is not stored as INTEGER."
        )

        transaction = connection.execute("""
            SELECT tx_id, amount
            FROM ledger
            WHERE account_id = ?
        """, ("TEST-001",)).fetchone()

        assert_condition(
            transaction is not None,
            "Migrated ledger transaction was not found."
        )

        tx_id, amount = transaction

        assert_condition(
            tx_id == 1,
            f"Transaction identity was not preserved: {tx_id}"
        )

        assert_condition(
            isinstance(amount, int),
            f"Ledger amount is not stored as INTEGER: {type(amount)}"
        )

        assert_condition(
            amount == 100000,
            f"Unexpected migrated ledger amount: {amount}"
        )

        assert_condition(
            opening_balance + amount == balance,
            "Financial reconciliation failed."
        )

        print("Independent database inspection: PASS")
        print("Account:", account_id)
        print("Balance:", balance, "cents")
        print("Opening balance:", opening_balance, "cents")
        print("Transaction ID:", tx_id)
        print("Transaction amount:", amount, "cents")
        print("Financial reconciliation: PASS")
        print("SQLite integrity: PASS")
        print("Foreign-key check: PASS")

    finally:
        connection.close()


# ============================================================
# TEST RUNNER
# ============================================================

def run_tests():

    print("=" * 65)
    print("CONTINUUM — MIGRATION FAILURE TESTS")
    print("=" * 65)

    assert_condition(
        MIGRATION_SCRIPT.exists(),
        f"Migration script not found: {MIGRATION_SCRIPT}"
    )

    with tempfile.TemporaryDirectory() as temporary_directory:

        root = Path(temporary_directory)

        print("\nIsolated test directory:", root)

        # ----------------------------------------------------
        # TEST 1: MISSING SOURCE
        # ----------------------------------------------------

        print("\n--- TEST 1: PRE-MIGRATION FAILURE ---")
        print("Scenario: Missing source database")

        source = root / "missing_source.db"
        destination = root / "destination.db"
        temporary = root / "migration_temp.db"
        backup = root / "backup.db"

        destination.write_bytes(SENTINEL_CONTENT)

        original_hash = sha256_file(destination)

        result = run_migration(
            source,
            destination,
            temporary,
            backup
        )

        print_result(result)

        assert_condition(
            result.returncode != 0,
            "Migration unexpectedly succeeded with a missing source."
        )

        assert_destination_unchanged(
            destination,
            original_hash
        )

        assert_temporary_cleaned(temporary)

        print("\nTEST 1: PASS")
        print("Original destination preserved.")
        print("Migration exited unsuccessfully as expected.")

        # ----------------------------------------------------
        # TEST 2: SUB-CENT SOURCE DATA
        # ----------------------------------------------------

        print("\n--- TEST 2: MID-MIGRATION FAILURE ---")
        print("Scenario: Source contains a sub-cent monetary value")

        source = root / "corrupt_source.db"
        destination = root / "protected_destination.db"
        temporary = root / "corrupt_temp.db"
        backup = root / "corrupt_backup.db"

        create_source_database(
            source,
            balance=10.005,
            ledger_amount=10.005
        )

        destination.write_bytes(SENTINEL_CONTENT)

        original_hash = sha256_file(destination)

        result = run_migration(
            source,
            destination,
            temporary,
            backup
        )

        print_result(result)

        assert_condition(
            result.returncode != 0,
            "Migration accepted a source containing sub-cent values."
        )

        assert_destination_unchanged(
            destination,
            original_hash
        )

        assert_temporary_cleaned(temporary)

        assert_condition(
            source.exists(),
            "Original source database was removed."
        )

        print("\nTEST 2: PASS")
        print("Invalid monetary data rejected.")
        print("Original destination preserved.")
        print("Original source preserved.")
        print("Temporary migration file cleaned up.")

        # ----------------------------------------------------
        # TEST 3: SUCCESSFUL MIGRATION
        # ----------------------------------------------------

        print("\n--- TEST 3: SUCCESSFUL MIGRATION ---")
        print("Scenario: Valid source database")

        source = root / "valid_source.db"
        destination = root / "valid_destination.db"
        temporary = root / "valid_temp.db"
        backup = root / "valid_backup.db"

        create_source_database(
            source,
            balance=1000.00,
            ledger_amount=1000.00
        )

        source_hash_before = sha256_file(source)

        result = run_migration(
            source,
            destination,
            temporary,
            backup
        )

        print_result(result)

        assert_condition(
            result.returncode == 0,
            "Migration failed for valid source data."
        )

        assert_condition(
            destination.exists(),
            "Successful migration did not publish a destination."
        )

        assert_temporary_cleaned(temporary)

        assert_condition(
            source.exists(),
            "Original source database was removed."
        )

        source_hash_after = sha256_file(source)

        assert_condition(
            source_hash_before == source_hash_after,
            "Original source database was modified."
        )

        inspect_migrated_database(destination)

        print("\nTEST 3: PASS")
        print("Valid migration completed.")
        print("Original source preserved.")
        print("Migrated database independently inspected.")

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    print("\n" + "=" * 65)
    print("MIGRATION FAILURE TEST SUITE: PASS")
    print("Tests passed: 3")
    print("Tests failed: 0")
    print("=" * 65)


if __name__ == "__main__":

    try:
        run_tests()

    except Exception as error:
        print("\n" + "=" * 65)
        print("MIGRATION FAILURE TEST SUITE: FAIL")
        print("=" * 65)
        print(type(error).__name__ + ":", error)
        raise

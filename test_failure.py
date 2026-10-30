import os
import shutil
import sqlite3
import tempfile
import subprocess
import sys

def setup_fixture(fixture_path):
    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    conn = sqlite3.connect(fixture_path)
    conn.execute("CREATE TABLE accounts (account_id TEXT, balance REAL, status TEXT, opening_balance REAL, customer_id TEXT, created_at TEXT)")
    conn.execute("INSERT INTO accounts VALUES ('ACC-A', 1000.00, 'Active', 1000.00, 'C1', '2026-01-01')")
    conn.execute("CREATE TABLE ledger (tx_id INTEGER, account_id TEXT, amount REAL, type TEXT, related_account_id TEXT, timestamp TEXT, description TEXT)")
    conn.execute("INSERT INTO ledger VALUES (1, 'ACC-A', 1000.00, 'Deposit', NULL, '2026-01-01', 'Init')")
    conn.commit()
    conn.close()

def run_tests():
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Running isolated tests in {tmpdir}")
        
        src_path = os.path.join(tmpdir, "fixtures", "pre_migration.db")
        dst_path = os.path.join(tmpdir, "banking.db")
        script_path = os.path.abspath("migrate_to_cents.py")
        
        setup_fixture(src_path)
        
        with open(dst_path, "w") as f:
            f.write("ORIGINAL_VALID_STATE")

        env = os.environ.copy()
        env["MIG_SRC"] = src_path
        env["MIG_DST"] = dst_path
        env["MIG_TMP"] = os.path.join(tmpdir, "banking.db.tmp")
        env["MIG_BAK"] = os.path.join(tmpdir, "fixtures", "backup.db")

        # --- TEST 1: Pre-migration failure (Missing Source) ---
        print("\n--- Test 1: Pre-migration failure (Missing Source) ---")
        hidden_path = src_path + ".hidden"
        os.rename(src_path, hidden_path)
        
        try:
            result = subprocess.run([sys.executable, script_path], env=env, capture_output=True, text=True)
            assert result.returncode != 0, "Expected failure, but script succeeded"
            assert "Source database not found" in result.stderr, "Did not catch missing source"
            with open(dst_path, "r") as f:
                assert f.read() == "ORIGINAL_VALID_STATE", "FAIL: Destination was destroyed!"
            print("✅ PASS: Original destination preserved.")
        finally:
            if os.path.exists(hidden_path):
                os.rename(hidden_path, src_path)

        # --- TEST 2: Mid-migration failure (Invalid Data) ---
        print("\n--- Test 2: Mid-migration failure (Corrupt Source Data) ---")
        conn = sqlite3.connect(src_path)
        conn.execute("INSERT INTO accounts VALUES ('ACC-B', 10.005, 'Active', 10.005, 'C2', '2026-01-01')")
        conn.commit()
        conn.close()

        result = subprocess.run([sys.executable, script_path], env=env, capture_output=True, text=True)
        assert result.returncode != 0, "Expected failure, but script succeeded"
        assert "Sub-cent value detected" in result.stderr, "Did not catch sub-cent value"
        with open(dst_path, "r") as f:
            assert f.read() == "ORIGINAL_VALID_STATE", "FAIL: Destination was modified!"
        assert not os.path.exists(env["MIG_TMP"]), "FAIL: Temp file was not cleaned up."
        print("✅ PASS: Original destination preserved and temp file cleaned up.")

        # --- TEST 3: Successful Migration ---
        print("\n--- Test 3: Successful Migration ---")
        # Remove the corrupt record to allow success
        conn = sqlite3.connect(src_path)
        conn.execute("DELETE FROM accounts WHERE account_id = 'ACC-B'")
        conn.commit()
        conn.close()

        result = subprocess.run([sys.executable, script_path], env=env, capture_output=True, text=True)
        assert result.returncode == 0, f"Expected success, but failed: {result.stderr}"
        
        # Verify files
        assert os.path.exists(dst_path), "FAIL: Destination missing"
        assert not os.path.exists(env["MIG_TMP"]), "FAIL: Temp file not cleaned up"
        
        # Verify backup contents
        assert os.path.exists(env["MIG_BAK"]), "FAIL: Backup was not created"
        with open(env["MIG_BAK"], "r") as f:
            assert f.read() == "ORIGINAL_VALID_STATE", "FAIL: Backup does not contain the original destination."

        # Verify data in destination
        conn = sqlite3.connect(dst_path)
        row = conn.execute("SELECT balance FROM accounts WHERE account_id = 'ACC-A'").fetchone()
        assert row[0] == 100000, f"FAIL: Balance was {row[0]}, expected 100000"
        
        ledger_row = conn.execute("SELECT tx_id, amount FROM ledger WHERE account_id = 'ACC-A'").fetchone()
        assert ledger_row[0] == 1, f"FAIL: tx_id was {ledger_row[0]}, expected 1"
        assert ledger_row[1] == 100000, f"FAIL: Ledger amount was {ledger_row[1]}, expected 100000"
        conn.close()
        
        print("✅ PASS: Migration succeeded, data is correct, backup verified.")

if __name__ == "__main__":
    run_tests()

import os
import shutil
import sqlite3
import tempfile
import subprocess

def setup_fixture(fixture_path):
    # Create a dummy source DB
    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    conn = sqlite3.connect(fixture_path)
    conn.execute("CREATE TABLE accounts (account_id TEXT, balance REAL, status TEXT, opening_balance REAL, customer_id TEXT, created_at TEXT)")
    conn.execute("INSERT INTO accounts VALUES ('ACC-A', 1000.00, 'Active', 1000.00, 'C1', '2026-01-01')")
    conn.execute("CREATE TABLE ledger (tx_id INTEGER, account_id TEXT, amount REAL, type TEXT, related_account_id TEXT, timestamp TEXT, description TEXT)")
    conn.commit()
    conn.close()

def run_tests():
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Running isolated tests in {tmpdir}")
        
        # Setup paths inside the sandbox
        src_path = os.path.join(tmpdir, "fixtures", "pre_migration.db")
        dst_path = os.path.join(tmpdir, "banking.db")
        script_path = os.path.abspath("migrate_to_cents.py") # Use actual script
        
        # Create dummy source
        setup_fixture(src_path)
        
        # Create dummy destination to represent "Original Valid State"
        with open(dst_path, "w") as f:
            f.write("ORIGINAL_VALID_STATE")

        env = os.environ.copy()
        env["MIG_SRC"] = src_path
        env["MIG_DST"] = dst_path
        env["MIG_TMP"] = os.path.join(tmpdir, "banking.db.tmp")
        env["MIG_BAK"] = os.path.join(tmpdir, "fixtures", "backup.db")

        # --- TEST 1: Missing Source (Pre-migration failure) ---
        print("\n--- Test 1: Pre-migration failure (Missing Source) ---")
        os.rename(src_path, src_path + ".hidden")
        
        result = subprocess.run(["python", script_path], env=env, capture_output=True, text=True)
        
        assert result.returncode != 0, "Expected failure, but script succeeded"
        assert "Source database not found" in result.stderr, "Did not catch missing source"
        
        with open(dst_path, "r") as f:
            assert f.read() == "ORIGINAL_VALID_STATE", "FAIL: Destination was destroyed!"
        print("✅ PASS: Original destination preserved.")
        
        # Restore source
        os.rename(src_path + ".hidden", src_path)

        # --- TEST 2: Mid-migration failure (Invalid Data) ---
        print("\n--- Test 2: Mid-migration failure (Corrupt Source Data) ---")
        # Inject a sub-cent value into the source to trigger a failure during processing
        conn = sqlite3.connect(src_path)
        conn.execute("INSERT INTO accounts VALUES ('ACC-B', 10.005, 'Active', 10.005, 'C2', '2026-01-01')")
        conn.commit()
        conn.close()

        result = subprocess.run(["python", script_path], env=env, capture_output=True, text=True)
        
        assert result.returncode != 0, "Expected failure, but script succeeded"
        assert "Sub-cent value detected" in result.stderr, "Did not catch sub-cent value"
        
        with open(dst_path, "r") as f:
            assert f.read() == "ORIGINAL_VALID_STATE", "FAIL: Destination was modified or destroyed!"
        
        assert not os.path.exists(env["MIG_TMP"]), "FAIL: Temporary file was not cleaned up."
        print("✅ PASS: Original destination preserved and temp file cleaned up.")

if __name__ == "__main__":
    run_tests()

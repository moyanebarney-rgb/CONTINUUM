import os

# 1. Create a dummy destination file to simulate existing state
with open("banking.db", "w") as f: 
    f.write("ORIGINAL_VALID_STATE")

# 2. Hide the source to simulate a missing file
os.rename("fixtures/pre_migration.db", "fixtures/pre_migration.db.hidden")

try:
    # 3. Attempt migration
    from migrate_to_cents import run_migration
    run_migration()
except FileNotFoundError as e:
    print(f"✅ Migration failed as expected: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")

# 4. Verify the original destination is untouched
with open("banking.db", "r") as f:
    content = f.read()
    if content == "ORIGINAL_VALID_STATE":
        print("✅ PASS: Original destination preserved.")
    else:
        print("❌ FAIL: Destination was corrupted or overwritten.")

# 5. Verify temp file was cleaned up
if os.path.exists("banking.db.tmp"):
    print("❌ FAIL: Temporary database file was not cleaned up.")
else:
    print("✅ PASS: Temporary file cleaned up.")

# 6. Clean up
os.rename("fixtures/pre_migration.db.hidden", "fixtures/pre_migration.db")

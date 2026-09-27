import sqlite3, csv, os, hashlib
from decimal import Decimal, ROUND_HALF_UP

def cents(v):
    return int((Decimal(str(v)) * Decimal("100"))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

pre  = sqlite3.connect("fixtures/pre_migration_backup.db"); pre.row_factory  = sqlite3.Row
post = sqlite3.connect("banking.db");                       post.row_factory = sqlite3.Row

rows = []

tables = {r[0] for r in post.execute(
    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
rows.append(("MIG-STR", "structural: tables present", True,
             "schema_version" in tables and "accounts" in tables and "ledger" in tables))

bal_type = post.execute("SELECT typeof(balance) FROM accounts LIMIT 1").fetchone()
rows.append(("MIG-TYP", "balance column is INTEGER", "integer",
             bal_type[0] if bal_type else None))

rows.append(("MIG-ACC", "account count",
             pre.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
             post.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]))
rows.append(("MIG-LGR", "ledger count",
             pre.execute("SELECT COUNT(*) FROM ledger").fetchone()[0],
             post.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]))

expected_total = 0
for r in pre.execute("SELECT account_id, balance FROM accounts"):
    expected = cents(r["balance"])
    expected_total += expected
    actual = post.execute("SELECT balance FROM accounts WHERE account_id=?",
                          (r["account_id"],)).fetchone()["balance"]
    rows.append((f"MIG-{r['account_id']}", f"convert {r['account_id']}",
                 expected, actual))

rows.append(("MIG-TOT", "total value (cents)", expected_total,
             post.execute("SELECT SUM(balance) FROM accounts").fetchone()[0]))

for r in post.execute("SELECT account_id, balance, opening_balance FROM accounts"):
    derived = (r["opening_balance"] +
               post.execute("SELECT COALESCE(SUM(amount),0) FROM ledger "
                            "WHERE account_id=?", (r["account_id"],)).fetchone()[0])
    rows.append((f"REC-{r['account_id']}", f"reconcile {r['account_id']}",
                 r["balance"], derived))

rows.append(("MIG-SCH", "schema version", 2,
             post.execute("SELECT version FROM schema_version "
                          "ORDER BY applied_at DESC LIMIT 1").fetchone()[0]))

os.makedirs("evidence/migration", exist_ok=True)
out = "evidence/migration/migration_results.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check_id", "description", "expected", "actual", "status"])
    for cid, desc, exp, act in rows:
        w.writerow([cid, desc, exp, act, "PASS" if exp == act else "FAIL"])

with open(out, "rb") as f:
    digest = hashlib.sha256(f.read()).hexdigest()
with open(out + ".sha256", "w") as f:
    f.write(f"{digest}  migration_results.csv\n")

for cid, desc, exp, act in rows:
    flag = "PASS" if exp == act else "FAIL"
    print(f"{flag}  {cid:8} {desc:28} expected={exp!r:>10} actual={act!r:>10}")

all_pass = all(exp == act for _, _, exp, act in rows)
print()
print("MIGRATION GATE:", "PASS" if all_pass else "FAIL")
print("SHA-256:       ", digest)

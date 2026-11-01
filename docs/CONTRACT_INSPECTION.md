# Migration Contract Inspection & Remediation

## Findings
A post-implementation contract inspection of `migrate_to_cents.py` revealed three critical vulnerabilities:
1. **Foreign Key Illusion:** SQLite disables foreign key enforcement by default. The script created the constraint but never executed `PRAGMA foreign_keys = ON;`, allowing orphaned ledger rows.
2. **Null Poisoning:** The conversion function `Decimal(str(v))` crashed with `InvalidOperation` if it encountered a `NULL` value, halting the migration mid-process.
3. **Atomicity Gap:** The inserts were not wrapped in an explicit transaction block, risking partial writes if a crash occurred.

## Evidence
The vulnerabilities were reproduced in the execution environment (capturing the `InvalidOperation` traceback and the successful insertion of a foreign key orphan).

## Remediation
`migrate_to_cents.py` was patched to:
- Execute `PRAGMA foreign_keys = ON;` immediately after connecting.
- Use a `safe_cents()` wrapper to handle `NULL` values gracefully.
- Wrap the `INSERT` loops in a `with dst:` transaction block for atomicity.

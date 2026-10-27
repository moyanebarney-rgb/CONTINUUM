# Recovery Proof

## Executive summary
1. **What was tested:** Capability to destroy the runtime, reconstruct from committed inputs, and reproduce evidence.
2. **What persisted:** Git repository, committed evidence sidecars, committed generators.
3. **What disappeared:** SQLite databases (`banking.db`), generated CSVs, runtime memory.
4. **What matched:** Level 2 (financial reconciliation) PASSED. Level 1 (artifact hashes) MATCHED committed sidecars.

## 1. What was tested
The recovery drill executed from a clean environment. State was destroyed, then reconstructed purely from committed Git inputs.

## 2. What persisted
The GitHub remote, the committed Python scripts (`build_fixture.py`, `migrate_to_cents.py`, etc.), and the committed `.sha256` sidecars.

## 3. What disappeared
The working clones, the `banking.db` files, the generated `evidence/` CSVs, and all Python in-memory state.

## 4. What was reconstructed
A fresh clone was pulled. The pipeline (`build_fixture` → `migrate_to_cents` → `verify_migration` → `build_day5_aggregate`) was executed sequentially.

## 5. What matched

### Level 2 — Internal reconciliation (primary)
PASS. Exact integer match for all accounts (`ACC-A`, `ACC-B`, `ACC-C`). `opening_balance + Σ ledger.amount = closing_balance`.

### Level 1 — Byte-identical artifacts (diagnostic)
MATCH. 
- `day5_results.csv` matched the committed sidecar (`17d0972e...`).
- `migration_results.csv` matched the committed sidecar (`4099a01c...`).

## 6. Reconciliation
The independent SQL query confirmed internal consistency across the reconstructed database.

## 7. Observed limitations
The drill tests evidence regeneration and internal ledger consistency. It does not test database-file byte equivalence or full-chain settlement alignment.

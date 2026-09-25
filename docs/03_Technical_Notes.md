# 03 — Technical Notes

## Ledger row semantics (verified by F1-004)

- create_account → 0 ledger rows
- deposit        → 1 ledger row
- withdraw       → 1 ledger row
- transfer       → 2 ledger rows (Transfer Out + Transfer In)

Any test asserting ledger count must account for this.

Verified: 2026-09-22, from evidence/day5/day5_flow1_happy_path.csv

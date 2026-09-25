# Technical Notes

Working notes for CONTINUUM. Decisions with rationale belong in
`DECISIONS.md`. This file captures verified behaviour, invariants, and
non-obvious facts that would otherwise be re-derived.

## Ledger row semantics

Verified 2026-09-22, from `evidence/day5/day5_flow1_happy_path.csv`.

| Operation | Ledger rows |
|---|---|
| `create_account` | 0 |
| `deposit` | 1 |
| `withdraw` | 1 |
| `transfer` | 2 (Transfer Out + Transfer In) |

Any test asserting ledger count must account for this. The off-by-one
error in Flow 2's initial specification came from assuming
`create_account` writes a ledger row. It does not.

## External vs internal identifiers

- Internal `id` will be the canonical ledger key (immutable UUID).
- External identifiers will be stored separately for reconciliation and
  tracing.
- External identifiers must never serve as ledger primary keys.
- Constraint scope varies per identifier — see `DECISIONS.md` ADR-007.

Source: Shashank Chaudhary, 2026-09-25.

## Monetary representation invariant

Current implementation stores amounts as integer cents (`get_balance_cents()`).
Any schema change must preserve this. `REAL`/floating-point amounts are not
acceptable in the ledger. See `DECISIONS.md` ADR-001.

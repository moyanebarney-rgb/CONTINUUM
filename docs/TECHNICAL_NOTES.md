## External vs internal identifiers

- Internal `id` will be the canonical ledger key (immutable UUID).
- External identifiers will be stored separately for reconciliation and tracing.
- External identifiers must never serve as ledger primary keys.
- Constraint scope varies per identifier — see `DECISIONS.md`.

Source: Shashank Chaudhary, 2026-09-25.

## Monetary representation invariant

Current implementation stores amounts as integer cents (`get_balance_cents()`).
Any schema change must preserve this. `REAL`/floating-point amounts are not
acceptable in the ledger.

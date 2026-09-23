# Architecture Decision Records

## ADR-001 — Integer cents for monetary values

**Context:** Floating-point arithmetic produces rounding errors on
values as simple as `0.10 + 0.20`. Text-based money storage breaks SQL
aggregation.

**Decision:** All monetary values are stored as `INTEGER` cents.
Conversion happens only at system boundaries, using `Decimal` with
half-up rounding.

**Consequences:**

- Exact arithmetic and direct SQL aggregation (`SUM`, `>=`).
- Requires explicit conversion at the presentation layer.
- Sum-then-convert is forbidden. Convert-then-sum is required, because
  `sum(rand_to_cents(x_i))` and `rand_to_cents(sum(x_i))` diverge under
  float drift.

## ADR-002 — `BEGIN IMMEDIATE` for all write transactions

**Context:** SQLite supports deferred, immediate, and exclusive
transaction modes. Deferred transactions can fail mid-work when the
write lock is claimed later.

**Decision:** All write transactions use `BEGIN IMMEDIATE`.

**Consequences:**

- The write lock is acquired before validation and mutation.
- A `started` flag is required in the rollback path, so that a failed
  `BEGIN` does not itself raise a secondary error.
- Concurrent writers queue rather than fail unpredictably.

## ADR-003 — Append-only ledger

**Context:** A production banking ledger cannot have rows edited or
deleted. Corrections must be traceable.

**Decision:** The `ledger` table is append-only. Account balances are
derived from `opening_balance + Σ ledger.amount`.

**Consequences:**

- Reversals and corrections are posted as new entries, not mutations.
- The audit trail is preserved indefinitely.
- Balance queries require aggregation, but the invariant is provable
  and reconcilable at any point in time.

## ADR-004 — Schema versioning

**Context:** A database without explicit schema identity forces the
runtime environment to infer which structural contract it satisfies.

**Decision:** A `schema_version` table records every migration applied,
with timestamp and note.

**Consequences:**

- The database explains its own structural history.
- Migration scripts read and update the version explicitly.
- Version 1 = pre-integer-cents schema. Version 2 = integer-cents.

## ADR-005 — Two-level recovery comparison

**Context:** Byte-identical hashing and financial correctness answer
different questions. Conflating them means a legitimate timestamp
difference can be mistaken for a financial defect.

**Decision:** Recovery drills report two levels independently:

- **Level 1** — byte-identical artifact (`sha256(a) == sha256(b)`)
- **Level 2** — financial/semantic equivalence (independent reconciliation)

**Consequences:**

| Level 1 | Level 2 | Meaning |
|---|---|---|
| Match | Pass | Full reproducibility |
| Mismatch | Pass | Reproducibility note (ordering, timestamps) |
| Match | Fail | Serious defect — verifier is weak |
| Mismatch | Fail | Investigate both dimensions |

## ADR-006 — Reproducible aggregate, not archival

**Context:** The original `day5_results.csv` aggregate was generated
inside a Colab runtime and committed only as a SHA-256 sidecar before
the runtime reset. The sidecar survived; the file it protected did not.

**Decision:** Commit the generator script (`build_day5_aggregate.py`),
not just the output.

**Consequences:**

- Anyone cloning the repo can regenerate the aggregate from committed
  inputs and verify the hash independently.
- The evidence chain is reproducible, not merely archival.
- A missing aggregate is recoverable, not fatal.

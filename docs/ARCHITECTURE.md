# Architecture

## Layered model

```text
Financial invariants
        ↓
Transaction safety
        ↓
Persistent state
        ↓
Migration equivalence
        ↓
Independent reconciliation
        ↓
Evidence integrity
        ↓
Runtime recovery
```

## Transaction boundary

Every write operation executes inside a single SQLite transaction:

```text
BEGIN IMMEDIATE
      ↓
validate account existence and status
      ↓
validate amount and available funds
      ↓
apply balance mutations
      ↓
append ledger event(s)
      ↓
COMMIT          (or ROLLBACK on any failure)
```

`BEGIN IMMEDIATE` acquires the write lock upfront. A `started` flag
guards the rollback so that a failed `BEGIN` does not itself raise a
secondary error.

## Authority hierarchy

| Layer | Authority |
|---|---|
| Code | Git repository |
| Schema | Migration scripts + `schema_version` table |
| Financial state | `banking.db` (integer cents) |
| Historical protection | Backups (migration/restore only) |
| Evidence | Canonical CSV/MD + SHA-256 sidecar |
| Environment | Canonical manifest |
| Execution | Colab notebook (disposable) |

## Three distinct integrity questions

| Question | Mechanism |
|---|---|
| Has this file changed? | SHA-256 of the canonical evidence file |
| Does the ledger satisfy its properties? | Invariants + independent reconciliation |
| Can another runtime reproduce it? | Recovery drill + two-level compare |

These are not the same question, and no mechanism substitutes for another.

## Stage 3 gate — six checks

Migration success is not established by a script exiting 0. All six
checks must pass independently:

1. Structural verification — column types, constraints, `schema_version`
2. Population verification — account count, ledger count
3. Independent cents conversion — recomputed from the pre-migration backup
4. Financial reconciliation — `Opening + Σ Ledger = Closing` per account
5. Schema-version verification — the migrated DB self-identifies
6. Preserved evidence — hashed artifacts that can be re-checked later

## Related

- [DECISIONS.md](DECISIONS.md)
- [RECOVERY.md](RECOVERY.md)

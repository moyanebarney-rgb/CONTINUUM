# CONTiNUUM

*Financial state & transaction integrity*

CONTiNUUM is a reproducible financial state system designed to demonstrate
transactional integrity, exact monetary representation, independent
reconciliation, failure rollback, schema migration, evidence integrity,
and runtime recovery.

The project asks:

> Can financial state remain continuous, verifiable, and reproducible
> across change, failure, and recovery?

## Architecture

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

## Status

```text
Flow 1:    Happy path                          ✅ complete
Flow 2:    Daily grind                         ✅ complete (+ preserved spec-error history)
Flow 3:    Transfer                            ✅ complete
Flow 4:    Insufficient funds                  ✅ complete
Flow 5:    Frozen account                      ✅ complete
Aggregate: 30/30 checks PASS                   ✅ reproducible + sealed
Migration: 12/12 rows PASS                     ✅ clean-clone verified
```

## Four Gates

| Gate | Test | Status |
|---|---|---|
| Failure | Injected/rejected ops leave no partial state | ✅ 30/30 (flows 1–5) |
| Evidence | Verified result → artifact → SHA-256 | ✅ clean-clone verified |
| Migration | Old → New → Independent reconciliation | ✅ 7 categories / 12 rows PASS |
| Recovery | Execute → Destroy → Reconstruct → Two-level compare | ⏳ pending |

## Key Properties

- Integer cents as source of truth. No floating-point money.
- `BEGIN IMMEDIATE` for atomic transfers.
- Append-only ledger. Balances derived, never edited.
- Startup reconciliation: `Opening + Σ Ledger = Closing`.
- Schema versioning for migration history.
- Hashed evidence for tamper-evident artifacts.

## Evidence

### Day 5 — Flow verification

Flow-level evidence is committed under `evidence/day5/`:

```text
evidence/day5/
├── day5_flow1_happy_path.csv
├── day5_flow2_daily_grind.csv
├── day5_flow2_daily_grind_v1_spec_error.csv
├── day5_flow2_analysis.md
├── day5_flow3_transfer.csv
├── day5_flow4_insufficient_funds.csv
├── day5_flow5_frozen_account.csv
└── day5_results.csv.sha256
```

`day5_results.csv` itself is not committed. It is regenerated on demand by
`build_day5_aggregate.py` and verified against the committed sidecar.

Aggregate fingerprint:

```text
17d0972e5b0035cc6f6c754d25985d2be87f815c92c5d762979ac3cd374f6321
```

### Migration — Integer-cents conversion

Migration evidence is committed under `evidence/migration/`:

```text
evidence/migration/
├── migration_results.csv
└── migration_results.csv.sha256
```

The verifier executes 7 check categories, producing 12 evidence rows:

| Category | Rows |
|---|---|
| Structural | `MIG-STR` |
| Type | `MIG-TYP` |
| Population | `MIG-ACC`, `MIG-LGR` |
| Conversion | `MIG-ACC-A`, `MIG-ACC-B`, `MIG-ACC-C` |
| Total value | `MIG-TOT` |
| Reconciliation | `REC-ACC-A`, `REC-ACC-B`, `REC-ACC-C` |
| Schema version | `MIG-SCH` |

Migration fingerprint:

```text
4099a01c739e72c670045bc78cc138028aa3ea1263e7475701ae8a92fb7be373
```

### Reproducibility

Both evidence chains are regenerable from committed inputs. Anyone cloning
the repository can rebuild and verify them.

**Day 5 aggregate:**

```bash
python build_day5_aggregate.py
cd evidence/day5
sha256sum -c day5_results.csv.sha256
```

Expected output:

```text
rows written: 30
sha256:       17d0972e5b0035cc6f6c754d25985d2be87f815c92c5d762979ac3cd374f6321
day5_results.csv: OK
```

**Migration:**

```bash
python build_fixture.py
python migrate_to_cents.py
python verify_migration.py
cd evidence/migration
sha256sum -c migration_results.csv.sha256
```

Expected output:

```text
MIGRATION GATE: PASS
SHA-256:        4099a01c739e72c670045bc78cc138028aa3ea1263e7475701ae8a92fb7be373
migration_results.csv: OK
```

The original Day 5 aggregate was generated during a Colab session and
committed only as a SHA-256 sidecar before the runtime reset. The aggregate
was later regenerated from the five committed flow files, and the regenerated
digest matched the committed sidecar. A clean clone can therefore reproduce
and verify both evidence chains from committed inputs rather than relying on
an archival copy.

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [DECISIONS.md](docs/DECISIONS.md)
- [RECOVERY.md](docs/RECOVERY.md)
- [TECHNICAL_NOTES.md](docs/TECHNICAL_NOTES.md)

## Boundaries

This project does **not** claim:

- Distributed exactly-once processing
- Multi-node consistency
- Production disaster recovery
- Regulatory compliance

Correctness was verified at fixture scale: 3 accounts, 6 ledger rows,
30 test checks, 12 migration evidence rows. No performance characterization
at any other scale is claimed or implied.

## License

MIT

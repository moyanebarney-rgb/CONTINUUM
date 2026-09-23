# CONTiNUUM

## Financial State & Transaction Integrity System

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
```

## Four Gates

| Gate | Test | Status |
|---|---|---|
| Failure | Injected/rejected ops leave no partial state | ✅ 30/30 (flows 1–5) |
| Evidence | Verified result → artifact → SHA-256 | ✅ reproducible + sealed |
| Migration | Old → New → Independent reconciliation | ⏳ pending |
| Recovery | Execute → Destroy → Reconstruct → Two-level compare | ⏳ pending |

## Key Properties

- Integer cents as source of truth. No floating-point money.
- `BEGIN IMMEDIATE` for atomic transfers.
- Append-only ledger. Balances derived, never edited.
- Startup reconciliation: `Opening + Σ Ledger = Closing`.
- Schema versioning for migration history.
- Hashed evidence for tamper-evident artifacts.

## Evidence

Flow-level evidence committed under `evidence/day5/`:

```text
evidence/day5/
├── day5_flow1_happy_path.csv
├── day5_flow2_daily_grind.csv
├── day5_flow2_daily_grind_v1_spec_error.csv
├── day5_flow2_analysis.md
├── day5_flow3_transfer.csv
├── day5_flow4_insufficient_funds.csv
├── day5_flow5_frozen_account.csv
├── day5_results.csv
└── day5_results.csv.sha256
```

Aggregate fingerprint:

```text
17d0972e5b0035cc6f6c754d25985d2be87f815c92c5d762979ac3cd374f6321
```

### Reproducibility

The aggregate is regenerable from committed inputs. Anyone who clones
the repository can rebuild it and verify the seal:

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

The original aggregate was generated once during a Colab session and
committed only as a hash sidecar before the runtime reset. On recovery,
the aggregate was regenerated from the five committed flow files. The
regenerated hash matched the committed sidecar byte-for-byte, proving
the evidence chain is intact end-to-end and the aggregate is derivable
from committed inputs, not merely archival.

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [DECISIONS.md](docs/DECISIONS.md)
- [RECOVERY.md](docs/RECOVERY.md)

## Boundaries

This project does **not** claim:

- Distributed exactly-once processing
- Multi-node consistency
- Production disaster recovery
- Regulatory compliance
- High-scale performance

## License

MITRuntime recovery

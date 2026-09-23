# Recovery Drill

## Objective

Prove the ledger's testing environment survives runtime destruction.

The drill is not "I saved everything." It is a demonstrated property
that another execution can reconstruct the environment and reproduce
the evidence.

## Sequence

### Phase A — Capture

Before destroying the runtime, record:

- Evidence hash A (canonical projection of results)
- Environment hash A (stable identifiers only)
- Git commit SHA
- Schema version

### Phase B — Destroy

Reset the Colab runtime. Intentionally lose all Python state:

- Variables, imports, class definitions
- In-memory databases
- Execution history

Persist:

- Git repository
- Drive files
- Committed evidence artifacts
- Environment manifest

### Phase C — Reconstruct

Run only the canonical setup cell:

```text
mount Drive
    ↓
load project
    ↓
import bank_ledger.py
    ↓
load database
    ↓
verify schema
    ↓
run experiment
```

### Phase D — Reproduce

Generate the same evidence artifacts. Recompute both hashes.

### Phase E — Compare

Two-level comparison:

**Level 1 — byte-identical artifact**

```text
sha256(canonical_a) == sha256(canonical_b)
```

Match = identical canonical output.

**Level 2 — financial/semantic equivalence**

```text
independent reconciliation == PASS
```

Match = financial meaning preserved even if ordering or timestamps differ.

## Interpretation

| Level 1 | Level 2 | Meaning |
|---|---|---|
| Match | Pass | Full reproducibility |
| Mismatch | Pass | Reproducibility note |
| Match | Fail | Serious defect |
| Mismatch | Fail | Investigate both |

## Rule

Do not manipulate the evidence to force a match. A mismatch is
diagnostic information, not a failure to conceal.

## Exit artifacts

```text
evidence/recovery/
├── recovery_proof.md              (narrative)
├── recovery_hashes.csv            (Level 1 result)
└── recovery_reconciliation.md     (Level 2 result)
```

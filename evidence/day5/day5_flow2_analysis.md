# Flow 2 — Spec Error Analysis

## Summary

The first Flow 2 run produced two FAILs (F2-003, F2-004). These were
traced to an arithmetic error in the expected values defined in the
test harness, not a defect in the ledger.

## v1 output (preserved)

| check  | expected | actual | status |
|--------|----------|--------|--------|
| F2-001 | 250000   | 250000 | PASS   |
| F2-002 | 245000   | 245000 | PASS   |
| F2-003 | 246000   | 255000 | FAIL   |
| F2-004 | 244000   | 240000 | FAIL   |
| F2-005 | 4        | 4      | PASS   |
| F2-006 | True     | True   | PASS   |

## Diagnosis

Trace from opening balance:

    R500 (opening)
    +R2000 → R2500   (F2-001 ✓)
    -R50   → R2450   (F2-002 ✓)
    +R100  → R2550   (F2-003 spec said R2460 — wrong)
    -R150  → R2400   (F2-004 spec said R2440 — wrong)

F2-006 (reconciliation) passed in both runs, confirming that the
ledger's internal accounting was self-consistent throughout. The FAILs
were a specification mismatch, not a system defect.

## Resolution

Expected values for F2-003 and F2-004 were corrected. The rerun
produced all six PASS (see `day5_flow2_daily_grind.csv`).

Both the failing run and the corrected run are preserved here as
evidence of the diagnostic process.

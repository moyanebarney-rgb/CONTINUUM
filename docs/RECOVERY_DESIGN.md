# Recovery Drill

## Objective

Prove the ledger's testing environment survives runtime destruction.

The drill is not "I saved everything." It is a demonstrated property
that another execution can reconstruct the environment and reproduce
the evidence.

The detailed design — captures, comparison semantics, external input,
and anti-scope — lives in `RECOVERY_DESIGN.md`. This file is the
operational protocol.

## Scope boundary

Recovery covers two distinct claims. Only one is tested by this drill
in full.

**Claim A — Evidence artifact recovery.** The pipeline regenerates
byte-identical outputs from committed inputs.

**Claim B — State replay.** The ledger replays from
`opening_balance + Σ ledger.amount` to reproduce the same balances.
Tested as internal reconciliation only — not as state-equivalence of
the database file, because SQLite embeds timestamps and page ordering
that are not stable across regenerations.

**Out of scope:** alignment across authorisation, clearing, and
settlement. CONTINUUM has no clearing or settlement layer.

## Sequence

### Phase A — Pre-destruction capability check

Before destroying anything, confirm that a fresh clone regenerates the
existing evidence from committed inputs with matching hashes.

```bash
git clone https://github.com/moyanebarney-rgb/CONTINUUM.git /tmp/cap_check
cd /tmp/cap_check
python build_fixture.py
python migrate_to_cents.py
python verify_migration.py
python build_day5_aggregate.py

-- verify_recovery.sql
-- Independent reconciliation for the Recovery drill's Level 2 check.
-- Does NOT import bank_ledger.py. Does NOT call BankDatabase.reconcile().
--
-- PRE-CONDITION: schema stores `amount` as signed integer cents
--   (credits positive, debits negative). Confirm against the schema
--   before running. If amounts are stored unsigned with a direction
--   column, this query is wrong and the fix is to CASE on direction.
--
-- Usage:
--   sqlite3 banking.db < verify_recovery.sql

.headers on
.mode column

-- Per-account reconciliation: opening + signed ledger sum = stored balance
SELECT
    a.account_id,
    a.opening_balance                              AS opening,
    COALESCE(SUM(l.amount), 0)                     AS ledger_sum,
    a.opening_balance + COALESCE(SUM(l.amount), 0) AS derived,
    a.balance                                      AS stored,
    CASE
        WHEN a.opening_balance + COALESCE(SUM(l.amount), 0) = a.balance
        THEN 'PASS'
        ELSE 'FAIL'
    END                                            AS status
FROM accounts a
LEFT JOIN ledger l ON a.account_id = l.account_id
GROUP BY a.account_id, a.opening_balance, a.balance
ORDER BY a.account_id;

-- Population counts
SELECT 'accounts' AS entity, COUNT(*) AS n FROM accounts
UNION ALL
SELECT 'ledger',   COUNT(*) FROM ledger;

-- System-wide total
SELECT
    'system_total_cents' AS metric,
    SUM(balance) AS value
FROM accounts;


import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

SCHEMA_VERSION = 2

def rand_to_cents(value) -> int:
    return int((Decimal(str(value)) * Decimal("100"))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def cents_to_rand(cents: int) -> float:
    return cents / 100.0

def zar(cents: int) -> str:
    return f"R{cents / 100:,.2f}" if cents >= 0 else f"-R{abs(cents) / 100:,.2f}"

class BankDatabase:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._initialize_schema()

    def _initialize_schema(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id      TEXT PRIMARY KEY,
                    balance         INTEGER NOT NULL CHECK (balance >= 0),
                    status          TEXT NOT NULL CHECK (status IN ('Active','Frozen')),
                    opening_balance INTEGER NOT NULL DEFAULT 0,
                    customer_id     TEXT,
                    created_at      TEXT
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    tx_id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id         TEXT NOT NULL,
                    amount             INTEGER NOT NULL CHECK (amount <> 0),
                    type               TEXT NOT NULL,
                    related_account_id TEXT,
                    timestamp          TEXT NOT NULL,
                    description        TEXT,
                    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version    INTEGER NOT NULL,
                    applied_at TEXT    NOT NULL,
                    note       TEXT
                );
            """)
            if self.conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
                self.conn.execute(
                    "INSERT INTO schema_version (version, applied_at, note) VALUES (?,?,?)",
                    (SCHEMA_VERSION,
                     datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "initialised"))

    def _execute_atomic(self, operations):
        started = False
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            started = True
            operations(self.conn)
            self.conn.execute("COMMIT")
            return True, "Success"
        except Exception as e:
            if started:
                self.conn.execute("ROLLBACK")
            return False, str(e)

    def create_account(self, account_id, opening_balance=0.0,
                       status="Active", customer_id=None):
        cents = rand_to_cents(opening_balance)
        if cents < 0: return False, "Opening balance cannot be negative"
        if status not in {"Active","Frozen"}: return False, "Invalid status"
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        def ops(c):
            c.execute("INSERT INTO accounts "
                      "(account_id,balance,status,opening_balance,customer_id,created_at) "
                      "VALUES (?,?,?,?,?,?)",
                      (account_id, cents, status, cents, customer_id, ts))
        return self._execute_atomic(ops)

    def deposit(self, account_id, amount_rand, description=""):
        def ops(c):
            cents = rand_to_cents(amount_rand)
            if cents <= 0: raise ValueError("Deposit must be positive")
            r = c.execute("SELECT balance,status FROM accounts WHERE account_id=?",
                          (account_id,)).fetchone()
            if not r: raise ValueError("Account not found")
            if r["status"] == "Frozen": raise ValueError("Account is frozen")
            c.execute("UPDATE accounts SET balance = balance + ? WHERE account_id=?",
                      (cents, account_id))
            c.execute("INSERT INTO ledger "
                      "(account_id,amount,type,timestamp,description) VALUES (?,?,?,?,?)",
                      (account_id, cents, "Deposit",
                       datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       description))
        return self._execute_atomic(ops)

    def withdraw(self, account_id, amount_rand, description=""):
        def ops(c):
            cents = rand_to_cents(amount_rand)
            if cents <= 0: raise ValueError("Withdrawal must be positive")
            r = c.execute("SELECT balance,status FROM accounts WHERE account_id=?",
                          (account_id,)).fetchone()
            if not r: raise ValueError("Account not found")
            if r["status"] == "Frozen": raise ValueError("Account is frozen")
            if r["balance"] < cents: raise ValueError("Insufficient funds")
            c.execute("UPDATE accounts SET balance = balance - ? WHERE account_id=?",
                      (cents, account_id))
            c.execute("INSERT INTO ledger "
                      "(account_id,amount,type,timestamp,description) VALUES (?,?,?,?,?)",
                      (account_id, -cents, "Withdrawal",
                       datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       description))
        return self._execute_atomic(ops)

    def transfer(self, src, dst, amount_rand, description=""):
        def ops(c):
            cents = rand_to_cents(amount_rand)
            if cents <= 0: raise ValueError("Transfer must be positive")
            if src == dst: raise ValueError("Cannot self-transfer")
            s = c.execute("SELECT balance,status FROM accounts WHERE account_id=?",
                          (src,)).fetchone()
            if not s: raise ValueError("Sender not found")
            if s["status"] == "Frozen": raise ValueError("Sender frozen")
            if s["balance"] < cents: raise ValueError("Insufficient funds")
            d = c.execute("SELECT status FROM accounts WHERE account_id=?",
                          (dst,)).fetchone()
            if not d: raise ValueError("Receiver not found")
            if d["status"] == "Frozen": raise ValueError("Receiver frozen")
            c.execute("UPDATE accounts SET balance = balance - ? WHERE account_id=?",
                      (cents, src))
            c.execute("UPDATE accounts SET balance = balance + ? WHERE account_id=?",
                      (cents, dst))
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            c.execute("INSERT INTO ledger "
                      "(account_id,amount,type,related_account_id,timestamp,description) "
                      "VALUES (?,?,?,?,?,?)",
                      (src, -cents, "Transfer Out", dst, ts, description))
            c.execute("INSERT INTO ledger "
                      "(account_id,amount,type,related_account_id,timestamp,description) "
                      "VALUES (?,?,?,?,?,?)",
                      (dst, cents, "Transfer In", src, ts, description))
        return self._execute_atomic(ops)

    def get_balance_cents(self, account_id):
        r = self.conn.execute("SELECT balance FROM accounts WHERE account_id=?",
                              (account_id,)).fetchone()
        return r["balance"] if r else None

    def count_accounts(self):
        return self.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]

    def count_ledger(self):
        return self.conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]

    def get_schema_version(self):
        r = self.conn.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        ).fetchone()
        return r["version"] if r else None

    def reconcile(self):
        q = """
            SELECT a.account_id, a.balance, a.opening_balance,
                   COALESCE(SUM(l.amount),0) AS ledger_sum
            FROM accounts a
            LEFT JOIN ledger l ON a.account_id = l.account_id
            GROUP BY a.account_id
        """
        for row in self.conn.execute(q):
            expected = row["opening_balance"] + row["ledger_sum"]
            if row["balance"] != expected:
                raise ValueError(
                    f"RECONCILIATION FAILED {row['account_id']}: "
                    f"stored={row['balance']} expected={expected}")
        print("Reconciliation: PASSED")

    def close(self):
        self.conn.close()

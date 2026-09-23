"""
Deterministically rebuild evidence/day5/day5_results.csv
from the five committed flow files.

Usage:
    python build_day5_aggregate.py

Writes:
    evidence/day5/day5_results.csv
    evidence/day5/day5_results.csv.sha256
"""
import csv, hashlib, os

ROOT = os.path.dirname(os.path.abspath(__file__))
DAY5 = os.path.join(ROOT, "evidence", "day5")

FLOWS = [
    "day5_flow1_happy_path.csv",
    "day5_flow2_daily_grind.csv",
    "day5_flow3_transfer.csv",
    "day5_flow4_insufficient_funds.csv",
    "day5_flow5_frozen_account.csv",
]

rows = []
header_written = False

for name in FLOWS:
    path = os.path.join(DAY5, name)
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        if not header_written:
            rows.append(header)
            header_written = True
        rows.extend(reader)

agg_path = os.path.join(DAY5, "day5_results.csv")
with open(agg_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerows(rows)

with open(agg_path, "rb") as f:
    digest = hashlib.sha256(f.read()).hexdigest()

with open(agg_path + ".sha256", "w") as f:
    f.write(f"{digest}  day5_results.csv\n")

print(f"rows written: {len(rows) - 1}")
print(f"sha256:       {digest}")

"""Show the column names and first rows of a bulk file, to check its format before filtering.
Usage: python -m scripts.peek_bulk data/bulk/courts-2024-12-31.csv.bz2 [number_of_rows]"""
import sys
from app.bulk import read_rows

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
with read_rows(path) as rows:
    print("COLUMNS:", rows.fieldnames)
    for i, row in enumerate(rows):
        if i >= n:
            break
        print({k: (v[:80] + "...") if v and len(v) > 80 else v for k, v in row.items()})

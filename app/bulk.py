"""Reading CourtListener bulk files: big bz2-compressed CSV files, one row per record."""
import bz2
import csv
import datetime
import io
import json
import sys
from contextlib import contextmanager
from app import config

csv.field_size_limit(sys.maxsize)        # opinion texts are very long


@contextmanager
def read_rows(path):
    """Yields a reader of dicts (one per CSV row). path can be:
       a .csv.bz2 file, a plain .csv file, or "-" to read already-decompressed CSV from stdin."""
    if str(path) == "-":
        stream = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace", newline="")
    elif str(path).endswith(".bz2"):
        stream = bz2.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    else:
        stream = open(path, encoding="utf-8", errors="replace", newline="")
    try:
        yield csv.DictReader(stream, quotechar=config.CSV_QUOTECHAR,
                             escapechar=config.CSV_ESCAPECHAR, doublequote=True)
    finally:
        stream.close()


def progress(n, every=100_000, label="rows"):
    if n % every == 0:
        print(f"  {n:,} {label} read...", flush=True)


def save_filter_report(name, **counts):
    """SR15: remember how many rows each filter read and kept (added to the ingestion report)."""
    counts["finished_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    json.dump(counts, open(config.WORK / f"report_{name}.json", "w"))

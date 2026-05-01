"""
Standalone JSONL ingestion script.

Use this to replay battle records from any JSONL file into Postgres —
useful if a worker went down mid-run or if you want to ingest files
from multiple servers in one shot.

Usage:
    python ingest.py path/to/worker_0.jsonl [path/to/worker_1.jsonl ...]
    python ingest.py battle_logs/*.jsonl
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from recorder.battle_recorder import flush_records_to_db


def ingest_file(path: str) -> int:
    records = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Skipping malformed line {i} in {path}: {e}")
    if records:
        flush_records_to_db(records)
    return len(records)


def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <file.jsonl> [file2.jsonl ...]")
        sys.exit(1)

    files = sys.argv[1:]
    total = 0
    for path in files:
        print(f"Ingesting {path} ...", end=" ", flush=True)
        n = ingest_file(path)
        print(f"{n} battles written.")
        total += n
    print(f"Done. Total battles ingested: {total}")


if __name__ == "__main__":
    main()

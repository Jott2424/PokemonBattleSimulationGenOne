"""
Loads silver-layer CSVs (battle results, theoretical trainers, ...) into an
empty silver schema. Run sql/schema_bronze.sql + sql/schema_silver.sql (or
scripts/setup_bronze.py + scripts/setup_silver.py) first, and load bronze
data before this — battles_to_sim and theoretical_trainers_teams have FKs
into bronze.trainers/pokemon/moves.

Expects one CSV per table, named exactly "<table>.csv", all in one
directory. Not every table needs to be present — any missing file is
skipped. Tables are loaded in FK dependency order, so a table's own
referenced tables always land first regardless of the CSVs' order on disk.

Several of these tables are referenced by primary key from other tables
(sim_battles.id from sim_battle_turns/snapshots/decisions,
theoretical_trainers.pk_theoretical_trainers_id from
theoretical_trainers_teams), so this preserves the exact ids from the
CSVs rather than letting them re-serialize, then bumps each table's
sequence past the imported max so future inserts (new simulations) don't
collide with imported ids.

Skips any table that already has rows, so a run that fails partway
through can just be re-run without duplicating already-loaded tables.

Usage (run from output/):
    python scripts/load_silver_csvs.py path/to/csv_dir
"""
import argparse
import csv
import json
import os

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Different export tools default to different delimiters (comma, pipe, ...).
# csv.Sniffer's unrestricted mode will happily "detect" any repeating
# character (e.g. the underscores in column names like pk_battles_to_sim_id),
# so the candidate set is restricted to delimiters anyone would plausibly use.
_CANDIDATE_DELIMITERS = ",|;\t"


def _detect_delimiter(path):
    with open(path, newline="") as f:
        sample = f.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=_CANDIDATE_DELIMITERS).delimiter
    except csv.Error:
        return ","

# FK dependency order: each table here only references tables earlier in
# this list (plus bronze tables, already loaded), so loading in this order
# never violates a foreign key.
TABLE_LOAD_ORDER = [
    "battles_to_sim",
    "sim_battles",
    "sim_battle_team_snapshots",
    "sim_battle_turns",
    "sim_battle_decisions",
    "theoretical_trainers",
    "theoretical_trainers_teams",
    "theoretical_battles_to_sim",
]

# table -> (primary key column, sequence name). Tables with no entry here
# have no primary key of their own (sim_battle_team_snapshots/turns/decisions
# are pure fact tables keyed only by fk_battle_id) and need no sequence fixup.
SEQUENCES = {
    "battles_to_sim": ("pk_battles_to_sim_id", None),
    "sim_battles": ("id", None),
    "theoretical_trainers": ("pk_theoretical_trainers_id", "theoretical_trainers_id_seq"),
    "theoretical_trainers_teams": ("pk_theoretical_trainers_teams_id", None),
    "theoretical_battles_to_sim": ("pk_theoretical_battles_to_sim_id", None),
}


def reset_sequence(cur, table, pk_col, seq_name):
    if seq_name is None:
        cur.execute("SELECT pg_get_serial_sequence(%s, %s)", (f"silver.{table}", pk_col))
        row = cur.fetchone()
        seq_name = row[0] if row else None
        if seq_name is None:
            return

    cur.execute(f"SELECT MAX({pk_col}) FROM silver.{table}")
    max_id = cur.fetchone()[0]
    if max_id is not None:
        cur.execute("SELECT setval(%s, %s)", (seq_name, max_id))


def load_table(cur, csv_dir, table):
    path = os.path.join(csv_dir, f"{table}.csv")
    if not os.path.exists(path):
        print(f"  Skipping silver.{table}: no {table}.csv found in {csv_dir}")
        return

    cur.execute(f"SELECT COUNT(*) FROM silver.{table}")
    if cur.fetchone()[0] > 0:
        print(f"  Skipping silver.{table}: already has rows")
        return

    df = pd.read_csv(path, sep=_detect_delimiter(path))
    df = df.replace({np.nan: None})

    columns = ",".join(df.columns)
    data_tuples = [tuple(x) for x in df.itertuples(index=False, name=None)]
    sql = f"INSERT INTO silver.{table} ({columns}) VALUES %s"
    execute_values(cur, sql, data_tuples)
    print(f"  {len(df)} rows inserted into silver.{table}")

    if table in SEQUENCES:
        pk_col, seq_name = SEQUENCES[table]
        reset_sequence(cur, table, pk_col, seq_name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_dir", help="Directory containing <table>.csv files")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(script_dir, "config.json")) as f:
        config = json.load(f)

    db = config["database"]
    conn = psycopg2.connect(
        host=db["host"], port=db["port"], dbname=db["dbname"],
        user=db["user"], password=db["password"], options=db.get("options", "")
    )
    with conn:
        with conn.cursor() as cur:
            for table in TABLE_LOAD_ORDER:
                load_table(cur, args.csv_dir, table)
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()

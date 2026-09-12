"""
Loads bronze reference-data CSVs (games, pokemon, moves, types, trainers,
teams, ...) into an empty bronze schema. Run sql/schema_bronze.sql (or
scripts/setup_bronze.py) first.

Expects one CSV per table, named exactly "<table>.csv" (e.g. games.csv,
pokemon.csv, trainers_teams.csv), all in one directory. Tables are loaded
in FK dependency order, so a table's own referenced tables always land
first regardless of the CSVs' order on disk.

Skips any table that already has rows, so a run that fails partway through
can just be re-run without duplicating already-loaded tables.

Usage (run from output/):
    python scripts/load_bronze_csvs.py path/to/csv_dir
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# FK dependency order: each table here only references tables earlier in
# this list, so loading in this order never violates a foreign key.
TABLE_LOAD_ORDER = [
    "games",
    "locations",
    "types",
    "moves_damage_categories",
    "moves",
    "pokemon",
    "pokemon_stats",
    "trainer_types",
    "trainers",
    "rival_scenarios",
    "trainers_teams",
    "moves_stats",
    "types_effectiveness",
]


def load_table(cur, csv_dir, table):
    path = os.path.join(csv_dir, f"{table}.csv")
    if not os.path.exists(path):
        print(f"  Skipping bronze.{table}: no {table}.csv found in {csv_dir}")
        return

    cur.execute(f"SELECT COUNT(*) FROM bronze.{table}")
    if cur.fetchone()[0] > 0:
        print(f"  Skipping bronze.{table}: already has rows")
        return

    df = pd.read_csv(path)
    df = df.replace({np.nan: None})

    columns = ",".join(df.columns)
    data_tuples = [tuple(x) for x in df.itertuples(index=False, name=None)]
    sql = f"INSERT INTO bronze.{table} ({columns}) VALUES %s"
    execute_values(cur, sql, data_tuples)
    print(f"  {len(df)} rows inserted into bronze.{table}")


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

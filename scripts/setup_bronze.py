import json
import os
import psycopg2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.dirname(SCRIPT_DIR)

with open(os.path.join(OUTPUT_DIR, "config.json")) as f:
    config = json.load(f)

db = config["database"]
conn = psycopg2.connect(
    host=db["host"],
    port=db["port"],
    dbname=db["dbname"],
    user=db["user"],
    password=db["password"],
    options=db.get("options", "")
)

sql_path = os.path.join(OUTPUT_DIR, "sql", "schema_bronze.sql")
with open(sql_path) as f:
    sql = f.read()

with conn:
    with conn.cursor() as cur:
        cur.execute(sql)

conn.close()
print("Bronze schema created successfully.")

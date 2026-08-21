import json
import os
import psycopg2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(SCRIPT_DIR, "config.json")) as f:
    config = json.load(f)

db = config["database"]
limit = config["simulation"]["insert_battle_limit"]

conn = psycopg2.connect(
    host=db["host"],
    port=db["port"],
    dbname=db["dbname"],
    user=db["user"],
    password=db["password"],
    options=db.get("options", "")
)

sql = """
INSERT INTO silver.battles_to_sim
    (fk_trainers_id_one, fk_trainers_id_two, logic_profile_trainer1, logic_profile_trainer2, status)
SELECT
    t1.pk_trainers_id,
    t2.pk_trainers_id,
    p.profile1,
    p.profile2,
    'pending'
FROM bronze.trainers t1
JOIN bronze.trainers t2
    ON t2.pk_trainers_id > t1.pk_trainers_id
    AND t2.fk_games_id IN (2, 3)
CROSS JOIN (VALUES
    ('random',     'random'),
    ('random',     'no_swap'),
    ('random',     'type_aware'),
    ('no_swap',    'random'),
    ('no_swap',    'no_swap'),
    ('no_swap',    'type_aware'),
    ('type_aware', 'random'),
    ('type_aware', 'no_swap'),
    ('type_aware', 'type_aware')
) AS p(profile1, profile2)
WHERE t1.fk_games_id IN (2, 3)
  AND NOT EXISTS (
      SELECT 1 FROM silver.battles_to_sim x
      WHERE x.fk_trainers_id_one = t1.pk_trainers_id
        AND x.fk_trainers_id_two = t2.pk_trainers_id
        AND x.logic_profile_trainer1 = p.profile1
        AND x.logic_profile_trainer2 = p.profile2
  )
ORDER BY random()
LIMIT %s;
"""

with conn:
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        print(f"{cur.rowcount} battles inserted (limit was {limit}).")

conn.close()

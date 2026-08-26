"""
Queues battles for Blue-only trainer matchups. Every (trainer1, trainer2,
profile1, profile2) matchup gets a flat target of SAMPLES_PER_COMBO (10)
simulations — no decisiveness evaluation.

Only stages smart-vs-smart battles: cleanest signal for team-strength/
win-probability modeling, without random/no_swap/type_aware noise diluting
which team actually played better. Add more rows to the VALUES clause below
if broader profile coverage is ever needed again.

Finds every specific sample_index (1-10) that's still missing for each
matchup — via NOT EXISTS on the exact (matchup, sample_index) tuple, not
an offset from the current max — so a run that gets truncated by
insert_battle_limit never leaves a permanent gap: whatever's still
missing gets picked up correctly on the next run regardless of how
sparse the existing data is.

Usage (run from output/):
    python scripts/populate_battles.py
"""
import json
import os

import psycopg2

BLUE_GAME_ID = 2
SAMPLES_PER_COMBO = 10

SQL = """
INSERT INTO silver.battles_to_sim
    (fk_trainers_id_one, fk_trainers_id_two, logic_profile_trainer1, logic_profile_trainer2,
     sample_index, status)
SELECT
    t1.pk_trainers_id,
    t2.pk_trainers_id,
    p.profile1,
    p.profile2,
    s.sample_index,
    'pending'
FROM bronze.trainers t1
JOIN bronze.trainers t2
    ON t2.pk_trainers_id > t1.pk_trainers_id
    AND t2.fk_games_id = %(blue)s
CROSS JOIN (VALUES
    ('smart', 'smart')
) AS p(profile1, profile2)
CROSS JOIN generate_series(1, %(samples)s) AS s(sample_index)
WHERE t1.fk_games_id = %(blue)s
  AND NOT EXISTS (
      SELECT 1 FROM silver.battles_to_sim x
      WHERE x.fk_trainers_id_one = t1.pk_trainers_id
        AND x.fk_trainers_id_two = t2.pk_trainers_id
        AND x.logic_profile_trainer1 = p.profile1
        AND x.logic_profile_trainer2 = p.profile2
        AND x.sample_index = s.sample_index
  )
ORDER BY random()
LIMIT %(limit)s;
"""


def main():
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(script_dir, "config.json")) as f:
        config = json.load(f)

    db = config["database"]
    limit = config["simulation"]["insert_battle_limit"]

    conn = psycopg2.connect(
        host=db["host"], port=db["port"], dbname=db["dbname"],
        user=db["user"], password=db["password"], options=db.get("options", "")
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute(SQL, {"blue": BLUE_GAME_ID, "samples": SAMPLES_PER_COMBO, "limit": limit})
            print(f"{cur.rowcount} battles queued (limit was {limit}).")
    conn.close()


if __name__ == "__main__":
    main()

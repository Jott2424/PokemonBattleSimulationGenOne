"""
Queue battles for a theoretical trainer against a set of opponents.

Usage:
    python populate_theoretical_battles.py --trainer-id 20000 --against real
    python populate_theoretical_battles.py --trainer-id 20000 --against theoretical
"""
import argparse
import os
import sys

import psycopg2.extras

sys.path.insert(0, os.path.dirname(__file__))

from db.connection import get_connection, get_cursor
from repository.trainer_repo import THEORETICAL_ID_OFFSET


def populate(conn, trainer_id: int, against: str, profile_theoretical: str, profile_opponent: str) -> int:
    with get_cursor(conn) as cur:
        if against == "real":
            cur.execute("SELECT pk_trainers_id AS id FROM trainers")
        else:
            cur.execute(
                "SELECT pk_theoretical_trainers_id AS id FROM theoretical_trainers "
                "WHERE pk_theoretical_trainers_id != %s",
                (trainer_id,),
            )
        opponent_ids = [row["id"] for row in cur.fetchall()]

        rows = [
            (trainer_id, opp_id, profile_theoretical, profile_opponent)
            for opp_id in opponent_ids
        ]
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO theoretical_battles_to_sim
                (fk_trainers_id_one, fk_trainers_id_two, logic_profile_trainer1, logic_profile_trainer2)
            VALUES (%s, %s, %s, %s)
        """, rows)

    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Queue theoretical-trainer battles")
    parser.add_argument("--trainer-id", type=int, required=True)
    parser.add_argument("--against", choices=["real", "theoretical"], required=True)
    parser.add_argument("--logic-profile-theoretical", default="type_aware")
    parser.add_argument("--logic-profile-opponent", default="type_aware")
    args = parser.parse_args()

    if args.trainer_id < THEORETICAL_ID_OFFSET:
        raise ValueError(f"--trainer-id must be >= {THEORETICAL_ID_OFFSET} (a theoretical trainer)")

    with get_connection() as conn:
        n = populate(conn, args.trainer_id, args.against,
                     args.logic_profile_theoretical, args.logic_profile_opponent)

    print(f"Queued {n} battles for theoretical trainer {args.trainer_id} against {args.against} opponents.")


if __name__ == "__main__":
    main()

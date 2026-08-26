"""
Insert a theoretical (synthetic) trainer and team into the database.

Usage (run from output/):
    python scripts/build_theoretical_trainer.py --label "All-Dragon Experiment" --team team.json

team.json is a list of 1-6 slots, each:
    {"pokemon_id": 149, "level": 55, "move_ids": [82, 91, 34, 44]}
party_order is taken from list position (starting at 1).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import get_connection, get_cursor


def build_theoretical_trainer(conn, label: str, team_spec: list) -> int:
    with get_cursor(conn) as cur:
        cur.execute(
            "INSERT INTO theoretical_trainers (label) VALUES (%s) RETURNING pk_theoretical_trainers_id",
            (label,),
        )
        trainer_id = cur.fetchone()["pk_theoretical_trainers_id"]

        for party_order, slot in enumerate(team_spec, start=1):
            move_ids = (slot["move_ids"] + [None, None, None, None])[:4]
            cur.execute("""
                INSERT INTO theoretical_trainers_teams
                    (fk_theoretical_trainers_id, fk_pokemon_id, party_order, level,
                     fk_move1_id, fk_move2_id, fk_move3_id, fk_move4_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (trainer_id, slot["pokemon_id"], party_order, slot["level"], *move_ids))

    return trainer_id


def main():
    parser = argparse.ArgumentParser(description="Build a theoretical trainer/team")
    parser.add_argument("--label", required=True, help="Human-readable name for this team")
    parser.add_argument("--team", required=True, help="Path to a JSON team spec file")
    args = parser.parse_args()

    with open(args.team) as f:
        team_spec = json.load(f)

    if not 1 <= len(team_spec) <= 6:
        raise ValueError("Team must have 1-6 Pokemon")

    with get_connection() as conn:
        trainer_id = build_theoretical_trainer(conn, args.label, team_spec)

    print(f"Created theoretical trainer id {trainer_id}: {args.label}")


if __name__ == "__main__":
    main()

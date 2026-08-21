"""
Writes battle results to disk (JSONL) and/or Postgres.

Strategy:
- Each worker appends completed battle records to a local JSONL file.
- After every `flush_every_n` battles, the buffer is bulk-inserted into Postgres.
- A separate ingest.py script can replay any JSONL file into Postgres independently.

JSONL format: one JSON object per line, with keys:
  "meta"       - sim_battles row
  "snapshots"  - list of sim_battle_team_snapshots rows
  "turns"      - list of sim_battle_turns rows
  "decisions"  - list of sim_battle_decisions rows
"""
import json
import os
from typing import List, Optional

import psycopg2.extras

from battle.battle import BattleResult, TurnEvent, DecisionEvent
from db.connection import get_connection, get_cursor


def result_to_record(result: BattleResult) -> dict:
    """Convert a BattleResult into a serializable dict ready for JSONL or DB insert."""
    meta = {
        "fk_trainer1_id": result.trainer1_id,
        "fk_trainer2_id": result.trainer2_id,
        "logic_profile_1": result.logic_profile_1,
        "logic_profile_2": result.logic_profile_2,
        "seed": result.seed,
        "winner_trainer_id": result.winner_trainer_id,
        "total_turns": result.total_turns,
        "is_draw": result.is_draw,
    }

    turns = [
        {
            "turn_number": e.turn,
            "fk_trainer_id": e.trainer_id,
            "fk_pokemon_id": e.pokemon_id,
            "action_type": e.action,
            "fk_move_id": e.move_id,
            "is_critical": e.is_critical,
            "hit": e.hit,
            "damage_dealt": e.damage,
            "fk_target_trainer_id": e.target_trainer_id,
            "fk_target_pokemon_id": e.target_pokemon_id,
            "target_hp_before": e.target_hp_before,
            "target_hp_after": e.target_hp_after,
            "target_fainted": e.target_fainted,
        }
        for e in result.turn_events
    ]

    decisions = []
    for d in result.decision_events:
        moves = d.moves + [{"id": None, "pp": None}] * (4 - len(d.moves))
        decisions.append({
            "turn_number": d.turn,
            "fk_trainer_id": d.trainer_id,
            "fk_active_pokemon_id": d.active_pokemon_id,
            "active_hp": d.active_hp,
            "active_status": d.active_status,
            "atk_stage": d.atk_stage,
            "def_stage": d.def_stage,
            "spe_stage": d.spe_stage,
            "spc_stage": d.spc_stage,
            "fk_opp_pokemon_id": d.opp_pokemon_id,
            "opp_hp": d.opp_hp,
            "opp_status": d.opp_status,
            "opp_atk_stage": d.opp_atk_stage,
            "opp_def_stage": d.opp_def_stage,
            "opp_spe_stage": d.opp_spe_stage,
            "opp_spc_stage": d.opp_spc_stage,
            "active_reflect_turns": d.active_reflect_turns,
            "active_light_screen_turns": d.active_light_screen_turns,
            "opp_reflect_turns": d.opp_reflect_turns,
            "opp_light_screen_turns": d.opp_light_screen_turns,
            "active_substitute_hp": d.active_substitute_hp,
            "opp_substitute_hp": d.opp_substitute_hp,
            "active_is_seeded": d.active_is_seeded,
            "opp_is_seeded": d.opp_is_seeded,
            "active_toxic_counter": d.active_toxic_counter,
            "opp_toxic_counter": d.opp_toxic_counter,
            "active_pokemon_remaining": d.active_pokemon_remaining,
            "opp_pokemon_remaining": d.opp_pokemon_remaining,
            "active_bench_pokemon_ids": d.active_bench_pokemon_ids,
            "opp_bench_pokemon_ids": d.opp_bench_pokemon_ids,
            "move1_id": moves[0]["id"],
            "move1_pp": moves[0]["pp"],
            "move2_id": moves[1]["id"],
            "move2_pp": moves[1]["pp"],
            "move3_id": moves[2]["id"],
            "move3_pp": moves[2]["pp"],
            "move4_id": moves[3]["id"],
            "move4_pp": moves[3]["pp"],
            "chosen_action": d.chosen_action,
            "chosen_move_id": d.chosen_move_id,
        })

    return {
        "meta": meta,
        "snapshots": result.team_snapshots,
        "turns": turns,
        "decisions": decisions,
    }


def append_to_jsonl(record: dict, jsonl_path: str):
    """Append one battle record as a single line to the JSONL file."""
    os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def flush_records_to_db(records: List[dict]):
    """Bulk-insert a list of battle records into Postgres."""
    with get_connection() as conn:
        for rec in records:
            _insert_record(conn, rec)


def _insert_record(conn, rec: dict):
    with get_cursor(conn) as cur:
        # 1. Insert battle meta, get generated id
        cur.execute("""
            INSERT INTO sim_battles
                (fk_trainer1_id, fk_trainer2_id, logic_profile_1, logic_profile_2,
                 seed, winner_trainer_id, total_turns, is_draw)
            VALUES
                (%(fk_trainer1_id)s, %(fk_trainer2_id)s, %(logic_profile_1)s, %(logic_profile_2)s,
                 %(seed)s, %(winner_trainer_id)s, %(total_turns)s, %(is_draw)s)
            RETURNING id
        """, rec["meta"])
        battle_id = cur.fetchone()["id"]

        # 2. Team snapshots
        for snap in rec["snapshots"]:
            snap["fk_battle_id"] = battle_id
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO sim_battle_team_snapshots
                (fk_battle_id, fk_trainer_id, fk_pokemon_id, party_order, level,
                 hp, attack, defense, special, speed,
                 fk_move1_id, fk_move2_id, fk_move3_id, fk_move4_id)
            VALUES
                (%(fk_battle_id)s, %(trainer_id)s, %(pokemon_id)s, %(party_order)s, %(level)s,
                 %(hp)s, %(attack)s, %(defense)s, %(special)s, %(speed)s,
                 %(move1_id)s, %(move2_id)s, %(move3_id)s, %(move4_id)s)
        """, rec["snapshots"])

        # 3. Turn events
        for t in rec["turns"]:
            t["fk_battle_id"] = battle_id
        if rec["turns"]:
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO sim_battle_turns
                    (fk_battle_id, turn_number, fk_trainer_id, fk_pokemon_id,
                     action_type, fk_move_id, is_critical, hit, damage_dealt,
                     fk_target_pokemon_id, target_hp_before, target_hp_after, target_fainted)
                VALUES
                    (%(fk_battle_id)s, %(turn_number)s, %(fk_trainer_id)s, %(fk_pokemon_id)s,
                     %(action_type)s, %(fk_move_id)s, %(is_critical)s, %(hit)s, %(damage_dealt)s,
                     %(fk_target_pokemon_id)s, %(target_hp_before)s, %(target_hp_after)s, %(target_fainted)s)
            """, rec["turns"])

        # 4. Decision events
        for d in rec["decisions"]:
            d["fk_battle_id"] = battle_id
        if rec["decisions"]:
            psycopg2.extras.execute_batch(cur, """
                INSERT INTO sim_battle_decisions
                    (fk_battle_id, turn_number, fk_trainer_id,
                     fk_active_pokemon_id, active_hp, active_status,
                     atk_stage, def_stage, spe_stage, spc_stage,
                     fk_opp_pokemon_id, opp_hp, opp_status,
                     opp_atk_stage, opp_def_stage, opp_spe_stage, opp_spc_stage,
                     active_reflect_turns, active_light_screen_turns,
                     opp_reflect_turns, opp_light_screen_turns,
                     active_substitute_hp, opp_substitute_hp,
                     active_is_seeded, opp_is_seeded,
                     active_toxic_counter, opp_toxic_counter,
                     active_pokemon_remaining, opp_pokemon_remaining,
                     active_bench_pokemon_ids, opp_bench_pokemon_ids,
                     move1_id, move1_pp, move2_id, move2_pp,
                     move3_id, move3_pp, move4_id, move4_pp,
                     chosen_action, chosen_move_id)
                VALUES
                    (%(fk_battle_id)s, %(turn_number)s, %(fk_trainer_id)s,
                     %(fk_active_pokemon_id)s, %(active_hp)s, %(active_status)s,
                     %(atk_stage)s, %(def_stage)s, %(spe_stage)s, %(spc_stage)s,
                     %(fk_opp_pokemon_id)s, %(opp_hp)s, %(opp_status)s,
                     %(opp_atk_stage)s, %(opp_def_stage)s, %(opp_spe_stage)s, %(opp_spc_stage)s,
                     %(active_reflect_turns)s, %(active_light_screen_turns)s,
                     %(opp_reflect_turns)s, %(opp_light_screen_turns)s,
                     %(active_substitute_hp)s, %(opp_substitute_hp)s,
                     %(active_is_seeded)s, %(opp_is_seeded)s,
                     %(active_toxic_counter)s, %(opp_toxic_counter)s,
                     %(active_pokemon_remaining)s, %(opp_pokemon_remaining)s,
                     %(active_bench_pokemon_ids)s, %(opp_bench_pokemon_ids)s,
                     %(move1_id)s, %(move1_pp)s, %(move2_id)s, %(move2_pp)s,
                     %(move3_id)s, %(move3_pp)s, %(move4_id)s, %(move4_pp)s,
                     %(chosen_action)s, %(chosen_move_id)s)
            """, rec["decisions"])

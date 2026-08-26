"""
Converts battle results into DB-ready records and bulk-writes them to Postgres.

Records are kept in memory for the whole batch and flushed straight to
Postgres — no local file involved. A record is a dict with keys:
  "meta"       - sim_battles row
  "snapshots"  - list of sim_battle_team_snapshots rows
  "turns"      - list of sim_battle_turns rows
  "decisions"  - list of sim_battle_decisions rows
"""
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


def flush_records_to_db(records: List[dict], conn=None, mark_done=None):
    """
    Bulk-insert a batch of battle records into Postgres — one execute_values
    call per table for the WHOLE batch, not one per record, so a 500-battle
    flush is ~4 round trips instead of ~2000.

    conn: if given, the insert runs on this connection and the caller owns
    commit/rollback (main.py uses this to fold mark-done into the same
    transaction as the flush). If None, opens and commits its own connection
    — used by ingest.py for standalone replay.

    mark_done: optional zero-arg callable invoked with the cursor after the
    inserts succeed but before commit, e.g. to batch-update battles_to_sim
    in the same transaction. Only used when conn is passed in.
    """
    if not records:
        return
    if conn is not None:
        _flush_batch(conn, records, mark_done)
        return
    with get_connection() as c:
        _flush_batch(c, records, None)


def _flush_batch(conn, records: List[dict], mark_done):
    # page_size must cover the whole batch or execute_values silently splits
    # it into multiple round trips (default page_size is only 100).
    page_size = len(records) + 1

    with get_cursor(conn) as cur:
        # 1. Insert all battle metas in one statement, get all generated ids back.
        #    RETURNING on a multi-row VALUES insert preserves input row order,
        #    so zip(records, battle_ids) below lines up correctly.
        result_rows = psycopg2.extras.execute_values(cur, """
            INSERT INTO sim_battles
                (fk_trainer1_id, fk_trainer2_id, logic_profile_1, logic_profile_2,
                 seed, winner_trainer_id, total_turns, is_draw)
            VALUES %s
            RETURNING id
        """, [rec["meta"] for rec in records], template="""(
            %(fk_trainer1_id)s, %(fk_trainer2_id)s, %(logic_profile_1)s, %(logic_profile_2)s,
            %(seed)s, %(winner_trainer_id)s, %(total_turns)s, %(is_draw)s
        )""", page_size=page_size, fetch=True)
        battle_ids = [row["id"] for row in result_rows]

        all_snapshots, all_turns, all_decisions = [], [], []
        for rec, battle_id in zip(records, battle_ids):
            for snap in rec["snapshots"]:
                snap["fk_battle_id"] = battle_id
                all_snapshots.append(snap)
            for t in rec["turns"]:
                t["fk_battle_id"] = battle_id
                all_turns.append(t)
            for d in rec["decisions"]:
                d["fk_battle_id"] = battle_id
                all_decisions.append(d)

        # 2. Team snapshots — one statement for every snapshot row across the whole batch.
        if all_snapshots:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO sim_battle_team_snapshots
                    (fk_battle_id, fk_trainer_id, fk_pokemon_id, party_order, level,
                     hp, attack, defense, special, speed,
                     fk_move1_id, fk_move2_id, fk_move3_id, fk_move4_id)
                VALUES %s
            """, all_snapshots, template="""(
                %(fk_battle_id)s, %(trainer_id)s, %(pokemon_id)s, %(party_order)s, %(level)s,
                %(hp)s, %(attack)s, %(defense)s, %(special)s, %(speed)s,
                %(move1_id)s, %(move2_id)s, %(move3_id)s, %(move4_id)s
            )""", page_size=len(all_snapshots) + 1)

        # 3. Turn events — one statement for every turn event across the whole batch.
        if all_turns:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO sim_battle_turns
                    (fk_battle_id, turn_number, fk_trainer_id, fk_pokemon_id,
                     action_type, fk_move_id, is_critical, hit, damage_dealt,
                     fk_target_pokemon_id, target_hp_before, target_hp_after, target_fainted)
                VALUES %s
            """, all_turns, template="""(
                %(fk_battle_id)s, %(turn_number)s, %(fk_trainer_id)s, %(fk_pokemon_id)s,
                %(action_type)s, %(fk_move_id)s, %(is_critical)s, %(hit)s, %(damage_dealt)s,
                %(fk_target_pokemon_id)s, %(target_hp_before)s, %(target_hp_after)s, %(target_fainted)s
            )""", page_size=len(all_turns) + 1)

        # 4. Decision events — one statement for every decision event across the whole batch.
        if all_decisions:
            psycopg2.extras.execute_values(cur, """
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
                VALUES %s
            """, all_decisions, template="""(
                %(fk_battle_id)s, %(turn_number)s, %(fk_trainer_id)s,
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
                %(chosen_action)s, %(chosen_move_id)s
            )""", page_size=len(all_decisions) + 1)

        # 5. Mark-done, folded into the same transaction as the results —
        #    closes the gap where a battle could be 'done' before its rows exist.
        if mark_done is not None:
            mark_done(cur)

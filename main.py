"""
Distributed battle simulation orchestrator.

Usage:
    python main.py [--workers N] [--flush-every N] [--log-dir PATH]

Each worker process:
1. Claims the next pending battle from battles_to_sim using SELECT FOR UPDATE SKIP LOCKED.
2. Loads both trainers and their teams from Postgres.
3. Runs the battle simulation.
4. Appends the result to a local JSONL file.
5. When its local buffer reaches flush_every battles, bulk-inserts into Postgres.
6. Marks the battle as done in battles_to_sim.

Multiple instances of this script can run on different servers simultaneously —
the SKIP LOCKED claim is the concurrency-safe handoff mechanism.
"""
import argparse
import json
import multiprocessing
import os
import sys
import time
import traceback

import psycopg2

# Make output/ the import root when run as `python main.py`
sys.path.insert(0, os.path.dirname(__file__))

from db.connection import get_connection, open_connection
from logic import load_profile
from models.trainer import Trainer
from repository.trainer_repo import (claim_next_battle, claim_next_theoretical_battle, get_trainer,
                                     get_move_by_name, get_type_chart, mark_battle_done,
                                     mark_theoretical_battle_done, requeue_stale_battles,
                                     requeue_stale_theoretical_battles)
from battle.battle import Battle
from recorder.battle_recorder import result_to_record, append_to_jsonl, flush_records_to_db


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        return json.load(f)


def _worker(args: tuple):
    """
    Entry point for each worker process.
    Loops until the battle queue is empty, then exits.
    """
    worker_id, flush_every, log_dir, seed_override, max_turns = args
    config = _load_config()
    sim_cfg = config["simulation"]
    seed = seed_override if seed_override is not None else sim_cfg["seed"]

    os.makedirs(log_dir, exist_ok=True)
    jsonl_path = os.path.join(log_dir, f"worker_{worker_id}.jsonl")

    buffer = []
    battles_run = 0

    # One long-lived connection per worker instead of opening/closing per
    # operation — cuts connection churn (handshake + backend fork) way down.
    conn = open_connection()
    type_chart = get_type_chart(conn)  # static table, loaded once per worker
    conn.commit()

    def _move_loader(move_name: str):
        move = get_move_by_name(conn, move_name)
        conn.commit()
        return move

    try:
        while True:
            battle_row = None
            is_theoretical = False
            try:
                # Sweep stale battles on startup (only worker 0 does this)
                if worker_id == 0 and battles_run == 0:
                    requeue_stale_battles(conn)
                    requeue_stale_theoretical_battles(conn)
                    conn.commit()

                battle_row = claim_next_battle(conn)
                if battle_row is None:
                    battle_row = claim_next_theoretical_battle(conn)
                    is_theoretical = battle_row is not None
                conn.commit()

                if battle_row is None:
                    break  # Both queues empty — exit

                t1_profile = load_profile(battle_row["logic_profile_trainer1"] or "random")
                t2_profile = load_profile(battle_row["logic_profile_trainer2"] or "random")

                trainer1 = get_trainer(conn, battle_row["fk_trainer1_id"], t1_profile)
                trainer2 = get_trainer(conn, battle_row["fk_trainer2_id"], t2_profile)
                conn.commit()  # release the SELECT FOR UPDATE lock promptly

                battle = Battle(
                    battle_queue_id=battle_row["id"],
                    trainer1=trainer1,
                    trainer2=trainer2,
                    logic_profile_1=battle_row["logic_profile_trainer1"] or "random",
                    logic_profile_2=battle_row["logic_profile_trainer2"] or "random",
                    seed=seed + battle_row["id"],  # Unique seed per battle
                    max_turns=max_turns,
                    type_chart=type_chart,
                    move_loader=_move_loader,
                )
                result = battle.run()

                record = result_to_record(result)
                append_to_jsonl(record, jsonl_path)
                buffer.append(record)
                battles_run += 1

                if len(buffer) >= flush_every:
                    flush_records_to_db(buffer)
                    buffer.clear()
                    print(f"[worker {worker_id}] Flushed {flush_every} battles to DB.", flush=True)

                if is_theoretical:
                    mark_theoretical_battle_done(conn, battle_row["id"])
                else:
                    mark_battle_done(conn, battle_row["id"])
                conn.commit()

                print(f"[worker {worker_id}] Battle {battle_row['id']} done — "
                      f"winner: {result.winner_trainer_id}, turns: {result.total_turns}", flush=True)

            except psycopg2.OperationalError:
                print(f"[worker {worker_id}] Lost DB connection, reconnecting...", flush=True)
                try:
                    conn.close()
                except Exception:
                    pass
                conn = open_connection()
            except Exception:
                print(f"[worker {worker_id}] ERROR on battle {battle_row}: {traceback.format_exc()}", flush=True)
                conn.rollback()
                # Do not mark as done — it will be requeued by the stale sweeper
    finally:
        if buffer:
            flush_records_to_db(buffer)
            print(f"[worker {worker_id}] Final flush: {len(buffer)} battles.", flush=True)
        conn.close()

    print(f"[worker {worker_id}] Done. Ran {battles_run} battles.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Gen 1 Pokemon battle simulator")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of parallel worker processes (default: CPU count)")
    parser.add_argument("--flush-every", type=int, default=None,
                        help="Flush to DB after this many battles per worker")
    parser.add_argument("--log-dir", type=str, default=None,
                        help="Directory for JSONL output files")
    parser.add_argument("--seed", type=int, default=None,
                        help="Base random seed (overrides config)")
    parser.add_argument("--max-turns", type=int, default=None,
                        help="Maximum turns per battle (overrides config)")
    args = parser.parse_args()

    config = _load_config()
    sim_cfg = config["simulation"]

    n_workers = args.workers or sim_cfg.get("default_workers") or multiprocessing.cpu_count()
    flush_every = args.flush_every or sim_cfg.get("flush_every_n_battles", 50)
    log_dir = args.log_dir or config.get("output", {}).get("jsonl_dir", "battle_logs")
    seed = args.seed
    max_turns = args.max_turns or sim_cfg.get("max_turns", 200)

    print(f"Starting simulation: {n_workers} workers, flush every {flush_every}, max_turns={max_turns}")

    worker_args = [(i, flush_every, log_dir, seed, max_turns) for i in range(n_workers)]

    if n_workers == 1:
        _worker(worker_args[0])
    else:
        with multiprocessing.Pool(processes=n_workers) as pool:
            pool.map(_worker, worker_args)

    print("All workers finished.")


if __name__ == "__main__":
    main()

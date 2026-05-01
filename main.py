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

# Make output/ the import root when run as `python main.py`
sys.path.insert(0, os.path.dirname(__file__))

from db.connection import get_connection
from logic import load_profile
from models.trainer import Trainer
from repository.trainer_repo import (claim_next_battle, get_trainer, get_move_by_name,
                                     mark_battle_done, requeue_stale_battles)
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

    while True:
        battle_row = None
        try:
            with get_connection() as conn:
                # Sweep stale battles on startup (only worker 0 does this)
                if worker_id == 0 and battles_run == 0:
                    requeue_stale_battles(conn)

                battle_row = claim_next_battle(conn)
                if battle_row is None:
                    break  # Queue empty — exit

                t1_profile = load_profile(battle_row["logic_profile_trainer1"] or "random")
                t2_profile = load_profile(battle_row["logic_profile_trainer2"] or "random")

                # Load type chart once; it never changes
                from repository.trainer_repo import get_type_chart
                type_chart = get_type_chart(conn)

                trainer1 = get_trainer(conn, battle_row["fk_trainer1_id"], t1_profile)
                trainer2 = get_trainer(conn, battle_row["fk_trainer2_id"], t2_profile)

            def _move_loader(move_name: str):
                with get_connection() as c:
                    return get_move_by_name(c, move_name)

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

            with get_connection() as conn:
                mark_battle_done(conn, battle_row["id"])

            print(f"[worker {worker_id}] Battle {battle_row['id']} done — "
                  f"winner: {result.winner_trainer_id}, turns: {result.total_turns}", flush=True)

        except Exception:
            print(f"[worker {worker_id}] ERROR on battle {battle_row}: {traceback.format_exc()}", flush=True)
            # Do not mark as done — it will be requeued by the stale sweeper

    # Flush remaining buffer on exit
    if buffer:
        flush_records_to_db(buffer)
        print(f"[worker {worker_id}] Final flush: {len(buffer)} battles.", flush=True)

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

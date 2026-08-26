"""
Distributed battle simulation orchestrator.

Usage (run from output/):
    python scripts/main.py [--workers N] [--flush-every N]

Each worker process:
1. Claims a batch of pending battles from battles_to_sim using SELECT FOR UPDATE SKIP LOCKED.
2. Loads both trainers and their teams from an in-memory reference cache.
3. Runs the battle simulations, keeping results in memory.
4. Bulk-inserts the whole batch into Postgres and marks it done, in one transaction.

Multiple instances of this script can run on different servers simultaneously —
the SKIP LOCKED claim is the concurrency-safe handoff mechanism.
"""
import argparse
import json
import multiprocessing
import os
import random
import sys
import time
import traceback

import psycopg2

# Make output/ the import root when run as `python scripts/main.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import get_connection, open_connection
from logic import load_profile
from models.trainer import Trainer
from repository.trainer_repo import (claim_battle_batch, claim_theoretical_battle_batch,
                                     load_reference_cache, get_trainer_cached, get_cached_move_for_name,
                                     get_type_chart, requeue_stale_battles,
                                     requeue_stale_theoretical_battles)
from battle.battle import Battle
from recorder.battle_recorder import result_to_record, flush_records_to_db


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    with open(config_path) as f:
        return json.load(f)


def _worker(args: tuple):
    """
    Entry point for each worker process.
    Loops until the battle queue is empty, then exits.

    Each iteration claims a whole BATCH of battles in one round trip, runs
    them all against an in-memory reference cache (no DB access mid-batch),
    then flushes the results and marks the batch done in one transaction —
    a handful of round trips per batch instead of ~16 per battle.
    """
    worker_id, batch_size, seed_override, max_turns = args
    config = _load_config()
    sim_cfg = config["simulation"]
    seed = seed_override if seed_override is not None else sim_cfg["seed"]

    battles_run = 0

    # One long-lived connection per worker instead of opening/closing per
    # operation — cuts connection churn (handshake + backend fork) way down.
    conn = open_connection()
    type_chart = get_type_chart(conn)  # static table, loaded once per worker
    cache = load_reference_cache(conn)  # all trainers/teams/moves, loaded once per worker
    conn.commit()

    def _move_loader(move_name: str):
        return get_cached_move_for_name(cache, move_name)

    # Stagger workers so they don't finish batches (and flush to Postgres)
    # in lockstep — a fixed per-worker offset plus a little randomness so
    # the offsets don't stay perfectly aligned cycle after cycle.
    time.sleep(worker_id * 0.5 + random.uniform(0, 0.5))

    try:
        while True:
            battles = []
            is_theoretical = False
            try:
                # Sweep stale battles on startup (only worker 0 does this)
                if worker_id == 0 and battles_run == 0:
                    requeue_stale_battles(conn)
                    requeue_stale_theoretical_battles(conn)
                    conn.commit()

                # Jitter the claim size a bit each cycle so workers keep
                # drifting apart instead of resyncing to the same cadence.
                claim_size = max(1, int(batch_size * random.uniform(0.8, 1.2)))

                battles = claim_battle_batch(conn, claim_size)
                if not battles:
                    battles = claim_theoretical_battle_batch(conn, claim_size)
                    is_theoretical = True
                conn.commit()  # release the SELECT FOR UPDATE locks promptly

                if not battles:
                    break  # Both queues empty — exit

                records = []
                done_ids = []
                for battle_row in battles:
                    t1_profile = load_profile(battle_row["logic_profile_trainer1"] or "random")
                    t2_profile = load_profile(battle_row["logic_profile_trainer2"] or "random")

                    trainer1 = get_trainer_cached(cache, battle_row["fk_trainer1_id"], t1_profile)
                    trainer2 = get_trainer_cached(cache, battle_row["fk_trainer2_id"], t2_profile)

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
                    records.append(record)
                    done_ids.append(battle_row["id"])
                    battles_run += 1

                    print(f"[worker {worker_id}] Battle {battle_row['id']} done — "
                          f"winner: {result.winner_trainer_id}, turns: {result.total_turns}", flush=True)

                table = "theoretical_battles_to_sim" if is_theoretical else "battles_to_sim"
                id_col = "pk_theoretical_battles_to_sim_id" if is_theoretical else "pk_battles_to_sim_id"

                def _mark_done(cur, ids=done_ids, table=table, id_col=id_col):
                    cur.execute(f"UPDATE {table} SET status = 'done' WHERE {id_col} = ANY(%s)", (ids,))

                # Results + mark-done commit together — a battle can never end up
                # marked 'done' without its rows durably in Postgres.
                flush_records_to_db(records, conn=conn, mark_done=_mark_done)
                conn.commit()

                print(f"[worker {worker_id}] Flushed batch of {len(records)} battles to DB.", flush=True)

            except psycopg2.OperationalError:
                print(f"[worker {worker_id}] Lost DB connection, reconnecting...", flush=True)
                try:
                    conn.close()
                except Exception:
                    pass
                conn = open_connection()
            except Exception:
                print(f"[worker {worker_id}] ERROR on batch {[b['id'] for b in battles]}: "
                      f"{traceback.format_exc()}", flush=True)
                conn.rollback()
                # Do not mark as done — battles will be requeued by the stale sweeper
    finally:
        conn.close()

    print(f"[worker {worker_id}] Done. Ran {battles_run} battles.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Gen 1 Pokemon battle simulator")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of parallel worker processes (default: CPU count)")
    parser.add_argument("--flush-every", type=int, default=None,
                        help="Battles claimed/simulated/flushed together per round trip")
    parser.add_argument("--seed", type=int, default=None,
                        help="Base random seed (overrides config)")
    parser.add_argument("--max-turns", type=int, default=None,
                        help="Maximum turns per battle (overrides config)")
    args = parser.parse_args()

    config = _load_config()
    sim_cfg = config["simulation"]

    n_workers = args.workers or sim_cfg.get("default_workers") or multiprocessing.cpu_count()
    flush_every = args.flush_every or sim_cfg.get("flush_every_n_battles", 50)
    seed = args.seed
    max_turns = args.max_turns or sim_cfg.get("max_turns", 200)

    print(f"Starting simulation: {n_workers} workers, flush every {flush_every}, max_turns={max_turns}")

    worker_args = [(i, flush_every, seed, max_turns) for i in range(n_workers)]

    if n_workers == 1:
        _worker(worker_args[0])
    else:
        with multiprocessing.Pool(processes=n_workers) as pool:
            pool.map(_worker, worker_args)

    print("All workers finished.")


if __name__ == "__main__":
    main()

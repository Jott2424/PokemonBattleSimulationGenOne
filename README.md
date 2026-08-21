# PokemonBattleSimulationGenOne

A Generation 1 Pokémon (Red/Blue/Yellow) battle simulator that runs thousands of battles between real in-game trainers, records every decision and state change turn-by-turn, and persists the results to Postgres — generating training data for two downstream ML models: a **win-probability predictor** (given two teams, who wins) and a **real-time decision model** (given the current battle state, what's the best move).

Trainer behavior during simulated battles is controlled by pluggable **logic profiles** of increasing sophistication (e.g. pure random, never-swap, type-effectiveness-aware), so battles can be run under different "AI" assumptions and compared.

## How it fits together

```
rawdata/*.csv  ──[LoadRawData.py]──>  bronze schema (trainers, pokemon, moves, ...)
                                             │
                                    [setup_silver.py applies schema_silver.sql]
                                             ▼
                        silver.battles_to_sim  (queue of trainer1 vs trainer2 matchups)
                                             │
                                    [main.py workers claim rows]
                                             ▼
                              battle/battle.py runs the simulation
                                             │
                          ┌──────────────────┴──────────────────┐
                          ▼                                     ▼
              output/battle_logs/*.jsonl              silver.sim_battles /
              (local, durable buffer)                 silver.sim_battle_decisions
                                                        (final destination)
```

- **bronze schema** — raw game data (trainers, teams, Pokémon, moves, type chart) loaded verbatim from `rawdata/`.
- **silver schema** — simulation queue and results. `battles_to_sim` is a work queue (`pending` → `running` → `done`) that worker processes claim from using `SELECT ... FOR UPDATE SKIP LOCKED`, so multiple `main.py` processes (even on different machines, pointed at the same DB) can run concurrently without double-processing a battle. `sim_battles` holds one row per completed battle; `sim_battle_decisions` holds one row per trainer-per-turn, capturing the full state (HP, status, stat stages, screens, substitute, seeded, toxic counter, bench) each trainer saw when they made their decision.
- Each worker buffers finished battles in memory, appends them to a local JSONL file as a durable log, and periodically bulk-inserts the buffer into Postgres. If a worker dies mid-run, `ingest.py` can replay its JSONL file back into the DB without re-simulating anything.

## Setup

1. Clone the repo and install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Deploy a Postgres instance and create an empty database (owner `postgres`, or update the config below to match your setup).
3. Copy the config template and fill in your real connection details:
   ```
   cp config.example.json config.json
   ```
   `config.json` is gitignored — it holds live DB credentials and is never committed.
4. Load the raw Gen 1 data (games, trainers, Pokémon, moves, type chart, ...) from `rawdata/`:
   ```
   python LoadRawData.py
   ```
5. Create the simulation (silver) schema:
   ```
   python setup_silver.py
   ```

## Running simulations

Queue battles into `silver.battles_to_sim`, then let workers drain the queue.

**Queue a small test batch** (10 random matchups) — useful to sanity-check the pipeline end-to-end:
```
psql -f populate_test_battles.sql <connection args>
```

**Queue the full cross join** — every trainer pair × every combination of the 3 logic profiles, in batches (`insert_battle_limit` in `config.json` caps how many rows are inserted per run so you can control pace):
```
python populate_battles.py
```

**Run the workers:**
```
python main.py [--workers N] [--flush-every N] [--log-dir PATH] [--seed N] [--max-turns N]
```
Each worker claims one battle at a time from the queue, simulates it, appends the result to `<log-dir>/worker_<id>.jsonl`, and bulk-flushes to Postgres every `--flush-every` battles (and once more on exit for anything left in its buffer). Defaults for all flags come from `config.json`. Workers that lose their DB connection reconnect automatically; battles left `running` past a timeout are swept back to `pending` by worker 0 on the next startup.

**Recover a JSONL file into the DB** (e.g. after a crash, or to merge logs from multiple machines):
```
python ingest.py output/battle_logs/*.jsonl
```

**Inspect a single battle turn-by-turn:**
```
python replay.py <battle_id>
```

## Logic profiles

Trainer decision-making is pluggable. Built-in profiles (`logic/`):

| Profile | Behavior |
|---|---|
| `random` | All decisions (attack vs. swap, which move, which swap target) are uniformly random. |
| `no_swap` | Never voluntarily swaps; picks a random usable move each turn. Still forced to swap when the active Pokémon faints. |
| `type_aware` | Never voluntarily swaps; picks whichever usable move has the best type-effectiveness multiplier against the opponent's active Pokémon (ties broken randomly). |

To add a new profile, drop a module in `logic/` that subclasses `BaseProfile` (`logic/base_profile.py`) and exposes a module-level `profile` instance — `logic/__init__.py` loads profiles dynamically by filename, so no registration step is needed elsewhere.

## Theoretical trainers

Beyond the ~1000+ real in-game trainers, you can simulate battles for synthetic teams that never existed in-game — useful for "what if" experiments (e.g. an all-Dragon team). These are kept in separate tables (`theoretical_trainers`, `theoretical_trainers_teams`, `theoretical_battles_to_sim`) so they never collide with real trainer IDs (theoretical IDs start at 20000) or pollute the real battle history.

**Create a theoretical trainer:**
```
python build_theoretical_trainer.py --label "All-Dragon Experiment" --team team.json
```
where `team.json` is a list of 1-6 slots: `{"pokemon_id": 149, "level": 55, "move_ids": [82, 91, 34, 44]}` (party order follows list order).

**Queue battles for it** against every real trainer or every other theoretical trainer:
```
python populate_theoretical_battles.py --trainer-id 20000 --against real
python populate_theoretical_battles.py --trainer-id 20000 --against theoretical
```
`main.py` workers drain this queue the same way as the real one (checking it only once the real queue is empty), and results land in the same `sim_battles` / `sim_battle_decisions` tables.

## Project structure

```
rawdata/                CSVs — the raw Gen 1 data (games, trainers, Pokémon, moves, type chart, ...)
LoadRawData.py           Loads rawdata/ CSVs into the bronze schema
schema_silver.sql        DDL for the simulation queue + results tables
setup_silver.py          Applies schema_silver.sql

battle/battle.py         Core battle engine — turn order, move resolution, status/volatile effects
mechanics/                Damage calc, stat-stage modifiers, status conditions, move effect dispatch
models/                  Pokemon / Move / Trainer dataclasses
logic/                   Pluggable trainer decision-making profiles
data/                    Move effect metadata lookup

db/                      Postgres connection helpers
repository/              Query layer — loading trainers/teams/moves, claiming/marking battle queue rows
recorder/                Converts battle results to DB/JSONL records and writes them

main.py                  Multi-worker orchestrator — claims queue rows and runs battles
populate_battles.py       Queues the full real-trainer cross join
populate_test_battles.sql Queues a small random test batch
populate_theoretical_battles.py  Queues battles for a theoretical trainer
build_theoretical_trainer.py     Creates a synthetic trainer/team
ingest.py                 Replays a JSONL log file into the DB
replay.py                 Prints a turn-by-turn log for one battle

config.example.json      Config template — copy to config.json and fill in real values
```

## Notes

- `sim_battle_decisions` gained a batch of opponent-state columns (opponent stat stages, screens, substitute HP, seeded/toxic status, bench, remaining Pokémon count) partway through this project. Battles simulated before that change have `NULL` in those columns — the raw state wasn't captured anywhere at the time, so it can't be backfilled without re-simulating those battles.

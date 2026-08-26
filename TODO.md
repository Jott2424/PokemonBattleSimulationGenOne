# TODO

## Known bugs (unfixed)

- **Metronome/Mirror Move silently fail on multi-word moves.**
  `repository/trainer_repo.py`'s `get_move_by_name()` and
  `get_cached_move_for_name()` both do `move_name.replace("-", "_")` before
  looking the name up against `bronze.moves`, on the assumption the DB
  stores underscores — it actually stores hyphens (`acid-armor`, not
  `acid_armor`). Confirmed *actively* broken against the current v3 sim
  data: of 2,872 Metronome dispatches, only 29.4% produced a follow-up
  attack event, matching the "bug active" prediction (29.1%) almost
  exactly against the bug-free expectation (66.2%). Net effect: whenever
  Metronome/Mirror Move selects a multi-word damaging move (~56% of the
  time it selects a damaging move at all), the turn is spent with zero
  effect — no damage, no miss, no event.
  Fix: drop the `.replace("-", "_")` in both functions.
  Impact on the v3 model: judged negligible — Metronome/Mirror Move only
  sit on 85,200 of a much larger pool of move slots, so this shouldn't be
  blocking a resim on its own, but worth fixing before the next one.

## Security / hardening

- **Default Postgres credentials.** `config.json`'s `database.password` is
  still `postgres` (the default). Not committed to git (gitignored), but
  worth rotating to a real credential regardless — a default password is a
  soft target the moment that VM is reachable beyond the LAN.

## Planned features

- **Fully separate theoretical/random-trainer battle results from real ones.**
  Currently, only the *pre-simulation* side is separated:
  `theoretical_trainers`/`theoretical_trainers_teams` (vs. `bronze.trainers`/
  `trainers_teams`) and the `theoretical_battles_to_sim` queue (vs.
  `battles_to_sim`) already exist as their own tables. But once
  `scripts/main.py` actually simulates a theoretical battle, the *results*
  land in the exact same shared tables as real battles —
  `sim_battles`, `sim_battle_team_snapshots`, `sim_battle_turns`,
  `sim_battle_decisions` — with nothing but the trainer id range
  (`>= THEORETICAL_ID_OFFSET`, currently 20000) to tell them apart later.
  Goal, per conversation 2026-08-26:
    - Create theoretical/random trainers (via `build_theoretical_trainer.py`
      and/or `generate_random_team.py --insert`) as today — already isolated.
    - Populate battles for every theoretical/random trainer against every
      real trainer (`populate_theoretical_battles.py --against real`) —
      already queues into the separate `theoretical_battles_to_sim` table.
    - **Simulate those with a separate script** (not `scripts/main.py`
      itself — a similar but distinct script) that claims only from
      `theoretical_battles_to_sim` and writes results into **new,
      theoretical-only result tables** (e.g. `theoretical_sim_battles`,
      `theoretical_sim_battle_team_snapshots`, `theoretical_sim_battle_turns`,
      `theoretical_sim_battle_decisions`), mirroring the real schema so
      existing analysis/query patterns still apply.
  Explicitly decided: theoretical-vs-real battles stay supported (that's the
  whole point of populating against real trainers), so
  `theoretical_battles_to_sim.fk_trainers_id_one/two` still needs to hold
  either kind of id with no FK constraint, same as today — the
  `THEORETICAL_ID_OFFSET` disambiguation scheme is **not** being removed,
  just the shared *result* tables are being split off.
  Touches: a new `schema_theoretical.sql` (or an addition to
  `schema_silver.sql`) for the new tables, a new simulation script parallel
  to `scripts/main.py`, and `recorder/battle_recorder.py`'s
  `flush_records_to_db()`/`_flush_batch()` (currently hardcoded to the real
  table names) needing a theoretical-table-targeting counterpart.

## Housekeeping

- **`scripts/generate_random_team.py` is uncommitted.** Written and
  validated against the live DB (STAB/stat-mod/random move selection,
  Dragon-type STAB-shortfall fallback, no duplicate species/moves, levels
  within one tranche) but never `git add`ed/committed.
- **`sql/archive_simulation_data.sql` doesn't cover
  `theoretical_battles_to_sim`.** Its archive list only moves
  `sim_battle_team_snapshots`, `sim_battle_turns`, `sim_battle_decisions`,
  `sim_battles`, and `battles_to_sim` into the `archive` schema. If
  theoretical battles are in active use during a future resim cycle, that
  queue table won't get archived/reset alongside everything else and will
  need handling by hand (as happened this time, since a full wipe was used
  instead of the archive script).

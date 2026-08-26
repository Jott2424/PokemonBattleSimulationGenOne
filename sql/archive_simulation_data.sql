-- =============================================================================
-- Archives the existing simulation queue + results, leaving silver.* empty
-- for a fresh start.
--
-- ALTER TABLE ... SET SCHEMA is metadata-only in Postgres — it does not copy
-- or rewrite any data, so this is fast regardless of table size and does not
-- duplicate storage. Nothing is deleted.
--
-- After running this, re-run setup_silver.py (schema_silver.sql uses
-- CREATE TABLE IF NOT EXISTS) to recreate fresh, empty versions of these
-- same tables — with their indexes rebuilt clean — back in silver.
--
-- To reverse (move the archived data back instead of recreating fresh
-- tables), run the mirror image of this script with silver/archive swapped:
--   ALTER TABLE archive.sim_battle_team_snapshots SET SCHEMA silver;
--   ALTER TABLE archive.sim_battle_turns SET SCHEMA silver;
--   ALTER TABLE archive.sim_battle_decisions SET SCHEMA silver;
--   ALTER TABLE archive.sim_battles SET SCHEMA silver;
--   ALTER TABLE archive.battles_to_sim SET SCHEMA silver;
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS archive;

-- Children first (no FK-related requirement to do so — schema moves don't
-- care about foreign keys — just more readable dependency order).
ALTER TABLE silver.sim_battle_team_snapshots SET SCHEMA archive;
ALTER TABLE silver.sim_battle_turns SET SCHEMA archive;
ALTER TABLE silver.sim_battle_decisions SET SCHEMA archive;
ALTER TABLE silver.sim_battles SET SCHEMA archive;
ALTER TABLE silver.battles_to_sim SET SCHEMA archive;

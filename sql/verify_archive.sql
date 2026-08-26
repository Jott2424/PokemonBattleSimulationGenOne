-- Quick sanity check after running archive_simulation_data.sql and
-- re-running setup_silver.py: confirms silver.* is empty and archive.*
-- still has everything.

SELECT 'silver.battles_to_sim' AS table_name, count(*) FROM silver.battles_to_sim
UNION ALL
SELECT 'silver.sim_battles', count(*) FROM silver.sim_battles
UNION ALL
SELECT 'silver.sim_battle_team_snapshots', count(*) FROM silver.sim_battle_team_snapshots
UNION ALL
SELECT 'silver.sim_battle_turns', count(*) FROM silver.sim_battle_turns
UNION ALL
SELECT 'silver.sim_battle_decisions', count(*) FROM silver.sim_battle_decisions
UNION ALL
SELECT 'archive.battles_to_sim', count(*) FROM archive.battles_to_sim
UNION ALL
SELECT 'archive.sim_battles', count(*) FROM archive.sim_battles
UNION ALL
SELECT 'archive.sim_battle_team_snapshots', count(*) FROM archive.sim_battle_team_snapshots
UNION ALL
SELECT 'archive.sim_battle_turns', count(*) FROM archive.sim_battle_turns
UNION ALL
SELECT 'archive.sim_battle_decisions', count(*) FROM archive.sim_battle_decisions;

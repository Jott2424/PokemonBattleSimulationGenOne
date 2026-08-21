-- Preview row count before inserting
SELECT
    (SELECT COUNT(*) FROM bronze.trainers WHERE fk_games_id IN (2, 3)) AS trainer_count,
    (SELECT COUNT(*) FROM bronze.trainers WHERE fk_games_id IN (2, 3)) *
    ((SELECT COUNT(*) FROM bronze.trainers WHERE fk_games_id IN (2, 3)) - 1) / 2 AS unique_pairs,
    (SELECT COUNT(*) FROM bronze.trainers WHERE fk_games_id IN (2, 3)) *
    ((SELECT COUNT(*) FROM bronze.trainers WHERE fk_games_id IN (2, 3)) - 1) / 2 * 9 AS total_rows;

-- Insert all unique pairs x all logic profile combinations
-- Skips any trainer pair + profile combo already in the table
-- Change the LIMIT value to control how many rows to insert at once
INSERT INTO silver.battles_to_sim
    (fk_trainers_id_one, fk_trainers_id_two, logic_profile_trainer1, logic_profile_trainer2, status)
SELECT
    t1.pk_trainers_id,
    t2.pk_trainers_id,
    p.profile1,
    p.profile2,
    'pending'
FROM bronze.trainers t1
JOIN bronze.trainers t2
    ON t2.pk_trainers_id > t1.pk_trainers_id
    AND t2.fk_games_id IN (2, 3)
CROSS JOIN (VALUES
    ('random',     'random'),
    ('random',     'no_swap'),
    ('random',     'type_aware'),
    ('no_swap',    'random'),
    ('no_swap',    'no_swap'),
    ('no_swap',    'type_aware'),
    ('type_aware', 'random'),
    ('type_aware', 'no_swap'),
    ('type_aware', 'type_aware')
) AS p(profile1, profile2)
WHERE t1.fk_games_id IN (2, 3)
  AND NOT EXISTS (
      SELECT 1 FROM silver.battles_to_sim x
      WHERE x.fk_trainers_id_one = t1.pk_trainers_id
        AND x.fk_trainers_id_two = t2.pk_trainers_id
        AND x.logic_profile_trainer1 = p.profile1
        AND x.logic_profile_trainer2 = p.profile2
  )
LIMIT 50;

SELECT COUNT(*) AS rows_inserted FROM silver.battles_to_sim WHERE status = 'pending';

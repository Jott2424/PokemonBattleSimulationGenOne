-- Selects 20 random trainers who have teams, pairs them into 10 matchups,
-- and inserts into silver.battles_to_sim with status = 'pending'.

WITH random_trainers AS (
    SELECT fk_trainers_id AS trainer_id
    FROM bronze.trainers_teams
    GROUP BY fk_trainers_id
    ORDER BY random()
    LIMIT 20
),
numbered AS (
    SELECT trainer_id, ROW_NUMBER() OVER () AS rn
    FROM random_trainers
),
matchups AS (
    SELECT
        a.trainer_id AS trainer1_id,
        b.trainer_id AS trainer2_id
    FROM numbered a
    JOIN numbered b ON b.rn = a.rn + 10
    WHERE a.rn <= 10
)
INSERT INTO silver.battles_to_sim (
    fk_trainers_id_one,
    fk_trainers_id_two,
    logic_profile_trainer1,
    logic_profile_trainer2,
    status
)
SELECT
    trainer1_id,
    trainer2_id,
    'random',
    'random',
    'pending'
FROM matchups;

-- Confirm what was inserted
SELECT
    b.pk_battles_to_sim_id,
    t1.long_name AS trainer_1,
    t2.long_name AS trainer_2,
    b.logic_profile_trainer1,
    b.logic_profile_trainer2,
    b.status
FROM silver.battles_to_sim b
JOIN bronze.trainers t1 ON t1.pk_trainers_id = b.fk_trainers_id_one
JOIN bronze.trainers t2 ON t2.pk_trainers_id = b.fk_trainers_id_two
WHERE b.status = 'pending'
ORDER BY b.pk_battles_to_sim_id;

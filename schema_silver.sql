-- =============================================================================
-- Silver-layer tables for battle simulation results.
-- Run this once against pokemon_battlesim_g1 before starting simulations.
-- =============================================================================

-- -----------------------------------------------------------------------
-- Extend battles_to_sim with distributed-safe columns
-- (Only adds columns — does not drop or alter existing ones.)
-- -----------------------------------------------------------------------
ALTER TABLE battles_to_sim
    ADD COLUMN IF NOT EXISTS status              VARCHAR(10)  DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS claimed_at          TIMESTAMP,
    ADD COLUMN IF NOT EXISTS logic_profile_trainer1 VARCHAR(50),
    ADD COLUMN IF NOT EXISTS logic_profile_trainer2 VARCHAR(50);

-- Index to make the SKIP LOCKED queue claim fast
CREATE INDEX IF NOT EXISTS idx_battles_to_sim_status
    ON battles_to_sim (status)
    WHERE status = 'pending';

-- -----------------------------------------------------------------------
-- sim_battles — one row per completed simulation
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sim_battles (
    id                  SERIAL       PRIMARY KEY,
    fk_trainer1_id      INT          NOT NULL,
    fk_trainer2_id      INT          NOT NULL,
    logic_profile_1     VARCHAR(50),
    logic_profile_2     VARCHAR(50),
    seed                INT          NOT NULL,
    winner_trainer_id   INT,                    -- NULL = draw
    total_turns         SMALLINT     NOT NULL,
    is_draw             BOOLEAN      NOT NULL    DEFAULT FALSE,
    run_at              TIMESTAMP    NOT NULL    DEFAULT NOW()
);

-- -----------------------------------------------------------------------
-- sim_battle_team_snapshots — full team state at battle start
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sim_battle_team_snapshots (
    fk_battle_id    INT          NOT NULL REFERENCES sim_battles(id),
    fk_trainer_id   INT          NOT NULL,
    fk_pokemon_id   INT          NOT NULL,
    party_order     SMALLINT     NOT NULL,
    level           SMALLINT     NOT NULL,
    hp              SMALLINT     NOT NULL,
    attack          SMALLINT     NOT NULL,
    defense         SMALLINT     NOT NULL,
    special         SMALLINT     NOT NULL,
    speed           SMALLINT     NOT NULL,
    fk_move1_id     INT,
    fk_move2_id     INT,
    fk_move3_id     INT,
    fk_move4_id     INT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_battle_id ON sim_battle_team_snapshots (fk_battle_id);

-- -----------------------------------------------------------------------
-- sim_battle_turns — turn-by-turn action log
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sim_battle_turns (
    fk_battle_id            INT          NOT NULL REFERENCES sim_battles(id),
    turn_number             SMALLINT     NOT NULL,
    fk_trainer_id           INT          NOT NULL,
    fk_pokemon_id           INT          NOT NULL,
    action_type             VARCHAR(20)  NOT NULL,   -- attack | swap | forced_swap | struggle | skipped | confusion_self_hit | substitute_break
    fk_move_id              INT,
    is_critical             BOOLEAN,
    hit                     BOOLEAN,
    damage_dealt            SMALLINT,
    fk_target_pokemon_id    INT,
    target_hp_before        SMALLINT,
    target_hp_after         SMALLINT,
    target_fainted          BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_turns_battle_id ON sim_battle_turns (fk_battle_id);

-- -----------------------------------------------------------------------
-- sim_battle_decisions — decision context for real-time ML model training
-- One row per decision point (each trainer, each turn)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sim_battle_decisions (
    fk_battle_id            INT          NOT NULL REFERENCES sim_battles(id),
    turn_number             SMALLINT     NOT NULL,
    fk_trainer_id           INT          NOT NULL,

    -- State of the active Pokemon at decision time
    fk_active_pokemon_id    INT          NOT NULL,
    active_hp               SMALLINT     NOT NULL,
    active_status           VARCHAR(30),
    atk_stage               SMALLINT     NOT NULL,
    def_stage               SMALLINT     NOT NULL,
    spe_stage               SMALLINT     NOT NULL,
    spc_stage               SMALLINT     NOT NULL,

    -- State of the opponent's active Pokemon
    fk_opp_pokemon_id       INT          NOT NULL,
    opp_hp                  SMALLINT     NOT NULL,
    opp_status              VARCHAR(30),

    -- Available moves and remaining PP
    move1_id                INT,
    move1_pp                SMALLINT,
    move2_id                INT,
    move2_pp                SMALLINT,
    move3_id                INT,
    move3_pp                SMALLINT,
    move4_id                INT,
    move4_pp                SMALLINT,

    -- What the trainer actually chose
    chosen_action           VARCHAR(20)  NOT NULL,
    chosen_move_id          INT
);

CREATE INDEX IF NOT EXISTS idx_decisions_battle_id ON sim_battle_decisions (fk_battle_id);

-- -----------------------------------------------------------------------
-- Decision-model recording gaps — the battle engine already tracks all of
-- this state in memory (models/pokemon.py, battle/battle.py) but never
-- wrote it out to sim_battle_decisions.
-- -----------------------------------------------------------------------
ALTER TABLE sim_battle_decisions
    ADD COLUMN IF NOT EXISTS opp_atk_stage SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_def_stage SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_spe_stage SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_spc_stage SMALLINT,
    ADD COLUMN IF NOT EXISTS active_reflect_turns SMALLINT,
    ADD COLUMN IF NOT EXISTS active_light_screen_turns SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_reflect_turns SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_light_screen_turns SMALLINT,
    ADD COLUMN IF NOT EXISTS active_substitute_hp SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_substitute_hp SMALLINT,
    ADD COLUMN IF NOT EXISTS active_is_seeded BOOLEAN,
    ADD COLUMN IF NOT EXISTS opp_is_seeded BOOLEAN,
    ADD COLUMN IF NOT EXISTS active_toxic_counter SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_toxic_counter SMALLINT,
    ADD COLUMN IF NOT EXISTS active_pokemon_remaining SMALLINT,
    ADD COLUMN IF NOT EXISTS opp_pokemon_remaining SMALLINT,
    ADD COLUMN IF NOT EXISTS active_bench_pokemon_ids SMALLINT[],
    ADD COLUMN IF NOT EXISTS opp_bench_pokemon_ids SMALLINT[];

-- =============================================================================
-- Theoretical (synthetic) trainers — kept fully separate from bronze trainers.
-- IDs start at 20000, well clear of real trainers (currently max 1058).
-- =============================================================================
CREATE SEQUENCE IF NOT EXISTS theoretical_trainers_id_seq AS smallint START WITH 20000;

CREATE TABLE IF NOT EXISTS theoretical_trainers (
    pk_theoretical_trainers_id  SMALLINT     PRIMARY KEY DEFAULT nextval('theoretical_trainers_id_seq'),
    label                       VARCHAR(200) NOT NULL,
    created_at                  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS theoretical_trainers_teams (
    pk_theoretical_trainers_teams_id SERIAL   PRIMARY KEY,
    fk_theoretical_trainers_id       SMALLINT NOT NULL REFERENCES theoretical_trainers(pk_theoretical_trainers_id),
    fk_pokemon_id                    SMALLINT NOT NULL REFERENCES pokemon(pk_pokemon_id),
    party_order                      SMALLINT NOT NULL,
    level                             SMALLINT NOT NULL,
    fk_move1_id                      SMALLINT NOT NULL REFERENCES moves(pk_moves_id),
    fk_move2_id                      SMALLINT REFERENCES moves(pk_moves_id),
    fk_move3_id                      SMALLINT REFERENCES moves(pk_moves_id),
    fk_move4_id                      SMALLINT REFERENCES moves(pk_moves_id)
);

CREATE INDEX IF NOT EXISTS idx_theoretical_teams_trainer_id
    ON theoretical_trainers_teams (fk_theoretical_trainers_id);

-- Parallel queue table — battles_to_sim has a real FK to trainers.pk_trainers_id,
-- so it cannot hold theoretical (>=20000) trainer ids. This table has no such FK,
-- since a row may reference either a real trainer or a theoretical one.
CREATE TABLE IF NOT EXISTS theoretical_battles_to_sim (
    pk_theoretical_battles_to_sim_id SERIAL       PRIMARY KEY,
    fk_trainers_id_one               INTEGER      NOT NULL,
    fk_trainers_id_two               INTEGER      NOT NULL,
    logic_profile_trainer1           VARCHAR(50)  NOT NULL,
    logic_profile_trainer2           VARCHAR(50)  NOT NULL,
    status                           VARCHAR(10)  NOT NULL DEFAULT 'pending',
    claimed_at                       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_theoretical_battles_to_sim_status
    ON theoretical_battles_to_sim (status)
    WHERE status = 'pending';

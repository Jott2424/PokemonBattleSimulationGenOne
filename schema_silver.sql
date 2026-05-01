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

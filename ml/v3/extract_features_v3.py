"""
Builds the win-probability model's training table from the simulation
results in Postgres, and writes it to a Parquet file for train_model.py.

Output shape: one row per (battle, subject trainer) — every battle
contributes TWO rows, one from each trainer's perspective (subject vs.
opponent), so the model is trained symmetrically and can answer
"what are the subject's odds against the opponent" regardless of which
trainer is asked about first. Label = 1 if the subject won, 0 if the
subject lost OR the battle was a draw (draws are grouped with losses,
not excluded).

Feature groups (see article_notes.md / conversation history for the
full design discussion):
  - Per-side aggregate stats (level, base stats, battle stats)
  - Per-side species-type profile (defensive/STAB signal)
  - Per-side move-type profile (offensive reach, independent of species type)
  - Per-side moveset profile (physical/special/status mix, power, accuracy, PP)
  - Per-side move-effect category counts (new in v3) — OHKO, sleep/paralysis
    infliction, trapping, priority, high-crit, recovery, explosion, evasion/
    accuracy manipulation, multi-hit — pulled from data/move_effects_map.py's
    Gen 1 effect taxonomy, the same source of truth the battle simulator
    itself dispatches on. These capture *which* specific Gen 1 mechanics a
    team has access to, which the physical/special/status split (already
    present in v1/v2) doesn't distinguish.
  - Lead-Pokemon block (party_order == 1, sent out first)
  - Cross-side effectiveness: subject's move-types vs opponent's species-types,
    both plain and STAB-adjusted, computed as a type-frequency-vector product
    against the type-effectiveness matrix (not exact per-move/per-Pokemon
    enumeration — a standard feature-engineering simplification, distinct
    from the battle simulator itself which computes exact ground truth)
  - Hard-counter counts, level/stat differentials, speed-advantage count,
    team-size differential
  - logic_profile (categorical, left as pandas 'category' dtype for
    XGBoost's native categorical support)

trainer_type is deliberately excluded (redundant with team composition).

Usage (run from ml/v3/):
    python extract_features_v3.py [--out FILE] [--games-id N]
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import psycopg2

# Reuse the simulator's own Gen 1 move-effect taxonomy instead of
# re-deriving/duplicating it here — same source of truth the battle engine
# dispatches on (mechanics/move_effects.py), so this stays in sync for free
# whenever a move's effect entry changes.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from data.move_effects_map import MOVE_EFFECTS  # noqa: E402

N_TYPES = 15  # bronze.types ids are 1..15, sequential, no gaps
PHYSICAL, SPECIAL, STATUS = 1, 2, 3


def _load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, "..", "..", "config.json")) as f:
        return json.load(f)


def _connect():
    db = _load_config()["database"]
    return psycopg2.connect(
        host=db["host"], port=db["port"], dbname=db["dbname"],
        user=db["user"], password=db["password"], options=db.get("options", "")
    )


def _type_effectiveness_matrix(conn):
    """15x15 numpy array, E[attacker_type-1, defender_type-1] = multiplier."""
    df = pd.read_sql("SELECT fk_types_id_a, fk_types_id_d, multiplier FROM bronze.types_effectiveness", conn)
    mat = np.ones((N_TYPES, N_TYPES), dtype=np.float64)
    for row in df.itertuples(index=False):
        mat[row.fk_types_id_a - 1, row.fk_types_id_d - 1] = float(row.multiplier)
    return mat


def _load_type_names(conn):
    """Lowercase type name per id, index 0..N_TYPES-1 (id 1 -> index 0)."""
    df = pd.read_sql("SELECT pk_types_id, type FROM bronze.types ORDER BY pk_types_id", conn)
    return [t.lower() for t in df["type"]]


def _load_pokemon(conn):
    return pd.read_sql(
        "SELECT pk_pokemon_id AS pokemon_id, fk_types_id_one AS type1, fk_types_id_two AS type2 "
        "FROM bronze.pokemon", conn
    ).set_index("pokemon_id")


def _load_pokemon_stats(conn):
    return pd.read_sql(
        "SELECT fk_pokemon_id AS pokemon_id, hp AS base_hp, attack AS base_attack, "
        "defense AS base_defense, special AS base_special, speed AS base_speed "
        "FROM bronze.pokemon_stats", conn
    ).set_index("pokemon_id")


def _load_moves(conn):
    return pd.read_sql(
        "SELECT pk_moves_id AS move_id, m.move AS move_name, fk_types_id AS move_type, "
        "fk_damage_categories_id AS category, power, accuracy, pp "
        "FROM bronze.moves m JOIN bronze.moves_stats ms ON ms.fk_moves_id = m.pk_moves_id", conn
    ).set_index("move_id")


def _classify_move_effect(move_name: str) -> dict:
    """Looks up this move's Gen 1 effect in MOVE_EFFECTS (DB names use
    underscores, the effects map uses hyphens) and returns category flags.
    A move absent from MOVE_EFFECTS (none currently, but defensive) gets
    all-False flags rather than raising."""
    key = (move_name or "").replace("_", "-")
    data = MOVE_EFFECTS.get(key, {})
    effect = data.get("effect")
    return {
        "is_ohko": effect == "ohko",
        "is_sleep_inflict": effect == "status_sleep",
        "is_paralyze_inflict": effect == "status_paralyze",
        "is_trapping": effect == "binding",
        "is_priority": data.get("priority", 0) > 0,
        "is_high_crit": (effect == "high_crit") or bool(data.get("high_crit", False)),
        "is_recovery": effect in ("heal_half", "rest"),
        "is_explosion": effect == "self_destruct",
        "is_evasion_accuracy": effect == "stat_change" and data.get("stat") in ("accuracy", "evasion"),
        "is_multi_hit": effect in ("multi_hit", "twineedle"),
    }


def _add_effect_flags(moves_ref: pd.DataFrame) -> pd.DataFrame:
    flags = moves_ref["move_name"].apply(_classify_move_effect).apply(pd.Series).astype(np.int64)
    return pd.concat([moves_ref, flags], axis=1)


def _load_slots(conn, games_id):
    """One row per (battle, trainer, party_order) with type + base/battle stats."""
    sql = """
        SELECT s.fk_battle_id AS battle_id, s.fk_trainer_id AS trainer_id,
               s.party_order, s.level,
               s.hp AS battle_hp, s.attack AS battle_attack, s.defense AS battle_defense,
               s.special AS battle_special, s.speed AS battle_speed,
               s.fk_pokemon_id AS pokemon_id,
               s.fk_move1_id AS move1_id, s.fk_move2_id AS move2_id,
               s.fk_move3_id AS move3_id, s.fk_move4_id AS move4_id
        FROM silver.sim_battle_team_snapshots s
        JOIN bronze.trainers t ON t.pk_trainers_id = s.fk_trainer_id AND t.fk_games_id = %(games_id)s
    """
    return pd.read_sql(sql, conn, params={"games_id": games_id})


def _load_battles(conn, games_id):
    sql = """
        SELECT b.id AS battle_id, b.fk_trainer1_id AS trainer1_id, b.fk_trainer2_id AS trainer2_id,
               b.logic_profile_1, b.logic_profile_2, b.winner_trainer_id
               -- total_turns deliberately NOT selected: only known after a battle
               -- happens, so it would leak information a real pre-battle
               -- prediction could never have.
        FROM silver.sim_battles b
        JOIN bronze.trainers t1 ON t1.pk_trainers_id = b.fk_trainer1_id AND t1.fk_games_id = %(games_id)s
        JOIN bronze.trainers t2 ON t2.pk_trainers_id = b.fk_trainer2_id AND t2.fk_games_id = %(games_id)s
    """
    return pd.read_sql(sql, conn, params={"games_id": games_id})


def _onehot_sum(ids: pd.Series, n: int) -> np.ndarray:
    """For a Series of 1..n type ids (NaN allowed), return an (len(ids), n) one-hot array."""
    out = np.zeros((len(ids), n), dtype=np.float64)
    valid = ids.notna()
    idx = ids[valid].astype(int).values - 1
    out[np.where(valid)[0], idx] = 1.0
    return out


_EFFECT_COUNT_COLS = [
    "ohko_move_count", "sleep_move_count", "paralysis_move_count", "trapping_move_count",
    "priority_move_count", "high_crit_move_count", "recovery_move_count", "explosion_move_count",
    "evasion_accuracy_move_count", "multi_hit_move_count",
]


def build_side_profile(slots: pd.DataFrame, moves: pd.DataFrame, type_names: list) -> pd.DataFrame:
    """Aggregates slot-level data to one row per (battle_id, trainer_id)."""
    key = ["battle_id", "trainer_id"]

    # --- Species-type frequency vectors (dual-typed Pokemon count in both slots) ---
    type1_oh = _onehot_sum(slots["type1"], N_TYPES)
    type2_oh = _onehot_sum(slots["type2"], N_TYPES)
    species_type_freq = type1_oh + type2_oh
    species_cols = [f"species_type_{type_names[i]}_freq" for i in range(N_TYPES)]
    species_df = pd.DataFrame(species_type_freq, columns=species_cols, index=slots.index)

    slot_agg_src = pd.concat([slots[key + ["level",
        "battle_hp", "battle_attack", "battle_defense", "battle_special", "battle_speed"]],
        species_df], axis=1)
    slot_agg_src["has_type2"] = slots["type2"].notna().astype(np.int64)

    # Base stats need the pokemon_id -> base stat join, done by the caller before this
    # function is called (see main()); slots already carries base_* columns by then.
    for stat in ["base_hp", "base_attack", "base_defense", "base_special", "base_speed"]:
        slot_agg_src[stat] = slots[stat]

    g = slot_agg_src.groupby(key)
    agg_spec = {"level": ["sum", "mean", "min", "max"]}
    for stat in ["battle_hp", "battle_attack", "battle_defense", "battle_special", "battle_speed",
                 "base_hp", "base_attack", "base_defense", "base_special", "base_speed"]:
        agg_spec[stat] = ["sum", "mean", "min", "max"]
    for c in species_cols:
        agg_spec[c] = ["sum"]
    agg_spec["has_type2"] = ["sum"]

    slot_profile = g.agg(agg_spec)
    slot_profile.columns = ["_".join(c) if isinstance(c, tuple) and c[1] else c[0]
                             for c in slot_profile.columns]
    slot_profile = slot_profile.reset_index()
    slot_profile["team_size"] = g.size().values
    for c in species_cols:
        slot_profile[f"{c}_present"] = (slot_profile[f"{c}_sum"] > 0).astype(np.int8)
    slot_profile["species_type_distinct_count"] = slot_profile[[f"{c}_present" for c in species_cols]].sum(axis=1)
    # Drop the redundant "_sum" suffix on species_type_N_freq (only one agg func
    # was applied, so the suffix carries no information) — keeps the column name
    # consistent with move_type_N_freq, which never had a suffix added.
    slot_profile = slot_profile.rename(columns={f"{c}_sum": c for c in species_cols})

    # --- Manual-feature-design additions: level range, team/type/move diversity ratios ---
    slot_profile["level_range"] = slot_profile["level_max"] - slot_profile["level_min"]

    distinct_pokemon = slots.groupby(key)["pokemon_id"].nunique().rename("distinct_pokemon_count")
    slot_profile = slot_profile.merge(distinct_pokemon, on=key, how="left")
    slot_profile["team_diversity_ratio"] = (
        slot_profile["distinct_pokemon_count"] / slot_profile["team_size"]
    )

    # Type-slot count: 1 per single-typed Pokemon, 2 per dual-typed (has_type2_sum
    # counts how many team members are dual-typed).
    type_slot_count = slot_profile["team_size"] + slot_profile["has_type2_sum"]
    slot_profile["type_diversity_ratio"] = (
        slot_profile["species_type_distinct_count"] / type_slot_count
    )
    slot_profile = slot_profile.drop(columns=["has_type2_sum"])

    # --- Lead Pokemon (party_order == 1) block ---
    # A handful of trainers (4 of 1058, a pre-existing raw-data quirk) have two
    # roster rows sharing party_order=1 — dedupe defensively so the later merge
    # can never produce a cartesian blow-up.
    lead = slots[slots["party_order"] == 1].drop_duplicates(subset=key, keep="first").copy()
    lead_cols = {
        "level": "lead_level", "type1": "lead_type1", "type2": "lead_type2",
        "battle_hp": "lead_battle_hp", "battle_attack": "lead_battle_attack",
        "battle_defense": "lead_battle_defense", "battle_special": "lead_battle_special",
        "battle_speed": "lead_battle_speed",
        "base_hp": "lead_base_hp", "base_attack": "lead_base_attack",
        "base_defense": "lead_base_defense", "base_special": "lead_base_special",
        "base_speed": "lead_base_speed",
    }
    lead = lead[key + list(lead_cols.keys())].rename(columns=lead_cols)
    type_name_map = {i + 1: name for i, name in enumerate(type_names)}
    lead["lead_type1"] = lead["lead_type1"].map(type_name_map)
    lead["lead_type2"] = lead["lead_type2"].map(type_name_map)

    # --- Move-level aggregation ---
    stab = moves["is_stab"].astype(np.float64).values[:, None]
    dmg_mask = moves["category"].isin([PHYSICAL, SPECIAL])

    move_type_oh = _onehot_sum(moves.loc[dmg_mask, "move_type"], N_TYPES)
    move_type_cols = [f"move_type_{type_names[i]}_freq" for i in range(N_TYPES)]
    move_type_df = pd.DataFrame(move_type_oh, columns=move_type_cols, index=moves.index[dmg_mask])

    stab_type_oh = move_type_oh * stab[dmg_mask.values]
    stab_type_cols = [f"stab_move_type_{type_names[i]}_freq" for i in range(N_TYPES)]
    stab_type_df = pd.DataFrame(stab_type_oh, columns=stab_type_cols, index=moves.index[dmg_mask])

    move_type_src = pd.concat([moves.loc[dmg_mask, key], move_type_df, stab_type_df], axis=1)
    move_type_profile = move_type_src.groupby(key)[move_type_cols + stab_type_cols].sum().reset_index()

    moves["is_physical"] = (moves["category"] == PHYSICAL).astype(np.int64)
    moves["is_special"] = (moves["category"] == SPECIAL).astype(np.int64)
    moves["is_status"] = (moves["category"] == STATUS).astype(np.int64)
    moveset_profile = moves.groupby(key).agg(
        move_count=("category", "count"),
        distinct_move_count=("move_id", "nunique"),
        physical_move_count=("is_physical", "sum"),
        special_move_count=("is_special", "sum"),
        status_move_count=("is_status", "sum"),
        avg_move_power=("power", "mean"),
        max_move_power=("power", "max"),
        avg_move_accuracy=("accuracy", "mean"),
        total_pp=("pp", "sum"),
        stab_move_count=("is_stab", "sum"),
        # Move-effect category counts — which specific Gen 1 mechanics this
        # team's moveset can reach for, not just the physical/special/status split.
        ohko_move_count=("is_ohko", "sum"),
        sleep_move_count=("is_sleep_inflict", "sum"),
        paralysis_move_count=("is_paralyze_inflict", "sum"),
        trapping_move_count=("is_trapping", "sum"),
        priority_move_count=("is_priority", "sum"),
        high_crit_move_count=("is_high_crit", "sum"),
        recovery_move_count=("is_recovery", "sum"),
        explosion_move_count=("is_explosion", "sum"),
        evasion_accuracy_move_count=("is_evasion_accuracy", "sum"),
        multi_hit_move_count=("is_multi_hit", "sum"),
    ).reset_index()
    moveset_profile["stab_fraction"] = (
        moveset_profile["stab_move_count"] / moveset_profile["move_count"].replace(0, np.nan)
    ).fillna(0.0)
    moveset_profile["move_diversity_ratio"] = (
        moveset_profile["distinct_move_count"] / moveset_profile["move_count"].replace(0, np.nan)
    ).fillna(0.0)

    profile = slot_profile.merge(lead, on=key, how="left")
    profile = profile.merge(moveset_profile, on=key, how="left")
    profile = profile.merge(move_type_profile, on=key, how="left")
    for c in (move_type_cols + stab_type_cols + ["move_count", "distinct_move_count", "physical_move_count",
            "special_move_count", "status_move_count", "stab_move_count", "total_pp"] + _EFFECT_COUNT_COLS):
        profile[c] = profile[c].fillna(0.0)
    return profile


def build_move_table(slots: pd.DataFrame, moves_ref: pd.DataFrame) -> pd.DataFrame:
    """Melts the 4 move-id columns into one row per (battle, trainer, move instance),
    with move_type/category/power/accuracy/pp/effect-flags resolved and an is_stab
    flag computed against that Pokemon's own species type(s)."""
    key = ["battle_id", "trainer_id"]
    frames = []
    for i in range(1, 5):
        col = f"move{i}_id"
        sub = slots[key + [col, "type1", "type2"]].rename(columns={col: "move_id"})
        sub = sub[sub["move_id"].notna()]
        frames.append(sub)
    m = pd.concat(frames, ignore_index=True)
    m = m.merge(moves_ref, left_on="move_id", right_index=True, how="left")
    m["is_stab"] = (m["move_type"] == m["type1"]) | (m["move_type"] == m["type2"])
    return m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "training_data.parquet"))
    parser.add_argument("--games-id", type=int, default=2, help="bronze.games id to restrict to (2 = Blue)")
    args = parser.parse_args()

    conn = _connect()
    print("Loading reference tables...")
    eff_matrix = _type_effectiveness_matrix(conn)
    type_names = _load_type_names(conn)
    pokemon = _load_pokemon(conn)
    pokemon_stats = _load_pokemon_stats(conn)
    moves_ref = _add_effect_flags(_load_moves(conn))

    print("Loading team snapshots...")
    slots = _load_slots(conn, args.games_id)
    slots = slots.join(pokemon, on="pokemon_id").join(pokemon_stats, on="pokemon_id")

    print("Building move table...")
    moves = build_move_table(slots, moves_ref)

    print("Building per-side team profiles...")
    profile = build_side_profile(slots, moves, type_names)
    print(f"  {len(profile)} (battle, trainer) sides")

    print("Loading battle outcomes...")
    battles = _load_battles(conn, args.games_id)
    conn.close()

    print("Assembling subject/opponent rows...")
    p_subj = profile.add_prefix("subj_").rename(columns={"subj_battle_id": "battle_id", "subj_trainer_id": "subject_trainer_id"})
    p_opp = profile.add_prefix("opp_").rename(columns={"opp_battle_id": "battle_id", "opp_trainer_id": "opponent_trainer_id"})
    rows = p_subj.merge(p_opp, on="battle_id")
    rows = rows[rows["subject_trainer_id"] != rows["opponent_trainer_id"]].reset_index(drop=True)
    # exactly 2 rows per battle survive: (t1 as subject, t2 as opponent) and vice versa

    b = battles.set_index("battle_id")
    rows = rows.join(b[["trainer1_id", "trainer2_id", "logic_profile_1", "logic_profile_2",
                         "winner_trainer_id"]], on="battle_id")
    rows["subject_profile"] = np.where(rows["subject_trainer_id"] == rows["trainer1_id"],
                                        rows["logic_profile_1"], rows["logic_profile_2"])
    rows["opponent_profile"] = np.where(rows["subject_trainer_id"] == rows["trainer1_id"],
                                         rows["logic_profile_2"], rows["logic_profile_1"])
    rows["label_win"] = (rows["subject_trainer_id"] == rows["winner_trainer_id"]).astype(np.int8)
    rows = rows.drop(columns=["trainer1_id", "trainer2_id", "logic_profile_1", "logic_profile_2",
                               "winner_trainer_id"])

    print("Computing cross-side features...")
    subj_move_freq = rows[[f"subj_move_type_{t}_freq" for t in type_names]].values
    subj_stab_move_freq = rows[[f"subj_stab_move_type_{t}_freq" for t in type_names]].values
    opp_species_freq = rows[[f"opp_species_type_{t}_freq" for t in type_names]].values
    opp_move_freq = rows[[f"opp_move_type_{t}_freq" for t in type_names]].values
    opp_stab_move_freq = rows[[f"opp_stab_move_type_{t}_freq" for t in type_names]].values
    subj_species_freq = rows[[f"subj_species_type_{t}_freq" for t in type_names]].values

    def weighted_eff(move_freq, species_freq):
        num = np.einsum("ij,jk,ik->i", move_freq, eff_matrix, species_freq)
        den = move_freq.sum(axis=1) * species_freq.sum(axis=1)
        return np.divide(num, den, out=np.ones_like(num), where=den > 0)

    rows["subj_offense_effectiveness"] = weighted_eff(subj_move_freq, opp_species_freq)
    rows["opp_offense_effectiveness"] = weighted_eff(opp_move_freq, subj_species_freq)
    # STAB-adjusted: STAB moves get an extra 0.5x weight (1.0 base + 0.5 bonus = 1.5x)
    rows["subj_offense_effectiveness_stab"] = weighted_eff(subj_move_freq + 0.5 * subj_stab_move_freq, opp_species_freq)
    rows["opp_offense_effectiveness_stab"] = weighted_eff(opp_move_freq + 0.5 * opp_stab_move_freq, subj_species_freq)

    # Hard-counter count: how many of the opponent's species-type "slots" are resisted
    # (multiplier <= 0.5) by the subject's move-type coverage, weighted by frequency.
    resist_matrix = (eff_matrix <= 0.5).astype(np.float64)
    rows["subj_hard_counter_score"] = np.einsum("ij,jk,ik->i",
        (subj_move_freq > 0).astype(np.float64), resist_matrix, opp_species_freq)
    rows["opp_hard_counter_score"] = np.einsum("ij,jk,ik->i",
        (opp_move_freq > 0).astype(np.float64), resist_matrix, subj_species_freq)

    for stat in ["level_sum", "level_mean", "battle_hp_sum", "battle_attack_sum", "battle_defense_sum",
                 "battle_special_sum", "battle_speed_sum", "base_hp_sum", "base_attack_sum",
                 "base_defense_sum", "base_special_sum", "base_speed_sum"]:
        rows[f"diff_{stat}"] = rows[f"subj_{stat}"] - rows[f"opp_{stat}"]
    rows["diff_team_size"] = rows["subj_team_size"] - rows["opp_team_size"]
    for ratio in ["team_diversity_ratio", "type_diversity_ratio", "level_range", "move_diversity_ratio"]:
        rows[f"diff_{ratio}"] = rows[f"subj_{ratio}"] - rows[f"opp_{ratio}"]
    # Team-average speed comparison, not a per-Pokemon outspeed count — the exact
    # "how many of subject's Pokemon outspeed how many of opponent's" would need
    # the raw per-slot speed table cross-joined per battle, which this pipeline
    # doesn't carry through to this stage. Documented simplification.
    rows["subj_speed_advantage"] = (
        rows["subj_battle_speed_mean"] > rows["opp_battle_speed_mean"]
    ).astype(np.int8)

    rows["subject_profile"] = rows["subject_profile"].astype("category")
    rows["opponent_profile"] = rows["opponent_profile"].astype("category")
    for c in ["subj_lead_type1", "subj_lead_type2", "opp_lead_type1", "opp_lead_type2"]:
        rows[c] = rows[c].astype("category")

    print(f"Writing {len(rows)} rows x {len(rows.columns)} columns to {args.out}")
    rows.to_parquet(args.out, index=False)
    print("Done.")


if __name__ == "__main__":
    main()

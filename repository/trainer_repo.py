"""
Reads trainer, team, and reference data from the bronze-layer Postgres tables.
All writes go through the recorder module — this file is read-only.
"""
from typing import Dict, List, Optional, Tuple

from db.connection import get_connection, get_cursor
from models.move import Move
from models.pokemon import Pokemon
from models.trainer import Trainer


# ---------------------------------------------------------------------------
# Reference data (loaded once per process)
# ---------------------------------------------------------------------------

def get_type_chart(conn) -> Dict[Tuple[int, int], float]:
    """Returns {(attacking_type_id, defending_type_id): multiplier}."""
    with get_cursor(conn) as cur:
        cur.execute("SELECT fk_types_id_a, fk_types_id_d, multiplier FROM types_effectiveness")
        return {(row["fk_types_id_a"], row["fk_types_id_d"]): float(row["multiplier"])
                for row in cur.fetchall()}


def get_move_by_name(conn, move_name: str) -> Optional[Move]:
    """Look up a move by its name column. Returns None if not found."""
    move_name = move_name.replace("-", "_")  # DB stores underscores
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                m.pk_moves_id        AS id,
                m.move               AS name,
                m.fk_types_id        AS type_id,
                t.type               AS type_name,
                dc.damage_category   AS damage_category,
                ms.power,
                ms.accuracy,
                ms.pp
            FROM moves m
            JOIN types t              ON t.pk_types_id = m.fk_types_id
            JOIN moves_damage_categories dc ON dc.pk_move_damage_categories_id = m.fk_damage_categories_id
            LEFT JOIN moves_stats ms  ON ms.fk_moves_id = m.pk_moves_id
            WHERE m.move = %s
        """, (move_name,))
        row = cur.fetchone()
    if row is None:
        return None
    return Move(
        id=row["id"],
        name=row["name"],
        type_id=row["type_id"],
        type_name=row["type_name"],
        damage_category=row["damage_category"].lower(),
        power=row["power"],
        accuracy=row["accuracy"],
        pp_start=row["pp"],
    )


def get_moves_by_ids(conn, move_ids: List[int]) -> Dict[int, Move]:
    """Batch move lookup — one round trip instead of one per move."""
    if not move_ids:
        return {}
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                m.pk_moves_id        AS id,
                m.move               AS name,
                m.fk_types_id        AS type_id,
                t.type               AS type_name,
                dc.damage_category   AS damage_category,
                ms.power,
                ms.accuracy,
                ms.pp
            FROM moves m
            JOIN types t              ON t.pk_types_id = m.fk_types_id
            JOIN moves_damage_categories dc ON dc.pk_move_damage_categories_id = m.fk_damage_categories_id
            LEFT JOIN moves_stats ms  ON ms.fk_moves_id = m.pk_moves_id
            WHERE m.pk_moves_id = ANY(%s)
        """, (list(set(move_ids)),))
        rows = cur.fetchall()
    return {
        row["id"]: Move(
            id=row["id"],
            name=row["name"],
            type_id=row["type_id"],
            type_name=row["type_name"],
            damage_category=row["damage_category"].lower(),
            power=row["power"],
            accuracy=row["accuracy"],
            pp_start=row["pp"],
        )
        for row in rows
    }


def get_move(conn, move_id: int) -> Move:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                m.pk_moves_id        AS id,
                m.move               AS name,
                m.fk_types_id        AS type_id,
                t.type               AS type_name,
                dc.damage_category   AS damage_category,
                ms.power,
                ms.accuracy,
                ms.pp
            FROM moves m
            JOIN types t              ON t.pk_types_id = m.fk_types_id
            JOIN moves_damage_categories dc ON dc.pk_move_damage_categories_id = m.fk_damage_categories_id
            LEFT JOIN moves_stats ms  ON ms.fk_moves_id = m.pk_moves_id
            WHERE m.pk_moves_id = %s
        """, (move_id,))
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Move id {move_id} not found in database.")
    return Move(
        id=row["id"],
        name=row["name"],
        type_id=row["type_id"],
        type_name=row["type_name"],
        damage_category=row["damage_category"].lower(),
        power=row["power"],
        accuracy=row["accuracy"],
        pp_start=row["pp"],
    )


def get_trainer_team(conn, trainer_id: int) -> List[Pokemon]:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                tt.pk_trainers_teams_id,
                tt.fk_pokemon_id,
                p.pokemon           AS name,
                p.fk_types_id_one   AS type_id_one,
                p.fk_types_id_two   AS type_id_two,
                t1.type             AS type_name_one,
                t2.type             AS type_name_two,
                tt.level,
                tt.party_order,
                tt.fk_move1_id,
                tt.fk_move2_id,
                tt.fk_move3_id,
                tt.fk_move4_id,
                ps.hp               AS base_hp,
                ps.attack           AS base_attack,
                ps.defense          AS base_defense,
                ps.special          AS base_special,
                ps.speed            AS base_speed
            FROM trainers_teams tt
            JOIN pokemon p          ON p.pk_pokemon_id = tt.fk_pokemon_id
            JOIN types t1           ON t1.pk_types_id = p.fk_types_id_one
            LEFT JOIN types t2      ON t2.pk_types_id = p.fk_types_id_two
            JOIN pokemon_stats ps   ON ps.fk_pokemon_id = tt.fk_pokemon_id
            WHERE tt.fk_trainers_id = %s
            ORDER BY tt.party_order ASC
        """, (trainer_id,))
        rows = cur.fetchall()

    all_move_ids = {row[f"fk_move{i}_id"] for row in rows for i in range(1, 5) if row[f"fk_move{i}_id"] is not None}
    moves_by_id = get_moves_by_ids(conn, list(all_move_ids))

    team = []
    for row in rows:
        move_ids = [row[f"fk_move{i}_id"] for i in range(1, 5) if row[f"fk_move{i}_id"] is not None]
        moves = [moves_by_id[mid] for mid in move_ids]

        type_ids = [row["type_id_one"]]
        type_names = [row["type_name_one"]]
        if row["type_id_two"] is not None:
            type_ids.append(row["type_id_two"])
            type_names.append(row["type_name_two"])

        poke = Pokemon(
            id=row["fk_pokemon_id"],
            name=row["name"],
            level=row["level"],
            type_ids=type_ids,
            type_names=type_names,
            moves=moves,
            party_order=row["party_order"],
            base_hp=row["base_hp"],
            base_attack=row["base_attack"],
            base_defense=row["base_defense"],
            base_special=row["base_special"],
            base_speed=row["base_speed"],
        )
        team.append(poke)
    return team


def get_trainer(conn, trainer_id: int, logic_profile) -> Trainer:
    if trainer_id >= THEORETICAL_ID_OFFSET:
        return get_theoretical_trainer(conn, trainer_id, logic_profile)
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT pk_trainers_id AS id, long_name AS name
            FROM trainers
            WHERE pk_trainers_id = %s
        """, (trainer_id,))
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Trainer id {trainer_id} not found.")
    team = get_trainer_team(conn, trainer_id)
    return Trainer(id=row["id"], name=row["name"], team=team, logic_profile=logic_profile)


# ---------------------------------------------------------------------------
# Theoretical (synthetic) trainers — kept separate from bronze data.
# IDs >= THEORETICAL_ID_OFFSET live in theoretical_trainers/theoretical_trainers_teams.
# ---------------------------------------------------------------------------

THEORETICAL_ID_OFFSET = 20000


def get_theoretical_trainer_team(conn, trainer_id: int) -> List[Pokemon]:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                tt.fk_pokemon_id,
                p.pokemon           AS name,
                p.fk_types_id_one   AS type_id_one,
                p.fk_types_id_two   AS type_id_two,
                t1.type             AS type_name_one,
                t2.type             AS type_name_two,
                tt.level,
                tt.party_order,
                tt.fk_move1_id,
                tt.fk_move2_id,
                tt.fk_move3_id,
                tt.fk_move4_id,
                ps.hp               AS base_hp,
                ps.attack           AS base_attack,
                ps.defense          AS base_defense,
                ps.special          AS base_special,
                ps.speed            AS base_speed
            FROM theoretical_trainers_teams tt
            JOIN pokemon p          ON p.pk_pokemon_id = tt.fk_pokemon_id
            JOIN types t1           ON t1.pk_types_id = p.fk_types_id_one
            LEFT JOIN types t2      ON t2.pk_types_id = p.fk_types_id_two
            JOIN pokemon_stats ps   ON ps.fk_pokemon_id = tt.fk_pokemon_id
            WHERE tt.fk_theoretical_trainers_id = %s
            ORDER BY tt.party_order ASC
        """, (trainer_id,))
        rows = cur.fetchall()

    all_move_ids = {row[f"fk_move{i}_id"] for row in rows for i in range(1, 5) if row[f"fk_move{i}_id"] is not None}
    moves_by_id = get_moves_by_ids(conn, list(all_move_ids))

    team = []
    for row in rows:
        move_ids = [row[f"fk_move{i}_id"] for i in range(1, 5) if row[f"fk_move{i}_id"] is not None]
        moves = [moves_by_id[mid] for mid in move_ids]

        type_ids = [row["type_id_one"]]
        type_names = [row["type_name_one"]]
        if row["type_id_two"] is not None:
            type_ids.append(row["type_id_two"])
            type_names.append(row["type_name_two"])

        poke = Pokemon(
            id=row["fk_pokemon_id"],
            name=row["name"],
            level=row["level"],
            type_ids=type_ids,
            type_names=type_names,
            moves=moves,
            party_order=row["party_order"],
            base_hp=row["base_hp"],
            base_attack=row["base_attack"],
            base_defense=row["base_defense"],
            base_special=row["base_special"],
            base_speed=row["base_speed"],
        )
        team.append(poke)
    return team


def get_theoretical_trainer(conn, trainer_id: int, logic_profile) -> Trainer:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT pk_theoretical_trainers_id AS id, label AS name
            FROM theoretical_trainers
            WHERE pk_theoretical_trainers_id = %s
        """, (trainer_id,))
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Theoretical trainer id {trainer_id} not found.")
    team = get_theoretical_trainer_team(conn, trainer_id)
    return Trainer(id=row["id"], name=row["name"], team=team, logic_profile=logic_profile)


# ---------------------------------------------------------------------------
# Battle queue management
# ---------------------------------------------------------------------------

def claim_next_battle(conn) -> Optional[Dict]:
    """
    Atomically claim the next pending battle using SELECT FOR UPDATE SKIP LOCKED.
    Returns the battle row dict, or None if queue is empty.
    Sets status = 'running' and claimed_at = NOW() in the same transaction.
    """
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT pk_battles_to_sim_id AS id,
                   fk_trainers_id_one AS fk_trainer1_id,
                   fk_trainers_id_two AS fk_trainer2_id,
                   logic_profile_trainer1, logic_profile_trainer2
            FROM battles_to_sim
            WHERE status = 'pending'
            ORDER BY pk_battles_to_sim_id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("""
            UPDATE battles_to_sim
            SET status = 'running', claimed_at = NOW()
            WHERE pk_battles_to_sim_id = %s
        """, (row["id"],))
    return dict(row)


def mark_battle_done(conn, battle_queue_id: int):
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE battles_to_sim SET status = 'done'
            WHERE pk_battles_to_sim_id = %s
        """, (battle_queue_id,))


def requeue_stale_battles(conn, timeout_minutes: int = 30):
    """Reset battles stuck in 'running' longer than timeout_minutes back to 'pending'."""
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE battles_to_sim
            SET status = 'pending', claimed_at = NULL
            WHERE status = 'running'
              AND claimed_at < NOW() - INTERVAL '%s minutes'
        """, (timeout_minutes,))


# ---------------------------------------------------------------------------
# Theoretical battle queue — same shape as battles_to_sim, no trainer FK
# (rows may reference a real trainer id or a theoretical one).
# ---------------------------------------------------------------------------

def claim_next_theoretical_battle(conn) -> Optional[Dict]:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT pk_theoretical_battles_to_sim_id AS id,
                   fk_trainers_id_one AS fk_trainer1_id,
                   fk_trainers_id_two AS fk_trainer2_id,
                   logic_profile_trainer1, logic_profile_trainer2
            FROM theoretical_battles_to_sim
            WHERE status = 'pending'
            ORDER BY pk_theoretical_battles_to_sim_id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute("""
            UPDATE theoretical_battles_to_sim
            SET status = 'running', claimed_at = NOW()
            WHERE pk_theoretical_battles_to_sim_id = %s
        """, (row["id"],))
    return dict(row)


def mark_theoretical_battle_done(conn, battle_queue_id: int):
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE theoretical_battles_to_sim SET status = 'done'
            WHERE pk_theoretical_battles_to_sim_id = %s
        """, (battle_queue_id,))


def requeue_stale_theoretical_battles(conn, timeout_minutes: int = 30):
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE theoretical_battles_to_sim
            SET status = 'pending', claimed_at = NULL
            WHERE status = 'running'
              AND claimed_at < NOW() - INTERVAL '%s minutes'
        """, (timeout_minutes,))

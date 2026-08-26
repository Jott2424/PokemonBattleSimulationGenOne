"""
Reads trainer, team, and reference data from the bronze-layer Postgres tables.
All writes go through the recorder module — this file is read-only.
"""
import copy
from dataclasses import dataclass, field
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
# Preloaded reference cache — avoids re-querying static trainer/team/move data
# on every single battle. Trainer/team rows in bronze never change during a
# simulation run, so a worker can load everything once at startup.
#
# IMPORTANT: the cached Trainer objects are pristine templates. Pokemon/Move
# are mutable dataclasses (HP, PP, status, stat stages all change mid-battle),
# so a template must never be handed to a Battle directly — always hand out
# copy.deepcopy(template) via get_trainer_cached() so battles don't leak
# state into each other through a shared cached object.
# ---------------------------------------------------------------------------

@dataclass
class ReferenceCache:
    trainers: Dict[int, Trainer] = field(default_factory=dict)              # pristine templates
    theoretical_trainers: Dict[int, Trainer] = field(default_factory=dict)  # pristine templates
    moves_by_name: Dict[str, Move] = field(default_factory=dict)


def _build_move(row) -> Move:
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


def _group_teams_by_trainer(rows, moves_by_id: Dict[int, Move]) -> Dict[int, List[Pokemon]]:
    teams: Dict[int, List[Pokemon]] = {}
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
        teams.setdefault(row["trainer_id"], []).append(poke)
    return teams


def load_reference_cache(conn) -> ReferenceCache:
    """
    One-time load of every trainer's team (real + theoretical) and every move
    into memory. Call once per worker at startup — replaces 6 DB queries per
    battle (2x get_trainer) with a fixed handful of queries for the whole run.
    """
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
        """)
        move_rows = cur.fetchall()

        cur.execute("SELECT pk_trainers_id AS id, long_name AS name FROM trainers")
        trainer_meta_rows = cur.fetchall()

        cur.execute("""
            SELECT
                tt.fk_trainers_id   AS trainer_id,
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
            ORDER BY tt.fk_trainers_id, tt.party_order ASC
        """)
        team_rows = cur.fetchall()

        cur.execute("SELECT pk_theoretical_trainers_id AS id, label AS name FROM theoretical_trainers")
        theoretical_meta_rows = cur.fetchall()

        cur.execute("""
            SELECT
                tt.fk_theoretical_trainers_id AS trainer_id,
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
            ORDER BY tt.fk_theoretical_trainers_id, tt.party_order ASC
        """)
        theoretical_team_rows = cur.fetchall()

    moves_by_id = {row["id"]: _build_move(row) for row in move_rows}
    moves_by_name = {mv.name: mv for mv in moves_by_id.values()}

    teams_by_trainer = _group_teams_by_trainer(team_rows, moves_by_id)
    theoretical_teams_by_trainer = _group_teams_by_trainer(theoretical_team_rows, moves_by_id)

    trainers = {
        row["id"]: Trainer(id=row["id"], name=row["name"],
                            team=teams_by_trainer.get(row["id"], []), logic_profile=None)
        for row in trainer_meta_rows
    }
    theoretical_trainers = {
        row["id"]: Trainer(id=row["id"], name=row["name"],
                            team=theoretical_teams_by_trainer.get(row["id"], []), logic_profile=None)
        for row in theoretical_meta_rows
    }

    return ReferenceCache(trainers=trainers, theoretical_trainers=theoretical_trainers,
                           moves_by_name=moves_by_name)


def get_trainer_cached(cache: ReferenceCache, trainer_id: int, logic_profile) -> Trainer:
    """Returns a fresh, independent copy of the cached trainer template — safe to
    mutate during a battle without affecting any other battle."""
    source = cache.theoretical_trainers if trainer_id >= THEORETICAL_ID_OFFSET else cache.trainers
    template = source.get(trainer_id)
    if template is None:
        raise ValueError(f"Trainer id {trainer_id} not found in reference cache.")
    trainer = copy.deepcopy(template)
    trainer.logic_profile = logic_profile
    return trainer


def get_cached_move_for_name(cache: ReferenceCache, move_name: str) -> Optional[Move]:
    """In-memory replacement for get_move_by_name — used by the rare
    Metronome/Mirror Move path so it doesn't need a live DB query either."""
    move = cache.moves_by_name.get(move_name.replace("-", "_"))
    return copy.copy(move) if move is not None else None


# ---------------------------------------------------------------------------
# Battle queue management
# ---------------------------------------------------------------------------

def claim_battle_batch(conn, batch_size: int) -> List[Dict]:
    """
    Atomically claim up to batch_size pending battles in a single round trip
    (one CTE combining the SELECT FOR UPDATE SKIP LOCKED claim and the status
    update, instead of claiming one row at a time).
    """
    with get_cursor(conn) as cur:
        cur.execute("""
            WITH claimed AS (
                SELECT pk_battles_to_sim_id
                FROM battles_to_sim
                WHERE status = 'pending'
                ORDER BY pk_battles_to_sim_id ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE battles_to_sim b
            SET status = 'running', claimed_at = NOW()
            FROM claimed c
            WHERE b.pk_battles_to_sim_id = c.pk_battles_to_sim_id
            RETURNING b.pk_battles_to_sim_id AS id,
                      b.fk_trainers_id_one AS fk_trainer1_id,
                      b.fk_trainers_id_two AS fk_trainer2_id,
                      b.logic_profile_trainer1, b.logic_profile_trainer2
        """, (batch_size,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def mark_battles_done_batch(conn, battle_queue_ids: List[int]):
    if not battle_queue_ids:
        return
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE battles_to_sim SET status = 'done'
            WHERE pk_battles_to_sim_id = ANY(%s)
        """, (battle_queue_ids,))


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

def claim_theoretical_battle_batch(conn, batch_size: int) -> List[Dict]:
    with get_cursor(conn) as cur:
        cur.execute("""
            WITH claimed AS (
                SELECT pk_theoretical_battles_to_sim_id
                FROM theoretical_battles_to_sim
                WHERE status = 'pending'
                ORDER BY pk_theoretical_battles_to_sim_id ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE theoretical_battles_to_sim b
            SET status = 'running', claimed_at = NOW()
            FROM claimed c
            WHERE b.pk_theoretical_battles_to_sim_id = c.pk_theoretical_battles_to_sim_id
            RETURNING b.pk_theoretical_battles_to_sim_id AS id,
                      b.fk_trainers_id_one AS fk_trainer1_id,
                      b.fk_trainers_id_two AS fk_trainer2_id,
                      b.logic_profile_trainer1, b.logic_profile_trainer2
        """, (batch_size,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def mark_theoretical_battles_done_batch(conn, battle_queue_ids: List[int]):
    if not battle_queue_ids:
        return
    with get_cursor(conn) as cur:
        cur.execute("""
            UPDATE theoretical_battles_to_sim SET status = 'done'
            WHERE pk_theoretical_battles_to_sim_id = ANY(%s)
        """, (battle_queue_ids,))


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

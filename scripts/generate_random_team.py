"""
Generates one or more random theoretical teams for the simulator.

Per team:
  - Team size: uniform random 1-6.
  - Level tranche: a random 2-level bracket from 5-6 up to 59-60 (5,7,9,...,59
    as the low end). Every Pokemon on the team gets a level drawn from within
    that one bracket, so the whole team sits in a consistent power tier
    instead of levels being independently random per slot.
  - Species: sampled without replacement from all 151 Gen 1 Pokemon minus the
    5 legendaries (Articuno, Zapdos, Moltres, Mewtwo, Mew) — confirmed by name
    against bronze.pokemon, not assumed from id position.
  - Moveset: 2 STAB damaging moves (type1/type2, Physical or Special only —
    STAB doesn't mean anything for a Status move), 1 stat-modifying move
    (effect == "stat_change" in data/move_effects_map.py: any raise/lower of
    attack/defense/special/speed/accuracy/evasion), 1 fully random move from
    the whole 165-move pool. All 4 slots are deduped against each other.

    Edge case: pure Dragon-type Pokemon (Dratini, Dragonair) only have one
    damaging Dragon-type move in all of Gen 1 (Dragon Rage) — nowhere near
    enough for "2 STAB moves". Any STAB shortfall like that is padded with
    random damaging moves rather than raising, so generation never fails.

Usage (run from project root):
    python scripts/generate_random_team.py --out team.json
    python scripts/generate_random_team.py --count 20 --insert --label-prefix "Random"
    python scripts/generate_random_team.py --seed 42 --out team.json
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # sibling import below

from db.connection import get_connection, get_cursor
from data.move_effects_map import MOVE_EFFECTS
from build_theoretical_trainer import build_theoretical_trainer

LEGENDARY_NAMES = {"articuno", "zapdos", "moltres", "mewtwo", "mew"}
LEVEL_TRANCHE_LOWS = list(range(5, 60, 2))  # 5, 7, 9, ..., 59 -> brackets (5,6) .. (59,60)
DAMAGING_CATEGORIES = {"physical", "special"}


def _load_pokemon(conn):
    """{pokemon_id: (type1_name, type2_name_or_None)}, legendaries excluded."""
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT p.pk_pokemon_id AS id, p.pokemon AS name,
                   t1.type AS type1, t2.type AS type2
            FROM bronze.pokemon p
            JOIN bronze.types t1 ON t1.pk_types_id = p.fk_types_id_one
            LEFT JOIN bronze.types t2 ON t2.pk_types_id = p.fk_types_id_two
        """)
        rows = cur.fetchall()
    return {
        row["id"]: (row["type1"], row["type2"])
        for row in rows
        if row["name"].lower() not in LEGENDARY_NAMES
    }


def _load_moves(conn):
    """Returns (all_move_ids, damaging_moves_by_type, stat_change_move_ids)."""
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT m.pk_moves_id AS id, m.move AS name, t.type AS move_type,
                   dc.damage_category AS category
            FROM bronze.moves m
            JOIN bronze.types t ON t.pk_types_id = m.fk_types_id
            JOIN bronze.moves_damage_categories dc
                ON dc.pk_move_damage_categories_id = m.fk_damage_categories_id
        """)
        rows = cur.fetchall()

    all_move_ids = [row["id"] for row in rows]

    damaging_by_type: dict[str, list[int]] = {}
    for row in rows:
        if row["category"].lower() in DAMAGING_CATEGORIES:
            damaging_by_type.setdefault(row["move_type"], []).append(row["id"])

    stat_change_ids = [
        row["id"] for row in rows
        if MOVE_EFFECTS.get(row["name"], {}).get("effect") == "stat_change"
    ]

    all_damaging_ids = [
        row["id"] for row in rows if row["category"].lower() in DAMAGING_CATEGORIES
    ]

    return all_move_ids, damaging_by_type, stat_change_ids, all_damaging_ids


def _pick_moveset(type1, type2, damaging_by_type, stat_change_ids, all_damaging_ids,
                   all_move_ids, rng: random.Random) -> list:
    chosen = []

    # 2 STAB moves — pooled from either type, deduped, damaging categories only.
    stab_pool = list(set(damaging_by_type.get(type1, []) + damaging_by_type.get(type2, [])))
    rng.shuffle(stab_pool)
    chosen.extend(stab_pool[:2])

    # Fallback for STAB-starved types (pure Dragon: only 1 damaging move exists).
    shortfall = 2 - len(chosen)
    if shortfall > 0:
        backfill_pool = [m for m in all_damaging_ids if m not in chosen]
        chosen.extend(rng.sample(backfill_pool, min(shortfall, len(backfill_pool))))

    # 1 stat-modifying move.
    stat_pool = [m for m in stat_change_ids if m not in chosen]
    if stat_pool:
        chosen.append(rng.choice(stat_pool))

    # 1 fully random move (any move, any category).
    random_pool = [m for m in all_move_ids if m not in chosen]
    chosen.append(rng.choice(random_pool))

    return chosen[:4]


def generate_team(pokemon: dict, damaging_by_type: dict, stat_change_ids: list,
                   all_damaging_ids: list, all_move_ids: list, rng: random.Random) -> list:
    team_size = rng.randint(1, 6)
    tranche_low = rng.choice(LEVEL_TRANCHE_LOWS)
    tranche_high = tranche_low + 1

    species_ids = rng.sample(list(pokemon.keys()), team_size)

    team = []
    for pokemon_id in species_ids:
        type1, type2 = pokemon[pokemon_id]
        level = rng.choice([tranche_low, tranche_high])
        move_ids = _pick_moveset(type1, type2, damaging_by_type, stat_change_ids,
                                  all_damaging_ids, all_move_ids, rng)
        team.append({"pokemon_id": pokemon_id, "level": level, "move_ids": move_ids})
    return team


def main():
    parser = argparse.ArgumentParser(description="Generate random theoretical team(s)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (omit for nondeterministic)")
    parser.add_argument("--count", type=int, default=1, help="How many teams to generate")
    parser.add_argument("--out", default="team.json",
                         help="Output path for --count 1 (ignored with --insert); "
                              "with --count > 1 and no --insert, used as a prefix "
                              "(team.json -> team_1.json, team_2.json, ...)")
    parser.add_argument("--insert", action="store_true",
                         help="Insert directly as theoretical trainer(s) instead of writing JSON")
    parser.add_argument("--label-prefix", default="Random Team",
                         help="Label prefix when --insert is used (labels get ' N' appended)")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    with get_connection() as conn:
        pokemon = _load_pokemon(conn)
        all_move_ids, damaging_by_type, stat_change_ids, all_damaging_ids = _load_moves(conn)

        teams = [
            generate_team(pokemon, damaging_by_type, stat_change_ids, all_damaging_ids,
                          all_move_ids, rng)
            for _ in range(args.count)
        ]

        if args.insert:
            for i, team in enumerate(teams, start=1):
                label = f"{args.label_prefix} {i}" if args.count > 1 else args.label_prefix
                trainer_id = build_theoretical_trainer(conn, label, team)
                print(f"Created theoretical trainer id {trainer_id}: {label} "
                      f"({len(team)} Pokemon)")
            return

    if args.count == 1:
        with open(args.out, "w") as f:
            json.dump(teams[0], f, indent=2)
        print(f"Wrote {args.out} ({len(teams[0])} Pokemon)")
    else:
        base, ext = os.path.splitext(args.out)
        for i, team in enumerate(teams, start=1):
            path = f"{base}_{i}{ext}"
            with open(path, "w") as f:
                json.dump(team, f, indent=2)
            print(f"Wrote {path} ({len(team)} Pokemon)")


if __name__ == "__main__":
    main()

"""
Battle replay printer.

Usage (run from output/):
    python scripts/replay.py <battle_id>

Prints a turn-by-turn log showing each trainer's available options,
what they chose, and what happened.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import get_connection, get_cursor


def _fetch_battle(conn, battle_id: int) -> dict:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT b.id, b.fk_trainer1_id, b.fk_trainer2_id,
                   b.logic_profile_1, b.logic_profile_2,
                   b.total_turns, b.is_draw, b.winner_trainer_id,
                   t1.long_name AS trainer1_name,
                   t2.long_name AS trainer2_name
            FROM silver.sim_battles b
            JOIN bronze.trainers t1 ON t1.pk_trainers_id = b.fk_trainer1_id
            JOIN bronze.trainers t2 ON t2.pk_trainers_id = b.fk_trainer2_id
            WHERE b.id = %s
        """, (battle_id,))
        return cur.fetchone()


def _fetch_teams(conn, battle_id: int) -> dict:
    """Returns {trainer_id: [{pokemon_id, name, party_order}]} sorted by party order."""
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT s.fk_trainer_id, s.fk_pokemon_id, s.party_order, p.pokemon AS name
            FROM silver.sim_battle_team_snapshots s
            JOIN bronze.pokemon p ON p.pk_pokemon_id = s.fk_pokemon_id
            WHERE s.fk_battle_id = %s
            ORDER BY s.fk_trainer_id, s.party_order
        """, (battle_id,))
        rows = cur.fetchall()
    teams = {}
    for row in rows:
        teams.setdefault(row["fk_trainer_id"], []).append({
            "id": row["fk_pokemon_id"],
            "name": row["name"],
            "party_order": row["party_order"],
        })
    return teams


def _fetch_turns(conn, battle_id: int) -> list:
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                t.turn_number,
                t.fk_trainer_id,
                tr.long_name        AS trainer_name,
                p.pokemon           AS pokemon_name,
                t.action_type,
                t.fk_move_id,
                m.move              AS move_name,
                t.hit,
                t.is_critical,
                t.damage_dealt,
                t.fk_target_pokemon_id,
                tp.pokemon          AS target_name,
                t.target_hp_before,
                t.target_hp_after,
                t.target_fainted
            FROM silver.sim_battle_turns t
            JOIN bronze.trainers tr     ON tr.pk_trainers_id  = t.fk_trainer_id
            JOIN bronze.pokemon p       ON p.pk_pokemon_id    = t.fk_pokemon_id
            LEFT JOIN bronze.moves m    ON m.pk_moves_id      = t.fk_move_id
            LEFT JOIN bronze.pokemon tp ON tp.pk_pokemon_id   = t.fk_target_pokemon_id
            WHERE t.fk_battle_id = %s
            ORDER BY t.turn_number, t.fk_trainer_id
        """, (battle_id,))
        return cur.fetchall()


def _fetch_decisions(conn, battle_id: int) -> dict:
    """Returns {(turn_number, trainer_id): decision_row} with all move slots and names."""
    with get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                d.turn_number,
                d.fk_trainer_id,
                d.fk_active_pokemon_id,
                d.active_hp,
                d.active_status,
                d.chosen_action,
                d.chosen_move_id,
                d.move1_id, d.move1_pp,
                d.move2_id, d.move2_pp,
                d.move3_id, d.move3_pp,
                d.move4_id, d.move4_pp,
                ap.pokemon  AS active_pokemon_name,
                cm.move     AS chosen_move_name,
                m1.move     AS move1_name,
                m2.move     AS move2_name,
                m3.move     AS move3_name,
                m4.move     AS move4_name
            FROM silver.sim_battle_decisions d
            JOIN bronze.pokemon ap   ON ap.pk_pokemon_id = d.fk_active_pokemon_id
            LEFT JOIN bronze.moves cm ON cm.pk_moves_id  = d.chosen_move_id
            LEFT JOIN bronze.moves m1 ON m1.pk_moves_id  = d.move1_id
            LEFT JOIN bronze.moves m2 ON m2.pk_moves_id  = d.move2_id
            LEFT JOIN bronze.moves m3 ON m3.pk_moves_id  = d.move3_id
            LEFT JOIN bronze.moves m4 ON m4.pk_moves_id  = d.move4_id
            WHERE d.fk_battle_id = %s
            ORDER BY d.turn_number, d.fk_trainer_id
        """, (battle_id,))
        return {(row["turn_number"], row["fk_trainer_id"]): row for row in cur.fetchall()}


def _fmt_move(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title() if name else "unknown"


def _format_action(turn: dict) -> str:
    action = turn["action_type"]
    poke = turn["pokemon_name"]

    if action == "move":
        move = _fmt_move(turn["move_name"])
        if not turn["hit"]:
            return f"{poke} used {move}, but it missed!"
        return f"{poke} used {move}"

    if action == "attack":
        move = _fmt_move(turn["move_name"])
        target = turn["target_name"] or "?"
        if not turn["hit"]:
            return f"{poke} used {move} — missed!"
        parts = [f"{poke} used {move}"]
        if turn["is_critical"]:
            parts.append("(crit!)")
        dmg = turn["damage_dealt"] or 0
        parts.append(f"→ {dmg} dmg to {target}")
        parts.append(f"[{turn['target_hp_before']} → {turn['target_hp_after']} HP]")
        if turn["target_fainted"]:
            parts.append(f"** {target} fainted! **")
        return " ".join(parts)

    if action in ("swap", "forced_swap"):
        label = "forced swap" if action == "forced_swap" else "swapped"
        target = turn["target_name"] or "?"
        return f"{poke} {label} → {target}"

    if action == "struggle":
        dmg = turn["damage_dealt"] or 0
        target = turn["target_name"] or "?"
        return f"{poke} used Struggle → {dmg} dmg to {target} [{turn['target_hp_before']} → {turn['target_hp_after']} HP]"

    if action == "skipped":
        return f"{poke} couldn't move"

    if action == "recharge":
        return f"{poke} must recharge"

    if action == "flinched":
        return f"{poke} flinched"

    if action == "confusion_self_hit":
        dmg = turn["damage_dealt"] or 0
        return f"{poke} hurt itself in confusion — {dmg} dmg"

    if action == "charge":
        move = _fmt_move(turn["move_name"])
        return f"{poke} began charging {move}"

    if action == "charge_release":
        move = _fmt_move(turn["move_name"])
        dmg = turn["damage_dealt"] or 0
        crit = " (critical hit!)" if turn["is_critical"] else ""
        target = turn["target_name"] or "?"
        hp_b, hp_a = turn["target_hp_before"], turn["target_hp_after"]
        fainted = f" ** {target} fainted! **" if turn["target_fainted"] else ""
        return f"{poke} used {move}{crit} → {dmg} dmg to {target} [{hp_b} → {hp_a} HP]{fainted}"

    if action == "bide":
        return f"{poke} is storing energy (Bide)"

    if action == "metronome":
        move = _fmt_move(turn["move_name"])
        return f"{poke} used Metronome → {move}"

    if action == "mirror_move":
        move = _fmt_move(turn["move_name"])
        return f"{poke} used Mirror Move → {move}"

    if action == "substitute_break":
        target = turn["target_name"] or "?"
        return f"{poke}'s move broke {target}'s substitute"

    if action == "burn_drain":
        dmg = turn["damage_dealt"] or 0
        return f"{poke} hurt by burn — {dmg} dmg [{turn['target_hp_before']} → {turn['target_hp_after']} HP]"

    if action == "poison_drain":
        dmg = turn["damage_dealt"] or 0
        return f"{poke} hurt by poison — {dmg} dmg [{turn['target_hp_before']} → {turn['target_hp_after']} HP]"

    if action == "toxic_drain":
        dmg = turn["damage_dealt"] or 0
        return f"{poke} hurt by toxic — {dmg} dmg [{turn['target_hp_before']} → {turn['target_hp_after']} HP]"

    if action == "leech_seed_drain":
        dmg = turn["damage_dealt"] or 0
        note = f" ({turn['note']})" if turn.get("note") else ""
        return f"{poke} drained by Leech Seed — {dmg} dmg [{turn['target_hp_before']} → {turn['target_hp_after']} HP]{note}"

    if action == "binding_drain":
        dmg = turn["damage_dealt"] or 0
        return f"{poke} hurt by binding — {dmg} dmg [{turn['target_hp_before']} → {turn['target_hp_after']} HP]"

    return f"{poke}: {action}"


def print_replay(battle_id: int):
    with get_connection() as conn:
        battle = _fetch_battle(conn, battle_id)
        if battle is None:
            print(f"Battle {battle_id} not found.")
            return
        turns = _fetch_turns(conn, battle_id)
        decisions = _fetch_decisions(conn, battle_id)
        teams = _fetch_teams(conn, battle_id)

    t1_id = battle["fk_trainer1_id"]
    t2_id = battle["fk_trainer2_id"]
    t1_name = battle["trainer1_name"]
    t2_name = battle["trainer2_name"]

    trainer_name = {t1_id: t1_name, t2_id: t2_name}

    # Track fainted, active, and last-known status per pokemon across turns
    fainted: dict[int, set] = {t1_id: set(), t2_id: set()}
    active: dict[int, int] = {
        t1_id: teams[t1_id][0]["id"],
        t2_id: teams[t2_id][0]["id"],
    }
    # pokemon_id → last known status condition (updated whenever pokemon is active)
    poke_status: dict[int, str | None] = {}

    pokemon_name_map = {
        p["id"]: p["name"]
        for roster in teams.values()
        for p in roster
    }

    print("=" * 65)
    print(f"BATTLE {battle_id}:  {t1_name} ({battle['logic_profile_1']})  vs  {t2_name} ({battle['logic_profile_2']})")
    print("=" * 65)

    turn_map: dict[int, list] = {}
    for row in turns:
        turn_map.setdefault(row["turn_number"], []).append(row)

    for turn_num in sorted(turn_map.keys()):
        turn_rows = turn_map[turn_num]
        print(f"\n{'─' * 65}")
        print(f"  TURN {turn_num}")
        print(f"{'─' * 65}")

        for trainer_id in (t1_id, t2_id):
            dec = decisions.get((turn_num, trainer_id))
            if dec is None:
                continue

            tname = trainer_name[trainer_id]
            active_poke_id = active[trainer_id]

            # Update last-known status for active pokemon this turn
            poke_status[dec["fk_active_pokemon_id"]] = dec["active_status"]

            print(f"\n  {tname}")

            # --- Full roster display ---
            active_slot_printed = False
            for p in teams[trainer_id]:
                pid = p["id"]
                pname = p["name"]
                if pid in fainted[trainer_id]:
                    print(f"    [fainted] {pname}")
                elif pid == active_poke_id and not active_slot_printed:
                    active_slot_printed = True
                    status = dec["active_status"]
                    status_str = f"  [{status}]" if status else ""
                    print(f"    [active]  {pname}  HP {dec['active_hp']}{status_str}")
                else:
                    last_status = poke_status.get(pid)
                    status_str = f"  [{last_status}]" if last_status else ""
                    print(f"    [bench]   {pname}{status_str}")

            # --- Available options ---
            available_moves = []
            for i in range(1, 5):
                mid = dec[f"move{i}_id"]
                mname = dec[f"move{i}_name"]
                mpp = dec[f"move{i}_pp"]
                if mid is not None and mname and mpp is not None and mpp > 0:
                    available_moves.append(f"{_fmt_move(mname)} (PP {mpp})")

            if available_moves:
                print(f"    Moves:  {',  '.join(available_moves)}")

            # --- What was chosen ---
            action = dec["chosen_action"]
            if action == "attack" and dec["chosen_move_name"]:
                print(f"    Chose:  {_fmt_move(dec['chosen_move_name'])}")
            elif action == "swap":
                swap_event = next(
                    (r for r in turn_rows
                     if r["fk_trainer_id"] == trainer_id and r["action_type"] == "swap"),
                    None
                )
                swap_target = pokemon_name_map.get(swap_event["fk_target_pokemon_id"], "?") if swap_event else "?"
                print(f"    Chose:  Swap → {swap_target}")
            elif action == "struggle":
                print(f"    Chose:  Struggle (no PP remaining)")
            elif action == "charge_release":
                move_name = _fmt_move(next(
                    (r["move_name"] for r in turn_rows
                     if r["fk_trainer_id"] == trainer_id and r["action_type"] == "charge_release"),
                    None
                ))
                print(f"    Chose:  {move_name} (release)")
            elif action in ("recharge", "skipped"):
                print(f"    Chose:  {action} (forced)")
            else:
                print(f"    Chose:  {action}")

        # --- What happened ---
        print(f"\n  What happened:")
        for row in turn_rows:
            tname = trainer_name.get(row["fk_trainer_id"], str(row["fk_trainer_id"]))
            print(f"    {tname}: {_format_action(row)}")

        # Update fainted and active trackers for next turn
        for row in turn_rows:
            if row["target_fainted"] and row["fk_target_pokemon_id"]:
                for tid, roster in teams.items():
                    if any(p["id"] == row["fk_target_pokemon_id"] for p in roster):
                        fainted[tid].add(row["fk_target_pokemon_id"])
            if row["action_type"] in ("swap", "forced_swap") and row["fk_target_pokemon_id"]:
                active[row["fk_trainer_id"]] = row["fk_target_pokemon_id"]

    print(f"\n{'=' * 65}")
    if battle["is_draw"]:
        print(f"RESULT: Draw after {battle['total_turns']} turns")
    else:
        winner = t1_name if battle["winner_trainer_id"] == t1_id else t2_name
        print(f"RESULT: {winner} wins in {battle['total_turns']} turns")
    print("=" * 65)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/replay.py <battle_id>")
        sys.exit(1)
    battle_id = int(sys.argv[1])
    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"battle_{battle_id}.txt")
    with open(out_path, "w") as f:
        sys.stdout = f
        print_replay(battle_id)
    sys.stdout = sys.__stdout__
    print(f"Written to {out_path}")

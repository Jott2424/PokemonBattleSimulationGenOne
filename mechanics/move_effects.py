"""
Move effect handlers for all Gen 1 effect types.

Each handler has the signature:
    handler(effect_data, attacker, defender, battle, move, rng) -> List[TurnEvent]

Handlers are responsible for recording their own events via battle._record_event().
Damage calculation and accuracy checks are handled by the battle engine BEFORE
calling these handlers for standard damaging moves.

For special moves (bide, counter, metronome, etc.) the handler takes full control
of the turn and the battle engine defers to it entirely.
"""
import random
from typing import TYPE_CHECKING, Optional

from mechanics.status import apply_status, is_frozen, thaw

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move
    from battle.battle import Battle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_secondary_effects(effect_data: dict, attacker: "Trainer", defender: "Trainer",
                               damage: int, hit: bool, move: "Move", battle: "Battle", rng: random.Random):
    """Apply optional secondary effects after a damaging move lands."""
    if not hit or damage == 0:
        return

    poke = defender.active

    # Status secondary
    status = effect_data.get("secondary_status")
    if status and rng.random() < effect_data.get("secondary_chance", 0):
        if not poke.has_substitute:
            apply_status(poke, status, rng)

    # Confusion secondary
    if effect_data.get("secondary_confuse") and rng.random() < effect_data.get("secondary_chance", 0):
        if not poke.has_substitute and not poke.confused:
            poke.confused = True
            poke.confusion_turns_remaining = rng.randint(1, 4)

    # Flinch secondary
    flinch_chance = effect_data.get("flinch_chance", 0)
    if flinch_chance and rng.random() < flinch_chance:
        if not poke.has_substitute:
            poke.flinched = True

    # Stat secondary (e.g., acid, aurora-beam, psychic)
    stat_sec = effect_data.get("stat_secondary")
    if stat_sec and rng.random() < effect_data.get("secondary_chance", 0):
        target_poke = defender.active if stat_sec["delta"] < 0 else attacker.active
        # Mist blocks stat reductions on defender
        if stat_sec["delta"] < 0 and defender.active.mist_active:
            pass
        else:
            target_poke.apply_stage(stat_sec["stat"], stat_sec["delta"])

    # Fire-type thaws frozen target
    if move.type_name.lower() == "fire" and is_frozen(poke):
        thaw(poke)


# ---------------------------------------------------------------------------
# Pure damage (no special primary effect — secondaries from effect_data)
# ---------------------------------------------------------------------------

def handle_pure_damage(effect_data, attacker, defender, battle, move, rng, damage, hit):
    _apply_secondary_effects(effect_data, attacker, defender, damage, hit, move, battle, rng)


# ---------------------------------------------------------------------------
# High critical hit ratio (uses Gen 1 Speed-based formula)
# Actual damage and crit flag computed by damage.py using base_speed / 64
# ---------------------------------------------------------------------------

def handle_high_crit(effect_data, attacker, defender, battle, move, rng, damage, hit):
    _apply_secondary_effects(effect_data, attacker, defender, damage, hit, move, battle, rng)


# ---------------------------------------------------------------------------
# Drain (Absorb, Mega Drain, Leech Life)
# ---------------------------------------------------------------------------

def handle_drain(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if hit and damage > 0:
        heal = max(1, int(damage * effect_data.get("fraction", 0.5)))
        attacker.active.heal(heal)


# ---------------------------------------------------------------------------
# Dream Eater — drains only if target is sleeping
# ---------------------------------------------------------------------------

def handle_drain_sleep(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if hit and damage > 0 and defender.active.status == "sleep":
        heal = max(1, int(damage * effect_data.get("fraction", 0.5)))
        attacker.active.heal(heal)


# ---------------------------------------------------------------------------
# Recoil (Take Down, Double-Edge, Submission)
# ---------------------------------------------------------------------------

def handle_recoil(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if hit and damage > 0:
        recoil = max(1, int(damage * effect_data.get("recoil_fraction", 0.25)))
        attacker.active.take_damage(recoil)


# ---------------------------------------------------------------------------
# Recoil crash on miss (High Jump Kick, Jump Kick)
# Gen 1: user takes 1 HP if move misses
# ---------------------------------------------------------------------------

def handle_recoil_crash(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if not hit:
        crash = effect_data.get("crash_hp", 1)
        attacker.active.take_damage(crash)
    # No secondary effects


# ---------------------------------------------------------------------------
# Self-Destruct / Explosion
# Halves defender's Defense in damage calc (handled in damage.py via flag)
# User HP set to 0 after damage is dealt
# ---------------------------------------------------------------------------

def handle_self_destruct(effect_data, attacker, defender, battle, move, rng, damage, hit):
    attacker.active.hp = 0  # User faints regardless of outcome


# ---------------------------------------------------------------------------
# Fixed damage (SonicBoom=20, Dragon Rage=40)
# ---------------------------------------------------------------------------

def handle_fixed_damage(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # Damage already applied by caller using fixed_value from effect_data


# ---------------------------------------------------------------------------
# Level damage (Seismic Toss, Night Shade) — damage = user's level
# ---------------------------------------------------------------------------

def handle_level_damage(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # Damage already calculated and applied by caller


# ---------------------------------------------------------------------------
# Psywave — random damage 50-150% of user's level
# ---------------------------------------------------------------------------

def handle_psywave(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # Damage already calculated by caller


# ---------------------------------------------------------------------------
# Super Fang — always deals half of target's current HP
# ---------------------------------------------------------------------------

def handle_super_fang(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # Damage already calculated by caller


# ---------------------------------------------------------------------------
# Swift — always hits; accuracy check skipped by caller
# ---------------------------------------------------------------------------

def handle_swift(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # No secondary effects


# ---------------------------------------------------------------------------
# Earthquake — doubles power if defender is underground (Dig)
# ---------------------------------------------------------------------------

def handle_earthquake(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # Power doubling handled in damage calc by caller; no secondaries


# ---------------------------------------------------------------------------
# Multi-hit (2-5 or fixed 2)
# Caller handles hit loop; this records nothing extra
# ---------------------------------------------------------------------------

def handle_multi_hit(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # Handled by caller


# ---------------------------------------------------------------------------
# Twineedle — always 2 hits, poison chance per hit
# ---------------------------------------------------------------------------

def handle_twineedle(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if hit and damage > 0:
        poison_chance = effect_data.get("poison_chance", 0.20)
        if not defender.active.has_substitute and rng.random() < poison_chance:
            apply_status(defender.active, "poison", rng)


# ---------------------------------------------------------------------------
# OHKO (Fissure, Horn Drill, Guillotine) — flat 30% accuracy, instant KO
# Caller handles accuracy; this sets target HP to 0
# ---------------------------------------------------------------------------

def handle_ohko(effect_data, attacker, defender, battle, move, rng, damage, hit):
    pass  # KO applied by caller


# ---------------------------------------------------------------------------
# Two-turn moves (Fly, Dig, Solar Beam, Skull Bash, etc.)
# On turn 1: set charging state. On turn 2: release.
# ---------------------------------------------------------------------------

def handle_two_turn(effect_data, attacker, defender, battle, move, rng, damage, hit):
    poke = attacker.active
    if not poke.is_charging:
        # Begin charging
        poke.is_charging = True
        poke.charging_move_id = move.id
        poke.charging_move_name = move.name
        if effect_data.get("invulnerable"):
            poke.invulnerable = True
            poke.invulnerable_type = effect_data.get("invulnerable_type")
    else:
        # Release
        poke.is_charging = False
        poke.invulnerable = False
        poke.invulnerable_type = None
        poke.charging_move_id = None
        poke.charging_move_name = None
        _apply_secondary_effects(effect_data, attacker, defender, damage, hit, move, battle, rng)


# ---------------------------------------------------------------------------
# Binding moves (Wrap, Bind, Clamp, Fire Spin)
# ---------------------------------------------------------------------------

def handle_binding(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if hit and damage > 0:
        target = defender.active
        if not target.is_bound:
            target.is_bound = True
            target.bound_turns_remaining = rng.randint(2, 5)
        # Fire-type binding thaws frozen target
        if move.type_name.lower() == "fire" and is_frozen(target):
            thaw(target)


# ---------------------------------------------------------------------------
# Bide — endures 2 turns then releases double absorbed damage
# ---------------------------------------------------------------------------

def handle_bide(effect_data, attacker, defender, battle, move, rng):
    """Full control handler for Bide. Called instead of the standard attack flow."""
    poke = attacker.active
    if not poke.bide_active:
        poke.bide_active = True
        poke.bide_turns_remaining = 2
        poke.bide_damage_absorbed = 0
    elif poke.bide_turns_remaining > 0:
        poke.bide_turns_remaining -= 1
        if poke.bide_turns_remaining == 0:
            release = poke.bide_damage_absorbed * 2
            poke.bide_active = False
            poke.bide_damage_absorbed = 0
            if release > 0:
                defender.active.take_damage(release)


# ---------------------------------------------------------------------------
# Counter — deals double the last physical damage taken from opponent
# Only works if last hit was Normal or Fighting type
# ---------------------------------------------------------------------------

def handle_counter(effect_data, attacker, defender, battle, move, rng):
    """Full control handler for Counter."""
    poke = attacker.active
    if poke.last_damage_was_physical and poke.last_physical_damage_taken > 0:
        counter_damage = poke.last_physical_damage_taken * 2
        defender.active.take_damage(counter_damage)


# ---------------------------------------------------------------------------
# Thrash / Petal Dance — lock 2-3 turns then confuse self
# ---------------------------------------------------------------------------

def handle_thrash(effect_data, attacker, defender, battle, move, rng, damage, hit):
    poke = attacker.active
    if not poke.is_thrashing:
        turns = rng.randint(effect_data.get("min_turns", 2), effect_data.get("max_turns", 3))
        poke.is_thrashing = True
        poke.thrash_turns_remaining = turns
        poke.thrash_move_id = move.id
        poke.thrash_move_name = move.name
    else:
        poke.thrash_turns_remaining -= 1
        if poke.thrash_turns_remaining <= 0:
            poke.is_thrashing = False
            poke.thrash_move_id = None
            poke.thrash_move_name = None
            # Self-confuse at the end
            if not poke.confused:
                poke.confused = True
                poke.confusion_turns_remaining = rng.randint(1, 4)


# ---------------------------------------------------------------------------
# Rage — lock into Rage; Attack raises +1 each time hit
# ---------------------------------------------------------------------------

def handle_rage(effect_data, attacker, defender, battle, move, rng, damage, hit):
    poke = attacker.active
    if not poke.is_raging:
        poke.is_raging = True
        poke.rage_move_id = move.id
        poke.rage_move_name = move.name


# ---------------------------------------------------------------------------
# Hyper Beam — must recharge next turn (unless target fainted)
# ---------------------------------------------------------------------------

def handle_hyper_beam(effect_data, attacker, defender, battle, move, rng, damage, hit):
    if hit and damage > 0 and not defender.active.is_fainted:
        attacker.active.must_recharge = True


# ---------------------------------------------------------------------------
# Status infliction — non-volatile
# ---------------------------------------------------------------------------

def handle_status_sleep(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    if target.has_substitute:
        return
    apply_status(target, "sleep", rng)


def handle_status_paralyze(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    if target.has_substitute:
        return
    apply_status(target, "paralysis", rng)


def handle_status_poison(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    if target.has_substitute:
        return
    apply_status(target, "poison", rng)


def handle_status_toxic(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    if target.has_substitute:
        return
    if apply_status(target, "toxic", rng):
        target.toxic_counter = 1


def handle_status_confuse(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    if target.has_substitute:
        return
    if not target.confused:
        target.confused = True
        target.confusion_turns_remaining = rng.randint(1, 4)


def handle_rest(effect_data, attacker, defender, battle, move, rng):
    poke = attacker.active
    if poke.hp == poke.max_hp:
        return  # No effect if already full HP
    poke.status = None
    poke.sleep_turns_remaining = 0
    poke.toxic_counter = 0
    apply_status(poke, "sleep", rng)
    poke.sleep_turns_remaining = 2  # Override random sleep with fixed 2
    poke.heal(poke.max_hp)


# ---------------------------------------------------------------------------
# Stat changes
# ---------------------------------------------------------------------------

def handle_stat_change(effect_data, attacker, defender, battle, move, rng):
    target_trainer = attacker if effect_data.get("target") == "self" else defender
    poke = target_trainer.active
    delta = effect_data["delta"]
    stat = effect_data["stat"]
    # Mist blocks stat reductions on the defender
    if delta < 0 and poke.mist_active and target_trainer is defender:
        return
    poke.apply_stage(stat, delta)


# ---------------------------------------------------------------------------
# Heal half
# ---------------------------------------------------------------------------

def handle_heal_half(effect_data, attacker, defender, battle, move, rng):
    poke = attacker.active
    poke.heal(max(1, poke.max_hp // 2))


# ---------------------------------------------------------------------------
# Leech Seed
# ---------------------------------------------------------------------------

def handle_leech_seed(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    if target.has_substitute or target.is_seeded:
        return
    # Grass-types are immune to Leech Seed
    if any(t.lower() == "grass" for t in target.type_names):
        return
    target.is_seeded = True


# ---------------------------------------------------------------------------
# Substitute
# ---------------------------------------------------------------------------

def handle_substitute(effect_data, attacker, defender, battle, move, rng):
    poke = attacker.active
    if poke.has_substitute:
        return  # Already has one
    cost = max(1, poke.max_hp // 4)
    if poke.hp <= cost:
        return  # Not enough HP
    poke.take_damage(cost)
    poke.substitute_hp = cost


# ---------------------------------------------------------------------------
# Reflect / Light Screen — no turn timer in Gen 1; stays active until the
# trainer's active Pokemon switches out (cleared in Battle._do_swap).
# ---------------------------------------------------------------------------

def handle_reflect(effect_data, attacker, defender, battle, move, rng):
    battle.reflect_turns[attacker.id] = 1


def handle_light_screen(effect_data, attacker, defender, battle, move, rng):
    battle.light_screen_turns[attacker.id] = 1


# ---------------------------------------------------------------------------
# Haze — reset all stat stages for both active Pokemon
# ---------------------------------------------------------------------------

def handle_haze(effect_data, attacker, defender, battle, move, rng):
    for stat in attacker.active.stages:
        attacker.active.stages[stat] = 0
    for stat in defender.active.stages:
        defender.active.stages[stat] = 0


# ---------------------------------------------------------------------------
# Mist — block stat reductions for 5 turns
# ---------------------------------------------------------------------------

def handle_mist(effect_data, attacker, defender, battle, move, rng):
    poke = attacker.active
    poke.mist_active = True
    poke.mist_turns_remaining = 5


# ---------------------------------------------------------------------------
# Focus Energy — increases critical hit rate
# ---------------------------------------------------------------------------

def handle_focus_energy(effect_data, attacker, defender, battle, move, rng):
    attacker.active.focus_energy_active = True


# ---------------------------------------------------------------------------
# Disable — disables one of opponent's moves for 1-8 turns
# ---------------------------------------------------------------------------

def handle_disable(effect_data, attacker, defender, battle, move, rng):
    target = defender.active
    last_id = getattr(defender, "last_move_used_id", None)
    if last_id is None:
        return
    last_move = next((m for m in target.moves if m.id == last_id and m.has_pp), None)
    if last_move is None:
        return
    target.disabled_move_id = last_move.id
    target.disable_turns_remaining = rng.randint(1, 8)


# ---------------------------------------------------------------------------
# Mirror Move — uses the opponent's last move
# Full control: delegates back to battle engine dispatch
# ---------------------------------------------------------------------------

def handle_mirror_move(effect_data, attacker, defender, battle, move, rng):
    """Triggers the opponent's last used move. Returns the move name to execute, or None."""
    last_name = defender.last_move_used_name
    if last_name is None:
        return None
    return last_name  # Battle engine will dispatch this move


# ---------------------------------------------------------------------------
# Metronome — picks a random move and executes it
# Returns the move name to execute
# ---------------------------------------------------------------------------

def handle_metronome(effect_data, attacker, defender, battle, move, rng):
    from data.move_effects_map import METRONOME_POOL
    chosen_name = rng.choice(METRONOME_POOL)
    return chosen_name  # Battle engine will dispatch this move


# ---------------------------------------------------------------------------
# Mimic — temporarily copies one of the opponent's moves
# ---------------------------------------------------------------------------

def handle_mimic(effect_data, attacker, defender, battle, move, rng):
    import copy
    poke = attacker.active
    opp_moves = [m for m in defender.active.moves if m.name != "mimic"]
    if not opp_moves:
        return
    chosen = rng.choice(opp_moves)
    # Find which slot mimic is in
    for i, m in enumerate(poke.moves):
        if m.name == "mimic":
            copied = copy.copy(chosen)
            copied.pp_curr = 5  # Mimic gives 5 PP in Gen 1
            copied.pp_start = 5
            poke.mimic_slot = i
            poke.mimic_move = copied
            poke.moves[i] = copied
            break


# ---------------------------------------------------------------------------
# Transform — user copies the opponent's form
# ---------------------------------------------------------------------------

def handle_transform(effect_data, attacker, defender, battle, move, rng):
    import copy
    poke = attacker.active
    opp = defender.active
    if poke.is_transformed:
        return
    # Save originals for switch-out restoration
    poke.pre_transform_stats = {
        "attack": poke.attack, "defense": poke.defense,
        "special": poke.special, "speed": poke.speed,
    }
    poke.pre_transform_moves = poke.moves[:]
    poke.pre_transform_types = opp.type_names[:]
    poke.pre_transform_type_ids = opp.type_ids[:]
    # Copy stats (not HP), types, moves (5 PP each)
    poke.attack = opp.attack
    poke.defense = opp.defense
    poke.special = opp.special
    poke.speed = opp.speed
    poke.type_ids = opp.type_ids[:]
    poke.type_names = opp.type_names[:]
    poke.stages = {k: v for k, v in opp.stages.items()}
    new_moves = []
    for m in opp.moves:
        mc = copy.copy(m)
        mc.pp_start = 5
        mc.pp_curr = 5
        new_moves.append(mc)
    poke.moves = new_moves
    poke.is_transformed = True


# ---------------------------------------------------------------------------
# Conversion — change user's type to type of first move
# ---------------------------------------------------------------------------

def handle_conversion(effect_data, attacker, defender, battle, move, rng):
    poke = attacker.active
    if not poke.moves:
        return
    first_move = poke.moves[0]
    poke.type_ids = [first_move.type_id]
    poke.type_names = [first_move.type_name]


# ---------------------------------------------------------------------------
# Splash / No-op
# ---------------------------------------------------------------------------

def handle_splash(effect_data, attacker, defender, battle, move, rng):
    pass  # Nothing happens


def handle_no_trainer_effect(effect_data, attacker, defender, battle, move, rng):
    pass  # Roar, Whirlwind, Teleport all fail in trainer battles


# ---------------------------------------------------------------------------
# Dispatch table — maps effect keys to handler functions
# ---------------------------------------------------------------------------

EFFECT_HANDLERS = {
    "pure_damage":       handle_pure_damage,
    "high_crit":         handle_high_crit,
    "drain":             handle_drain,
    "drain_sleep":       handle_drain_sleep,
    "recoil":            handle_recoil,
    "recoil_crash":      handle_recoil_crash,
    "self_destruct":     handle_self_destruct,
    "fixed_damage":      handle_fixed_damage,
    "level_damage":      handle_level_damage,
    "psywave":           handle_psywave,
    "super_fang":        handle_super_fang,
    "swift":             handle_swift,
    "earthquake":        handle_earthquake,
    "multi_hit":         handle_multi_hit,
    "twineedle":         handle_twineedle,
    "ohko":              handle_ohko,
    "two_turn":          handle_two_turn,
    "binding":           handle_binding,
    "thrash":            handle_thrash,
    "rage":              handle_rage,
    "hyper_beam":        handle_hyper_beam,
    "status_sleep":      handle_status_sleep,
    "status_paralyze":   handle_status_paralyze,
    "status_poison":     handle_status_poison,
    "status_toxic":      handle_status_toxic,
    "status_confuse":    handle_status_confuse,
    "rest":              handle_rest,
    "stat_change":       handle_stat_change,
    "heal_half":         handle_heal_half,
    "leech_seed":        handle_leech_seed,
    "substitute":        handle_substitute,
    "reflect":           handle_reflect,
    "light_screen":      handle_light_screen,
    "haze":              handle_haze,
    "mist":              handle_mist,
    "focus_energy":      handle_focus_energy,
    "disable":           handle_disable,
    "bide":              handle_bide,
    "counter":           handle_counter,
    "mirror_move":       handle_mirror_move,
    "metronome":         handle_metronome,
    "mimic":             handle_mimic,
    "transform":         handle_transform,
    "conversion":        handle_conversion,
    "splash":            handle_splash,
    "no_trainer_effect": handle_no_trainer_effect,
}

# Effects that are non-damaging (battle engine skips damage calc for these)
NON_DAMAGING_EFFECTS = {
    "status_sleep", "status_paralyze", "status_poison", "status_toxic",
    "status_confuse", "rest", "stat_change", "heal_half", "leech_seed",
    "substitute", "reflect", "light_screen", "haze", "mist", "focus_energy",
    "disable", "bide", "counter", "mirror_move", "metronome", "mimic",
    "transform", "conversion", "splash", "no_trainer_effect",
}

# Effects that take full control of the turn (no standard accuracy/damage flow)
FULL_CONTROL_EFFECTS = {
    "bide", "counter", "mirror_move", "metronome",
    "splash", "no_trainer_effect", "two_turn",
}

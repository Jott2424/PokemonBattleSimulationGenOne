"""
Gen 1 damage calculation.

Formula: ((2*L/5 + 2) * Power * Atk / Def) / 50 + 2
- Stat stages applied to Atk and Def (critical hits use raw un-staged stats).
- Burn halves physical Attack (on non-crit only).
- Type effectiveness applied as a multiplier.
- Random roll: damage * randint(217, 255) / 255.

Critical hit rates:
  Normal moves:    flat 1/16 (6.25%)
  High-crit moves: attacker's base_speed / 64, capped at 1.0
                   (Gen 1 Speed-based formula; user approved for high-crit moves)
"""
import random
from typing import Dict, Tuple

from models.move import Move
from models.pokemon import Pokemon


_NORMAL_CRIT_CHANCE = 1 / 16


def _crit_chance(attacker: Pokemon, high_crit: bool) -> float:
    if high_crit:
        if attacker.focus_energy_active:
            # Focus Energy in Gen 1 intended to double crit rate for high-crit moves
            return min(1.0, (attacker.base_speed / 64) * 2)
        return min(1.0, attacker.base_speed / 64)
    else:
        if attacker.focus_energy_active:
            return min(1.0, _NORMAL_CRIT_CHANCE * 2)
        return _NORMAL_CRIT_CHANCE


def calc_damage(
    attacker: Pokemon,
    defender: Pokemon,
    move: Move,
    type_chart: Dict[Tuple[int, int], float],
    rng: random.Random,
    high_crit: bool = False,
    halve_defense: bool = False,  # for Explosion/Self-Destruct
) -> Tuple[int, bool]:
    """
    Returns (damage, is_critical).
    Returns (0, False) for non-damaging moves.
    """
    if not move.is_damaging or move.power is None:
        return 0, False

    is_crit = rng.random() < _crit_chance(attacker, high_crit)

    if is_crit:
        atk = attacker.attack if move.damage_category == "physical" else attacker.special
        def_ = defender.defense if move.damage_category == "physical" else defender.special
    else:
        atk = attacker.effective_attack() if move.damage_category == "physical" else attacker.effective_special()
        def_ = defender.effective_defense() if move.damage_category == "physical" else defender.effective_special()

    if halve_defense and move.damage_category == "physical":
        def_ = max(1, def_ // 2)

    # Reflect halves physical damage (if attacker's screen is not active, check defender's)
    # (Screen check is applied by the battle engine before calling calc_damage)

    power = move.power
    level = attacker.level
    base = ((2 * level // 5 + 2) * power * atk // def_) // 50 + 2

    effectiveness = _get_effectiveness(move.type_id, defender.type_ids, type_chart)
    damage = int(base * effectiveness)

    if damage > 1:
        roll = rng.randint(217, 255)
        damage = damage * roll // 255

    damage = max(1, damage)
    return damage, is_crit


def calc_fixed_damage(fixed_value: int) -> Tuple[int, bool]:
    return fixed_value, False


def calc_level_damage(attacker: Pokemon) -> Tuple[int, bool]:
    return attacker.level, False


def calc_psywave_damage(attacker: Pokemon, rng: random.Random) -> Tuple[int, bool]:
    # Random damage: 50% to 150% of user's level (integer range)
    damage = rng.randint(attacker.level // 2, attacker.level + attacker.level // 2)
    return max(1, damage), False


def calc_super_fang_damage(defender: Pokemon) -> Tuple[int, bool]:
    return max(1, defender.hp // 2), False


def calc_ohko_damage(defender: Pokemon) -> Tuple[int, bool]:
    return defender.hp, False


def calc_confusion_damage(attacker: Pokemon, rng: random.Random) -> int:
    """Confusion self-hit: 40-power typeless physical using attacker's own Attack/Defense."""
    level = attacker.level
    atk = attacker.effective_attack()
    def_ = attacker.effective_defense()
    base = ((2 * level // 5 + 2) * 40 * atk // def_) // 50 + 2
    if base > 1:
        roll = rng.randint(217, 255)
        base = base * roll // 255
    return max(1, base)


def _get_effectiveness(move_type_id: int, defender_type_ids: list, type_chart: Dict) -> float:
    multiplier = 1.0
    for def_type_id in defender_type_ids:
        multiplier *= type_chart.get((move_type_id, def_type_id), 1.0)
    return multiplier


def check_accuracy(move: Move, attacker: Pokemon, defender: Pokemon, rng: random.Random) -> bool:
    """Returns True if the move hits. Respects stat stages for accuracy/evasion."""
    if move.accuracy is None:
        return True

    from models.pokemon import _STAGE_MULTIPLIERS
    combined = max(-6, min(6, attacker.stages["accuracy"] - defender.stages["evasion"]))
    stage_mult = _STAGE_MULTIPLIERS[combined + 6]
    return rng.random() < (move.accuracy / 100) * stage_mult

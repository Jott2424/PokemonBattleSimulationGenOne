"""
Stat stage modifiers for Gen 1.

Stages range from -6 to +6. The multiplier table is already embedded in
Pokemon.effective_*() methods; this module handles application logic and
resolves which stat a move targets.
"""
from models.pokemon import Pokemon


# Maps move effect codes to (stat, delta) — extend as new moves are added
_MOVE_EFFECT_MAP = {
    "raise_attack_1":    ("attack",   +1),
    "raise_attack_2":    ("attack",   +2),
    "lower_attack_1":    ("attack",   -1),
    "lower_attack_2":    ("attack",   -2),
    "raise_defense_1":   ("defense",  +1),
    "raise_defense_2":   ("defense",  +2),
    "lower_defense_1":   ("defense",  -1),
    "lower_defense_2":   ("defense",  -2),
    "raise_special_1":   ("special",  +1),
    "raise_special_2":   ("special",  +2),
    "lower_special_1":   ("special",  -1),
    "lower_special_2":   ("special",  -2),
    "raise_speed_1":     ("speed",    +1),
    "raise_speed_2":     ("speed",    +2),
    "lower_speed_1":     ("speed",    -1),
    "lower_speed_2":     ("speed",    -2),
    "raise_accuracy_1":  ("accuracy", +1),
    "lower_accuracy_1":  ("accuracy", -1),
    "lower_evasion_1":   ("evasion",  -1),
    "raise_evasion_1":   ("evasion",  +1),
}


def apply_stage_change(pokemon: Pokemon, stat: str, delta: int) -> int:
    """
    Apply a stage change to a stat. Returns the actual change applied
    (0 if already at the cap in that direction).
    """
    old = pokemon.stages[stat]
    new = max(-6, min(6, old + delta))
    pokemon.stages[stat] = new
    return new - old


def apply_move_effect(effect_code: str, target: Pokemon) -> int:
    """
    Apply a named move effect to target. Returns actual stage delta applied.
    Raises KeyError if effect_code is not recognized.
    """
    stat, delta = _MOVE_EFFECT_MAP[effect_code]
    return apply_stage_change(target, stat, delta)


def stage_is_maxed(pokemon: Pokemon, stat: str, direction: int) -> bool:
    """True if the stat stage is already at its cap in the given direction (+1 or -1)."""
    stage = pokemon.stages[stat]
    return (direction > 0 and stage >= 6) or (direction < 0 and stage <= -6)

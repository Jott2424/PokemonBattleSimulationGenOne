"""
Gen 1 status condition rules (no glitches).

Burn   — halves Attack (applied in damage calc), drains 1/16 max HP per turn.
Freeze — Pokemon cannot move. Thaws only via a move effect (e.g. Fire-type hit).
          Natural thawing does NOT occur (intentional Gen 1 design).
Paralysis — 25% chance to fully skip move each turn; Speed quartered (in effective_speed).
Sleep  — Cannot move. Wakes after 1-7 turns chosen at the time of application.
Poison — Drains 1/16 max HP per turn.

Rules:
- A Pokemon can only have one non-volatile status at a time.
- Fainted Pokemon cannot gain a status.
"""
import random
from models.pokemon import Pokemon


def apply_status(pokemon: Pokemon, status: str, rng: random.Random) -> bool:
    """
    Attempt to apply a status condition.
    Returns True if successfully applied, False if blocked (already has a status).
    """
    if pokemon.status is not None:
        return False
    if pokemon.is_fainted:
        return False

    pokemon.status = status
    if status == "sleep":
        pokemon.sleep_turns_remaining = rng.randint(1, 7)
    return True


def tick_end_of_turn(pokemon: Pokemon) -> int:
    """
    Apply end-of-turn status damage (burn, poison).
    Returns the HP drained (0 if none).
    """
    if pokemon.is_fainted:
        return 0
    if pokemon.status in ("burn", "poison"):
        drain = max(1, pokemon.max_hp // 16)
        pokemon.take_damage(drain)
        return drain
    return 0


def check_can_move(pokemon: Pokemon, rng: random.Random) -> bool:
    """
    Returns True if the Pokemon is able to execute a move this turn.
    Handles sleep countdown and paralysis skip check.
    Does NOT handle freeze (handled separately — frozen Pokemon cannot choose moves).
    """
    if pokemon.status == "sleep":
        if pokemon.sleep_turns_remaining > 0:
            pokemon.sleep_turns_remaining -= 1
            return False
        else:
            pokemon.status = None  # Wake up
            return True

    if pokemon.status == "paralysis":
        if rng.random() < 0.25:
            return False  # Fully paralyzed this turn

    return True


def is_frozen(pokemon: Pokemon) -> bool:
    return pokemon.status == "freeze"


def thaw(pokemon: Pokemon):
    """Remove freeze. Called when a fire-type move hits the frozen Pokemon."""
    if pokemon.status == "freeze":
        pokemon.status = None

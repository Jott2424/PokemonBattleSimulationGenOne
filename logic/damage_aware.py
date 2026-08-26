"""
Profile: damage_aware
Never voluntarily swaps. Picks the move with the highest ESTIMATED expected
damage against the opponent's active Pokemon — not just the best type
multiplier (that's all type_aware does). Accounts for the move's power, the
type-effectiveness multiplier, the attacker's actual Attack/Special stat vs.
the defender's Defense/Special (with stat stages applied, via the same
effective_attack()/effective_special()/effective_defense() the real damage
calc uses), and accuracy.

This fixes type_aware's biggest blind spot: it would happily pick a weak,
low-power super-effective move over a devastating neutral one, which no
reasonable player would do.

Non-damaging moves score 0 — this profile makes no attempt to value status
moves strategically. Ties (including "everything scores 0", e.g. every
damaging move is fully resisted/immune) are broken randomly among the
highest-scoring usable moves.
"""
import random
from typing import TYPE_CHECKING

from logic.base_profile import BaseProfile

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move


def expected_damage(attacker, defender, move, type_chart) -> float:
    """Deterministic expected-damage estimate (no crit/random-roll variance):
    the same base formula the real damage calc uses, scaled by type
    effectiveness and accuracy. Not used for the actual damage roll — only
    for a profile's move/switch judgment."""
    if not move.is_damaging:
        return 0.0
    atk = attacker.effective_attack() if move.damage_category == "physical" else attacker.effective_special()
    def_ = defender.effective_defense() if move.damage_category == "physical" else defender.effective_special()
    def_ = max(1, def_)
    base = ((2 * attacker.level / 5 + 2) * move.power * atk / def_) / 50 + 2

    effectiveness = 1.0
    for def_type_id in defender.type_ids:
        effectiveness *= type_chart.get((move.type_id, def_type_id), 1.0)

    accuracy = (move.accuracy / 100) if move.accuracy is not None else 1.0
    return base * effectiveness * accuracy


class DamageAwareProfile(BaseProfile):

    def decide_action(self, trainer, opponent, type_chart, rng: random.Random) -> str:
        return "attack"

    def decide_move(self, trainer, opponent, type_chart, rng: random.Random):
        usable = trainer.active.usable_moves()
        scores = [expected_damage(trainer.active, opponent.active, m, type_chart) for m in usable]
        best_score = max(scores)
        best_moves = [m for m, s in zip(usable, scores) if s == best_score]
        return rng.choice(best_moves)

    def decide_swap(self, trainer, opponent, type_chart, rng: random.Random):
        # Should never be called for this profile, but provide a safe fallback
        return rng.choice(trainer.bench)


profile = DamageAwareProfile()

"""
Profile: smart
Builds on damage_aware's move selection (estimated expected damage, not just
type multiplier — see damage_aware.py) and adds real switching judgment:
type_aware and damage_aware both never voluntarily swap. This profile will,
if the matchup looks bad enough and the bench has something clearly better.

Danger and opportunity are both measured as (estimated damage / defender's
current HP) — a simple proxy for "how much of this Pokemon's health does
that hit represent," using the opponent's actual visible moves (nothing
hidden in this simulation) to estimate their best shot the same way
damage_aware estimates the trainer's own.

Switch only when: the opponent's best shot represents a serious chunk of the
current active's HP (DANGER_THRESHOLD) AND the current active can't bite back
proportionally hard, AND the best bench alternative's matchup margin clearly
beats staying in by more than SWITCH_MARGIN — avoids waffling over marginal
differences. decide_swap recomputes the same evaluation independently rather
than caching a choice from decide_action, since profile instances are shared
across every battle a worker runs and shouldn't carry mutable state between
calls.
"""
import random
from typing import TYPE_CHECKING

from logic.base_profile import BaseProfile
from logic.damage_aware import expected_damage

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move


DANGER_THRESHOLD = 0.5   # opponent's best hit represents >50% of my active's HP
SWITCH_MARGIN = 0.15     # how much better the bench option's margin must be to bother switching


def _best_expected_damage(attacker, defender, type_chart) -> float:
    usable = attacker.usable_moves()
    if not usable:
        return 0.0
    return max(expected_damage(attacker, defender, m, type_chart) for m in usable)


def _matchup_margin(mine, theirs, type_chart) -> float:
    """(my best bite on them, relative to their HP) minus (their best bite on
    me, relative to my HP) — positive means I favor this matchup."""
    my_bite = _best_expected_damage(mine, theirs, type_chart) / max(1, theirs.hp)
    their_bite = _best_expected_damage(theirs, mine, type_chart) / max(1, mine.hp)
    return my_bite - their_bite


def _best_bench_option(trainer, opp_active, type_chart):
    """Returns (best_bench_pokemon, its_margin) or (None, -inf) if bench is empty."""
    best_poke, best_margin = None, float("-inf")
    for candidate in trainer.bench:
        margin = _matchup_margin(candidate, opp_active, type_chart)
        if margin > best_margin:
            best_margin = margin
            best_poke = candidate
    return best_poke, best_margin


class SmartProfile(BaseProfile):

    def decide_action(self, trainer, opponent, type_chart, rng: random.Random) -> str:
        if not trainer.bench:
            return "attack"

        my_active, opp_active = trainer.active, opponent.active
        danger = _best_expected_damage(opp_active, my_active, type_chart) / max(1, my_active.hp)
        if danger < DANGER_THRESHOLD:
            return "attack"

        current_margin = _matchup_margin(my_active, opp_active, type_chart)
        _, best_bench_margin = _best_bench_option(trainer, opp_active, type_chart)
        if best_bench_margin > current_margin + SWITCH_MARGIN:
            return "swap"
        return "attack"

    def decide_move(self, trainer, opponent, type_chart, rng: random.Random):
        usable = trainer.active.usable_moves()
        scores = [expected_damage(trainer.active, opponent.active, m, type_chart) for m in usable]
        best_score = max(scores)
        best_moves = [m for m, s in zip(usable, scores) if s == best_score]
        return rng.choice(best_moves)

    def decide_swap(self, trainer, opponent, type_chart, rng: random.Random):
        # Recomputes the same evaluation decide_action used to trigger this
        # switch, rather than caching a choice between the two calls — profile
        # instances are shared across every battle a worker runs, so no
        # mutable state gets carried between decide_action and decide_swap.
        best_poke, _ = _best_bench_option(trainer, opponent.active, type_chart)
        return best_poke if best_poke is not None else rng.choice(trainer.bench)


profile = SmartProfile()

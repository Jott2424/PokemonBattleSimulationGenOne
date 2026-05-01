"""
Profile: type_aware
Never voluntarily swaps. Picks the move with the highest type effectiveness
multiplier against the opponent's active Pokemon. Ties broken randomly.
"""
import random
from typing import Dict, List, Tuple, TYPE_CHECKING

from logic.base_profile import BaseProfile

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move


class TypeAwareProfile(BaseProfile):

    def decide_action(self, trainer, opponent, rng: random.Random) -> str:
        return "attack"

    def decide_move(self, trainer, opponent, type_chart, rng: random.Random):
        usable = trainer.active.usable_moves()
        opp_type_ids = opponent.active.type_ids

        best_score = -1.0
        best_moves = []

        for move in usable:
            if not move.is_damaging:
                score = 1.0  # Status moves treated as neutral
            else:
                score = 1.0
                for def_type_id in opp_type_ids:
                    score *= type_chart.get((move.type_id, def_type_id), 1.0)

            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return rng.choice(best_moves)

    def decide_swap(self, trainer, opponent, rng: random.Random):
        return rng.choice(trainer.bench)


profile = TypeAwareProfile()

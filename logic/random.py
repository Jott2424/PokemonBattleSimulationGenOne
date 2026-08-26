"""
Profile: random
All decisions are made uniformly at random.
- Action: random choice between attack and swap (swap only if bench is non-empty)
- Move: random usable move
- Swap target: random conscious bench Pokemon
"""
import random
from typing import Dict, Tuple, TYPE_CHECKING

from logic.base_profile import BaseProfile

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move


class RandomProfile(BaseProfile):

    def decide_action(self, trainer, opponent, type_chart, rng: random.Random) -> str:
        if trainer.bench:
            return rng.choice(["attack", "swap"])
        return "attack"

    def decide_move(self, trainer, opponent, type_chart, rng: random.Random):
        return rng.choice(trainer.active.usable_moves())

    def decide_swap(self, trainer, opponent, type_chart, rng: random.Random):
        return rng.choice(trainer.bench)


profile = RandomProfile()

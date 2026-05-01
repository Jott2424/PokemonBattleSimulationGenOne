"""
Profile: no_swap
Never voluntarily swaps the active Pokemon. Chooses a random usable move each turn.
The trainer will still be forced to swap when the active Pokemon faints
(that is handled by the battle engine, not this profile).
"""
import random
from typing import Dict, Tuple, TYPE_CHECKING

from logic.base_profile import BaseProfile

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move


class NoSwapProfile(BaseProfile):

    def decide_action(self, trainer, opponent, rng: random.Random) -> str:
        return "attack"

    def decide_move(self, trainer, opponent, type_chart, rng: random.Random):
        return rng.choice(trainer.active.usable_moves())

    def decide_swap(self, trainer, opponent, rng: random.Random):
        # Should never be called for this profile, but provide a safe fallback
        return rng.choice(trainer.bench)


profile = NoSwapProfile()

"""
Abstract base class for trainer decision logic profiles.

To create a new profile, add a Python file in this directory that:
1. Imports and subclasses BaseProfile
2. Defines a module-level instance named `profile`

The orchestrator loads profiles dynamically:
    import importlib
    mod = importlib.import_module(f"logic.{profile_name}")
    profile = mod.profile
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import random

if TYPE_CHECKING:
    from models.trainer import Trainer
    from models.pokemon import Pokemon
    from models.move import Move


class BaseProfile(ABC):

    @abstractmethod
    def decide_action(
        self,
        trainer: "Trainer",
        opponent: "Trainer",
        type_chart: Dict[Tuple[int, int], float],
        rng: random.Random,
    ) -> str:
        """
        Returns 'attack' or 'swap'.
        Called at the start of each turn before moves are resolved.
        """

    @abstractmethod
    def decide_move(
        self,
        trainer: "Trainer",
        opponent: "Trainer",
        type_chart: Dict[Tuple[int, int], float],
        rng: random.Random,
    ) -> "Move":
        """
        Returns the Move the trainer will use this turn.
        Only called when decide_action returned 'attack'.
        Guaranteed: trainer.active.usable_moves() is non-empty when this is called.
        """

    @abstractmethod
    def decide_swap(
        self,
        trainer: "Trainer",
        opponent: "Trainer",
        type_chart: Dict[Tuple[int, int], float],
        rng: random.Random,
    ) -> "Pokemon":
        """
        Returns the Pokemon to swap in from the bench.
        Only called when decide_action returned 'swap' and bench is non-empty.
        """

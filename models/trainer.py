from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from models.pokemon import Pokemon

if TYPE_CHECKING:
    from logic.base_profile import BaseProfile


@dataclass
class Trainer:
    id: int
    name: str
    team: List[Pokemon]
    logic_profile: "BaseProfile"

    # Active index into team; always points to a conscious Pokemon
    _active_index: int = field(default=0, repr=False)

    # Last-move tracking (for Mirror Move, Mimic, Counter)
    last_move_used_id: Optional[int] = field(default=None)
    last_move_used_name: Optional[str] = field(default=None)

    def __post_init__(self):
        # Ensure starting Pokemon is conscious (should always be true at battle start)
        self._active_index = 0

    @property
    def active(self) -> Pokemon:
        return self.team[self._active_index]

    @property
    def bench(self) -> List[Pokemon]:
        return [p for i, p in enumerate(self.team) if i != self._active_index and p.is_conscious]

    @property
    def all_fainted(self) -> bool:
        return all(p.is_fainted for p in self.team)

    @property
    def conscious_pokemon(self) -> List[Pokemon]:
        return [p for p in self.team if p.is_conscious]

    def force_next_pokemon(self):
        """Switch to the next conscious Pokemon after current one faints."""
        for i, p in enumerate(self.team):
            if p.is_conscious:
                self._active_index = i
                return
        # No conscious Pokemon — caller should check all_fainted first

    def swap_to(self, pokemon: Pokemon):
        self.active.reset_volatile_conditions()
        idx = self.team.index(pokemon)
        self._active_index = idx

    def __repr__(self):
        return f"Trainer({self.name}, active={self.active.name}, conscious={len(self.conscious_pokemon)}/{len(self.team)})"

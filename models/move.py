from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Move:
    id: int
    name: str
    type_id: int
    type_name: str
    damage_category: str       # 'physical', 'special', or 'status'
    power: Optional[int]       # None for status moves
    accuracy: Optional[int]    # None for always-hit / status moves
    pp_start: int
    pp_curr: int = field(init=False)

    def __post_init__(self):
        self.pp_curr = self.pp_start

    @property
    def has_pp(self) -> bool:
        return self.pp_curr > 0

    @property
    def is_damaging(self) -> bool:
        return self.damage_category in ("physical", "special") and self.power is not None

    def use(self):
        if self.pp_curr <= 0:
            raise ValueError(f"Move '{self.name}' has no PP remaining.")
        self.pp_curr -= 1

    def __repr__(self):
        return f"Move({self.name}, pp={self.pp_curr}/{self.pp_start})"

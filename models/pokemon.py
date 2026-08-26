from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from models.move import Move

# All trainer Pokemon use max DVs (15) per Gen 1 trainer behavior
_DV = 15

# Gen 1 stat stage multipliers indexed by stage (-6 to +6, offset by 6)
_STAGE_MULTIPLIERS = [
    2/8, 2/7, 2/6, 2/5, 2/4, 2/3,  # -6 to -1
    2/2,                              # 0
    3/2, 4/2, 5/2, 6/2, 7/2, 8/2,  # +1 to +6
]

StatusType = Optional[str]  # None | 'burn' | 'freeze' | 'paralysis' | 'sleep' | 'poison' | 'toxic'


@dataclass
class Pokemon:
    id: int
    name: str
    level: int
    type_ids: List[int]
    type_names: List[str]
    moves: List["Move"]
    party_order: int

    # Base stats (from DB)
    base_hp: int
    base_attack: int
    base_defense: int
    base_special: int
    base_speed: int

    # Computed stats (set in __post_init__)
    max_hp: int = field(init=False)
    hp: int = field(init=False)
    attack: int = field(init=False)
    defense: int = field(init=False)
    special: int = field(init=False)
    speed: int = field(init=False)

    # --- Non-volatile status (persists through switching) ---
    status: StatusType = field(default=None)
    sleep_turns_remaining: int = field(default=0)
    toxic_counter: int = field(default=0)  # escalates each turn when status='toxic'

    # Stat stages: each clamped to [-6, +6]
    stages: Dict[str, int] = field(default_factory=lambda: {
        "attack": 0, "defense": 0, "special": 0,
        "speed": 0, "accuracy": 0, "evasion": 0,
    })

    # --- Volatile conditions (reset on switch-out) ---

    # Confusion
    confused: bool = field(default=False)
    confusion_turns_remaining: int = field(default=0)

    # Flinch (checked at move execution, cleared each turn)
    flinched: bool = field(default=False)

    # Two-turn charge (fly, dig, solar beam, etc.)
    is_charging: bool = field(default=False)
    charging_move_id: Optional[int] = field(default=None)
    charging_move_name: Optional[str] = field(default=None)
    invulnerable: bool = field(default=False)
    invulnerable_type: Optional[str] = field(default=None)  # 'fly' or 'dig'

    # Binding (wrap, bind, fire spin, clamp)
    is_bound: bool = field(default=False)
    bound_turns_remaining: int = field(default=0)

    # Bide
    bide_active: bool = field(default=False)
    bide_turns_remaining: int = field(default=0)
    bide_damage_absorbed: int = field(default=0)

    # Thrash / Petal Dance lock
    is_thrashing: bool = field(default=False)
    thrash_turns_remaining: int = field(default=0)
    thrash_move_id: Optional[int] = field(default=None)
    thrash_move_name: Optional[str] = field(default=None)

    # Rage lock
    is_raging: bool = field(default=False)
    rage_move_id: Optional[int] = field(default=None)
    rage_move_name: Optional[str] = field(default=None)

    # Hyper Beam recharge
    must_recharge: bool = field(default=False)

    # Leech Seed
    is_seeded: bool = field(default=False)

    # Substitute
    substitute_hp: int = field(default=0)

    # Mist (blocks stat reductions)
    mist_active: bool = field(default=False)
    mist_turns_remaining: int = field(default=0)

    # Disable
    disabled_move_id: Optional[int] = field(default=None)
    disable_turns_remaining: int = field(default=0)

    # Focus Energy
    focus_energy_active: bool = field(default=False)

    # Transform
    is_transformed: bool = field(default=False)
    pre_transform_stats: Optional[Dict] = field(default=None)
    pre_transform_moves: Optional[List] = field(default=None)
    pre_transform_types: Optional[List] = field(default=None)
    pre_transform_type_ids: Optional[List] = field(default=None)

    # Mimic (which slot is currently mimicked and what move)
    mimic_slot: Optional[int] = field(default=None)
    mimic_move: Optional["Move"] = field(default=None)

    # For Counter: track last physical damage taken from opponent this turn
    last_physical_damage_taken: int = field(default=0)
    last_damage_was_physical: bool = field(default=False)

    # For Rage: track whether this pokemon was hit by any damaging move this turn
    was_hit_this_turn: bool = field(default=False)

    def __post_init__(self):
        self.max_hp = self._calc_hp()
        self.hp = self.max_hp
        self.attack = self._calc_stat(self.base_attack)
        self.defense = self._calc_stat(self.base_defense)
        self.special = self._calc_stat(self.base_special)
        self.speed = self._calc_stat(self.base_speed)

    # --- Stat formulas (Gen 1, DV=15) ---

    def _calc_stat(self, base: int) -> int:
        return ((base + _DV) * 2 * self.level // 100) + 5

    def _calc_hp(self) -> int:
        return ((self.base_hp + _DV) * 2 * self.level // 100) + self.level + 10

    # --- Stage-modified stats ---

    def effective_attack(self) -> int:
        val = max(1, int(self.attack * _STAGE_MULTIPLIERS[self.stages["attack"] + 6]))
        if self.status == "burn":
            val = max(1, val // 2)
        return val

    def effective_defense(self) -> int:
        return max(1, int(self.defense * _STAGE_MULTIPLIERS[self.stages["defense"] + 6]))

    def effective_special(self) -> int:
        return max(1, int(self.special * _STAGE_MULTIPLIERS[self.stages["special"] + 6]))

    def effective_speed(self) -> int:
        base = max(1, int(self.speed * _STAGE_MULTIPLIERS[self.stages["speed"] + 6]))
        if self.status == "paralysis":
            base = max(1, base // 4)
        return base

    # --- Battle helpers ---

    @property
    def is_fainted(self) -> bool:
        return self.hp <= 0

    @property
    def is_conscious(self) -> bool:
        return self.hp > 0

    @property
    def has_substitute(self) -> bool:
        return self.substitute_hp > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage, return actual amount dealt."""
        actual = min(amount, self.hp)
        self.hp = max(0, self.hp - amount)
        return actual

    def take_damage_to_substitute(self, amount: int) -> bool:
        """Deal damage to substitute. Returns True if substitute broke."""
        self.substitute_hp = max(0, self.substitute_hp - amount)
        return self.substitute_hp == 0

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def apply_stage(self, stat: str, delta: int) -> int:
        """Apply stage change, return actual delta applied."""
        old = self.stages[stat]
        self.stages[stat] = max(-6, min(6, old + delta))
        return self.stages[stat] - old

    def usable_moves(self) -> List["Move"]:
        return [
            m for m in self.moves
            if m.has_pp and m.id != self.disabled_move_id
        ]

    def reset_volatile_conditions(self):
        """Called when this Pokemon switches out."""
        self.confused = False
        self.confusion_turns_remaining = 0
        self.flinched = False
        self.is_charging = False
        self.charging_move_id = None
        self.charging_move_name = None
        self.invulnerable = False
        self.invulnerable_type = None
        self.is_bound = False
        self.bound_turns_remaining = 0
        self.bide_active = False
        self.bide_turns_remaining = 0
        self.bide_damage_absorbed = 0
        self.is_thrashing = False
        self.thrash_turns_remaining = 0
        self.thrash_move_id = None
        self.thrash_move_name = None
        self.is_raging = False
        self.rage_move_id = None
        self.rage_move_name = None
        self.must_recharge = False
        self.is_seeded = False
        self.substitute_hp = 0
        self.mist_active = False
        self.mist_turns_remaining = 0
        self.disabled_move_id = None
        self.disable_turns_remaining = 0
        self.focus_energy_active = False
        self.last_physical_damage_taken = 0
        self.last_damage_was_physical = False
        self.was_hit_this_turn = False
        # Toxic counter resets on switch in Gen 1
        if self.status == "toxic":
            self.toxic_counter = 0
        # Transform ends on switch
        if self.is_transformed and self.pre_transform_moves is not None:
            self.moves = self.pre_transform_moves
            self.attack = self.pre_transform_stats["attack"]
            self.defense = self.pre_transform_stats["defense"]
            self.special = self.pre_transform_stats["special"]
            self.speed = self.pre_transform_stats["speed"]
            self.type_ids = self.pre_transform_type_ids
            self.type_names = self.pre_transform_types
        self.is_transformed = False
        self.pre_transform_stats = None
        self.pre_transform_moves = None
        self.pre_transform_types = None
        self.pre_transform_type_ids = None
        self.mimic_slot = None
        self.mimic_move = None

    def __repr__(self):
        return f"Pokemon({self.name} Lv{self.level}, HP={self.hp}/{self.max_hp}, status={self.status})"

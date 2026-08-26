"""
Gen 1 battle engine — full move effect dispatch.

Turn flow:
1. Decrement screen/volatile counters (Reflect, Light Screen, Mist, Disable).
2. Reset per-turn volatiles (flinch, last_physical_damage_taken).
3. Each trainer decides action. Locked states (recharge, charge, thrash, rage, bide)
   override the decision.
4. Voluntary swaps execute first.
5. Attacks resolve in priority → Speed order (ties broken randomly).
6. For each attacker:
   a. Skip if fainted, frozen, or flinched.
   b. Check paralysis/sleep can-move (confusion self-hit rolled here).
   c. Accuracy check (skipped for swift, ohko uses flat 30%).
   d. Damage calculation (special types use their own calc functions).
   e. Damage applied to substitute or target HP.
   f. Dispatch secondary effect handler.
   g. Faint check → forced swap.
7. End-of-turn: burn/poison/toxic drain, leech seed drain, binding damage, status ticks.
8. Repeat until winner or max_turns reached.
"""
import copy
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from models.trainer import Trainer
from models.pokemon import Pokemon
from models.move import Move
from mechanics.damage import (
    calc_damage, calc_fixed_damage, calc_level_damage, calc_psywave_damage,
    calc_super_fang_damage, calc_ohko_damage, calc_confusion_damage, check_accuracy,
)
from mechanics.status import apply_status, tick_end_of_turn, check_can_move, is_frozen, thaw
from mechanics.move_effects import EFFECT_HANDLERS, NON_DAMAGING_EFFECTS, FULL_CONTROL_EFFECTS
from data.move_effects_map import MOVE_EFFECTS, METRONOME_POOL

_STRUGGLE_POWER = 50


def _ekey(name: str) -> str:
    """Normalize a DB move name (underscores) to an effects-map key (hyphens)."""
    return (name or "").replace("_", "-")


@dataclass
class TurnEvent:
    turn: int
    trainer_id: int
    pokemon_id: int
    action: str
    move_id: Optional[int] = None
    move_name: Optional[str] = None
    hit: bool = True
    is_critical: bool = False
    damage: int = 0
    target_trainer_id: Optional[int] = None
    target_pokemon_id: Optional[int] = None
    target_hp_before: Optional[int] = None
    target_hp_after: Optional[int] = None
    target_fainted: bool = False
    note: Optional[str] = None


@dataclass
class DecisionEvent:
    turn: int
    trainer_id: int
    active_pokemon_id: int
    active_hp: int
    active_status: Optional[str]
    atk_stage: int
    def_stage: int
    spe_stage: int
    spc_stage: int
    opp_pokemon_id: int
    opp_hp: int
    opp_status: Optional[str]
    opp_atk_stage: int
    opp_def_stage: int
    opp_spe_stage: int
    opp_spc_stage: int
    active_reflect_turns: int
    active_light_screen_turns: int
    opp_reflect_turns: int
    opp_light_screen_turns: int
    active_substitute_hp: int
    opp_substitute_hp: int
    active_is_seeded: bool
    opp_is_seeded: bool
    active_toxic_counter: int
    opp_toxic_counter: int
    active_pokemon_remaining: int
    opp_pokemon_remaining: int
    active_bench_pokemon_ids: List[int]
    opp_bench_pokemon_ids: List[int]
    moves: List[Dict]
    chosen_action: str
    chosen_move_id: Optional[int]


@dataclass
class BattleResult:
    battle_queue_id: int
    trainer1_id: int
    trainer2_id: int
    logic_profile_1: str
    logic_profile_2: str
    seed: int
    winner_trainer_id: Optional[int]
    is_draw: bool
    total_turns: int
    turn_events: List[TurnEvent]
    decision_events: List[DecisionEvent]
    team_snapshots: List[Dict]


class Battle:

    def __init__(
        self,
        battle_queue_id: int,
        trainer1: Trainer,
        trainer2: Trainer,
        logic_profile_1: str,
        logic_profile_2: str,
        seed: int,
        max_turns: int,
        type_chart: Dict[Tuple[int, int], float],
        move_loader: Optional[Callable[[str], Optional[Move]]] = None,
    ):
        self.battle_queue_id = battle_queue_id
        self.trainer1 = trainer1
        self.trainer2 = trainer2
        self.logic_profile_1 = logic_profile_1
        self.logic_profile_2 = logic_profile_2
        self.seed = seed
        self.max_turns = max_turns
        self.type_chart = type_chart
        self.move_loader = move_loader
        self.rng = random.Random(seed)
        self.turn = 0
        self._turn_events: List[TurnEvent] = []
        self._decision_events: List[DecisionEvent] = []

        # Screen states: {trainer_id: turns_remaining}
        self.reflect_turns: Dict[int, int] = {trainer1.id: 0, trainer2.id: 0}
        self.light_screen_turns: Dict[int, int] = {trainer1.id: 0, trainer2.id: 0}

    def run(self) -> BattleResult:
        snapshots = _capture_team_snapshots(self.trainer1, self.trainer2)
        while self.turn < self.max_turns:
            self.turn += 1
            self._run_turn()
            if self.trainer1.all_fainted or self.trainer2.all_fainted:
                break
        winner_id = self._determine_winner()
        return BattleResult(
            battle_queue_id=self.battle_queue_id,
            trainer1_id=self.trainer1.id,
            trainer2_id=self.trainer2.id,
            logic_profile_1=self.logic_profile_1,
            logic_profile_2=self.logic_profile_2,
            seed=self.seed,
            winner_trainer_id=winner_id,
            is_draw=(winner_id is None),
            total_turns=self.turn,
            turn_events=self._turn_events,
            decision_events=self._decision_events,
            team_snapshots=snapshots,
        )

    # ------------------------------------------------------------------
    # Turn orchestration
    # ------------------------------------------------------------------

    def _run_turn(self):
        t1, t2 = self.trainer1, self.trainer2
        self._tick_screen_counters()
        self._reset_per_turn_volatiles(t1, t2)

        # Collect decisions
        t1_action, t1_move, t1_swap = self._collect_decision(t1, t2, self.logic_profile_1)
        t2_action, t2_move, t2_swap = self._collect_decision(t2, t1, self.logic_profile_2)

        # Voluntary swaps first
        if t1_action == "swap" and t1_swap is not None:
            self._do_swap(t1, t1_swap, forced=False)
        if t2_action == "swap" and t2_swap is not None:
            self._do_swap(t2, t2_swap, forced=False)

        # Build attack queue sorted by (priority DESC, speed DESC, random tiebreak)
        queue = []
        for trainer, opponent, move, action in [
            (t1, t2, t1_move, t1_action),
            (t2, t1, t2_move, t2_action),
        ]:
            if action in ("attack", "struggle", "charge_release", "recharge"):
                priority = MOVE_EFFECTS.get(_ekey(move.name) if move else "", {}).get("priority", 0) if move else 0
                queue.append((priority, trainer.active.effective_speed(), self.rng.random(),
                               trainer, opponent, move, action))

        queue.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

        for _, _, _, trainer, opponent, move, action in queue:
            if trainer.all_fainted or opponent.all_fainted:
                break
            if trainer.active.is_fainted:
                continue
            if action == "recharge":
                trainer.active.must_recharge = False
                self._emit(TurnEvent(turn=self.turn, trainer_id=trainer.id,
                                     pokemon_id=trainer.active.id, action="recharge"))
                continue
            self._execute_attack(trainer, opponent, move, action)

        # End-of-turn ticks
        self._end_of_turn_ticks(t1, t2)

    # ------------------------------------------------------------------
    # Decision collection
    # ------------------------------------------------------------------

    def _collect_decision(self, trainer: Trainer, opponent: Trainer, profile_name: str):
        poke = trainer.active

        # Must-recharge (Hyper Beam)
        if poke.must_recharge:
            self._record_decision(trainer, opponent, "recharge", None)
            return "recharge", None, None

        # Charging (two-turn move release)
        if poke.is_charging:
            move = next((m for m in poke.moves if m.id == poke.charging_move_id), None)
            if move is None:
                # Fallback: find by name
                move = next((m for m in poke.moves if m.name == poke.charging_move_name), None)
            self._record_decision(trainer, opponent, "charge_release", move.id if move else None)
            return "charge_release", move, None

        # Frozen — cannot act
        if is_frozen(poke):
            self._record_decision(trainer, opponent, "skipped", None)
            return "skipped", None, None

        # Thrash/Petal Dance lock
        if poke.is_thrashing and poke.thrash_turns_remaining > 0:
            move = next((m for m in poke.moves if m.id == poke.thrash_move_id and m.has_pp), None)
            if move:
                self._record_decision(trainer, opponent, "attack", move.id)
                return "attack", move, None
            poke.is_thrashing = False  # PP gone — break lock, fall through to normal decision

        # Rage lock
        if poke.is_raging:
            move = next((m for m in poke.moves if m.id == poke.rage_move_id and m.has_pp), None)
            if move:
                self._record_decision(trainer, opponent, "attack", move.id)
                return "attack", move, None
            poke.is_raging = False  # PP gone — break lock, fall through to normal decision

        # Bide lock
        if poke.bide_active:
            bide_move = next((m for m in poke.moves if m.name == "bide" and m.has_pp), None)
            if bide_move:
                self._record_decision(trainer, opponent, "attack", bide_move.id)
                return "attack", bide_move, None
            poke.bide_active = False  # PP gone — break lock, fall through to normal decision

        # Normal decision
        action = trainer.logic_profile.decide_action(trainer, opponent, self.type_chart, self.rng)
        if action == "swap" and not trainer.bench:
            action = "attack"

        move = None
        swap_target = None

        if action == "attack":
            usable = poke.usable_moves()
            if usable:
                move = trainer.logic_profile.decide_move(trainer, opponent, self.type_chart, self.rng)
            else:
                action = "struggle"
        elif action == "swap":
            swap_target = trainer.logic_profile.decide_swap(trainer, opponent, self.type_chart, self.rng)

        self._record_decision(trainer, opponent, action, move.id if move else None)
        return action, move, swap_target

    # ------------------------------------------------------------------
    # Attack execution
    # ------------------------------------------------------------------

    def _execute_attack(self, attacker: Trainer, defender: Trainer,
                         move: Optional[Move], action: str):
        poke = attacker.active
        target = defender.active

        if poke.is_fainted:
            return

        # Flinch check
        if poke.flinched:
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="flinched"))
            return

        # Sleep / paralysis / confusion check
        if not self._check_can_act(attacker, defender):
            return

        # Struggle
        if action == "struggle":
            self._execute_struggle(attacker, defender)
            return

        # Charge release (two-turn move, second turn)
        if action == "charge_release":
            self._execute_charge_release(attacker, defender, move)
            return

        # Guard: move should never be None for an attack action
        if move is None:
            self._execute_struggle(attacker, defender)
            return

        # Normal move
        effect_data = MOVE_EFFECTS.get(_ekey(move.name), {"effect": "pure_damage"})
        effect = effect_data.get("effect", "pure_damage")

        # Full-control moves (bide, counter, metronome, mirror_move, splash, etc.)
        if effect in FULL_CONTROL_EFFECTS:
            self._execute_full_control(effect, effect_data, attacker, defender, move)
            return

        # Non-damaging moves (status, stat, field)
        if effect in NON_DAMAGING_EFFECTS:
            move.use()
            attacker.last_move_used_id = move.id
            attacker.last_move_used_name = move.name
            hit = check_accuracy(move, poke, target, self.rng)
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="move",
                                 move_id=move.id, move_name=move.name, hit=hit))
            if not hit:
                return
            handler = EFFECT_HANDLERS[effect]
            handler(effect_data, attacker, defender, self, move, self.rng)
            return

        # Damaging moves: accuracy → damage → effect dispatch
        self._execute_damaging_move(effect, effect_data, attacker, defender, move)

    def _check_can_act(self, attacker: Trainer, defender: Trainer) -> bool:
        """Check sleep, paralysis, and confusion. Returns True if the Pokemon can move."""
        poke = attacker.active

        # Sleep
        if poke.status == "sleep":
            if poke.sleep_turns_remaining > 0:
                poke.sleep_turns_remaining -= 1
                self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                     pokemon_id=poke.id, action="skipped", note="sleep"))
                return False
            else:
                poke.status = None

        # Paralysis
        if poke.status == "paralysis" and self.rng.random() < 0.25:
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="skipped", note="paralysis"))
            return False

        # Confusion
        if poke.confused:
            poke.confusion_turns_remaining -= 1
            if poke.confusion_turns_remaining <= 0:
                poke.confused = False
            else:
                if self.rng.random() < 0.50:
                    # Self-hit
                    self_damage = calc_confusion_damage(poke, self.rng)
                    poke.take_damage(self_damage)
                    self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                         pokemon_id=poke.id, action="confusion_self_hit",
                                         damage=self_damage,
                                         target_hp_before=poke.hp + self_damage,
                                         target_hp_after=poke.hp,
                                         target_fainted=poke.is_fainted))
                    if poke.is_fainted:
                        self._handle_faint(attacker)
                    return False

        return True

    def _execute_damaging_move(self, effect: str, effect_data: dict,
                                attacker: Trainer, defender: Trainer, move: Move):
        poke = attacker.active
        target = defender.active

        move.use()
        attacker.last_move_used_id = move.id
        attacker.last_move_used_name = move.name

        high_crit = (effect == "high_crit") or effect_data.get("high_crit", False)

        # --- Accuracy check ---
        hit = self._check_hit(effect, effect_data, move, poke, target)

        hp_before = target.hp

        # --- Damage calculation ---
        damage, is_crit = self._calc_move_damage(effect, effect_data, move,
                                                   poke, target, hit, high_crit)

        # --- Apply damage (to substitute if present, else directly) ---
        actually_hit_target = False
        sub_broke = False
        if hit and damage > 0:
            if target.has_substitute and not self._bypasses_substitute(move):
                sub_broke = target.take_damage_to_substitute(damage)
                actually_hit_target = False
                if sub_broke:
                    self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                         pokemon_id=poke.id, action="substitute_break",
                                         move_id=move.id, move_name=move.name,
                                         target_trainer_id=defender.id,
                                         target_pokemon_id=target.id))
            else:
                target.take_damage(damage)
                actually_hit_target = True
                target.was_hit_this_turn = True
                # Track last physical damage for Counter
                if move.damage_category == "physical":
                    target.last_physical_damage_taken = damage
                    target.last_damage_was_physical = True

        # --- Fire-type thaw ---
        if hit and move.type_name.lower() == "fire" and is_frozen(target):
            thaw(target)

        fainted = target.is_fainted
        self._emit(TurnEvent(
            turn=self.turn, trainer_id=attacker.id, pokemon_id=poke.id,
            action="attack", move_id=move.id, move_name=move.name,
            hit=hit, is_critical=is_crit, damage=damage if actually_hit_target else 0,
            target_trainer_id=defender.id, target_pokemon_id=target.id,
            target_hp_before=hp_before, target_hp_after=target.hp,
            target_fainted=fainted,
        ))

        # --- Effect dispatch (only if hit target directly, not substitute) ---
        handler = EFFECT_HANDLERS.get(effect)
        if handler:
            if effect == "recoil_crash":
                handler(effect_data, attacker, defender, self, move, self.rng, damage, hit)
            elif effect in ("bide", "counter", "thrash", "rage", "two_turn", "binding",
                            "hyper_beam", "self_destruct"):
                handler(effect_data, attacker, defender, self, move, self.rng, damage, hit)
            else:
                handler(effect_data, attacker, defender, self, move, self.rng, damage,
                        hit and actually_hit_target)

        # --- Rage: attacker's own attack raises when hit ---
        if poke.is_raging and hit and damage > 0:
            pass  # Rage raises attack when the raging pokemon is HIT, handled in end of attacker's turn

        if fainted:
            self._handle_faint(defender)

        # Recoil self-damage faint check
        if poke.is_fainted:
            self._handle_faint(attacker)

    def _check_hit(self, effect: str, effect_data: dict, move: Move,
                   poke: Pokemon, target: Pokemon) -> bool:
        """Determine if the move hits, accounting for special accuracy rules."""
        # Swift always hits
        if effect == "swift":
            return True

        # OHKO: flat 30% accuracy
        if effect == "ohko":
            return self.rng.random() < 0.30

        # Invulnerable target (dig/fly charge turn)
        if target.invulnerable:
            bypass = effect_data.get("bypass_moves", [])
            if _ekey(move.name) not in bypass:
                return False

        return check_accuracy(move, poke, target, self.rng)

    def _calc_move_damage(self, effect: str, effect_data: dict, move: Move,
                           poke: Pokemon, target: Pokemon, hit: bool,
                           high_crit: bool) -> Tuple[int, bool]:
        """Compute damage for a move based on its effect type."""
        if not hit:
            return 0, False

        if effect == "fixed_damage":
            return calc_fixed_damage(effect_data["fixed_value"])

        if effect == "level_damage":
            return calc_level_damage(poke)

        if effect == "psywave":
            return calc_psywave_damage(poke, self.rng)

        if effect == "super_fang":
            return calc_super_fang_damage(target)

        if effect == "ohko":
            return calc_ohko_damage(target)

        if effect == "self_destruct":
            return calc_damage(poke, target, move, self.type_chart, self.rng,
                               high_crit=False, halve_defense=True)

        if effect == "earthquake" and target.invulnerable and target.invulnerable_type == "dig":
            # Double power vs digging pokemon — use a temporary doubled-power move
            boosted = copy.copy(move)
            boosted.power = (move.power or 0) * 2
            return calc_damage(poke, target, boosted, self.type_chart, self.rng, high_crit=high_crit)

        if effect == "multi_hit":
            return self._calc_multi_hit(effect_data, poke, target, move, high_crit)

        if effect == "twineedle":
            # Always 2 hits — calc total here (handler applies poison)
            d1, _ = calc_damage(poke, target, move, self.type_chart, self.rng)
            d2, _ = calc_damage(poke, target, move, self.type_chart, self.rng)
            return d1 + d2, False

        # Drain and drain_sleep use standard damage
        if effect in ("drain", "drain_sleep"):
            return calc_damage(poke, target, move, self.type_chart, self.rng, high_crit=high_crit)

        # Recoil and recoil_crash use standard damage
        if effect in ("recoil", "recoil_crash"):
            return calc_damage(poke, target, move, self.type_chart, self.rng, high_crit=high_crit)

        # Reflect halves physical damage
        dmg, crit = calc_damage(poke, target, move, self.type_chart, self.rng, high_crit=high_crit)
        if not crit and move.damage_category == "physical":
            if self.reflect_turns.get(self.trainer1.id if self.trainer1 is not self._get_defender_trainer(poke) else self.trainer2.id, 0) > 0:
                dmg = max(1, dmg // 2)
        if not crit and move.damage_category == "special":
            if self.light_screen_turns.get(self.trainer1.id if self.trainer1 is not self._get_defender_trainer(poke) else self.trainer2.id, 0) > 0:
                dmg = max(1, dmg // 2)
        return dmg, crit

    def _calc_multi_hit(self, effect_data: dict, poke: Pokemon, target: Pokemon,
                         move: Move, high_crit: bool) -> Tuple[int, bool]:
        min_h = effect_data.get("min_hits", 2)
        max_h = effect_data.get("max_hits", 5)
        if min_h == max_h:
            hits = min_h
        else:
            # Gen 1 distribution: 37.5% / 37.5% / 12.5% / 12.5% for 2/3/4/5
            hits = self.rng.choices([2, 3, 4, 5], weights=[3, 3, 1, 1])[0]
            hits = max(min_h, min(max_h, hits))
        total = 0
        for _ in range(hits):
            d, _ = calc_damage(poke, target, move, self.type_chart, self.rng, high_crit=high_crit)
            total += d
        return total, False

    def _get_defender_trainer(self, poke: Pokemon) -> Trainer:
        """Return the trainer who owns poke."""
        return self.trainer1 if poke in [p for p in self.trainer1.team] else self.trainer2

    def _bypasses_substitute(self, move: Move) -> bool:
        """Some moves bypass substitute. In Gen 1, very few do."""
        return move.name in {"transform", "leech-seed"}

    # ------------------------------------------------------------------
    # Special full-control move execution
    # ------------------------------------------------------------------

    def _execute_full_control(self, effect: str, effect_data: dict,
                               attacker: Trainer, defender: Trainer, move: Move):
        poke = attacker.active
        move.use()
        attacker.last_move_used_id = move.id
        attacker.last_move_used_name = move.name

        if effect == "splash" or effect == "no_trainer_effect":
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="move",
                                 move_id=move.id, move_name=move.name))
            return

        if effect == "bide":
            handler = EFFECT_HANDLERS["bide"]
            handler(effect_data, attacker, defender, self, move, self.rng)
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="bide",
                                 move_id=move.id, move_name=move.name))
            if defender.active.is_fainted:
                self._handle_faint(defender)
            return

        if effect == "counter":
            handler = EFFECT_HANDLERS["counter"]
            hp_before = defender.active.hp
            handler(effect_data, attacker, defender, self, move, self.rng)
            damage = hp_before - defender.active.hp
            fainted = defender.active.is_fainted
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="attack",
                                 move_id=move.id, move_name=move.name,
                                 damage=damage,
                                 target_trainer_id=defender.id,
                                 target_pokemon_id=defender.active.id,
                                 target_hp_before=hp_before, target_hp_after=defender.active.hp,
                                 target_fainted=fainted))
            if fainted:
                self._handle_faint(defender)
            return

        if effect == "two_turn":
            handler = EFFECT_HANDLERS["two_turn"]
            handler(effect_data, attacker, defender, self, move, self.rng, 0, False)
            self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                 pokemon_id=poke.id, action="charge",
                                 move_id=move.id, move_name=move.name))
            return

        if effect == "metronome":
            result_name = EFFECT_HANDLERS["metronome"](effect_data, attacker, defender, self, move, self.rng)
            if result_name:
                self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                     pokemon_id=poke.id, action="metronome",
                                     move_id=move.id, move_name=result_name))
                self._dispatch_named_move(result_name, attacker, defender)
            return

        if effect == "mirror_move":
            result_name = EFFECT_HANDLERS["mirror_move"](effect_data, attacker, defender, self, move, self.rng)
            if result_name:
                self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id,
                                     pokemon_id=poke.id, action="mirror_move",
                                     move_id=move.id, move_name=result_name))
                self._dispatch_named_move(result_name, attacker, defender)
            return

    def _execute_charge_release(self, attacker: Trainer, defender: Trainer, move: Optional[Move]):
        """Execute the release turn of a two-turn move."""
        poke = attacker.active
        if move is None:
            return
        effect_data = MOVE_EFFECTS.get(_ekey(move.name), {"effect": "two_turn"})
        high_crit = effect_data.get("high_crit", False)

        hit = check_accuracy(move, poke, defender.active, self.rng)
        hp_before = defender.active.hp
        damage, is_crit = 0, False
        if hit:
            damage, is_crit = calc_damage(poke, defender.active, move, self.type_chart, self.rng,
                                           high_crit=high_crit)
            defender.active.take_damage(damage)

        fainted = defender.active.is_fainted
        self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id, pokemon_id=poke.id,
                              action="attack", move_id=move.id, move_name=move.name,
                              hit=hit, is_critical=is_crit, damage=damage,
                              target_trainer_id=defender.id, target_pokemon_id=defender.active.id,
                              target_hp_before=hp_before, target_hp_after=defender.active.hp,
                              target_fainted=fainted))

        # Apply secondary effects (flinch, etc.) if configured
        flinch_chance = effect_data.get("flinch_chance", 0)
        if hit and damage > 0 and flinch_chance and self.rng.random() < flinch_chance:
            defender.active.flinched = True

        # End charging state
        poke.is_charging = False
        poke.invulnerable = False
        poke.invulnerable_type = None
        poke.charging_move_id = None
        poke.charging_move_name = None

        if fainted:
            self._handle_faint(defender)

    def _dispatch_named_move(self, move_name: str, attacker: Trainer, defender: Trainer):
        """
        Look up a move by name (single DB query) and execute it.
        Used by Metronome and Mirror Move. Does not consume PP on the fetched move.
        """
        move: Optional[Move] = None
        if self.move_loader:
            move = self.move_loader(move_name)

        effect_data = MOVE_EFFECTS.get(_ekey(move_name), {"effect": "pure_damage"})
        effect = effect_data.get("effect", "pure_damage")

        if effect in NON_DAMAGING_EFFECTS:
            handler = EFFECT_HANDLERS.get(effect)
            if handler:
                handler(effect_data, attacker, defender, self, move, self.rng)
            return

        if move is None:
            return  # Can't execute a damaging move without full move data

        # Execute as a damaging move — no PP use, no last_move_used update
        self._execute_damaging_move(effect, effect_data, attacker, defender, move)

    def _execute_struggle(self, attacker: Trainer, defender: Trainer):
        poke = attacker.active
        target = defender.active
        hp_before = target.hp
        # Struggle: typeless physical 50 power, 1/4 recoil, ignore type effectiveness
        from models.move import Move as _Move
        struggle = _Move(id=-1, name="struggle", type_id=0, type_name="Typeless",
                          damage_category="physical", power=_STRUGGLE_POWER,
                          accuracy=None, pp_start=1)
        damage, _ = calc_damage(poke, target, struggle, {}, self.rng)
        target.take_damage(damage)
        recoil = max(1, damage // 4)
        poke.take_damage(recoil)
        fainted = target.is_fainted
        self._emit(TurnEvent(turn=self.turn, trainer_id=attacker.id, pokemon_id=poke.id,
                              action="struggle", hit=True, damage=damage,
                              target_trainer_id=defender.id, target_pokemon_id=target.id,
                              target_hp_before=hp_before, target_hp_after=target.hp,
                              target_fainted=fainted))
        if fainted:
            self._handle_faint(defender)
        if poke.is_fainted:
            self._handle_faint(attacker)

    # ------------------------------------------------------------------
    # End-of-turn ticks
    # ------------------------------------------------------------------

    def _end_of_turn_ticks(self, t1: Trainer, t2: Trainer):
        for trainer, opponent in [(t1, t2), (t2, t1)]:
            poke = trainer.active
            if poke.is_fainted:
                continue

            # Burn / regular poison
            if poke.status in ("burn", "poison"):
                drain = max(1, poke.max_hp // 16)
                hp_before = poke.hp
                poke.take_damage(drain)
                self._emit(TurnEvent(turn=self.turn, trainer_id=trainer.id,
                                     pokemon_id=poke.id,
                                     action=f"{poke.status}_drain",
                                     damage=drain,
                                     target_trainer_id=trainer.id,
                                     target_pokemon_id=poke.id,
                                     target_hp_before=hp_before,
                                     target_hp_after=poke.hp,
                                     target_fainted=poke.is_fainted))
                if poke.is_fainted:
                    self._handle_faint(trainer)
                    continue

            # Toxic escalation
            if poke.status == "toxic":
                drain = max(1, (poke.max_hp * poke.toxic_counter) // 16)
                hp_before = poke.hp
                poke.take_damage(drain)
                poke.toxic_counter = min(poke.toxic_counter + 1, 15)
                self._emit(TurnEvent(turn=self.turn, trainer_id=trainer.id,
                                     pokemon_id=poke.id,
                                     action="toxic_drain",
                                     damage=drain,
                                     target_trainer_id=trainer.id,
                                     target_pokemon_id=poke.id,
                                     target_hp_before=hp_before,
                                     target_hp_after=poke.hp,
                                     target_fainted=poke.is_fainted))
                if poke.is_fainted:
                    self._handle_faint(trainer)
                    continue

            # Leech Seed drain
            if poke.is_seeded and not poke.is_fainted:
                drain = max(1, poke.max_hp // 16)
                hp_before = poke.hp
                poke.take_damage(drain)
                opponent.active.heal(drain)
                self._emit(TurnEvent(turn=self.turn, trainer_id=trainer.id,
                                     pokemon_id=poke.id,
                                     action="leech_seed_drain",
                                     damage=drain,
                                     target_trainer_id=trainer.id,
                                     target_pokemon_id=poke.id,
                                     target_hp_before=hp_before,
                                     target_hp_after=poke.hp,
                                     target_fainted=poke.is_fainted,
                                     note=f"healed {opponent.active.name} for {drain}"))
                if poke.is_fainted:
                    self._handle_faint(trainer)
                    continue

            # Binding damage tick
            if poke.is_bound:
                drain = max(1, poke.max_hp // 16)
                hp_before = poke.hp
                poke.take_damage(drain)
                poke.bound_turns_remaining -= 1
                if poke.bound_turns_remaining <= 0:
                    poke.is_bound = False
                self._emit(TurnEvent(turn=self.turn, trainer_id=trainer.id,
                                     pokemon_id=poke.id,
                                     action="binding_drain",
                                     damage=drain,
                                     target_trainer_id=trainer.id,
                                     target_pokemon_id=poke.id,
                                     target_hp_before=hp_before,
                                     target_hp_after=poke.hp,
                                     target_fainted=poke.is_fainted))
                if poke.is_fainted:
                    self._handle_faint(trainer)
                    continue

            # Rage: attack raised whenever the raging pokemon was hit by any damaging move
            if poke.is_raging and poke.was_hit_this_turn:
                poke.apply_stage("attack", 1)

            # Mist countdown
            if poke.mist_active:
                poke.mist_turns_remaining -= 1
                if poke.mist_turns_remaining <= 0:
                    poke.mist_active = False

            # Disable countdown
            if poke.disabled_move_id is not None:
                poke.disable_turns_remaining -= 1
                if poke.disable_turns_remaining <= 0:
                    poke.disabled_move_id = None

    # ------------------------------------------------------------------
    # Swap and faint handling
    # ------------------------------------------------------------------

    def _do_swap(self, trainer: Trainer, target: Pokemon, forced: bool):
        old = trainer.active
        trainer.swap_to(target)
        self._emit(TurnEvent(turn=self.turn, trainer_id=trainer.id,
                              pokemon_id=old.id,
                              action="forced_swap" if forced else "swap",
                              target_pokemon_id=target.id))

    def _handle_faint(self, trainer: Trainer):
        if not trainer.all_fainted:
            bench = trainer.bench
            if bench:
                self._do_swap(trainer, bench[0], forced=True)

    # ------------------------------------------------------------------
    # Screen / volatile counter ticks
    # ------------------------------------------------------------------

    def _tick_screen_counters(self):
        for trainer_id in list(self.reflect_turns):
            if self.reflect_turns[trainer_id] > 0:
                self.reflect_turns[trainer_id] -= 1
        for trainer_id in list(self.light_screen_turns):
            if self.light_screen_turns[trainer_id] > 0:
                self.light_screen_turns[trainer_id] -= 1

    def _reset_per_turn_volatiles(self, t1: Trainer, t2: Trainer):
        for t in (t1, t2):
            t.active.flinched = False
            t.active.last_physical_damage_taken = 0
            t.active.last_damage_was_physical = False
            t.active.was_hit_this_turn = False

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    def _emit(self, event: TurnEvent):
        self._turn_events.append(event)

    def _record_decision(self, trainer: Trainer, opponent: Trainer,
                          action: str, chosen_move_id: Optional[int]):
        active = trainer.active
        opp = opponent.active
        status_parts = ([active.status] if active.status else []) + (["confused"] if active.confused else [])
        opp_status_parts = ([opp.status] if opp.status else []) + (["confused"] if opp.confused else [])
        self._decision_events.append(DecisionEvent(
            turn=self.turn,
            trainer_id=trainer.id,
            active_pokemon_id=active.id,
            active_hp=active.hp,
            active_status=", ".join(status_parts) if status_parts else None,
            atk_stage=active.stages["attack"],
            def_stage=active.stages["defense"],
            spe_stage=active.stages["speed"],
            spc_stage=active.stages["special"],
            opp_pokemon_id=opp.id,
            opp_hp=opp.hp,
            opp_status=", ".join(opp_status_parts) if opp_status_parts else None,
            opp_atk_stage=opp.stages["attack"],
            opp_def_stage=opp.stages["defense"],
            opp_spe_stage=opp.stages["speed"],
            opp_spc_stage=opp.stages["special"],
            active_reflect_turns=self.reflect_turns.get(trainer.id, 0),
            active_light_screen_turns=self.light_screen_turns.get(trainer.id, 0),
            opp_reflect_turns=self.reflect_turns.get(opponent.id, 0),
            opp_light_screen_turns=self.light_screen_turns.get(opponent.id, 0),
            active_substitute_hp=active.substitute_hp,
            opp_substitute_hp=opp.substitute_hp,
            active_is_seeded=active.is_seeded,
            opp_is_seeded=opp.is_seeded,
            active_toxic_counter=active.toxic_counter,
            opp_toxic_counter=opp.toxic_counter,
            active_pokemon_remaining=len(trainer.conscious_pokemon),
            opp_pokemon_remaining=len(opponent.conscious_pokemon),
            active_bench_pokemon_ids=[p.id for p in trainer.bench],
            opp_bench_pokemon_ids=[p.id for p in opponent.bench],
            moves=[{"id": m.id, "pp": m.pp_curr} for m in active.moves],
            chosen_action=action,
            chosen_move_id=chosen_move_id,
        ))

    def _determine_winner(self) -> Optional[int]:
        t1_out = self.trainer1.all_fainted
        t2_out = self.trainer2.all_fainted
        if t1_out and not t2_out:
            return self.trainer2.id
        if t2_out and not t1_out:
            return self.trainer1.id
        return None


# ------------------------------------------------------------------
# Team snapshot helper
# ------------------------------------------------------------------

def _capture_team_snapshots(t1: Trainer, t2: Trainer) -> List[Dict]:
    snapshots = []
    for trainer in (t1, t2):
        for poke in trainer.team:
            ids = [m.id for m in poke.moves] + [None] * 4
            snapshots.append({
                "trainer_id": trainer.id,
                "pokemon_id": poke.id,
                "party_order": poke.party_order,
                "level": poke.level,
                "hp": poke.max_hp,
                "attack": poke.attack,
                "defense": poke.defense,
                "special": poke.special,
                "speed": poke.speed,
                "move1_id": ids[0],
                "move2_id": ids[1],
                "move3_id": ids[2],
                "move4_id": ids[3],
            })
    return snapshots

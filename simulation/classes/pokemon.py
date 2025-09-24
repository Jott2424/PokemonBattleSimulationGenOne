from class_move_effects import MoveEffects

class Pokemon:
    def __init__(self, pokemon_details: dict):
        self.id = pokemon_details['id']
        self.level = pokemon_details['level']
        self.type_ids = pokemon_details['type_ids']
        self.types = pokemon_details['types']
        self.moves = pokemon_details['moves']
        self.party_order_st = pokemon_details['party_order']
        self.party_order_cur = pokemon_details['party_order']
        
        self.concious = True
        self.active = False
        self.focus_energy_active = False
        self.status_condition_active = False
        self.status_condition = None
        self.active_turn_counter = 0
        self.swap_counter = 0
        self.item_counter = 0
        self.active_status = None
        self.arena_trapped = False
        self.flinch_flag = False
        self.flinched_this_turn = False
        self.confused = False
        
        #immutable
        self.moves_st = self.moves
        #mutable
        self.moves_cur = self.moves

        # stats dictionary
        self.stats = {
            "hp": {"base": stats[0], "start": self.calc_hp(level, stats[0], 8), "current": self.calc_hp(level, stats[0], 8)},
            "attack": {"base": stats[1], "start": self.calc_stats(level, stats[1], 9), "current": self.calc_stats(level, stats[1], 9)},
            "defense": {"base": stats[2], "start": self.calc_stats(level, stats[2], 8), "current": self.calc_stats(level, stats[2], 8)},
            "special": {"base": stats[3], "start": self.calc_stats(level, stats[3], 8), "current": self.calc_stats(level, stats[3], 8)},
            "speed": {"base": stats[4], "start": self.calc_stats(level, stats[4], 8), "current": self.calc_stats(level, stats[4], 8)},
        }

        # Initialize stat modifiers (for accuracy/evasion and other stat changes)
        self.stat_modifiers = {
            "attack": {"stage": 0, "modifier": 1.0},
            "defense": {"stage": 0, "modifier": 1.0},
            "special": {"stage": 0, "modifier": 1.0},
            "speed": {"stage": 0, "modifier": 1.0},
            "accuracy": {"stage": 0, "modifier": 1.0},
            "evasiveness": {"stage": 0, "modifier": 1.0},
        }

        # Add missing attributes that MoveEffects expects
        self.accuracy_modifier = 1.0
        self.evasion_modifier = 1.0
        self.flying = False
        self.sleep_turns = 0
        self.bide_active = False
        self.bide_turns = 0
        self.bide_damage = 0
        self.last_move = None
        self.disabled_move = None

        # Initialize the move effects handler
        self.move_effects = MoveEffects(self)
        
        # Add generic move execution method
        def execute_move_generic(self, attacker, defender, trainer_id, move_id):
            return self.move_effects.execute_move(attacker, defender, trainer_id, move_id)
        
        self.execute_move_generic = execute_move_generic.__get__(self)

    def calc_stats(self, level, basestat, IV):
        return int((basestat + IV) * 2 * level // 100) + 5

    def calc_hp(self, level, basestat, IV):
        return int((basestat + IV) * 2 * level // 100) + level + 10

    def update_stat(self, stat_name, action):
        """Update a stat modifier (increase/decrease)"""
        # Define stage-to-percentage mapping
        stage_to_percent = {
            -6: 0.25, -5: 0.29, -4: 0.33, -3: 0.4, -2: 0.5,
            -1: 0.66, 0: 1.0, 1: 1.5, 2: 2.0, 3: 2.5,
            4: 3.0, 5: 3.5, 6: 4.0,
        }

        # Update the stage and modifier
        current_stage = self.stat_modifiers[stat_name]["stage"]
        new_stage = max(min(current_stage + (1 if action == "increase" else -1), 6), -6)
        self.stat_modifiers[stat_name]["stage"] = new_stage
        self.stat_modifiers[stat_name]["modifier"] = stage_to_percent[new_stage]

        # Update the corresponding modifier for accuracy/evasion
        if stat_name == "accuracy":
            self.accuracy_modifier = stage_to_percent[new_stage]
        elif stat_name == "evasiveness":
            self.evasion_modifier = stage_to_percent[new_stage]

    def reset_stats(self):
        """Reset all stat modifiers to normal"""
        for stat in self.stat_modifiers:
            self.stat_modifiers[stat]["stage"] = 0
            self.stat_modifiers[stat]["modifier"] = 1.0
        
        self.accuracy_modifier = 1.0
        self.evasion_modifier = 1.0

    def print_stats(self):
        print(f"Initialized Pokémon ID: {self.id}")
        print("Stats:", self.stats)
        print("Stat Modifiers:", self.stat_modifiers)
        print("-" * 50)

    def pickMove(self):
        #need to improve
        import random
        return random.choice(self.moves)

    def __repr__(self):
        return (f"Pokemon(partyorder={self.partyorder_st}, id={self.id}, types={self.types}, level={self.level}, "
                f"moves={self.moves}, attributes={self.attributes}, flag_active={self.flag_active}, "
                f"stats={self.stats})")

class Trainer:
    def __init__(self, trainer_details: dict):
        self.id = trainer_details['id']
        self.team_st = trainer_details['team']
        self.team_cur = trainer_details['team']
        self.seed = trainer_details['seed']
        self.type_chart = trainer_details['type_chart']

        #pokemon attributes, need to be updated after every turn
        self.activepokemon = None
        self.faintedpokemon = None
        self.bench = None
        self.fainted = []

        # #turn attributes (these need reset to None before and after each move)
        self.this_turn_action = None
        self.this_turn_attack = None
        self.this_turn_attack_critical = False
        self.this_turn_fainted = False
        self.this_turn_priority = None
        self.this_turn_accuracy = True

        # #turn logic attributes
        # self.prevent_swap = False

    def __repr__(self):
        cls_name = self.__class__.__name__
        attrs = ",\n  ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{cls_name}(\n  {attrs}\n)"
    
    def reset_turn_attributes(self):
        self.this_turn_action = None
        self.this_turn_move = None
        self.this_turn_attack = None
        self.this_turn_attack_critical = False

    def get_activePokemon(self):
        for partorder, pokemon in self.team_cur.items():
            if partorder == 1:   # if Pokémon objects
                self.activepokemon = pokemon
        return None
    
    #----------------------------- these will need to move to the subclasses -----------------------------#
    def decide_action(self):
        self.this_turn_action = 'attack'
        return self.this_turn_action
    
    def decide_attack(self, defender):
        import random
        elligible_moves = [value for key,value in self.activepokemon.moves.items() if value.pp_curr > 0]
        self.this_turn_attack = random.choice(elligible_moves)
        return None
    
    def decide_swap(self):
        self.this_turn_action = 'attack'
        return self.this_turn_action
    #----------------------------- these will need to move to the subclasses -----------------------------#

    def checkTypeEffectiveness(self,atk_type,def_type):
        return self.type_chart[atk_type][def_type]

    # def calc_damage(self, defender):
    #     import math
    #     import random

    #     attacking_move_type_id = self.this_turn_moves[trainer_id]['move_details']['type']
    #     attacking_move_id = self.this_turn_moves[trainer_id]['move_id']

    #     stab = 1.5 if attacking_move_type_id in attacker.activepokemon.types else 1.0

    #     #critical hit
    #     # self.critical_check(trainer_id) #fe_or_dh need to fix this
        
    #     #types effectiveness
    #     type1_effectiveness = self.checkTypeEffectiveness(attacking_move_type_id,defender.activepokemon.types[0])
    #     if defender.activepokemon.types[1] == None:
    #         type2_effectiveness = 1.0
    #     else:
    #         type2_effectiveness = self.checkTypeEffectiveness(attacking_move_type_id,defender.activepokemon.types[1])
        
    #     if int(type1_effectiveness) == 0 or int(type2_effectiveness) == 0:
    #         damage = False
    #         critical_damage = False
        
    #     if self.this_turn_moves[trainer_id]['move_details']['damagecategory'] == 1:
    #         print('move category 1 and critical 1')
    #         attack = attacker.activepokemon.stats.get("attack").get("current")
    #         critical_attack = attacker.activepokemon.stats.get("attack").get("start")
    #         if self.reflect_active:
    #             defense = defender.activepokemon.stats.get("defense").get("current") * 2
    #             critical_defense = defender.activepokemon.stats.get("defense").get("start")
    #         else:
    #             defense = defender.activepokemon.stats.get("defense").get("current")
    #             critical_defense = defender.activepokemon.stats.get("defense").get("start")
    #     elif self.this_turn_moves[trainer_id]['move_details']['damagecategory'] == 2:
    #         print('move category 2 and critical 1')
    #         attack = attacker.activepokemon.stats.get("special").get("current")
    #         critical_attack = attacker.activepokemon.stats.get("special").get("start")
    #         if self.light_screen_active:
    #             defense = defender.activepokemon.stats.get("special").get("current") * 2
    #             critical_defense = defender.activepokemon.stats.get("special").get("start")
    #         else:
    #             defense = defender.activepokemon.stats.get("special").get("current")
    #             critical_defense = defender.activepokemon.stats.get("special").get("start")

    #     #if the attack is explosion or self-destruct, halve the defense and round down
    #     if attacking_move_id in (41,115):
    #         defense = max(1,defense//2)
    #         critical_defense = max(1,critical_defense//2)
        
    #     #if either the attack or dense stat > 255, divide both by 4 and round down
    #     if attack > 255 or defense > 255:
    #         attack = attack//4
    #         critical_attack = critical_attack//4
    #         defense = defense//4
    #         critical_defense = critical_defense//4
        
    #     #need to account for attack/defense being 0 with round down errors
    #     attack = max(1,attack)
    #     critical_attack = max(1,critical_attack)
    #     defense = max(1,defense)
    #     critical_defense = max(1,critical_defense)

    #     # Random modifier for damage calculation
    #     randomint = random.randint(217, 255) / 255.0

    #     #check if move not effective against opponent types
    #     if type1_effectiveness == 0 or type2_effectiveness == 0:
    #         damage = 0
    #         critical_damage = 0
    #         print('selected move has no effect on opponent')
    #     #inflict damage = attacker level
    #     elif attacking_move_id in (88,114): 
    #         damage = attacker.activepokemon.level
    #         critical_damage = ((2 * attacker.activepokemon.level) + 5)//(attacker.activepokemon.level + 5) * attacker.activepokemon.level
    #         print('level damage')
    #     #inflict 50%-150% of attacker level
    #     elif attacking_move_id == 99: 
    #         damage = math.floor(attacker.activepokemon.level * random.uniform(0.5, 1.5))
    #         critical_damage = math.floor(((2 * attacker.activepokemon.level) + 5)//(attacker.activepokemon.level + 5) * attacker.activepokemon.level * random.uniform(0.5, 1.5))
    #     #inflict 40 hp damage
    #     elif attacking_move_id == 35:
    #         damage = 40
    #         critical_damage = 40
    #     #inflict 20 hp damage
    #     elif attacking_move_id == 128:
    #         damage = 20
    #         critical_damage = 20
    #     else:
    #         critical_damage = ((((((float(2.0) * float(attacker.activepokemon.level) * float(2.0))//float(5)) + float(2)) * float(self.this_turn_moves[trainer_id]['move_details']['power']) * float(attack) // float(defense)) // float(50)) + float(2)) * float(stab) * float(type1_effectiveness) * float(type2_effectiveness) * (float(randomint))
    #         damage = ((((((float(2.0) * float(attacker.activepokemon.level) * float(1.0))//float(5)) + float(2)) * float(self.this_turn_moves[trainer_id]['move_details']['power']) * float(attack) // float(defense)) // float(50)) + float(2)) * float(stab) * float(type1_effectiveness) * float(type2_effectiveness) * (float(randomint))
    #     print(f'damage = {int(damage)}.')
    #     if defender.activepokemon.stats.get("hp").get("current") < damage:
    #         damage = defender.activepokemon.stats.get("hp").get("current")
    #     if defender.activepokemon.stats.get("hp").get("current") < critical_damage:
    #         critical_damage = defender.activepokemon.stats.get("hp").get("current")
    #     return [int(damage),int(critical_damage)]



#just for printing
    # def __repr__(self):
    #     attrs = ', '.join(f"{k}={v!r}" for k, v in vars(self).items())
    #     return f"{self.__class__.__name__}({attrs})"

    

# class RandomEverything(Trainer):
#     def choose_action(self, opponent):
#         import random
#         random_action_value = random.random()
#         if random_action_value < 0.5:
#             return "Fight"
#         else:
#             return "Swap"

#     def choose_move(self, opponent):


# class RandomAction(Trainer):
#     def choose_action(self, opponent):
#         import random
#         random_action_value = random.random()
#         if random_action_value < 0.5:
#             return "Fight"
#         else:
#             return "Swap"

# class RandomMoves(Trainer):
#     def choose_action(self, opponent):
#         import random
#         random_action_value = random.random()
#         if random_action_value < 0.5:
#             return "Fight"
#         else:
#             return "Swap"
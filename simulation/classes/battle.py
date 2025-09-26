#-----------------------------------------------------------------------------------------------------------------------------------------------#
# Add this import at the top of the file
# from class_move_effects import MoveEffects

class Battle:
    def __init__(self, id, trainer1, trainer2, max_turns, seed, metronome_moves):
        self.id = id
        self.trainer1 = trainer1
        self.trainer2 = trainer2
        self.trainers = [self.trainer1,self.trainer2]
        self.seed = seed
        self.metronome_moves = metronome_moves

        # self.battle_mechanics = battle_mechanics
        self.turn = 1
        self.max_turns = max_turns
        self.winner = None
        self.winnerID = None

        # Initialize the MoveEffects system
        # self.move_effects = MoveEffects(self)

        # Flags for Reflect and Light Screen
        self.reflect_active = False
        self.light_screen_active = False
        self.reflect_counter = 0
        self.light_screen_counter = 0

        # Turn tracking dictionaries
        self.reset_this_turn_actions()

        # Initialize each trainers first active Pokémon
        self.trainer1.get_activePokemon()
        self.trainer2.get_activePokemon()

        print(f"Battle {self.id} initialized: Trainer {trainer1.id} vs Trainer {trainer2.id}\n")
    
    def commence(self):
        attacker = None
        defender = None

        #each trainer decides what to do
        for trainer in self.trainers:
            trainer.decide_action()
        
        #evaluate trainer decisions
        for trainer in self.trainers:
            if trainer.this_turn_action == 'attack':
                self.this_turn_attacks.append(trainer)
            if trainer.this_turn_action == 'swap':
                self.this_turn_swaps.append(trainer)
        
        #for those attacking, determine which attack they want to use
        for trainer in self.this_turn_attacks:
            attacker = self.trainer1 if trainer.id == self.trainer1.id else self.trainer2
            defender = self.trainer2 if attacker == self.trainer1 else self.trainer1

            print(f'{attacker.id} is deciding which move to use against {defender.id}')
            trainer.decide_attack(defender)
            #decide which move to use
        
        #execute swaps first
        for trainer in self.this_turn_swaps:
            print(f'{trainer.id} is swapping')
        
        #evaluate to see if either attacker picked a priority move and sort the order accordingly
        
        for trainer in self.this_turn_attacks:
            attacker = self.trainer1 if trainer.id == self.trainer1.id else self.trainer2
            defender = self.trainer2 if attacker == self.trainer1 else self.trainer1
            # print(f'{attacker.id} is attacking with {trainer.this_turn_attack}')
            self.execute_attack(attacker,defender)

        self.turn+=1
        self.reset_this_turn_actions()
    
    def reset_this_turn_actions(self):
        self.this_turn_attacks = []
        self.this_turn_swaps = []

    def execute_attack(self,attacker,defender):
        
        """order of events 
            1. Evaluate if defender active pokemon is able to be hit (flying, digging, etc)
            2. Evaluate Accuracy
            3. Evaluate critical hit
            4. Evaluate Damage
            """
        
        accuracy_check = self.accuracy_check(attacker,defender)
        # self.calc_damage(attacker,defender):


    def accuracy_check(self,attacker,defender):
        import math
        import random
        move_accuracy = attacker.this_turn_attack.accuracy
        attacker_accuracy = attacker.activepokemon.stat_modifiers['accuracy']['modifier']
        defender_evasion = defender.activepokemon.stat_modifiers['evasiveness']['modifier']

        final_move_accuracy = max(1,math.floor(math.floor(255 * move_accuracy//100) * math.floor(attacker_accuracy/defender_evasion)))
        accuracy_check_value = random.randint(1,255) #should this be 0?

        print(final_move_accuracy,accuracy_check_value)

        if final_move_accuracy > accuracy_check_value:
            print('passed accuracy check')
            self.gen_one_miss = False
            attacker.this_turn_accuracy = True
            return True
        elif final_move_accuracy == 255 and accuracy_check_value == 255:
            print('Gen 1 Miss!')
            self.gen_one_miss = True
            attacker.this_turn_accuracy = False
            return False
        else:
            print('failed accuracy check')
            self.gen_one_miss = False
            attacker.this_turn_accuracy = False
            return False

#     def lorelei_decide_action(self, attacker, defender):
#         import random
#         # Get moves with available PP
#         moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
#         base_weights = [63, 64, 63, 66]
#         weights = base_weights[:len(moves)]
#         priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

#         # Define the lists of moves affected by modifications
#         low_priority_moves = []  # Moves disfavored by Modification 1 or 3
#         high_priority_moves = []  # Moves favored by Modifications 2 or 3

#         #------------------------------------------------------------------start special logic------------------------------------------------------------------#
#         #--------------------------------------------------lorelei specific logic--------------------------------------------------#    
#         # # if 2 super potions have been used set prevent items = True
#         if attacker.activepokemon.item_counter == 2:
#             attacker.prevent_items = True
#         else:
#             None  

#         #lorelei has a 128/256 chance to use super potion(item id 18 below)
#         rand_action_value = random.randint(0,255)
#         print(rand_action_value)
#         if rand_action_value <=127 and not attacker.prevent_items and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.20:
#             action = 2
#         #if not swapping or using item, then use move
#         else:
#             action = 3

#         #init the trainer action details
#         trainer_action_details = {"action": action}

#         # ------------------------------------------------------------------
#         # Apply Modifications to Priorities
#         # ------------------------------------------------------------------
#         # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
#         if defender.activepokemon.status_condition_active:
#             low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
#             priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

#         # Modification 2: favor specific moves on the second turn a pokemon is out
#         if attacker.activepokemon.active_turn_counter == 1:
#             high_priority_moves = [3,4,5,8,23,27,33,47,53,54,57,58,71,74,76,79,85,89,104,105,106,111,113,116,125,126,134,142,143,145,155,164]
#             priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]

#         # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
#         low_priority_moves = []  # Moves disfavored by Modification 1 or 3
#         high_priority_moves = []  # Moves favored by Modifications 2 or 3

#         for move_id in attacker.activepokemon.moves_cur.keys():
#             defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
#             if defender.activepokemon.types[1] == None:
#                 defender_type2_effectiveness = 1.00
#             else:
#                 defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
#             if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
#                 low_priority_moves += [move_id]
#             elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
#                 high_priority_moves += [move_id]
#             else:
#                 None
        
#         if len(high_priority_moves) !=0:
#             priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
#         else:
#             priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
#             priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
#             priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
#             priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            
#         priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

#         # ------------------------------------------------------------------
#         # Select Moves with Minimum Priority
#         # ------------------------------------------------------------------
#         min_priority = min(priorities)
#         valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
#         valid_weights = [weights[moves.index(move)] for move in valid_moves]

#         # ------------------------------------------------------------------
#         # Decide on a Move
#         # ------------------------------------------------------------------
#         if len(valid_moves) == 0:
#             # No valid moves, default to Struggle
#             selected_move_id = 135  # Struggle move ID
#             trainer_action_details = {
#                 "action": action,
#                 "move_id": selected_move_id,
#                 "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
#             }
#         else:
#             # Select move based on weights
#             selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
#             trainer_action_details = {
#                 "action": action,
#                 "move_id": selected_move_id,
#                 "move_details": attacker.activepokemon.moves_cur[selected_move_id]
#             }

#         # Save the trainer action
#         self.this_turn_moves[attacker.id] = trainer_action_details
#         self.this_turn_actions[attacker.id] = trainer_action_details

#         print(self.this_turn_actions)
    
#     def move_priority_check(self, dict_):
#         priorityMoves = {100: {"priority": 1}, 24: {"priority": -1}}
#         for key,value in dict_.items():
#             self.move_priorities[key] = priorityMoves.get(value, {}).get("priority", 0)
#         if len(set(list(self.move_priorities.values()))) == 1:
#             self.this_turn_move_priorities = False
#         else:
#             sorted_keys = sorted(self.move_priorities.keys(), key=lambda k: self.move_priorities[k], reverse=True)
#             self.this_turn_move_priorities = {i + 1: key for i, key in enumerate(sorted_keys)}
    
#     def speed_priority_check(self, dict_):
#         import random     
#         if len(set(list(dict_.values()))) == 1:
#             keys = list(dict_.keys())
#             random.shuffle(keys)  # Shuffle the keys
#             self.this_turn_move_priorities = {i + 1: keys[i] for i in range(len(keys))}
#         else:
#             sorted_keys = sorted(dict_, key=dict_.get, reverse=True)
#             self.this_turn_move_priorities = {i + 1: sorted_keys[i] for i in range(len(sorted_keys))}
    
#     def accuracy_check(self,trainer_id):
#         import math
#         import random
#         attacker = self.trainer1 if trainer_id == self.trainer1.id else self.trainer2
#         defender = self.trainer2 if attacker == self.trainer1 else self.trainer1

#         move_accuracy = self.this_turn_moves[trainer_id]["move_details"]["accuracy"]
#         attacker_accuracy = attacker.activepokemon.stat_modifiers_cur['accuracy']['modifier']
#         defender_evasion = defender.activepokemon.stat_modifiers_cur['evasiveness']['modifier']

#         final_move_accuracy = max(1,math.floor(math.floor(255 * move_accuracy//100) * math.floor(attacker_accuracy/defender_evasion)))
#         accuracy_check_value = random.randint(1,255) #should this be 0?


#         if final_move_accuracy > accuracy_check_value:
#             print('passed accuracy check')
#             self.gen_one_miss = False
#             attacker.this_turn_accuracy = True
#             return True
#         elif final_move_accuracy == 255 and accuracy_check_value == 255:
#             print('Gen 1 Miss!')
#             self.gen_one_miss = True
#             attacker.this_turn_accuracy = False
#             return False
#         else:
#             print('failed accuracy check')
#             self.gen_one_miss = False
#             attacker.this_turn_accuracy = False
#             return False

#     def thirtythree_percent_odds(self):
#         import math
#         import random

#         check_value = random.randint(0,255) #should this be 0?

#         if check_value < 85:
#             return True
#         else:
#             return False
    
#     def ten_percent_odds(self):
#         import math
#         import random

#         check_value = random.randint(0,255) #should this be 0?

#         if check_value < 26:
#             return True
#         else:
#             return False
        
#     def checkTypeEffectiveness(self,atk_type,def_type):
#         return self.type_chart[atk_type][def_type]
        
#     def critical_check(self, trainer_id):
#         import random
#         attacker = self.trainer1 if trainer_id == self.trainer1.id else self.trainer2

#         #generate check value
#         critical_check_value = random.randint(0,255)

#         # print(self.this_turn_moves[trainer_id])

#         #checking for focus energy and dire hit as well as high critical hit moves (crabhammer, karate chop, razor leaf, slash)
#         if not attacker.activepokemon.focus_energy_active == 1 and not self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
#             critical_threshold = attacker.activepokemon.stats.get("speed").get("base")//2
#         elif attacker.activepokemon.focus_energy_active == 1 and not self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
#             critical_threshold = attacker.activepokemon.stats.get("speed").get("base")//8
#         elif not attacker.activepokemon.focus_energy_active == 1 and self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
#             critical_threshold = 8*attacker.activepokemon.stats.get("speed").get("base")//2
#         elif attacker.activepokemon.focus_energy_active == 1 and self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
#             critical_threshold = attacker.activepokemon.stats.get("speed").get("base")
        
#         if critical_threshold > 255:
#             critical_threshold = 255
        
#         if critical_check_value < critical_threshold:
#             print('critical hit!')
#             attacker.this_turn_move_critical = True
#             return True
#         else:
#             print('not a critical hit')
#             attacker.this_turn_move_critical = False
#             return False
        
#         # attacker.this_turn_move_critical = True
    
#     def calc_damage(self,attacker, defender, trainer_id):
#         import math
#         import random

#         attacking_move_type_id = self.this_turn_moves[trainer_id]['move_details']['type']
#         attacking_move_id = self.this_turn_moves[trainer_id]['move_id']

#         stab = 1.5 if attacking_move_type_id in attacker.activepokemon.types else 1.0

#         #critical hit
#         # self.critical_check(trainer_id) #fe_or_dh need to fix this
        
#         #types effectiveness
#         type1_effectiveness = self.checkTypeEffectiveness(attacking_move_type_id,defender.activepokemon.types[0])
#         if defender.activepokemon.types[1] == None:
#             type2_effectiveness = 1.0
#         else:
#             type2_effectiveness = self.checkTypeEffectiveness(attacking_move_type_id,defender.activepokemon.types[1])
        
#         if int(type1_effectiveness) == 0 or int(type2_effectiveness) == 0:
#             damage = False
#             critical_damage = False
        
#         if self.this_turn_moves[trainer_id]['move_details']['damagecategory'] == 1:
#             print('move category 1 and critical 1')
#             attack = attacker.activepokemon.stats.get("attack").get("current")
#             critical_attack = attacker.activepokemon.stats.get("attack").get("start")
#             if self.reflect_active:
#                 defense = defender.activepokemon.stats.get("defense").get("current") * 2
#                 critical_defense = defender.activepokemon.stats.get("defense").get("start")
#             else:
#                 defense = defender.activepokemon.stats.get("defense").get("current")
#                 critical_defense = defender.activepokemon.stats.get("defense").get("start")
#         elif self.this_turn_moves[trainer_id]['move_details']['damagecategory'] == 2:
#             print('move category 2 and critical 1')
#             attack = attacker.activepokemon.stats.get("special").get("current")
#             critical_attack = attacker.activepokemon.stats.get("special").get("start")
#             if self.light_screen_active:
#                 defense = defender.activepokemon.stats.get("special").get("current") * 2
#                 critical_defense = defender.activepokemon.stats.get("special").get("start")
#             else:
#                 defense = defender.activepokemon.stats.get("special").get("current")
#                 critical_defense = defender.activepokemon.stats.get("special").get("start")

#         #if the attack is explosion or self-destruct, halve the defense and round down
#         if attacking_move_id in (41,115):
#             defense = max(1,defense//2)
#             critical_defense = max(1,critical_defense//2)
        
#         #if either the attack or dense stat > 255, divide both by 4 and round down
#         if attack > 255 or defense > 255:
#             attack = attack//4
#             critical_attack = critical_attack//4
#             defense = defense//4
#             critical_defense = critical_defense//4
        
#         #need to account for attack/defense being 0 with round down errors
#         attack = max(1,attack)
#         critical_attack = max(1,critical_attack)
#         defense = max(1,defense)
#         critical_defense = max(1,critical_defense)

#         # Random modifier for damage calculation
#         randomint = random.randint(217, 255) / 255.0

#         #check if move not effective against opponent types
#         if type1_effectiveness == 0 or type2_effectiveness == 0:
#             damage = 0
#             critical_damage = 0
#             print('selected move has no effect on opponent')
#         #inflict damage = attacker level
#         elif attacking_move_id in (88,114): 
#             damage = attacker.activepokemon.level
#             critical_damage = ((2 * attacker.activepokemon.level) + 5)//(attacker.activepokemon.level + 5) * attacker.activepokemon.level
#             print('level damage')
#         #inflict 50%-150% of attacker level
#         elif attacking_move_id == 99: 
#             damage = math.floor(attacker.activepokemon.level * random.uniform(0.5, 1.5))
#             critical_damage = math.floor(((2 * attacker.activepokemon.level) + 5)//(attacker.activepokemon.level + 5) * attacker.activepokemon.level * random.uniform(0.5, 1.5))
#         #inflict 40 hp damage
#         elif attacking_move_id == 35:
#             damage = 40
#             critical_damage = 40
#         #inflict 20 hp damage
#         elif attacking_move_id == 128:
#             damage = 20
#             critical_damage = 20
#         else:
#             critical_damage = ((((((float(2.0) * float(attacker.activepokemon.level) * float(2.0))//float(5)) + float(2)) * float(self.this_turn_moves[trainer_id]['move_details']['power']) * float(attack) // float(defense)) // float(50)) + float(2)) * float(stab) * float(type1_effectiveness) * float(type2_effectiveness) * (float(randomint))
#             damage = ((((((float(2.0) * float(attacker.activepokemon.level) * float(1.0))//float(5)) + float(2)) * float(self.this_turn_moves[trainer_id]['move_details']['power']) * float(attack) // float(defense)) // float(50)) + float(2)) * float(stab) * float(type1_effectiveness) * float(type2_effectiveness) * (float(randomint))
#         print(f'damage = {int(damage)}.')
#         if defender.activepokemon.stats.get("hp").get("current") < damage:
#             damage = defender.activepokemon.stats.get("hp").get("current")
#         if defender.activepokemon.stats.get("hp").get("current") < critical_damage:
#             critical_damage = defender.activepokemon.stats.get("hp").get("current")
#         return [int(damage),int(critical_damage)]
    
#     def execute_swaps(self):
#         if len(self.this_turn_swaps.keys()) == 0:
#             #must increase the swapped pokemons .sswap_counter attribute, which is used by juggler to calc if he can keep swapping
            
#             print('No swaps')

#     def execute_items(self):
#         if len(self.this_turn_items.keys()) == 0:
#             #must increase active pokemon .item_counter attribute, many trainers use this to determine if they can keep using moves
#             print('No items')
    
# ############################################################################### Attack Supporting Functions ###############################################################################
#     def applyDamage(self,attacker,defender,damageAmt):
#         print(f'{attacker.activepokemon.id} inflicted {damageAmt} on {defender.activepokemon.id}, who has {defender.activepokemon.stats.get("hp").get("current")} hp')
#         #if the amount of damage is greater or equal to defender current hp, knock it out
#         if defender.activepokemon.stats.get("hp").get("current") < damageAmt:
#             defender.activepokemon.stats['hp']['current'] = 0
#             defender.activepokemon.concious = False
#             print(f'{defender.activepokemon.id} knocked out!')
#         #if the amount of damage is less than defender current hp, find the difference and set the new hp
#         elif defender.activepokemon.stats.get("hp").get("current") > damageAmt:
#             difference = defender.activepokemon.stats.get("hp").get("current") - damageAmt
#             defender.activepokemon.stats['hp']['current'] = difference
#         return

#     def restoreHealth(self,target,amt):
#         if target.stats['hp']['current'] + amt > target.stats['hp']['start']:
#             amt = target.stats['hp']['start'] - target.stats['hp']['current']
#         target.stats['hp']['current'] += amt
#         print(f'{target.id} healed {amt} hp')

    
# ################################################################################################################################################################################################################
#     def execute_moves(self):
#         import random
#         self.move_priorities = {}
#         self.speed_priorities = {}
#         self.this_turn_move_priorities = {}
#         accuracy = False
#         #if there are no moves this turn, exit
#         if len(self.this_turn_moves.keys()) == 0:
#             print('No moves')
#             self.this_turn_move_priorities = False
#         #if there is only 1 move this turn, set the move priorities to that 1 trainer
#         elif len(self.this_turn_moves.keys()) == 1:
#             self.this_turn_move_priorities = {1: key for key in self.this_turn_moves.keys()}
#         #if there is more than 1 move this turn, evaluate the priorities
#         elif len(self.this_turn_moves.keys()) > 1:
#             print('Moves!')
#             self.move_priority_check({key: value['move_id'] for key, value in self.this_turn_moves.items()})
#             #see if we need to do a speed check
#             if not self.this_turn_move_priorities:
#                 self.speed_priority_check({trainer.id: trainer.activepokemon.stats['speed'].get("current") for trainer in [self.trainer1,self.trainer2]})
#             else:
#                 print('dont need speed check')
        
#         #if there is atleast 1 move being executed, loop through them.
#         if self.this_turn_move_priorities:
#             for priority, trainer_id in self.this_turn_move_priorities.items():
#                 #identify attacker and defender
#                 attacker = self.trainer1 if trainer_id == self.trainer1.id else self.trainer2
#                 defender = self.trainer2 if attacker == self.trainer1 else self.trainer1
#                 #determine attack physical/special/status
#                 damage_category = self.this_turn_moves[trainer_id]['move_details']['damagecategory']
#                 #evaluate accuracy in udf
#                 accuracy = self.accuracy_check(trainer_id)
#                 #if the move doesnt miss, determine damage and apply
#                 if accuracy:
#                     #if damage will be inflicted then calculate it and apply, otherwise inflict status condition
#                     if damage_category in (1,2):
#                         print(f'trainer id {trainer_id} will use the move {self.this_turn_moves[trainer_id]['move_id']}')

#                         ###################################################################################################################################################
#                         #calc and apply damage
#                         #############################
#                         #if move will hit 2-5 times, determine how many then calc and apply each
#                         if self.this_turn_moves[trainer_id]['move_id'] in (7,19,32,50,51,92,129):
#                             attackloopcount = random.randint(2,5)
#                             for attackloop in range(0,attackloopcount+1):
#                                 damage = self.calc_damage(trainer_id)
#                                 if defender.activepokemon.stats.get("hp").get("current") < damage:
#                                     damage = defender.activepokemon.stats.get("hp").get("current")
#                                 self.applyDamage(attacker,defender,damage)
#                             print(f'move hit {attackloopcount} times')
#                         #otherwise just calc and apply damage
#                         else:
#                             damage = self.calc_damage(trainer_id)
#                             if defender.activepokemon.stats.get("hp").get("current") < damage:
#                                     damage = defender.activepokemon.stats.get("hp").get("current")
#                             self.applyDamage(attacker,defender,damage)
                        
#                         #if some health is recovered
#                         #--------------------------------------------------------------------------#
#                         if self.this_turn_moves[trainer_id]['move_id'] in (1,36,72,80):
#                             restoreamt = damage//2
#                             newhp = min(attacker.activepokemon.stats['hp']['current'] + restoreamt,attacker.activepokemon.stats['hp']['start'])
#                             attacker.activepokemon.stats['hp']['current'] = newhp
#                         else:
#                             print('no health recovered')
                        
#                         #if a move might lower a stat of the opponent
#                         if self.this_turn_moves[trainer_id]['move_id'] in (2,6,16,17,22,98):
#                             stat_lower = self.thirtythree_percent_odds()
#                             if not stat_lower:
#                                 return
#                             elif stat_lower and self.this_turn_moves[trainer_id]['move_id'] in (2,98):
#                                 defender.activepokemon.update_stat("special","decrease")
#                             elif stat_lower and self.this_turn_moves[trainer_id]['move_id'] in (16,17,22):
#                                 defender.activepokemon.update_stat("speed","decrease")
#                             elif stat_lower and self.this_turn_moves[trainer_id]['move_id'] in (6):
#                                 defender.activepokemon.update_stat("attack","decrease")

#                     else:
#                         damage = 0
#                         print('damage category 3 need to implement ')
#                     #if move restores 50% max health
#                     if self.this_turn_moves[trainer_id]['move_id'] in (104,126):
#                         restoreamt = attacker.activepokemon.stats['hp']['start']//2
#                         newhp = min(attacker.activepokemon.stats['hp']['current'] + restoreamt,attacker.activepokemon.stats['hp']['start'])
#                         attacker.activepokemon.stats['hp']['current'] = newhp

#                         #checking to make sure health is restored as it should be - can delete this-#
#                         print(attacker.activepokemon.stats['hp']['current'])
#                         print(self.trainer1.activepokemon.stats['hp']['current'])
#                         print(self.trainer2.activepokemon.stats['hp']['current'])
#                         #---------------------------------------------------------------------------#
#                     #otherwise restore 0 health
#                     else:
#                         None
#                     #apply any arena effects if necessary
                    
#                     #apply any status effects if necessary
#                     #may lower opponent special defense
#                     # if self.this_turn_moves[trainer_id]['move_id'] == 2:
#                     #     stat_lower_check_value = random.randint(0,255)
#                     #     if stat_lower_check_value <= 84:
#                     #         if self.this_turn_moves[trainer_id]['move_id']:
#                     #             defender.activepokemon.update_stat(stat_name, action)
#                     # print(attacker.activepokemon.stat_modifiers_cur)
                    
#                     #apply any stat changes if necessary
#                     #drop the pp of the attacker's move

#                 else:
#                     next
#                 #apply any lingering status effects
#                 #apply any lingering arena effects
    
#     def take_turn(self):
#         """Simulates a single turn in the battle."""
#         print(f"Turn {self.turn} begins!\n")

#         #reset turn attributes before taking turn
#         # self.reset_turn_attributes()

#         # Get active Pokémon
#         trainer1_active_pokemon = self.trainer1.activepokemon
#         trainer2_active_pokemon = self.trainer2.activepokemon

#         trainers = [self.trainer1,self.trainer2]
        
#         # decide turn action
#         self.this_turn_actions = {}
#         self.this_turn_swaps = {}
#         self.this_turn_items = {}
#         self.this_turn_moves = {}


#         self.juggler_decide_action(self.trainer1,self.trainer2)

#         # self.decide_trainer_actions(trainers)

#         #execute swaps (order doesnt matter)
#         self.execute_swaps()

#         #execute items (order doesnt matter)
#         self.execute_items()

#         #execute moves (order DOES matter)
#         self.execute_moves()

#         self.turn +=1
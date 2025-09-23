#-----------------------------------------------------------------------------------------------------------------------------------------------#
# Add this import at the top of the file
from class_move_effects import MoveEffects

class Battle:
    # def __init__(self, id, trainer1, trainer2, battle_mechanics, max_turns=100):
    def __init__(self, id, trainer1, trainer2, max_turns=1):
        self.id = id
        self.trainer1 = trainer1
        self.trainer2 = trainer2
        # self.battle_mechanics = battle_mechanics
        self.turn = 1
        self.max_turns = max_turns
        self.winner = None
        self.winnerID = None

        # Initialize the MoveEffects system
        self.move_effects = MoveEffects(self)

        # Flags for Reflect and Light Screen
        self.reflect_active = False
        self.light_screen_active = False
        self.reflect_counter = 0
        self.light_screen_counter = 0

        # Turn tracking dictionaries
        self.this_turn_moves = {}
        self.this_turn_actions = {}
        self.this_turn_swaps = {}
        self.this_turn_items = {}

        # Move data from CSV
        self.moves_data = self.load_moves_data()

        # Initialize each trainers first active Pokémon
        self.trainer1.get_activePokemon()
        self.trainer2.get_activePokemon()

        print(f"Battle {self.id} initialized: Trainer {trainer1.id} vs Trainer {trainer2.id}\n")
    
    def load_moves_data(self):
        """Load move data from CSV file for better move handling"""
        import csv
        moves_data = {}
        try:
            with open('moves.csv', 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    move_id = int(row['pk_move_id'])
                    moves_data[move_id] = {
                        'id': move_id,
                        'type_id': int(row['fk_type_id']),
                        'damage_category': int(row['fk_damage_category_id']),
                        'name': row['move_name'],
                        'description': row['move_desc']
                    }
        except FileNotFoundError:
            print("Warning: moves.csv not found. Using basic move data.")
        return moves_data
    #--------------------------------------------------------------------------------------------# 
    def get_typeChart(self,credentials):
        import psycopg2 #remove this down the line, make this a module/package

        conn = psycopg2.connect(
            host=credentials[0],
            port=credentials[1],
            database=credentials[2],
            user=credentials[3],
            password=credentials[4]
        )
        cursor = conn.cursor()

        # Query the type matchups
        query = f"""
        SELECT fk_atk_type_id, fk_def_type_id, multiplier
        FROM genone_pokedex_ingested.types_effectiveness;
        """
        cursor.execute(query)

        # Create a nested dictionary from the results
        type_chart = {}
        for row in cursor.fetchall():
            fk_atk_type_id, fk_def_type_id, multiplier = row
            if fk_atk_type_id not in type_chart:
                type_chart[fk_atk_type_id] = {}
            type_chart[fk_atk_type_id][fk_def_type_id] = multiplier

        # Close the connection
        cursor.close()
        conn.close()

        self.type_chart = type_chart
    
    def c1ns_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}

        # ------------------------------------------------------------------
        # Apply Modifications to Priorities
        # ------------------------------------------------------------------
        # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
        if defender.activepokemon.status_condition_active:
            low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
            priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # ------------------------------------------------------------------
        # Select Moves with Minimum Priority
        # ------------------------------------------------------------------
        min_priority = min(priorities)
        valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
        valid_weights = [weights[moves.index(move)] for move in valid_moves]

        # ------------------------------------------------------------------
        # Decide on a Move
        # ------------------------------------------------------------------
        if len(valid_moves) == 0:
            # No valid moves, default to Struggle
            selected_move_id = 135  # Struggle move ID
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
            }
        else:
            # Select move based on weights
            selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": attacker.activepokemon.moves_cur[selected_move_id]
            }

        # Save the trainer action
        self.this_turn_moves[attacker.id] = trainer_action_details
        self.this_turn_actions[attacker.id] = trainer_action_details

        print(self.this_turn_actions)
    
    def c12ns_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}

        # ------------------------------------------------------------------
        # Apply Modifications to Priorities
        # ------------------------------------------------------------------
        # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
        if defender.activepokemon.status_condition_active:
            low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
            priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # Modification 2: favor specific moves on the second turn a pokemon is out
        if attacker.activepokemon.active_turn_counter == 1:
            high_priority_moves = [3,4,5,8,23,27,33,47,53,54,57,58,71,74,76,79,85,89,104,105,106,111,113,116,125,126,134,142,143,145,155,164]
            priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]

        # ------------------------------------------------------------------
        # Select Moves with Minimum Priority
        # ------------------------------------------------------------------
        min_priority = min(priorities)
        valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
        valid_weights = [weights[moves.index(move)] for move in valid_moves]

        # ------------------------------------------------------------------
        # Decide on a Move
        # ------------------------------------------------------------------
        if len(valid_moves) == 0:
            # No valid moves, default to Struggle
            selected_move_id = 135  # Struggle move ID
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
            }
        else:
            # Select move based on weights
            selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": attacker.activepokemon.moves_cur[selected_move_id]
            }

        # Save the trainer action
        self.this_turn_moves[attacker.id] = trainer_action_details
        self.this_turn_actions[attacker.id] = trainer_action_details

        print(self.this_turn_actions)
    
    def c13ns_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}

        # ------------------------------------------------------------------
        # Apply Modifications to Priorities
        # ------------------------------------------------------------------
        # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
        if defender.activepokemon.status_condition_active:
            low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
            priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        for move_id in attacker.activepokemon.moves_cur.keys():
            defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
            if defender.activepokemon.types[1] == None:
                defender_type2_effectiveness = 1.00
            else:
                defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
            if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                low_priority_moves += [move_id]
            elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                high_priority_moves += [move_id]
            else:
                None
        
        if len(high_priority_moves) !=0:
            priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
        else:
            priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            
        priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # ------------------------------------------------------------------
        # Select Moves with Minimum Priority
        # ------------------------------------------------------------------
        min_priority = min(priorities)
        valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
        valid_weights = [weights[moves.index(move)] for move in valid_moves]

        # ------------------------------------------------------------------
        # Decide on a Move
        # ------------------------------------------------------------------
        if len(valid_moves) == 0:
            # No valid moves, default to Struggle
            selected_move_id = 135  # Struggle move ID
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
            }
        else:
            # Select move based on weights
            selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": attacker.activepokemon.moves_cur[selected_move_id]
            }

        # Save the trainer action
        self.this_turn_moves[attacker.id] = trainer_action_details
        self.this_turn_actions[attacker.id] = trainer_action_details

        print(self.this_turn_actions)
    
    def c123ns_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}

        # ------------------------------------------------------------------
        # Apply Modifications to Priorities
        # ------------------------------------------------------------------
        # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
        if defender.activepokemon.status_condition_active:
            low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
            priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # Modification 2: favor specific moves on the second turn a pokemon is out
        if attacker.activepokemon.active_turn_counter == 1:
            high_priority_moves = [3,4,5,8,23,27,33,47,53,54,57,58,71,74,76,79,85,89,104,105,106,111,113,116,125,126,134,142,143,145,155,164]
            priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]

        # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        for move_id in attacker.activepokemon.moves_cur.keys():
            defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
            if defender.activepokemon.types[1] == None:
                defender_type2_effectiveness = 1.00
            else:
                defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
            if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                low_priority_moves += [move_id]
            elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                high_priority_moves += [move_id]
            else:
                None
        
        if len(high_priority_moves) !=0:
            priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
        else:
            priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            
        priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # ------------------------------------------------------------------
        # Select Moves with Minimum Priority
        # ------------------------------------------------------------------
        min_priority = min(priorities)
        valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
        valid_weights = [weights[moves.index(move)] for move in valid_moves]

        # ------------------------------------------------------------------
        # Decide on a Move
        # ------------------------------------------------------------------
        if len(valid_moves) == 0:
            # No valid moves, default to Struggle
            selected_move_id = 135  # Struggle move ID
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
            }
        else:
            # Select move based on weights
            selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": attacker.activepokemon.moves_cur[selected_move_id]
            }

        # Save the trainer action
        self.this_turn_moves[attacker.id] = trainer_action_details
        self.this_turn_actions[attacker.id] = trainer_action_details

        print(self.this_turn_actions)
    
    def ns_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}

        # ------------------------------------------------------------------
        # Select Moves with Minimum Priority
        # ------------------------------------------------------------------
        min_priority = min(priorities)
        valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
        valid_weights = [weights[moves.index(move)] for move in valid_moves]

        # ------------------------------------------------------------------
        # Decide on a Move
        # ------------------------------------------------------------------
        if len(valid_moves) == 0:
            # No valid moves, default to Struggle
            selected_move_id = 135  # Struggle move ID
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
            }
        else:
            # Select move based on weights
            selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": attacker.activepokemon.moves_cur[selected_move_id]
            }

        # Save the trainer action
        self.this_turn_moves[attacker.id] = trainer_action_details
        self.this_turn_actions[attacker.id] = trainer_action_details

        print(self.this_turn_actions)

    def agatha_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------agatha specific logic--------------------------------------------------#  
        # if 2 super potions have been used on the active pokemon, set prevent items = True and prevent swap = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
            attacker.prevent_swap = True
        else:
            None
        rand_action_value = random.randint(0,255)
        #agatha has a 20/256 chance to swap to her next unfainted party member (party order 2 below)
        if rand_action_value <=19 and not attacker.prevent_swap and not len(attacker.bench) == 0:
            action = 1
        #agatha has 108/256 chance to use a super potion on her active pokemon if its current health is < 25% of its max health (item id 18 below)
        #once she uses 2 super potions on an active pokemon she will not use any more and she will no longer switch
        elif not attacker.prevent_items and rand_action_value <=107 and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.25:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}
        
        if action == 1:
            print('need to implement logic to swap to next unfainted party member')
            trainer_action_details["swap_target_party_order"] = 2

            self.this_turn_swaps[attacker.id] = trainer_action_details
        elif action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 18 #super potion
            trainer_action_details["item_target_party_order"] = 1

            self.this_turn_items[attacker.id] = trainer_action_details
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details
        #save the turn actions
        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def blackbelt_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------blackbelt specific logic--------------------------------------------------#    
        # if 2 x attacks have been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
        else:
            None  

        rand_action_value = random.randint(0,255)
        #blackbelt has 32/256 chance to use an x attack on their active pokemon
        #once they use 2 x attacks on an active pokemon they will not use any more
        if not attacker.prevent_items and rand_action_value <=31:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}
        
        if action == 2:
            print('need to implement logic to use x attack')
            trainer_action_details["item_id"] = 63 #x attack
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details
        #save the turn actions
        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def blaine_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------blaine specific logic--------------------------------------------------#      
        # if 2 super potions have been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
        else:
            None 
        rand_action_value = random.randint(0,255)
        #blaine has 64/256 chance to use a super potion on his active pokemon (item id 18 below)
        #once he uses 2 super potions on an active pokemon she will not use any more and she will no longer switch
        if not attacker.prevent_items and rand_action_value <=63:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        #--------------------------------------------------blaine specific logic--------------------------------------------------# 
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 18 #super potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def blue2_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------blue2 specific logic--------------------------------------------------#      
        # if 1 potion has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None 
        rand_action_value = random.randint(0,255)
        #blue2 has 32/256 chance to use a potion on his active pokemon if the health is below 20% (item id 19 below)
        #once he uses 1 potions on an active pokemon he will not use any more
        if not attacker.prevent_items and rand_action_value <=31 and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.2:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}
        
        if action == 2:
            print('need to implement logic to use potion')
            trainer_action_details["item_id"] = 19 # potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def blue3_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------blue3 specific logic--------------------------------------------------#    
        # # if 1 full restore has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  
        rand_action_value = random.randint(0,255)
        #blue3 has 32/256 chance to use a full restore on his active pokemon if the health is below 20% (item id 15 below)
        #once he uses 1 full restore on an active pokemon he will not use any more
        if not attacker.prevent_items and rand_action_value <=31 and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.2:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}
        
        if action == 2:
            print('need to implement logic to use full restore')
            trainer_action_details["item_id"] = 15 # full restore
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def brock_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------brock specific logic--------------------------------------------------#    
        # # if 5 full heals have been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 5:
            attacker.prevent_items = True
        else:
            None  
        
        #brock has 100% chance to use a full heal on his active pokemon if there is a status condition
        #once he uses 5 on an active pokemon he will not use any more
        if attacker.activepokemon.status_condition_active:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}
        
        if action == 2:
            print('need to implement logic to use full heal')
            trainer_action_details["item_id"] = 50 # full heal
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def bruno_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------bruno specific logic--------------------------------------------------#    
        # # if 2 x defends have been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
        else:
            None  
        rand_action_value = random.randint(0,255)
        #bruno has 64/256 chance to use an x defend on his active pokemon (item id 64 below)
        #once he uses 2 x defend on an active pokemon he will not use any more
        if not attacker.prevent_items and rand_action_value <=63:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3

        
        #init the trainer action details
        trainer_action_details = {"action": action}
        
        if action == 2:
            print('need to implement logic to use full heal')
            trainer_action_details["item_id"] = 64 # full heal
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def cooltrainerF_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------cooltrainer F specific logic--------------------------------------------------#    
        # # if 1 hyper potion has been used on the active pokemon, set prevent items = True and prevent swaps = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
            attacker.prevent_swap = True
        else:
            None  
        #cool trainer F has 100% chance to use a hyper potion if the active pokemon's health is below 10% (item id 17 below)
        #cool trainer F also has 100% chance to swap to the next pokemon if the active pokemon's health is between 10 and 20 %
        #once she uses 1 hyper potion she will not use any more or swap pokemon
        if not attacker.prevent_items and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.10:
            action = 2
        elif not attacker.prevent_swap and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] >= 0.10 and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] <= 0.20 and not len(attacker.bench) == 0:
            action = 1
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 1:
            print('need to implement logic to swap to next unfainted party member')
            trainer_action_details["swap_target_party_order"] = 2
            self.this_turn_swaps[attacker.id] = trainer_action_details
        elif action == 2:
            print('need to implement logic to use hyper potion')
            trainer_action_details["item_id"] = 17 #hyper potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def cooltrainerM_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------cooltrainer M specific logic--------------------------------------------------#    
        # # if 2 X Attack have been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
        else:
            None  

        #cool trainer M has 64/256 chance to use an X Attack (item id 63 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_items:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use x attack')
            trainer_action_details["item_id"] = 63 # X attack #hyper potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def erika_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------erika specific logic--------------------------------------------------#    
        # # if 1 super potion has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  

        #erika has 128/256 chance to use a super potion if her active pokemons health is below 10% (item id 18 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=127 and not attacker.prevent_items and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.10:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 18 # super potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def giovanni_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------giovanni specific logic--------------------------------------------------#    
        # # if 1 guard spec. has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  

        #giovanni has 64/256 chance to use a gaurd spec (item id 53 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_items:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 53 # guard spec
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)

    def koga_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------koga specific logic--------------------------------------------------#    
        # # if 2 x attack have been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
        else:
            None  

        #koga has 64/256 chance to use an x attack (item id 63 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_items:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 63 # x attack
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def lance_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------lance specific logic--------------------------------------------------#    
        # # if 1 hyper potion has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  

        #lance has a 128/256 chance to use a hyper potion if the active pokemons health is below 20% (item id 17 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=127 and not attacker.prevent_items and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.20:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 17 # hyper potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def ltsurge_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------lt surge specific logic--------------------------------------------------#    
        # # if 1 x speed has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  

        #lt surge has a 64/256 chance to use a x speed (item id 65 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_items:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 65 # x speed
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def misty_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------misty specific logic--------------------------------------------------#    
        # # if 1 x defend has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  

        #misty has a 64/256 chance to use a x defend (item id 64 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_items:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 64 # x defend
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def sabrina_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------sabrina specific logic--------------------------------------------------#    
        # # if 1hyper potion has been used on the active pokemon, set prevent items = True
        if attacker.activepokemon.item_counter == 1:
            attacker.prevent_items = True
        else:
            None  

        #sabrina has a 64/256 chance to use a hyper potion if the active pokemon health is below 10% (item id 64 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_items and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.10:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 2:
            print('need to implement logic to use super potion')
            trainer_action_details["item_id"] = 17 # hyper potion
            trainer_action_details["item_target_party_order"] = 1
            self.this_turn_items[attacker.id] = trainer_action_details
            
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
            low_priority_moves = []  # Moves disfavored by Modification 1 or 3
            high_priority_moves = []  # Moves favored by Modifications 2 or 3

            for move_id in attacker.activepokemon.moves_cur.keys():
                defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
                if defender.activepokemon.types[1] == None:
                    defender_type2_effectiveness = 1.00
                else:
                    defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
                if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                    low_priority_moves += [move_id]
                elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                    high_priority_moves += [move_id]
                else:
                    None
            
            if len(high_priority_moves) !=0:
                priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
            else:
                priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
                
            priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def juggler_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------juggler specific logic--------------------------------------------------#    
        # # if active pokemon has been swapped 3 times set prevent swap = True
        if attacker.activepokemon.swap_counter == 3:
            attacker.prevent_swap = True
        else:
            None  

        #juggler has a 64/256 chance to swap (max 3 times per pokemon)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=63 and not attacker.prevent_swap and not len(attacker.bench) == 0:
            action = 1
        #if not swapping or using item, then use move
        else:
            action = 3
        
        #init the trainer action details
        trainer_action_details = {"action": action}

        if action == 1:
            print('need to implement logic to swap to next unfainted party member')
            trainer_action_details["swap_target_party_order"] = 2

            self.this_turn_swaps[attacker.id] = trainer_action_details
        else:
            # ------------------------------------------------------------------
            # Apply Modifications to Priorities
            # ------------------------------------------------------------------
            # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
            if defender.activepokemon.status_condition_active:
                low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
                priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            # ------------------------------------------------------------------
            # Select Moves with Minimum Priority
            # ------------------------------------------------------------------
            min_priority = min(priorities)
            valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
            valid_weights = [weights[moves.index(move)] for move in valid_moves]

            # ------------------------------------------------------------------
            # Decide on a Move
            # ------------------------------------------------------------------
            if len(valid_moves) == 0:
                # No valid moves, default to Struggle
                selected_move_id = 135  # Struggle move ID
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
                }
            else:
                # Select move based on weights
                selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
                trainer_action_details = {
                    "action": action,
                    "move_id": selected_move_id,
                    "move_details": attacker.activepokemon.moves_cur[selected_move_id]
                }

            # Save the trainer action
            self.this_turn_moves[attacker.id] = trainer_action_details

        self.this_turn_actions[attacker.id] = trainer_action_details
        print(self.this_turn_actions)
    
    def lorelei_decide_action(self, attacker, defender):
        import random
        # Get moves with available PP
        moves = [move_id for move_id, move_info in attacker.activepokemon.moves_cur.items() if move_info['pp'] > 0]
        base_weights = [63, 64, 63, 66]
        weights = base_weights[:len(moves)]
        priorities = [10 for _ in moves]  # Start with a default priority of 10 for each move

        # Define the lists of moves affected by modifications
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        #------------------------------------------------------------------start special logic------------------------------------------------------------------#
        #--------------------------------------------------lorelei specific logic--------------------------------------------------#    
        # # if 2 super potions have been used set prevent items = True
        if attacker.activepokemon.item_counter == 2:
            attacker.prevent_items = True
        else:
            None  

        #lorelei has a 128/256 chance to use super potion(item id 18 below)
        rand_action_value = random.randint(0,255)
        print(rand_action_value)
        if rand_action_value <=127 and not attacker.prevent_items and attacker.activepokemon.stats['hp']['current']/attacker.activepokemon.stats['hp']['start'] < 0.20:
            action = 2
        #if not swapping or using item, then use move
        else:
            action = 3

        #init the trainer action details
        trainer_action_details = {"action": action}

        # ------------------------------------------------------------------
        # Apply Modifications to Priorities
        # ------------------------------------------------------------------
        # Modification 1: Disfavor non damaging status moves if the defender already has a status condition
        if defender.activepokemon.status_condition_active:
            low_priority_moves = [52, 66, 77, 93, 94, 106, 117, 122, 131, 136, 152, 154]
            priorities = [priority + 5 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # Modification 2: favor specific moves on the second turn a pokemon is out
        if attacker.activepokemon.active_turn_counter == 1:
            high_priority_moves = [3,4,5,8,23,27,33,47,53,54,57,58,71,74,76,79,85,89,104,105,106,111,113,116,125,126,134,142,143,145,155,164]
            priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]

        # Modification 3: Disfavor or favor moves based on effectiveness or predetermined damage amounts
        low_priority_moves = []  # Moves disfavored by Modification 1 or 3
        high_priority_moves = []  # Moves favored by Modifications 2 or 3

        for move_id in attacker.activepokemon.moves_cur.keys():
            defender_type1_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[0])
            if defender.activepokemon.types[1] == None:
                defender_type2_effectiveness = 1.00
            else:
                defender_type2_effectiveness = self.checkTypeEffectiveness(attacker.activepokemon.moves_cur[move_id]['type'],defender.activepokemon.types[1])
            if defender_type1_effectiveness < 1.00 or defender_type2_effectiveness < 1.00:
                low_priority_moves += [move_id]
            elif defender_type1_effectiveness > 1.00 or defender_type2_effectiveness > 1.00:
                high_priority_moves += [move_id]
            else:
                None
        
        if len(high_priority_moves) !=0:
            priorities = [priority - 1 if move in high_priority_moves else priority for move, priority in zip(moves, priorities)]
        else:
            priorities = [priority - 5 if move == 139 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 4 if move in (35,99,88,114,128) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 3 if move == 48 and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            priorities = [priority - 2 if move in (1,2,6,7,9,10,11,12,13,14,15,16,17,18,19,21,22,24,25,26,28,30,31,32,34,35,36,37,38,39,40,41,42,43,44,45,46,48,50,51,55,56,59,60,61,62,63,64,65,67,68,69,70,72,75,78,80,81,82,88,89,90,91,92,95,96,97,98,99,100,101,102,103,108,109,110,112,114,115,118,119,120,121,123,124,127,128,129,132,133,135,137,139,141,142,144,146,148,149,150,151,153,156,157,158,159,160,161,163,165) and move not in low_priority_moves else priority for move, priority in zip(moves, priorities)]
            
        priorities = [priority + 1 if move in low_priority_moves else priority for move, priority in zip(moves, priorities)]

        # ------------------------------------------------------------------
        # Select Moves with Minimum Priority
        # ------------------------------------------------------------------
        min_priority = min(priorities)
        valid_moves = [move for move, priority in zip(moves, priorities) if priority == min_priority]
        valid_weights = [weights[moves.index(move)] for move in valid_moves]

        # ------------------------------------------------------------------
        # Decide on a Move
        # ------------------------------------------------------------------
        if len(valid_moves) == 0:
            # No valid moves, default to Struggle
            selected_move_id = 135  # Struggle move ID
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": {'type': 1, 'power': 50, 'accuracy': 100, 'pp': 999, 'damagecategory': 1}
            }
        else:
            # Select move based on weights
            selected_move_id = random.choices(valid_moves, weights=valid_weights, k=1)[0]
            trainer_action_details = {
                "action": action,
                "move_id": selected_move_id,
                "move_details": attacker.activepokemon.moves_cur[selected_move_id]
            }

        # Save the trainer action
        self.this_turn_moves[attacker.id] = trainer_action_details
        self.this_turn_actions[attacker.id] = trainer_action_details

        print(self.this_turn_actions)
    
    def move_priority_check(self, dict_):
        priorityMoves = {100: {"priority": 1}, 24: {"priority": -1}}
        for key,value in dict_.items():
            self.move_priorities[key] = priorityMoves.get(value, {}).get("priority", 0)
        if len(set(list(self.move_priorities.values()))) == 1:
            self.this_turn_move_priorities = False
        else:
            sorted_keys = sorted(self.move_priorities.keys(), key=lambda k: self.move_priorities[k], reverse=True)
            self.this_turn_move_priorities = {i + 1: key for i, key in enumerate(sorted_keys)}
    
    def speed_priority_check(self, dict_):
        import random     
        if len(set(list(dict_.values()))) == 1:
            keys = list(dict_.keys())
            random.shuffle(keys)  # Shuffle the keys
            self.this_turn_move_priorities = {i + 1: keys[i] for i in range(len(keys))}
        else:
            sorted_keys = sorted(dict_, key=dict_.get, reverse=True)
            self.this_turn_move_priorities = {i + 1: sorted_keys[i] for i in range(len(sorted_keys))}
    
    def accuracy_check(self,trainer_id):
        import math
        import random
        attacker = self.trainer1 if trainer_id == self.trainer1.id else self.trainer2
        defender = self.trainer2 if attacker == self.trainer1 else self.trainer1

        move_accuracy = self.this_turn_moves[trainer_id]["move_details"]["accuracy"]
        attacker_accuracy = attacker.activepokemon.stat_modifiers_cur['accuracy']['modifier']
        defender_evasion = defender.activepokemon.stat_modifiers_cur['evasiveness']['modifier']

        final_move_accuracy = max(1,math.floor(math.floor(255 * move_accuracy//100) * math.floor(attacker_accuracy/defender_evasion)))
        accuracy_check_value = random.randint(1,255) #should this be 0?


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

    def thirtythree_percent_odds(self):
        import math
        import random

        check_value = random.randint(0,255) #should this be 0?

        if check_value < 85:
            return True
        else:
            return False
    
    def ten_percent_odds(self):
        import math
        import random

        check_value = random.randint(0,255) #should this be 0?

        if check_value < 26:
            return True
        else:
            return False
        
    def checkTypeEffectiveness(self,atk_type,def_type):
        return self.type_chart[atk_type][def_type]
        
    def critical_check(self, trainer_id):
        import random
        attacker = self.trainer1 if trainer_id == self.trainer1.id else self.trainer2

        #generate check value
        critical_check_value = random.randint(0,255)

        # print(self.this_turn_moves[trainer_id])

        #checking for focus energy and dire hit as well as high critical hit moves (crabhammer, karate chop, razor leaf, slash)
        if not attacker.activepokemon.focus_energy_active == 1 and not self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
            critical_threshold = attacker.activepokemon.stats.get("speed").get("base")//2
        elif attacker.activepokemon.focus_energy_active == 1 and not self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
            critical_threshold = attacker.activepokemon.stats.get("speed").get("base")//8
        elif not attacker.activepokemon.focus_energy_active == 1 and self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
            critical_threshold = 8*attacker.activepokemon.stats.get("speed").get("base")//2
        elif attacker.activepokemon.focus_energy_active == 1 and self.this_turn_moves[trainer_id]['move_id'] in (25,70,102,121):
            critical_threshold = attacker.activepokemon.stats.get("speed").get("base")
        
        if critical_threshold > 255:
            critical_threshold = 255
        
        if critical_check_value < critical_threshold:
            print('critical hit!')
            attacker.this_turn_move_critical = True
            return True
        else:
            print('not a critical hit')
            attacker.this_turn_move_critical = False
            return False
        
        # attacker.this_turn_move_critical = True
    
    def calc_damage(self,attacker, defender, trainer_id):
        import math
        import random

        attacking_move_type_id = self.this_turn_moves[trainer_id]['move_details']['type']
        attacking_move_id = self.this_turn_moves[trainer_id]['move_id']

        stab = 1.5 if attacking_move_type_id in attacker.activepokemon.types else 1.0

        #critical hit
        # self.critical_check(trainer_id) #fe_or_dh need to fix this
        
        #types effectiveness
        type1_effectiveness = self.checkTypeEffectiveness(attacking_move_type_id,defender.activepokemon.types[0])
        if defender.activepokemon.types[1] == None:
            type2_effectiveness = 1.0
        else:
            type2_effectiveness = self.checkTypeEffectiveness(attacking_move_type_id,defender.activepokemon.types[1])
        
        if int(type1_effectiveness) == 0 or int(type2_effectiveness) == 0:
            damage = False
            critical_damage = False
        
        if self.this_turn_moves[trainer_id]['move_details']['damagecategory'] == 1:
            print('move category 1 and critical 1')
            attack = attacker.activepokemon.stats.get("attack").get("current")
            critical_attack = attacker.activepokemon.stats.get("attack").get("start")
            if self.reflect_active:
                defense = defender.activepokemon.stats.get("defense").get("current") * 2
                critical_defense = defender.activepokemon.stats.get("defense").get("start")
            else:
                defense = defender.activepokemon.stats.get("defense").get("current")
                critical_defense = defender.activepokemon.stats.get("defense").get("start")
        elif self.this_turn_moves[trainer_id]['move_details']['damagecategory'] == 2:
            print('move category 2 and critical 1')
            attack = attacker.activepokemon.stats.get("special").get("current")
            critical_attack = attacker.activepokemon.stats.get("special").get("start")
            if self.light_screen_active:
                defense = defender.activepokemon.stats.get("special").get("current") * 2
                critical_defense = defender.activepokemon.stats.get("special").get("start")
            else:
                defense = defender.activepokemon.stats.get("special").get("current")
                critical_defense = defender.activepokemon.stats.get("special").get("start")

        #if the attack is explosion or self-destruct, halve the defense and round down
        if attacking_move_id in (41,115):
            defense = max(1,defense//2)
            critical_defense = max(1,critical_defense//2)
        
        #if either the attack or dense stat > 255, divide both by 4 and round down
        if attack > 255 or defense > 255:
            attack = attack//4
            critical_attack = critical_attack//4
            defense = defense//4
            critical_defense = critical_defense//4
        
        #need to account for attack/defense being 0 with round down errors
        attack = max(1,attack)
        critical_attack = max(1,critical_attack)
        defense = max(1,defense)
        critical_defense = max(1,critical_defense)

        # Random modifier for damage calculation
        randomint = random.randint(217, 255) / 255.0

        #check if move not effective against opponent types
        if type1_effectiveness == 0 or type2_effectiveness == 0:
            damage = 0
            critical_damage = 0
            print('selected move has no effect on opponent')
        #inflict damage = attacker level
        elif attacking_move_id in (88,114): 
            damage = attacker.activepokemon.level
            critical_damage = ((2 * attacker.activepokemon.level) + 5)//(attacker.activepokemon.level + 5) * attacker.activepokemon.level
            print('level damage')
        #inflict 50%-150% of attacker level
        elif attacking_move_id == 99: 
            damage = math.floor(attacker.activepokemon.level * random.uniform(0.5, 1.5))
            critical_damage = math.floor(((2 * attacker.activepokemon.level) + 5)//(attacker.activepokemon.level + 5) * attacker.activepokemon.level * random.uniform(0.5, 1.5))
        #inflict 40 hp damage
        elif attacking_move_id == 35:
            damage = 40
            critical_damage = 40
        #inflict 20 hp damage
        elif attacking_move_id == 128:
            damage = 20
            critical_damage = 20
        else:
            critical_damage = ((((((float(2.0) * float(attacker.activepokemon.level) * float(2.0))//float(5)) + float(2)) * float(self.this_turn_moves[trainer_id]['move_details']['power']) * float(attack) // float(defense)) // float(50)) + float(2)) * float(stab) * float(type1_effectiveness) * float(type2_effectiveness) * (float(randomint))
            damage = ((((((float(2.0) * float(attacker.activepokemon.level) * float(1.0))//float(5)) + float(2)) * float(self.this_turn_moves[trainer_id]['move_details']['power']) * float(attack) // float(defense)) // float(50)) + float(2)) * float(stab) * float(type1_effectiveness) * float(type2_effectiveness) * (float(randomint))
        print(f'damage = {int(damage)}.')
        if defender.activepokemon.stats.get("hp").get("current") < damage:
            damage = defender.activepokemon.stats.get("hp").get("current")
        if defender.activepokemon.stats.get("hp").get("current") < critical_damage:
            critical_damage = defender.activepokemon.stats.get("hp").get("current")
        return [int(damage),int(critical_damage)]
    
    def execute_swaps(self):
        if len(self.this_turn_swaps.keys()) == 0:
            #must increase the swapped pokemons .sswap_counter attribute, which is used by juggler to calc if he can keep swapping
            
            print('No swaps')

    def execute_items(self):
        if len(self.this_turn_items.keys()) == 0:
            #must increase active pokemon .item_counter attribute, many trainers use this to determine if they can keep using moves
            print('No items')
    
############################################################################### Attack Supporting Functions ###############################################################################
    def applyDamage(self,attacker,defender,damageAmt):
        print(f'{attacker.activepokemon.id} inflicted {damageAmt} on {defender.activepokemon.id}, who has {defender.activepokemon.stats.get("hp").get("current")} hp')
        #if the amount of damage is greater or equal to defender current hp, knock it out
        if defender.activepokemon.stats.get("hp").get("current") < damageAmt:
            defender.activepokemon.stats['hp']['current'] = 0
            defender.activepokemon.concious = False
            print(f'{defender.activepokemon.id} knocked out!')
        #if the amount of damage is less than defender current hp, find the difference and set the new hp
        elif defender.activepokemon.stats.get("hp").get("current") > damageAmt:
            difference = defender.activepokemon.stats.get("hp").get("current") - damageAmt
            defender.activepokemon.stats['hp']['current'] = difference
        return

    def restoreHealth(self,target,amt):
        if target.stats['hp']['current'] + amt > target.stats['hp']['start']:
            amt = target.stats['hp']['start'] - target.stats['hp']['current']
        target.stats['hp']['current'] += amt
        print(f'{target.id} healed {amt} hp')

############################################################################### Attack Functions ###############################################################################
    
    def useAbsorb(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Absorb')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        if not damage:
            print('move has no effect on opponent')
            return
        restoreamt = damage//2
        self.applyDamage(attacker,defender,damage)
        self.restoreHealth(attacker.activepokemon,restoreamt)

    def useAcid(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Acid')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        stat_lower = self.thirtythree_percent_odds()
        if not stat_lower:
            return
        else:
            defender.activepokemon.update_stat("special","decrease")
    
    def useAcidArmor(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Acid-Armor')
        attacker.activepokemon.update_stat("defense","increase")
        attacker.activepokemon.update_stat("defense","increase")
    
    def useAgility(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Agility')
        attacker.activepokemon.update_stat("speed","increase")
        attacker.activepokemon.update_stat("speed","increase")

    def useAmnesia(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Amnesia')
        attacker.activepokemon.update_stat("special","increase")
        attacker.activepokemon.update_stat("special","increase")

    def useAuroraBeam(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Aurora-Beam')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        stat_lower = self.thirtythree_percent_odds()
        if not stat_lower:
            return
        else:
            defender.activepokemon.update_stat("attack","decrease")
    
    def useBarrage(self,attacker,defender,trainer_id):
        import random
        print(f'{attacker.id} used Barrage')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        attackloopcount = random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for attackloop in range(0,attackloopcount):
            if attackloop == 0 and critical:
                damage = self.calc_damage(attacker,defender,trainer_id)[1]
            else:
                damage = self.calc_damage(attacker,defender,trainer_id)[0]
            if defender.activepokemon.stats.get("hp").get("current") < damage:
                damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker,defender,damage)
        print(f'move hit {attackloopcount} times')

    def useBarrier(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Barrier')
        attacker.activepokemon.update_stat("defense","increase")
        attacker.activepokemon.update_stat("defense","increase")

#need to address bide    
    # def useBide(self,attacker,defender,trainer_id):
    #     print(f'{attacker.id} used Bide')
    #     if attacker.activepokemon.bide_hits_taken < 2:
    #         print(f'{attacker.activepokemon.id} takes the bide')
    #     else:
    #         damage = attacker.activepokemon.bide_taken_damage
    #     self.applyDamage(attacker,defender,damage)
    #     attacker.activepokemon.bide_taken_damage = 0
    #     attacker.activepokemon.bide_hits_taken = False
    #     print(f'{attacker.activepokemon.id} unleashes bide for ')
    
    def useBind(self,attacker,defender,trainer_id):
        import random
        print(f'{attacker.id} used Bind')
        if defender.activepokemon.arena_trapped:
            print('Bind has no effect')
            return
        else:
            bind_length = random.randint(4,5)
            defender.activepokemon.arena_trapped = True
            defender.activepokemon.arena_trap_remaining_turns = bind_length

    def useBite(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Bite')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        flinch = self.ten_percent_odds()
        if not flinch:
            return
        else:
            defender.activepokemon.flinch_flag = flinch
    
    def useBlizzard(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Blizzard')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        if defender.activepokemon.status_condition_active:
            return
        freeze = self.ten_percent_odds()
        if not freeze:
            return
        else:
            print('opponent is frozen!')
            defender.activepokemon.status_condition_active = freeze
            defender.activepokemon.status_condition = 'frozen'
    
    def useBodySlam(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Body-Slam')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        if defender.activepokemon.status_condition_active:
            return
        paralyze = self.ten_percent_odds()
        if not paralyze:
            return
        else:
            print('opponent is paralyzed!')
            defender.activepokemon.status_condition_active = paralyze
            defender.activepokemon.status_condition = 'paralyzed'
    
    def useBoneClub(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Bone-Club')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        flinch = self.ten_percent_odds()
        if not flinch:
            return
        else:
            defender.activepokemon.flinch_flag = flinch
    
    def useBonemerang(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Bonemerang')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        attackloopcount = 2
        for attackloop in range(0,attackloopcount):
            if attackloop == 0 and critical:
                damage = self.calc_damage(attacker,defender,trainer_id)[1]
            else:
                damage = self.calc_damage(attacker,defender,trainer_id)[0]
            if defender.activepokemon.stats.get("hp").get("current") < damage:
                damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker,defender,damage)
        print(f'move hit {attackloopcount} times')
    
    def useBubble(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Bubble')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        stat_lower = self.thirtythree_percent_odds()
        if not stat_lower:
            return
        else:
            defender.activepokemon.update_stat("speed","decrease")
    
    def useBubbleBeam(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used BubbleBeam')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        stat_lower = self.thirtythree_percent_odds()
        if not stat_lower:
            return
        else:
            defender.activepokemon.update_stat("speed","decrease")

#comeback to clamp    
    # def useClamp(self,attacker,defender,trainer_id):
    #     print(f'{attacker.id} used Clamp')
    #     if defender.activepokemon.arena_trapped:
    #         print('Clamp has no effect')
    #         return
    #     else:
    #         trap_length = random.randint(4,5)
    #         defender.activepokemon.arena_trapped = True
    #         defender.activepokemon.arena_trap_remaining_turns = trap_length

    def useCometPunch(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Comet-Punch')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        attackloopcount =  random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for attackloop in range(0,attackloopcount):
            if attackloop == 0 and critical:
                damage = self.calc_damage(attacker,defender,trainer_id)[1]
            else:
                damage = self.calc_damage(attacker,defender,trainer_id)[0]
            if defender.activepokemon.stats.get("hp").get("current") < damage:
                damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker,defender,damage)
        print(f'move hit {attackloopcount} times')
    
    def useConfuseRay(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Confuse-Ray')
        if defender.activepokemon.confused:
            print('opponent already confused')
            return
        else:
            defender.activepokemon.confused = True
    
    def useConfusion(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Confusion')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        if defender.activepokemon.confused:
            return
        confusion = self.ten_percent_odds()
        if not confusion:
            return
        else:
            defender.activepokemon.confused = True

    def useConstrict(self,attacker,defender,trainer_id):
        print(f'{attacker.id} used Constrict')
        critical = self.critical_check(trainer_id) #fe_or_dh need to fix this
        if not critical:
            damage = self.calc_damage(attacker,defender,trainer_id)[0]
        else:
            damage = self.calc_damage(attacker,defender,trainer_id)[1]
        self.applyDamage(attacker,defender,damage)
        stat_lower = self.thirtythree_percent_odds()
        if not stat_lower:
            return
        else:
            defender.activepokemon.update_stat("speed","decrease")
    
#come back to this
    # def useConversion():

    def useCrabhammer(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Crabhammer')
        critical = self.high_critical_check(trainer_id)
        damage = self.calc_damage(attacker, defender, trainer_id)[critical]
        self.applyDamage(attacker, defender, damage)

    def useCut(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Cut')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)

    def useDefenseCurl(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Defense Curl')
        attacker.activepokemon.update_stat("defense", "increase")

    def useDig(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Dig')
        if not attacker.activepokemon.digging:
            attacker.activepokemon.digging = True
            print(f'{attacker.id} burrowed underground!')
        else:
            attacker.activepokemon.digging = False
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            if defender.activepokemon.underground:
                damage *= 2
            self.applyDamage(attacker, defender, damage)

    def useDisable(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Disable')
        if defender.activepokemon.last_move:
            defender.activepokemon.disabled_move = defender.activepokemon.last_move
            defender.activepokemon.disable_timer = random.randint(2, 5)
            print(f'{defender.id} is disabled!')

    def useDizzyPunch(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Dizzy Punch')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        if self.ten_percent_odds():
            defender.activepokemon.status_condition = 'confused'
            print(f'{defender.id} is confused!')

    def useDoubleKick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Double Kick')
        for _ in range(2):
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)

    def useDoubleSlap(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Double Slap')
        hit_count = random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for _ in range(hit_count):
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)
        print(f'Move hit {hit_count} times')

    def useDoubleTeam(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Double Team')
        attacker.activepokemon.update_stat("evasion", "increase")

    def useDoubleEdge(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Double-Edge')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        recoil = damage // 3
        self.applyDamage(attacker, attacker, recoil)
        print(f'{attacker.id} took recoil damage!')

    def useDragonRage(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Dragon Rage')
        self.applyDamage(attacker, defender, 40)

    def useDreamEater(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Dream Eater')
        if defender.activepokemon.status_condition == 'sleep':
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)
            self.healDamage(attacker, damage // 2)
        else:
            print('But it failed!')

    def useDrillPeck(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Drill Peck')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)

    def useEarthquake(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Earthquake')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        if defender.activepokemon.underground:
            damage *= 2
        self.applyDamage(attacker, defender, damage)

    def useEggBomb(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Egg Bomb')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)

    def useEmber(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Ember')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        if self.ten_percent_odds():
            defender.activepokemon.status_condition = 'burned'
            print(f'{defender.id} was burned!')

    def useExplosion(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Explosion')
        damage = self.calc_damage(attacker, defender, trainer_id)[0] * 2
        self.applyDamage(attacker, defender, damage)
        self.applyDamage(attacker, attacker, attacker.activepokemon.hp)
        print(f'{attacker.id} fainted!')

    def useFireBlast(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fire Blast')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        if self.ten_percent_odds():
            defender.activepokemon.status_condition = 'burned'
            print(f'{defender.id} was burned!')

    def useFirePunch(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fire Punch')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        if self.ten_percent_odds():
            defender.activepokemon.status_condition = 'burned'
            print(f'{defender.id} was burned!')

    def useFireSpin(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fire Spin')
        if defender.activepokemon.arena_trapped:
            print('Fire Spin has no effect')
            return
        else:
            spin_length = random.randint(4,5)
            defender.activepokemon.arena_trapped = True
            defender.activepokemon.arena_trap_remaining_turns = spin_length
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)
    
    def useFissure(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fissure')
        if self.one_hit_ko_check(attacker, defender, trainer_id):
            print("It's a one-hit KO!")
            defender.activepokemon.stats["hp"]["current"] = 0
        else:
            print('Fissure missed!')
    
    def useFlamethrower(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Flamethrower')
        critical = self.critical_check(trainer_id)
        damage = self.calc_damage(attacker, defender, trainer_id)[1] if critical else self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        burn = self.ten_percent_odds()
        if burn:
            print('Opponent is burned!')
            defender.activepokemon.status_condition_active = burn
            defender.activepokemon.status_condition = 'burned'
    
    def useFlash(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Flash')
        defender.activepokemon.update_stat("accuracy", "decrease")
    
    def useFly(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fly')
        if not attacker.activepokemon.flying:
            attacker.activepokemon.flying = True
            print(f'{attacker.id} flew up high!')
        else:
            attacker.activepokemon.flying = False
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)
    
    def useFocusEnergy(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Focus Energy')
        attacker.activepokemon.critical_boost = True
    
    def useFuryAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fury Attack')
        hit_count = random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for _ in range(hit_count):
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)
        print(f'Move hit {hit_count} times')
    
    def useFurySwipes(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Fury Swipes')
        hit_count = random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for _ in range(hit_count):
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
            self.applyDamage(attacker, defender, damage)
        print(f'Move hit {hit_count} times')
    
    def useGlare(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Glare')
        defender.activepokemon.status_condition_active = True
        defender.activepokemon.status_condition = 'paralyzed'
    
    def useGrowl(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Growl')
        defender.activepokemon.update_stat("attack", "decrease")
    
    def useGrowth(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Growth')
        attacker.activepokemon.update_stat("attack", "increase")
        attacker.activepokemon.update_stat("special", "increase")
    
    def useGuillotine(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Guillotine')
        if self.one_hit_ko_check(attacker, defender, trainer_id):
            print("It's a one-hit KO!")
            defender.activepokemon.stats["hp"]["current"] = 0
        else:
            print('Guillotine missed!')
    
    def useGust(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Gust')
        damage = self.calc_damage(attacker, defender, trainer_id)[0]
        if defender.activepokemon.flying:
            damage *= 2
            print("It's super effective against flying Pokémon!")
        self.applyDamage(attacker, defender, damage)

    def useHarden(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Harden')
        attacker.activepokemon.update_stat("defense", "increase")

    def useHaze(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Haze')
        # Reset all stats for both Pokemon
        for stat in ["attack", "defense", "speed", "special"]:
            attacker.activepokemon.reset_stat(stat)
            defender.activepokemon.reset_stat(stat)

    def useHeadbutt(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Headbutt')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 30% chance to cause flinching
        flinch_chance = random.random() < 0.3
        if flinch_chance:
            defender.activepokemon.apply_status("flinch")

    def useHighJumpKick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used High-Jump-Kick')
        # Check if move hits (assuming accuracy check is done elsewhere)
        hit = self.accuracy_check(attacker, defender, trainer_id)
        if hit:
            critical = self.critical_check(trainer_id)
            if not critical:
                damage = self.calc_damage(attacker, defender, trainer_id)[0]
            else:
                damage = self.calc_damage(attacker, defender, trainer_id)[1]
            self.applyDamage(attacker, defender, damage)
        else:
            # If move misses, user takes damage equal to half their max HP
            recoil_damage = attacker.activepokemon.stats.get("hp").get("max") // 2
            print(f'{attacker.id} missed and crashed!')
            self.applyDamage(attacker, attacker, recoil_damage)

    def useHornAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Horn-Attack')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useHornDrill(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Horn-Drill')
        # Check if defender is immune (higher level or ghost-type)
        if defender.activepokemon.level > attacker.activepokemon.level:
            print("But it failed!")
            return
        # Horn Drill has low accuracy (30% in Gen 1)
        hit_chance = random.random() < 0.3
        if hit_chance:
            # One-hit KO if it hits
            damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker, defender, damage)
        else:
            print("But it missed!")

    def useHydroPump(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Hydro-Pump')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useHyperBeam(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Hyper-Beam')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # User must recharge next turn
        attacker.activepokemon.apply_status("recharging")

    def useHyperFang(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Hyper-Fang')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to cause flinching in Gen 1
        flinch_chance = random.random() < 0.1
        if flinch_chance:
            defender.activepokemon.apply_status("flinch")

    def useHypnosis(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Hypnosis')
        # Check if move hits (Hypnosis has 60% accuracy in Gen 1)
        hit_chance = random.random() < 0.6
        if hit_chance:
            defender.activepokemon.apply_status("sleep")
        else:
            print("But it missed!")

    def useIceBeam(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Ice-Beam')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to freeze in Gen 1
        freeze_chance = random.random() < 0.1
        if freeze_chance:
            defender.activepokemon.apply_status("freeze")

    def useIcePunch(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Ice-Punch')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to freeze in Gen 1
        freeze_chance = random.random() < 0.1
        if freeze_chance:
            defender.activepokemon.apply_status("freeze")

    def useJumpKick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Jump-Kick')
        # Check if move hits (assuming accuracy check is done elsewhere)
        hit = self.accuracy_check(attacker, defender, trainer_id)
        if hit:
            critical = self.critical_check(trainer_id)
            if not critical:
                damage = self.calc_damage(attacker, defender, trainer_id)[0]
            else:
                damage = self.calc_damage(attacker, defender, trainer_id)[1]
            self.applyDamage(attacker, defender, damage)
        else:
            # If move misses, user takes damage equal to half their max HP
            recoil_damage = attacker.activepokemon.stats.get("hp").get("max") // 2
            print(f'{attacker.id} missed and crashed!')
            self.applyDamage(attacker, attacker, recoil_damage)

    def useKarateChop(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Karate-Chop')
        # Force critical hit check with higher ratio
        # In Gen 1, Karate Chop has a critical hit ratio of 8/24 instead of 1/24
        critical = random.random() < (8/24)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
            print("A critical hit!")
        self.applyDamage(attacker, defender, damage)

    def useKinesis(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Kinesis')
        defender.activepokemon.update_stat("accuracy", "decrease")

    def useLeechLife(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Leech-Life')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        if not damage:
            print('move has no effect on opponent')
            return
        self.applyDamage(attacker, defender, damage)
        # Recover half the damage dealt
        restore_amt = damage // 2
        if restore_amt > 0:
            self.restoreHealth(attacker, restore_amt)

    def useLeechSeed(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Leech-Seed')
        # Check if the defender is already seeded or is a grass type (immune in Gen 1)
        if defender.activepokemon.has_status("seeded") or "grass" in defender.activepokemon.type:
            print("But it failed!")
            return
        # Apply seeded status effect
        defender.activepokemon.apply_status("seeded")
        defender.activepokemon.seeded_by = attacker.id

    def useLeer(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Leer')
        defender.activepokemon.update_stat("defense", "decrease")

    def useLick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Lick')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 30% chance to paralyze in Gen 1
        paralyze_chance = random.random() < 0.3
        if paralyze_chance:
            if not "ghost" in defender.activepokemon.type:  # Ghost types are immune to paralysis in Gen 1
                defender.activepokemon.apply_status("paralysis")

    def useLightScreen(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Light-Screen')
        # Set up light screen effect for 5 turns
        attacker.activepokemon.apply_status("light_screen")
        attacker.activepokemon.light_screen_turns = 5

    def useLovelyKiss(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Lovely-Kiss')
        # Check if move hits (Lovely Kiss has 75% accuracy in Gen 1)
        hit_chance = random.random() < 0.75
        if hit_chance:
            defender.activepokemon.apply_status("sleep")
        else:
            print("But it missed!")

    def useLowKick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Low-Kick')
        # In Gen 1, Low Kick is just a normal damage move with no weight consideration
        # In later gens, damage is based on opponent's weight
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useMeditate(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Meditate')
        attacker.activepokemon.update_stat("attack", "increase")

    def useMegaDrain(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Mega-Drain')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        if not damage:
            print('move has no effect on opponent')
            return
        self.applyDamage(attacker, defender, damage)
        # Recover half the damage dealt
        restore_amt = damage // 2
        if restore_amt > 0:
            self.restoreHealth(attacker, restore_amt)

    def useMegaKick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Mega-Kick')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useMegaPunch(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Mega-Punch')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useMetronome(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Metronome')
        # List of all possible moves (excluding Metronome itself and a few others)
        all_moves = [move for move in dir(self) if move.startswith('use') and move != 'useMetronome' 
                    and move != 'useStruggle' and move != 'useTransform']
        
        # Select a random move
        random_move = random.choice(all_moves)
        print(f"Waggling a finger let it use {random_move[3:]}!")
        
        # Call the randomly selected move
        move_function = getattr(self, random_move)
        move_function(attacker, defender, trainer_id)

    def useMimic(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Mimic')
        if hasattr(defender, 'last_move_used') and defender.last_move_used:
            attacker.mimic_move = defender.last_move_used
            print(f'{attacker.id} copied {defender.last_move_used}!')
        else:
            print("But it failed!")

    def useMinimize(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Minimize')
        attacker.activepokemon.update_stat("evasion", "increase")
        attacker.activepokemon.update_stat("evasion", "increase")
        print(f'{attacker.id} shrunk itself down!')

    def useMirrorMove(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Mirror-Move')
        if hasattr(defender, 'last_move_used') and defender.last_move_used:
            move_name = defender.last_move_used
            print(f'{attacker.id} used {move_name}!')
            # Get the move function and call it
            move_function = getattr(self, f'use{move_name}')
            move_function(attacker, defender, trainer_id)
        else:
            print("But it failed!")

    def useMist(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Mist')
        attacker.activepokemon.apply_status("mist")
        print(f"{attacker.id} is shrouded in mist!")

    def useNightShade(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Night-Shade')
        # Damage equal to user's level
        damage = attacker.activepokemon.level
        self.applyDamage(attacker, defender, damage)

    def usePayDay(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Pay-Day')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # Calculate money earned (level * 5 in Gen 1)
        money = attacker.activepokemon.level * 5
        if hasattr(attacker, 'money_earned'):
            attacker.money_earned += money
        else:
            attacker.money_earned = money
        print(f"Coins scattered everywhere!")

    def usePeck(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Peck')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def usePetalDance(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Petal-Dance')
        # Determine number of turns (2-3 in Gen 1)
        if not hasattr(attacker.activepokemon, 'petal_dance_turns'):
            attacker.activepokemon.petal_dance_turns = random.randint(2, 3)
            attacker.activepokemon.petal_dance_count = 0
        
        attacker.activepokemon.petal_dance_count += 1
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        
        # Check if Petal Dance is complete
        if attacker.activepokemon.petal_dance_count >= attacker.activepokemon.petal_dance_turns:
            attacker.activepokemon.apply_status("confusion")
            print(f"{attacker.id} became confused due to fatigue!")
            delattr(attacker.activepokemon, 'petal_dance_turns')
            delattr(attacker.activepokemon, 'petal_dance_count')

    def usePinMissile(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Pin-Missile')
        critical = self.critical_check(trainer_id)
        hit_count = random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for hit in range(hit_count):
            if hit == 0 and critical:
                damage = self.calc_damage(attacker, defender, trainer_id)[1]
            else:
                damage = self.calc_damage(attacker, defender, trainer_id)[0]
            if defender.activepokemon.stats.get("hp").get("current") < damage:
                damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker, defender, damage)
        print(f'Hit {hit_count} times!')

    def usePoisonGas(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Poison-Gas')
        # Check if opponent is immune (Poison types in Gen 1)
        if "poison" in defender.activepokemon.type:
            print("But it had no effect!")
            return
        # 55% accuracy in Gen 1
        hit_chance = random.random() < 0.55
        if hit_chance:
            defender.activepokemon.apply_status("poison")
        else:
            print("But it missed!")

    def usePoisonPowder(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Poison-Powder')
        # Check if opponent is immune (Poison types in Gen 1)
        if "poison" in defender.activepokemon.type:
            print("But it had no effect!")
            return
        # 75% accuracy in Gen 1
        hit_chance = random.random() < 0.75
        if hit_chance:
            defender.activepokemon.apply_status("poison")
        else:
            print("But it missed!")

    def usePoisonSting(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Poison-Sting')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 20% chance to poison in Gen 1
        if random.random() < 0.2:
            if "poison" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("poison")

    def usePound(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Pound')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def usePsybeam(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Psybeam')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to confuse in Gen 1
        if random.random() < 0.1:
            defender.activepokemon.apply_status("confusion")

    def usePsychic(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Psychic')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 33% chance to lower Special in Gen 1
        if random.random() < 0.33:
            defender.activepokemon.update_stat("special", "decrease")

    def usePsywave(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Psywave')
        # Damage is between 50-150% of user's level
        damage_percent = random.randint(50, 150) / 100
        damage = int(attacker.activepokemon.level * damage_percent)
        if damage < 1:
            damage = 1
        self.applyDamage(attacker, defender, damage)

    def useQuickAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Quick-Attack')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useRage(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Rage')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # Apply rage status
        attacker.activepokemon.apply_status("rage")

    def useRazorLeaf(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Razor-Leaf')
        # Higher critical hit ratio (25% in Gen 1)
        critical = random.random() < 0.25
        if critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
            print("A critical hit!")
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)

    def useRazorWind(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Razor-Wind')
        if not hasattr(attacker.activepokemon, 'razor_wind_charging'):
            print(f'{attacker.id} whipped up a whirlwind!')
            attacker.activepokemon.razor_wind_charging = True
            return
        
        # Second turn, attack
        delattr(attacker.activepokemon, 'razor_wind_charging')
        # Higher critical hit ratio
        critical = random.random() < 0.25
        if critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
            print("A critical hit!")
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)

    def useRecover(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Recover')
        # Restore half of max HP
        max_hp = attacker.activepokemon.stats.get("hp").get("max")
        restore_amount = max_hp // 2
        self.restoreHealth(attacker, restore_amount)

    def useReflect(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Reflect')
        # Set up reflect for 5 turns
        attacker.activepokemon.apply_status("reflect")
        attacker.activepokemon.reflect_turns = 5
        print(f'A barrier was created!')

    def useRest(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Rest')
        # Put user to sleep for 2 turns
        attacker.activepokemon.apply_status("sleep")
        attacker.activepokemon.sleep_turns = 2
        # Fully restore HP
        max_hp = attacker.activepokemon.stats.get("hp").get("max")
        current_hp = attacker.activepokemon.stats.get("hp").get("current")
        restore_amount = max_hp - current_hp
        self.restoreHealth(attacker, restore_amount)
        print(f'{attacker.id} slept and became healthy!')

    def useRoar(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Roar')
        # In wild battles, ends the battle
        # In trainer battles, forces a switch
        if defender.is_wild:
            print(f'The wild {defender.activepokemon.name} fled!')
            self.battle_over = True
        else:
            # Force random switch
            print(f'{defender.id} was scared away!')
            # This would need to be implemented in the battle system
            self.force_switch(defender)

    def useRockSlide(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Rock-Slide')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 30% chance to cause flinching
        if random.random() < 0.3:
            defender.activepokemon.apply_status("flinch")

    def useRockThrow(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Rock-Throw')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useRollingKick(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Rolling-Kick')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 30% chance to cause flinching
        if random.random() < 0.3:
            defender.activepokemon.apply_status("flinch")

    def useSandAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sand-Attack')
        defender.activepokemon.update_stat("accuracy", "decrease")

    def useScratch(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Scratch')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useScreech(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Screech')
        # Sharply lowers Defense (by two stages in Gen 1)
        defender.activepokemon.update_stat("defense", "decrease")
        defender.activepokemon.update_stat("defense", "decrease")

    def useSeismicToss(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Seismic-Toss')
        # Damage equal to user's level
        damage = attacker.activepokemon.level
        self.applyDamage(attacker, defender, damage)

    def useSelfDestruct(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Self-Destruct')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # User faints
        attacker.activepokemon.stats["hp"]["current"] = 0
        print(f'{attacker.id} fainted!')

    def useSharpen(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sharpen')
        attacker.activepokemon.update_stat("attack", "increase")

    def useSing(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sing')
        # 55% accuracy in Gen 1
        hit_chance = random.random() < 0.55
        if hit_chance:
            defender.activepokemon.apply_status("sleep")
        else:
            print("But it missed!")

    def useSkullBash(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Skull-Bash')
        if not hasattr(attacker.activepokemon, 'skull_bash_charging'):
            print(f'{attacker.id} lowered its head!')
            attacker.activepokemon.update_stat("defense", "increase")
            attacker.activepokemon.skull_bash_charging = True
            return
        
        # Second turn, attack
        delattr(attacker.activepokemon, 'skull_bash_charging')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useSkyAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sky-Attack')
        if not hasattr(attacker.activepokemon, 'sky_attack_charging'):
            print(f'{attacker.id} is glowing!')
            attacker.activepokemon.sky_attack_charging = True
            return
        
        # Second turn, attack
        delattr(attacker.activepokemon, 'sky_attack_charging')
        # Higher critical hit ratio
        critical = random.random() < 0.25
        if critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
            print("A critical hit!")
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)
        
        # 30% chance to cause flinching
        if random.random() < 0.3:
            defender.activepokemon.apply_status("flinch")

    def useSlam(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Slam')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useSlash(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Slash')
        # Higher critical hit ratio (25% in Gen 1)
        critical = random.random() < 0.25
        if critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
            print("A critical hit!")
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        self.applyDamage(attacker, defender, damage)

    def useSleepPowder(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sleep-Powder')
        # 75% accuracy in Gen 1
        hit_chance = random.random() < 0.75
        if hit_chance:
            defender.activepokemon.apply_status("sleep")
        else:
            print("But it missed!")

    def useSludge(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sludge')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 30% chance to poison in Gen 1
        if random.random() < 0.3:
            if "poison" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("poison")

    def useSmog(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Smog')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 40% chance to poison in Gen 1
        if random.random() < 0.4:
            if "poison" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("poison")

    def useSmokescreen(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Smokescreen')
        defender.activepokemon.update_stat("accuracy", "decrease")

    def useSoftBoiled(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Soft-Boiled')
        # Restore half of max HP
        max_hp = attacker.activepokemon.stats.get("hp").get("max")
        restore_amount = max_hp // 2
        self.restoreHealth(attacker, restore_amount)

    def useSolarBeam(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Solar-Beam')
        if not hasattr(attacker.activepokemon, 'solar_beam_charging'):
            print(f'{attacker.id} took in sunlight!')
            attacker.activepokemon.solar_beam_charging = True
            return
        
        # Second turn, attack
        delattr(attacker.activepokemon, 'solar_beam_charging')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useSonicBoom(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Sonic-Boom')
        # Always inflicts 20 HP of damage
        damage = 20
        self.applyDamage(attacker, defender, damage)

    def useSpikeCanon(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Spike-Cannon')
        critical = self.critical_check(trainer_id)
        hit_count = random.choices([2, 3, 4, 5], weights=[37.5, 37.5, 12.5, 12.5], k=1)[0]
        for hit in range(hit_count):
            if hit == 0 and critical:
                damage = self.calc_damage(attacker, defender, trainer_id)[1]
            else:
                damage = self.calc_damage(attacker, defender, trainer_id)[0]
            if defender.activepokemon.stats.get("hp").get("current") < damage:
                damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker, defender, damage)
        print(f'Hit {hit_count} times!')

    def useSplash(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Splash')
        print('But nothing happened!')

    def useSpore(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Spore')
        # 100% accuracy in Gen 1
        defender.activepokemon.apply_status("sleep")

    def useStomp(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Stomp')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 30% chance to cause flinching
        if random.random() < 0.3:
            defender.activepokemon.apply_status("flinch")

    def useStrength(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Strength')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useStringShot(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used String-Shot')
        # Sharply lowers Speed (by two stages in Gen 1)
        defender.activepokemon.update_stat("speed", "decrease")
        defender.activepokemon.update_stat("speed", "decrease")

    def useStruggle(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Struggle')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # Recoil damage (1/4 of damage dealt in Gen 1)
        recoil = max(1, damage // 4)
        self.applyDamage(attacker, attacker, recoil)
        print(f'{attacker.id} is damaged by recoil!')

    def useStunSpore(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Stun-Spore')
        # Check if opponent is immune (ground types in later gens)
        # 75% accuracy in Gen 1
        hit_chance = random.random() < 0.75
        if hit_chance:
            defender.activepokemon.apply_status("paralysis")
        else:
            print("But it missed!")

    def useSubmission(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Submission')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # Recoil damage (1/4 of damage dealt in Gen 1)
        recoil = max(1, damage // 4)
        self.applyDamage(attacker, attacker, recoil)
        print(f'{attacker.id} is damaged by recoil!')

    def useSubstitute(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Substitute')
        # Check if user has enough HP (1/4 of max HP)
        max_hp = attacker.activepokemon.stats.get("hp").get("max")
        hp_cost = max_hp // 4
        if attacker.activepokemon.stats.get("hp").get("current") <= hp_cost:
            print("But it failed!")
            return
        
        # Create substitute
        self.applyDamage(attacker, attacker, hp_cost)
        attacker.activepokemon.substitute_hp = hp_cost
        attacker.activepokemon.has_substitute = True
        print(f'{attacker.id} created a substitute!')

    def useSuperFang(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Super-Fang')
        # Always takes off half of opponent's current HP
        damage = max(1, defender.activepokemon.stats.get("hp").get("current") // 2)
        self.applyDamage(attacker, defender, damage)

    def useSupersonic(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Supersonic')
        # 55% accuracy in Gen 1
        hit_chance = random.random() < 0.55
        if hit_chance:
            defender.activepokemon.apply_status("confusion")
        else:
            print("But it missed!")

    def useSurf(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Surf')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # In double battles, would hit both opponents

    def useSwift(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Swift')
        # Always hits, ignores accuracy and evasion
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useSwordsDance(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Swords-Dance')
        # Sharply raises Attack (by two stages in Gen 1)
        attacker.activepokemon.update_stat("attack", "increase")
        attacker.activepokemon.update_stat("attack", "increase")

    def useTackle(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Tackle')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useTailWhip(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Tail-Whip')
        defender.activepokemon.update_stat("defense", "decrease")

    def useTakeDown(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Take-Down')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # Recoil damage (1/4 of damage dealt in Gen 1)
        recoil = max(1, damage // 4)
        self.applyDamage(attacker, attacker, recoil)
        print(f'{attacker.id} is damaged by recoil!')

    def useTeleport(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Teleport')
        # In wild battles, allows escape
        if defender.is_wild:
            print(f'{attacker.id} teleported away!')
            self.battle_over = True
        else:
            print("But it failed!")

    def useThrash(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Thrash')
        # Determine number of turns (2-3 in Gen 1)
        if not hasattr(attacker.activepokemon, 'thrash_turns'):
            attacker.activepokemon.thrash_turns = random.randint(2, 3)
            attacker.activepokemon.thrash_count = 0
        
        attacker.activepokemon.thrash_count += 1
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        
        # Check if Thrash is complete
        if attacker.activepokemon.thrash_count >= attacker.activepokemon.thrash_turns:
            attacker.activepokemon.apply_status("confusion")
            print(f"{attacker.id} became confused due to fatigue!")
            delattr(attacker.activepokemon, 'thrash_turns')
            delattr(attacker.activepokemon, 'thrash_count')

    def useThunder(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Thunder')
        # 70% accuracy in Gen 1
        hit_chance = random.random() < 0.7
        if hit_chance:
            critical = self.critical_check(trainer_id)
            if not critical:
                damage = self.calc_damage(attacker, defender, trainer_id)[0]
            else:
                damage = self.calc_damage(attacker, defender, trainer_id)[1]
            self.applyDamage(attacker, defender, damage)
            # 10% chance to paralyze
            if random.random() < 0.1:
                if "electric" not in defender.activepokemon.type:
                    defender.activepokemon.apply_status("paralysis")
        else:
            print("But it missed!")

    def useThunderPunch(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Thunder-Punch')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to paralyze
        if random.random() < 0.1:
            if "electric" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("paralysis")

    def useThunderShock(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Thunder-Shock')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to paralyze
        if random.random() < 0.1:
            if "electric" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("paralysis")

    def useThunderWave(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Thunder-Wave')
        # No effect on ground types (though this wasn't true in Gen 1)
        if "electric" in defender.activepokemon.type:
            print("It doesn't affect electric types!")
            return
        # 100% accuracy in Gen 1 (immune to accuracy/evasion mods)
        defender.activepokemon.apply_status("paralysis")

    def useThunderbolt(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Thunderbolt')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # 10% chance to paralyze
        if random.random() < 0.1:
            if "electric" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("paralysis")

    def useToxic(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Toxic')
        # Check if opponent is immune (Poison types in Gen 1)
        if "poison" in defender.activepokemon.type:
            print("But it had no effect!")
            return
        # 85% accuracy in Gen 1
        hit_chance = random.random() < 0.85
        if hit_chance:
            defender.activepokemon.apply_status("toxic")
            # Initialize toxic counter
            defender.activepokemon.toxic_counter = 1
        else:
            print("But it missed!")

    def useTransform(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Transform')
        # Copy opponent's stats, types, and moves
        attacker.activepokemon.transformed = True
        attacker.activepokemon.transform_into = defender.activepokemon
        
        # Copy stats (except HP)
        for stat in ["attack", "defense", "speed", "special"]:
            attacker.activepokemon.stats[stat]["base"] = defender.activepokemon.stats[stat]["base"]
            attacker.activepokemon.stats[stat]["current"] = defender.activepokemon.stats[stat]["current"]
        
        # Copy types
        attacker.activepokemon.type = defender.activepokemon.type.copy()
        
        # Copy moves
        attacker.activepokemon.moves = defender.activepokemon.moves.copy()
        
        print(f'{attacker.id} transformed into {defender.activepokemon.name}!')

    def useTriAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Tri-Attack')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        
        # In Gen 1, Tri Attack doesn't have status effects
        # This is for later gens: 20% chance to cause paralysis, burn, or freeze
        if random.random() < 0.2:
            status_effect = random.choice(["paralysis", "burn", "freeze"])
            # Check type immunities
            if (status_effect == "paralysis" and "electric" not in defender.activepokemon.type) or \
            (status_effect == "burn" and "fire" not in defender.activepokemon.type) or \
            (status_effect == "freeze" and "ice" not in defender.activepokemon.type):
                defender.activepokemon.apply_status(status_effect)

    def useTwineedle(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Twineedle')
        critical = self.critical_check(trainer_id)
        
        # Attack hits twice
        for hit in range(2):
            if hit == 0 and critical:
                damage = self.calc_damage(attacker, defender, trainer_id)[1]
            else:
                damage = self.calc_damage(attacker, defender, trainer_id)[0]
            if defender.activepokemon.stats.get("hp").get("current") < damage:
                damage = defender.activepokemon.stats.get("hp").get("current")
            self.applyDamage(attacker, defender, damage)
        
        print(f'Hit 2 times!')
        
        # 20% chance to poison
        if random.random() < 0.2:
            if "poison" not in defender.activepokemon.type:
                defender.activepokemon.apply_status("poison")

    def useVineWhip(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Vine-Whip')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useViseGrip(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Vise-Grip')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useWaterGun(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Water-Gun')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useWaterfall(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Waterfall')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        # In Gen 1, Waterfall doesn't cause flinching
        # For later gens: 20% chance to cause flinching
        if random.random() < 0.2:
            defender.activepokemon.apply_status("flinch")

    def useWhirlwind(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Whirlwind')
        # In wild battles, ends the battle
        # In trainer battles, forces a switch
        if defender.is_wild:
            print(f'The wild {defender.activepokemon.name} fled!')
            self.battle_over = True
        else:
            # Force random switch
            print(f'{defender.id} was blown away!')
            # This would need to be implemented in the battle system
            self.force_switch(defender)

    def useWingAttack(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Wing-Attack')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)

    def useWithdraw(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Withdraw')
        attacker.activepokemon.update_stat("defense", "increase")

    def useWrap(self, attacker, defender, trainer_id):
        print(f'{attacker.id} used Wrap')
        critical = self.critical_check(trainer_id)
        if not critical:
            damage = self.calc_damage(attacker, defender, trainer_id)[0]
        else:
            damage = self.calc_damage(attacker, defender, trainer_id)[1]
        self.applyDamage(attacker, defender, damage)
        
        # In Gen 1, traps opponent for 2-5 turns
        if not hasattr(defender.activepokemon, 'wrapped'):
            wrap_turns = random.randint(2, 5)
            defender.activepokemon.wrapped = True
            defender.activepokemon.wrap_turns = wrap_turns
            defender.activepokemon.wrapped_by = attacker.id
            print(f'{defender.activepokemon.name} was wrapped by {attacker.id}!')
    
    def execute_move_generic(self, attacker, defender, trainer_id, move_id):
        """
        Generic move execution using the improved MoveEffects system.
        This replaces individual move methods with a centralized approach.
        """
        return self.move_effects.execute_move(attacker, defender, trainer_id, move_id)
    
################################################################################################################################################################################################################
    def execute_moves(self):
        import random
        self.move_priorities = {}
        self.speed_priorities = {}
        self.this_turn_move_priorities = {}
        accuracy = False
        #if there are no moves this turn, exit
        if len(self.this_turn_moves.keys()) == 0:
            print('No moves')
            self.this_turn_move_priorities = False
        #if there is only 1 move this turn, set the move priorities to that 1 trainer
        elif len(self.this_turn_moves.keys()) == 1:
            self.this_turn_move_priorities = {1: key for key in self.this_turn_moves.keys()}
        #if there is more than 1 move this turn, evaluate the priorities
        elif len(self.this_turn_moves.keys()) > 1:
            print('Moves!')
            self.move_priority_check({key: value['move_id'] for key, value in self.this_turn_moves.items()})
            #see if we need to do a speed check
            if not self.this_turn_move_priorities:
                self.speed_priority_check({trainer.id: trainer.activepokemon.stats['speed'].get("current") for trainer in [self.trainer1,self.trainer2]})
            else:
                print('dont need speed check')
        
        #if there is atleast 1 move being executed, loop through them.
        if self.this_turn_move_priorities:
            for priority, trainer_id in self.this_turn_move_priorities.items():
                #identify attacker and defender
                attacker = self.trainer1 if trainer_id == self.trainer1.id else self.trainer2
                defender = self.trainer2 if attacker == self.trainer1 else self.trainer1
                #determine attack physical/special/status
                damage_category = self.this_turn_moves[trainer_id]['move_details']['damagecategory']
                #evaluate accuracy in udf
                accuracy = self.accuracy_check(trainer_id)
                #if the move doesnt miss, determine damage and apply
                if accuracy:
                    #if damage will be inflicted then calculate it and apply, otherwise inflict status condition
                    if damage_category in (1,2):
                        print(f'trainer id {trainer_id} will use the move {self.this_turn_moves[trainer_id]['move_id']}')

                        ###################################################################################################################################################
                        #calc and apply damage
                        #############################
                        #if move will hit 2-5 times, determine how many then calc and apply each
                        if self.this_turn_moves[trainer_id]['move_id'] in (7,19,32,50,51,92,129):
                            attackloopcount = random.randint(2,5)
                            for attackloop in range(0,attackloopcount+1):
                                damage = self.calc_damage(trainer_id)
                                if defender.activepokemon.stats.get("hp").get("current") < damage:
                                    damage = defender.activepokemon.stats.get("hp").get("current")
                                self.applyDamage(attacker,defender,damage)
                            print(f'move hit {attackloopcount} times')
                        #otherwise just calc and apply damage
                        else:
                            damage = self.calc_damage(trainer_id)
                            if defender.activepokemon.stats.get("hp").get("current") < damage:
                                    damage = defender.activepokemon.stats.get("hp").get("current")
                            self.applyDamage(attacker,defender,damage)
                        
                        #if some health is recovered
                        #--------------------------------------------------------------------------#
                        if self.this_turn_moves[trainer_id]['move_id'] in (1,36,72,80):
                            restoreamt = damage//2
                            newhp = min(attacker.activepokemon.stats['hp']['current'] + restoreamt,attacker.activepokemon.stats['hp']['start'])
                            attacker.activepokemon.stats['hp']['current'] = newhp
                        else:
                            print('no health recovered')
                        
                        #if a move might lower a stat of the opponent
                        if self.this_turn_moves[trainer_id]['move_id'] in (2,6,16,17,22,98):
                            stat_lower = self.thirtythree_percent_odds()
                            if not stat_lower:
                                return
                            elif stat_lower and self.this_turn_moves[trainer_id]['move_id'] in (2,98):
                                defender.activepokemon.update_stat("special","decrease")
                            elif stat_lower and self.this_turn_moves[trainer_id]['move_id'] in (16,17,22):
                                defender.activepokemon.update_stat("speed","decrease")
                            elif stat_lower and self.this_turn_moves[trainer_id]['move_id'] in (6):
                                defender.activepokemon.update_stat("attack","decrease")

                    else:
                        damage = 0
                        print('damage category 3 need to implement ')
                    #if move restores 50% max health
                    if self.this_turn_moves[trainer_id]['move_id'] in (104,126):
                        restoreamt = attacker.activepokemon.stats['hp']['start']//2
                        newhp = min(attacker.activepokemon.stats['hp']['current'] + restoreamt,attacker.activepokemon.stats['hp']['start'])
                        attacker.activepokemon.stats['hp']['current'] = newhp

                        #checking to make sure health is restored as it should be - can delete this-#
                        print(attacker.activepokemon.stats['hp']['current'])
                        print(self.trainer1.activepokemon.stats['hp']['current'])
                        print(self.trainer2.activepokemon.stats['hp']['current'])
                        #---------------------------------------------------------------------------#
                    #otherwise restore 0 health
                    else:
                        None
                    #apply any arena effects if necessary
                    
                    #apply any status effects if necessary
                    #may lower opponent special defense
                    # if self.this_turn_moves[trainer_id]['move_id'] == 2:
                    #     stat_lower_check_value = random.randint(0,255)
                    #     if stat_lower_check_value <= 84:
                    #         if self.this_turn_moves[trainer_id]['move_id']:
                    #             defender.activepokemon.update_stat(stat_name, action)
                    # print(attacker.activepokemon.stat_modifiers_cur)
                    
                    #apply any stat changes if necessary
                    #drop the pp of the attacker's move

                else:
                    next
                #apply any lingering status effects
                #apply any lingering arena effects
    
    def take_turn(self):
        """Simulates a single turn in the battle."""
        print(f"Turn {self.turn} begins!\n")

        #reset turn attributes before taking turn
        # self.reset_turn_attributes()

        # Get active Pokémon
        trainer1_active_pokemon = self.trainer1.activepokemon
        trainer2_active_pokemon = self.trainer2.activepokemon

        trainers = [self.trainer1,self.trainer2]
        
        # decide turn action
        self.this_turn_actions = {}
        self.this_turn_swaps = {}
        self.this_turn_items = {}
        self.this_turn_moves = {}


        self.juggler_decide_action(self.trainer1,self.trainer2)

        # self.decide_trainer_actions(trainers)

        #execute swaps (order doesnt matter)
        self.execute_swaps()

        #execute items (order doesnt matter)
        self.execute_items()

        #execute moves (order DOES matter)
        self.execute_moves()

        self.turn +=1
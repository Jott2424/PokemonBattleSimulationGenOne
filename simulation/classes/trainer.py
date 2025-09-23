class Trainer:
    def __init__(self, id, team, items):
        self.id = id
        self.items = items

        #pokemon attributes, need to be updated after every turn
        self.team_st = team
        self.team_cur = team
        self.activepokemon = None
        self.faintedpokemon = None
        self.bench = None
        self.fainted = []

        #turn attributes (these need reset to None before and after each move)
        self.this_turn_action = None
        self.this_turn_move_critical = False
        self.this_turn_fainted = False
        self.this_turn_priority = None
        self.this_turn_accuracy = True

        #turn logic attributes
        self.prevent_swap = False
        self.prevent_items = False
        self.activepokemon_itemusedcounter = 0




    
    def __repr__(self):
        return (f"ID = {self.id}, Team = {self.team_cur}, Items = {self.items}")




    
    def reset_turn_attributes(self):
        self.this_turn_action = None
        self.this_turn_move = None




    def get_activePokemon(self):
        #cycle through pokemon until we find who is partyorder 1
        active_pokemon = next((p for p in self.team_cur if p.partyorder_cur == 1 and p.concious == True), None)
        # print(active_pokemon) #debugging
        active_pokemon.flag_active = 1
        self.activepokemon = active_pokemon
        # print(self.activepokemon) #debugging
        self.bench = [pokemon for pokemon in self.team_cur if pokemon != self.activepokemon]
        self.activepokemon_itemsusedcounter = 0
        return active_pokemon

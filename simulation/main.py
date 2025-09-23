####################################
# imports
####################################
# from classes import battle, trainer, pokemon, move
import HelperFunctions as hf
import json
import numpy as np

####################################
# config & variables
####################################
with open("config.json") as f:
    config = json.load(f)

seed     = config["seed"]
host     = config["databaseCredentials"]["host"]
port     = config["databaseCredentials"]["port"]
database = config["databaseCredentials"]["database"]
username = config["databaseCredentials"]["username"]
password = config["databaseCredentials"]["password"]

####################################
# prep
####################################
battles_to_sim = hf.get_battles_to_sim_pks(host,port,database,username,password)
if not battles_to_sim:
    print('No battles found to sim')
    exit
####################################
# loop through battles
####################################
for battlenum in battles_to_sim:
    print(f'Starting battle #{battlenum} using seed {seed}.')

    #  check if battle has been simulated with this seed already
    battle_already_simulated = hf.check_battle_already_simulated(host,port,database,username,password,battlenum,seed)
    if not battle_already_simulated:
        #get Trainers in this battle
        trainersInBattle = hf.get_trainers_in_battle(host,port,database,username,password,battlenum)
        print(f'Trainers in battle #{battlenum} are {trainersInBattle[0]}')

        #get each trainers pokemon and init them
        # trainer1 = trainer()
#     trainer1_pokemon = init_trainerTeams(get_pokemonInBattle(credentials, trainersInBattle[0]))
#     trainer2_pokemon = init_trainerTeams(get_pokemonInBattle(credentials, trainersInBattle[1]))

#     #init each trainer
#     trainer1 = Trainer(trainersInBattle[0],trainer1_pokemon,[])
#     # print(trainer1)
#     trainer2 = Trainer(trainersInBattle[1],trainer2_pokemon,[])

#     #init the battle
#     battle = Battle(battlenum,trainer1,trainer2)

#     battle.get_typeChart(credentials)



#     #while the battle turn counter < max turns AND no winner take turns
#     while battle.turn <= battle.max_turns and battle.winner == None:
#         battle.take_turn()
# #         dataToExport.append((battlenum,
# #                              battle.turn,
# #                              battle.first_to_move,
# #                              battle.second_to_move,
# #                              trainer1.id,
# #                              trainer1.this_turn_action,
# #                             #  trainer1.this_turn_move,
# #                              trainer1.this_turn_move.id,
# #                              trainer1.activepokemon.pp_st[trainer1.this_turn_move.id], #this moves starting pp
# #                              trainer1.activepokemon.pp_cur[trainer1.this_turn_move.id], #this moves remaining pp
# #                              trainer1.faintedpokemon
# #                              ))

# # print(dataToExport)


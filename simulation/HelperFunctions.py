# from class_battle import Battle
# from class_trainer import Trainer
# from class_pokemon import Pokemon
# from class_move import Move
#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_battles_to_sim_pks(host,port,database,username,password):
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    # Query the trainers in this battle number
    query = f"""
    SELECT pk_battles_to_sim_id
    FROM silver.battles_to_sim
    """

    cursor.execute(query)

    # convert results to a list
    results = [row[0] for row in cursor.fetchall()]

    # Close the cursor and connection
    cursor.close()
    conn.close()

    # Return the trainer ids 
    # (1,2)
    return results
#-----------------------------------------------------------------------------------------------------------------------------------------------#
def check_battle_already_simulated(host,port,database,username,password,fk_battles_to_sim_id,seed):
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    # Query the trainers in this battle number
    query = f"""
    SELECT pk_battles_sim_results_id
    FROM silver.battles_sim_results
    WHERE fk_battles_to_sim_id = {fk_battles_to_sim_id}
    AND seed = {seed}
    """

    cursor.execute(query)

    # convert results to a list
    results = bool([row[0] for row in cursor.fetchall()])

    # Close the cursor and connection
    cursor.close()
    conn.close()

    # Return the trainer ids 
    # (1,2)
    return results
#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_trainers_in_battle(host,port,database,username,password,battlenum):
    import psycopg2
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    # Query the trainers in this battle number
    query = f"""
    SELECT fk_trainers_id_one, fk_trainers_id_two
    FROM silver.battles_to_sim
    WHERE pk_battles_to_sim_id = {battlenum}
    """

    cursor.execute(query)

    # convert results to a list
    results = cursor.fetchone()

    # Close the cursor and connection
    cursor.close()
    conn.close()

    # Return the trainer ids 
    # (1,2)
    return results

# #-----------------------------------------------------------------------------------------------------------------------------------------------#
# def get_moveStats(credentials, moveIDs): 
#     import psycopg2 #remove this down the line, make this a module/package

#     conn = psycopg2.connect(
#         host=credentials[0],
#         port=credentials[1],
#         database=credentials[2],
#         user=credentials[3],
#         password=credentials[4]
#     )
#     cursor = conn.cursor()

#     # Query the moves
#     query = f"""
#     SELECT pk_move_id, fk_type_id, power, accuracy, power_points as powerpoints, fk_damage_category_id as damagecategory
#     FROM genone_pokedex_ingested.moves t1
#     LEFT JOIN genone_pokedex_ingested.moves_stats t2 on t1.pk_move_id = t2.fk_move_id 
#     WHERE pk_move_id in {moveIDs}
#     """

#     cursor.execute(query)

#     # Create a nested dictionary from the results
#     moveStats = {}
#     for row in cursor.fetchall():
#         pk_move_id = row[0]
#         fk_type_id = row[1]
#         power = row[2]
#         accuracy = row[3]
#         powerpoints = row[4]
#         damagecategory = row[5]

#         moveStats[pk_move_id] = [fk_type_id, power, accuracy, powerpoints, damagecategory]

#     # Close the connection
#     cursor.close()
#     conn.close()

#     return moveStats

# #-----------------------------------------------------------------------------------------------------------------------------------------------#
# def get_pokemonInBattle(credentials, trainerID): 
#     import psycopg2 #remove this down the line, make this a module/package

#     conn = psycopg2.connect(
#         host=credentials[0],
#         port=credentials[1],
#         database=credentials[2],
#         user=credentials[3],
#         password=credentials[4]
#     )
#     cursor = conn.cursor()

#     # Query the pokemon for this trainerid
#     query = f"""
#     SELECT fk_trainer_id, pk_pokemon_id, fk_move1_id, fk_move2_id, fk_move3_id, fk_move4_id, party_order, level, fk_type_one_id, fk_type_two_id, hp, attack, defense, special, speed
#     FROM genone_pokedex_ingested.trainers_teams t1
#     LEFT JOIN genone_pokedex_ingested.pokemon t2 on t1.fk_pokemon_id = t2.pk_pokemon_id
#     LEFT JOIN genone_pokedex_ingested.pokemon_stats t3 on t1.fk_pokemon_id = t3.fk_pokemon_id
#     WHERE fk_trainer_id = {trainerID}
#     ORDER BY t1.fk_trainer_id, t1.party_order
#     """

#     cursor.execute(query)

#     #create an empty dictionary 
#     pokemon_in_battle={}

#     # loop through each row returned from the sql query, and fill in the dictionary one by one
#     for row in cursor.fetchall():
#         # trainer_id = row[0]
#         party_order = row[6]
#         pokemon_id = row[1]
#         level = row[7]
#         types = [row[8], row[9]]
#         moveIDs = (row[2], row[3], row[4], row[5])
#         #get moves by passing list of moves this trainers pokemon has
#         moves = get_moveStats(credentials,moveIDs)
#         stats = [row[10],row[11],row[12],row[13],row[14]]

#         # If the trainer doesn't already exist in the dictionary, initialize their list
#         # if trainer_id not in pokemon_in_battle:
#         #     pokemon_in_battle[trainer_id] = {}

#         # Store Pokémon information by trainer id and by party order
#         # pokemon_in_battle[trainer_id][party_order] = {
#         pokemon_in_battle[party_order] = {
#         "pokemon_id": pokemon_id,
#         "level": level,
#         "types": types,
#         "moves": moves,
#         "stats": stats
#         }

#     # Close the connection
#     cursor.close()
#     conn.close()

#     return pokemon_in_battle

#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_trainer_team(host,port,database,username,password,trainer_id):
    

    #loop through by party order in the passed dict
    for partyorder in dict:
        pokemon_id = dict[partyorder]['pokemon_id']
        level = dict[partyorder]['level']
        types = dict[partyorder]['types']
        moves_dict = dict[partyorder]['moves']
        stats = dict[partyorder]['stats']
        attributes = [0,0,0] # does this need to be hardcoded?

        #empty list the init_moves will be appended to
        moves_list = []
        for move_id, move_stats in moves_dict.items():   
            #init the move         
            move_instance = Move(move_id, move_stats)
            moves_list.append(move_instance)

        #init the pokemon
        pokemon_instance = Pokemon(partyorder,pokemon_id,level,types,moves_list,stats,attributes)
        team.append(pokemon_instance)

    return team
# #-----------------------------------------------------------------------------------------------------------------------------------------------#
# def get_typeMatchups(credentials, table): 
#     import psycopg2 #remove this down the line, make this a module/package

#     conn = psycopg2.connect(
#         host=credentials[0],
#         database=credentials[1],
#         user=credentials[2],
#         password=credentials[3]
#     )
#     cursor = conn.cursor()

#     # Query the type matchups
#     query = f"""
#     SELECT fk_atk_type_id, fk_def_type_id, multiplier
#     FROM {table};
#     """
#     cursor.execute(query)

#     # Create a nested dictionary from the results
#     type_chart = {}
#     for row in cursor.fetchall():
#         fk_atk_type_id, fk_def_type_id, multiplier = row
#         if fk_atk_type_id not in type_chart:
#             type_chart[fk_atk_type_id] = {}
#         type_chart[fk_atk_type_id][fk_def_type_id] = multiplier

#     # Close the connection
#     cursor.close()
#     conn.close()

#     return type_chart

# # #example
# # typeMatchups = get_typeMatchups('10.0.0.101','pokemon','python','python','genone_pokedex_ingested.types_effectiveness')
# # print(typeMatchups)

# # # returns the following
# # # {
# # #     "Fire": {"Grass": 2.0, "Water" : 0.5},
# # #     "Water": {"Fire": 2.0, "Grass" : 0.5},
# # #     "Grass": {"Water": 2.0, "Fire" : 0.5}
# # # }

# #-----------------------------------------------------------------------------------------------------------------------------------------------#
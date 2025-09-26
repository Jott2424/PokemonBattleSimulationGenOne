# from class_battle import Battle
# from class_trainer import Trainer
# from class_pokemon import Pokemon
# from class_move import Move
#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_battles_to_sim_pks(host,port,database,username,password):
    print('Getting battles to simulate!')
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

    # Return the battle pks
    return results
#-----------------------------------------------------------------------------------------------------------------------------------------------#
def check_battle_already_simulated(host,port,database,username,password,fk_battles_to_sim_id,seed):
    print(f'Checking if battle #{fk_battles_to_sim_id} has been simulated with the seed #{seed}')
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    # Query the trainers in this battle number using this seed
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

    # Return true/false
    return results
#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_trainers_in_battle(host,port,database,username,password,battlenum):
    print(f'Getting trainers in battle #{battlenum}')
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

#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_move_stats(host,port,database,username,password,moves): 
    # print(f'Getting move stats for moves {moves}')
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    moves_str = f"({','.join(map(str,moves))})"

    # Query the trainers in this battle number
    query = f"""
    SELECT ms.fk_moves_id, ms.pp, ms.power, ms.accuracy, m.fk_damage_categories_id as mdc_id, mdc.damage_category, m.move, m.fk_types_id, t.type
    FROM bronze.moves_stats ms
    join bronze.moves m on ms.fk_moves_id = m.pk_moves_id
    join bronze.moves_damage_categories mdc on m.fk_damage_categories_id = mdc.pk_move_damage_categories_id
    join bronze.types t on m.fk_types_id = t.pk_types_id
    WHERE fk_moves_id in {moves_str}
    """

    cursor.execute(query)

    #convert results to a dict
    colnames = [desc[0] for desc in cursor.description]
    rows = [dict(zip(colnames,row)) for row in cursor.fetchall()]
    results = {row['fk_moves_id']: row for row in rows}

    # Close the connection
    cursor.close()
    conn.close()

    return results

#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_pokemon_stats(host,port,database,username,password,pokemon): 
    # print(f'Getting pokemon stats for {pokemon}')
    import psycopg2

    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    pokemon_str = f"({','.join(map(str,pokemon))})"

    # Query the trainers in this battle number
    query = f"""
    SELECT ps.fk_pokemon_id as id, ps.hp, ps.attack, ps.defense, ps.speed, ps.special
    FROM bronze.pokemon_stats ps
    WHERE fk_pokemon_id in {pokemon_str}
    """

    cursor.execute(query)

    #convert results to a dict
    colnames = [desc[0] for desc in cursor.description]
    rows = [dict(zip(colnames,row)) for row in cursor.fetchall()]
    results = {row['id']: row for row in rows}

    # Close the connection
    cursor.close()
    conn.close()

    return results

#-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_trainer_team(host,port,database,username,password,trainer_id):
    # print(f'Getting trainer team for trainer #{trainer_id}')
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
    SELECT party_order, p.pk_pokemon_id as id, fk_move1_id, fk_move2_id, fk_move3_id, fk_move4_id, level, p.fk_types_id_one, p.fk_types_id_two, t1.type as Type1, t2.type as Type2, ps.hp, ps.attack, ps.defense, ps.speed, ps.special
    FROM bronze.trainers_teams tt
    join bronze.pokemon p on tt.fk_pokemon_id = p.pk_pokemon_id
    join bronze.pokemon_stats ps on p.pk_pokemon_id = ps.fk_pokemon_id
    join bronze.types t1 on p.fk_types_id_one = t1.pk_types_id
    join bronze.types t2 on p.fk_types_id_two = t2.pk_types_id

    WHERE fk_trainers_id = {trainer_id}
    """

    cursor.execute(query)

    #convert results to a list of dicts
    colnames = [desc[0] for desc in cursor.description]
    results = [dict(zip(colnames,row)) for row in cursor.fetchall()]

    # Close the cursor and connection
    cursor.close()
    conn.close()

    return results

# #-----------------------------------------------------------------------------------------------------------------------------------------------#
def init_trainer(host,port,database,username,password,trainer_id,seed,type_chart):
    print(f'Initializing trainer #{trainer_id}')
    from HelperFunctions import get_trainer_team, get_pokemon_stats
    from classes.trainer import Trainer

    trainer_details = {}

    #get the list of pokemon on the trainers team
    team = get_trainer_team(host,port,database,username,password,trainer_id)

    #get base stats for all moves in one sweep
    move_stats = get_move_stats(host,port,database,username,password,list({row[key] for row in team for key in ['fk_move1_id','fk_move2_id','fk_move3_id','fk_move4_id']}))
    
    #trainer_team holds pokemon objects
    trainer_team = {}
    for pokemon_dict in team:
        party_order = pokemon_dict['party_order']
        #list of this pokemons moves out of the full list of all moves
        pokemon_moves_dict = {k:v for k,v in move_stats.items() if k in list(pokemon_dict[key] for key in ['fk_move1_id','fk_move2_id','fk_move3_id','fk_move4_id'])}

        #init this pokemon object and append to the team list
        trainer_team[party_order] = init_pokemon(pokemon_dict, pokemon_moves_dict)
    
    #gather trainer details
    trainer_details['id'] = trainer_id
    trainer_details['team'] = trainer_team
    trainer_details['seed'] = seed
    trainer_details['type_chart'] = type_chart

    #init the trainer
    trainer_obj = Trainer(trainer_details)

    return trainer_obj


# #-----------------------------------------------------------------------------------------------------------------------------------------------#
def init_pokemon(pokemon_details, moves_dict):
    # print(f'Initializing pokemon {pokemon_details["id"]}')
    from classes.pokemon import Pokemon

    #init the moves for this pokemon
    moves = {}
    move_counter = 1
    for move_id,move_details in moves_dict.items():
        moves[move_counter] = init_move(move_details)
        move_counter+=1
    
    #init the pokemon
    pokemon_details['moves'] = moves
    pokemon_obj = Pokemon(pokemon_details)

    return pokemon_obj

# #-----------------------------------------------------------------------------------------------------------------------------------------------#
def init_move(details):
    # print(f'Initializing move {details}')
    from classes.move import Move
    move_obj = Move(details)
    return move_obj

# #-----------------------------------------------------------------------------------------------------------------------------------------------#
def get_type_chart(host,port,database,username,password):
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
    SELECT fk_types_id_a, fk_types_id_d, multiplier
    FROM bronze.types_effectiveness;
    """
    cursor.execute(query)

    # Create a nested dictionary from the results
    type_chart = {}
    for row in cursor.fetchall():
        fk_types_id_a, fk_types_id_d, multiplier = row
        if fk_types_id_a not in type_chart:
            type_chart[fk_types_id_a] = {}
        type_chart[fk_types_id_a][fk_types_id_d] = multiplier

    # Close the connection
    cursor.close()
    conn.close()

    return type_chart

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
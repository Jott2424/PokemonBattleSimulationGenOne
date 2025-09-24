import psycopg2
from psycopg2.extras import execute_values
import os
import pandas as pd
import numpy as np
import json
import numpy as np

####################################
# config & variables
####################################
with open("config.json") as f:
    config = json.load(f)

host     = config["databaseCredentials"]["host"]
port     = config["databaseCredentials"]["port"]
database = config["databaseCredentials"]["database"]
username = config["databaseCredentials"]["username"]
password = config["databaseCredentials"]["password"]

# Database connection parameters
conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )

# Create a cursor object
cur = conn.cursor()

create_schemas_query = """
CREATE SCHEMA IF NOT EXISTS bronze AUTHORIZATION postgres;

CREATE SCHEMA IF NOT EXISTS silver AUTHORIZATION postgres;

CREATE SCHEMA IF NOT EXISTS gold AUTHORIZATION postgres;
"""

# SQL statement to create a table
create_table_query = """

CREATE TABLE IF NOT EXISTS bronze.games (
	pk_games_id smallserial NOT NULL,
	game varchar(6) NOT null,
	CONSTRAINT games_pk PRIMARY KEY (pk_games_id)
);

CREATE TABLE IF NOT EXISTS bronze.locations (
	pk_locations_id smallserial NOT NULL,
	location text NOT null,
	CONSTRAINT locations_pk PRIMARY KEY (pk_locations_id)
);

CREATE TABLE IF NOT EXISTS bronze."types" (
	pk_types_id smallserial NOT NULL,
	"type" varchar(10) NOT null,
	CONSTRAINT types_pk PRIMARY KEY (pk_types_id)
);

CREATE TABLE IF NOT EXISTS bronze.moves_damage_categories (
	pk_move_damage_categories_id smallserial NOT NULL,
	damage_category varchar(8) NOT null,
	CONSTRAINT moves_damage_categories_pk PRIMARY KEY (pk_move_damage_categories_id)
);

CREATE TABLE IF NOT EXISTS bronze.moves (
	pk_moves_id smallserial NOT NULL,
	fk_types_id int2 NOT NULL,
	fk_damage_categories_id int2 NOT NULL,
	move varchar(14) NOT NULL,
	description varchar(87) NULL,
    CONSTRAINT moves_pk PRIMARY KEY (pk_moves_id),
    CONSTRAINT moves_types_fk FOREIGN KEY (fk_types_id) REFERENCES bronze."types"(pk_types_id),
    CONSTRAINT moves_moves_damage_categories_fk FOREIGN KEY (fk_damage_categories_id) REFERENCES bronze.moves_damage_categories(pk_move_damage_categories_id)
);

CREATE TABLE IF NOT EXISTS bronze.pokemon (
	pk_pokemon_id serial NOT NULL,
	fk_types_id_one int2 NOT NULL,
	fk_types_id_two int2 NULL,
	pokedex_number int2 NOT NULL,
	pokemon varchar(10) NOT null,
	CONSTRAINT pokemon_pk PRIMARY KEY (pk_pokemon_id),
    CONSTRAINT pokemon_types_fk FOREIGN KEY (fk_types_id_one) REFERENCES bronze."types"(pk_types_id),
    CONSTRAINT pokemon_types2_fk FOREIGN KEY (fk_types_id_two) REFERENCES bronze."types"(pk_types_id)
);

CREATE TABLE IF NOT EXISTS bronze.pokemon_stats (
	pk_pokemon_stats_id smallserial NOT NULL,
	fk_pokemon_id int2 NOT NULL,
	hp int2 NOT NULL,
	attack int2 NOT NULL,
	defense int2 NOT NULL,
	special int2 NOT NULL,
	speed int2 NOT null,
	CONSTRAINT pokemon_stats_pk PRIMARY KEY (pk_pokemon_stats_id),
    CONSTRAINT pokemon_pokemon_stats_fk FOREIGN KEY (fk_pokemon_id) REFERENCES bronze.pokemon(pk_pokemon_id)
);

CREATE TABLE IF NOT EXISTS bronze.trainer_types (
	pk_trainer_types_id smallserial NOT NULL,
	trainer_type varchar(15) NOT NULL,
	CONSTRAINT trainer_types_pk PRIMARY KEY (pk_trainer_types_id)
);

CREATE TABLE IF NOT EXISTS bronze.trainers (
	pk_trainers_id smallserial NOT NULL,
	fk_games_id int4 NULL,
	fk_trainer_types_id int4 NOT NULL,
	short_name varchar(16) NOT NULL,
	long_name varchar(59) NOT NULL,
	CONSTRAINT trainers_pk PRIMARY KEY (pk_trainers_id),
    CONSTRAINT trainers_games_fk FOREIGN KEY (fk_games_id) REFERENCES bronze.games(pk_games_id),
	CONSTRAINT trainers_trainer_types_fk FOREIGN KEY (fk_trainer_types_id) REFERENCES bronze.trainer_types(pk_trainer_types_id)
);

CREATE TABLE IF NOT EXISTS bronze.rival_scenarios (
	pk_rival_scenarios_id smallserial NOT NULL,
	scenario varchar(21) NOT null,
	CONSTRAINT rival_scenarios_pk PRIMARY KEY (pk_rival_scenarios_id)
);

CREATE TABLE IF NOT EXISTS bronze.trainers_teams (
	pk_trainers_teams_id smallserial NOT NULL,
	fk_games_id int2 NOT NULL,
	fk_locations_id int2 NOT NULL,
	fk_rival_scenarios_id int2 NOT NULL,
	fk_trainers_id int2 NOT NULL,
	fk_pokemon_id int2 NOT NULL,
	fk_move1_id int2 NOT NULL,
	fk_move2_id int2 NULL,
	fk_move3_id int2 NULL,
	fk_move4_id int2 NULL,
	party_order int2 NULL,
	"level" int2 null,
	CONSTRAINT trainers_teams_pk PRIMARY KEY (pk_trainers_teams_id),
    CONSTRAINT trainers_teams_games_fk FOREIGN KEY (fk_games_id) REFERENCES bronze.games(pk_games_id),
    CONSTRAINT trainers_teams_locations_fk FOREIGN KEY (fk_locations_id) REFERENCES bronze.locations(pk_locations_id),
    CONSTRAINT trainers_teams_rival_scenarios_fk FOREIGN KEY (fk_rival_scenarios_id) REFERENCES bronze.rival_scenarios(pk_rival_scenarios_id),
    CONSTRAINT trainers_teams_trainers_fk FOREIGN KEY (fk_trainers_id) REFERENCES bronze.trainers(pk_trainers_id),
    CONSTRAINT trainers_teams_pokemon_fk FOREIGN KEY (fk_pokemon_id) REFERENCES bronze.pokemon(pk_pokemon_id),
    CONSTRAINT trainers_teams_moves_fk FOREIGN KEY (fk_move1_id) REFERENCES bronze.moves(pk_moves_id),
    CONSTRAINT trainers_teams_moves2_fk FOREIGN KEY (fk_move2_id) REFERENCES bronze.moves(pk_moves_id),
    CONSTRAINT trainers_teams_moves3_fk FOREIGN KEY (fk_move3_id) REFERENCES bronze.moves(pk_moves_id),
    CONSTRAINT trainers_teams_moves4_fk FOREIGN KEY (fk_move4_id) REFERENCES bronze.moves(pk_moves_id)
);

CREATE TABLE IF NOT EXISTS bronze.moves_stats (
	pk_moves_stats_id smallserial NOT NULL,
	fk_moves_id int2 NOT NULL,
	power int2 NULL,
    accuracy int2 NULL,
    pp int2 NULL,
	CONSTRAINT moves_stats_pk PRIMARY KEY (pk_moves_stats_id),
    CONSTRAINT moves_stats_moves_fk FOREIGN KEY (fk_moves_id) REFERENCES bronze.moves(pk_moves_id)
);

CREATE TABLE IF NOT EXISTS silver.battles_to_sim (
	pk_battles_to_sim_id serial NOT NULL,
	fk_trainers_id_one int NOT null,
    fk_trainers_id_two int NOT null,
	CONSTRAINT battles_to_sim_pk PRIMARY KEY (pk_battles_to_sim_id),
    CONSTRAINT trainers_trainers_1 FOREIGN KEY (fk_trainers_id_one) REFERENCES bronze.trainers(pk_trainers_id),
    CONSTRAINT trainers_trainers_2 FOREIGN KEY (fk_trainers_id_two) REFERENCES bronze.trainers(pk_trainers_id)
);

CREATE TABLE IF NOT EXISTS silver.battles_sim_results (
	pk_battles_sim_results_id serial NOT NULL,
    fk_battles_to_sim_id int NOT NULL,
    seed int NOT NULL,
	CONSTRAINT battles_sim_results_pk PRIMARY KEY (pk_battles_sim_results_id),
    CONSTRAINT battles_sim_results_battles_to_sim FOREIGN KEY (fk_battles_to_sim_id) REFERENCES silver.battles_to_sim(pk_battles_to_sim_id)
);

"""

# Execute the query
cur.execute(create_schemas_query)
print("Schemas created successfully")

# Execute the query
cur.execute(create_table_query)
print("Tables created successfully")

# Commit changes
conn.commit()


for file in sorted([file for file in os.listdir("./rawdata")]):
    df = pd.read_csv(f'./rawdata/{file}')
    df = df.replace({np.nan: None})  # handle NaN for SQL NULL
    
    print(f'Reading ./rawdata/{file}')
    print(df.dtypes)

    # Determine table name from file name
    table_name = file.split(".")[1]

    # Convert DataFrame to list of native Python tuples
    data_tuples = [tuple(x) for x in df.itertuples(index=False, name=None)]

    # Generate SQL insert statement
    columns = ','.join(df.columns)
    sql = f"INSERT INTO bronze.{table_name} ({columns}) VALUES %s"
    print(f'INSERT INTO bronze.{table_name}')

    # Bulk insert
    execute_values(cur, sql, data_tuples)
    conn.commit()
    print(f"{len(df)} rows inserted into bronze.{table_name} \n")
    
cur.close()
conn.close()
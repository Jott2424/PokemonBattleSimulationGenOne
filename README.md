# PokemonBattleSimulationGenOne
Simulating pokemon battles using the first generations pokemon, moves, stats, etc... in python!

# Contents
1. Raw Data
2. Scripts to load this data to a postgres database
3. Scripts to simulate battles
4. Scripts to load battle data to a database
5. Scripts to build ML models on all of this data

# Raw Data
CSVs in the "./rawdata" folder, contains everything needed to get simulations up and running

# Load Raw Data
1. Clone Repo
2. Deploy Postgres instance (config set for localhost and default port 5432)
3. Create database with owner set to postgres (config set for pokemon_battlesim_g1)
4. Update config variables if necessary and run LoadRawData.py

# Running Simulations
By default, this script will populate a silver table called "battles_to_sim" which contains a cross join of all trainers vs all trainers, including themselves.<br><br>Simulations are set to use a seed for reproduceability, and by default it will check if the given simulation has already been run with the seed set in the config file
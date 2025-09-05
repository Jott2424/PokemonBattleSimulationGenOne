# PokemonBattleSimulationGenOne
a python project to simulate pokemon battles using the first generations pokemon, moves, stats, etc...

# Contents
1. Raw Data
2. Scripts to load this data to a postgres database
3. Scripts to simulate battles
4. Scripts to load battle data to a database
5. Scripts to build ML models on all of this data

# Raw Data
10 csvs in the "./rawdata" folder, contains everything needed to get simulations up and running

# Instructions To Load Raw Data
1. Deploy Postgres instance
2. Create database example - "pokemon_battlesim_g1"
3. Update variables and run LoadRawData.py
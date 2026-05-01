"""
Move effects map for all 165 Gen 1 moves.

Each entry maps a move name (matching the DB 'move' column) to a dict:
  effect       — primary effect handler key
  priority     — move priority (0=normal, 1=quick, -1=counter)
  secondary_*  — optional secondary effect fields consumed by handlers

Where this file deviates from the DB descriptions for Gen 1 accuracy:
  - low-kick (78):       DB says weight-based; Gen 1 is 30% flinch, 50 power
  - tri-attack (156):    DB says may cause status; Gen 1 is pure damage
  - waterfall (161):     DB says may flinch; Gen 1 is pure damage
  - gust (56):           DB says double vs Fly; Gen 1 is normal damage
  - skull-bash (118):    DB says raise Defense on charge; Gen 1 does not
  - growth (54):         DB says raises Attack+Special; Gen 1 raises Special only
  - high-jump-kick (60): DB says lose half HP on miss; Gen 1 is 1 HP crash
  - jump-kick (69):      same as above
  - minimize (85):       DB says "sharply" (+2); Gen 1 is +1
  - string-shot (134):   DB says "sharply" (-2); Gen 1 is -1
"""

MOVE_EFFECTS = {
    # --- 1: absorb ---
    "absorb": {"effect": "drain", "fraction": 0.5},

    # --- 2: acid ---
    "acid": {"effect": "pure_damage", "stat_secondary": {"stat": "special", "delta": -1}, "secondary_chance": 0.33},

    # --- 3: acid-armor ---
    "acid-armor": {"effect": "stat_change", "stat": "defense", "delta": 2, "target": "self"},

    # --- 4: agility ---
    "agility": {"effect": "stat_change", "stat": "speed", "delta": 2, "target": "self"},

    # --- 5: amnesia ---
    "amnesia": {"effect": "stat_change", "stat": "special", "delta": 2, "target": "self"},

    # --- 6: aurora-beam ---
    "aurora-beam": {"effect": "pure_damage", "stat_secondary": {"stat": "attack", "delta": -1}, "secondary_chance": 0.33},

    # --- 7: barrage ---
    "barrage": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 8: barrier ---
    "barrier": {"effect": "stat_change", "stat": "defense", "delta": 2, "target": "self"},

    # --- 9: bide ---
    "bide": {"effect": "bide"},

    # --- 10: bind ---
    "bind": {"effect": "binding"},

    # --- 11: bite ---
    "bite": {"effect": "pure_damage", "flinch_chance": 0.10},

    # --- 12: blizzard ---
    "blizzard": {"effect": "pure_damage", "secondary_status": "freeze", "secondary_chance": 0.10},

    # --- 13: body-slam ---
    "body-slam": {"effect": "pure_damage", "secondary_status": "paralysis", "secondary_chance": 0.30},

    # --- 14: bone-club ---
    "bone-club": {"effect": "pure_damage", "flinch_chance": 0.10},

    # --- 15: bonemerang ---
    "bonemerang": {"effect": "multi_hit", "min_hits": 2, "max_hits": 2},

    # --- 16: bubble ---
    "bubble": {"effect": "pure_damage", "stat_secondary": {"stat": "speed", "delta": -1}, "secondary_chance": 0.33},

    # --- 17: bubble-beam ---
    "bubble-beam": {"effect": "pure_damage", "stat_secondary": {"stat": "speed", "delta": -1}, "secondary_chance": 0.33},

    # --- 18: clamp ---
    "clamp": {"effect": "binding"},

    # --- 19: comet-punch ---
    "comet-punch": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 20: confuse-ray ---
    "confuse-ray": {"effect": "status_confuse"},

    # --- 21: confusion ---
    "confusion": {"effect": "pure_damage", "secondary_confuse": True, "secondary_chance": 0.10},

    # --- 22: constrict ---
    "constrict": {"effect": "pure_damage", "stat_secondary": {"stat": "speed", "delta": -1}, "secondary_chance": 0.10},

    # --- 23: conversion ---
    "conversion": {"effect": "conversion"},

    # --- 24: counter ---
    # Counter goes after opponent attacks (priority -1)
    "counter": {"effect": "counter", "priority": -1},

    # --- 25: crabhammer ---
    "crabhammer": {"effect": "high_crit"},

    # --- 26: cut ---
    "cut": {"effect": "pure_damage"},

    # --- 27: defense-curl ---
    "defense-curl": {"effect": "stat_change", "stat": "defense", "delta": 1, "target": "self"},

    # --- 28: dig ---
    # Underground turn 1; Earthquake/Fissure bypass
    "dig": {"effect": "two_turn", "invulnerable": True, "invulnerable_type": "dig",
            "bypass_moves": ["earthquake", "fissure"]},

    # --- 29: disable ---
    "disable": {"effect": "disable"},

    # --- 30: dizzy-punch ---
    "dizzy-punch": {"effect": "pure_damage", "secondary_confuse": True, "secondary_chance": 0.20},

    # --- 31: double-kick ---
    "double-kick": {"effect": "multi_hit", "min_hits": 2, "max_hits": 2},

    # --- 32: double-slap ---
    "double-slap": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 33: double-team ---
    "double-team": {"effect": "stat_change", "stat": "evasion", "delta": 1, "target": "self"},

    # --- 34: double-edge ---
    "double-edge": {"effect": "recoil", "recoil_fraction": 0.25},

    # --- 35: dragon-rage ---
    "dragon-rage": {"effect": "fixed_damage", "fixed_value": 40},

    # --- 36: dream-eater ---
    "dream-eater": {"effect": "drain_sleep", "fraction": 0.5},

    # --- 37: drill-peck ---
    "drill-peck": {"effect": "pure_damage"},

    # --- 38: earthquake ---
    # Doubles power if target is digging (invulnerable underground)
    "earthquake": {"effect": "earthquake"},

    # --- 39: egg-bomb ---
    "egg-bomb": {"effect": "pure_damage"},

    # --- 40: ember ---
    "ember": {"effect": "pure_damage", "secondary_status": "burn", "secondary_chance": 0.10},

    # --- 41: explosion ---
    # User faints; target's Defense is halved in damage calc
    "explosion": {"effect": "self_destruct"},

    # --- 42: fire-blast ---
    "fire-blast": {"effect": "pure_damage", "secondary_status": "burn", "secondary_chance": 0.30},

    # --- 43: fire-punch ---
    "fire-punch": {"effect": "pure_damage", "secondary_status": "burn", "secondary_chance": 0.10},

    # --- 44: fire-spin ---
    "fire-spin": {"effect": "binding"},

    # --- 45: fissure ---
    "fissure": {"effect": "ohko"},

    # --- 46: flamethrower ---
    "flamethrower": {"effect": "pure_damage", "secondary_status": "burn", "secondary_chance": 0.10},

    # --- 47: flash ---
    "flash": {"effect": "stat_change", "stat": "accuracy", "delta": -1, "target": "opponent"},

    # --- 48: fly ---
    # In sky turn 1; nothing bypasses Fly in Gen 1
    "fly": {"effect": "two_turn", "invulnerable": True, "invulnerable_type": "fly", "bypass_moves": []},

    # --- 49: focus-energy ---
    "focus-energy": {"effect": "focus_energy"},

    # --- 50: fury-attack ---
    "fury-attack": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 51: fury-swipes ---
    "fury-swipes": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 52: glare ---
    "glare": {"effect": "status_paralyze"},

    # --- 53: growl ---
    "growl": {"effect": "stat_change", "stat": "attack", "delta": -1, "target": "opponent"},

    # --- 54: growth ---
    # Gen 1: raises Special only (+1). DB says Attack+Special — Gen 1 accurate implemented.
    "growth": {"effect": "stat_change", "stat": "special", "delta": 1, "target": "self"},

    # --- 55: guillotine ---
    "guillotine": {"effect": "ohko"},

    # --- 56: gust ---
    # Gen 1: normal damage (no fly-targeting bonus). DB description is Gen 2+.
    "gust": {"effect": "pure_damage"},

    # --- 57: harden ---
    "harden": {"effect": "stat_change", "stat": "defense", "delta": 1, "target": "self"},

    # --- 58: haze ---
    "haze": {"effect": "haze"},

    # --- 59: headbutt ---
    "headbutt": {"effect": "pure_damage", "flinch_chance": 0.30},

    # --- 60: high-jump-kick ---
    # Gen 1: if miss, user takes 1 HP crash damage (not half HP — that is Gen 2+)
    "high-jump-kick": {"effect": "recoil_crash", "crash_hp": 1},

    # --- 61: horn-attack ---
    "horn-attack": {"effect": "pure_damage"},

    # --- 62: horn-drill ---
    "horn-drill": {"effect": "ohko"},

    # --- 63: hydro-pump ---
    "hydro-pump": {"effect": "pure_damage"},

    # --- 64: hyper-beam ---
    "hyper-beam": {"effect": "hyper_beam"},

    # --- 65: hyper-fang ---
    "hyper-fang": {"effect": "pure_damage", "flinch_chance": 0.10},

    # --- 66: hypnosis ---
    "hypnosis": {"effect": "status_sleep"},

    # --- 67: ice-beam ---
    "ice-beam": {"effect": "pure_damage", "secondary_status": "freeze", "secondary_chance": 0.10},

    # --- 68: ice-punch ---
    "ice-punch": {"effect": "pure_damage", "secondary_status": "freeze", "secondary_chance": 0.10},

    # --- 69: jump-kick ---
    # Gen 1: 1 HP crash on miss
    "jump-kick": {"effect": "recoil_crash", "crash_hp": 1},

    # --- 70: karate-chop ---
    "karate-chop": {"effect": "high_crit"},

    # --- 71: kinesis ---
    "kinesis": {"effect": "stat_change", "stat": "accuracy", "delta": -1, "target": "opponent"},

    # --- 72: leech-life ---
    "leech-life": {"effect": "drain", "fraction": 0.5},

    # --- 73: leech-seed ---
    "leech-seed": {"effect": "leech_seed"},

    # --- 74: leer ---
    "leer": {"effect": "stat_change", "stat": "defense", "delta": -1, "target": "opponent"},

    # --- 75: lick ---
    "lick": {"effect": "pure_damage", "secondary_status": "paralysis", "secondary_chance": 0.30},

    # --- 76: light-screen ---
    "light-screen": {"effect": "light_screen"},

    # --- 77: lovely-kiss ---
    "lovely-kiss": {"effect": "status_sleep"},

    # --- 78: low-kick ---
    # Gen 1: 30% flinch, NOT weight-based. DB description is Gen 3+.
    "low-kick": {"effect": "pure_damage", "flinch_chance": 0.30},

    # --- 79: meditate ---
    "meditate": {"effect": "stat_change", "stat": "attack", "delta": 1, "target": "self"},

    # --- 80: mega-drain ---
    "mega-drain": {"effect": "drain", "fraction": 0.5},

    # --- 81: mega-kick ---
    "mega-kick": {"effect": "pure_damage"},

    # --- 82: mega-punch ---
    "mega-punch": {"effect": "pure_damage"},

    # --- 83: metronome ---
    "metronome": {"effect": "metronome"},

    # --- 84: mimic ---
    "mimic": {"effect": "mimic"},

    # --- 85: minimize ---
    # Gen 1: +1 evasion. DB says "sharply" (+2) — Gen 1 accurate implemented.
    "minimize": {"effect": "stat_change", "stat": "evasion", "delta": 1, "target": "self"},

    # --- 86: mirror-move ---
    "mirror-move": {"effect": "mirror_move"},

    # --- 87: mist ---
    "mist": {"effect": "mist"},

    # --- 88: night-shade ---
    "night-shade": {"effect": "level_damage"},

    # --- 89: pay-day ---
    # No battle effect beyond damage
    "pay-day": {"effect": "pure_damage"},

    # --- 90: peck ---
    "peck": {"effect": "pure_damage"},

    # --- 91: petal-dance ---
    "petal-dance": {"effect": "thrash", "min_turns": 2, "max_turns": 3},

    # --- 92: pin-missile ---
    "pin-missile": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 93: poison-gas ---
    "poison-gas": {"effect": "status_poison"},

    # --- 94: poison-powder ---
    "poison-powder": {"effect": "status_poison"},

    # --- 95: poison-sting ---
    "poison-sting": {"effect": "pure_damage", "secondary_status": "poison", "secondary_chance": 0.20},

    # --- 96: pound ---
    "pound": {"effect": "pure_damage"},

    # --- 97: psybeam ---
    "psybeam": {"effect": "pure_damage", "secondary_confuse": True, "secondary_chance": 0.10},

    # --- 98: psychic ---
    "psychic": {"effect": "pure_damage", "stat_secondary": {"stat": "special", "delta": -1}, "secondary_chance": 0.33},

    # --- 99: psywave ---
    "psywave": {"effect": "psywave"},

    # --- 100: quick-attack ---
    "quick-attack": {"effect": "pure_damage", "priority": 1},

    # --- 101: rage ---
    "rage": {"effect": "rage"},

    # --- 102: razor-leaf ---
    "razor-leaf": {"effect": "high_crit"},

    # --- 103: razor-wind ---
    # Charge turn, no invulnerability, high crit on release
    "razor-wind": {"effect": "two_turn", "invulnerable": False, "high_crit": True},

    # --- 104: recover ---
    "recover": {"effect": "heal_half"},

    # --- 105: reflect ---
    "reflect": {"effect": "reflect"},

    # --- 106: rest ---
    "rest": {"effect": "rest"},

    # --- 107: roar ---
    # Fails in trainer battles in Gen 1
    "roar": {"effect": "no_trainer_effect"},

    # --- 108: rock-slide ---
    "rock-slide": {"effect": "pure_damage", "flinch_chance": 0.30},

    # --- 109: rock-throw ---
    "rock-throw": {"effect": "pure_damage"},

    # --- 110: rolling-kick ---
    "rolling-kick": {"effect": "pure_damage", "flinch_chance": 0.30},

    # --- 111: sand-attack ---
    "sand-attack": {"effect": "stat_change", "stat": "accuracy", "delta": -1, "target": "opponent"},

    # --- 112: scratch ---
    "scratch": {"effect": "pure_damage"},

    # --- 113: screech ---
    "screech": {"effect": "stat_change", "stat": "defense", "delta": -2, "target": "opponent"},

    # --- 114: seismic-toss ---
    "seismic-toss": {"effect": "level_damage"},

    # --- 115: self-destruct ---
    "self-destruct": {"effect": "self_destruct"},

    # --- 116: sharpen ---
    "sharpen": {"effect": "stat_change", "stat": "attack", "delta": 1, "target": "self"},

    # --- 117: sing ---
    "sing": {"effect": "status_sleep"},

    # --- 118: skull-bash ---
    # Gen 1: charge turn with no Defense raise (that is Gen 2+). DB says raise Defense.
    "skull-bash": {"effect": "two_turn", "invulnerable": False},

    # --- 119: sky-attack ---
    # Charge turn, no invulnerability, high crit + flinch on release
    "sky-attack": {"effect": "two_turn", "invulnerable": False, "high_crit": True, "flinch_chance": 0.30},

    # --- 120: slam ---
    "slam": {"effect": "pure_damage"},

    # --- 121: slash ---
    "slash": {"effect": "high_crit"},

    # --- 122: sleep-powder ---
    "sleep-powder": {"effect": "status_sleep"},

    # --- 123: sludge ---
    "sludge": {"effect": "pure_damage", "secondary_status": "poison", "secondary_chance": 0.40},

    # --- 124: smog ---
    "smog": {"effect": "pure_damage", "secondary_status": "poison", "secondary_chance": 0.40},

    # --- 125: smokescreen ---
    "smokescreen": {"effect": "stat_change", "stat": "accuracy", "delta": -1, "target": "opponent"},

    # --- 126: soft-boiled ---
    "soft-boiled": {"effect": "heal_half"},

    # --- 127: solar-beam ---
    # Charge turn, no invulnerability
    "solar-beam": {"effect": "two_turn", "invulnerable": False},

    # --- 128: sonic-boom ---
    "sonic-boom": {"effect": "fixed_damage", "fixed_value": 20},

    # --- 129: spike-cannon ---
    "spike-cannon": {"effect": "multi_hit", "min_hits": 2, "max_hits": 5},

    # --- 130: splash ---
    "splash": {"effect": "splash"},

    # --- 131: spore ---
    "spore": {"effect": "status_sleep"},

    # --- 132: stomp ---
    "stomp": {"effect": "pure_damage", "flinch_chance": 0.30},

    # --- 133: strength ---
    "strength": {"effect": "pure_damage"},

    # --- 134: string-shot ---
    # Gen 1: -1 Speed. DB says "sharply" (-2) — Gen 1 accurate implemented.
    "string-shot": {"effect": "stat_change", "stat": "speed", "delta": -1, "target": "opponent"},

    # --- 135: struggle ---
    # Handled separately by the battle engine; should never be dispatched here
    "struggle": {"effect": "pure_damage"},

    # --- 136: stun-spore ---
    "stun-spore": {"effect": "status_paralyze"},

    # --- 137: submission ---
    "submission": {"effect": "recoil", "recoil_fraction": 0.25},

    # --- 138: substitute ---
    "substitute": {"effect": "substitute"},

    # --- 139: super-fang ---
    "super-fang": {"effect": "super_fang"},

    # --- 140: supersonic ---
    "supersonic": {"effect": "status_confuse"},

    # --- 141: surf ---
    "surf": {"effect": "pure_damage"},

    # --- 142: swift ---
    # Always hits; ignores accuracy and evasion
    "swift": {"effect": "swift"},

    # --- 143: swords-dance ---
    "swords-dance": {"effect": "stat_change", "stat": "attack", "delta": 2, "target": "self"},

    # --- 144: tackle ---
    "tackle": {"effect": "pure_damage"},

    # --- 145: tail-whip ---
    "tail-whip": {"effect": "stat_change", "stat": "defense", "delta": -1, "target": "opponent"},

    # --- 146: take-down ---
    "take-down": {"effect": "recoil", "recoil_fraction": 0.25},

    # --- 147: teleport ---
    # No effect in trainer battles
    "teleport": {"effect": "no_trainer_effect"},

    # --- 148: thrash ---
    "thrash": {"effect": "thrash", "min_turns": 2, "max_turns": 3},

    # --- 149: thunder ---
    "thunder": {"effect": "pure_damage", "secondary_status": "paralysis", "secondary_chance": 0.10},

    # --- 150: thunder-punch ---
    "thunder-punch": {"effect": "pure_damage", "secondary_status": "paralysis", "secondary_chance": 0.10},

    # --- 151: thunder-shock ---
    "thunder-shock": {"effect": "pure_damage", "secondary_status": "paralysis", "secondary_chance": 0.10},

    # --- 152: thunder-wave ---
    "thunder-wave": {"effect": "status_paralyze"},

    # --- 153: thunderbolt ---
    "thunderbolt": {"effect": "pure_damage", "secondary_status": "paralysis", "secondary_chance": 0.10},

    # --- 154: toxic ---
    "toxic": {"effect": "status_toxic"},

    # --- 155: transform ---
    "transform": {"effect": "transform"},

    # --- 156: tri-attack ---
    # Gen 1: pure damage, no secondary effect. DB description is Gen 2+.
    "tri-attack": {"effect": "pure_damage"},

    # --- 157: twineedle ---
    # Always hits twice; 20% poison chance per hit
    "twineedle": {"effect": "twineedle", "poison_chance": 0.20},

    # --- 158: vine-whip ---
    "vine-whip": {"effect": "pure_damage"},

    # --- 159: vise-grip ---
    "vise-grip": {"effect": "pure_damage"},

    # --- 160: water-gun ---
    "water-gun": {"effect": "pure_damage"},

    # --- 161: waterfall ---
    # Gen 1: pure damage, no flinch. DB description is Gen 2+.
    "waterfall": {"effect": "pure_damage"},

    # --- 162: whirlwind ---
    # Fails in trainer battles in Gen 1
    "whirlwind": {"effect": "no_trainer_effect"},

    # --- 163: wing-attack ---
    "wing-attack": {"effect": "pure_damage"},

    # --- 164: withdraw ---
    "withdraw": {"effect": "stat_change", "stat": "defense", "delta": 1, "target": "self"},

    # --- 165: wrap ---
    "wrap": {"effect": "binding"},
}

# Effects excluded from Metronome — moves with these effects can't be cleanly
# executed mid-battle without the move being on the trainer's actual moveset.
_METRONOME_EXCLUDED_EFFECTS = {
    "two_turn",        # fly, dig, solar-beam, skull-bash, razor-wind, sky-attack
    "bide",            # bide
    "counter",         # counter
    "mirror_move",     # mirror-move
    "thrash",          # thrash, petal-dance
    "rage",            # rage
    "no_trainer_effect",  # roar, whirlwind, teleport
}

METRONOME_EXCLUDED = {"metronome", "struggle"}

# Valid Metronome targets: moves whose effects we can fully execute inline
METRONOME_POOL = [
    name for name, data in MOVE_EFFECTS.items()
    if name not in METRONOME_EXCLUDED
    and data.get("effect") not in _METRONOME_EXCLUDED_EFFECTS
]

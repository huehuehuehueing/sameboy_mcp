"""Pokemon Generation 1 static data tables for Pokemon Yellow.

Species use Gen 1 INTERNAL indices (not Pokedex numbers).
Data from pret/pokeyellow disassembly.
"""


def _s(name, t1, t2, hp, atk, dfn, spd, spc):
    return {"name": name, "type1": t1, "type2": t2,
            "base_hp": hp, "base_attack": atk, "base_defense": dfn,
            "base_speed": spd, "base_special": spc}


# ============================================================
# Species (Internal Index -> Data)
# ============================================================

SPECIES = {
    # Pikachu line (starter in Yellow)
    0x54: _s("Pikachu",     "Electric", "Electric",  35,  55,  30,  90,  50),
    0x55: _s("Raichu",      "Electric", "Electric",  60,  90,  55, 100,  90),
    # Bulbasaur line
    0x99: _s("Bulbasaur",   "Grass",    "Poison",    45,  49,  49,  45,  65),
    0x09: _s("Ivysaur",     "Grass",    "Poison",    60,  62,  63,  60,  80),
    0x9A: _s("Venusaur",    "Grass",    "Poison",    80,  82,  83,  80, 100),
    # Charmander line
    0xB0: _s("Charmander",  "Fire",     "Fire",      39,  52,  43,  65,  50),
    0xB2: _s("Charmeleon",  "Fire",     "Fire",      58,  64,  58,  80,  65),
    0xB4: _s("Charizard",   "Fire",     "Flying",    78,  84,  78, 100,  85),
    # Squirtle line
    0xB1: _s("Squirtle",    "Water",    "Water",     44,  48,  65,  43,  50),
    0xB3: _s("Wartortle",   "Water",    "Water",     59,  63,  80,  58,  65),
    0x1C: _s("Blastoise",   "Water",    "Water",     79,  83, 100,  78,  85),
    # Caterpie line
    0x7B: _s("Caterpie",    "Bug",      "Bug",       45,  30,  35,  45,  20),
    0x7C: _s("Metapod",     "Bug",      "Bug",       50,  20,  55,  30,  25),
    0x7D: _s("Butterfree",  "Bug",      "Flying",    60,  45,  50,  70,  80),
    # Weedle line
    0x70: _s("Weedle",      "Bug",      "Poison",    40,  35,  30,  50,  20),
    0x71: _s("Kakuna",      "Bug",      "Poison",    45,  25,  50,  35,  25),
    0x72: _s("Beedrill",    "Bug",      "Poison",    65,  80,  40,  75,  45),
    # Pidgey line
    0x24: _s("Pidgey",      "Normal",   "Flying",    40,  45,  40,  56,  35),
    0x96: _s("Pidgeotto",   "Normal",   "Flying",    63,  60,  55,  71,  50),
    0x97: _s("Pidgeot",     "Normal",   "Flying",    83,  80,  75,  91,  70),
    # Rattata/Raticate
    0xA5: _s("Rattata",     "Normal",   "Normal",    30,  56,  35,  72,  25),
    0xA6: _s("Raticate",    "Normal",   "Normal",    55,  81,  60,  97,  50),
    # Spearow/Fearow
    0x05: _s("Spearow",     "Normal",   "Flying",    40,  60,  30,  70,  31),
    0x23: _s("Fearow",      "Normal",   "Flying",    65,  90,  65, 100,  61),
    # Nidoran lines
    0x0F: _s("Nidoran_F",   "Poison",   "Poison",    55,  47,  52,  41,  40),
    0xA8: _s("Nidorina",    "Poison",   "Poison",    70,  62,  67,  56,  55),
    0x10: _s("Nidoqueen",   "Poison",   "Ground",    90,  82,  87,  76,  75),
    0x03: _s("Nidoran_M",   "Poison",   "Poison",    46,  57,  40,  50,  40),
    0xA7: _s("Nidorino",    "Poison",   "Poison",    61,  72,  57,  65,  55),
    0x07: _s("Nidoking",    "Poison",   "Ground",    81,  92,  77,  85,  75),
    # Clefairy/Clefable
    0x04: _s("Clefairy",    "Normal",   "Normal",    70,  45,  48,  35,  60),
    0x8E: _s("Clefable",    "Normal",   "Normal",   95,  70,  73,  60,  85),
    # Vulpix/Ninetales
    0x52: _s("Vulpix",      "Fire",     "Fire",      38,  41,  40,  65,  65),
    0x53: _s("Ninetales",   "Fire",     "Fire",      73,  76,  75, 100, 100),
    # Jigglypuff/Wigglytuff
    0x64: _s("Jigglypuff",  "Normal",   "Normal",   115,  45,  20,  20,  25),
    0x65: _s("Wigglytuff",  "Normal",   "Normal",   140,  70,  45,  45,  50),
    # Zubat/Golbat
    0x6B: _s("Zubat",       "Poison",   "Flying",    40,  45,  35,  55,  40),
    0x82: _s("Golbat",      "Poison",   "Flying",    75,  80,  70,  90,  75),
    # Oddish line
    0xB9: _s("Oddish",      "Grass",    "Poison",    45,  50,  55,  30,  75),
    0xBA: _s("Gloom",       "Grass",    "Poison",    60,  65,  70,  40,  85),
    0xBB: _s("Vileplume",   "Grass",    "Poison",    75,  80,  85,  50, 100),
    # Diglett/Dugtrio
    0x3B: _s("Diglett",     "Ground",   "Ground",    10,  55,  25,  95,  45),
    0x76: _s("Dugtrio",     "Ground",   "Ground",    35,  80,  50, 120,  70),
    # Meowth/Persian
    0x4D: _s("Meowth",      "Normal",   "Normal",    40,  45,  35,  90,  40),
    0x90: _s("Persian",     "Normal",   "Normal",    65,  70,  60, 115,  65),
    # Psyduck/Golduck
    0x2F: _s("Psyduck",     "Water",    "Water",     50,  52,  48,  55,  50),
    0x80: _s("Golduck",     "Water",    "Water",     80,  82,  78,  85,  80),
    # Mankey/Primeape
    0x39: _s("Mankey",      "Fighting", "Fighting",  40,  80,  35,  70,  35),
    0x75: _s("Primeape",    "Fighting", "Fighting",  65, 105,  60,  95,  60),
    # Growlithe/Arcanine
    0x21: _s("Growlithe",   "Fire",     "Fire",      55,  70,  45,  60,  50),
    0x14: _s("Arcanine",    "Fire",     "Fire",      90, 110,  80,  95,  80),
    # Poliwag line
    0x47: _s("Poliwag",     "Water",    "Water",     40,  50,  40,  90,  40),
    0x6E: _s("Poliwhirl",   "Water",    "Water",     65,  65,  65,  90,  50),
    0x6F: _s("Poliwrath",   "Water",    "Fighting",  90,  85,  95,  70,  70),
    # Abra line
    0x94: _s("Abra",        "Psychic",  "Psychic",   25,  20,  15,  90, 105),
    0x26: _s("Kadabra",     "Psychic",  "Psychic",   40,  35,  30, 105, 120),
    0x95: _s("Alakazam",    "Psychic",  "Psychic",   55,  50,  45, 120, 135),
    # Machop line
    0x6A: _s("Machop",      "Fighting", "Fighting",  70,  80,  50,  35,  35),
    0x29: _s("Machoke",     "Fighting", "Fighting",  80, 100,  70,  45,  50),
    0x7E: _s("Machamp",     "Fighting", "Fighting",  90, 130,  80,  55,  65),
    # Geodude line
    0xA9: _s("Geodude",     "Rock",     "Ground",    40,  80, 100,  20,  30),
    0x27: _s("Graveler",    "Rock",     "Ground",    55,  95, 115,  35,  45),
    0x31: _s("Golem",       "Rock",     "Ground",    80, 110, 130,  45,  55),
    # Ponyta/Rapidash
    0xA3: _s("Ponyta",      "Fire",     "Fire",      50,  85,  55,  90,  65),
    0xA4: _s("Rapidash",    "Fire",     "Fire",      65, 100,  70, 105,  80),
    # Magnemite/Magneton
    0xAD: _s("Magnemite",   "Electric", "Electric",  25,  35,  70,  45,  95),
    0x36: _s("Magneton",    "Electric", "Electric",  50,  60,  95,  70, 120),
    # Doduo/Dodrio
    0x46: _s("Doduo",       "Normal",   "Flying",    35,  85,  45,  75,  35),
    0x74: _s("Dodrio",      "Normal",   "Flying",    60, 110,  70, 100,  60),
    # Gastly line
    0x19: _s("Gastly",      "Ghost",    "Poison",    30,  35,  30,  80, 100),
    0x93: _s("Haunter",     "Ghost",    "Poison",    45,  50,  45,  95, 115),
    0x0E: _s("Gengar",      "Ghost",    "Poison",    60,  65,  60, 110, 130),
    # Onix
    0x22: _s("Onix",        "Rock",     "Ground",    35,  45, 160,  70,  30),
    # Voltorb/Electrode
    0x06: _s("Voltorb",     "Electric", "Electric",  40,  30,  50, 100,  55),
    0x8D: _s("Electrode",   "Electric", "Electric",  60,  50,  70, 140,  80),
    # Exeggcute/Exeggutor
    0x0C: _s("Exeggcute",   "Grass",    "Psychic",   60,  40,  80,  40,  60),
    0x0A: _s("Exeggutor",   "Grass",    "Psychic",   95,  95,  85,  55, 125),
    # Hitmonlee/Hitmonchan
    0x2B: _s("Hitmonlee",   "Fighting", "Fighting",  50, 120,  53,  87,  35),
    0x2C: _s("Hitmonchan",  "Fighting", "Fighting",  50, 105,  79,  76,  35),
    # Chansey
    0x28: _s("Chansey",     "Normal",   "Normal",   250,   5,   5,  50, 105),
    # Staryu/Starmie
    0x1B: _s("Staryu",      "Water",    "Water",     30,  45,  55,  85,  70),
    0x98: _s("Starmie",     "Water",    "Psychic",   60,  75,  85, 115, 100),
    # Mr. Mime
    0x2A: _s("Mr. Mime",    "Psychic",  "Psychic",   40,  45,  65,  90, 100),
    # Scyther
    0x1A: _s("Scyther",     "Bug",      "Flying",    70, 110,  80, 105,  55),
    # Jynx
    0x48: _s("Jynx",        "Ice",      "Psychic",   65,  50,  35,  95,  95),
    # Electabuzz
    0x35: _s("Electabuzz",  "Electric", "Electric",  65,  83,  57, 105,  85),
    # Magmar
    0x33: _s("Magmar",      "Fire",     "Fire",      65,  95,  57,  93,  85),
    # Pinsir
    0x1D: _s("Pinsir",      "Bug",      "Bug",       65, 125, 100,  85,  55),
    # Tauros
    0x3C: _s("Tauros",      "Normal",   "Normal",    75, 100,  95, 110,  70),
    # Magikarp/Gyarados
    0x85: _s("Magikarp",    "Water",    "Water",     20,  10,  55,  80,  20),
    0x16: _s("Gyarados",    "Water",    "Flying",    95, 125,  79,  81, 100),
    # Lapras
    0x13: _s("Lapras",      "Water",    "Ice",      130,  85,  80,  60,  95),
    # Ditto
    0x4C: _s("Ditto",       "Normal",   "Normal",    48,  48,  48,  48,  48),
    # Eevee line
    0x66: _s("Eevee",       "Normal",   "Normal",    55,  55,  50,  55,  65),
    0x69: _s("Vaporeon",    "Water",    "Water",    130,  65,  60,  65, 110),
    0x68: _s("Jolteon",     "Electric", "Electric",  65,  65,  60, 130, 110),
    0x67: _s("Flareon",     "Fire",     "Fire",      65, 130,  60,  65, 110),
    # Porygon
    0xAA: _s("Porygon",     "Normal",   "Normal",    65,  60,  70,  40,  75),
    # Snorlax
    0x84: _s("Snorlax",     "Normal",   "Normal",   160, 110,  65,  30,  65),
    # Legendary birds
    0x4A: _s("Articuno",    "Ice",      "Flying",    90,  85, 100,  85, 125),
    0x4B: _s("Zapdos",      "Electric", "Flying",    90,  90,  85, 100, 125),
    0x49: _s("Moltres",     "Fire",     "Flying",    90, 100,  90,  90, 125),
    # Dratini line
    0x58: _s("Dratini",     "Dragon",   "Dragon",    41,  64,  45,  50,  50),
    0x59: _s("Dragonair",   "Dragon",   "Dragon",    61,  84,  65,  70,  70),
    0x42: _s("Dragonite",   "Dragon",   "Flying",    91, 134,  95,  80, 100),
    # Mewtwo/Mew
    0x83: _s("Mewtwo",      "Psychic",  "Psychic",  106, 110,  90, 130, 154),
    0x15: _s("Mew",         "Psychic",  "Psychic",  100, 100, 100, 100, 100),
    # Ekans/Arbok (Jessie's Pokemon in Yellow)
    0x6C: _s("Ekans",       "Poison",   "Poison",    35,  60,  44,  55,  40),
    0x2D: _s("Arbok",       "Poison",   "Poison",    60,  85,  69,  80,  65),
    # Sandshrew/Sandslash
    0x60: _s("Sandshrew",   "Ground",   "Ground",    50,  75,  85,  40,  30),
    0x61: _s("Sandslash",   "Ground",   "Ground",    75, 100, 110,  65,  55),
    # Tentacool/Tentacruel
    0x18: _s("Tentacool",   "Water",    "Poison",    40,  40,  35,  70, 100),
    0x9B: _s("Tentacruel",  "Water",    "Poison",    80,  70,  65, 100, 120),
    # Slowpoke/Slowbro
    0x25: _s("Slowpoke",    "Water",    "Psychic",   90,  65,  65,  15,  40),
    0x08: _s("Slowbro",     "Water",    "Psychic",   95,  75, 110,  30,  80),
    # Koffing/Weezing (James's Pokemon in Yellow)
    0x37: _s("Koffing",     "Poison",   "Poison",    40,  65,  95,  35,  60),
    0x8F: _s("Weezing",     "Poison",   "Poison",    65,  90, 120,  60,  85),
    # Rhyhorn/Rhydon
    0x12: _s("Rhyhorn",     "Ground",   "Rock",      80,  85,  95,  25,  30),
    0x01: _s("Rhydon",      "Ground",   "Rock",     105, 130, 120,  40,  45),
    # Kangaskhan
    0x02: _s("Kangaskhan",  "Normal",   "Normal",   105,  95,  80,  90,  40),
    # Horsea/Seadra
    0x5C: _s("Horsea",      "Water",    "Water",     30,  40,  70,  60,  70),
    0x5D: _s("Seadra",      "Water",    "Water",     55,  65,  95,  85,  95),
    # Goldeen/Seaking
    0x9D: _s("Goldeen",     "Water",    "Water",     45,  67,  60,  63,  50),
    0x9E: _s("Seaking",     "Water",    "Water",     80,  92,  65,  68,  80),
    # Cubone/Marowak
    0x11: _s("Cubone",      "Ground",   "Ground",    50,  50,  95,  35,  40),
    0x91: _s("Marowak",     "Ground",   "Ground",    60,  80, 110,  45,  50),
    # Lickitung
    0x0B: _s("Lickitung",   "Normal",   "Normal",    90,  55,  75,  30,  60),
    # Paras/Parasect
    0x6D: _s("Paras",        "Bug",      "Grass",     35,  70,  55,  25,  55),
    0x2E: _s("Parasect",     "Bug",      "Grass",     60,  95,  80,  30,  80),
    # Venonat/Venomoth
    0x41: _s("Venonat",      "Bug",      "Poison",    60,  55,  50,  45,  40),
    0x77: _s("Venomoth",     "Bug",      "Poison",    70,  65,  60,  90,  90),
    # Bellsprout line
    0xBC: _s("Bellsprout",   "Grass",    "Poison",    50,  75,  35,  40,  70),
    0xBD: _s("Weepinbell",   "Grass",    "Poison",    65,  90,  50,  55,  85),
    0xBE: _s("Victreebel",   "Grass",    "Poison",    80, 105,  65,  70, 100),
    # Farfetch'd
    0x40: _s("Farfetch'd",   "Normal",   "Flying",    52,  65,  55,  60,  58),
    # Seel/Dewgong
    0x3A: _s("Seel",         "Water",    "Water",     65,  45,  55,  45,  70),
    0x78: _s("Dewgong",      "Water",    "Ice",       90,  70,  80,  70,  95),
    # Grimer/Muk
    0x0D: _s("Grimer",       "Poison",   "Poison",    80,  80,  50,  25,  40),
    0x88: _s("Muk",          "Poison",   "Poison",   105, 105,  75,  50,  65),
    # Shellder/Cloyster
    0x17: _s("Shellder",     "Water",    "Water",     30,  65, 100,  40,  45),
    0x8B: _s("Cloyster",     "Water",    "Ice",       50,  95, 180,  70,  85),
    # Drowzee/Hypno
    0x30: _s("Drowzee",      "Psychic",  "Psychic",   60,  48,  45,  42,  90),
    0x81: _s("Hypno",        "Psychic",  "Psychic",   85,  73,  67,  67, 115),
    # Krabby/Kingler
    0x4E: _s("Krabby",       "Water",    "Water",     30, 105,  90,  50,  25),
    0x8A: _s("Kingler",      "Water",    "Water",     55, 130, 115,  75,  50),
    # Tangela
    0x1E: _s("Tangela",      "Grass",    "Grass",     65,  55, 115,  60, 100),
    # Omanyte/Omastar
    0x62: _s("Omanyte",      "Rock",     "Water",     35,  40, 100,  35,  90),
    0x63: _s("Omastar",      "Rock",     "Water",     70,  60, 125,  55, 115),
    # Kabuto/Kabutops
    0x5A: _s("Kabuto",       "Rock",     "Water",     30,  80,  90,  55,  45),
    0x5B: _s("Kabutops",     "Rock",     "Water",     60, 115, 105,  80,  70),
    # Aerodactyl
    0xAB: _s("Aerodactyl",   "Rock",     "Flying",    80, 105,  65, 130,  60),
}


# ============================================================
# Internal Index <-> Pokedex Number
# ============================================================

INTERNAL_TO_POKEDEX = {
    0x01: 112, 0x02: 115, 0x03: 32,  0x04: 35,  0x05: 21,
    0x06: 100, 0x07: 34,  0x08: 80,  0x09: 2,   0x0A: 103,
    0x0B: 108, 0x0C: 102, 0x0D: 88,  0x0E: 94,  0x0F: 29,
    0x10: 31,  0x11: 104, 0x12: 111, 0x13: 131, 0x14: 59,
    0x15: 151, 0x16: 130, 0x17: 90,  0x18: 72,  0x19: 92,
    0x1A: 123, 0x1B: 120, 0x1C: 9,   0x1D: 127, 0x1E: 114,
    0x21: 58,  0x22: 95,  0x23: 22,  0x24: 16,  0x25: 79,
    0x26: 64,  0x27: 75,  0x28: 113, 0x29: 67,  0x2A: 122,
    0x2B: 106, 0x2C: 107, 0x2D: 24,  0x2E: 47,  0x2F: 54,
    0x30: 96,  0x31: 76,  0x33: 126, 0x35: 125, 0x36: 82,
    0x37: 109, 0x39: 56,  0x3A: 86,  0x3B: 50,  0x3C: 128,
    0x40: 83,  0x41: 48,  0x42: 149, 0x46: 84,  0x47: 60,
    0x48: 124, 0x49: 146, 0x4A: 144, 0x4B: 145, 0x4C: 132,
    0x4D: 52,  0x4E: 98,  0x52: 37,  0x53: 38,  0x54: 25,
    0x55: 26,  0x58: 147, 0x59: 148, 0x5A: 140, 0x5B: 141,
    0x5C: 116, 0x5D: 117, 0x60: 27,  0x61: 28,  0x62: 138,
    0x63: 139, 0x64: 39,  0x65: 40,  0x66: 133, 0x67: 136,
    0x68: 135, 0x69: 134, 0x6A: 66,  0x6B: 41,  0x6C: 23,
    0x6D: 46,  0x6E: 61,  0x6F: 62,  0x70: 13,  0x71: 14,
    0x72: 15,  0x74: 85,  0x75: 57,  0x76: 51,  0x77: 49,
    0x78: 87,  0x7B: 10,  0x7C: 11,  0x7D: 12,  0x7E: 68,
    0x80: 55,  0x81: 97,  0x82: 42,  0x83: 150, 0x84: 143,
    0x85: 129, 0x88: 89,  0x8A: 99,  0x8B: 91,  0x8D: 101,
    0x8E: 36,  0x8F: 110, 0x90: 53,  0x91: 105, 0x93: 93,
    0x94: 63,  0x95: 65,  0x96: 17,  0x97: 18,  0x98: 121,
    0x99: 1,   0x9A: 3,   0x9B: 73,  0x9D: 118, 0x9E: 119,
    0xA3: 77,  0xA4: 78,  0xA5: 19,  0xA6: 20,  0xA7: 33,
    0xA8: 30,  0xA9: 74,  0xAA: 137, 0xAB: 142, 0xAD: 81,
    0xB0: 4,   0xB1: 7,   0xB2: 5,   0xB3: 8,   0xB4: 6,
    0xB9: 43,  0xBA: 44,  0xBB: 45,  0xBC: 69,  0xBD: 70,
    0xBE: 71,
}

POKEDEX_TO_INTERNAL = {v: k for k, v in INTERNAL_TO_POKEDEX.items()}


# ============================================================
# Type System
# ============================================================

TYPE_NAMES = {
    0x00: "Normal",   0x01: "Fighting", 0x02: "Flying",
    0x03: "Poison",   0x04: "Ground",   0x05: "Rock",
    0x07: "Bug",      0x08: "Ghost",
    0x14: "Fire",     0x15: "Water",    0x16: "Grass",
    0x17: "Electric", 0x18: "Psychic",  0x19: "Ice",
    0x1A: "Dragon",
}

TYPE_ID = {v: k for k, v in TYPE_NAMES.items()}

# Only non-1.0 entries (attacking_type_name, defending_type_name) -> multiplier
TYPE_EFFECTIVENESS = {
    ("Normal", "Rock"):     0.5, ("Normal", "Ghost"):    0,
    ("Fighting", "Normal"): 2,   ("Fighting", "Flying"):  0.5,
    ("Fighting", "Poison"): 0.5, ("Fighting", "Bug"):     0.5,
    ("Fighting", "Rock"):   2,   ("Fighting", "Ghost"):   0,
    ("Fighting", "Psychic"):0.5, ("Fighting", "Ice"):     2,
    ("Flying", "Fighting"): 2,   ("Flying", "Rock"):      0.5,
    ("Flying", "Bug"):      2,   ("Flying", "Grass"):     2,
    ("Flying", "Electric"): 0.5,
    ("Poison", "Poison"):   0.5, ("Poison", "Ground"):    0.5,
    ("Poison", "Rock"):     0.5, ("Poison", "Bug"):       2,
    ("Poison", "Ghost"):    0.5, ("Poison", "Grass"):     2,
    ("Ground", "Flying"):   0,   ("Ground", "Bug"):       0.5,
    ("Ground", "Fire"):     2,   ("Ground", "Electric"):  2,
    ("Ground", "Rock"):     2,   ("Ground", "Poison"):    2,
    ("Ground", "Grass"):    0.5,
    ("Rock", "Fighting"):   0.5, ("Rock", "Ground"):      0.5,
    ("Rock", "Flying"):     2,   ("Rock", "Bug"):         2,
    ("Rock", "Fire"):       2,   ("Rock", "Ice"):         2,
    ("Bug", "Fighting"):    0.5, ("Bug", "Flying"):       0.5,
    ("Bug", "Poison"):      2,   ("Bug", "Ghost"):        0.5,
    ("Bug", "Fire"):        0.5, ("Bug", "Grass"):        2,
    ("Bug", "Psychic"):     2,
    ("Ghost", "Normal"):    0,   ("Ghost", "Ghost"):      2,
    ("Ghost", "Psychic"):   0,
    ("Fire", "Rock"):       0.5, ("Fire", "Fire"):        0.5,
    ("Fire", "Water"):      0.5, ("Fire", "Grass"):       2,
    ("Fire", "Ice"):        2,   ("Fire", "Bug"):         2,
    ("Fire", "Dragon"):     0.5,
    ("Water", "Water"):     0.5, ("Water", "Grass"):      0.5,
    ("Water", "Fire"):      2,   ("Water", "Ground"):     2,
    ("Water", "Rock"):      2,   ("Water", "Dragon"):     0.5,
    ("Grass", "Flying"):    0.5, ("Grass", "Poison"):     0.5,
    ("Grass", "Bug"):       0.5, ("Grass", "Fire"):       0.5,
    ("Grass", "Water"):     2,   ("Grass", "Grass"):      0.5,
    ("Grass", "Ground"):    2,   ("Grass", "Rock"):       2,
    ("Grass", "Dragon"):    0.5,
    ("Electric", "Flying"):  2,  ("Electric", "Ground"):   0,
    ("Electric", "Water"):   2,  ("Electric", "Grass"):    0.5,
    ("Electric", "Electric"):0.5,("Electric", "Dragon"):   0.5,
    ("Psychic", "Fighting"): 2,  ("Psychic", "Poison"):    2,
    ("Psychic", "Psychic"):  0.5,
    ("Ice", "Flying"):      2,   ("Ice", "Ground"):       2,
    ("Ice", "Water"):       0.5, ("Ice", "Grass"):        2,
    ("Ice", "Ice"):         0.5, ("Ice", "Dragon"):       2,
    ("Dragon", "Dragon"):   2,
}


# ============================================================
# Moves (move index -> data)
# ============================================================

MOVES = {
    1:  {"name": "Pound",          "type": "Normal",   "power": 40,  "accuracy": 100, "pp": 35},
    2:  {"name": "Karate Chop",    "type": "Normal",   "power": 50,  "accuracy": 100, "pp": 25},
    3:  {"name": "Double Slap",    "type": "Normal",   "power": 15,  "accuracy": 85,  "pp": 10},
    4:  {"name": "Comet Punch",    "type": "Normal",   "power": 18,  "accuracy": 85,  "pp": 15},
    5:  {"name": "Mega Punch",     "type": "Normal",   "power": 80,  "accuracy": 85,  "pp": 20},
    6:  {"name": "Pay Day",        "type": "Normal",   "power": 40,  "accuracy": 100, "pp": 20},
    7:  {"name": "Fire Punch",     "type": "Fire",     "power": 75,  "accuracy": 100, "pp": 15},
    8:  {"name": "Ice Punch",      "type": "Ice",      "power": 75,  "accuracy": 100, "pp": 15},
    9:  {"name": "Thunder Punch",  "type": "Electric", "power": 75,  "accuracy": 100, "pp": 15},
    10: {"name": "Scratch",        "type": "Normal",   "power": 40,  "accuracy": 100, "pp": 35},
    11: {"name": "Vice Grip",      "type": "Normal",   "power": 55,  "accuracy": 100, "pp": 30},
    12: {"name": "Guillotine",     "type": "Normal",   "power": 0,   "accuracy": 30,  "pp": 5},
    13: {"name": "Razor Wind",     "type": "Normal",   "power": 80,  "accuracy": 75,  "pp": 10},
    14: {"name": "Swords Dance",   "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 30},
    15: {"name": "Cut",            "type": "Normal",   "power": 50,  "accuracy": 95,  "pp": 30},
    16: {"name": "Gust",           "type": "Normal",   "power": 40,  "accuracy": 100, "pp": 35},
    17: {"name": "Wing Attack",    "type": "Flying",   "power": 35,  "accuracy": 100, "pp": 35},
    18: {"name": "Whirlwind",      "type": "Normal",   "power": 0,   "accuracy": 85,  "pp": 20},
    19: {"name": "Fly",            "type": "Flying",   "power": 70,  "accuracy": 95,  "pp": 15},
    20: {"name": "Bind",           "type": "Normal",   "power": 15,  "accuracy": 75,  "pp": 20},
    21: {"name": "Slam",           "type": "Normal",   "power": 80,  "accuracy": 75,  "pp": 20},
    22: {"name": "Vine Whip",      "type": "Grass",    "power": 35,  "accuracy": 100, "pp": 10},
    23: {"name": "Stomp",          "type": "Normal",   "power": 65,  "accuracy": 100, "pp": 20},
    24: {"name": "Double Kick",    "type": "Fighting", "power": 30,  "accuracy": 100, "pp": 30},
    25: {"name": "Mega Kick",      "type": "Normal",   "power": 120, "accuracy": 75,  "pp": 5},
    26: {"name": "Jump Kick",      "type": "Fighting", "power": 70,  "accuracy": 95,  "pp": 25},
    27: {"name": "Rolling Kick",   "type": "Fighting", "power": 60,  "accuracy": 85,  "pp": 15},
    28: {"name": "Sand Attack",    "type": "Ground",   "power": 0,   "accuracy": 100, "pp": 15},
    29: {"name": "Headbutt",       "type": "Normal",   "power": 70,  "accuracy": 100, "pp": 15},
    30: {"name": "Horn Attack",    "type": "Normal",   "power": 65,  "accuracy": 100, "pp": 25},
    31: {"name": "Fury Attack",    "type": "Normal",   "power": 15,  "accuracy": 85,  "pp": 20},
    32: {"name": "Horn Drill",     "type": "Normal",   "power": 0,   "accuracy": 30,  "pp": 5},
    33: {"name": "Tackle",         "type": "Normal",   "power": 35,  "accuracy": 95,  "pp": 35},
    34: {"name": "Body Slam",      "type": "Normal",   "power": 85,  "accuracy": 100, "pp": 15},
    35: {"name": "Wrap",           "type": "Normal",   "power": 15,  "accuracy": 85,  "pp": 20},
    36: {"name": "Take Down",      "type": "Normal",   "power": 90,  "accuracy": 85,  "pp": 20},
    37: {"name": "Thrash",         "type": "Normal",   "power": 90,  "accuracy": 100, "pp": 20},
    38: {"name": "Double-Edge",    "type": "Normal",   "power": 100, "accuracy": 100, "pp": 15},
    39: {"name": "Tail Whip",      "type": "Normal",   "power": 0,   "accuracy": 100, "pp": 30},
    40: {"name": "Poison Sting",   "type": "Poison",   "power": 15,  "accuracy": 100, "pp": 35},
    41: {"name": "Twineedle",      "type": "Bug",      "power": 25,  "accuracy": 100, "pp": 20},
    42: {"name": "Pin Missile",    "type": "Bug",      "power": 14,  "accuracy": 85,  "pp": 20},
    43: {"name": "Leer",           "type": "Normal",   "power": 0,   "accuracy": 100, "pp": 30},
    44: {"name": "Bite",           "type": "Normal",   "power": 60,  "accuracy": 100, "pp": 25},
    45: {"name": "Growl",          "type": "Normal",   "power": 0,   "accuracy": 100, "pp": 40},
    46: {"name": "Roar",           "type": "Normal",   "power": 0,   "accuracy": 100, "pp": 20},
    47: {"name": "Sing",           "type": "Normal",   "power": 0,   "accuracy": 55,  "pp": 15},
    48: {"name": "Supersonic",     "type": "Normal",   "power": 0,   "accuracy": 55,  "pp": 20},
    49: {"name": "Sonic Boom",     "type": "Normal",   "power": 0,   "accuracy": 90,  "pp": 20},
    50: {"name": "Disable",        "type": "Normal",   "power": 0,   "accuracy": 55,  "pp": 20},
    51: {"name": "Acid",           "type": "Poison",   "power": 40,  "accuracy": 100, "pp": 30},
    52: {"name": "Ember",          "type": "Fire",     "power": 40,  "accuracy": 100, "pp": 25},
    53: {"name": "Flamethrower",   "type": "Fire",     "power": 95,  "accuracy": 100, "pp": 15},
    54: {"name": "Mist",           "type": "Ice",      "power": 0,   "accuracy": 0,   "pp": 30},
    55: {"name": "Water Gun",      "type": "Water",    "power": 40,  "accuracy": 100, "pp": 25},
    56: {"name": "Hydro Pump",     "type": "Water",    "power": 120, "accuracy": 80,  "pp": 5},
    57: {"name": "Surf",           "type": "Water",    "power": 95,  "accuracy": 100, "pp": 15},
    58: {"name": "Ice Beam",       "type": "Ice",      "power": 95,  "accuracy": 100, "pp": 10},
    59: {"name": "Blizzard",       "type": "Ice",      "power": 120, "accuracy": 90,  "pp": 5},
    60: {"name": "Psybeam",        "type": "Psychic",  "power": 65,  "accuracy": 100, "pp": 20},
    61: {"name": "Bubble Beam",    "type": "Water",    "power": 65,  "accuracy": 100, "pp": 20},
    62: {"name": "Aurora Beam",    "type": "Ice",      "power": 65,  "accuracy": 100, "pp": 20},
    63: {"name": "Hyper Beam",     "type": "Normal",   "power": 150, "accuracy": 90,  "pp": 5},
    64: {"name": "Peck",           "type": "Flying",   "power": 35,  "accuracy": 100, "pp": 35},
    65: {"name": "Drill Peck",     "type": "Flying",   "power": 80,  "accuracy": 100, "pp": 20},
    66: {"name": "Submission",     "type": "Fighting", "power": 80,  "accuracy": 80,  "pp": 25},
    67: {"name": "Low Kick",       "type": "Fighting", "power": 50,  "accuracy": 90,  "pp": 20},
    68: {"name": "Counter",        "type": "Fighting", "power": 0,   "accuracy": 100, "pp": 20},
    69: {"name": "Seismic Toss",   "type": "Fighting", "power": 0,   "accuracy": 100, "pp": 20},
    70: {"name": "Strength",       "type": "Normal",   "power": 80,  "accuracy": 100, "pp": 15},
    71: {"name": "Absorb",         "type": "Grass",    "power": 20,  "accuracy": 100, "pp": 20},
    72: {"name": "Mega Drain",     "type": "Grass",    "power": 40,  "accuracy": 100, "pp": 10},
    73: {"name": "Leech Seed",     "type": "Grass",    "power": 0,   "accuracy": 90,  "pp": 10},
    74: {"name": "Growth",         "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 40},
    75: {"name": "Razor Leaf",     "type": "Grass",    "power": 55,  "accuracy": 95,  "pp": 25},
    76: {"name": "Solar Beam",     "type": "Grass",    "power": 120, "accuracy": 100, "pp": 10},
    77: {"name": "Poison Powder",  "type": "Poison",   "power": 0,   "accuracy": 75,  "pp": 35},
    78: {"name": "Stun Spore",     "type": "Grass",    "power": 0,   "accuracy": 75,  "pp": 30},
    79: {"name": "Sleep Powder",   "type": "Grass",    "power": 0,   "accuracy": 75,  "pp": 15},
    80: {"name": "Petal Dance",    "type": "Grass",    "power": 70,  "accuracy": 100, "pp": 20},
    81: {"name": "String Shot",    "type": "Bug",      "power": 0,   "accuracy": 95,  "pp": 40},
    82: {"name": "Dragon Rage",    "type": "Dragon",   "power": 0,   "accuracy": 100, "pp": 10},
    83: {"name": "Fire Spin",      "type": "Fire",     "power": 15,  "accuracy": 70,  "pp": 15},
    84: {"name": "Thunder Shock",  "type": "Electric", "power": 40,  "accuracy": 100, "pp": 30},
    85: {"name": "Thunderbolt",    "type": "Electric", "power": 95,  "accuracy": 100, "pp": 15},
    86: {"name": "Thunder Wave",   "type": "Electric", "power": 0,   "accuracy": 100, "pp": 20},
    87: {"name": "Thunder",        "type": "Electric", "power": 120, "accuracy": 70,  "pp": 10},
    88: {"name": "Rock Throw",     "type": "Rock",     "power": 50,  "accuracy": 65,  "pp": 15},
    89: {"name": "Earthquake",     "type": "Ground",   "power": 100, "accuracy": 100, "pp": 10},
    90: {"name": "Fissure",        "type": "Ground",   "power": 0,   "accuracy": 30,  "pp": 5},
    91: {"name": "Dig",            "type": "Ground",   "power": 100, "accuracy": 100, "pp": 10},
    92: {"name": "Toxic",          "type": "Poison",   "power": 0,   "accuracy": 85,  "pp": 10},
    93: {"name": "Confusion",      "type": "Psychic",  "power": 50,  "accuracy": 100, "pp": 25},
    94: {"name": "Psychic",        "type": "Psychic",  "power": 90,  "accuracy": 100, "pp": 10},
    95: {"name": "Hypnosis",       "type": "Psychic",  "power": 0,   "accuracy": 60,  "pp": 20},
    96: {"name": "Meditate",       "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 40},
    97: {"name": "Agility",        "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 30},
    98: {"name": "Quick Attack",   "type": "Normal",   "power": 40,  "accuracy": 100, "pp": 30},
    99: {"name": "Rage",           "type": "Normal",   "power": 20,  "accuracy": 100, "pp": 20},
    100: {"name": "Teleport",      "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 20},
    101: {"name": "Night Shade",   "type": "Ghost",    "power": 0,   "accuracy": 100, "pp": 15},
    102: {"name": "Mimic",         "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 10},
    103: {"name": "Screech",       "type": "Normal",   "power": 0,   "accuracy": 85,  "pp": 40},
    104: {"name": "Double Team",   "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 15},
    105: {"name": "Recover",       "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 20},
    106: {"name": "Harden",        "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 30},
    107: {"name": "Minimize",      "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 20},
    108: {"name": "Smokescreen",   "type": "Normal",   "power": 0,   "accuracy": 100, "pp": 20},
    109: {"name": "Confuse Ray",   "type": "Ghost",    "power": 0,   "accuracy": 100, "pp": 10},
    110: {"name": "Withdraw",      "type": "Water",    "power": 0,   "accuracy": 0,   "pp": 40},
    111: {"name": "Defense Curl",  "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 40},
    112: {"name": "Barrier",       "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 30},
    113: {"name": "Light Screen",  "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 30},
    114: {"name": "Haze",          "type": "Ice",      "power": 0,   "accuracy": 0,   "pp": 30},
    115: {"name": "Reflect",       "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 20},
    116: {"name": "Focus Energy",  "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 30},
    117: {"name": "Bide",          "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 10},
    118: {"name": "Metronome",     "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 10},
    119: {"name": "Mirror Move",   "type": "Flying",   "power": 0,   "accuracy": 0,   "pp": 20},
    120: {"name": "Self-Destruct", "type": "Normal",   "power": 130, "accuracy": 100, "pp": 5},
    121: {"name": "Egg Bomb",      "type": "Normal",   "power": 100, "accuracy": 75,  "pp": 10},
    122: {"name": "Lick",          "type": "Ghost",    "power": 20,  "accuracy": 100, "pp": 30},
    123: {"name": "Smog",          "type": "Poison",   "power": 20,  "accuracy": 70,  "pp": 20},
    124: {"name": "Sludge",        "type": "Poison",   "power": 65,  "accuracy": 100, "pp": 20},
    125: {"name": "Bone Club",     "type": "Ground",   "power": 65,  "accuracy": 85,  "pp": 20},
    126: {"name": "Fire Blast",    "type": "Fire",     "power": 120, "accuracy": 85,  "pp": 5},
    127: {"name": "Waterfall",     "type": "Water",    "power": 80,  "accuracy": 100, "pp": 15},
    128: {"name": "Clamp",         "type": "Water",    "power": 35,  "accuracy": 75,  "pp": 10},
    129: {"name": "Swift",         "type": "Normal",   "power": 60,  "accuracy": 0,   "pp": 20},
    130: {"name": "Skull Bash",    "type": "Normal",   "power": 100, "accuracy": 100, "pp": 15},
    131: {"name": "Spike Cannon",  "type": "Normal",   "power": 20,  "accuracy": 100, "pp": 15},
    132: {"name": "Constrict",     "type": "Normal",   "power": 10,  "accuracy": 100, "pp": 35},
    133: {"name": "Amnesia",       "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 20},
    134: {"name": "Kinesis",       "type": "Psychic",  "power": 0,   "accuracy": 80,  "pp": 15},
    135: {"name": "Soft-Boiled",   "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 10},
    136: {"name": "High Jump Kick","type": "Fighting",  "power": 85,  "accuracy": 90,  "pp": 20},
    137: {"name": "Glare",         "type": "Normal",   "power": 0,   "accuracy": 75,  "pp": 30},
    138: {"name": "Dream Eater",   "type": "Psychic",  "power": 100, "accuracy": 100, "pp": 15},
    139: {"name": "Poison Gas",    "type": "Poison",   "power": 0,   "accuracy": 55,  "pp": 40},
    140: {"name": "Barrage",       "type": "Normal",   "power": 15,  "accuracy": 85,  "pp": 20},
    141: {"name": "Leech Life",    "type": "Bug",      "power": 20,  "accuracy": 100, "pp": 15},
    142: {"name": "Lovely Kiss",   "type": "Normal",   "power": 0,   "accuracy": 75,  "pp": 10},
    143: {"name": "Sky Attack",    "type": "Flying",   "power": 140, "accuracy": 90,  "pp": 5},
    144: {"name": "Transform",     "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 10},
    145: {"name": "Bubble",        "type": "Water",    "power": 20,  "accuracy": 100, "pp": 30},
    146: {"name": "Dizzy Punch",   "type": "Normal",   "power": 70,  "accuracy": 100, "pp": 10},
    147: {"name": "Spore",         "type": "Grass",    "power": 0,   "accuracy": 100, "pp": 15},
    148: {"name": "Flash",         "type": "Normal",   "power": 0,   "accuracy": 70,  "pp": 20},
    149: {"name": "Psywave",       "type": "Psychic",  "power": 0,   "accuracy": 80,  "pp": 15},
    150: {"name": "Splash",        "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 40},
    151: {"name": "Acid Armor",    "type": "Poison",   "power": 0,   "accuracy": 0,   "pp": 40},
    152: {"name": "Crabhammer",    "type": "Water",    "power": 90,  "accuracy": 85,  "pp": 10},
    153: {"name": "Explosion",     "type": "Normal",   "power": 170, "accuracy": 100, "pp": 5},
    154: {"name": "Fury Swipes",   "type": "Normal",   "power": 18,  "accuracy": 80,  "pp": 15},
    155: {"name": "Bonemerang",    "type": "Ground",   "power": 50,  "accuracy": 90,  "pp": 10},
    156: {"name": "Rest",          "type": "Psychic",  "power": 0,   "accuracy": 0,   "pp": 10},
    157: {"name": "Rock Slide",    "type": "Rock",     "power": 75,  "accuracy": 90,  "pp": 10},
    158: {"name": "Hyper Fang",    "type": "Normal",   "power": 80,  "accuracy": 90,  "pp": 15},
    159: {"name": "Sharpen",       "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 30},
    160: {"name": "Conversion",    "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 30},
    161: {"name": "Tri Attack",    "type": "Normal",   "power": 80,  "accuracy": 100, "pp": 10},
    162: {"name": "Super Fang",    "type": "Normal",   "power": 0,   "accuracy": 90,  "pp": 10},
    163: {"name": "Slash",         "type": "Normal",   "power": 70,  "accuracy": 100, "pp": 20},
    164: {"name": "Substitute",    "type": "Normal",   "power": 0,   "accuracy": 0,   "pp": 10},
    165: {"name": "Struggle",      "type": "Normal",   "power": 50,  "accuracy": 100, "pp": 1},
}


# ============================================================
# Map Names
# ============================================================

MAP_NAMES = {
    # Cities and Towns
    0: "Pallet Town",          # $00
    1: "Viridian City",        # $01
    2: "Pewter City",          # $02
    3: "Cerulean City",        # $03
    4: "Lavender Town",        # $04
    5: "Vermilion City",       # $05
    6: "Celadon City",         # $06
    7: "Fuchsia City",         # $07
    8: "Cinnabar Island",      # $08
    9: "Indigo Plateau",       # $09
    10: "Saffron City",        # $0A
    # Routes
    12: "Route 1",             # $0C
    13: "Route 2",             # $0D
    14: "Route 3",             # $0E
    15: "Route 4",             # $0F
    16: "Route 5",             # $10
    17: "Route 6",             # $11
    18: "Route 7",             # $12
    19: "Route 8",             # $13
    20: "Route 9",             # $14
    21: "Route 10",            # $15
    22: "Route 11",            # $16
    23: "Route 12",            # $17
    24: "Route 13",            # $18
    25: "Route 14",            # $19
    26: "Route 15",            # $1A
    27: "Route 16",            # $1B
    28: "Route 17",            # $1C
    29: "Route 18",            # $1D
    30: "Route 19",            # $1E
    31: "Route 20",            # $1F
    32: "Route 21",            # $20
    33: "Route 22",            # $21
    34: "Route 23",            # $22
    35: "Route 24",            # $23
    36: "Route 25",            # $24
    # Pallet Town buildings
    37: "Player House 1F",     # $25 REDS_HOUSE_1F
    38: "Player House 2F",     # $26 REDS_HOUSE_2F
    39: "Rival House",         # $27 BLUES_HOUSE
    40: "Oak's Lab",           # $28 OAKS_LAB
    # Viridian City buildings
    41: "Viridian Pokemon Center",     # $29
    42: "Viridian Mart",               # $2A
    43: "Viridian School",             # $2B
    44: "Viridian Nickname House",     # $2C
    45: "Viridian Gym",                # $2D
    # Route 2 area
    46: "Diglett's Cave (Route 2)",    # $2E
    47: "Viridian Forest North Gate",  # $2F
    48: "Route 2 Trade House",         # $30
    49: "Route 2 Gate",                # $31
    50: "Viridian Forest South Gate",  # $32
    51: "Viridian Forest",             # $33
    # Pewter City buildings
    52: "Pewter Museum 1F",            # $34
    53: "Pewter Museum 2F",            # $35
    54: "Pewter Gym",                  # $36
    55: "Pewter Nidoran House",        # $37
    56: "Pewter Mart",                 # $38
    57: "Pewter Speech House",         # $39
    58: "Pewter Pokemon Center",       # $3A
    # Mt. Moon
    59: "Mt. Moon 1F",                 # $3B
    60: "Mt. Moon B1F",                # $3C
    61: "Mt. Moon B2F",                # $3D
    # Cerulean City buildings
    62: "Cerulean Trashed House",      # $3E
    63: "Cerulean Melanie's House",    # $3F
    64: "Cerulean Pokemon Center",     # $40
    65: "Cerulean Gym",                # $41
    66: "Bike Shop",                   # $42
    67: "Cerulean Mart",               # $43
    68: "Mt. Moon Pokemon Center",     # $44
    69: "Cerulean Trashed House Copy", # $45
    # Route 5-8 area
    70: "Route 5 Gate",                # $46
    71: "Underground Path (Route 5)",  # $47
    72: "Day Care",                    # $48
    73: "Route 6 Gate",                # $49
    74: "Underground Path (Route 6)",  # $4A
    75: "Underground Path (Route 6) Copy", # $4B
    76: "Route 7 Gate",                # $4C
    77: "Underground Path (Route 7)",  # $4D
    78: "Underground Path (Route 7) Copy", # $4E
    79: "Route 8 Gate",                # $4F
    80: "Underground Path (Route 8)",  # $50
    # Rock Tunnel area
    81: "Rock Tunnel Pokemon Center",  # $51
    82: "Rock Tunnel 1F",             # $52
    # Power Plant
    83: "Power Plant",                 # $53
    # Route 11-12 area
    84: "Route 11 Gate 1F",            # $54
    85: "Diglett's Cave (Route 11)",   # $55
    86: "Route 11 Gate 2F",            # $56
    87: "Route 12 Gate 1F",            # $57
    # Bill's House
    88: "Bill's House",                # $58
    # Vermilion City buildings
    89: "Vermilion Pokemon Center",    # $59
    90: "Pokemon Fan Club",            # $5A
    91: "Vermilion Mart",              # $5B
    92: "Vermilion Gym",               # $5C
    93: "Vermilion Pidgey House",      # $5D
    94: "Vermilion Dock",              # $5E
    # SS Anne
    95: "SS Anne 1F",                  # $5F
    96: "SS Anne 2F",                  # $60
    97: "SS Anne 3F",                  # $61
    98: "SS Anne B1F",                 # $62
    99: "SS Anne Bow",                 # $63
    100: "SS Anne Kitchen",            # $64
    101: "SS Anne Captain's Room",     # $65
    102: "SS Anne 1F Rooms",           # $66
    103: "SS Anne 2F Rooms",           # $67
    104: "SS Anne B1F Rooms",          # $68
    # Victory Road / Pokemon League
    108: "Victory Road 1F",            # $6C
    113: "Lance's Room",               # $71
    118: "Hall of Fame",               # $76
    # Underground Paths
    119: "Underground Path (N-S)",     # $77
    120: "Champion's Room",            # $78
    121: "Underground Path (W-E)",     # $79
    # Celadon City buildings
    122: "Celadon Mart 1F",            # $7A
    123: "Celadon Mart 2F",            # $7B
    124: "Celadon Mart 3F",            # $7C
    125: "Celadon Mart 4F",            # $7D
    126: "Celadon Mart Roof",          # $7E
    127: "Celadon Mart Elevator",      # $7F
    128: "Celadon Mansion 1F",         # $80
    129: "Celadon Mansion 2F",         # $81
    130: "Celadon Mansion 3F",         # $82
    131: "Celadon Mansion Roof",       # $83
    132: "Celadon Mansion Roof House", # $84
    133: "Celadon Pokemon Center",     # $85
    134: "Celadon Gym",                # $86
    135: "Game Corner",                # $87
    136: "Celadon Mart 5F",            # $88
    137: "Game Corner Prize Room",     # $89
    138: "Celadon Diner",              # $8A
    139: "Celadon Chief House",        # $8B
    140: "Celadon Hotel",              # $8C
    # Lavender Town buildings
    141: "Lavender Pokemon Center",    # $8D
    142: "Pokemon Tower 1F",           # $8E
    143: "Pokemon Tower 2F",           # $8F
    144: "Pokemon Tower 3F",           # $90
    145: "Pokemon Tower 4F",           # $91
    146: "Pokemon Tower 5F",           # $92
    147: "Pokemon Tower 6F",           # $93
    148: "Pokemon Tower 7F",           # $94
    149: "Mr. Fuji's House",           # $95
    150: "Lavender Mart",              # $96
    151: "Lavender Cubone House",      # $97
    # Fuchsia City buildings
    152: "Fuchsia Mart",               # $98
    153: "Fuchsia Bill's Grandpa House", # $99
    154: "Fuchsia Pokemon Center",     # $9A
    155: "Warden's House",             # $9B
    156: "Safari Zone Gate",           # $9C
    157: "Fuchsia Gym",                # $9D
    158: "Fuchsia Meeting Room",       # $9E
    # Seafoam Islands
    159: "Seafoam Islands B1F",        # $9F
    160: "Seafoam Islands B2F",        # $A0
    161: "Seafoam Islands B3F",        # $A1
    162: "Seafoam Islands B4F",        # $A2
    # Vermilion extras
    163: "Vermilion Old Rod House",    # $A3
    164: "Fuchsia Good Rod House",     # $A4
    # Pokemon Mansion / Cinnabar
    165: "Pokemon Mansion 1F",         # $A5
    166: "Cinnabar Gym",               # $A6
    167: "Cinnabar Lab",               # $A7
    168: "Cinnabar Lab Trade Room",    # $A8
    169: "Cinnabar Lab Metronome Room", # $A9
    170: "Cinnabar Lab Fossil Room",   # $AA
    171: "Cinnabar Pokemon Center",    # $AB
    172: "Cinnabar Mart",              # $AC
    173: "Cinnabar Mart Copy",         # $AD
    # Indigo Plateau
    174: "Indigo Plateau Lobby",       # $AE
    # Saffron City buildings
    175: "Copycat's House 1F",         # $AF
    176: "Copycat's House 2F",         # $B0
    177: "Fighting Dojo",              # $B1
    178: "Saffron Gym",                # $B2
    179: "Saffron Pidgey House",       # $B3
    180: "Saffron Mart",               # $B4
    181: "Silph Co. 1F",               # $B5
    182: "Saffron Pokemon Center",     # $B6
    183: "Mr. Psychic's House",        # $B7
    # Route gates
    184: "Route 15 Gate 1F",           # $B8
    185: "Route 15 Gate 2F",           # $B9
    186: "Route 16 Gate 1F",           # $BA
    187: "Route 16 Gate 2F",           # $BB
    188: "Route 16 Fly House",         # $BC
    189: "Route 12 Super Rod House",   # $BD
    190: "Route 18 Gate 1F",           # $BE
    191: "Route 18 Gate 2F",           # $BF
    # More dungeons
    192: "Seafoam Islands 1F",         # $C0
    193: "Route 22 Gate",              # $C1
    194: "Victory Road 2F",            # $C2
    195: "Route 12 Gate 2F",           # $C3
    196: "Vermilion Trade House",      # $C4
    197: "Diglett's Cave",             # $C5
    198: "Victory Road 3F",            # $C6
    # Rocket Hideout
    199: "Rocket Hideout B1F",         # $C7
    200: "Rocket Hideout B2F",         # $C8
    201: "Rocket Hideout B3F",         # $C9
    202: "Rocket Hideout B4F",         # $CA
    203: "Rocket Hideout Elevator",    # $CB
    # Silph Co.
    207: "Silph Co. 2F",               # $CF
    208: "Silph Co. 3F",               # $D0
    209: "Silph Co. 4F",               # $D1
    210: "Silph Co. 5F",               # $D2
    211: "Silph Co. 6F",               # $D3
    212: "Silph Co. 7F",               # $D4
    213: "Silph Co. 8F",               # $D5
    # Pokemon Mansion upper floors
    214: "Pokemon Mansion 2F",         # $D6
    215: "Pokemon Mansion 3F",         # $D7
    216: "Pokemon Mansion B1F",        # $D8
    # Safari Zone
    217: "Safari Zone East",           # $D9
    218: "Safari Zone North",          # $DA
    219: "Safari Zone West",           # $DB
    220: "Safari Zone Center",         # $DC
    221: "Safari Zone Center Rest House", # $DD
    222: "Safari Zone Secret House",   # $DE
    223: "Safari Zone West Rest House", # $DF
    224: "Safari Zone East Rest House", # $E0
    225: "Safari Zone North Rest House", # $E1
    # Cerulean Cave
    226: "Cerulean Cave 2F",           # $E2
    227: "Cerulean Cave B1F",          # $E3
    228: "Cerulean Cave 1F",           # $E4
    # Misc
    229: "Name Rater's House",         # $E5
    230: "Cerulean Badge House",       # $E6
    232: "Rock Tunnel B1F",            # $E8
    # Silph Co. upper floors
    233: "Silph Co. 9F",               # $E9
    234: "Silph Co. 10F",              # $EA
    235: "Silph Co. 11F",              # $EB
    236: "Silph Co. Elevator",         # $EC
    # Link areas
    239: "Trade Center",               # $EF
    240: "Colosseum",                  # $F0
    # Elite Four
    245: "Lorelei's Room",             # $F5
    246: "Bruno's Room",               # $F6
    247: "Agatha's Room",              # $F7
    # Yellow-specific
    248: "Summer Beach House",         # $F8
}

# Pokecenter map IDs — used for cross-map warp detection
POKECENTER_MAP_IDS = {
    41,   # Viridian Pokemon Center
    58,   # Pewter Pokemon Center
    64,   # Cerulean Pokemon Center
    68,   # Mt. Moon Pokemon Center
    81,   # Rock Tunnel Pokemon Center
    89,   # Vermilion Pokemon Center
    133,  # Celadon Pokemon Center
    141,  # Lavender Pokemon Center
    154,  # Fuchsia Pokemon Center
    171,  # Cinnabar Pokemon Center
    182,  # Saffron Pokemon Center
    174,  # Indigo Plateau Lobby (has healing)
}

# Tileset names — sequential 0-24 per tileset_headers.asm
TILESET_NAMES = {
    0x00: "OVERWORLD",
    0x01: "REDS_HOUSE_1",
    0x02: "MART",
    0x03: "FOREST",
    0x04: "REDS_HOUSE_2",
    0x05: "DOJO",
    0x06: "POKECENTER",
    0x07: "GYM",
    0x08: "HOUSE",
    0x09: "FOREST_GATE",
    0x0A: "MUSEUM",
    0x0B: "UNDERGROUND",
    0x0C: "GATE",
    0x0D: "SHIP",
    0x0E: "SHIP_PORT",
    0x0F: "CEMETERY",
    0x10: "INTERIOR",
    0x11: "CAVERN",
    0x12: "LOBBY",
    0x13: "MANSION",
    0x14: "LAB",
    0x15: "CLUB",
    0x16: "FACILITY",
    0x17: "PLATEAU",
    0x18: "BEACH_HOUSE",
}


# ============================================================
# Item Names
# ============================================================

ITEM_NAMES = {
    0x01: "Master Ball", 0x02: "Ultra Ball", 0x03: "Great Ball",
    0x04: "Poke Ball", 0x06: "Bicycle", 0x08: "Safari Ball",
    0x09: "Pokedex", 0x0A: "Moon Stone",
    0x0B: "Antidote", 0x0C: "Burn Heal", 0x0D: "Ice Heal",
    0x0E: "Awakening", 0x0F: "Parlyz Heal",
    0x10: "Full Restore", 0x11: "Max Potion", 0x12: "Hyper Potion",
    0x13: "Super Potion", 0x14: "Potion",
    0x15: "Boulder Badge", 0x16: "Cascade Badge", 0x17: "Thunder Badge",
    0x18: "Rainbow Badge", 0x19: "Soul Badge", 0x1A: "Marsh Badge",
    0x1B: "Volcano Badge", 0x1C: "Earth Badge",
    0x1D: "Escape Rope", 0x1E: "Repel",
    0x1F: "Old Amber", 0x20: "Fire Stone", 0x21: "Thunder Stone",
    0x22: "Water Stone", 0x23: "HP Up", 0x24: "Protein",
    0x25: "Iron", 0x26: "Carbos", 0x27: "Calcium",
    0x28: "Rare Candy",
    0x29: "Dome Fossil", 0x2A: "Helix Fossil",
    0x2B: "Secret Key", 0x2C: "???",
    0x2D: "Bike Voucher", 0x2E: "X Accuracy",
    0x2F: "Leaf Stone", 0x30: "Card Key",
    0x31: "Nugget", 0x32: "PP Up",
    0x33: "Poke Doll", 0x34: "Full Heal",
    0x35: "Revive", 0x36: "Max Revive",
    0x37: "Guard Spec.", 0x38: "Super Repel", 0x39: "Max Repel",
    0x3A: "Dire Hit", 0x3B: "Coin",
    0x3C: "Fresh Water", 0x3D: "Soda Pop", 0x3E: "Lemonade",
    0x3F: "S.S. Ticket", 0x40: "Gold Teeth",
    0x41: "X Attack", 0x42: "X Defend",
    0x43: "X Speed", 0x44: "X Special",
    0x45: "Coin Case", 0x46: "Oak's Parcel",
    0x47: "Itemfinder", 0x48: "Silph Scope", 0x49: "Poke Flute",
    0x4A: "Lift Key", 0x4B: "Exp. All",
    0x4C: "Old Rod", 0x4D: "Good Rod", 0x4E: "Super Rod",
    0x4F: "PP Up", 0x50: "Ether", 0x51: "Max Ether",
    0x52: "Elixir", 0x53: "Max Elixir",
    0xC4: "HM01 Cut", 0xC5: "HM02 Fly",
    0xC6: "HM03 Surf", 0xC7: "HM04 Strength", 0xC8: "HM05 Flash",
    0xC9: "TM01 Mega Punch", 0xCA: "TM02 Razor Wind",
    0xCB: "TM03 Swords Dance", 0xCC: "TM04 Whirlwind",
    0xCD: "TM05 Mega Kick", 0xCE: "TM06 Toxic",
    0xCF: "TM07 Horn Drill", 0xD0: "TM08 Body Slam",
    0xD1: "TM09 Take Down", 0xD2: "TM10 Double-Edge",
    0xD3: "TM11 Bubble Beam", 0xD4: "TM12 Water Gun",
    0xD5: "TM13 Ice Beam", 0xD6: "TM14 Blizzard",
    0xD7: "TM15 Hyper Beam", 0xD8: "TM16 Pay Day",
    0xD9: "TM17 Submission", 0xDA: "TM18 Counter",
    0xDB: "TM19 Seismic Toss", 0xDC: "TM20 Rage",
    0xDD: "TM21 Mega Drain", 0xDE: "TM22 Solar Beam",
    0xDF: "TM23 Dragon Rage", 0xE0: "TM24 Thunderbolt",
    0xE1: "TM25 Thunder", 0xE2: "TM26 Earthquake",
    0xE3: "TM27 Fissure", 0xE4: "TM28 Dig",
    0xE5: "TM29 Psychic", 0xE6: "TM30 Teleport",
    0xE7: "TM31 Mimic", 0xE8: "TM32 Double Team",
    0xE9: "TM33 Reflect", 0xEA: "TM34 Bide",
    0xEB: "TM35 Metronome", 0xEC: "TM36 Self-Destruct",
    0xED: "TM37 Egg Bomb", 0xEE: "TM38 Fire Blast",
    0xEF: "TM39 Swift", 0xF0: "TM40 Skull Bash",
    0xF1: "TM41 Softboiled", 0xF2: "TM42 Dream Eater",
    0xF3: "TM43 Sky Attack", 0xF4: "TM44 Rest",
    0xF5: "TM45 Thunder Wave", 0xF6: "TM46 Psywave",
    0xF7: "TM47 Explosion", 0xF8: "TM48 Rock Slide",
    0xF9: "TM49 Tri Attack", 0xFA: "TM50 Substitute",
}


# ============================================================
# Map Name -> ID reverse lookup
# ============================================================

MAP_NAME_TO_ID: dict[str, int] = {}
for _id, _name in MAP_NAMES.items():
    # Store exact, lowercase, uppercase, and underscore-separated forms
    MAP_NAME_TO_ID[_name] = _id
    MAP_NAME_TO_ID[_name.lower()] = _id
    MAP_NAME_TO_ID[_name.upper()] = _id
    MAP_NAME_TO_ID[_name.upper().replace(" ", "_")] = _id


# ============================================================
# Map Adjacency Graph — static connections from pokeyellow headers
# ============================================================
# Each entry: source_map_id -> list of (dest_map_id, connection_type)
# Connection types:
#   "border_north"  — walk north off the map edge
#   "border_south"  — walk south off the map edge
#   "border_east"   — walk east off the map edge
#   "border_west"   — walk west off the map edge
#   "warp"          — use a warp tile (door/stairs) to reach dest
#
# Built from pret/pokeyellow data/maps/headers/*.asm

MAP_GRAPH: dict[int, list[tuple[int, str]]] = {}

def _add_edge(src: int, dst: int, conn_type: str):
    MAP_GRAPH.setdefault(src, []).append((dst, conn_type))

# --- Border connections (outdoor ↔ outdoor) ---
# Pallet Town (0)
_add_edge(0, 12, "border_north")   # → Route 1
_add_edge(0, 32, "border_south")   # → Route 21

# Route 1 (12)
_add_edge(12, 1, "border_north")   # → Viridian City
_add_edge(12, 0, "border_south")   # → Pallet Town

# Viridian City (1)
_add_edge(1, 13, "border_north")   # → Route 2
_add_edge(1, 12, "border_south")   # → Route 1
_add_edge(1, 33, "border_west")    # → Route 22

# Route 2 (13)
_add_edge(13, 2, "border_north")   # → Pewter City
_add_edge(13, 1, "border_south")   # → Viridian City

# Pewter City (2)
_add_edge(2, 13, "border_south")   # → Route 2
_add_edge(2, 14, "border_east")    # → Route 3

# Route 3 (14)
_add_edge(14, 15, "border_north")  # → Route 4
_add_edge(14, 2, "border_west")    # → Pewter City

# Route 4 (15)
_add_edge(15, 14, "border_south")  # → Route 3
_add_edge(15, 3, "border_east")    # → Cerulean City

# Cerulean City (3)
_add_edge(3, 35, "border_north")   # → Route 24
_add_edge(3, 16, "border_south")   # → Route 5
_add_edge(3, 15, "border_west")    # → Route 4
_add_edge(3, 20, "border_east")    # → Route 9

# Route 24 (35)
_add_edge(35, 3, "border_south")   # → Cerulean City
_add_edge(35, 36, "border_east")   # → Route 25

# Route 25 (36)
_add_edge(36, 35, "border_west")   # → Route 24

# Route 5 (16)
_add_edge(16, 3, "border_north")   # → Cerulean City
_add_edge(16, 10, "border_south")  # → Saffron City

# Route 6 (17)
_add_edge(17, 10, "border_north")  # → Saffron City
_add_edge(17, 5, "border_south")   # → Vermilion City

# Route 7 (18)
_add_edge(18, 6, "border_west")    # → Celadon City
_add_edge(18, 10, "border_east")   # → Saffron City

# Route 8 (19)
_add_edge(19, 10, "border_west")   # → Saffron City
_add_edge(19, 4, "border_east")    # → Lavender Town

# Route 9 (20)
_add_edge(20, 3, "border_west")    # → Cerulean City
_add_edge(20, 21, "border_east")   # → Route 10

# Route 10 (21)
_add_edge(21, 20, "border_west")   # → Route 9
_add_edge(21, 4, "border_south")   # → Lavender Town

# Saffron City (10)
_add_edge(10, 16, "border_north")  # → Route 5
_add_edge(10, 17, "border_south")  # → Route 6
_add_edge(10, 18, "border_west")   # → Route 7
_add_edge(10, 19, "border_east")   # → Route 8

# Lavender Town (4)
_add_edge(4, 21, "border_north")   # → Route 10
_add_edge(4, 23, "border_south")   # → Route 12
_add_edge(4, 19, "border_west")    # → Route 8

# Vermilion City (5)
_add_edge(5, 17, "border_north")   # → Route 6
_add_edge(5, 22, "border_east")    # → Route 11

# Route 11 (22)
_add_edge(22, 5, "border_west")    # → Vermilion City
_add_edge(22, 23, "border_east")   # → Route 12

# Route 12 (23)
_add_edge(23, 4, "border_north")   # → Lavender Town
_add_edge(23, 24, "border_south")  # → Route 13
_add_edge(23, 22, "border_west")   # → Route 11

# Route 13 (24)
_add_edge(24, 23, "border_north")  # → Route 12
_add_edge(24, 25, "border_west")   # → Route 14

# Route 14 (25)
_add_edge(25, 26, "border_west")   # → Route 15
_add_edge(25, 24, "border_east")   # → Route 13

# Route 15 (26)
_add_edge(26, 7, "border_west")    # → Fuchsia City
_add_edge(26, 25, "border_east")   # → Route 14

# Celadon City (6)
_add_edge(6, 27, "border_west")    # → Route 16
_add_edge(6, 18, "border_east")    # → Route 7

# Route 16 (27)
_add_edge(27, 28, "border_south")  # → Route 17
_add_edge(27, 6, "border_east")    # → Celadon City

# Route 17 (28)
_add_edge(28, 27, "border_north")  # → Route 16
_add_edge(28, 29, "border_south")  # → Route 18

# Route 18 (29)
_add_edge(29, 28, "border_north")  # → Route 17
_add_edge(29, 7, "border_east")    # → Fuchsia City

# Fuchsia City (7)
_add_edge(7, 30, "border_south")   # → Route 19
_add_edge(7, 29, "border_west")    # → Route 18
_add_edge(7, 26, "border_east")    # → Route 15

# Route 19 (30)
_add_edge(30, 7, "border_north")   # → Fuchsia City
_add_edge(30, 31, "border_west")   # → Route 20

# Route 20 (31)
_add_edge(31, 8, "border_west")    # → Cinnabar Island
_add_edge(31, 30, "border_east")   # → Route 19

# Cinnabar Island (8)
_add_edge(8, 32, "border_north")   # → Route 21
_add_edge(8, 31, "border_east")    # → Route 20

# Route 21 (32)
_add_edge(32, 0, "border_north")   # → Pallet Town
_add_edge(32, 8, "border_south")   # → Cinnabar Island

# Route 22 (33)
_add_edge(33, 34, "border_north")  # → Route 23
_add_edge(33, 1, "border_east")    # → Viridian City

# Route 23 (34)
_add_edge(34, 9, "border_north")   # → Indigo Plateau
_add_edge(34, 33, "border_south")  # → Route 22

# Indigo Plateau (9)
_add_edge(9, 34, "border_south")   # → Route 23

# --- Warp connections (indoor ↔ outdoor, transit) ---

# Parent map for each indoor map (warp exits to this outdoor map)
# Maps that use LAST_MAP (0xFF) are grouped by city prefix.
_INDOOR_PARENT: dict[int, int] = {
    # Pallet Town buildings
    37: 0,   # Player House 1F
    38: 37,  # Player House 2F → 1F (stairs)
    39: 0,   # Rival House
    40: 0,   # Oak's Lab
    # Viridian City buildings
    41: 1,   # Viridian Pokemon Center
    42: 1,   # Viridian Mart
    43: 1,   # Viridian School
    44: 1,   # Viridian Nickname House
    45: 1,   # Viridian Gym
    # Route 2 area
    46: 13,  # Diglett's Cave (Route 2 entrance)
    47: 13,  # Viridian Forest North Gate → Route 2
    48: 13,  # Route 2 Trade House
    49: 13,  # Route 2 Gate
    50: 13,  # Viridian Forest South Gate → Route 2
    51: 50,  # Viridian Forest (connects via gates)
    # Pewter City buildings
    52: 2,   # Pewter Museum 1F
    53: 52,  # Pewter Museum 2F
    54: 2,   # Pewter Gym
    55: 2,   # Pewter Nidoran House
    56: 2,   # Pewter Mart
    57: 2,   # Pewter Speech House
    58: 2,   # Pewter Pokemon Center
    # Mt. Moon
    59: 14,  # Mt. Moon 1F (entrance from Route 3 area)
    60: 59,  # Mt. Moon B1F
    61: 60,  # Mt. Moon B2F
    # Cerulean City buildings
    62: 3,   # Cerulean Trashed House
    63: 3,   # Cerulean Melanie's House
    64: 3,   # Cerulean Pokemon Center
    65: 3,   # Cerulean Gym
    66: 3,   # Bike Shop
    67: 3,   # Cerulean Mart
    68: 14,  # Mt. Moon Pokemon Center (on Route 3 area)
    69: 3,   # Cerulean Trashed House Copy
    # Route 5-8 gates and underground
    70: 16,  # Route 5 Gate
    71: 70,  # Underground Path (Route 5 entrance)
    72: 16,  # Day Care (Route 5)
    73: 17,  # Route 6 Gate
    74: 73,  # Underground Path (Route 6 entrance)
    76: 18,  # Route 7 Gate
    77: 76,  # Underground Path (Route 7 entrance)
    79: 19,  # Route 8 Gate
    80: 79,  # Underground Path (Route 8 entrance)
    # Rock Tunnel area
    81: 21,  # Rock Tunnel Pokemon Center (Route 10)
    82: 21,  # Rock Tunnel 1F
    232: 82, # Rock Tunnel B1F
    # Power Plant
    83: 21,  # Power Plant (Route 10 area)
    # Route 11-12 gates
    84: 22,  # Route 11 Gate 1F
    85: 22,  # Diglett's Cave (Route 11 entrance)
    86: 84,  # Route 11 Gate 2F
    87: 23,  # Route 12 Gate 1F
    # Bill's House (Route 25)
    88: 36,  # Bill's House
    # Vermilion City buildings
    89: 5,   # Vermilion Pokemon Center
    90: 5,   # Pokemon Fan Club
    91: 5,   # Vermilion Mart
    92: 5,   # Vermilion Gym
    93: 5,   # Vermilion Pidgey House
    94: 5,   # Vermilion Dock
    # SS Anne
    95: 94,  # SS Anne 1F
    96: 95,  # SS Anne 2F
    97: 96,  # SS Anne 3F
    98: 95,  # SS Anne B1F
    # Victory Road / Pokemon League
    108: 34, # Victory Road 1F (Route 23)
    194: 108, # Victory Road 2F
    198: 194, # Victory Road 3F
    # Underground Paths (transit tunnels)
    119: 71, # Underground Path N-S (from Route 5 underground entrance)
    121: 77, # Underground Path W-E (from Route 7 underground entrance)
    # Celadon City buildings
    122: 6,  # Celadon Mart 1F
    128: 6,  # Celadon Mansion 1F
    133: 6,  # Celadon Pokemon Center
    134: 6,  # Celadon Gym
    135: 6,  # Game Corner
    137: 6,  # Game Corner Prize Room
    138: 6,  # Celadon Diner
    139: 6,  # Celadon Chief House
    140: 6,  # Celadon Hotel
    # Rocket Hideout (under Game Corner)
    199: 135, # Rocket Hideout B1F
    200: 199, # Rocket Hideout B2F
    201: 200, # Rocket Hideout B3F
    202: 201, # Rocket Hideout B4F
    # Lavender Town buildings
    141: 4,  # Lavender Pokemon Center
    142: 4,  # Pokemon Tower 1F
    143: 142, # Pokemon Tower 2F
    144: 143, # Pokemon Tower 3F
    145: 144, # Pokemon Tower 4F
    146: 145, # Pokemon Tower 5F
    147: 146, # Pokemon Tower 6F
    148: 147, # Pokemon Tower 7F
    149: 4,  # Mr. Fuji's House
    150: 4,  # Lavender Mart
    151: 4,  # Lavender Cubone House
    # Fuchsia City buildings
    152: 7,  # Fuchsia Mart
    153: 7,  # Fuchsia Bill's Grandpa House
    154: 7,  # Fuchsia Pokemon Center
    155: 7,  # Warden's House
    156: 7,  # Safari Zone Gate
    157: 7,  # Fuchsia Gym
    158: 7,  # Fuchsia Meeting Room
    # Safari Zone
    220: 156, # Safari Zone Center
    217: 220, # Safari Zone East
    218: 220, # Safari Zone North
    219: 220, # Safari Zone West
    # Seafoam Islands
    192: 31, # Seafoam Islands 1F (Route 20)
    159: 192, # Seafoam Islands B1F
    160: 159, # Seafoam Islands B2F
    161: 160, # Seafoam Islands B3F
    162: 161, # Seafoam Islands B4F
    # Cinnabar Island buildings
    165: 8,  # Pokemon Mansion 1F
    166: 8,  # Cinnabar Gym
    167: 8,  # Cinnabar Lab
    171: 8,  # Cinnabar Pokemon Center
    172: 8,  # Cinnabar Mart
    # Pokemon Mansion floors
    214: 165, # Pokemon Mansion 2F
    215: 214, # Pokemon Mansion 3F
    216: 165, # Pokemon Mansion B1F
    # Indigo Plateau
    174: 9,  # Indigo Plateau Lobby
    245: 174, # Lorelei's Room
    246: 245, # Bruno's Room
    247: 246, # Agatha's Room
    113: 247, # Lance's Room
    120: 113, # Champion's Room
    118: 120, # Hall of Fame
    # Saffron City buildings
    175: 10, # Copycat's House 1F
    176: 175, # Copycat's House 2F
    177: 10, # Fighting Dojo
    178: 10, # Saffron Gym
    179: 10, # Saffron Pidgey House
    180: 10, # Saffron Mart
    181: 10, # Silph Co. 1F
    182: 10, # Saffron Pokemon Center
    183: 10, # Mr. Psychic's House
    # Silph Co. floors
    207: 181, # Silph Co. 2F
    208: 207, # Silph Co. 3F
    209: 208, # Silph Co. 4F
    210: 209, # Silph Co. 5F
    211: 210, # Silph Co. 6F
    212: 211, # Silph Co. 7F
    213: 212, # Silph Co. 8F
    233: 213, # Silph Co. 9F
    234: 233, # Silph Co. 10F
    235: 234, # Silph Co. 11F
    # Route gates with upper floors
    184: 26, # Route 15 Gate 1F
    185: 184, # Route 15 Gate 2F
    186: 27, # Route 16 Gate 1F
    187: 186, # Route 16 Gate 2F
    188: 27, # Route 16 Fly House
    189: 23, # Route 12 Super Rod House
    190: 29, # Route 18 Gate 1F
    191: 190, # Route 18 Gate 2F
    193: 33, # Route 22 Gate
    195: 87, # Route 12 Gate 2F
    163: 5,  # Vermilion Old Rod House
    164: 7,  # Fuchsia Good Rod House
    196: 5,  # Vermilion Trade House
    229: 4,  # Name Rater's House (Lavender)
    230: 3,  # Cerulean Badge House
    # Cerulean Cave
    228: 3,  # Cerulean Cave 1F
    226: 228, # Cerulean Cave 2F
    227: 228, # Cerulean Cave B1F
    # Yellow-specific
    248: 31, # Summer Beach House (Route 20)
}

# Build warp edges from parent map
for child_id, parent_id in _INDOOR_PARENT.items():
    _add_edge(child_id, parent_id, "warp")
    _add_edge(parent_id, child_id, "warp")

# --- Transit connections (caves/tunnels connecting two outdoor areas) ---
# These are critical for pathfinding through areas that require going indoor

# Viridian Forest: South Gate (50) ↔ Forest (51) ↔ North Gate (47)
# (Already connected via _INDOOR_PARENT, but ensure the full chain exists)

# Diglett's Cave: Route 2 entrance (46) ↔ Diglett's Cave (197) ↔ Route 11 entrance (85)
_add_edge(46, 197, "warp")
_add_edge(197, 46, "warp")
_add_edge(85, 197, "warp")
_add_edge(197, 85, "warp")

# Underground Path N-S: Route 5 underground (71) ↔ path (119) ↔ Route 6 underground (74)
_add_edge(74, 119, "warp")
_add_edge(119, 74, "warp")

# Underground Path W-E: Route 7 underground (77) ↔ path (121) ↔ Route 8 underground (80)
_add_edge(80, 121, "warp")
_add_edge(121, 80, "warp")

# Mt. Moon: exit from B2F leads to Route 4
_add_edge(61, 15, "warp")
_add_edge(15, 61, "warp")

# Rock Tunnel: B1F (232) connects to Route 10 area
_add_edge(232, 21, "warp")
_add_edge(21, 232, "warp")

# Seafoam Islands: B4F connects to Cinnabar side (Route 20 west)
# (Already connected through the chain)

# Route 5 Gate connects Route 5 to Saffron
_add_edge(70, 10, "warp")
_add_edge(10, 70, "warp")

# Route 6 Gate connects Route 6 to Saffron
_add_edge(73, 10, "warp")
_add_edge(10, 73, "warp")

# Route 7 Gate connects Route 7 to Saffron/Celadon
_add_edge(76, 10, "warp")
_add_edge(10, 76, "warp")

# Route 8 Gate connects Route 8 to Saffron
_add_edge(79, 10, "warp")
_add_edge(10, 79, "warp")

del _add_edge  # Clean up module namespace


# ============================================================
# Helper functions
# ============================================================

def get_species_name(internal_id):
    entry = SPECIES.get(internal_id)
    return entry["name"] if entry else f"???({internal_id:#04x})"

def get_move_name(move_id):
    if move_id == 0:
        return "---"
    entry = MOVES.get(move_id)
    return entry["name"] if entry else f"move_{move_id}"

def get_type_multiplier(atk_type, def_type):
    return TYPE_EFFECTIVENESS.get((atk_type, def_type), 1.0)

def calc_type_effectiveness(move_type, def_type1, def_type2):
    m1 = get_type_multiplier(move_type, def_type1)
    m2 = get_type_multiplier(move_type, def_type2) if def_type1 != def_type2 else 1.0
    return m1 * m2

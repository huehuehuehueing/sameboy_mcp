"""Pokemon Yellow (US) memory addresses.

All addresses from the pret/pokeyellow disassembly project.
https://github.com/pret/pokeyellow

Note: Yellow shifted some WRAM addresses by -1 compared to Red/Blue
after $CF1A due to wGBC moving to HRAM $FFFE.
"""

# ============================================================
# Player Position & Map
# ============================================================

WRAM_CUR_MAP = 0xD35D            # Current map ID (1 byte)
WRAM_Y_COORD = 0xD360            # Player Y tile coordinate
WRAM_X_COORD = 0xD361            # Player X tile coordinate
WRAM_Y_BLOCK_COORD = 0xD362      # Player Y block coordinate
WRAM_X_BLOCK_COORD = 0xD363      # Player X block coordinate
WRAM_LAST_MAP = 0xD364            # Last map visited
WRAM_CUR_MAP_TILESET = 0xD366    # Current map tileset
WRAM_CUR_MAP_HEIGHT = 0xD367     # Map height in blocks
WRAM_CUR_MAP_WIDTH = 0xD368      # Map width in blocks
WRAM_MAP_CONNECTIONS = 0xD36F    # Map connection flags (NSEW)
WRAM_PLAYER_DIRECTION = 0xD529   # Player facing direction
WRAM_PLAYER_MOVE_DIR = 0xD527    # Direction player is moving
WRAM_CUR_MAP_SCRIPT = 0xDA38     # Current map script index

# Sprite/player visual state
WRAM_SPRITE_PLAYER_Y = 0xC104    # Y pixel position on screen
WRAM_SPRITE_PLAYER_X = 0xC106    # X pixel position on screen
WRAM_SPRITE_FACING = 0xC109      # Facing direction (sprite level)
WRAM_WALK_COUNTER = 0xCFC4       # Walk animation counter
WRAM_TILE_IN_FRONT = 0xCFC5      # Tile ID in front of player
WRAM_WALK_BIKE_SURF = 0xD119     # Walking/biking/surfing state

# ============================================================
# Player Identity
# ============================================================

WRAM_PLAYER_NAME = 0xD157        # Player name (11 bytes, terminated $50)
WRAM_RIVAL_NAME = 0xD349         # Rival name (11 bytes, terminated $50)
WRAM_PLAYER_ID = 0xD358          # Trainer ID (2 bytes)

# ============================================================
# Party Pokemon
# ============================================================

WRAM_PARTY_COUNT = 0xD162        # Number of Pokemon in party (0-6)
WRAM_PARTY_SPECIES = 0xD163      # Species list (6+terminator = 7 bytes)

# Party mon structure: 44 bytes each
WRAM_PARTY_MON1 = 0xD16A        # Start of party mon 1
WRAM_PARTY_MON2 = 0xD196
WRAM_PARTY_MON3 = 0xD1C2
WRAM_PARTY_MON4 = 0xD1EE
WRAM_PARTY_MON5 = 0xD21A
WRAM_PARTY_MON6 = 0xD246

PARTY_MON_ADDRESSES = [
    WRAM_PARTY_MON1, WRAM_PARTY_MON2, WRAM_PARTY_MON3,
    WRAM_PARTY_MON4, WRAM_PARTY_MON5, WRAM_PARTY_MON6,
]

# Offsets within a party mon structure (44 bytes)
MON_SPECIES = 0        # 1 byte
MON_HP = 1             # 2 bytes (big-endian)
MON_BOX_LEVEL = 3      # 1 byte
MON_STATUS = 4         # 1 byte bitfield
MON_TYPE1 = 5          # 1 byte
MON_TYPE2 = 6          # 1 byte
MON_CATCH_RATE = 7     # 1 byte
MON_MOVES = 8          # 4 bytes (move 1-4)
MON_OT_ID = 12         # 2 bytes
MON_EXP = 14           # 3 bytes
MON_HP_EXP = 17        # 2 bytes
MON_ATK_EXP = 19       # 2 bytes
MON_DEF_EXP = 21       # 2 bytes
MON_SPD_EXP = 23       # 2 bytes
MON_SPC_EXP = 25       # 2 bytes
MON_DVS = 27           # 2 bytes (IVs)
MON_PP = 29            # 4 bytes (PP for moves 1-4)
MON_LEVEL = 33         # 1 byte (actual level)
MON_MAX_HP = 34        # 2 bytes (big-endian)
MON_ATTACK = 36        # 2 bytes
MON_DEFENSE = 38       # 2 bytes
MON_SPEED = 40         # 2 bytes
MON_SPECIAL = 42       # 2 bytes

PARTY_MON_SIZE = 44

# Party nicknames and OT names
WRAM_PARTY_MON_OT = 0xD272      # OT names (11 bytes x 6)
WRAM_PARTY_MON_NICKS = 0xD2B4   # Nicknames (11 bytes x 6)

# ============================================================
# Badges, Money, Items
# ============================================================

WRAM_BADGES = 0xD355             # Badge bitfield (1 byte)
WRAM_MONEY = 0xD346              # Money in BCD (3 bytes, big-endian)
WRAM_COINS = 0xD5A3              # Game Corner coins in BCD (2 bytes)
WRAM_NUM_BAG_ITEMS = 0xD31C      # Number of items in bag
WRAM_BAG_ITEMS = 0xD31D          # Item pairs (ID+qty), 20 slots + terminator
WRAM_NUM_BOX_ITEMS = 0xD539      # Number of items in PC
WRAM_BOX_ITEMS = 0xD53A          # PC item storage

# Badge bits
BADGE_BOULDER = 0   # Brock
BADGE_CASCADE = 1   # Misty
BADGE_THUNDER = 2   # Lt. Surge
BADGE_RAINBOW = 3   # Erika
BADGE_SOUL = 4      # Koga
BADGE_MARSH = 5     # Sabrina
BADGE_VOLCANO = 6   # Blaine
BADGE_EARTH = 7     # Giovanni

# ============================================================
# Pokedex
# ============================================================

WRAM_POKEDEX_OWNED = 0xD2F6      # Bitfield of owned Pokemon (19 bytes)
WRAM_POKEDEX_SEEN = 0xD309       # Bitfield of seen Pokemon (19 bytes)

# ============================================================
# Battle State
# ============================================================

WRAM_IS_IN_BATTLE = 0xD056       # 0=no, 1=wild, 2=trainer, 0xFF=lost
WRAM_CUR_OPPONENT = 0xD058       # Trainer class or wild Pokemon ID
WRAM_BATTLE_TYPE = 0xD059        # Battle type
WRAM_BATTLE_RESULT = 0xCF0B      # Result of last battle
WRAM_DAMAGE = 0xD0D6             # Damage for current attack (2 bytes)
WRAM_CRITICAL_HIT = 0xD05D       # Critical hit / OHKO flags
WRAM_MOVE_MISSED = 0xD05E        # Whether current move missed
WRAM_DAMAGE_MULTIPLIERS = 0xD05A # STAB and type effectiveness

# Player's active battle Pokemon (wBattleMon at $D013)
WRAM_BATTLE_MON_NICK = 0xD008    # 11 bytes
WRAM_BATTLE_MON_SPECIES = 0xD013
WRAM_BATTLE_MON_HP = 0xD014      # 2 bytes
WRAM_BATTLE_MON_LEVEL = 0xD021   # 1 byte (actual level in battle)
WRAM_BATTLE_MON_STATUS = 0xD017
WRAM_BATTLE_MON_TYPE1 = 0xD018
WRAM_BATTLE_MON_TYPE2 = 0xD019
WRAM_BATTLE_MON_MOVES = 0xD01B   # 4 bytes
WRAM_BATTLE_MON_MAX_HP = 0xD022  # 2 bytes
WRAM_BATTLE_MON_ATTACK = 0xD024  # 2 bytes
WRAM_BATTLE_MON_DEFENSE = 0xD026 # 2 bytes
WRAM_BATTLE_MON_SPEED = 0xD028   # 2 bytes
WRAM_BATTLE_MON_SPECIAL = 0xD02A # 2 bytes
WRAM_BATTLE_MON_PP = 0xD02C      # 4 bytes

# Enemy active battle Pokemon (wEnemyMon at $CFE4)
WRAM_ENEMY_MON_NICK = 0xCFD9     # 11 bytes
WRAM_ENEMY_MON_SPECIES = 0xCFE4
WRAM_ENEMY_MON_HP = 0xCFE5       # 2 bytes
WRAM_ENEMY_MON_LEVEL = 0xCFF2
WRAM_ENEMY_MON_STATUS = 0xCFE8
WRAM_ENEMY_MON_TYPE1 = 0xCFE9
WRAM_ENEMY_MON_TYPE2 = 0xCFEA
WRAM_ENEMY_MON_MOVES = 0xCFEC    # 4 bytes
WRAM_ENEMY_MON_MAX_HP = 0xCFF3   # 2 bytes
WRAM_ENEMY_MON_ATTACK = 0xCFF5   # 2 bytes
WRAM_ENEMY_MON_DEFENSE = 0xCFF7  # 2 bytes
WRAM_ENEMY_MON_SPEED = 0xCFF9    # 2 bytes
WRAM_ENEMY_MON_SPECIAL = 0xCFFB  # 2 bytes
WRAM_ENEMY_MON_CATCH_RATE = 0xD006  # Actual catch rate

# Battle stat modifiers (stored as 1-13, 7=neutral)
WRAM_PLAYER_ATK_MOD = 0xCD1E
WRAM_PLAYER_DEF_MOD = 0xCD1F
WRAM_PLAYER_SPD_MOD = 0xCD20
WRAM_PLAYER_SPC_MOD = 0xCD21
WRAM_ENEMY_ATK_MOD = 0xCD2E
WRAM_ENEMY_DEF_MOD = 0xCD2F
WRAM_ENEMY_SPD_MOD = 0xCD30
WRAM_ENEMY_SPC_MOD = 0xCD31

# Battle status flags
WRAM_PLAYER_BATTLE_STATUS1 = 0xD061
WRAM_PLAYER_BATTLE_STATUS2 = 0xD062
WRAM_PLAYER_BATTLE_STATUS3 = 0xD063
WRAM_ENEMY_BATTLE_STATUS1 = 0xD066
WRAM_ENEMY_BATTLE_STATUS2 = 0xD067
WRAM_ENEMY_BATTLE_STATUS3 = 0xD068

# Move selection
WRAM_PLAYER_SELECTED_MOVE = 0xCCDC
WRAM_ENEMY_SELECTED_MOVE = 0xCCDD
HRAM_WHOSE_TURN = 0xFFF3          # 0=player, 1=enemy

# Trainer data
WRAM_TRAINER_CLASS = 0xD030
WRAM_CUR_ENEMY_LVL = 0xD126
WRAM_ENEMY_PARTY_COUNT = 0xD89B

# ============================================================
# Menu & UI State
# ============================================================

WRAM_TOP_MENU_ITEM_Y = 0xCC24
WRAM_TOP_MENU_ITEM_X = 0xCC25
WRAM_CURRENT_MENU_ITEM = 0xCC26  # Currently selected menu item index
WRAM_MAX_MENU_ITEM = 0xCC28      # Maximum menu item index
WRAM_MENU_WATCHED_KEYS = 0xCC29  # Keys the menu responds to
WRAM_LAST_MENU_ITEM = 0xCC2A
WRAM_LIST_SCROLL_OFFSET = 0xCC36
WRAM_MENU_WRAPPING = 0xCC4A      # Whether menu cursor wraps

# ============================================================
# Text & Dialog
# ============================================================

WRAM_TEXT_BOX_ID = 0xD124         # Current text box identifier
WRAM_IGNORE_INPUT_COUNTER = 0xD139  # Frames to ignore input (text delay)
WRAM_LETTER_DELAY_FLAGS = 0xD357    # Text printing speed flags
WRAM_AUTO_TEXT_BOX = 0xCF0C         # Auto text box drawing control

# ============================================================
# Joypad Input
# ============================================================

HRAM_JOY_LAST = 0xFFB1            # Previous frame's joypad state
HRAM_JOY_RELEASED = 0xFFB2        # Buttons released this frame
HRAM_JOY_PRESSED = 0xFFB3         # Buttons newly pressed (edges)
HRAM_JOY_HELD = 0xFFB4            # Buttons currently held
HRAM_JOY_5 = 0xFFB5               # Auto-repeat for menus
HRAM_DISABLE_JOY_POLLING = 0xFFF8 # Nonzero stops joypad reads
WRAM_JOY_IGNORE = 0xCD6B          # Bitmask of buttons to ignore
WRAM_SIM_JOYPAD_INDEX = 0xCD38    # Index for joypad simulation

# Button bit layout (in processed joypad bytes)
BTN_A = 0x01
BTN_B = 0x02
BTN_SELECT = 0x04
BTN_START = 0x08
BTN_RIGHT = 0x10
BTN_LEFT = 0x20
BTN_UP = 0x40
BTN_DOWN = 0x80

# ============================================================
# Miscellaneous
# ============================================================

WRAM_PIKACHU_HAPPINESS = 0xD46F  # Pikachu friendship (Yellow only)
WRAM_GRASS_RATE = 0xD886         # Wild encounter rate (grass)
WRAM_WATER_RATE = 0xD8A3         # Wild encounter rate (water)
WRAM_NUM_SPRITES = 0xD4E0        # Sprites on current map
WRAM_CURRENT_BOX = 0xD59F        # Currently selected PC box
WRAM_PLAY_TIME_HOURS = 0xDA40
WRAM_PLAY_TIME_MINUTES = 0xDA42
WRAM_PLAY_TIME_SECONDS = 0xDA43
WRAM_PLAY_TIME_FRAMES = 0xDA44
WRAM_OPTIONS = 0xD354            # Game options (text speed etc.)
WRAM_NO_BATTLE_STEPS = 0xD13B    # Steps without random battles
WRAM_TILE_MAP = 0xC3A0           # Current tile map (20x18 = 360 bytes)

HRAM_RANDOM_ADD = 0xFFD3         # Random number (additive)
HRAM_RANDOM_SUB = 0xFFD4         # Random number (subtractive)
HRAM_FRAME_COUNTER = 0xFFD5      # Frame counter (increments each vblank)
HRAM_GBC = 0xFFFE                # GBC flag (Yellow-specific HRAM location)

# ROM bank tracking
HRAM_LOADED_ROM_BANK = 0xFFB8
HRAM_SAVED_ROM_BANK = 0xFFB9

# ============================================================
# Status condition bits (MON_STATUS byte)
# ============================================================

STATUS_NONE = 0x00
STATUS_SLEEP_MASK = 0x07   # Bits 0-2: sleep turns remaining
STATUS_POISON = 0x08       # Bit 3
STATUS_BURN = 0x10         # Bit 4
STATUS_FREEZE = 0x20       # Bit 5
STATUS_PARALYSIS = 0x40    # Bit 6

# ============================================================
# Direction values
# ============================================================

DIR_DOWN = 0x00
DIR_UP = 0x04
DIR_LEFT = 0x08
DIR_RIGHT = 0x0C

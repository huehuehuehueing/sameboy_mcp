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
WRAM_ENEMY_MON_PP = 0xCFFD        # 4 bytes (PP for moves 1-4)
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

# Battle status 1 bits (applies to both player and enemy)
BSTATUS1_BIDE = 0x01              # Using Bide
BSTATUS1_THRASH_PETAL = 0x02      # Thrashing / Petal Dance
BSTATUS1_CHARGING = 0x04          # Charging (Solar Beam, Skull Bash, etc.)
BSTATUS1_MULTI_HIT = 0x08         # Multi-hit move in progress
BSTATUS1_FLINCH = 0x10            # Flinched
BSTATUS1_RECHARGING = 0x20        # Recharging (Hyper Beam)
BSTATUS1_RAGE = 0x40              # Using Rage
BSTATUS1_SUBSTITUTE = 0x80        # Has Substitute

# Battle status 2 bits
BSTATUS2_X_ACCURACY = 0x01        # X Accuracy active
BSTATUS2_PROTECTED = 0x02         # Protected by Mist/etc.
BSTATUS2_FOCUS_ENERGY = 0x04      # Focus Energy active
BSTATUS2_CONFUSED = 0x80          # Confused

# Battle status 3 bits
BSTATUS3_REFLECT = 0x01           # Reflect active
BSTATUS3_LIGHT_SCREEN = 0x02      # Light Screen active
BSTATUS3_TRANSFORMED = 0x08       # Transformed (Transform)

# Move selection
WRAM_PLAYER_SELECTED_MOVE = 0xCCDC
WRAM_ENEMY_SELECTED_MOVE = 0xCCDD
HRAM_WHOSE_TURN = 0xFFF3          # 0=player, 1=enemy

# Trainer data
WRAM_TRAINER_CLASS = 0xD030
WRAM_CUR_ENEMY_LVL = 0xD126
WRAM_ENEMY_PARTY_COUNT = 0xD89B

# ============================================================
# Battle Memory Reference (for LLM context)
# ============================================================

BATTLE_MEMORY_REFERENCE = {
    "player_active_mon": {
        "species": ("$D013", "WRAM_BATTLE_MON_SPECIES"),
        "hp": ("$D014", "WRAM_BATTLE_MON_HP (2 bytes BE)"),
        "status": ("$D017", "WRAM_BATTLE_MON_STATUS"),
        "type1": ("$D018", "WRAM_BATTLE_MON_TYPE1"),
        "type2": ("$D019", "WRAM_BATTLE_MON_TYPE2"),
        "moves": ("$D01B", "WRAM_BATTLE_MON_MOVES (4 bytes)"),
        "level": ("$D021", "WRAM_BATTLE_MON_LEVEL"),
        "max_hp": ("$D022", "WRAM_BATTLE_MON_MAX_HP (2 bytes BE)"),
        "attack": ("$D024", "WRAM_BATTLE_MON_ATTACK (2 bytes BE)"),
        "defense": ("$D026", "WRAM_BATTLE_MON_DEFENSE (2 bytes BE)"),
        "speed": ("$D028", "WRAM_BATTLE_MON_SPEED (2 bytes BE)"),
        "special": ("$D02A", "WRAM_BATTLE_MON_SPECIAL (2 bytes BE)"),
        "pp": ("$D02C", "WRAM_BATTLE_MON_PP (4 bytes)"),
    },
    "enemy_active_mon": {
        "species": ("$CFE4", "WRAM_ENEMY_MON_SPECIES"),
        "hp": ("$CFE5", "WRAM_ENEMY_MON_HP (2 bytes BE)"),
        "status": ("$CFE8", "WRAM_ENEMY_MON_STATUS"),
        "type1": ("$CFE9", "WRAM_ENEMY_MON_TYPE1"),
        "type2": ("$CFEA", "WRAM_ENEMY_MON_TYPE2"),
        "moves": ("$CFEC", "WRAM_ENEMY_MON_MOVES (4 bytes)"),
        "level": ("$CFF2", "WRAM_ENEMY_MON_LEVEL"),
        "max_hp": ("$CFF3", "WRAM_ENEMY_MON_MAX_HP (2 bytes BE)"),
        "attack": ("$CFF5", "WRAM_ENEMY_MON_ATTACK (2 bytes BE)"),
        "defense": ("$CFF7", "WRAM_ENEMY_MON_DEFENSE (2 bytes BE)"),
        "speed": ("$CFF9", "WRAM_ENEMY_MON_SPEED (2 bytes BE)"),
        "special": ("$CFFB", "WRAM_ENEMY_MON_SPECIAL (2 bytes BE)"),
        "pp": ("$CFFD", "WRAM_ENEMY_MON_PP (4 bytes)"),
        "catch_rate": ("$D006", "WRAM_ENEMY_MON_CATCH_RATE"),
    },
    "stat_modifiers": {
        "player_atk": ("$CD1E", "1-13, 7=neutral"),
        "player_def": ("$CD1F", "1-13, 7=neutral"),
        "player_spd": ("$CD20", "1-13, 7=neutral"),
        "player_spc": ("$CD21", "1-13, 7=neutral"),
        "enemy_atk": ("$CD2E", "1-13, 7=neutral"),
        "enemy_def": ("$CD2F", "1-13, 7=neutral"),
        "enemy_spd": ("$CD30", "1-13, 7=neutral"),
        "enemy_spc": ("$CD31", "1-13, 7=neutral"),
    },
    "battle_flags": {
        "is_in_battle": ("$D056", "0=no, 1=wild, 2=trainer, 0xFF=lost"),
        "trainer_class": ("$D030", "WRAM_TRAINER_CLASS"),
        "enemy_party_count": ("$D89B", "WRAM_ENEMY_PARTY_COUNT"),
        "damage": ("$D0D6", "WRAM_DAMAGE (2 bytes)"),
        "critical_hit": ("$D05D", "WRAM_CRITICAL_HIT flags"),
        "move_missed": ("$D05E", "WRAM_MOVE_MISSED"),
    },
}

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

# ============================================================
# Event Flags
# ============================================================

WRAM_EVENT_FLAGS = 0xD747  # Base address for event flags bitfield

# Early game event flag bit numbers
# Flag N is at byte WRAM_EVENT_FLAGS + (N // 8), bit (N % 8)
EVENT_FLAGS = {
    "FOLLOWED_OAK_INTO_LAB": 0x00,
    "PALLET_AFTER_GETTING_POKEBALLS": 0x06,
    "GOT_TOWN_MAP": 0x18,
    "OAK_ASKED_TO_CHOOSE_MON": 0x21,
    "GOT_STARTER": 0x22,
    "BATTLED_RIVAL_IN_OAKS_LAB": 0x23,
    "GOT_POKEBALLS_FROM_OAK": 0x24,
    "GOT_POKEDEX": 0x25,
    "OAK_APPEARED_IN_PALLET": 0x27,
    "OAK_GOT_PARCEL": 0x33,
    "GOT_OAKS_PARCEL": 0x34,
}

# Game progress phases (checked in reverse order - most progressed first)
GAME_PROGRESS_ORDER = [
    ("GOT_POKEDEX", "Explore freely with Pokedex"),
    ("GOT_OAKS_PARCEL", "Deliver parcel to Oak"),
    ("BATTLED_RIVAL_IN_OAKS_LAB", "Leave Oak's Lab"),
    ("GOT_STARTER", "Battle rival in Oak's Lab"),
    ("OAK_ASKED_TO_CHOOSE_MON", "Choose starter Pokemon"),
    ("FOLLOWED_OAK_INTO_LAB", "Follow Oak into lab"),
    ("OAK_APPEARED_IN_PALLET", "Oak is escorting to lab"),
]

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


# ============================================================
# Additional state detection addresses
# ============================================================

WRAM_GAME_PROGRESS_FLAGS = 0xD356   # Event flags (1 byte)
WRAM_OAK_SPEECH_STATUS = 0xD72D     # Oak intro progress flags
WRAM_OBTAINED_STARTER = 0xD74B      # Bit 7 = obtained starter Pokemon
WRAM_MAIN_MENU_STATE = 0xD731       # Main menu selection state
WRAM_NAMING_SCREEN_TYPE = 0xCF91    # Name entry screen type (0=unused)
WRAM_CURSOR_TILE_POS = 0xC4B0       # Cursor position in name entry
WRAM_NUM_LETTERS_ENTERED = 0xCF4A   # Number of chars entered in name
WRAM_TEXTBOX_FLAG = 0xCFC4          # Whether text box is active
WRAM_JOY_IGNORE = 0xCD6B            # Bitmask of buttons to ignore
WRAM_PREDEF_ID = 0xD0B6             # Current predef function running
WRAM_WARP_DESTINATION = 0xD42F      # Destination map for warp
WRAM_DESTINATION_MAP = 0xFF8B       # Destination map ID (HRAM)

# Intro/title screen specific
WRAM_INTRO_SCENE = 0xD08A           # Intro scene index
WRAM_GAME_STATE = 0xD0C0            # Broad game state (varies by context)
WRAM_AUDIO_FLAG = 0xCFCA            # Audio state (can indicate title)
WRAM_SPRITE_FLAGS = 0xC100          # Sprite data start (can detect gameplay)

# Map and collision data
WRAM_MAP_DATA = 0xC6E8              # Current map block data (overworld)
WRAM_MAP_BLOCK_PTR = 0xD35F         # Pointer to current map blocks
WRAM_COLLISION_DATA = 0xC7C8        # Collision data for current map
WRAM_SPRITE_DATA = 0xC100           # Sprite movement data (16 bytes each)
WRAM_NUM_SPRITES_ACTUAL = 0xD4E0    # Actual sprite count on map
WRAM_WARP_DATA = 0xD3AA             # Warp destination data

# Warp/connection data
WRAM_NUM_WARPS = 0xD3AE             # Number of warp points on current map
WRAM_WARP_ENTRIES = 0xD3AF          # Warp entry data (4 bytes each: y, x, warp_id, dest_map)
WRAM_DEST_MAP = 0xD42F              # Destination map after warp
WRAM_WARP_DEST_ENTRY = 0xD430       # Which warp entry to use at destination

# Sprite structure (16 bytes each, starting at 0xC100)
# Sprite 0 is the player
SPRITE_PICTURE_ID = 0x00            # Sprite image ID
SPRITE_MOVE_STATUS = 0x01           # Movement status
SPRITE_IMAGE_INDEX = 0x02           # Current image/frame
SPRITE_Y_STEP = 0x03                # Y step counter
SPRITE_Y_POS = 0x04                 # Y position (pixels, offset from top-left)
SPRITE_X_STEP = 0x05                # X step counter
SPRITE_X_POS = 0x06                 # X position (pixels, offset from top-left)
SPRITE_INTRA_ANIM = 0x07            # Intra-animation counter
SPRITE_ANIM_DELAY = 0x08            # Animation frame delay
SPRITE_FACING = 0x09                # Facing direction
SPRITE_TILE_Y = 0x0A                # Y tile position (unused?)
SPRITE_TILE_X = 0x0B                # X tile position (unused?)
SPRITE_MAP_Y = 0x0C                 # Map Y coordinate
SPRITE_MAP_X = 0x0D                 # Map X coordinate
SPRITE_WALK_ANIM = 0x0E             # Walk animation counter
SPRITE_FLAGS = 0x0F                 # Sprite flags

# Dialog/Text state verification
WRAM_TEXT_DELAY_FRAMES = 0xCF42     # Frames until next text char
WRAM_JOYPAD_SIM_ACTIVE = 0xCD3D     # DEPRECATED - use WRAM_SIM_JOYPAD_STATES_INDEX
WRAM_TEXTBOX_OPEN = 0xC6F0          # Nonzero when text box is visible on screen
WRAM_DIALOG_STATE = 0xCF93          # Dialog state machine
WRAM_SCRIPT_RUNNING = 0xD730        # Bit 0: script is running

# ============================================================
# Critical Game State Detection (from pret/pokeyellow disassembly)
# ============================================================

# Joypad simulation - THIS is the key variable for detecting scripted movement
# When non-zero, the game is simulating button presses (cutscenes, intros, NPC scripts)
# When 0, normal player input is accepted
WRAM_SIM_JOYPAD_STATES_INDEX = 0xCC3F  # wSimulatedJoypadStatesIndex

# Yellow-specific intro tracking
# Tracks which scene of the intro is playing (0-17)
# Bit 7 set = intro has finished
WRAM_YELLOW_INTRO_SCENE = 0xC634       # wYellowIntroCurrentScene
WRAM_YELLOW_INTRO_TIMER = 0xC635       # wYellowIntroSceneTimer

# Text box detection
WRAM_TEXT_BOX_ID = 0xCF94              # wTextBoxID - non-zero when text box active

# Walk state (more reliable than WRAM_WALK_COUNTER)
WRAM_PLAYER_MOVING_DIRECTION = 0xD528  # wPlayerMovingDirection - direction player is trying to move

# Movement script states
WRAM_SIMULATED_JOYPAD_END = 0xCD40     # wSimulatedJoypadStatesEnd - buffer end for simulated inputs
WRAM_OVERRIDE_SIM_JOYPAD_MASK = 0xCC43 # wOverrideSimulatedJoypadStatesMask


# ============================================================
# Pokemon Yellow Character Encoding (Gen 1)
# ============================================================

# The Game Boy uses a custom character encoding, not ASCII.
# This table decodes tile IDs to characters for text reading.

CHAR_ENCODING = {
    0x00: " ",
    # Uppercase letters
    0x80: "A", 0x81: "B", 0x82: "C", 0x83: "D", 0x84: "E",
    0x85: "F", 0x86: "G", 0x87: "H", 0x88: "I", 0x89: "J",
    0x8A: "K", 0x8B: "L", 0x8C: "M", 0x8D: "N", 0x8E: "O",
    0x8F: "P", 0x90: "Q", 0x91: "R", 0x92: "S", 0x93: "T",
    0x94: "U", 0x95: "V", 0x96: "W", 0x97: "X", 0x98: "Y",
    0x99: "Z",
    # Special Pokemon symbols
    0x9A: "(", 0x9B: ")", 0x9C: ":", 0x9D: ";", 0x9E: "[", 0x9F: "]",
    # Lowercase letters
    0xA0: "a", 0xA1: "b", 0xA2: "c", 0xA3: "d", 0xA4: "e",
    0xA5: "f", 0xA6: "g", 0xA7: "h", 0xA8: "i", 0xA9: "j",
    0xAA: "k", 0xAB: "l", 0xAC: "m", 0xAD: "n", 0xAE: "o",
    0xAF: "p", 0xB0: "q", 0xB1: "r", 0xB2: "s", 0xB3: "t",
    0xB4: "u", 0xB5: "v", 0xB6: "w", 0xB7: "x", 0xB8: "y",
    0xB9: "z",
    # Accented characters and contractions (from pret/pokeyellow charmap.asm)
    0xBA: "é",
    0xBB: "'d",  # Contraction: "I'd", "you'd"
    0xBC: "'l",  # Contraction: "I'll", "you'll"
    0xBD: "'s",  # Contraction: "it's", "that's"
    0xBE: "'t",  # Contraction: "don't", "can't"
    0xBF: "'v",  # Contraction: "I've", "you've"
    # Numbers
    0xF6: "0", 0xF7: "1", 0xF8: "2", 0xF9: "3", 0xFA: "4",
    0xFB: "5", 0xFC: "6", 0xFD: "7", 0xFE: "8", 0xFF: "9",
    # Punctuation and symbols (corrected per pret/pokeyellow charmap.asm)
    0xE0: "'",  # Apostrophe
    0xE1: "PK", # PK symbol
    0xE2: "MN", # MN symbol (for "POKéMON")
    0xE3: "-",  # Dash/hyphen
    0xE4: "'r", # Contraction: "Mr."
    0xE5: "'m", # Contraction: "I'm"
    0xE6: "?",  # Question mark
    0xE7: "!",  # Exclamation mark
    0xE8: ".",  # Period
    0xEC: "▷",  # Right-pointing triangle
    0xED: "▶",  # Menu cursor arrow
    0xEE: "▼",  # Down arrow (more text indicator)
    0xEF: "♂",  # Male symbol
    0xF0: "¥",  # Yen/money symbol
    0xF1: "×",  # Multiplication sign
    0xF3: "/",  # Forward slash
    0xF4: ",",  # Comma
    0xF5: "♀",  # Female symbol
    0x50: "@",  # String terminator (end of text)
    0x4F: "\n", # Line break
    0x51: "*",  # End of page / paragraph marker
    0x55: "<CONT>",  # Continuation marker
    0x57: "<DONE>",  # Text done marker
    0x58: "<PROMPT>", # Waiting for input
    0x7F: " ",  # Space variant
    # More space/blank variants
    0x10: " ", 0x11: " ", 0x12: " ", 0x13: " ",
}

# Reverse encoding for writing text (single chars only)
CHAR_TO_TILE = {v: k for k, v in CHAR_ENCODING.items() if len(v) == 1}
# Ensure common characters map to canonical tile IDs
CHAR_TO_TILE.update({
    "A": 0x80, "B": 0x81, "C": 0x82, "D": 0x83, "E": 0x84,
    "F": 0x85, "G": 0x86, "H": 0x87, "I": 0x88, "J": 0x89,
    "K": 0x8A, "L": 0x8B, "M": 0x8C, "N": 0x8D, "O": 0x8E,
    "P": 0x8F, "Q": 0x90, "R": 0x91, "S": 0x92, "T": 0x93,
    "U": 0x94, "V": 0x95, "W": 0x96, "X": 0x97, "Y": 0x98,
    "Z": 0x99, " ": 0x7F, "@": 0x50,
    "?": 0xE6, "!": 0xE7, ".": 0xE8, ",": 0xF4, "/": 0xF3,
})


def decode_text(tile_bytes: list[int], max_len: int = 100) -> str:
    """Decode a sequence of tile bytes to text using Pokemon encoding."""
    result = []
    for i, b in enumerate(tile_bytes):
        if i >= max_len:
            break
        if b == 0x50:  # String terminator
            break
        char = CHAR_ENCODING.get(b, "")
        if char and not char.startswith("<"):
            result.append(char)
        elif char.startswith("<"):
            break  # Control character, stop
    return "".join(result)


def encode_text(text: str, terminator: bool = True) -> list[int]:
    """Encode a string to Pokemon tile bytes."""
    result = []
    for c in text.upper():
        if c in CHAR_TO_TILE:
            result.append(CHAR_TO_TILE[c])
        else:
            result.append(0x7F)  # Space for unknown
    if terminator:
        result.append(0x50)  # String terminator
    return result


# ============================================================
# Collision tile types (from pret/pokeyellow)
# ============================================================

# Tile IDs that are walkable (collision = 0)
WALKABLE_TILES = {
    0x00,  # Grass
    0x01,  # Grass variant
    0x04,  # Path/floor
    0x05,  # Path variant
    0x0A,  # Indoor floor
    0x0B,  # Indoor floor variant
    0x14,  # Carpet/rug
    0x48,  # Sand
    0x49,  # Sand variant
}

# Tiles that trigger encounters
ENCOUNTER_TILES = {
    0x0F,  # Tall grass
    0x14,  # Cave floor (encounters)
    0x15,  # Cave floor variant
}

# Tiles that are warp points (doors, stairs, etc.)
# These are collision tile IDs, not visual tile IDs
WARP_TILES = {
    0x1A,  # Door
    0x1B,  # Door variant
    0x3C,  # Warp/door (common indoor)
    0x3D,  # Warp/door variant
    0x52,  # Stairs
    0x53,  # Stairs variant
    0x5C,  # Ladder
    0x5D,  # Ladder variant
    0x71,  # Warp tile
    0x79,  # Warp tile variant
    # Common indoor warp tiles in Pokemon Yellow
    0x00,  # Some floors act as warp zones near edges
}

# Solid/impassable tiles
SOLID_TILES = {
    0x03,  # Tree
    0x07,  # Building wall
    0x08,  # Building wall variant
    0x12,  # Water
    0x13,  # Water variant
    0x21,  # Rock/boulder
    0x24,  # Fence
}


# ============================================================
# Name entry screen constants
# ============================================================

NAME_ENTRY_PLAYER = 0x00   # Naming the player
NAME_ENTRY_RIVAL = 0x01    # Naming the rival
NAME_ENTRY_POKEMON = 0x02  # Nicknaming a Pokemon

# Maximum name lengths
MAX_PLAYER_NAME = 7
MAX_RIVAL_NAME = 7
MAX_POKEMON_NICK = 10

# Default names in Pokemon Yellow
DEFAULT_PLAYER_NAMES = ["YELLOW", "ASH", "JACK"]
DEFAULT_RIVAL_NAMES = ["BLUE", "GARY", "JOHN"]

"""
ECHO//GARDEN // Shared tuning constants
=======================================
Every gameplay number lives here so balance can be tuned in one place.
This module imports nothing from the rest of the game, so any module can use it
without creating circular imports.
"""

# --- Display -----------------------------------------------------------------
SCREEN_W = 160
SCREEN_H = 120
FPS = 30
WINDOW_TITLE = "ECHO//GARDEN - THE LAST SIGNAL"

# --- Map layout (20 x 14 tiles of 8 px, drawn under an 8 px HUD) -------------
TILE = 8
HUD_H = 8
MAP_W = 20
MAP_H = 14
MAP_Y = HUD_H
ARENA_X0 = TILE                          # inner playfield (inside the outer walls)
ARENA_Y0 = MAP_Y + TILE
ARENA_X1 = SCREEN_W - TILE
ARENA_Y1 = MAP_Y + (MAP_H - 1) * TILE    # = 112, top of the bottom wall row
BOTTOM_BAR_Y = ARENA_Y1                  # message bar sits on the bottom wall row
TOP_BAR_Y = MAP_Y                        # boss bar sits on the top wall row

# --- Player (K-09) -------------------------------------------------------------
PLAYER_W = 6
PLAYER_H = 6
PLAYER_BASE_SPEED = 1.35
PLAYER_BASE_HP = 3
PLAYER_HP_CAP = 6
INVULN_FRAMES = 45
KNOCKBACK_FRAMES = 8
KNOCKBACK_SPEED = 2.4
DEATH_FRAMES = 50
CORNER_ASSIST = 3          # px of automatic nudge when clipping a wall corner
DIAGONAL = 0.70710678      # 1 / sqrt(2)

# --- Energy ----------------------------------------------------------------------
ENERGY_MAX = 100.0
ENERGY_START = 70.0
ENERGY_REGEN = 0.06        # per frame (1.8 per second)
SEED_ENERGY = 15.0
CELL_ENERGY = 35.0

# --- Energy Pulse ------------------------------------------------------------------
PULSE_BASE_COST = 35
PULSE_BASE_RADIUS = 36
PULSE_VISUAL_FRAMES = 10
PULSE_LOCKOUT = 12         # frames between pulses, even with energy to spare
PULSE_STUN_FRAMES = 75
PULSE_KNOCKBACK = 2.6
PULSE_EDGE_SLACK = 3       # px of forgiveness at the ring edge

# --- Echo Replay -------------------------------------------------------------------
ECHO_BASE_HISTORY = 90     # recorded frames (3 seconds)
ECHO_MIN_SAMPLES = 12      # need at least this much trail to project an echo
ECHO_BASE_COOLDOWN = 240   # 8 seconds, starts on activation
ECHO_LINGER = 45           # frames the ghost hovers at the end of its replay
ECHO_LURE_RADIUS = 100     # drones inside this radius hunt the echo instead of K-09
ECHO_COLLAPSE_RADIUS = 26  # when the replay ends, the ghost detonates and stuns lured drones
ECHO_COLLAPSE_STUN = 60
ECHO_COLLAPSE_FX = 10
SPROUT_GROW_FRAMES = 36

# --- Corrupted drones ----------------------------------------------------------------
DRONE_W = 6
DRONE_H = 6
DRONE_PATROL_SPEED = 0.55
DRONE_CHASE_SPEED = 0.80
DRONE_DETECT = 44
DRONE_LOSE = 72
DRONE_PATROL_RANGE = 28
DRONE_RECOVER_FRAMES = 24
DRONE_HIT_RECOIL_FRAMES = 30
DRONE_STUCK_LIMIT = 12
DRONE_SIDESTEP_FRAMES = 18
MOTE_SPEED = 0.75

# --- Environmental hazards -----------------------------------------------------------
VENT_PERIOD = 120
VENT_WARN = 30
VENT_ACTIVE = 30
POD_PERIOD = 120
POD_TELEGRAPH = 24
POD_STUN_FRAMES = 150
SPORE_SPEED = 0.7
SPORE_LIFE = 240
SPORE_SIZE = 4
SPORE_GRACE = 6            # frames a fresh spore ignores walls (it starts inside its pod)
BLIGHT_INSET = 2           # px of forgiveness around corrupted growth

# --- Final boss: THE BLIGHT HEART ------------------------------------------------------
BOSS_HP = 6
BOSS_PHASE2_HP = 3
BOSS_BODY_RADIUS = 14
BOSS_HIT_RADIUS = 18       # added to the pulse radius when checking a core hit
BOSS_SPORE_SPAWN_RADIUS = 24
BOSS_INTRO_FRAMES = 90
BOSS_DYING_FRAMES = 100
BOSS_LANE_SIZE = 16
BOSS_MAX_MOTES = 4
BOSS_CELL_RESPAWN = 240

# --- Chamber pacing --------------------------------------------------------------------
BOOT_FRAMES = 45           # drones and hazards wait while the chamber boots
BANNER_FRAMES = 80
EXIT_OPEN_FRAMES = 20
MESSAGE_FRAMES = 150
LOCKED_MSG_COOLDOWN = 60

# --- Scoring ---------------------------------------------------------------------------
SCORE_SEED = 100
SCORE_CELL = 25
SCORE_STUN = 10
SCORE_MOTE = 40
SCORE_PURIFY = 5
SCORE_CHAMBER = 500
SCORE_NO_DAMAGE = 300
SCORE_TIME_BASE = 600
SCORE_TIME_PER_SEC = 5
SCORE_BOSS_HIT = 150
SCORE_BOSS_DEFEAT = 3000
SCORE_CAP = 9_999_999

# --- Safety caps (keep every transient collection bounded) -------------------------------
MAX_PARTICLES = 240
MAX_LABELS = 14
MAX_SPORES = 48
MAX_DRONES = 12
MAX_SFX_QUEUE = 8
BOSS_MAX_CELLS = 2
INPUT_LOCK_FRAMES = 8

# --- Audio channels ----------------------------------------------------------------------
MUSIC_CHANNELS = (0, 1)
SFX_CHANNELS = (2, 3)

# --- Text --------------------------------------------------------------------------------
MAX_BAR_CHARS = 39         # characters that fit in the 160 px message bar

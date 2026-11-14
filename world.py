"""
ECHO//GARDEN // Chambers, upgrades and progression data
=======================================================
Map legend (20 x 14 tiles):
  #  wall              P  planter (solid)     T  tank / reactor tube (solid)
  O  spore pod (solid) H  boss root mass      .  floor
  @  K-09 spawn        s  Lumen Seed          e  energy cell
  X  exit relay        h  drone (horizontal)  v  drone (vertical)
  V  energy vent       ~  corrupted growth    i  log terminal
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import config as C

SOLID_TILES = "#PTOH"


@dataclass(frozen=True)
class Style:
    bg: int
    floor: int
    floor_line: int
    wall: int
    wall_face: int
    wall_hi: int
    leaf: int
    leaf_hi: int
    tank: int
    accent: int
    ambient: str
    ambient_colors: tuple[int, ...]


@dataclass(frozen=True)
class ChamberDef:
    key: str
    label: str
    name: str
    rows: tuple[str, ...]
    style: Style
    music: str
    drone_speed: float = 1.0
    is_boss: bool = False
    logs: tuple[str, ...] = ()
    hints: tuple[tuple[str, str], ...] = ()


CHAMBERS: list[ChamberDef] = [
    ChamberDef(
        key="vault",
        label="CHAMBER 01",
        name="SEED VAULT",
        rows=(
            "####################",
            "#@....#.......s....#",
            "#.....#.PP.........#",
            "#..i..#.PP....h....#",
            "#.................s#",
            "#.....####..PP.....#",
            "#.s...#.....PP.....#",
            "#.....#............#",
            "##.####...e...####.#",
            "#.........v.....#..#",
            "#..PP...........#..#",
            "#..PP...s.......#X.#",
            "#...............#..#",
            "####################",
        ),
        style=Style(1, 1, 5, 5, 1, 12, 3, 11, 6, 12, "pollen", (10, 11, 6)),
        music="garden",
        drone_speed=0.9,
        logs=("LOG 01: VAULT SEALED. NETWORK SILENT.",),
        hints=(
            ("start", "COLLECT EVERY LUMEN SEED"),
            ("drone", "SPACE: PULSE STUNS DRONES"),
            ("echo", "E: ECHO DECOY REPLAYS YOUR TRAIL"),
            ("relay", "RELAY ONLINE - REACH THE EXIT"),
        ),
    ),
    ChamberDef(
        key="hydro",
        label="CHAMBER 02",
        name="HYDROPONICS",
        rows=(
            "####################",
            "#@..#....s....#....#",
            "#...#.TT...TT.#.s..#",
            "#...V.TT...TT.V....#",
            "#...#....h....#....#",
            "#.i.#.PP.PP.PP#..e.#",
            "#...............O..#",
            "##V###.........###V#",
            "#s....PP.PP.PP.....#",
            "#..O......v.....h..#",
            "#....TT.......TT...#",
            "#e...TT...s...TT.sX#",
            "#..................#",
            "####################",
        ),
        style=Style(1, 1, 3, 3, 1, 11, 3, 11, 12, 11, "bubbles", (6, 12, 7)),
        music="garden",
        drone_speed=1.05,
        logs=("LOG 02: SPORES IN THE WATER. CONTAIN.",),
        hints=(
            ("start", "VENTS FLARE IN RHYTHM - WATCH THE GLOW"),
            ("relay", "RELAY ONLINE - REACH THE EXIT"),
        ),
    ),
    ChamberDef(
        key="reactor",
        label="CHAMBER 03",
        name="REACTOR BLOOM",
        rows=(
            "####################",
            "#@..~...s...~~....s#",
            "#...~..TTTT..~.h...#",
            "#.i.......V........#",
            "#~~..PP.......PP.v~#",
            "#s...PP..v....PP..~#",
            "#......~~~~~~......#",
            "#.V....~.e..~.s..V.#",
            "#......~~~~~~......#",
            "#~..PP...h....PP..~#",
            "#s..PP........PP..s#",
            "#~~...O.........O.~#",
            "#......V..X..V.....#",
            "####################",
        ),
        style=Style(0, 1, 4, 4, 2, 9, 2, 14, 9, 9, "embers", (8, 9, 10)),
        music="reactor",
        drone_speed=1.2,
        logs=("LOG 03: THE HEART IS GROWING. HELP US.",),
        hints=(
            ("start", "PULSE PURGES CORRUPTED GROWTH"),
            ("relay", "RELAY ONLINE - THE CORE AWAITS"),
        ),
    ),
    ChamberDef(
        key="heart",
        label="THE CORE",
        name="THE BLIGHT HEART",
        rows=(
            "####################",
            "#.......HHHH.......#",
            "#.......HHHH.......#",
            "#.......HHHH.......#",
            "#..T....HHHH....T..#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..T............T..#",
            "#..................#",
            "#..................#",
            "#.........@........#",
            "####################",
        ),
        style=Style(0, 0, 2, 2, 0, 8, 2, 8, 8, 8, "motes", (2, 8, 14)),
        music="boss",
        drone_speed=1.1,
        is_boss=True,
        hints=(("start", "ECHO DISTRACTS THE HEART. THEN PULSE!"),),
    ),
]

BOSS_CELL_SPOTS = ((2, 7), (17, 7), (6, 11), (13, 11))


# ---------------------------------------------------------------------------
# Upgrades
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UpgradeDef:
    key: str
    name: tuple[str, str]
    desc: tuple[str, str]
    icon: str


UPGRADES: dict[str, UpgradeDef] = {
    "boots": UpgradeDef("boots", ("PHASE", "BOOTS"), ("SPEED", "+15%"), "icon_boots"),
    "pulse": UpgradeDef("pulse", ("AMPLIFIED", "PULSE"), ("RADIUS +8", "COST -6"), "icon_pulse"),
    "echo": UpgradeDef("echo", ("ECHO", "MEMORY"), ("TRAIL +1S", "CD -2 SEC"), "icon_echo"),
    "shell": UpgradeDef("shell", ("REINFORCED", "SHELL"), ("MAX HP +1", "FULL REPAIR"), "icon_shell"),
}
UPGRADE_MAX_TIER = 2


@dataclass(frozen=True)
class Stats:
    speed: float
    pulse_radius: int
    pulse_cost: int
    echo_history: int
    echo_cooldown: int
    max_hp: int


def derive_stats(upgrades: dict[str, int]) -> Stats:
    """Every upgrade maps to a concrete number change here."""
    b = upgrades.get("boots", 0)
    p = upgrades.get("pulse", 0)
    e = upgrades.get("echo", 0)
    s = upgrades.get("shell", 0)
    return Stats(
        speed=C.PLAYER_BASE_SPEED * (1.0 + 0.15 * b),
        pulse_radius=C.PULSE_BASE_RADIUS + 8 * p,
        pulse_cost=C.PULSE_BASE_COST - 6 * p,
        echo_history=C.ECHO_BASE_HISTORY + 30 * e,
        echo_cooldown=C.ECHO_BASE_COOLDOWN - 60 * e,
        max_hp=min(C.PLAYER_HP_CAP, C.PLAYER_BASE_HP + s),
    )


# ---------------------------------------------------------------------------
# Validation (used by tests and --self-test)
# ---------------------------------------------------------------------------
def find_tiles(rows: tuple[str, ...], chars: str) -> list[tuple[int, int]]:
    return [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in chars]


def reachable(rows: tuple[str, ...], start: tuple[int, int]) -> set[tuple[int, int]]:
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= ny < len(rows) and 0 <= nx < len(rows[0]) and (nx, ny) not in seen:
                if rows[ny][nx] not in SOLID_TILES:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
    return seen


def validate_chamber(ch: ChamberDef) -> list[str]:
    errs: list[str] = []
    rows = ch.rows
    if len(rows) != C.MAP_H or any(len(r) != C.MAP_W for r in rows):
        return [f"{ch.key}: map must be {C.MAP_W}x{C.MAP_H}"]
    if any(r[0] != "#" or r[-1] != "#" for r in rows) or set(rows[0]) != {"#"} or set(rows[-1]) != {"#"}:
        errs.append(f"{ch.key}: outer wall broken")
    spawns = find_tiles(rows, "@")
    if len(spawns) != 1:
        return errs + [f"{ch.key}: needs exactly one spawn"]
    reach = reachable(rows, spawns[0])
    for t in find_tiles(rows, "seXi"):
        if t not in reach:
            errs.append(f"{ch.key}: tile {t} unreachable")
    if not ch.is_boss:
        if len(find_tiles(rows, "X")) != 1:
            errs.append(f"{ch.key}: needs exactly one exit")
        if not find_tiles(rows, "s"):
            errs.append(f"{ch.key}: no seeds")
    sx, sy = spawns[0]
    for dx, dy in find_tiles(rows, "hvVO~"):
        if abs(dx - sx) + abs(dy - sy) < 3:
            errs.append(f"{ch.key}: hazard/drone at {(dx, dy)} too close to spawn")
    for _, text in ch.hints:
        if len(text) > C.MAX_BAR_CHARS:
            errs.append(f"{ch.key}: hint too long: {text}")
    for text in ch.logs:
        if len(text) > C.MAX_BAR_CHARS:
            errs.append(f"{ch.key}: log too long: {text}")
    return errs


def validate_upgrades() -> list[str]:
    """Upgrade card text must fit the 48 px cards (11 characters)."""
    return [f"{u.key}: '{line}' too wide" for u in UPGRADES.values() for line in (*u.name, *u.desc) if len(line) > 11]

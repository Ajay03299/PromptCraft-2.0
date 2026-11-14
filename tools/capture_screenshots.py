"""
Capture real gameplay screenshots headlessly (no window) into docs/screenshots/.

    python tools/capture_screenshots.py

The deterministic test autopilot plays the game; frames are rendered by the real
renderer and written as 4x-scaled PNGs using only the standard library.
"""

from __future__ import annotations

import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pyxel  # noqa: E402

import config as C  # noqa: E402
from assets import init_assets  # noqa: E402
from game import Game, GameState  # noqa: E402
from render import Renderer  # noqa: E402
from selftest import Autopilot  # noqa: E402
from session import InputState  # noqa: E402

OUT = os.path.join(ROOT, "docs", "screenshots")
SCALE = 4


def save_png(path: str) -> None:
    palette = [int(c) for c in pyxel.colors]
    rows = []
    for y in range(C.SCREEN_H):
        line = bytearray()
        for x in range(C.SCREEN_W):
            rgb = palette[pyxel.pget(x, y)]
            line += bytes(((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)) * SCALE
        rows.extend([b"\x00" + bytes(line)] * SCALE)
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    w, h = C.SCREEN_W * SCALE, C.SCREEN_H * SCALE
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    pyxel.init(C.SCREEN_W, C.SCREEN_H, headless=True)
    init_assets()
    r = Renderer()
    g = Game(seed=12)
    bot = Autopilot()
    shots = {
        "01_title.png": lambda: g.state == GameState.TITLE and g.frame == 70,
        "02_intro.png": lambda: g.state == GameState.INTRO and g.intro_page == 2 and g.state_timer > 40,
        "03_seed_vault.png": lambda: g.state == GameState.PLAYING and g.chamber_index == 0 and g.session.frame == 200,
        "04_echo_decoy.png": lambda: g.state == GameState.PLAYING and g.session.echo is not None
        and g.session.echo.index == 40 and g.chamber_index in (0, 1),
        "05_hydroponics.png": lambda: g.state == GameState.PLAYING and g.chamber_index == 1 and g.session.frame == 420,
        "06_upgrade.png": lambda: g.state == GameState.UPGRADE and g.state_timer == 6,
        "07_reactor_bloom.png": lambda: g.state == GameState.PLAYING and g.chamber_index == 2 and g.session.frame == 300,
        "08_boss.png": lambda: g.state == GameState.PLAYING and g.chamber_index == 3 and g.session.lanes
        and not g.session.lanes[0].striking and g.session.boss.timer == 12,
        "09_boss_exposed.png": lambda: g.state == GameState.PLAYING and g.chamber_index == 3
        and g.session.boss.exposed and g.session.boss.timer == 60,
        "11_echo_trap.png": lambda: g.state == GameState.PLAYING and g.session.collapse_fx is not None
        and g.session.collapse_fx[2] == 6 and any(d.state.value == "STUNNED" for d in g.session.drones),
        "10_victory.png": lambda: g.state == GameState.VICTORY and g.state_timer == 88,
    }
    taken: set[str] = set()
    for _ in range(40000):
        if g.state == GameState.TITLE:
            inp = InputState(confirm=g.frame > 72)
        elif g.state == GameState.INTRO:
            inp = InputState(confirm=g.state_timer % 30 == 0 and g.state_timer > 0)
        else:
            inp = bot.act(g)
        g.update(inp)
        r.draw(g)
        for name, cond in shots.items():
            if name not in taken and cond():
                save_png(os.path.join(OUT, name))
                taken.add(name)
                print("saved", name)
        if g.state == GameState.VICTORY and g.state_timer > 89:
            break
    missing = set(shots) - taken
    if missing:
        print("not captured:", ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()

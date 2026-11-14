"""Shared fixtures for the unit tests (deterministic, no window)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game, GameState  # noqa: E402
from session import InputState  # noqa: E402

LOCK = 10  # comfortably longer than INPUT_LOCK_FRAMES


def playing(chamber: int = 0, seed: int = 1) -> Game:
    """A game sitting in PLAYING in the given chamber, entered through legal transitions."""
    g = Game(seed=seed)
    g.set_state(GameState.INTRO)
    g.start_new_run()
    if chamber:
        g._load_chamber(chamber)
    return g


def tick(g: Game, n: int = 1, **keys) -> None:
    for _ in range(n):
        g.update(InputState(**keys))


def clear_room(sess) -> None:
    """Remove every threat so a test can isolate one mechanic."""
    sess.drones.clear()
    sess.vents.clear()
    sess.pods.clear()
    sess.spores.clear()
    sess.blight.clear()
    sess.frame = 1000  # past boot

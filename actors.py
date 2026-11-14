"""
ECHO//GARDEN // Actors
======================
Plain data + small behaviours for everything that lives inside a chamber.
Simulation rules that need the whole chamber live in session.py.
"""

from __future__ import annotations

from enum import Enum

import config as C
from engine import Entity


class DroneState(str, Enum):
    PATROL = "PATROL"
    CHASE_PLAYER = "CHASE_PLAYER"
    CHASE_ECHO = "CHASE_ECHO"
    STUNNED = "STUNNED"
    RECOVER = "RECOVER"


HARMFUL_DRONE_STATES = (DroneState.PATROL, DroneState.CHASE_PLAYER, DroneState.CHASE_ECHO)


class Player(Entity):
    def __init__(self, x: float, y: float, max_hp: int, hp: int, energy: float) -> None:
        super().__init__(x=x, y=y, w=C.PLAYER_W, h=C.PLAYER_H, sprite="k09_idle_a", tag="player")
        self.max_hp = max_hp
        self.hp = max(0, min(hp, max_hp))
        self.energy = energy
        self.invuln = 0
        self.knock_vx = 0.0
        self.knock_vy = 0.0
        self.knock_frames = 0
        self.facing = 1
        self.moving = False
        self.dying = 0

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0


class Drone(Entity):
    _next_id = 0

    def __init__(self, x: float, y: float, axis: str = "h", speed_mult: float = 1.0, kind: str = "drone") -> None:
        super().__init__(x=x, y=y, w=C.DRONE_W, h=C.DRONE_H, sprite="drone_a", tag=kind)
        Drone._next_id += 1
        self.uid = Drone._next_id
        self.kind = kind
        self.state = DroneState.PATROL
        self.axis = axis
        self.home_x = x
        self.home_y = y
        self.dir = 1
        self.patrol_speed = C.DRONE_PATROL_SPEED * speed_mult
        self.chase_speed = (C.MOTE_SPEED if kind == "mote" else C.DRONE_CHASE_SPEED) * speed_mult
        self.stun_timer = 0
        self.recover_timer = 0
        self.stuck = 0
        self.sidestep = 0
        self.side_dx = 0.0
        self.side_dy = 0.0
        self.alert = 0

    @property
    def harmful(self) -> bool:
        return self.alive and self.state in HARMFUL_DRONE_STATES

    def stun(self, vx: float, vy: float, frames: int) -> None:
        self.state = DroneState.STUNNED
        self.stun_timer = max(1, frames)  # re-stunning resets, never stacks
        self.vx, self.vy = vx, vy

    def recoil(self, vx: float, vy: float, frames: int) -> None:
        self.state = DroneState.RECOVER
        self.recover_timer = max(1, frames)
        self.vx, self.vy = vx, vy


class EchoGhost:
    """A replay of K-09's recorded trail, played backwards so it walks away from the player."""

    def __init__(self, path: list[tuple[float, float]], linger: int = C.ECHO_LINGER) -> None:
        self.path = path if path else [(0.0, 0.0)]
        self.index = 0
        self.linger = linger
        self.linger_max = max(1, linger)
        self.alive = True
        self.boss_locked = False
        self.w = C.PLAYER_W
        self.h = C.PLAYER_H

    @property
    def pos(self) -> tuple[float, float]:
        return self.path[min(self.index, len(self.path) - 1)]

    def center(self) -> tuple[float, float]:
        x, y = self.pos
        return (x + self.w / 2, y + self.h / 2)

    @property
    def replaying(self) -> bool:
        return self.index < len(self.path) - 1

    def update(self) -> None:
        if not self.alive:
            return
        if self.replaying:
            self.index += 1
        else:
            self.linger -= 1
            if self.linger <= 0:
                self.alive = False

    def expire(self) -> None:
        self.alive = False


class Pickup(Entity):
    def __init__(self, x: float, y: float, kind: str) -> None:
        super().__init__(x=x, y=y, w=6, h=6, sprite="seed_a" if kind == "seed" else "cell", tag=kind)
        self.kind = kind


class Vent:
    def __init__(self, tx: int, ty: int, x: float, y: float, offset: int) -> None:
        self.tx, self.ty, self.x, self.y = tx, ty, x, y
        self.offset = offset

    def phase(self, t: int) -> str:
        """t is frames since the chamber finished booting; negative means still booting."""
        if t < 0:
            return "idle"
        p = (t + self.offset) % C.VENT_PERIOD
        if p >= C.VENT_PERIOD - C.VENT_ACTIVE:
            return "active"
        if p >= C.VENT_PERIOD - C.VENT_ACTIVE - C.VENT_WARN:
            return "warn"
        return "idle"


class SporePod:
    def __init__(self, tx: int, ty: int, cx: float, cy: float, delay: int) -> None:
        self.tx, self.ty, self.cx, self.cy = tx, ty, cx, cy
        self.timer = -delay
        self.stun = 0
        self.diagonal = False

    @property
    def telegraph(self) -> bool:
        return self.stun == 0 and self.timer >= C.POD_PERIOD - C.POD_TELEGRAPH


class Spore:
    def __init__(self, x: float, y: float, vx: float, vy: float, grace: int = C.SPORE_GRACE) -> None:
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.w = self.h = C.SPORE_SIZE
        self.life = C.SPORE_LIFE
        self.grace = grace
        self.alive = True


class Lane:
    """A telegraphed root-slam strip from the boss."""

    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h
        self.striking = False


class Terminal:
    def __init__(self, tx: int, ty: int, x: float, y: float, text: str) -> None:
        self.tx, self.ty, self.x, self.y, self.text = tx, ty, x, y, text


class Exit:
    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.state = "locked"  # locked -> opening -> open
        self.timer = 0

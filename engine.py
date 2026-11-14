"""
ECHO//GARDEN // Core Micro-Engine Primitives
============================================
Extended from the PIXELBOX starter engine. Reusable, game-agnostic building blocks:

  - Entity            : 2D actor with AABB collision (starter API preserved)
  - ParticleSystem    : bounded particle emitter (starter API preserved)
  - FloatingTextManager: bounded rising text popups (starter API preserved)
  - Camera            : screen shake + flash, with an accessibility on/off switch
  - TileGrid          : tile-map collision with sub-pixel-safe movement

Fixes over the starter:
  * Particles and labels were unbounded; both now have hard caps.
  * ParticleSystem.burst(life < 4) crashed (random.randint(4, 3)); fixed.
  * Randomness is injectable so gameplay can be deterministic when seeded.
  * Camera shake can be disabled and never touches gameplay coordinates.

Drawing methods are the only code here that calls Pyxel, so all logic is testable
without opening a window.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable

import pyxel

from assets import draw_sprite


# ---------------------------------------------------------------------------
# Small math helpers
# ---------------------------------------------------------------------------
def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to the inclusive range [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def rects_overlap(
    ax: float, ay: float, aw: float, ah: float, bx: float, by: float, bw: float, bh: float
) -> bool:
    """Axis-aligned rectangle overlap test (touching edges do not overlap)."""
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def safe_direction(dx: float, dy: float, fallback_angle: float = 0.0) -> tuple[float, float]:
    """Unit vector of (dx, dy). At zero length, return the fallback angle instead of dividing by 0."""
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return (math.cos(fallback_angle), math.sin(fallback_angle))
    return (dx / length, dy / length)


# ---------------------------------------------------------------------------
# Entity (starter API preserved)
# ---------------------------------------------------------------------------
@dataclass
class Entity:
    """Generic 2D actor with position, velocity, bounding box, and custom tags/state."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    w: int = 8
    h: int = 8
    sprite: str = "crate"
    tag: str = "neutral"
    flip_x: bool = False
    alive: bool = True
    hp: int = 3
    timer: int = 0
    data: dict = field(default_factory=dict)

    def update(self) -> None:
        self.x += self.vx
        self.y += self.vy
        self.timer += 1

    def draw(self, cam_x: float = 0.0, cam_y: float = 0.0) -> None:
        if self.alive:
            draw_sprite(self.sprite, self.x - cam_x, self.y - cam_y, flip_x=self.flip_x)

    def intersects(self, other: "Entity") -> bool:
        """Axis-Aligned Bounding Box (AABB) collision check."""
        return (
            self.alive
            and other.alive
            and rects_overlap(self.x, self.y, self.w, self.h, other.x, other.y, other.w, other.h)
        )

    def overlaps_rect(self, x: float, y: float, w: float, h: float) -> bool:
        return self.alive and rects_overlap(self.x, self.y, self.w, self.h, x, y, w, h)

    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    def distance_to(self, other: "Entity") -> float:
        ax, ay = self.center()
        bx, by = other.center()
        return math.hypot(bx - ax, by - ay)


# ---------------------------------------------------------------------------
# Particles (bounded)
# ---------------------------------------------------------------------------
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: int
    life: int
    max_life: int
    size: int = 2


class ParticleSystem:
    """Lightweight particle emitter with a hard cap so effects can never grow without limit."""

    def __init__(self, max_particles: int = 240, rng: random.Random | None = None) -> None:
        self.particles: list[Particle] = []
        self.max_particles = max(1, max_particles)
        self.rng = rng or random.Random()

    def _enforce_cap(self) -> None:
        overflow = len(self.particles) - self.max_particles
        if overflow > 0:
            del self.particles[:overflow]  # drop the oldest first

    def spawn(
        self, x: float, y: float, vx: float, vy: float, color: int, life: int = 16, size: int = 1
    ) -> None:
        life = max(1, int(life))
        self.particles.append(Particle(x, y, vx, vy, color & 15, life, life, max(1, size)))
        self._enforce_cap()

    def burst(
        self,
        x: float,
        y: float,
        count: int = 12,
        colors: list[int] | None = None,
        speed: float = 1.8,
        life: int = 18,
    ) -> None:
        palette = colors or [7, 9, 10, 12]
        life = max(1, int(life))
        low_life = max(1, min(life, max(4, life // 2)))  # starter crashed when life < 4
        rng = self.rng
        for _ in range(max(0, count)):
            angle = rng.uniform(0.0, math.tau)
            mag = rng.uniform(0.3, max(0.3, speed))
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * mag,
                    vy=math.sin(angle) * mag,
                    color=rng.choice(palette) & 15,
                    life=rng.randint(low_life, life),
                    max_life=life,
                    size=rng.choice((1, 2)),
                )
            )
        self._enforce_cap()

    def ring(
        self, x: float, y: float, radius: float, count: int, colors: list[int], speed: float = 1.0
    ) -> None:
        """Particles placed on a circle, flying outward (used for shockwaves)."""
        count = max(1, count)
        for i in range(count):
            angle = math.tau * i / count
            cx, cy = math.cos(angle), math.sin(angle)
            self.particles.append(
                Particle(
                    x + cx * radius,
                    y + cy * radius,
                    cx * speed,
                    cy * speed,
                    colors[i % len(colors)] & 15,
                    14,
                    14,
                    1,
                )
            )
        self._enforce_cap()

    def update(self, gravity: float = 0.04) -> None:
        alive_list: list[Particle] = []
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.vy += gravity
            p.life -= 1
            if p.life > 0:
                alive_list.append(p)
        self.particles = alive_list

    def clear(self) -> None:
        self.particles.clear()

    def draw(self, cam_x: float = 0.0, cam_y: float = 0.0) -> None:
        for p in self.particles:
            r = p.size if p.life > p.max_life // 3 else 1
            pyxel.rect(int(p.x - cam_x), int(p.y - cam_y), r, r, p.color)


# ---------------------------------------------------------------------------
# Floating text (bounded)
# ---------------------------------------------------------------------------
@dataclass
class FloatingLabel:
    text: str
    x: float
    y: float
    color: int = 7
    life: int = 24


class FloatingTextManager:
    """Renders rising pixel text popups (e.g., '+10', 'STUN', 'ECHO!')."""

    def __init__(self, max_labels: int = 14) -> None:
        self.labels: list[FloatingLabel] = []
        self.max_labels = max(1, max_labels)

    def spawn(self, text: str, x: float, y: float, color: int = 10, life: int = 24) -> None:
        self.labels.append(FloatingLabel(text=text, x=x, y=y, color=color & 15, life=max(1, life)))
        overflow = len(self.labels) - self.max_labels
        if overflow > 0:
            del self.labels[:overflow]

    def spawn_centered(self, text: str, cx: float, y: float, color: int = 10, life: int = 24) -> None:
        self.spawn(text, cx - len(text) * 2, y, color, life)

    def update(self) -> None:
        next_labels: list[FloatingLabel] = []
        for lbl in self.labels:
            lbl.y -= 0.4
            lbl.life -= 1
            if lbl.life > 0:
                next_labels.append(lbl)
        self.labels = next_labels

    def clear(self) -> None:
        self.labels.clear()

    def draw(self, cam_x: float = 0.0, cam_y: float = 0.0) -> None:
        for lbl in self.labels:
            x = int(lbl.x - cam_x)
            y = int(lbl.y - cam_y)
            pyxel.text(x + 1, y + 1, lbl.text, 0)  # 1px shadow for legibility
            pyxel.text(x, y, lbl.text, lbl.color)


# ---------------------------------------------------------------------------
# Camera (render-only: it never changes gameplay coordinates)
# ---------------------------------------------------------------------------
class Camera:
    """Handles viewport offset, screen shake, and flash effects."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.x: float = 0.0
        self.y: float = 0.0
        self.shake_frames: int = 0
        self.shake_intensity: float = 0.0
        self.flash_frames: int = 0
        self.flash_color: int = 7
        self.enabled: bool = True  # accessibility toggle for screen shake
        self.rng = rng or random.Random()

    def shake(self, frames: int = 6, intensity: float = 2.0) -> None:
        self.shake_frames = max(self.shake_frames, max(0, frames))
        self.shake_intensity = min(3.0, max(self.shake_intensity, intensity))  # capped for comfort

    def flash(self, frames: int = 3, color: int = 7) -> None:
        self.flash_frames = max(0, frames)
        self.flash_color = color & 15

    def get_offset(self) -> tuple[float, float]:
        if self.enabled and self.shake_frames > 0:
            ox = self.rng.uniform(-self.shake_intensity, self.shake_intensity)
            oy = self.rng.uniform(-self.shake_intensity, self.shake_intensity)
            return (self.x + ox, self.y + oy)
        return (self.x, self.y)

    def update(self) -> None:
        if self.shake_frames > 0:
            self.shake_frames -= 1
            if self.shake_frames == 0:
                self.shake_intensity = 0.0
        if self.flash_frames > 0:
            self.flash_frames -= 1

    def reset(self) -> None:
        self.shake_frames = 0
        self.shake_intensity = 0.0
        self.flash_frames = 0


# ---------------------------------------------------------------------------
# Tile-map collision
# ---------------------------------------------------------------------------
class TileGrid:
    """
    A grid of single-character tiles. Characters listed in `solid` block movement and
    anything outside the grid counts as solid, so actors can never leave the arena.
    """

    def __init__(
        self,
        rows: Iterable[str],
        tile_size: int = 8,
        origin_x: int = 0,
        origin_y: int = 0,
        solid: str = "#",
    ) -> None:
        self.tiles: list[list[str]] = [list(row) for row in rows]
        self.h = len(self.tiles)
        self.w = len(self.tiles[0]) if self.h else 0
        if any(len(row) != self.w for row in self.tiles):
            raise ValueError("TileGrid rows must all have the same width")
        self.size = tile_size
        self.ox = origin_x
        self.oy = origin_y
        self.solid = frozenset(solid)

    # --- queries -------------------------------------------------------------
    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.w and 0 <= ty < self.h

    def get(self, tx: int, ty: int) -> str:
        return self.tiles[ty][tx] if self.in_bounds(tx, ty) else "#"

    def set(self, tx: int, ty: int, ch: str) -> None:
        if self.in_bounds(tx, ty):
            self.tiles[ty][tx] = ch

    def is_solid_tile(self, tx: int, ty: int) -> bool:
        return (not self.in_bounds(tx, ty)) or self.tiles[ty][tx] in self.solid

    def tile_at(self, px: float, py: float) -> tuple[int, int]:
        return (int(math.floor((px - self.ox) / self.size)), int(math.floor((py - self.oy) / self.size)))

    def tile_rect(self, tx: int, ty: int) -> tuple[int, int, int, int]:
        return (self.ox + tx * self.size, self.oy + ty * self.size, self.size, self.size)

    def tile_center(self, tx: int, ty: int) -> tuple[float, float]:
        return (self.ox + tx * self.size + self.size / 2, self.oy + ty * self.size + self.size / 2)

    def tiles_in_rect(self, x: float, y: float, w: float, h: float) -> Iterable[tuple[int, int]]:
        eps = 1e-4
        tx0, ty0 = self.tile_at(x, y)
        tx1, ty1 = self.tile_at(x + w - eps, y + h - eps)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                yield (tx, ty)

    def rect_solid(self, x: float, y: float, w: float, h: float) -> bool:
        for tx, ty in self.tiles_in_rect(x, y, w, h):
            if self.is_solid_tile(tx, ty):
                return True
        return False

    def entity_solid(self, ent: Entity) -> bool:
        return self.rect_solid(ent.x, ent.y, ent.w, ent.h)

    # --- movement ------------------------------------------------------------
    def _move_axis(self, ent: Entity, dx: float, dy: float) -> bool:
        """Move along one axis in <=1 px steps; return True if a wall stopped the move."""
        dist = abs(dx) + abs(dy)
        if dist <= 0.0:
            return False
        steps = max(1, int(math.ceil(dist)))
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            nx, ny = ent.x + sx, ent.y + sy
            if self.rect_solid(nx, ny, ent.w, ent.h):
                # Bisect the remaining step so actors rest snugly against walls.
                lo, hi = 0.0, 1.0
                for _ in range(5):
                    mid = (lo + hi) / 2
                    if self.rect_solid(ent.x + sx * mid, ent.y + sy * mid, ent.w, ent.h):
                        hi = mid
                    else:
                        lo = mid
                ent.x += sx * lo
                ent.y += sy * lo
                return True
            ent.x, ent.y = nx, ny
        return False

    def move(self, ent: Entity, dx: float, dy: float, assist: int = 0) -> tuple[bool, bool]:
        """
        Axis-separated movement with wall sliding. `assist` lets the mover slip past
        corners it clips by up to that many pixels (used for the player only).
        Returns (blocked_x, blocked_y).
        """
        blocked_x = self._move_axis(ent, dx, 0.0)
        if blocked_x and assist and dy == 0.0:
            blocked_x = self._corner_assist(ent, dx, 0.0, assist)
        blocked_y = self._move_axis(ent, 0.0, dy)
        if blocked_y and assist and dx == 0.0:
            blocked_y = self._corner_assist(ent, 0.0, dy, assist)
        return blocked_x, blocked_y

    def _corner_assist(self, ent: Entity, dx: float, dy: float, assist: int) -> bool:
        step = 1.0 if dx != 0.0 else 0.0
        for offset in range(1, assist + 1):
            for sign in (-1, 1):
                ox = 0.0 if step else sign * offset
                oy = sign * offset if step else 0.0
                tx, ty = ent.x + ox, ent.y + oy
                if not self.rect_solid(tx, ty, ent.w, ent.h) and not self.rect_solid(
                    tx + (1 if dx > 0 else -1 if dx < 0 else 0),
                    ty + (1 if dy > 0 else -1 if dy < 0 else 0),
                    ent.w,
                    ent.h,
                ):
                    # Nudge toward the free side by at most the movement amount.
                    nudge = min(abs(dx) + abs(dy), 1.0)
                    self._move_axis(ent, (ox / offset) * nudge, (oy / offset) * nudge)
                    return False
        return True

    def find_free_near(self, x: float, y: float, w: float, h: float, max_radius: int = 8) -> tuple[float, float]:
        """Nearest position (tile-aligned search) where a w*h box is not inside a wall."""
        if not self.rect_solid(x, y, w, h):
            return (x, y)
        tx0, ty0 = self.tile_at(x + w / 2, y + h / 2)
        pad_x = (self.size - w) / 2
        pad_y = (self.size - h) / 2
        for radius in range(1, max_radius + 1):
            best: tuple[float, float] | None = None
            best_d = float("inf")
            for ty in range(ty0 - radius, ty0 + radius + 1):
                for tx in range(tx0 - radius, tx0 + radius + 1):
                    if max(abs(tx - tx0), abs(ty - ty0)) != radius:
                        continue
                    cx = self.ox + tx * self.size + pad_x
                    cy = self.oy + ty * self.size + pad_y
                    if not self.rect_solid(cx, cy, w, h):
                        d = (cx - x) ** 2 + (cy - y) ** 2
                        if d < best_d:
                            best, best_d = (cx, cy), d
            if best is not None:
                return best
        return (x, y)

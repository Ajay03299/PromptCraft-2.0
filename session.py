"""
ECHO//GARDEN // Chamber simulation
==================================
ChamberSession runs one chamber: K-09, Echo, Pulse, drones, hazards, pickups, the exit
relay and (in the final chamber) THE BLIGHT HEART. It never calls Pyxel, so every rule
here can be unit-tested headlessly with deterministic seeds.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field

import config as C
from actors import (
    DroneState, Drone, EchoGhost, Exit, Lane, Pickup, Player, Spore, SporePod, Terminal, Vent,
)
from engine import Camera, FloatingTextManager, ParticleSystem, TileGrid, clamp, distance, rects_overlap, safe_direction
from world import BOSS_CELL_SPOTS, SOLID_TILES, ChamberDef, Stats


@dataclass
class InputState:
    """One frame of player intent. Held directions + edge-triggered presses."""

    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    up_p: bool = False
    down_p: bool = False
    left_p: bool = False
    right_p: bool = False
    pulse: bool = False
    echo: bool = False
    confirm: bool = False
    pause: bool = False
    quit: bool = False
    mute: bool = False
    shake: bool = False

    def holds_only(self) -> "InputState":
        return InputState(up=self.up, down=self.down, left=self.left, right=self.right)


@dataclass
class Effects:
    particles: ParticleSystem
    popups: FloatingTextManager
    camera: Camera
    sfx: list[str] = field(default_factory=list)

    def play(self, name: str) -> None:
        self.sfx.append(name)
        if len(self.sfx) > C.MAX_SFX_QUEUE:
            del self.sfx[: len(self.sfx) - C.MAX_SFX_QUEUE]


@dataclass
class RunState:
    score: int = 0
    hp: int = C.PLAYER_BASE_HP
    upgrades: dict = field(default_factory=dict)
    hits_taken: int = 0
    seeds: int = 0
    stuns: int = 0
    purified: int = 0
    frames: int = 0

    def add_score(self, pts: int) -> None:
        self.score = int(clamp(self.score + pts, 0, C.SCORE_CAP))

    def copy(self) -> "RunState":
        return RunState(self.score, self.hp, dict(self.upgrades), self.hits_taken, self.seeds,
                        self.stuns, self.purified, self.frames)


@dataclass
class Message:
    text: str
    color: int
    timer: int


# ---------------------------------------------------------------------------
# Boss
# ---------------------------------------------------------------------------
class Boss:
    CYCLE_1 = ("ring", "slam", "ring", "overheat")
    CYCLE_2 = ("ring", "slam", "summon", "slam", "ring", "overheat")

    def __init__(self, cx: float, cy: float) -> None:
        self.cx, self.cy = cx, cy
        self.hp = C.BOSS_HP
        self.max_hp = C.BOSS_HP
        self.state = "intro"
        self.timer = C.BOSS_INTRO_FRAMES
        self.timer_max = C.BOSS_INTRO_FRAMES
        self.cycle_i = 0
        self.phase = 1
        self.flash = 0
        self.ring_angle = 0.0
        self.slams = 0
        self.beam: tuple[float, float] | None = None

    @property
    def exposed(self) -> bool:
        return self.state == "exposed"

    @property
    def alive(self) -> bool:
        return self.state not in ("dying", "dead")

    def set_state(self, state: str, frames: int) -> None:
        self.state = state
        self.timer = max(1, frames)
        self.timer_max = self.timer


# ---------------------------------------------------------------------------
# Chamber session
# ---------------------------------------------------------------------------
class ChamberSession:
    def __init__(self, chamber: ChamberDef, run: RunState, stats: Stats, fx: Effects, rng: random.Random) -> None:
        self.chamber = chamber
        self.run = run
        self.stats = stats
        self.fx = fx
        self.rng = rng
        self.frame = 0
        self.banner = C.BANNER_FRAMES
        self.message: Message | None = None
        self.hints_shown: set[str] = set()
        self.completed = False
        self.victory = False
        self.dead = False
        self.damage_here = 0
        self.purified_here = 0

        rows = chamber.rows
        self.grid = TileGrid(
            ["".join(ch if ch in SOLID_TILES else "." for ch in row) for row in rows],
            tile_size=C.TILE, origin_x=0, origin_y=C.MAP_Y, solid=SOLID_TILES,
        )
        self.seeds: list[Pickup] = []
        self.cells: list[Pickup] = []
        self.drones: list[Drone] = []
        self.vents: list[Vent] = []
        self.pods: list[SporePod] = []
        self.blight: set[tuple[int, int]] = set()
        self.terminals: list[Terminal] = []
        self.spores: list[Spore] = []
        self.lanes: list[Lane] = []
        self.exit: Exit | None = None
        self.boss: Boss | None = None
        spawn = (8.0, 16.0)
        log_i = 0
        for ty, row in enumerate(rows):
            for tx, ch in enumerate(row):
                x, y = tx * C.TILE, C.MAP_Y + ty * C.TILE
                if ch == "@":
                    spawn = (x + 1, y + 1)
                elif ch == "s":
                    self.seeds.append(Pickup(x + 1, y + 1, "seed"))
                elif ch == "e":
                    self.cells.append(Pickup(x + 1, y + 1, "cell"))
                elif ch in "hv":
                    self.drones.append(Drone(x + 1, y + 1, "h" if ch == "h" else "v", chamber.drone_speed))
                elif ch == "V":
                    self.vents.append(Vent(tx, ty, x, y, offset=(len(self.vents) * 40) % C.VENT_PERIOD))
                elif ch == "O":
                    self.pods.append(SporePod(tx, ty, x + 4, y + 4, delay=len(self.pods) * 45))
                elif ch == "~":
                    self.blight.add((tx, ty))
                elif ch == "i":
                    text = chamber.logs[log_i] if log_i < len(chamber.logs) else "LOG: DATA CORRUPTED."
                    self.terminals.append(Terminal(tx, ty, x, y, text))
                    log_i += 1
                elif ch == "X":
                    self.exit = Exit(x, y)
        self.player = Player(spawn[0], spawn[1], stats.max_hp, run.hp, C.ENERGY_START)
        self.seeds_required = len(self.seeds)
        self.seeds_collected = 0

        self.history: deque[tuple[float, float]] = deque(maxlen=stats.echo_history)
        self.echo: EchoGhost | None = None
        self.echo_cooldown = 0
        self.pulse_lockout = 0
        self.pulse_fx: tuple[float, float, int] | None = None  # (x, y, frames_left)
        self.on_terminal: int = -1
        self.locked_msg_cd = 0
        self.cell_timer = 0

        if chamber.is_boss:
            self.boss = Boss(80.0, C.MAP_Y + 3 * C.TILE)  # centre of the 'H' root mass
        self._hint("start")

    # ------------------------------------------------------------------ helpers
    def say(self, text: str, color: int = 7, frames: int = C.MESSAGE_FRAMES) -> None:
        self.message = Message(text[: C.MAX_BAR_CHARS], color, frames)

    def _hint(self, key: str) -> None:
        if key in self.hints_shown:
            return
        for k, text in self.chamber.hints:
            if k == key:
                self.hints_shown.add(key)
                self.say(text, 10)
                return

    @property
    def booting(self) -> bool:
        return self.frame <= C.BOOT_FRAMES

    @property
    def echo_active(self) -> bool:
        return self.echo is not None and self.echo.alive

    def damage_player(self, sx: float, sy: float) -> bool:
        p = self.player
        if p.invuln > 0 or p.is_dead or p.dying or self.completed or self.victory:
            return False
        if self.boss is not None and not self.boss.alive:
            return False
        p.hp = max(0, p.hp - 1)
        self.run.hp = p.hp
        self.run.hits_taken += 1
        self.damage_here += 1
        p.invuln = C.INVULN_FRAMES
        cx, cy = p.center()
        ux, uy = safe_direction(cx - sx, cy - sy, fallback_angle=-math.pi / 2)
        p.knock_vx, p.knock_vy = ux * C.KNOCKBACK_SPEED, uy * C.KNOCKBACK_SPEED
        p.knock_frames = C.KNOCKBACK_FRAMES
        self.fx.camera.shake(8, 2.0)
        self.fx.camera.flash(2, 8)
        self.fx.particles.burst(cx, cy, 14, [8, 14, 7], 2.0, 18)
        self.fx.popups.spawn_centered("-1", cx, p.y - 6, 8)
        self.fx.play("hurt")
        if p.hp <= 0:
            p.dying = C.DEATH_FRAMES
            self.fx.play("boom")
            self.clear_echo()  # an echo never outlives its robot
        return True

    # ------------------------------------------------------------------ update
    def update(self, inp: InputState) -> None:
        self.frame += 1
        self.run.frames += 1
        if self.banner > 0:
            self.banner -= 1
        if self.message:
            self.message.timer -= 1
            if self.message.timer <= 0:
                self.message = None
        if self.locked_msg_cd > 0:
            self.locked_msg_cd -= 1
        if self.pulse_fx:
            x, y, t = self.pulse_fx
            self.pulse_fx = (x, y, t - 1) if t > 1 else None
        if self.completed or self.dead or self.victory:
            return
        p = self.player
        if p.dying:
            p.dying -= 1
            if self.frame % 4 == 0:
                cx, cy = p.center()
                self.fx.particles.burst(cx, cy, 4, [8, 9, 10, 7], 1.6, 14)
            if p.dying <= 0:
                self.dead = True
            return

        self._update_player(inp)
        self._update_abilities(inp)
        self._update_echo()
        if not self.booting:
            self._update_drones()
            self._update_hazards()
        self._update_spores()
        if self.boss:
            self._update_boss()
        self._update_pickups()
        self._update_exit()
        self._update_terminals()
        p.energy = clamp(p.energy + C.ENERGY_REGEN, 0.0, C.ENERGY_MAX)
        if self.frame == 300:
            self._hint("echo")

    # ------------------------------------------------------------------ player
    def _update_player(self, inp: InputState) -> None:
        p = self.player
        if p.invuln > 0:
            p.invuln -= 1
        dx = (1.0 if inp.right else 0.0) - (1.0 if inp.left else 0.0)
        dy = (1.0 if inp.down else 0.0) - (1.0 if inp.up else 0.0)
        if dx and dy:
            dx *= C.DIAGONAL
            dy *= C.DIAGONAL
        if p.knock_frames > 0:
            p.knock_frames -= 1
            vx, vy = p.knock_vx, p.knock_vy
            p.knock_vx *= 0.8
            p.knock_vy *= 0.8
        else:
            vx, vy = dx * self.stats.speed, dy * self.stats.speed
        if dx:
            p.facing = 1 if dx > 0 else -1
        p.moving = bool(dx or dy)
        self.grid.move(p, vx, vy, assist=C.CORNER_ASSIST if p.knock_frames == 0 else 0)
        if self.grid.entity_solid(p):  # safety net: never leave K-09 inside a wall
            p.x, p.y = self.grid.find_free_near(p.x, p.y, p.w, p.h)
        p.x = clamp(p.x, C.ARENA_X0, C.ARENA_X1 - p.w)
        p.y = clamp(p.y, C.ARENA_Y0, C.ARENA_Y1 - p.h)
        self.history.append((p.x, p.y))

    # ------------------------------------------------------------------ abilities
    def _update_abilities(self, inp: InputState) -> None:
        if self.echo_cooldown > 0:
            self.echo_cooldown -= 1
        if self.pulse_lockout > 0:
            self.pulse_lockout -= 1
        if inp.pulse:
            self.try_pulse()
        if inp.echo:
            self.try_echo()

    def try_pulse(self) -> bool:
        p = self.player
        if self.pulse_lockout > 0:
            return False
        cost = self.stats.pulse_cost
        cx, cy = p.center()
        if p.energy < cost:
            self.fx.popups.spawn_centered("LOW ENERGY", cx, p.y - 8, 8, 20)
            self.fx.play("deny")
            self.pulse_lockout = C.PULSE_LOCKOUT
            return False
        p.energy = clamp(p.energy - cost, 0.0, C.ENERGY_MAX)
        self.pulse_lockout = C.PULSE_LOCKOUT
        self.pulse_fx = (cx, cy, C.PULSE_VISUAL_FRAMES)
        r = self.stats.pulse_radius
        self.fx.particles.ring(cx, cy, 6, 16, [12, 6, 7], 2.2)
        self.fx.camera.shake(5, 1.5)
        self.fx.play("pulse")
        self._hint("echo")

        for i, d in enumerate(self.drones):
            dx_, dy_ = d.center()
            dist = distance(cx, cy, dx_, dy_)
            if dist > r + C.PULSE_EDGE_SLACK:
                continue
            if d.kind == "mote":
                d.alive = False
                self.run.add_score(C.SCORE_MOTE)
                self.fx.particles.burst(dx_, dy_, 10, [2, 8, 14], 1.8)
                continue
            ux, uy = safe_direction(dx_ - cx, dy_ - cy, fallback_angle=i * 2.39996)
            d.stun(ux * C.PULSE_KNOCKBACK, uy * C.PULSE_KNOCKBACK, C.PULSE_STUN_FRAMES)
            self.run.add_score(C.SCORE_STUN)
            self.run.stuns += 1
            self.fx.popups.spawn_centered("STUN", dx_, d.y - 6, 6, 18)
            self.fx.play("stun")
        self.drones = [d for d in self.drones if d.alive]

        for s in self.spores:
            if distance(cx, cy, s.x + 2, s.y + 2) <= r + C.PULSE_EDGE_SLACK:
                s.alive = False
                self.fx.particles.burst(s.x + 2, s.y + 2, 3, [14, 8], 1.0, 8)
        self.spores = [s for s in self.spores if s.alive]
        for pod in self.pods:
            if distance(cx, cy, pod.cx, pod.cy) <= r + 4:
                pod.stun = C.POD_STUN_FRAMES
                pod.timer = 0
        purged = [t for t in self.blight if distance(cx, cy, *self.grid.tile_center(*t)) <= r]
        for t in purged:
            self.blight.discard(t)
            tcx, tcy = self.grid.tile_center(*t)
            self.fx.particles.burst(tcx, tcy, 4, [11, 3, 7], 1.2, 14)
        if purged:
            self.purified_here += len(purged)
            self.run.purified += len(purged)
            self.run.add_score(C.SCORE_PURIFY * len(purged))
            self.fx.play("purify")
        b = self.boss
        if b and b.exposed and distance(cx, cy, b.cx, b.cy) <= r + C.BOSS_HIT_RADIUS:
            self._boss_hit()
        return True

    def try_echo(self) -> bool:
        p = self.player
        cx = p.x + p.w / 2
        if self.echo_active:
            self.fx.popups.spawn_centered("ECHO ACTIVE", cx, p.y - 8, 6, 18)
            return False
        if self.echo_cooldown > 0:
            self.fx.popups.spawn_centered("CHARGING", cx, p.y - 8, 5, 18)
            self.fx.play("deny")
            return False
        if len(self.history) < C.ECHO_MIN_SAMPLES:
            self.say("ECHO NEEDS A TRAIL - MOVE FIRST", 6, 60)
            self.fx.play("deny")
            return False
        path = list(self.history)
        path.reverse()  # rewind: the ghost walks back along where K-09 came from
        self.echo = EchoGhost(path)
        self.echo_cooldown = self.stats.echo_cooldown
        self.fx.particles.burst(cx, p.y + 3, 16, [6, 12, 7, 2], 1.6, 20)
        self.fx.popups.spawn_centered("ECHO!", cx, p.y - 8, 6, 24)
        self.fx.play("echo")
        return True

    def _update_echo(self) -> None:
        if self.echo is None:
            return
        self.echo.update()
        if not self.echo.alive:
            ex, ey = self.echo.center()
            self.fx.particles.burst(ex, ey, 8, [6, 12, 2], 1.0, 14)
            self.clear_echo()

    def clear_echo(self) -> None:
        """Remove the echo and release every drone that was hunting it."""
        self.echo = None
        for d in self.drones:
            if d.state == DroneState.CHASE_ECHO:
                d.state = DroneState.PATROL

    # ------------------------------------------------------------------ drones
    def _update_drones(self) -> None:
        p = self.player
        pcx, pcy = p.center()
        for i, d in enumerate(self.drones):
            echo = self.echo if self.echo_active else None  # re-read: a hit can clear it mid-loop
            if d.state in (DroneState.STUNNED, DroneState.RECOVER):
                self.grid.move(d, d.vx, d.vy)
                d.vx *= 0.85
                d.vy *= 0.85
                if d.state == DroneState.STUNNED:
                    d.stun_timer -= 1
                    if d.stun_timer <= 0:
                        d.state = DroneState.RECOVER
                        d.recover_timer = C.DRONE_RECOVER_FRAMES
                else:
                    d.recover_timer -= 1
                    if d.recover_timer <= 0:
                        d.state = DroneState.PATROL
                continue
            dcx, dcy = d.center()
            new = DroneState.PATROL
            target = None
            if echo and distance(dcx, dcy, *echo.center()) <= C.ECHO_LURE_RADIUS:
                new, target = DroneState.CHASE_ECHO, echo.center()
            else:
                dp = distance(dcx, dcy, pcx, pcy)
                if d.kind == "mote" or dp <= C.DRONE_DETECT or (d.state == DroneState.CHASE_PLAYER and dp <= C.DRONE_LOSE):
                    new, target = DroneState.CHASE_PLAYER, (pcx, pcy)
            if new != d.state and new != DroneState.PATROL:
                d.alert = 20
                if new == DroneState.CHASE_PLAYER and d.kind == "drone":
                    self._hint("drone")
            d.state = new
            if d.alert > 0:
                d.alert -= 1
            if target:
                self._steer(d, target[0], target[1], d.chase_speed, i)
            else:
                self._patrol(d, i)
            if d.harmful and d.intersects(p) and self.damage_player(dcx, dcy):
                ux, uy = safe_direction(dcx - pcx, dcy - pcy, i)
                d.recoil(ux * 1.6, uy * 1.6, C.DRONE_HIT_RECOIL_FRAMES)
        # light separation so drones never stack into one blob
        for a in range(len(self.drones)):
            for b in range(a + 1, len(self.drones)):
                da, db = self.drones[a], self.drones[b]
                if da.intersects(db):
                    ax, ay = da.center()
                    bx, by = db.center()
                    ux, uy = safe_direction(bx - ax, by - ay, a + b)
                    self.grid.move(da, -ux * 0.5, -uy * 0.5)
                    self.grid.move(db, ux * 0.5, uy * 0.5)

    def _steer(self, d: Drone, tx: float, ty: float, speed: float, i: int) -> None:
        cx, cy = d.center()
        if distance(cx, cy, tx, ty) < 1.0:
            return
        if d.sidestep > 0:
            d.sidestep -= 1
            ux, uy = d.side_dx, d.side_dy
        else:
            ux, uy = safe_direction(tx - cx, ty - cy, i)
        ox, oy = d.x, d.y
        self.grid.move(d, ux * speed, uy * speed)
        if distance(ox, oy, d.x, d.y) < speed * 0.3:
            d.stuck += 1
            if d.stuck > C.DRONE_STUCK_LIMIT:
                sign = 1 if (d.uid + self.frame // 60) % 2 else -1
                d.side_dx, d.side_dy = -uy * sign, ux * sign
                d.sidestep = C.DRONE_SIDESTEP_FRAMES
                d.stuck = 0
        else:
            d.stuck = max(0, d.stuck - 1)
        d.flip_x = ux < 0

    def _patrol(self, d: Drone, i: int) -> None:
        if d.axis == "h":
            off = abs(d.y - d.home_y) + max(0.0, abs(d.x - d.home_x) - C.DRONE_PATROL_RANGE)
        else:
            off = abs(d.x - d.home_x) + max(0.0, abs(d.y - d.home_y) - C.DRONE_PATROL_RANGE)
        if off > 3:  # wandered off after a chase: head home first
            self._steer(d, d.home_x + d.w / 2, d.home_y + d.h / 2, d.patrol_speed, i)
            return
        if d.axis == "h":
            bx, _ = self.grid.move(d, d.dir * d.patrol_speed, 0.0)
            if bx or abs(d.x - d.home_x) >= C.DRONE_PATROL_RANGE:
                d.dir *= -1
                d.x = clamp(d.x, d.home_x - C.DRONE_PATROL_RANGE + 0.1, d.home_x + C.DRONE_PATROL_RANGE - 0.1)
        else:
            _, by = self.grid.move(d, 0.0, d.dir * d.patrol_speed)
            if by or abs(d.y - d.home_y) >= C.DRONE_PATROL_RANGE:
                d.dir *= -1
                d.y = clamp(d.y, d.home_y - C.DRONE_PATROL_RANGE + 0.1, d.home_y + C.DRONE_PATROL_RANGE - 0.1)
        d.flip_x = d.dir < 0

    # ------------------------------------------------------------------ hazards
    def vent_time(self) -> int:
        return self.frame - C.BOOT_FRAMES

    def _update_hazards(self) -> None:
        p = self.player
        t = self.vent_time()
        for v in self.vents:
            if v.phase(t) == "active" and p.overlaps_rect(v.x + 1, v.y + 1, 6, 6):
                self.damage_player(v.x + 4, v.y + 4)
        for pod in self.pods:
            if pod.stun > 0:
                pod.stun -= 1
                continue
            pod.timer += 1
            if pod.timer >= C.POD_PERIOD:
                pod.timer = 0
                dirs = ((0.707, 0.707), (-0.707, 0.707), (0.707, -0.707), (-0.707, -0.707)) if pod.diagonal \
                    else ((1, 0), (-1, 0), (0, 1), (0, -1))
                pod.diagonal = not pod.diagonal
                for ux, uy in dirs:
                    self._add_spore(pod.cx + ux * 5 - 2, pod.cy + uy * 5 - 2, ux * C.SPORE_SPEED, uy * C.SPORE_SPEED)
                if distance(pod.cx, pod.cy, *p.center()) < 70:
                    self.fx.play("spore")
        if self.blight:
            inset = C.BLIGHT_INSET
            for tx, ty in self.grid.tiles_in_rect(p.x, p.y, p.w, p.h):
                if (tx, ty) in self.blight:
                    x, y, w, h = self.grid.tile_rect(tx, ty)
                    if p.overlaps_rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset):
                        self.damage_player(x + 4, y + 4)
                        break

    def _add_spore(self, x: float, y: float, vx: float, vy: float, grace: int = C.SPORE_GRACE) -> None:
        if len(self.spores) < C.MAX_SPORES:
            self.spores.append(Spore(x, y, vx, vy, grace))

    def _update_spores(self) -> None:
        p = self.player
        for s in self.spores:
            s.x += s.vx
            s.y += s.vy
            s.life -= 1
            if s.grace > 0:
                s.grace -= 1
            elif self.grid.rect_solid(s.x, s.y, s.w, s.h):
                s.alive = False
            if s.life <= 0:
                s.alive = False
            if s.alive and p.overlaps_rect(s.x, s.y, s.w, s.h) and self.damage_player(s.x + 2, s.y + 2):
                s.alive = False
        self.spores = [s for s in self.spores if s.alive]

    # ------------------------------------------------------------------ pickups / exit / logs
    def _update_pickups(self) -> None:
        p = self.player
        for seed in self.seeds:
            if seed.alive and p.intersects(seed):
                seed.alive = False  # collected exactly once
                self.seeds_collected += 1
                self.run.seeds += 1
                self.run.add_score(C.SCORE_SEED)
                p.energy = clamp(p.energy + C.SEED_ENERGY, 0.0, C.ENERGY_MAX)
                cx, cy = seed.center()
                self.fx.particles.burst(cx, cy, 16, [10, 9, 7, 11], 1.8, 20)
                self.fx.popups.spawn_centered(f"+{C.SCORE_SEED}", cx, seed.y - 6, 10)
                self.fx.play("seed")
        self.seeds = [s for s in self.seeds if s.alive]
        for cell in self.cells:
            if cell.alive and p.intersects(cell):
                cell.alive = False
                p.energy = clamp(p.energy + C.CELL_ENERGY, 0.0, C.ENERGY_MAX)
                self.run.add_score(C.SCORE_CELL)
                cx, cy = cell.center()
                self.fx.particles.burst(cx, cy, 10, [12, 6, 7], 1.4, 16)
                self.fx.popups.spawn_centered("+NRG", cx, cell.y - 6, 12)
                self.fx.play("energy")
        self.cells = [c for c in self.cells if c.alive]
        if self.boss and self.boss.alive and not self.booting:
            self.cell_timer += 1
            if self.cell_timer >= C.BOSS_CELL_RESPAWN and len(self.cells) < 2:
                self.cell_timer = 0
                spot = BOSS_CELL_SPOTS[self.rng.randrange(len(BOSS_CELL_SPOTS))]
                x, y, _, _ = self.grid.tile_rect(*spot)
                if not any(abs(c.x - x - 1) < 1 and abs(c.y - y - 1) < 1 for c in self.cells):
                    self.cells.append(Pickup(x + 1, y + 1, "cell"))

    def _update_exit(self) -> None:
        ex = self.exit
        if ex is None:
            return
        p = self.player
        if ex.state == "locked" and self.seeds_collected >= self.seeds_required:
            ex.state, ex.timer = "opening", C.EXIT_OPEN_FRAMES
            self._hint("relay")
            self.fx.play("relay")
            self.fx.particles.burst(ex.x + 4, ex.y + 4, 20, [12, 6, 7, 11], 2.0, 22)
        elif ex.state == "opening":
            ex.timer -= 1
            if ex.timer <= 0:
                ex.state = "open"
        on_exit = p.overlaps_rect(ex.x + 1, ex.y + 1, 6, 6)
        if on_exit and ex.state == "open":
            self.completed = True
            self.clear_echo()
            self.fx.play("clear")
        elif on_exit and ex.state == "locked" and self.locked_msg_cd == 0:
            left = self.seeds_required - self.seeds_collected
            self.say(f"RELAY LOCKED: {left} SEED{'S' if left != 1 else ''} LEFT", 8, 60)
            self.locked_msg_cd = C.LOCKED_MSG_COOLDOWN
            self.fx.play("deny")

    def _update_terminals(self) -> None:
        p = self.player
        current = -1
        for i, t in enumerate(self.terminals):
            if p.overlaps_rect(t.x, t.y, C.TILE, C.TILE):
                current = i
        if current != -1 and current != self.on_terminal:
            self.say(self.terminals[current].text, 11)
            self.fx.play("terminal")
        self.on_terminal = current

    # ------------------------------------------------------------------ boss
    def _boss_dur(self, base: int) -> int:
        return int(base * 0.8) if self.boss and self.boss.phase == 2 else base

    def _update_boss(self) -> None:
        b = self.boss
        assert b is not None
        if b.flash > 0:
            b.flash -= 1
        if b.state == "dead":
            return
        b.timer -= 1
        echo = self.echo if self.echo_active else None
        if b.state == "intro":
            if b.timer == C.BOSS_INTRO_FRAMES - 10:
                self.fx.play("roar")
                self.fx.camera.shake(20, 1.5)
            if b.timer <= 0:
                b.set_state("idle", 30)
        elif b.state == "idle":
            if echo and not echo.boss_locked:
                echo.boss_locked = True
                b.set_state("lock_echo", 30)
                self.fx.popups.spawn_centered("LOCKED ON ECHO", b.cx, b.cy + 22, 6, 30)
            elif b.timer <= 0:
                cycle = Boss.CYCLE_1 if b.phase == 1 else Boss.CYCLE_2
                attack = cycle[b.cycle_i % len(cycle)]
                b.cycle_i += 1
                if attack == "ring":
                    b.set_state("tele_ring", self._boss_dur(36))
                elif attack == "slam":
                    self._make_lanes()
                    b.set_state("tele_slam", self._boss_dur(42))
                elif attack == "summon":
                    b.set_state("summon", 24)
                else:
                    b.set_state("exposed", 75)
                    self.fx.popups.spawn_centered("CORE EXPOSED!", b.cx, b.cy + 22, 10, 30)
        elif b.state == "lock_echo":
            b.beam = echo.center() if echo else b.beam
            if b.timer <= 0:
                b.beam = None
                b.set_state("exposed", 120)
                self.fx.popups.spawn_centered("OVERLOAD! PULSE IT!", b.cx, b.cy + 22, 10, 36)
                self.fx.play("relay")
        elif b.state == "tele_ring":
            if b.timer <= 0:
                self._fire_ring()
                b.set_state("idle", self._boss_dur(40))
        elif b.state == "tele_slam":
            if b.timer <= 0:
                for lane in self.lanes:
                    lane.striking = True
                self.fx.camera.shake(10, 2.5)
                self.fx.play("slam")
                b.set_state("slam", 12)
        elif b.state == "slam":
            p = self.player
            for lane in self.lanes:
                if p.overlaps_rect(lane.x + 2, lane.y + 2, lane.w - 4, lane.h - 4):
                    self.damage_player(p.x + 3, lane.y)
                    break
            if b.timer <= 0:
                self.lanes.clear()
                b.set_state("idle", self._boss_dur(40))
        elif b.state == "summon":
            if b.timer <= 0:
                motes = sum(1 for d in self.drones if d.kind == "mote")
                for sx in (-34, 26):
                    if motes < C.BOSS_MAX_MOTES:
                        x, y = self.grid.find_free_near(b.cx + sx, b.cy + 20, C.DRONE_W, C.DRONE_H)
                        self.drones.append(Drone(x, y, "h", 1.0, kind="mote"))
                        motes += 1
                self.fx.particles.burst(b.cx, b.cy + 16, 16, [2, 8, 14], 2.0)
                b.set_state("idle", self._boss_dur(40))
        elif b.state == "exposed":
            if b.timer <= 0:
                b.set_state("idle", self._boss_dur(30))
        elif b.state == "stagger":
            if b.timer <= 0:
                b.set_state("idle", self._boss_dur(30))
        elif b.state == "dying":
            if b.timer % 6 == 0:
                ang = self.rng.uniform(0, math.tau)
                rr = self.rng.uniform(0, 18)
                self.fx.particles.burst(b.cx + math.cos(ang) * rr, b.cy + math.sin(ang) * rr, 14, [8, 14, 10, 7, 2], 2.2, 22)
                self.fx.camera.shake(6, 2.0)
                self.fx.play("boom")
            if b.timer == 30:
                self.fx.camera.flash(4, 7)
                self.fx.play("boss_defeat")
            if b.timer <= 0:
                b.state = "dead"
                self.victory = True

    def _make_lanes(self) -> None:
        b = self.boss
        assert b is not None
        self.lanes.clear()
        p = self.player
        pcx, pcy = p.center()
        top = C.MAP_Y + 5 * C.TILE  # below the root mass
        size = C.BOSS_LANE_SIZE
        horizontal = b.phase == 2 and b.slams % 2 == 1
        b.slams += 1
        if horizontal:
            count = 4
            mine = int(clamp((pcy - top) // size, 0, count - 1))
            others = [i for i in range(count) if i != mine]
            chosen = {mine, self.rng.choice(others)}
            for j in sorted(chosen):
                self.lanes.append(Lane(C.ARENA_X0, top + j * size, C.ARENA_X1 - C.ARENA_X0, size))
        else:
            count = 9
            mine = int(clamp((pcx - C.ARENA_X0) // size, 0, count - 1))
            others = [i for i in range(count) if i != mine]
            extra = 3 if b.phase == 2 else 2
            chosen = {mine, *self.rng.sample(others, extra)}
            for i in sorted(chosen):
                self.lanes.append(Lane(C.ARENA_X0 + i * size, top, size, C.ARENA_Y1 - top))

    def _fire_ring(self) -> None:
        b = self.boss
        assert b is not None
        n = 12 if b.phase == 1 else 16
        gap = self.rng.randrange(n)
        speed = 0.8 if b.phase == 1 else 1.0
        for k in range(n):
            if k in (gap, (gap + 1) % n):
                continue  # a guaranteed gap: the ring is always escapable
            a = b.ring_angle + k * math.tau / n
            ux, uy = math.cos(a), math.sin(a)
            self._add_spore(b.cx + ux * C.BOSS_SPORE_SPAWN_RADIUS - 2, b.cy + uy * C.BOSS_SPORE_SPAWN_RADIUS - 2,
                            ux * speed, uy * speed, grace=0)
        b.ring_angle += 0.35
        self.fx.play("spore")

    def _boss_hit(self) -> None:
        b = self.boss
        assert b is not None
        b.hp = max(0, b.hp - 1)
        b.flash = 8
        self.run.add_score(C.SCORE_BOSS_HIT)
        self.fx.camera.shake(10, 2.5)
        self.fx.particles.burst(b.cx, b.cy, 24, [10, 7, 8, 14], 2.5, 22)
        self.fx.popups.spawn_centered("CRITICAL", b.cx, b.cy + 20, 10, 30)
        self.fx.play("boss_hit")
        if b.hp <= 0:
            b.set_state("dying", C.BOSS_DYING_FRAMES)
            self.lanes.clear()
            self.spores.clear()
            self.drones = [d for d in self.drones if d.kind != "mote"]
            self.player.invuln = C.BOSS_DYING_FRAMES + 30
            self.run.add_score(C.SCORE_BOSS_DEFEAT)
            self.say("THE BLIGHT HEART IS FAILING!", 10)
        else:
            if b.hp <= C.BOSS_PHASE2_HP and b.phase == 1:
                b.phase = 2
                self.spores.clear()
                self.say("THE HEART ENRAGES!", 8)
                self.fx.play("roar")
            b.set_state("stagger", 24)

"""
ECHO//GARDEN // Headless self-test  (python main.py --self-test)
================================================================
Real checks, no window:
  1. Asset + chamber validation (sprite rows, overlaps, map reachability, text widths).
  2. Fuzz: thousands of frames of seeded random input in every chamber, checking
     invariants every frame (bounds, walls, resources, caps, valid states).
  3. Autopilot: a scripted bot plays TITLE -> VICTORY with normal damage rules,
     proving every chamber and the boss can be completed.
  4. State-machine walk: pause freeze, game over, retry, new run, restart.
  5. Render smoke: draws every screen through Pyxel's headless mode.
Returns 0 when everything passes, 1 otherwise.
"""

from __future__ import annotations

import math
import os
import random
import sys
import tempfile
from collections import deque

import config as C
from actors import DroneState
from assets import validate_sprite_defs
from game import Game, GameState
from save import HighScoreStore
from session import InputState
from world import CHAMBERS, validate_chamber, validate_upgrades

S = GameState


class Failure(Exception):
    pass


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise Failure(msg)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------
def begin(g: Game, idx: int = 0) -> Game:
    """Enter a chamber through the legal TITLE -> INTRO -> PLAYING path."""
    g.set_state(S.INTRO)
    g.start_new_run()
    if idx:
        g._load_chamber(idx)
    return g


def check_invariants(g: Game) -> None:
    check(isinstance(g.state, GameState), "invalid state")
    check(not g.invalid_transitions, f"invalid transitions {g.invalid_transitions}")
    check(len(g.particles.particles) <= C.MAX_PARTICLES, "particle cap exceeded")
    check(len(g.popups.labels) <= C.MAX_LABELS, "label cap exceeded")
    check(len(g.sfx) <= C.MAX_SFX_QUEUE, "sfx queue unbounded")
    check(0 <= g.run.score <= C.SCORE_CAP, "score out of range")
    s = g.session
    if s is None or g.state not in (S.PLAYING, S.PAUSED):
        return
    p = s.player
    check(0 <= p.hp <= p.max_hp, f"hp out of range {p.hp}")
    check(0.0 <= p.energy <= C.ENERGY_MAX, f"energy out of range {p.energy}")
    check(s.echo_cooldown >= 0 and s.pulse_lockout >= 0, "negative cooldown")
    check(C.ARENA_X0 <= p.x <= C.ARENA_X1 - p.w and C.ARENA_Y0 <= p.y <= C.ARENA_Y1 - p.h, f"player out of bounds {p.x},{p.y}")
    check(not s.grid.entity_solid(p), f"player inside wall at {p.x:.1f},{p.y:.1f}")
    check(len(s.history) <= s.stats.echo_history, "echo history unbounded")
    check(s.echo is None or s.echo.alive, "expired echo still referenced")
    check(len(s.spores) <= C.MAX_SPORES, "spore cap exceeded")
    check(len(s.drones) <= C.MAX_DRONES, "drone cap exceeded")
    check(0 <= s.seeds_collected <= s.seeds_required, "seed count out of range")
    check(s.seeds_collected + len(s.seeds) == s.seeds_required, "seed accounting broken (duplicate collect?)")
    for d in s.drones:
        check(not s.grid.entity_solid(d), f"drone inside wall at {d.x:.1f},{d.y:.1f}")
        if d.state == DroneState.CHASE_ECHO:
            check(s.echo_active, "drone chasing an echo that does not exist")
    if s.boss:
        check(0 <= s.boss.hp <= s.boss.max_hp, "boss hp out of range")


# ---------------------------------------------------------------------------
# Autopilot (test-only bot): BFS over tiles toward the next objective
# ---------------------------------------------------------------------------
class Autopilot:
    def __init__(self) -> None:
        self.path: list[tuple[int, int]] = []
        self.goal: tuple[int, int] | None = None
        self.replan = 0

    def bfs(self, s, start, goal, avoid) -> list[tuple[int, int]]:
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            x, y = cur
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                n = (nx, ny)
                if n in prev or s.grid.is_solid_tile(nx, ny) or (n in avoid and n != goal):
                    continue
                prev[n] = cur
                q.append(n)
        if goal not in prev:
            return []
        out, cur = [], goal
        while cur is not None:
            out.append(cur)
            cur = prev[cur]
        out.reverse()
        return out

    def target_tile(self, s):
        p = s.player
        pc = s.grid.tile_at(*p.center())
        if s.boss:
            b = s.boss
            if b.exposed:
                return s.grid.tile_at(b.cx, b.cy + 34)
            if s.cells and p.energy < 60:
                return min((s.grid.tile_at(*c.center()) for c in s.cells), key=lambda t: abs(t[0] - pc[0]) + abs(t[1] - pc[1]))
            return s.grid.tile_at(b.cx + (30 if (s.frame // 200) % 2 else -30), b.cy + 52)
        if s.seeds:
            return min((s.grid.tile_at(*sd.center()) for sd in s.seeds), key=lambda t: abs(t[0] - pc[0]) + abs(t[1] - pc[1]))
        if s.exit:
            return s.grid.tile_at(s.exit.x + 4, s.exit.y + 4)
        return pc

    def act(self, g: Game) -> InputState:
        inp = InputState()
        if g.state != S.PLAYING:
            if g.state == S.GAME_OVER:
                g.menu_index = 0  # retry chamber
            if g.frame % 10 == 0:
                inp.confirm = True
            return inp
        s = g.session
        p = s.player
        pcx, pcy = p.center()
        pc = s.grid.tile_at(pcx, pcy)
        goal = self.target_tile(s)
        avoid = set(s.blight)
        vt = s.vent_time()
        avoid |= {(v.tx, v.ty) for v in s.vents if v.phase(vt + 20) != "idle" or v.phase(vt) != "idle"}
        for lane in s.lanes:
            for t in s.grid.tiles_in_rect(lane.x, lane.y, lane.w, lane.h):
                avoid.add(t)
        self.replan -= 1
        if goal != self.goal or self.replan <= 0 or not self.path:
            self.goal = goal
            self.replan = 10
            self.path = self.bfs(s, pc, goal, avoid) or self.bfs(s, pc, goal, set())
        while self.path and self.path[0] == pc:
            self.path.pop(0)
        if self.path:
            tcx, tcy = s.grid.tile_center(*self.path[0])
            dx, dy = tcx - pcx, tcy - pcy
            inp.right, inp.left = dx > 0.8, dx < -0.8
            inp.down, inp.up = dy > 0.8, dy < -0.8
        threats = [d for d in s.drones if d.harmful and math.hypot(d.center()[0] - pcx, d.center()[1] - pcy) < 28]
        spores_near = [sp for sp in s.spores if math.hypot(sp.x - pcx, sp.y - pcy) < 18]
        if s.boss and s.boss.exposed and math.hypot(s.boss.cx - pcx, s.boss.cy - pcy) <= s.stats.pulse_radius + C.BOSS_HIT_RADIUS - 2:
            inp.pulse = True
        elif (threats or spores_near) and p.energy >= s.stats.pulse_cost + (25 if s.boss else 0):
            inp.pulse = True
        if s.echo_cooldown == 0 and not s.echo_active and len(s.history) >= C.ECHO_MIN_SAMPLES:
            if s.boss or any(d.state == DroneState.CHASE_PLAYER for d in s.drones):
                inp.echo = True
        return inp


# ---------------------------------------------------------------------------
# Test sections
# ---------------------------------------------------------------------------
def test_static() -> str:
    errs = validate_sprite_defs() + validate_upgrades()
    for ch in CHAMBERS:
        errs += validate_chamber(ch)
    check(not errs, "; ".join(errs))
    return f"{len(CHAMBERS)} chambers, sprites valid"


def test_fuzz() -> str:
    frames = 0
    for seed in (1, 2, 3):
        rnd = random.Random(seed)
        for idx in range(len(CHAMBERS)):
            g = begin(Game(seed=seed), idx)
            held = InputState()
            for f in range(1500):
                if f % 7 == 0:
                    held = InputState(up=rnd.random() < 0.4, down=rnd.random() < 0.4,
                                      left=rnd.random() < 0.4, right=rnd.random() < 0.4)
                inp = InputState(held.up, held.down, held.left, held.right,
                                 pulse=rnd.random() < 0.05, echo=rnd.random() < 0.05,
                                 pause=rnd.random() < 0.003, confirm=rnd.random() < 0.01)
                g.update(inp)
                frames += 1
                check_invariants(g)
                if g.state == S.PAUSED:
                    g.update(InputState(pause=True)) if g.input_lock == 0 else None
                if g.state not in (S.PLAYING, S.PAUSED):
                    g = begin(Game(seed=seed + f), idx)
    return f"{frames} random frames, invariants held"


def test_autopilot() -> str:
    results = []
    for seed in (11, 12):
        g = Game(seed=seed)
        bot = Autopilot()
        g.update(InputState(confirm=True))
        deaths = 0
        last_state = g.state
        for _ in range(60000):
            g.update(bot.act(g))
            check_invariants(g)
            if g.state == S.GAME_OVER and last_state != S.GAME_OVER:
                deaths += 1
            last_state = g.state
            if g.state == S.VICTORY:
                break
        check(g.state == S.VICTORY, f"seed {seed}: autopilot stuck in {g.state.value} chamber {g.chamber_index}")
        results.append(f"seed {seed}: {g.run.frames // C.FPS}s, {deaths} deaths, score {g.run.score}")
    return " | ".join(results)


def test_state_walk() -> str:
    g = Game(seed=5)
    check(g.state == S.TITLE, "boot state not TITLE")
    g.update(InputState(confirm=True))
    check(g.state == S.INTRO, "title did not start intro")
    g.update(InputState(quit=True))  # locked: ignored
    check(g.state == S.INTRO, "input lock failed")
    for _ in range(C.INPUT_LOCK_FRAMES):
        g.update()
    g.update(InputState(quit=True))
    check(g.state == S.PLAYING, "skip intro failed")
    for _ in range(C.INPUT_LOCK_FRAMES + 60):
        g.update(InputState(right=True))
    g.update(InputState(pause=True))
    check(g.state == S.PAUSED, "pause failed")
    s = g.session
    snap = (s.frame, s.player.x, [(d.x, d.y) for d in s.drones])
    for _ in range(90):
        g.update(InputState(right=True, echo=True, left_p=True))
    check(snap == (s.frame, s.player.x, [(d.x, d.y) for d in s.drones]), "pause did not freeze gameplay")
    g.update(InputState(pause=True))
    check(g.state == S.PLAYING, "unpause failed")
    s.player.hp = 1
    s.player.invuln = 0
    s.damage_player(0, 0)
    for _ in range(C.DEATH_FRAMES + 5):
        g.update()
    check(g.state == S.GAME_OVER, "death did not reach GAME_OVER")
    for _ in range(25):
        g.update()
    g.update(InputState(confirm=True))
    check(g.state == S.PLAYING and g.session.player.hp == g.session.player.max_hp, "retry failed")
    return "title/intro/pause/game-over/retry ok"


def test_save() -> str:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "missing", "hs.json")
        st = HighScoreStore(path)
        check(st.load() == 0, "missing file")
        check(st.save(1234) and HighScoreStore(path).load() == 1234, "round trip")
        with open(path, "w") as fh:
            fh.write("{not json")
        check(HighScoreStore(path).load() == 0, "malformed json")
        with open(path, "w") as fh:
            fh.write("")
        check(HighScoreStore(path).load() == 0, "empty file")
        bad = HighScoreStore(os.path.join(d, "hs.json", "x", "y"))
        with open(os.path.join(d, "hs.json"), "w") as fh:
            fh.write("{}")
        check(bad.save(5) is False and bad.load() == 5, "unwritable path fallback")
    return "missing/empty/malformed/unwritable handled"


def test_render() -> str:
    try:
        import pyxel

        pyxel.init(C.SCREEN_W, C.SCREEN_H, headless=True)
    except Exception as exc:  # pragma: no cover - platform dependent
        return f"SKIPPED (headless Pyxel unavailable: {exc})"
    from assets import init_assets
    from render import Renderer

    init_assets()
    r = Renderer()
    g = Game(seed=3)
    bot = Autopilot()
    seen = set()
    for _ in range(20000):
        g.update(bot.act(g) if g.state != S.TITLE else InputState(confirm=True))
        if g.state not in seen or g.frame % 37 == 0:
            r.draw(g)
            seen.add(g.state)
        if g.state == S.VICTORY and g.state_timer > 100:
            r.draw(g)
            break
    g.set_state(S.TITLE) if g.state == S.VICTORY else None
    r.draw(g)
    for state in (S.PAUSED, S.GAME_OVER):
        g2 = begin(Game(seed=4))
        if state == S.PAUSED:
            g2.set_state(S.PAUSED)
        else:
            g2.session.dead = True
            g2.update()
        r.draw(g2)
        seen.add(g2.state)
    return f"drew {len(seen)} screen states"


def run_self_test() -> int:
    sections = [
        ("static data", test_static),
        ("save robustness", test_save),
        ("state machine", test_state_walk),
        ("random fuzz", test_fuzz),
        ("autopilot run", test_autopilot),
        ("render smoke", test_render),
    ]
    failed = 0
    print("ECHO//GARDEN self-test")
    print("=" * 50)
    for name, fn in sections:
        try:
            detail = fn()
            print(f"[PASS] {name:16s} {detail}")
        except Failure as exc:
            failed += 1
            print(f"[FAIL] {name:16s} {exc}")
        except Exception as exc:  # unexpected crash is a failure too
            failed += 1
            print(f"[FAIL] {name:16s} crashed: {exc!r}")
    print("=" * 50)
    print("ALL CHECKS PASSED" if not failed else f"{failed} SECTION(S) FAILED")
    sys.stdout.flush()
    return 0 if not failed else 1

"""
ECHO//GARDEN // Renderer
========================
Reads Game state and draws it. Purely visual: nothing here changes gameplay.
Static chamber art is baked once into image bank 1; animated things draw on top.
"""

from __future__ import annotations

import math
import random

import pyxel

import config as C
from actors import DroneState
from assets import SPRITES, draw_sprite
from game import GAME_OVER_ITEMS, INTRO_PAGES, PAUSE_ITEMS, Game, GameState
from world import CHAMBERS, UPGRADES

S = GameState

# 5x5 logo glyphs, drawn at 2x scale
GLYPHS = {
    "E": ("#####", "#....", "####.", "#....", "#####"),
    "C": (".####", "#....", "#....", "#....", ".####"),
    "H": ("#...#", "#...#", "#####", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", ".###."),
    "G": (".####", "#....", "#..##", "#...#", ".###."),
    "A": (".###.", "#...#", "#####", "#...#", "#...#"),
    "R": ("####.", "#...#", "####.", "#..#.", "#...#"),
    "D": ("####.", "#...#", "#...#", "#...#", "####."),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#"),
    "/": ("....#", "...#.", "..#..", ".#...", "#...."),
}


def text_c(y: int, s: str, col: int, shadow: int | None = 0, cx: int = C.SCREEN_W // 2) -> None:
    x = cx - len(s) * 2
    if shadow is not None:
        pyxel.text(x + 1, y + 1, s, shadow)
    pyxel.text(x, y, s, col)


def panel(x: int, y: int, w: int, h: int, fill: int = 0, border: int = 5, accent: int = 12) -> None:
    pyxel.rect(x, y, w, h, fill)
    pyxel.rectb(x, y, w, h, border)
    for px, py in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
        pyxel.pset(px, py, accent)


class Renderer:
    def __init__(self) -> None:
        self.baked: str | None = None
        rnd = random.Random(7)
        self.stars = [(rnd.randrange(160), rnd.randrange(120), rnd.choice((1, 5, 6, 13))) for _ in range(60)]
        self.fx_rng = random.Random(99)

    # ------------------------------------------------------------------ dispatch
    def draw(self, g: Game) -> None:
        pyxel.pal()
        pyxel.dither(1.0)
        if g.state == S.TITLE:
            self.draw_title(g)
        elif g.state == S.INTRO:
            self.draw_intro(g)
        elif g.state in (S.PLAYING, S.PAUSED, S.LEVEL_COMPLETE):
            self.draw_world(g)
            if g.state == S.PAUSED:
                self.draw_pause(g)
            elif g.state == S.LEVEL_COMPLETE:
                self.draw_level_complete(g)
        elif g.state == S.UPGRADE:
            self.draw_upgrade(g)
        elif g.state == S.GAME_OVER:
            self.draw_game_over(g)
        elif g.state == S.VICTORY:
            self.draw_victory(g)
        if g.camera.flash_frames > 0 and g.state in (S.PLAYING, S.VICTORY):
            pyxel.dither(0.5)
            pyxel.rect(0, 0, C.SCREEN_W, C.SCREEN_H, g.camera.flash_color)
            pyxel.dither(1.0)

    # ------------------------------------------------------------------ shared bits
    def draw_starfield(self, t: int, speed: float = 0.1) -> None:
        for i, (x, y, c) in enumerate(self.stars):
            xx = int(x - t * speed * (1 + i % 3)) % 160
            if (t // 8 + i) % 17 != 0:
                pyxel.pset(xx, y, c)

    def draw_logo(self, y: int, t: int) -> None:
        word = "ECHO//GARDEN"
        scale = 2
        x0 = (C.SCREEN_W - (len(word) * 6 - 1) * scale) // 2
        glitch_row = (t // 3) % 5 if (t % 90) < 6 else -1
        row_cols = (7, 6, 6, 12, 12)
        for layer in (0, 1):
            for ci, ch in enumerate(word):
                glyph = GLYPHS[ch]
                for ry, row in enumerate(glyph):
                    shift = 2 if ry == glitch_row and layer else 0
                    for rx, cell in enumerate(row):
                        if cell != "#":
                            continue
                        px = x0 + (ci * 6 + rx) * scale + shift
                        py = y + ry * scale
                        if layer == 0:
                            pyxel.rect(px + 1, py + 2, scale, scale, 1)
                        else:
                            col = 10 if ch == "/" else (8 if shift else row_cols[ry])
                            pyxel.rect(px, py, scale, scale, col)

    def draw_k09(self, x: float, y: float, t: int, moving: bool, facing: int = 1) -> None:
        if moving:
            name = "k09_run_a" if (t // 4) % 2 == 0 else "k09_run_b"
        else:
            name = "k09_idle_a" if (t // 20) % 2 == 0 else "k09_idle_b"
        draw_sprite(name, x, y, flip_x=facing < 0)

    def draw_ghost(self, x: float, y: float, t: int, facing: int = 1, alpha: float = 0.75) -> None:
        for a, b in ((7, 6), (12, 7), (1, 12), (5, 12), (11, 6), (13, 6), (10, 7), (9, 6)):
            pyxel.pal(a, b)
        pyxel.dither(alpha if (t // 2) % 4 else alpha * 0.6)
        self.draw_k09(x, y, t, True, facing)
        pyxel.dither(1.0)
        pyxel.pal()

    # ------------------------------------------------------------------ title
    def draw_title(self, g: Game) -> None:
        t = g.frame
        pyxel.cls(0)
        self.draw_starfield(t)
        # greenhouse dome
        pyxel.circ(80, 168, 82, 1)
        pyxel.circb(80, 168, 82, 5)
        for k in range(-4, 5):
            ang = -math.pi / 2 + k * 0.28
            pyxel.line(80, 168, 80 + math.cos(ang) * 82, 168 + math.sin(ang) * 82, 5)
        pyxel.circb(80, 168, 60, 5)
        for i in range(14):  # plants inside the dome
            px = 22 + i * 9
            h = 6 + (i * 7) % 9 + int(math.sin(t * 0.05 + i) * 1.5)
            col = 3 if i % 3 else 11
            pyxel.line(px, 104, px, 104 - h, col)
            pyxel.pset(px - 1, 104 - h + 1, 11)
            pyxel.pset(px + 1, 104 - h + 2, 3)
            if i % 4 == 1:  # corruption creeping in
                pyxel.pset(px, 104 - h, 8 if (t // 10 + i) % 2 else 2)
        pyxel.rect(0, 104, 160, 16, 0)
        pyxel.line(0, 104, 160, 104, 5)
        # rising lumen motes
        for i in range(10):
            mx = (i * 37 + int(math.sin(t * 0.03 + i) * 6)) % 160
            my = 104 - ((t // 2 + i * 23) % 90)
            pyxel.pset(mx, my, 10 if i % 2 else 11)
        self.draw_logo(18, t)
        text_c(34, "T H E   L A S T   S I G N A L", 6, 1)
        # K-09 walking with its echo ghost trailing behind
        kx = (t // 2) % 200 - 20
        self.draw_ghost(kx - 22, 96, t + 6)
        self.draw_k09(kx, 96, t, True)
        if (t // 15) % 2 == 0:
            text_c(66, "PRESS ENTER TO BEGIN", 10)
        text_c(78, "SPACE PULSE   E ECHO   P PAUSE", 13, 1)
        pyxel.text(4, 110, f"[M]SOUND:{'ON ' if g.sound_on else 'OFF'} [K]SHAKE:{'ON ' if g.shake_on else 'OFF'}", 5)
        pyxel.text(112, 110, f"HI {g.high_score:06d}", 10)

    # ------------------------------------------------------------------ intro
    def draw_intro(self, g: Game) -> None:
        pyxel.cls(0)
        self.draw_starfield(g.frame, 0.05)
        title, lines = INTRO_PAGES[g.intro_page]
        panel(6, 10, 148, 98, 0, 5, 12)
        pyxel.text(12, 15, title, 12)
        pyxel.line(12, 22, 148, 22, 1)
        remaining = g.intro_chars
        for i, line in enumerate(lines):
            shown = line[: max(0, remaining)]
            remaining -= len(line)
            pyxel.text(12, 28 + i * 9, shown, 7 if g.intro_page < 2 else (10 if i % 2 == 0 else 6))
        if g.intro_page == 2:
            self.draw_k09(130, 30, g.frame, False)
            self.draw_ghost(120, 30, g.frame)
        dots = "".join("o" if i == g.intro_page else "." for i in range(len(INTRO_PAGES)))
        pyxel.text(12, 98, dots, 5)
        if (g.frame // 15) % 2 == 0:
            pyxel.text(96, 98, "ENTER >", 10)
        pyxel.text(56, 112, "ESC: SKIP", 5)

    # ------------------------------------------------------------------ world
    def bake(self, chamber) -> None:
        img = pyxel.images[1]
        st = chamber.style
        rows = chamber.rows
        img.cls(st.bg)
        for ty, row in enumerate(rows):
            for tx, ch in enumerate(row):
                x, y = tx * 8, ty * 8
                solid_below = ty + 1 < len(rows) and rows[ty + 1][tx] in "#"
                if ch == "#":
                    img.rect(x, y, 8, 8, st.wall)
                    if not solid_below and ty + 1 < len(rows):
                        img.rect(x, y + 5, 8, 3, st.wall_face)
                        img.line(x, y + 5, x + 7, y + 5, st.wall_hi)
                        img.pset(x + 2, y + 6, st.wall)
                        img.pset(x + 6, y + 6, st.wall)
                    if ty > 0 and rows[ty - 1][tx] != "#":
                        img.line(x, y, x + 7, y, st.wall_hi)
                    continue
                # floor
                img.rect(x, y, 8, 8, st.floor)
                if (tx + ty) % 2 == 0:
                    img.pset(x, y, st.floor_line)
                    img.pset(x + 7, y + 7, st.floor_line)
                if tx % 2 == 0:
                    img.line(x, y, x, y + 7, st.floor_line) if (ty % 3 == 0) else None
                if (tx * 31 + ty * 17) % 13 == 0:
                    img.pset(x + 3, y + 4, st.leaf)
                    img.pset(x + 4, y + 3, st.leaf_hi)
                if ch == "P":
                    img.rect(x, y + 3, 8, 5, 4)
                    img.line(x, y + 3, x + 7, y + 3, 15 if st.leaf != 2 else 9)
                    for k in range(4):
                        lx = x + 1 + k * 2
                        img.line(lx, y + 3, lx, y + (k % 2), st.leaf)
                        img.pset(lx, y + (k % 2), st.leaf_hi)
                    if (tx + ty) % 3 == 0:
                        img.pset(x + 4, y, 10)
                elif ch == "T":
                    img.rect(x + 1, y, 6, 8, st.tank)
                    img.line(x + 1, y, x + 1, y + 7, 7)
                    img.line(x + 6, y, x + 6, y + 7, 5)
                    img.pset(x + 3, y + (tx * 3) % 7, 7)
                elif ch == "O":
                    img.circ(x + 4, y + 4, 3, 1)
                elif ch == "V":
                    img.rect(x + 1, y + 1, 6, 6, 0)
                    for k in range(1, 7, 2):
                        img.line(x + 1, y + k, x + 6, y + k, 5)
                elif ch == "i":
                    u, v, w, h = SPRITES["terminal"]
                    img.blt(x, y, 0, u, v, w, h, 0)
                elif ch == "X":
                    img.circb(x + 4, y + 4, 3, 5)
                elif ch == "H":
                    img.rect(x, y, 8, 8, 0)
                    img.line(x, y + (tx % 4) * 2, x + 7, y + 7 - (ty % 4), 2)
                    img.pset(x + 3, y + 3, 8)
        self.baked = chamber.key

    def draw_world(self, g: Game) -> None:
        sess = g.session
        if sess is None:
            return
        ch = sess.chamber
        if self.baked != ch.key:
            self.bake(ch)
        t = sess.frame
        ox, oy = g.camera.get_offset()
        pyxel.cls(ch.style.bg)
        pyxel.camera(ox, oy)
        pyxel.blt(0, C.MAP_Y, 1, 0, 0, 160, 112)
        self.draw_ambient(ch.style, t)
        self.draw_hazards(sess, t)
        self.draw_exit(sess, t)
        for tm in sess.terminals:
            if (t // 10) % 2:
                pyxel.line(tm.x + 2, tm.y + 2, tm.x + 4, tm.y + 2, 11)
            pyxel.pset(tm.x + 2, tm.y + 3, 11)
        for i, c in enumerate(sess.cells):
            bob = math.sin(t * 0.12 + i) * 1.2
            draw_sprite("cell", c.x - 1, c.y - 1 + bob)
        for i, s in enumerate(sess.seeds):
            bob = math.sin(t * 0.1 + i * 1.7) * 1.5
            pyxel.dither(0.3)
            pyxel.circ(s.x + 3, s.y + 3 + bob, 5 + (t // 8 + i) % 2, 10)
            pyxel.dither(1.0)
            draw_sprite("seed_a" if (t // 12 + i) % 3 else "seed_b", s.x - 1, s.y - 1 + bob)
        self.draw_echo(sess, t)
        self.draw_boss(sess, t)
        for d in sess.drones:
            self.draw_drone(d, t)
        self.draw_player(sess, t)
        for s in sess.spores:
            pyxel.circ(s.x + 2, s.y + 2, 1, 14 if (t // 3) % 2 else 8)
            pyxel.pset(s.x + 2, s.y + 2, 7)
        if sess.pulse_fx:
            x, y, left = sess.pulse_fx
            r = sess.stats.pulse_radius * (1 - left / C.PULSE_VISUAL_FRAMES) + 4
            pyxel.dither(0.25)
            pyxel.circ(x, y, r, 12)
            pyxel.dither(1.0)
            pyxel.circb(x, y, r, 6)
            pyxel.circb(x, y, max(1, r - 3), 12)
        g.particles.draw()
        g.popups.draw()
        pyxel.camera()
        self.draw_hud(g)
        self.draw_bars(sess, t)
        if sess.banner > 0:
            self.draw_banner(sess)

    def draw_ambient(self, st, t: int) -> None:
        for i in range(14):
            seed = i * 53
            if st.ambient in ("bubbles", "embers", "pollen"):
                speed = 0.3 + (i % 3) * 0.15
                x = (seed + math.sin(t * 0.04 + i) * 4) % 144 + 8
                y = 112 - ((t * speed + seed) % 96)
            else:
                ang = t * 0.02 + i
                x = 80 + math.cos(ang) * (30 + i * 4)
                y = 66 + math.sin(ang * 1.3) * (20 + i * 2)
            col = st.ambient_colors[i % len(st.ambient_colors)]
            if st.ambient == "bubbles" and i % 2:
                pyxel.circb(x, y, 1, col)
            else:
                pyxel.pset(x, y, col)

    def draw_hazards(self, sess, t: int) -> None:
        for tx, ty in sess.blight:
            x, y = tx * 8, C.MAP_Y + ty * 8
            pyxel.rect(x, y, 8, 8, 2)
            wave = (t // 6 + tx + ty) % 4
            pyxel.line(x, y + 2 + wave % 2, x + 7, y + 5 - wave % 2, 8)
            pyxel.line(x + 2 + wave % 3, y, x + 5, y + 7, 8)
            pyxel.pset(x + 1 + wave, y + 1 + (wave * 3) % 6, 14)
            pyxel.pset(x + 6 - wave, y + 6 - wave, 14)
        vt = sess.vent_time()
        for v in sess.vents:
            ph = v.phase(vt)
            if ph == "warn":
                if (t // 3) % 2:
                    pyxel.rect(v.x + 2, v.y + 2, 4, 4, 9)
                pyxel.pset(v.x + 1 + (t % 6), v.y + 1, 10)
            elif ph == "active":
                pyxel.dither(0.6)
                pyxel.rect(v.x, v.y - 6, 8, 14, 9)
                pyxel.dither(1.0)
                pyxel.rect(v.x + 2, v.y - 4 + (t % 3), 4, 10, 10)
                pyxel.line(v.x + 3, v.y - 6, v.x + 4, v.y + 6, 7)
        for pod in sess.pods:
            r = 3
            if pod.telegraph:
                r = 3 + (pod.timer - (C.POD_PERIOD - C.POD_TELEGRAPH)) // 8
            body = 13 if pod.stun else 3
            pyxel.circ(pod.cx, pod.cy, r, body)
            pyxel.circb(pod.cx, pod.cy, r, 8 if pod.telegraph and (t // 2) % 2 else 2)
            pyxel.pset(pod.cx - 1, pod.cy - 1, 14 if not pod.stun else 6)
        for lane in sess.lanes:
            if lane.striking:
                pyxel.rect(lane.x, lane.y, lane.w, lane.h, 14 if t % 2 else 8)
                pyxel.rectb(lane.x, lane.y, lane.w, lane.h, 7)
            else:
                pyxel.dither(0.25 + 0.2 * ((t // 4) % 2))
                pyxel.rect(lane.x, lane.y, lane.w, lane.h, 8)
                pyxel.dither(1.0)
                pyxel.rectb(lane.x, lane.y, lane.w, lane.h, 8)
                if (t // 6) % 2:
                    pyxel.text(lane.x + lane.w // 2 - 1, lane.y + lane.h // 2 - 2, "!", 7)

    def draw_exit(self, sess, t: int) -> None:
        ex = sess.exit
        if ex is None:
            return
        cx, cy = ex.x + 4, ex.y + 4
        if ex.state == "locked":
            pyxel.circb(cx, cy, 3, 8)
            pyxel.pset(cx, cy, 8 if (t // 15) % 2 else 2)
        else:
            r = 3 + (t // 4) % 3
            pyxel.circb(cx, cy, r, 12)
            pyxel.circ(cx, cy, 2, 7)
            pyxel.dither(0.35)
            pyxel.rect(ex.x + 2, ex.y - 18, 4, 22, 6)
            pyxel.dither(1.0)
            if ex.state == "open" and (t // 10) % 2:
                pyxel.text(ex.x - 4, ex.y - 26, "EXIT", 12)

    def draw_echo(self, sess, t: int) -> None:
        if sess.echo is not None:
            echo = sess.echo
            for k in range(echo.index + 3, len(echo.path), 4):
                px, py = echo.path[k]
                pyxel.pset(px + 3, py + 3, 5)
            ex, ey = echo.pos
            facing = 1
            if echo.index + 1 < len(echo.path):
                facing = 1 if echo.path[echo.index + 1][0] >= ex else -1
            alpha = 0.8 if echo.replaying else 0.8 * echo.linger / echo.linger_max + 0.1
            self.draw_ghost(ex - 1, ey - 2, t, facing, alpha)
            if not echo.replaying or (t // 6) % 2:
                pyxel.circb(ex + 3, ey + 3, 6 + (t // 3) % 4, 6)
        elif sess.echo_cooldown == 0 and len(sess.history) >= 12:
            hist = sess.history
            for k in range(0, len(hist), 6):
                px, py = hist[k]
                pyxel.pset(px + 3, py + 5, 1 if sess.chamber.style.floor != 1 else 5)

    def draw_drone(self, d, t: int) -> None:
        if d.state == DroneState.RECOVER and (t // 2) % 2:
            return
        x, y = d.x - 1, d.y - 1
        if d.kind == "mote":
            draw_sprite("mote_a" if (t // 5) % 2 else "mote_b", x, y)
            return
        stunned = d.state in (DroneState.STUNNED, DroneState.RECOVER)
        if stunned:
            pyxel.pal(8, 13)
            pyxel.pal(14, 6)
            pyxel.pal(2, 5)
        draw_sprite("drone_a" if (t // 3) % 2 else "drone_b", x, y + math.sin(t * 0.2 + d.uid) * 0.8, d.flip_x)
        pyxel.pal()
        if d.state == DroneState.STUNNED:
            for k in range(2):
                a = t * 0.3 + k * math.pi
                pyxel.pset(x + 4 + math.cos(a) * 5, y - 1 + math.sin(a) * 2, 10)
        elif d.state == DroneState.CHASE_PLAYER and (d.alert > 0 or (t // 8) % 2):
            pyxel.text(x + 3, y - 7, "!", 8)
        elif d.state == DroneState.CHASE_ECHO:
            pyxel.text(x + 2, y - 7, "?", 6)

    def draw_player(self, sess, t: int) -> None:
        p = sess.player
        if p.dying:
            if p.dying > 20:
                draw_sprite("k09_hurt", p.x - 1 + self.fx_rng.choice((-1, 0, 1)), p.y - 2)
            return
        if sess.dead:
            return
        if p.invuln > 0 and (t // 2) % 2:
            return
        if p.invuln > C.INVULN_FRAMES - 6:
            draw_sprite("k09_hurt", p.x - 1, p.y - 2, p.facing < 0)
        else:
            self.draw_k09(p.x - 1, p.y - 2, t, p.moving, p.facing)

    def draw_boss(self, sess, t: int) -> None:
        b = sess.boss
        if b is None or b.state == "dead":
            return
        cx, cy = b.cx, b.cy
        if b.state == "dying":
            cx += self.fx_rng.uniform(-2, 2)
            cy += self.fx_rng.uniform(-2, 2)
        rising = 1.0
        if b.state == "intro":
            rising = 1 - b.timer / C.BOSS_INTRO_FRAMES
        speed = 0.12 if b.phase == 1 else 0.2
        # tendrils
        for k in range(8):
            a = k * math.tau / 8 + math.sin(t * 0.03 + k) * 0.2
            length = (22 + 6 * math.sin(t * speed + k)) * rising
            mx = cx + math.cos(a) * length * 0.5 + math.sin(t * 0.1 + k) * 2
            my = cy + math.sin(a) * length * 0.5
            ex, ey = cx + math.cos(a) * length, cy + math.sin(a) * length
            pyxel.line(cx, cy, mx, my, 2)
            pyxel.line(mx, my, ex, ey, 8 if k % 2 else 2)
        pulse = math.sin(t * speed) * 1.5
        body_r = (14 + pulse) * rising
        flash = b.flash > 0 and b.flash % 2
        pyxel.circ(cx, cy, body_r, 7 if flash else 2)
        pyxel.circ(cx, cy, body_r - 3, 7 if flash else (14 if b.phase == 2 else 8))
        if b.exposed or b.state in ("dying",):
            pyxel.circ(cx, cy, 6, 10)
            pyxel.circ(cx, cy, 3, 7)
            pyxel.circb(cx, cy, 8 + (t // 3) % 3, 10)
        else:
            for k in range(5):  # closed shell petals
                a = k * math.tau / 5 + t * 0.01
                pyxel.tri(cx, cy, cx + math.cos(a) * 9, cy + math.sin(a) * 9,
                          cx + math.cos(a + 0.9) * 9, cy + math.sin(a + 0.9) * 9, 4)
            pyxel.circ(cx, cy, 2, 8)
        if b.state in ("tele_ring", "tele_slam") and (t // 3) % 2:
            pyxel.circb(cx, cy, body_r + 4, 7)
        if b.state == "lock_echo" and b.beam:
            bx, by = b.beam
            pyxel.line(cx, cy, bx, by, 6 if t % 2 else 7)
            pyxel.circb(bx, by, 4 + t % 3, 6)

    # ------------------------------------------------------------------ HUD
    def draw_hud(self, g: Game) -> None:
        sess = g.session
        if sess is None:
            return
        p = sess.player
        t = sess.frame
        pyxel.rect(0, 0, 160, 8, 0)
        pyxel.line(0, 7, 159, 7, 1)
        for i in range(p.max_hp):
            draw_sprite("heart" if i < p.hp else "heart_empty", 1 + i * 7, 0)
        draw_sprite("icon_bolt", 43, 0)
        pyxel.rect(51, 2, 24, 4, 1)
        cost = sess.stats.pulse_cost
        enough = p.energy >= cost
        fill = int(24 * p.energy / C.ENERGY_MAX)
        pyxel.rect(51, 2, fill, 4, 10 if enough else (8 if (t // 6) % 2 else 2))
        mark = 51 + int(24 * cost / C.ENERGY_MAX)
        pyxel.line(mark, 1, mark, 6, 7)
        ready = sess.echo_cooldown == 0 and not sess.echo_active
        if ready and (t // 10) % 2:
            pyxel.pal(6, 7)
        draw_sprite("icon_echo", 78, 0)
        pyxel.pal()
        pyxel.rect(86, 2, 14, 4, 1)
        if sess.echo_active:
            pyxel.rect(86, 2, 14, 4, 6 if (t // 4) % 2 else 12)
        else:
            cd = sess.stats.echo_cooldown
            prog = 1 - sess.echo_cooldown / cd if cd > 0 else 1
            pyxel.rect(86, 2, int(14 * prog), 4, 6 if ready else 5)
        if sess.chamber.is_boss:
            pyxel.text(103, 1, "CORE", 8)
        else:
            draw_sprite("seed_a", 102, 0)
            pyxel.text(110, 1, f"{sess.seeds_collected}/{sess.seeds_required}", 10)
        pyxel.text(131, 1, f"{g.run.score:07d}", 7)

    def draw_bars(self, sess, t: int) -> None:
        b = sess.boss
        if b is not None and b.state != "intro":
            pyxel.rect(0, C.TOP_BAR_Y, 160, 8, 0)
            pyxel.text(3, C.TOP_BAR_Y + 1, "BLIGHT HEART", 8)
            seg = 100 // b.max_hp
            for i in range(b.max_hp):
                x = 54 + i * seg
                col = (14 if b.phase == 2 else 8) if i < b.hp else 1
                pyxel.rect(x, C.TOP_BAR_Y + 2, seg - 2, 4, 7 if b.flash and i == b.hp else col)
            if b.exposed and (t // 4) % 2:
                pyxel.rectb(52, C.TOP_BAR_Y + 1, 104, 6, 10)
        if sess.message:
            m = sess.message
            pyxel.rect(0, C.BOTTOM_BAR_Y, 160, 8, 0)
            pyxel.line(0, C.BOTTOM_BAR_Y, 159, C.BOTTOM_BAR_Y, m.color)
            text_c(C.BOTTOM_BAR_Y + 2, m.text, m.color, None)

    def draw_banner(self, sess) -> None:
        f = sess.banner
        slide = 0
        if f > C.BANNER_FRAMES - 10:
            slide = (f - (C.BANNER_FRAMES - 10)) * 16
        elif f < 10:
            slide = -(10 - f) * 16
        x = 20 + slide
        panel(x, 44, 120, 30, 0, sess.chamber.style.accent, 7)
        text_c(49, sess.chamber.label, 6, None, x + 60)
        text_c(58, sess.chamber.name, 10, 1, x + 60)
        text_c(67, "- - -", 5, None, x + 60)

    # ------------------------------------------------------------------ overlays
    def _dim(self) -> None:
        pyxel.dither(0.5)
        pyxel.rect(0, 0, 160, 120, 0)
        pyxel.dither(1.0)

    def draw_pause(self, g: Game) -> None:
        self._dim()
        panel(36, 26, 88, 70, 0, 12, 10)
        text_c(31, "PAUSED", 10)
        text_c(40, g.chamber.name, 5, None)
        for i, item in enumerate(PAUSE_ITEMS):
            label = item
            if item == "SOUND":
                label = f"SOUND: {'ON' if g.sound_on else 'OFF'}"
            elif item == "SHAKE":
                label = f"SHAKE: {'ON' if g.shake_on else 'OFF'}"
            sel = i == g.menu_index
            text_c(52 + i * 8, ("> " + label + " <") if sel else label, 7 if sel else 13, None)

    def draw_level_complete(self, g: Game) -> None:
        self._dim()
        panel(20, 22, 120, 78, 0, 11, 10)
        text_c(28, "CHAMBER CLEARED", 11)
        text_c(37, g.chamber.name, 10, None)
        shown = min(len(g.tally), g.state_timer // 8)
        for i in range(shown):
            label, pts = g.tally[i]
            pyxel.text(28, 49 + i * 9, label, 7 if pts else 5)
            pyxel.text(104, 49 + i * 9, f"+{pts:5d}", 10 if pts else 5)
        if g.state_timer > 30:
            pyxel.text(28, 86, f"SCORE {g.run.score:07d}", 7)
            if (g.frame // 15) % 2:
                text_c(93, "ENTER: CONTINUE", 12, None)

    def draw_upgrade(self, g: Game) -> None:
        pyxel.cls(0)
        self.draw_starfield(g.frame, 0.05)
        text_c(8, "SYSTEM UPGRADE", 10, 1)
        text_c(18, "CHOOSE ONE MODULE", 6, None)
        n = len(g.upgrade_choices)
        for i, key in enumerate(g.upgrade_choices):
            up = UPGRADES[key]
            tier = g.run.upgrades.get(key, 0) + 1
            sel = i == g.upgrade_index
            x = 4 + i * 52 + (52 * (3 - n)) // 2
            y = 30 - (3 if sel else 0)
            panel(x, y, 48, 66, 1 if sel else 0, 10 if sel else 5, 7 if sel else 5)
            draw_sprite(up.icon, x + 20, y + 6)
            for j, line in enumerate(up.name):
                text_c(y + 18 + j * 7, line, 7 if sel else 13, None, x + 24)
            text_c(y + 34, "MK " + "I" * tier, 10 if sel else 5, None, x + 24)
            for j, line in enumerate(up.desc):
                text_c(y + 45 + j * 7, line, 6 if sel else 5, None, x + 24)
        text_c(102, "LEFT/RIGHT CHOOSE   ENTER INSTALL", 13, None)
        nxt = CHAMBERS[min(g.chamber_index + 1, len(CHAMBERS) - 1)]
        text_c(111, f"NEXT: {nxt.name}", 5, None)

    def draw_game_over(self, g: Game) -> None:
        t = g.state_timer
        pyxel.cls(0)
        for _ in range(60):
            pyxel.pset(self.fx_rng.randrange(160), self.fx_rng.randrange(120), self.fx_rng.choice((1, 5, 2)))
        y = 20 + (self.fx_rng.choice((-1, 0, 1)) if t % 20 < 3 else 0)
        text_c(y, "SIGNAL LOST", 8, 2)
        draw_sprite("k09_hurt", 76, 32)
        text_c(46, f"SCORE {g.run.score:07d}", 7, None)
        text_c(54, ("NEW HIGH SCORE!" if g.new_record else f"HI {g.high_score:07d}"),
               10 if g.new_record else 5, None)
        for i, item in enumerate(GAME_OVER_ITEMS):
            sel = i == g.menu_index
            text_c(70 + i * 10, ("> " + item + " <") if sel else item, 7 if sel else 13, None)
        text_c(108, "THE GARDEN STILL WAITS, K-09.", 5, None)

    def draw_victory(self, g: Game) -> None:
        t = g.state_timer
        pyxel.cls(1)
        self.draw_starfield(t, 0.05)
        grow = min(1.0, t / 120)
        for i in range(20):  # the garden regrows
            px = 4 + i * 8
            h = int((10 + (i * 13) % 22) * grow)
            pyxel.line(px, 112, px, 112 - h, 3)
            if h > 4:
                pyxel.pset(px - 1, 112 - h + 2, 11)
                pyxel.pset(px + 1, 112 - h + 4, 11)
                pyxel.circ(px, 112 - h, 1, (10, 14, 6, 15)[i % 4])
        pyxel.rect(0, 112, 160, 8, 3)
        glow = 8 + int(math.sin(t * 0.1) * 2)
        pyxel.dither(0.3)
        pyxel.circ(80, 52, glow + 6, 10)
        pyxel.dither(1.0)
        pyxel.circ(80, 52, 6, 10)
        pyxel.circ(80, 52, 3, 7)
        for i in range(12):
            mx = (i * 29 + int(math.sin(t * 0.05 + i) * 8)) % 160
            my = 112 - ((t + i * 17) % 100)
            pyxel.pset(mx, my, 10 if i % 2 else 11)
        self.draw_k09(76, 100, t, False)
        text_c(10, "SIGNAL RESTORED", 10, 1)
        if t > 30:
            text_c(20, "THE GARDEN BREATHES AGAIN", 11, None)
        if t > 60:
            pyxel.text(28, 66, f"SCORE  {g.run.score:07d}", 7)
            pyxel.text(28, 74, f"SEEDS  {g.run.seeds:3d}   HITS {g.run.hits_taken:3d}", 6)
            secs = g.run.frames // C.FPS
            pyxel.text(28, 82, f"TIME   {secs // 60}:{secs % 60:02d}", 6)
            if g.new_record and (t // 10) % 2:
                text_c(90, "NEW HIGH SCORE!", 10, None)
        if t > 90 and (t // 15) % 2:
            text_c(32, "ENTER: RETURN TO TITLE", 12, None)

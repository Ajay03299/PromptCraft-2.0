"""
ECHO//GARDEN // Game state machine
==================================
TITLE -> INTRO -> PLAYING <-> PAUSED
PLAYING -> LEVEL_COMPLETE -> UPGRADE -> PLAYING (next chamber)
PLAYING -> GAME_OVER -> PLAYING (retry / new run) | TITLE
PLAYING (boss destroyed) -> VICTORY -> TITLE

Game owns the run (score, upgrades, HP) and the menus; ChamberSession owns the
moment-to-moment gameplay. No Pyxel calls happen here.
"""

from __future__ import annotations

import random
from enum import Enum

import config as C
from engine import Camera, FloatingTextManager, ParticleSystem
from save import HighScoreStore
from session import ChamberSession, Effects, InputState, RunState
from world import CHAMBERS, UPGRADE_MAX_TIER, UPGRADES, derive_stats


class GameState(str, Enum):
    TITLE = "TITLE"
    INTRO = "INTRO"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    LEVEL_COMPLETE = "LEVEL_COMPLETE"
    UPGRADE = "UPGRADE"
    GAME_OVER = "GAME_OVER"
    VICTORY = "VICTORY"


S = GameState
TRANSITIONS: dict[GameState, set[GameState]] = {
    S.TITLE: {S.INTRO},
    S.INTRO: {S.PLAYING, S.TITLE},
    S.PLAYING: {S.PAUSED, S.LEVEL_COMPLETE, S.GAME_OVER, S.VICTORY},
    S.PAUSED: {S.PLAYING, S.TITLE},
    S.LEVEL_COMPLETE: {S.UPGRADE, S.PLAYING},
    S.UPGRADE: {S.PLAYING},
    S.GAME_OVER: {S.PLAYING, S.TITLE},
    S.VICTORY: {S.TITLE},
}

PAUSE_ITEMS = ("RESUME", "SOUND", "SHAKE", "CRT FILTER", "RESTART CHAMBER", "QUIT TO TITLE")
GAME_OVER_ITEMS = ("RETRY CHAMBER", "NEW RUN", "TITLE")

INTRO_PAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ARCHIVE // TRANSMISSION", (
        "ECHO//GARDEN: ORBITAL GREENHOUSE.",
        "IT GREW THE LIFE THAT HEALS WORLDS.",
        "",
        "THEN THE NETWORK WENT SILENT.",
        "THE MAINTENANCE SWARM TURNED.",
        "THE GARDEN IS DYING.",
    )),
    ("UNIT K-09 // ONLINE", (
        "YOU ARE THE LAST MAINTENANCE UNIT.",
        "",
        "RECOVER THE LUMEN SEEDS.",
        "WAKE EACH EXIT RELAY.",
        "FIND THE CORRUPTION AT THE CORE",
        "AND RESTORE THE GARDEN HEART.",
    )),
    ("FIELD MANUAL", (
        "WASD/ARROWS  MOVE",
        "SPACE        PULSE: STUN + PURGE",
        "E / X        ECHO: DECOY REWINDS",
        "             YOUR LAST 3 SECONDS",
        "P / ESC      PAUSE",
        "M SOUND  K SHAKE  C CRT FILTER",
    )),
)


class Game:
    def __init__(self, seed: int | None = None, store: HighScoreStore | None = None) -> None:
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        fx_rng = random.Random(self.seed ^ 0x5EED)
        self.fx = Effects(ParticleSystem(C.MAX_PARTICLES, fx_rng), FloatingTextManager(C.MAX_LABELS),
                          Camera(random.Random(self.seed ^ 0xCA3)))
        self.store = store or HighScoreStore(None)
        self.high_score = self.store.load()
        self.sound_on = True
        self.shake_on = True
        self.crt_on = False
        self.state = S.TITLE
        self.state_timer = 0
        self.frame = 0
        self.input_lock = 0
        self.quit_requested = False
        self.invalid_transitions: list[tuple[str, str]] = []
        self.run = RunState()
        self.checkpoint = RunState()
        self.session: ChamberSession | None = None
        self.chamber_index = 0
        self.menu_index = 0
        self.intro_page = 0
        self.intro_chars = 0
        self.upgrade_choices: list[str] = []
        self.upgrade_index = 0
        self.tally: list[tuple[str, int]] = []
        self.new_record = False

    # ------------------------------------------------------------------ plumbing
    @property
    def sfx(self) -> list[str]:
        return self.fx.sfx

    @property
    def particles(self) -> ParticleSystem:
        return self.fx.particles

    @property
    def popups(self) -> FloatingTextManager:
        return self.fx.popups

    @property
    def camera(self) -> Camera:
        return self.fx.camera

    def set_state(self, new: GameState) -> bool:
        if new not in TRANSITIONS[self.state]:
            self.invalid_transitions.append((self.state.value, new.value))
            return False
        self.state = new
        self.state_timer = 0
        self.menu_index = 0
        self.input_lock = C.INPUT_LOCK_FRAMES
        return True

    @property
    def music(self) -> str | None:
        if self.state in (S.TITLE, S.INTRO, S.UPGRADE):
            return "title"
        if self.state in (S.PLAYING, S.PAUSED) and self.session:
            return self.session.chamber.music
        if self.state == S.VICTORY:
            return "victory"
        return None

    @property
    def chamber(self):
        return CHAMBERS[self.chamber_index]

    # ------------------------------------------------------------------ update
    def update(self, inp: InputState | None = None) -> None:
        inp = inp or InputState()
        self.frame += 1
        self.state_timer += 1
        if inp.mute:
            self.sound_on = not self.sound_on
        if inp.shake:
            self.shake_on = not self.shake_on
        if inp.crt:
            self.crt_on = not self.crt_on
        self.fx.camera.enabled = self.shake_on
        if self.input_lock > 0:
            self.input_lock -= 1
            inp = inp.holds_only()
        handler = {
            S.TITLE: self._update_title,
            S.INTRO: self._update_intro,
            S.PLAYING: self._update_playing,
            S.PAUSED: self._update_paused,
            S.LEVEL_COMPLETE: self._update_level_complete,
            S.UPGRADE: self._update_upgrade,
            S.GAME_OVER: self._update_game_over,
            S.VICTORY: self._update_victory,
        }[self.state]
        handler(inp)
        if self.state != S.PAUSED:
            self.fx.particles.update(gravity=0.0)
            self.fx.popups.update()
            self.fx.camera.update()

    def _update_title(self, inp: InputState) -> None:
        if inp.quit:
            self.quit_requested = True
        elif inp.confirm or inp.pulse:
            self.fx.play("start")
            self.intro_page = 0
            self.intro_chars = 0
            self.set_state(S.INTRO)

    def _update_intro(self, inp: InputState) -> None:
        total = sum(len(line) for line in INTRO_PAGES[self.intro_page][1])
        self.intro_chars = min(total, self.intro_chars + 2)
        if inp.quit:
            self.start_new_run()
        elif inp.confirm or inp.pulse:
            if self.intro_chars < total:
                self.intro_chars = total
            elif self.intro_page < len(INTRO_PAGES) - 1:
                self.intro_page += 1
                self.intro_chars = 0
                self.fx.play("select")
            else:
                self.start_new_run()

    def _update_playing(self, inp: InputState) -> None:
        sess = self.session
        if sess is None:
            return
        if inp.pause:
            self.fx.play("select")
            self.set_state(S.PAUSED)
            return
        sess.update(inp)
        if sess.dead:
            self._finish_run_scoring()
            self.fx.play("game_over")
            self.set_state(S.GAME_OVER)
        elif sess.victory:
            self._finish_run_scoring()
            self.fx.play("victory")
            self.set_state(S.VICTORY)
        elif sess.completed:
            self._complete_chamber()

    def _update_paused(self, inp: InputState) -> None:
        if inp.pause:
            self.set_state(S.PLAYING)
            return
        self._menu_nav(inp, len(PAUSE_ITEMS))
        if inp.confirm or inp.pulse:
            item = PAUSE_ITEMS[self.menu_index]
            if item == "RESUME":
                self.set_state(S.PLAYING)
            elif item == "SOUND":
                self.sound_on = not self.sound_on
            elif item == "SHAKE":
                self.shake_on = not self.shake_on
            elif item == "CRT FILTER":
                self.crt_on = not self.crt_on
            elif item == "RESTART CHAMBER":
                self.retry_chamber()
            elif item == "QUIT TO TITLE":
                self.return_to_title()

    def _update_level_complete(self, inp: InputState) -> None:
        if self.state_timer > 30 and (inp.confirm or inp.pulse):
            self.fx.play("select")
            self._begin_upgrades()

    def _update_upgrade(self, inp: InputState) -> None:
        n = len(self.upgrade_choices)
        if n == 0:
            self._advance_chamber()
            return
        if inp.left_p or inp.up_p:
            self.upgrade_index = (self.upgrade_index - 1) % n
            self.fx.play("select")
        if inp.right_p or inp.down_p:
            self.upgrade_index = (self.upgrade_index + 1) % n
            self.fx.play("select")
        if inp.confirm or inp.pulse:
            self.apply_upgrade(self.upgrade_choices[self.upgrade_index])
            self.fx.play("upgrade")
            self._advance_chamber()

    def _update_game_over(self, inp: InputState) -> None:
        self._menu_nav(inp, len(GAME_OVER_ITEMS))
        if self.state_timer > 20 and (inp.confirm or inp.pulse):
            item = GAME_OVER_ITEMS[self.menu_index]
            if item == "RETRY CHAMBER":
                self.retry_chamber()
            elif item == "NEW RUN":
                self.start_new_run()
            else:
                self.return_to_title()

    def _update_victory(self, inp: InputState) -> None:
        if self.state_timer > 90 and (inp.confirm or inp.pulse):
            self.return_to_title()

    def _menu_nav(self, inp: InputState, n: int) -> None:
        if inp.up_p:
            self.menu_index = (self.menu_index - 1) % n
            self.fx.play("select")
        if inp.down_p:
            self.menu_index = (self.menu_index + 1) % n
            self.fx.play("select")

    # ------------------------------------------------------------------ run management
    def start_new_run(self) -> None:
        self.run = RunState()
        self.new_record = False
        self.chamber_index = 0
        self._load_chamber(0)

    def _load_chamber(self, index: int) -> None:
        self.chamber_index = max(0, min(index, len(CHAMBERS) - 1))
        stats = derive_stats(self.run.upgrades)
        self.run.hp = max(1, min(self.run.hp, stats.max_hp))
        self.checkpoint = self.run.copy()
        self.fx.particles.clear()
        self.fx.popups.clear()
        self.fx.camera.reset()
        self.session = ChamberSession(CHAMBERS[self.chamber_index], self.run, stats, self.fx, self.rng)
        if self.state != S.PLAYING:
            self.set_state(S.PLAYING)

    def retry_chamber(self) -> None:
        self.run = self.checkpoint.copy()
        self.run.hp = derive_stats(self.run.upgrades).max_hp
        self._load_chamber(self.chamber_index)

    def return_to_title(self) -> None:
        self.session = None
        self.fx.particles.clear()
        self.fx.popups.clear()
        self.set_state(S.TITLE)

    def _complete_chamber(self) -> None:
        sess = self.session
        assert sess is not None
        secs = sess.frame // C.FPS
        time_bonus = max(0, C.SCORE_TIME_BASE - secs * C.SCORE_TIME_PER_SEC)
        no_dmg = C.SCORE_NO_DAMAGE if sess.damage_here == 0 else 0
        self.tally = [
            ("SEEDS RECOVERED", sess.seeds_collected * C.SCORE_SEED),
            ("RELAY BONUS", C.SCORE_CHAMBER),
            (f"TIME {secs // 60}:{secs % 60:02d}", time_bonus),
            ("FLAWLESS", no_dmg),
        ]
        self.run.add_score(C.SCORE_CHAMBER + time_bonus + no_dmg)
        self.set_state(S.LEVEL_COMPLETE)

    def _begin_upgrades(self) -> None:
        available = [k for k in UPGRADES if self.run.upgrades.get(k, 0) < UPGRADE_MAX_TIER]
        self.rng.shuffle(available)
        self.upgrade_choices = available[:3]
        self.upgrade_index = 0
        self.set_state(S.UPGRADE)

    def apply_upgrade(self, key: str) -> None:
        if key not in UPGRADES or self.run.upgrades.get(key, 0) >= UPGRADE_MAX_TIER:
            return
        self.run.upgrades[key] = self.run.upgrades.get(key, 0) + 1
        stats = derive_stats(self.run.upgrades)
        if key == "shell":
            self.run.hp = stats.max_hp

    def _advance_chamber(self) -> None:
        stats = derive_stats(self.run.upgrades)
        self.run.hp = min(stats.max_hp, self.run.hp + 1)  # field repair between chambers
        self._load_chamber(self.chamber_index + 1)

    def _finish_run_scoring(self) -> None:
        self.new_record = False  # judged per ending: a retry must not inherit an old record flag
        if self.run.score > self.high_score:
            self.high_score = self.run.score
            self.new_record = True
            self.store.save(self.run.score)

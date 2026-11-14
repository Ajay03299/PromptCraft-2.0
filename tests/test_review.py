"""Adversarial regression tests added during the independent review pass."""

import os
import random
import tempfile
import unittest

from tests.helpers import LOCK, clear_room, playing, tick
import config as C
from actors import Drone, DroneState, Lane, Spore
from game import PAUSE_ITEMS, Game, GameState
from save import HighScoreStore
from session import InputState
from world import CHAMBERS, UPGRADE_MAX_TIER, derive_stats

S = GameState


def walk(s, frames=40):
    for i in range(frames):
        s._update_player(InputState(right=i % 40 < 20, left=i % 40 >= 20))


class TestReviewFixes(unittest.TestCase):
    def test_new_record_not_inherited_after_retry(self):
        g = playing()
        g.high_score = 0
        g.run.score = 500
        g.session.dead = True
        tick(g)
        self.assertTrue(g.new_record)
        g.retry_chamber()
        g.run.score = 100  # below the record just set
        g._finish_run_scoring()
        self.assertFalse(g.new_record)

    def test_echo_ready_feedback(self):
        s = playing().session
        clear_room(s)
        walk(s)
        s.try_echo()
        s.echo_cooldown = 1
        s._update_abilities(InputState())
        self.assertEqual(s.echo_cooldown, 0)
        self.assertTrue(any(lbl.text == "ECHO READY" for lbl in s.fx.popups.labels))

    def test_toggles_work_in_any_state(self):
        g = Game(seed=1)
        for flag, key in (("sound_on", "mute"), ("shake_on", "shake"), ("crt_on", "crt")):
            before = getattr(g, flag)
            tick(g, **{key: True})
            self.assertNotEqual(getattr(g, flag), before)
        self.assertFalse(g.camera.enabled)  # shake toggle reaches the camera
        self.assertTrue(g.crt_on)  # CRT starts off, so one toggle turns it on


class TestAbuse(unittest.TestCase):
    def test_repeated_upgrade_activation_capped(self):
        g = playing()
        for _ in range(10):
            g.apply_upgrade("shell")
            g.apply_upgrade("nonsense")
        self.assertEqual(g.run.upgrades, {"shell": UPGRADE_MAX_TIER})
        self.assertEqual(derive_stats(g.run.upgrades).max_hp, C.PLAYER_BASE_HP + UPGRADE_MAX_TIER)
        self.assertLessEqual(derive_stats({"shell": 99}).max_hp, C.PLAYER_HP_CAP)

    def test_rapid_room_transitions_leave_no_stale_state(self):
        g = playing()
        for i in range(40):
            walk(g.session, 15)
            g.session.try_echo()
            g.session.spores.append(Spore(50, 50, 1, 0))
            g._load_chamber(i % len(CHAMBERS))
            s = g.session
            self.assertIsNone(s.echo)
            self.assertEqual((s.echo_cooldown, len(s.spores), len(s.lanes)), (0, 0, 0))
            self.assertEqual(len(g.particles.particles), 0)
            self.assertFalse(s.grid.entity_solid(s.player))

    def test_death_during_active_echo_and_pulse(self):
        g = playing()
        s = g.session
        clear_room(s)
        walk(s)
        s.drones = [Drone(s.player.x + 30, s.player.y)]
        s.player.energy = C.ENERGY_MAX
        s.try_echo()
        s.try_pulse()
        s.player.hp = 1
        s.damage_player(0, 0)
        self.assertIsNone(s.echo)
        self.assertTrue(all(d.state != DroneState.CHASE_ECHO for d in s.drones))
        tick(g, C.DEATH_FRAMES + 3, pulse=True, echo=True)
        self.assertEqual(g.state, S.GAME_OVER)

    def test_restart_from_every_menu_state(self):
        g = playing()
        tick(g, LOCK)
        tick(g, pause=True)
        g.menu_index = PAUSE_ITEMS.index("RESTART CHAMBER")
        tick(g, LOCK)
        tick(g, confirm=True)
        self.assertEqual(g.state, S.PLAYING)
        tick(g, LOCK)
        tick(g, pause=True)
        g.menu_index = PAUSE_ITEMS.index("QUIT TO TITLE")
        tick(g, LOCK)
        tick(g, confirm=True)
        self.assertEqual(g.state, S.TITLE)
        self.assertIsNone(g.session)
        self.assertEqual(g.invalid_transitions, [])

    def test_boss_defeat_during_simultaneous_attacks(self):
        g = playing(3)
        s = g.session
        b = s.boss
        b.hp = 1
        s.lanes = [Lane(8, 48, 16, 64)]
        s.lanes[0].striking = True
        for _ in range(10):
            s.spores.append(Spore(80, 80, 0, 0.5))
        s.drones.append(Drone(30, 70, kind="mote"))
        walk(s)
        s.try_echo()
        b.set_state("exposed", 40)
        s.player.x, s.player.y = b.cx - 3, b.cy + 30
        s.player.energy = C.ENERGY_MAX
        s.try_pulse()
        self.assertEqual(b.state, "dying")
        self.assertEqual((len(s.lanes), len(s.spores)), (0, 0))
        self.assertFalse(any(d.kind == "mote" for d in s.drones))
        hp = s.player.hp
        tick(g, C.BOSS_DYING_FRAMES + 2)
        self.assertEqual(s.player.hp, hp)
        self.assertEqual(g.state, S.VICTORY)

    def test_zero_and_max_energy_bounds(self):
        g = playing()
        s = g.session
        s.player.energy = 0
        tick(g, 1, pulse=True)
        self.assertGreaterEqual(s.player.energy, 0)
        s.player.energy = C.ENERGY_MAX
        for seed in s.seeds:
            seed.x, seed.y = s.player.x, s.player.y
        s._update_pickups()
        self.assertLessEqual(s.player.energy, C.ENERGY_MAX)

    def test_long_boss_session_stays_bounded(self):
        g = playing(3)
        rnd = random.Random(9)
        for f in range(6000):
            s = g.session
            s.player.invuln = 5  # immortal: we are stress-testing accumulation
            g.update(InputState(left=rnd.random() < .5, right=rnd.random() < .5, up=rnd.random() < .5,
                                down=rnd.random() < .5, pulse=rnd.random() < .1, echo=rnd.random() < .1))
            self.assertLessEqual(len(s.spores), C.MAX_SPORES)
            self.assertLessEqual(len(s.drones), C.MAX_DRONES)
            self.assertLessEqual(len(g.particles.particles), C.MAX_PARTICLES)
            self.assertLessEqual(len(s.cells), C.BOSS_MAX_CELLS + 1)
            self.assertFalse(s.grid.entity_solid(s.player))
            if g.state != S.PLAYING:
                break

    def test_corner_wiggle_never_sticks(self):
        s = playing().session
        clear_room(s)
        rnd = random.Random(4)
        for _ in range(3000):
            keys = {k: rnd.random() < 0.5 for k in ("up", "down", "left", "right")}
            s._update_player(InputState(**keys))
            self.assertFalse(s.grid.entity_solid(s.player))

    def test_save_permission_denied_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hs.json")
            os.mkdir(path)  # a directory where the file should be: unreadable + unwritable as a file
            st = HighScoreStore(path)
            self.assertEqual(st.load(), 0)
            self.assertFalse(st.save(77))
            self.assertEqual(st.load(), 77)


class TestEchoCollapseAndSprouts(unittest.TestCase):
    def test_collapse_stuns_lured_drones_only(self):
        s = playing().session
        clear_room(s)
        walk(s)
        s.try_echo()
        ex, ey = s.echo.path[-1]
        near = Drone(ex, ey)
        far = Drone(ex + 60 if ex < 90 else ex - 60, ey)
        s.drones = [near, far]
        for _ in range(len(s.echo.path) + C.ECHO_LINGER + 2):
            s._update_echo()
        self.assertIsNone(s.echo)
        self.assertEqual(near.state, DroneState.STUNNED)
        self.assertNotEqual(far.state, DroneState.STUNNED)

    def test_no_collapse_when_echo_cleared_by_death(self):
        s = playing().session
        clear_room(s)
        walk(s)
        s.try_echo()
        ex, ey = s.echo.pos
        d = Drone(ex, ey)
        s.drones = [d]
        s.player.hp = 1
        s.damage_player(0, 0)
        self.assertNotEqual(d.state, DroneState.STUNNED)
        self.assertIsNone(s.collapse_fx)

    def test_each_seed_plants_one_sprout(self):
        s = playing().session
        clear_room(s)
        for seed in s.seeds:
            seed.x, seed.y = s.player.x, s.player.y
        n = len(s.seeds)
        s._update_pickups()
        s._update_pickups()
        self.assertEqual(len(s.sprouts), n)


if __name__ == "__main__":
    unittest.main()

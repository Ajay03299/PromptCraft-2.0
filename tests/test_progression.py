import os
import tempfile
import unittest

from tests.helpers import LOCK, clear_room, playing, tick
import config as C
from game import Game, GameState
from save import HighScoreStore
from world import CHAMBERS, derive_stats, validate_chamber

S = GameState


class TestStateMachine(unittest.TestCase):
    def test_boots_to_title_and_starts(self):
        g = Game(seed=1)
        self.assertEqual(g.state, S.TITLE)
        tick(g, confirm=True)
        self.assertEqual(g.state, S.INTRO)

    def test_input_lock_prevents_double_action(self):
        g = Game(seed=1)
        tick(g, confirm=True)
        tick(g, confirm=True)  # same press bleeding into INTRO is ignored
        self.assertEqual(g.intro_page, 0)

    def test_pause_freezes(self):
        g = playing()
        tick(g, LOCK)
        tick(g, pause=True)
        self.assertEqual(g.state, S.PAUSED)
        s = g.session
        snap = (s.frame, [(d.x, d.y) for d in s.drones], s.echo_cooldown)
        tick(g, 60, right=True, echo=True)
        self.assertEqual(snap, (s.frame, [(d.x, d.y) for d in s.drones], s.echo_cooldown))
        tick(g, LOCK)
        tick(g, pause=True)
        self.assertEqual(g.state, S.PLAYING)

    def test_invalid_transition_rejected(self):
        g = Game(seed=1)
        self.assertFalse(g.set_state(S.VICTORY))
        self.assertEqual(g.state, S.TITLE)

    def test_level_complete_upgrade_next(self):
        g = playing()
        s = g.session
        clear_room(s)
        s.completed = True
        tick(g)
        self.assertEqual(g.state, S.LEVEL_COMPLETE)
        tick(g, 35)
        tick(g, confirm=True)
        self.assertEqual(g.state, S.UPGRADE)
        self.assertEqual(len(g.upgrade_choices), 3)
        tick(g, LOCK)
        choice = g.upgrade_choices[0]
        tick(g, confirm=True)
        tick(g, confirm=True)
        self.assertEqual(g.state, S.PLAYING)
        self.assertEqual(g.chamber_index, 1)
        self.assertEqual(sum(g.run.upgrades.values()), 1)  # exactly one upgrade applied
        self.assertEqual(g.run.upgrades[choice], 1)

    def test_upgrades_change_numbers(self):
        base = derive_stats({})
        self.assertGreater(derive_stats({"boots": 1}).speed, base.speed)
        p = derive_stats({"pulse": 1})
        self.assertTrue(p.pulse_radius > base.pulse_radius and p.pulse_cost < base.pulse_cost)
        e = derive_stats({"echo": 1})
        self.assertTrue(e.echo_history > base.echo_history and e.echo_cooldown < base.echo_cooldown)
        self.assertEqual(derive_stats({"shell": 1}).max_hp, base.max_hp + 1)

    def test_upgrades_persist_across_chambers(self):
        g = playing()
        g.apply_upgrade("boots")
        g._load_chamber(1)
        self.assertGreater(g.session.stats.speed, C.PLAYER_BASE_SPEED)

    def test_transition_clears_echo_and_cooldown(self):
        g = playing()
        s = g.session
        for i in range(30):
            s._update_player(type("I", (), {"right": i < 15, "left": i >= 15, "up": False, "down": False})())
        s.try_echo()
        g._load_chamber(1)
        self.assertIsNone(g.session.echo)
        self.assertEqual(g.session.echo_cooldown, 0)

    def test_game_over_retry_and_new_run(self):
        g = playing()
        g.run.score = 999
        g.checkpoint = g.run.copy()
        g.session.dead = True
        tick(g)
        self.assertEqual(g.state, S.GAME_OVER)
        tick(g, 25)
        tick(g, confirm=True)  # RETRY CHAMBER
        self.assertEqual(g.state, S.PLAYING)
        self.assertEqual(g.session.player.hp, g.session.player.max_hp)
        g.session.dead = True
        tick(g)
        tick(g, 25)
        g.menu_index = 1  # NEW RUN
        tick(g, confirm=True)
        self.assertEqual((g.state, g.chamber_index, g.run.score, g.run.upgrades), (S.PLAYING, 0, 0, {}))

    def test_boss_defeat_to_victory_to_title(self):
        g = playing(3)
        s = g.session
        b = s.boss
        s.player.energy = C.ENERGY_MAX
        for _ in range(b.max_hp):
            b.set_state("exposed", 50)
            s.player.x, s.player.y = b.cx - 3, b.cy + 30
            s.pulse_lockout = 0
            s.player.energy = C.ENERGY_MAX
            s.try_pulse()
        self.assertEqual(b.hp, 0)
        self.assertEqual(b.state, "dying")
        self.assertFalse(s.damage_player(0, 0))  # no damage during the death sequence
        tick(g, C.BOSS_DYING_FRAMES + 2)
        self.assertEqual(g.state, S.VICTORY)
        tick(g, 95)
        tick(g, confirm=True)
        self.assertEqual(g.state, S.TITLE)
        self.assertIsNone(g.session)

    def test_boss_closed_shell_takes_no_damage(self):
        s = playing(3).session
        b = s.boss
        b.set_state("idle", 50)
        s.player.x, s.player.y = b.cx - 3, b.cy + 30
        s.player.energy = C.ENERGY_MAX
        s.try_pulse()
        self.assertEqual(b.hp, b.max_hp)


class TestDataAndSave(unittest.TestCase):
    def test_chambers_valid(self):
        for ch in CHAMBERS:
            self.assertEqual(validate_chamber(ch), [], ch.key)

    def test_high_score_robust(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "new", "hs.json")
            self.assertEqual(HighScoreStore(path).load(), 0)
            self.assertTrue(HighScoreStore(path).save(42))
            self.assertEqual(HighScoreStore(path).load(), 42)
            with open(path, "w") as fh:
                fh.write("[1, 2")
            self.assertEqual(HighScoreStore(path).load(), 0)


if __name__ == "__main__":
    unittest.main()

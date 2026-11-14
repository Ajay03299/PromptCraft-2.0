import unittest

from tests.helpers import clear_room, playing, tick
import config as C
from actors import Drone, DroneState, Pickup
from session import InputState


class TestPlayer(unittest.TestCase):
    def test_diagonal_normalized(self):
        g = playing()
        s = g.session
        clear_room(s)
        s.player.x, s.player.y = 40, 60
        s._update_player(InputState(right=True, down=True))
        moved = ((s.player.x - 40) ** 2 + (s.player.y - 60) ** 2) ** 0.5
        self.assertAlmostEqual(moved, s.stats.speed, places=3)

    def test_opposite_keys_cancel(self):
        g = playing()
        s = g.session
        x0, y0 = s.player.x, s.player.y
        s._update_player(InputState(left=True, right=True, up=True, down=True))
        self.assertEqual((s.player.x, s.player.y), (x0, y0))

    def test_never_leaves_arena_or_enters_walls(self):
        g = playing()
        s = g.session
        clear_room(s)
        for keys in ({"left": True, "up": True}, {"right": True}, {"down": True}, {"left": True, "down": True}):
            for _ in range(400):
                s._update_player(InputState(**keys))
                p = s.player
                self.assertFalse(s.grid.entity_solid(p))
                self.assertTrue(C.ARENA_X0 <= p.x <= C.ARENA_X1 - p.w)
                self.assertTrue(C.ARENA_Y0 <= p.y <= C.ARENA_Y1 - p.h)


class TestHealth(unittest.TestCase):
    def test_invulnerability_blocks_repeat_hits(self):
        s = playing().session
        hp = s.player.hp
        self.assertTrue(s.damage_player(0, 0))
        self.assertFalse(s.damage_player(0, 0))
        self.assertEqual(s.player.hp, hp - 1)

    def test_knockback_never_enters_wall(self):
        s = playing().session
        clear_room(s)
        s.player.x, s.player.y = C.ARENA_X0 + 1, C.ARENA_Y0 + 1
        s.damage_player(s.player.x + 50, s.player.y + 50)
        for _ in range(C.KNOCKBACK_FRAMES + 2):
            s._update_player(InputState())
            self.assertFalse(s.grid.entity_solid(s.player))

    def test_hp_clamps_and_death(self):
        s = playing().session
        s.player.hp = 1
        s.damage_player(0, 0)
        self.assertEqual(s.player.hp, 0)
        self.assertGreater(s.player.dying, 0)
        s.player.invuln = 0
        self.assertFalse(s.damage_player(0, 0))
        self.assertEqual(s.player.hp, 0)


class TestEnergyAndPulse(unittest.TestCase):
    def test_insufficient_energy(self):
        s = playing().session
        s.player.energy = 0
        self.assertFalse(s.try_pulse())
        self.assertEqual(s.player.energy, 0)

    def test_pulse_consumes_and_locks_out(self):
        s = playing().session
        s.player.energy = C.ENERGY_MAX
        self.assertTrue(s.try_pulse())
        self.assertEqual(s.player.energy, C.ENERGY_MAX - s.stats.pulse_cost)
        self.assertFalse(s.try_pulse())  # one press = one pulse

    def test_energy_regen_capped(self):
        g = playing()
        g.session.player.energy = C.ENERGY_MAX
        tick(g, 30)
        self.assertLessEqual(g.session.player.energy, C.ENERGY_MAX)

    def test_pulse_stuns_many_including_zero_distance(self):
        s = playing().session
        clear_room(s)
        p = s.player
        s.drones = [Drone(p.x, p.y), Drone(p.x + 10, p.y), Drone(p.x, p.y + 12)]
        p.energy = C.ENERGY_MAX
        s.try_pulse()
        self.assertTrue(all(d.state == DroneState.STUNNED for d in s.drones))

    def test_stun_then_recover_then_patrol(self):
        s = playing().session
        clear_room(s)
        d = Drone(100, 50)
        s.drones = [d]
        d.stun(0, 0, 5)
        d.stun(0, 0, 5)  # re-stun resets, does not stack
        self.assertEqual(d.stun_timer, 5)
        for _ in range(5):
            s._update_drones()
        self.assertEqual(d.state, DroneState.RECOVER)
        for _ in range(C.DRONE_RECOVER_FRAMES):
            s._update_drones()
        self.assertNotIn(d.state, (DroneState.STUNNED, DroneState.RECOVER))

    def test_pulse_purges_blight(self):
        s = playing(2).session
        p = s.player
        tile = s.grid.tile_at(*p.center())
        s.blight = {(tile[0] + 1, tile[1])}
        p.energy = C.ENERGY_MAX
        s.try_pulse()
        self.assertEqual(s.blight, set())


class TestEcho(unittest.TestCase):
    def walk(self, s, frames=40):
        for i in range(frames):
            s._update_player(InputState(right=i % 40 < 20, left=i % 40 >= 20))

    def test_needs_trail(self):
        s = playing().session
        s.history.clear()
        self.assertFalse(s.try_echo())
        self.assertIsNone(s.echo)
        self.assertEqual(s.echo_cooldown, 0)

    def test_history_bounded(self):
        s = playing().session
        clear_room(s)
        self.walk(s, 500)
        self.assertEqual(len(s.history), s.stats.echo_history)

    def test_single_echo_and_cooldown(self):
        s = playing().session
        clear_room(s)
        self.walk(s)
        self.assertTrue(s.try_echo())
        first = s.echo
        self.assertFalse(s.try_echo())
        self.assertIs(s.echo, first)
        self.assertEqual(s.echo_cooldown, s.stats.echo_cooldown)

    def test_replay_is_reverse_trail_then_expires(self):
        s = playing().session
        clear_room(s)
        self.walk(s, 30)
        trail = list(s.history)
        s.try_echo()
        self.assertEqual(s.echo.pos, trail[-1])
        for _ in range(len(trail) + C.ECHO_LINGER + 2):
            s._update_echo()
            s._update_abilities(InputState())
        self.assertIsNone(s.echo)
        self.assertGreaterEqual(s.echo_cooldown, 0)

    def test_drones_chase_echo_then_revert(self):
        g = playing()
        s = g.session
        clear_room(s)
        self.walk(s)
        p = s.player
        d = Drone(p.x + 30, p.y)
        s.drones = [d]
        s.try_echo()
        s._update_drones()
        self.assertEqual(d.state, DroneState.CHASE_ECHO)
        s.echo.alive = False
        s._update_echo()
        self.assertNotEqual(d.state, DroneState.CHASE_ECHO)
        s._update_drones()
        self.assertEqual(d.state, DroneState.CHASE_PLAYER)

    def test_ghost_never_collects_or_hurts(self):
        s = playing().session
        clear_room(s)
        self.walk(s)
        s.try_echo()
        ex, ey = s.echo.pos
        s.seeds = [Pickup(ex, ey, "seed")]
        s.player.x += 40
        before = (s.seeds_collected, s.player.hp)
        s._update_pickups()
        self.assertEqual((s.seeds_collected, s.player.hp), before)


class TestCollectibles(unittest.TestCase):
    def test_seed_collected_exactly_once(self):
        s = playing().session
        clear_room(s)
        p = s.player
        s.seeds = [Pickup(p.x, p.y, "seed"), Pickup(p.x + 1, p.y, "seed")]
        s.seeds_required = 2
        s.seeds_collected = 0
        score = s.run.score
        s._update_pickups()
        s._update_pickups()
        self.assertEqual(s.seeds_collected, 2)
        self.assertEqual(s.run.score, score + 2 * C.SCORE_SEED)

    def test_exit_locked_until_all_seeds(self):
        g = playing()
        s = g.session
        clear_room(s)
        ex = s.exit
        s.player.x, s.player.y = ex.x + 1, ex.y + 1
        s._update_exit()
        self.assertEqual(ex.state, "locked")
        self.assertFalse(s.completed)
        s.seeds_collected = s.seeds_required
        s._update_exit()
        self.assertEqual(ex.state, "opening")
        self.assertFalse(s.completed)  # opening animation must finish first
        for _ in range(C.EXIT_OPEN_FRAMES + 1):
            s._update_exit()
        self.assertTrue(s.completed)


class TestHazards(unittest.TestCase):
    def test_vent_warns_before_active(self):
        s = playing(1).session
        v = s.vents[0]
        phases = [v.phase(t) for t in range(C.VENT_PERIOD)]
        first_active = phases.index("active")
        self.assertEqual(phases[first_active - 1], "warn")
        self.assertEqual(v.phase(-5), "idle")


if __name__ == "__main__":
    unittest.main()

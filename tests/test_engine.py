import random
import unittest

from tests.helpers import *  # noqa: F401,F403  (sets up sys.path)
from assets import validate_sprite_defs
from engine import Camera, Entity, FloatingTextManager, ParticleSystem, TileGrid, rects_overlap, safe_direction


class TestEntity(unittest.TestCase):
    def test_movement(self):
        e = Entity(x=10, y=10, vx=1.5, vy=-2)
        e.update()
        self.assertEqual((e.x, e.y, e.timer), (11.5, 8, 1))

    def test_aabb(self):
        a, b = Entity(0, 0), Entity(7, 7)
        self.assertTrue(a.intersects(b))
        self.assertFalse(a.intersects(Entity(8, 0)))  # touching edges do not overlap
        b.alive = False
        self.assertFalse(a.intersects(b))
        self.assertTrue(rects_overlap(0, 0, 4, 4, 3, 3, 4, 4))

    def test_safe_direction_zero_length(self):
        ux, uy = safe_direction(0, 0, 0.0)
        self.assertAlmostEqual(ux, 1.0)
        self.assertAlmostEqual(uy, 0.0)


class TestEffects(unittest.TestCase):
    def test_particles_capped(self):
        ps = ParticleSystem(max_particles=50, rng=random.Random(1))
        for _ in range(20):
            ps.burst(0, 0, count=30)
        self.assertLessEqual(len(ps.particles), 50)

    def test_short_life_burst_no_crash(self):
        ps = ParticleSystem(rng=random.Random(1))
        ps.burst(0, 0, count=5, life=2)  # starter crashed here
        self.assertEqual(len(ps.particles), 5)
        for _ in range(3):
            ps.update()
        self.assertEqual(ps.particles, [])

    def test_labels_expire_and_cap(self):
        ft = FloatingTextManager(max_labels=3)
        for i in range(10):
            ft.spawn(str(i), 0, 0, life=5)
        self.assertEqual(len(ft.labels), 3)
        for _ in range(5):
            ft.update()
        self.assertEqual(ft.labels, [])

    def test_camera_shake_toggle(self):
        cam = Camera(random.Random(1))
        cam.shake(10, 5)
        self.assertLessEqual(cam.shake_intensity, 3.0)
        cam.enabled = False
        self.assertEqual(cam.get_offset(), (0.0, 0.0))


class TestTileGrid(unittest.TestCase):
    ROWS = ["#####", "#...#", "#.#.#", "#...#", "#####"]

    def setUp(self):
        self.grid = TileGrid(self.ROWS, tile_size=8, solid="#")

    def test_wall_blocks_and_snaps(self):
        e = Entity(9, 9, w=6, h=6)
        bx, _ = self.grid.move(e, -5, 0)
        self.assertTrue(bx)
        self.assertAlmostEqual(e.x, 8.0, delta=0.1)
        self.assertFalse(self.grid.entity_solid(e))

    def test_out_of_bounds_is_solid(self):
        self.assertTrue(self.grid.rect_solid(-4, 10, 2, 2))
        self.assertTrue(self.grid.is_solid_tile(99, 99))

    def test_find_free_near(self):
        x, y = self.grid.find_free_near(16, 16, 6, 6)  # centre pillar
        self.assertFalse(self.grid.rect_solid(x, y, 6, 6))

    def test_fast_move_never_tunnels(self):
        e = Entity(9, 9, w=6, h=6)
        for _ in range(50):
            self.grid.move(e, 7.5, 7.5)
            self.assertFalse(self.grid.entity_solid(e))


class TestAssets(unittest.TestCase):
    def test_sprite_defs_valid(self):
        self.assertEqual(validate_sprite_defs(), [])


if __name__ == "__main__":
    unittest.main()

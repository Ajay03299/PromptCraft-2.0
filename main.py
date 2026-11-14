"""
ECHO//GARDEN - THE LAST SIGNAL
==============================
A retro action-exploration game built on the PIXELBOX Pyxel starter.

Run:        python main.py
Self-test:  python main.py --self-test      (headless; non-zero exit code on failure)
Unit tests: python -m unittest discover -s tests -v
"""

from __future__ import annotations

import argparse
import sys

import config as C


def read_input():
    """Translate Pyxel keyboard/gamepad state into one InputState for this frame."""
    import pyxel

    from session import InputState

    def held(*keys: int) -> bool:
        return any(pyxel.btn(k) for k in keys)

    def pressed(*keys: int) -> bool:
        return any(pyxel.btnp(k) for k in keys)

    def menu(*keys: int) -> bool:
        return any(pyxel.btnp(k, 12, 4) for k in keys)

    up = (pyxel.KEY_UP, pyxel.KEY_W, pyxel.GAMEPAD1_BUTTON_DPAD_UP)
    down = (pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    left = (pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)
    right = (pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
    return InputState(
        up=held(*up), down=held(*down), left=held(*left), right=held(*right),
        up_p=menu(*up), down_p=menu(*down), left_p=menu(*left), right_p=menu(*right),
        pulse=pressed(pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A),
        echo=pressed(pyxel.KEY_E, pyxel.KEY_X, pyxel.KEY_SHIFT, pyxel.GAMEPAD1_BUTTON_B),
        confirm=pressed(pyxel.KEY_RETURN, pyxel.KEY_KP_ENTER, pyxel.KEY_Z, pyxel.GAMEPAD1_BUTTON_START),
        pause=pressed(pyxel.KEY_P, pyxel.KEY_ESCAPE, pyxel.GAMEPAD1_BUTTON_START),
        quit=pressed(pyxel.KEY_ESCAPE),
        mute=pressed(pyxel.KEY_M),
        shake=pressed(pyxel.KEY_K),
        crt=pressed(pyxel.KEY_C),
    )


class EchoGardenApp:
    def __init__(self, seed: int | None = None) -> None:
        import pyxel

        from assets import AudioDirector, init_assets
        from game import Game
        from render import Renderer
        from save import HighScoreStore

        pyxel.init(C.SCREEN_W, C.SCREEN_H, title=C.WINDOW_TITLE, fps=C.FPS, quit_key=pyxel.KEY_NONE)
        init_assets()
        self.game = Game(seed=seed, store=HighScoreStore.default())
        self.renderer = Renderer()
        self.audio = AudioDirector()
        pyxel.run(self.update, self.draw)

    def update(self) -> None:
        import pyxel

        self.game.update(read_input())
        self.audio.sync(self.game.sound_on, self.game.sfx, self.game.music)
        if self.game.quit_requested:
            pyxel.quit()

    def draw(self) -> None:
        self.renderer.draw(self.game)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECHO//GARDEN - THE LAST SIGNAL")
    parser.add_argument("--self-test", action="store_true", help="run the headless smoke simulation")
    parser.add_argument("--seed", type=int, default=None, help="deterministic random seed")
    args = parser.parse_args(argv)
    if args.self_test:
        from selftest import run_self_test

        return run_self_test()
    EchoGardenApp(seed=args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())

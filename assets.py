"""
ECHO//GARDEN // Procedural Asset Bank (Pyxel 2.9.9)
===================================================
All sprites are hex strings and all audio is note strings: no binary files.

Real Pyxel 2.x default palette (the starter docstring listed PICO-8 colours, which is wrong):
  0 black(transparent)  1 navy #2B335F    2 purple #7E2072   3 teal #19959C
  4 plum #8B4852        5 blue #395C98    6 lt-blue #A9C1FF  7 white #EEEEEE
  8 crimson #D4186C     9 orange #D38441  a gold #E9C35B     b mint #70C6A9
  c periwinkle #7696DE  d gray #A3A3A3    e salmon #FF9798   f peach #EDC7B0
"""

from __future__ import annotations

import pyxel

from config import MUSIC_CHANNELS, SFX_CHANNELS

SPRITES: dict[str, tuple[int, int, int, int]] = {}

# (name, u, v, rows). Starter sprites keep their original row-0 slots; new art starts at v=8.
SPRITE_DEFS: list[tuple[str, int, int, list[str]]] = [
    ("bot_idle", 0, 0, ["00cccc00", "0c7777c0", "0c7171c0", "0c7777c0", "00cccc00", "0ccbbcc0", "0c0cc0c0", "00c00c00"]),
    ("bot_run", 8, 0, ["00cccc00", "0c7777c0", "0c7878c0", "0c7777c0", "00cccc00", "0ccffcc0", "00c00c00", "0c0000c0"]),
    ("orb", 16, 0, ["000aa000", "00a77a00", "0a7aa7a0", "aa7997aa", "aa7997aa", "0a7aa7a0", "00a77a00", "000aa000"]),
    ("crate", 24, 0, ["44444444", "49999994", "49499494", "49944994", "49944994", "49499494", "49999994", "44444444"]),
    ("drone", 32, 0, ["08000080", "008ee800", "08e77e80", "8e7887e8", "8e7887e8", "08eeee80", "00800800", "08000080"]),
    ("heart", 40, 0, ["08800880", "88788888", "87888888", "88888888", "08888880", "00888800", "00088000", "00000000"]),
    ("cursor", 48, 0, ["00077000", "00077000", "00000000", "770aa077", "770aa077", "00000000", "00077000", "00077000"]),
    # --- K-09 maintenance robot (faces right) ---
    ("k09_idle_a", 0, 8, ["000a0000", "000d0000", "00777700", "0711cc70", "07777770", "005bb500", "05dddd50", "00505000"]),
    ("k09_idle_b", 8, 8, ["00090000", "000d0000", "00777700", "0711cc70", "07777770", "005bb500", "05dddd50", "00050500"]),
    ("k09_run_a", 16, 8, ["0000a000", "000d0000", "00777700", "0711cc70", "07777770", "005bb500", "05dddd50", "05050500"]),
    ("k09_run_b", 24, 8, ["000a0000", "0000d000", "00777700", "0711cc70", "07777770", "005bb500", "05dddd50", "00505050"]),
    ("k09_hurt", 32, 8, ["00080000", "000d0000", "00777700", "07818170", "07777770", "00588500", "05dddd50", "00505000"]),
    # --- Corrupted drone / boss mote ---
    ("drone_a", 40, 8, ["dd0000dd", "00d22d00", "02888820", "28e77e82", "28e78e82", "02888820", "00288200", "00e00e00"]),
    ("drone_b", 48, 8, ["0dd00dd0", "00d22d00", "02888820", "28e77e82", "28e78e82", "02888820", "00288200", "000ee000"]),
    ("mote_a", 56, 8, ["00022000", "00288200", "028ee820", "28e77e82", "28e77e82", "028ee820", "00288200", "00022000"]),
    ("mote_b", 64, 8, ["20022002", "02288220", "028ee820", "28e77e82", "28e77e82", "028ee820", "02288220", "20022002"]),
    # --- Pickups ---
    ("seed_a", 72, 8, ["0000b300", "000ab000", "00aaaa00", "0aa7aaa0", "0aaaa9a0", "0aaa99a0", "00a99a00", "000aa000"]),
    ("seed_b", 80, 8, ["00003b00", "000ab000", "00a77a00", "0a77aaa0", "0aaaa9a0", "0aaa99a0", "00a99a00", "000aa000"]),
    ("cell", 88, 8, ["000dd000", "00c66c00", "00c76c00", "00c66c00", "00cbbc00", "00cbbc00", "00cbbc00", "000cc000"]),
    # --- HUD / UI icons ---
    ("heart_empty", 96, 8, ["05500550", "50055005", "50000005", "50000005", "05000050", "00500500", "00055000", "00000000"]),
    ("icon_bolt", 104, 8, ["0000aa00", "000aa000", "00aa0000", "0aaaaa00", "000aa000", "00aa0000", "0aa00000", "00000000"]),
    ("icon_echo", 112, 8, ["00666600", "06666660", "06c66c60", "06666660", "06666660", "06606060", "06060600", "00000000"]),
    ("icon_boots", 120, 8, ["000cc000", "000c6000", "000c6000", "000c6600", "b0cc66c0", "0bcccccc", "b0555550", "00000000"]),
    ("icon_pulse", 128, 8, ["00cccc00", "0c0000c0", "c00aa00c", "c0a77a0c", "c0a77a0c", "c00aa00c", "0c0000c0", "00cccc00"]),
    ("icon_shell", 136, 8, ["0cccccc0", "c666666c", "c677776c", "c678876c", "c667766c", "0c6666c0", "00c66c00", "000cc000"]),
    ("terminal", 144, 8, ["00000000", "05555550", "05111150", "05111150", "05555550", "00d55d00", "0dddddd0", "00000000"]),
]


def validate_sprite_defs(defs=SPRITE_DEFS) -> list[str]:
    """Return a list of problems (empty when every sprite is valid and non-overlapping)."""
    errors: list[str] = []
    rects = []
    names = set()
    for name, u, v, rows in defs:
        if name in names:
            errors.append(f"{name}: duplicate name")
        names.add(name)
        if not rows or any(len(r) != len(rows[0]) for r in rows):
            errors.append(f"{name}: inconsistent row widths")
            continue
        if any(ch not in "0123456789abcdef" for r in rows for ch in r):
            errors.append(f"{name}: invalid colour index")
        w, h = len(rows[0]), len(rows)
        if u < 0 or v < 0 or u + w > 256 or v + h > 256:
            errors.append(f"{name}: outside image bank")
        for other, ou, ov, ow, oh in rects:
            if u < ou + ow and u + w > ou and v < ov + oh and v + h > ov:
                errors.append(f"{name}: overlaps {other}")
        rects.append((name, u, v, w, h))
    return errors


# ---------------------------------------------------------------------------
# Sound effects: name -> (slot, notes, tones, volumes, effects, speed)
# ---------------------------------------------------------------------------
SOUND_DEFS: dict[str, tuple[int, str, str, str, str, int]] = {
    "jump": (0, "c2e2g2c3", "s", "4", "s", 7),
    "pickup": (1, "e3g3b3e4", "p", "5", "n", 6),
    "boom": (2, "c2g1e1c1", "n", "6542", "f", 9),
    "blip": (3, "a3c4", "t", "4", "n", 5),
    "start": (4, "c3e3g3c4e4g4", "p", "5", "nnnnnf", 5),
    "seed": (5, "g3c4e4g4", "t", "6", "nnnf", 4),
    "energy": (6, "c3d#3g3c4", "s", "4", "s", 4),
    "echo": (7, "g4d4b3g3d3b2", "t", "765432", "v", 5),
    "pulse": (8, "c3g2c2g1", "s", "7654", "s", 3),
    "stun": (9, "a3f3d3", "p", "5", "n", 4),
    "hurt": (10, "c2b1a#1a1", "n", "7", "f", 6),
    "upgrade": (11, "c3g3c4e4g4c4", "t", "6", "nnnnnf", 5),
    "clear": (12, "c3e3g3c4rg3c4e4", "p", "5", "nnnnnnnf", 7),
    "boss_hit": (13, "c2f#1c1", "n", "7", "f", 5),
    "boss_defeat": (14, "c2b1a1g1f1e1d1c1", "n", "77665544", "f", 10),
    "victory": (15, "c3e3g3c4e4g4c4g4", "t", "6", "nnnnnnnf", 8),
    "deny": (16, "e2c2", "s", "4", "n", 6),
    "select": (17, "a3", "t", "4", "n", 3),
    "relay": (18, "c3g3c4g4c4g4", "p", "5", "n", 4),
    "spore": (19, "f2", "n", "2", "f", 6),
    "purify": (20, "e4c4", "n", "3", "f", 3),
    "terminal": (21, "c4rc4", "t", "3", "n", 4),
    "roar": (22, "c1c#1d1c1", "n", "7776", "v", 14),
    "slam": (23, "c1", "n", "7", "f", 12),
    "game_over": (24, "g2e2c2g1", "t", "5", "nnnf", 14),
}

# ---------------------------------------------------------------------------
# Music: two looping channels (lead + bass), slots 32+
# ---------------------------------------------------------------------------
_MUSIC_SOUNDS: dict[int, tuple[str, str, str, str, int]] = {
    # Title / upgrade: contemplative A minor
    32: ("e3ra3b3c4rb3a3g3re3rd3e3rr", "t", "3", "n", 16),
    33: ("c3re3g3a3rg3e3d3rb2rc3d3e3r", "t", "3", "n", 16),
    34: ("a1ra1ra1re1rf1rf1rf1rc2r", "t", "3", "n", 16),
    35: ("c2rc2rg1rg1re1re1re1re1r", "t", "3", "n", 16),
    # Chambers 1-2: greenhouse arpeggios in D minor
    36: ("d3f3a3f3d3f3a3f3a#2d3f3d3a#2d3f3d3", "t", "2", "n", 12),
    37: ("f2a2c3a2f2a2c3a2c3e3g3e3c3e3g3e3", "t", "2", "n", 12),
    38: ("d2rrrd2rrra#1rrra#1rrr", "s", "2", "n", 12),
    39: ("f1rrrf1rrrc2rrrc2rrr", "s", "2", "n", 12),
    # Reactor: tension
    40: ("e3re3f3e3re3g3e3re3f3e3d3c3b2", "p", "2", "n", 9),
    41: ("e3re3f3e3re3a3g3rf3re3rrr", "p", "2", "n", 9),
    42: ("e1re1re1re1re1re1rd1rd1r", "s", "3", "n", 9),
    43: ("c1rc1rc1rc1rb0rb0rb0rb0r", "s", "3", "n", 9),
    # Boss: driving
    44: ("c3c3d#3c3f3c3d#3c3c3c3d#3c3g3f3d#3d3", "p", "2", "n", 7),
    45: ("a#2a#2d3a#2d#3a#2d3a#2g#2g#2c3g#2d3c3a#2g2", "p", "2", "n", 7),
    46: ("c1c2c1c2c1c2c1c2c1c2c1c2c1c2c1c2", "s", "3", "n", 7),
    47: ("a#0a#1a#0a#1a#0a#1a#0a#1g#0g#1g#0g#1g0g1g0g1", "s", "3", "n", 7),
    # Victory: bright C major
    48: ("c3e3g3c4b3g3e3g3a3f3c3f3g3b3d4g3", "t", "3", "n", 12),
    49: ("c4g3e3c3d3f3a3f3e3g3c4e4c4rrr", "t", "3", "n", 12),
    50: ("c2rg1rc2rg1rf1rc2rg1rb1r", "t", "3", "n", 12),
    51: ("a1re1rf1ra1rc2rg1rc2rrr", "t", "3", "n", 12),
}

MUSIC_TRACKS: dict[str, tuple[list[int], list[int]]] = {
    "title": ([32, 33], [34, 35]),
    "garden": ([36, 37], [38, 39]),
    "reactor": ([40, 41], [42, 43]),
    "boss": ([44, 45], [46, 47]),
    "victory": ([48, 49], [50, 51]),
}


def register_sprite(name: str, u: int, v: int, rows: list[str]) -> None:
    """Register a sprite into Image Bank 0 from hex strings ('0' is transparent)."""
    pyxel.images[0].set(u, v, rows)
    SPRITES[name] = (u, v, len(rows[0]), len(rows))


def init_assets() -> None:
    """Populate Image Bank 0 and all sound slots. Requires pyxel.init() first."""
    for name, u, v, rows in SPRITE_DEFS:
        register_sprite(name, u, v, rows)
    for slot, notes, tones, volumes, effects, speed in SOUND_DEFS.values():
        pyxel.sounds[slot].set(notes, tones, volumes, effects, speed)
    for slot, (notes, tones, volumes, effects, speed) in _MUSIC_SOUNDS.items():
        pyxel.sounds[slot].set(notes, tones, volumes, effects, speed)


def draw_sprite(name: str, x: float, y: float, flip_x: bool = False, colkey: int = 0) -> None:
    """Draw a named sprite from Image Bank 0. Negative width flips horizontally."""
    if name not in SPRITES:
        pyxel.rect(int(x), int(y), 8, 8, 8)
        return
    u, v, w, h = SPRITES[name]
    pyxel.blt(int(x), int(y), 0, u, v, -w if flip_x else w, h, colkey)


def play_sfx(name: str, channel: int = SFX_CHANNELS[0]) -> None:
    """Trigger a named sound effect on the given channel (0-3)."""
    if name in SOUND_DEFS:
        pyxel.play(channel, SOUND_DEFS[name][0])


class AudioDirector:
    """Turns the game's sound requests into Pyxel playback. Music on ch 0-1, SFX on ch 2-3."""

    def __init__(self) -> None:
        self.current_music: str | None = None
        self.muted = False
        self._next = 0

    def sync(self, sound_on: bool, sfx_events: list[str], music: str | None) -> None:
        if not sound_on:
            if not self.muted:
                pyxel.stop()
                self.muted = True
                self.current_music = None
            sfx_events.clear()
            return
        self.muted = False
        if music != self.current_music:
            for ch in MUSIC_CHANNELS:
                pyxel.stop(ch)
            if music in MUSIC_TRACKS:
                for ch, seq in zip(MUSIC_CHANNELS, MUSIC_TRACKS[music]):
                    pyxel.play(ch, seq, loop=True)
            self.current_music = music
        for name in sfx_events[-2:]:
            play_sfx(name, SFX_CHANNELS[self._next])
            self._next = 1 - self._next
        sfx_events.clear()

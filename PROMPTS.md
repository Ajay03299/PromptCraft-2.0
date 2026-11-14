# PROMPTS.md — How ECHO//GARDEN was prompted

This is an honest log of the prompts used to build the game and what each one produced. The AI was **Claude (Opus 5.5)** running as an agent with a Linux workspace, a shell, and file tools. It read the starter, wrote the code, ran the tests, and fixed what failed.

> Extend this file with every prompt you use while you review and iterate. The judges reward process, not only the result.

---

## Prompt 1 — The master build prompt (attached file)

Rather than asking for features one at a time, we wrote a single long brief: **"MASTER BUILD PROMPT — PROMPTCRAFT 2.0 / PROJECT: ECHO//GARDEN — THE LAST SIGNAL"**. Its structure, section by section:

| Section | What it told the AI | Why we included it |
| :--- | :--- | :--- |
| Team roles | "Act as my entire senior game team: engineer, designer, pixel artist, UX, audio, architect, adversarial QA" | Pushes beyond "just make it run" toward design and polish |
| Competition rules | Must run via `python main.py`, stay on Pyxel, 16 colours, Pyxel audio, stdlib only, README needs screenshots and a PromptCraft section | Hard constraints stated up front so they shape every decision |
| Dependency constraint | Pin `pyxel==2.9.9`, verify every Pyxel API before using it | Stops hallucinated or newer-version APIs |
| Creative vision | Title, story (K-09, Lumen Seeds, Blight Heart), palette direction, core loop | One coherent creative bible instead of drip-fed ideas |
| Signature mechanic | ECHO REPLAY spec plus 10 technical rules (bounded buffer, single echo, expiry releases AI, ghost never collects...) | Makes the creative-divergence feature mechanically real, not cosmetic |
| Systems | Player, seeds, drone state machine (PATROL / CHASE_PLAYER / CHASE_ECHO / STUNNED / RECOVER), pulse, health, hazards | Concrete, checkable requirements |
| Levels and boss | Three chambers with distinct roles, a boss with telegraphs, vulnerability windows, Pulse/Echo interaction, upgrades | Gives the game a beginning, middle, and end |
| State machine | 8 required states plus rules (pause freezes, no input bleed, no stuck screens) | The "completeness" judging category |
| Edge cases | ~60 adversarial cases (echo at frame 0, pulse at zero distance, double collection...) | Became runtime invariants in the self-test |
| Testing | `unittest`, `--self-test` with real checks, deterministic seeds, no fake "SUCCESS" | Makes quality verifiable |
| Workflow | 7 phases, from audit to submission | Keeps the agent from stopping at a plan |
| Honesty rules | Don't fabricate prompts, screenshots, or test results; don't claim GUI testing that didn't happen | Keeps this documentation trustworthy |
| Acceptance criteria | A checkbox list, including `compileall`, `pip check`, and `git diff --check` | A definition of done the AI can verify itself |

## Prompt 2 — Kickoff

> "this is my repo which im working in, go through everything attached, all details are there, and lets cook this and smash it out of the park boss"

Attached: the master prompt, the `pixelbox_starter.zip`, the repo URL, and a screenshot of our terminal.

What the AI did with it:
- **Diagnosed our launch error from the screenshot.** `python main.py` was being run in `PromptCraft-2.0/` while the starter files sat in a different folder.
- **Audited the starter** and found these bugs:
  - Particles and labels grew without limit.
  - `burst(life<4)` crashed.
  - Energy was never clamped.
  - Every sound played on channel 0, so sounds cut each other off.
  - A camera flash blanked the HUD.
- **Verified the Pyxel 2.9.9 API surface** by introspecting the installed package. This turned up two things:
  1. The starter's palette docstring lists PICO-8 colours, but Pyxel's real palette differs (colour 3 is teal, 8 is crimson). All art was redesigned against the real values.
  2. `pyxel.init(..., headless=True)` exists, which enabled rendering tests and real screenshots without a window.
- Wrote `config.py` and an improved `engine.py` (bounded effects, injectable RNG, shake toggle, and a new `TileGrid` with sub-pixel-safe collision and corner assist).

## Prompt 3 — Course correction for speed

> "you are taking too long, do it quicker so that i can review and then make changes and improve"

**Lesson:** the master prompt asked for "think deeply, polish relentlessly", and the AI followed that literally, which was too slow for a 90-minute round. The follow-up prompt reset the priority to a playable vertical slice first, then iteration. The AI then:
- Wrote the remaining modules in large passes: `assets.py`, `world.py`, `actors.py`, `session.py`, `game.py`, `render.py`, `save.py`, `main.py`, and `selftest.py`.
- Ran `python main.py --self-test` immediately. The first run failed three sections:

| Failure | Root cause | Fix |
| :--- | :--- | :--- |
| "pause did not freeze gameplay" | Test bug: SPACE also means confirm in the pause menu, so it resumed | Test now sends non-menu input. SPACE-confirm kept as intended UX |
| "invalid transitions TITLE→PLAYING" | Tests skipped the legal TITLE→INTRO→PLAYING path | Added a `begin()` helper that enters chambers legally |
| "expired echo still referenced" | **Real bug.** On death, the echo was only flagged, and the dying branch skipped the cleanup | `clear_echo()` removes the echo and releases drones immediately |
| "drone chasing an echo that does not exist" | **Real bug.** A drone that killed K-09 cleared the echo mid-loop, but later drones still held a stale local reference | Echo is re-read per drone inside the loop |

- After the fixes, all six self-test sections passed. The autopilot reached **VICTORY** on two seeds under normal damage rules.
- Rendered real frames headlessly (`tools/capture_screenshots.py`) and inspected them. This caught upgrade-card text overflowing the 48 px cards ("COOLDOWN -2S"). The text was shortened, and a width validator was added to the self-test so it can't regress.
- Wrote 46 `unittest` tests covering the 20 areas the brief listed. All passed.

## What worked / what we'd do differently

**Worked well**
- **Verify before use.** Introspecting the installed Pyxel surfaced the palette mismatch and the headless mode, two facts that changed the design.
- **Edge-case lists become invariants.** Writing the edge cases into the prompt meant the AI turned them into per-frame assertions. Those caught two real bugs a human playtest could easily miss.
- **"Prove it's beatable."** Asking for a self-test that *plays* the game produced a BFS autopilot. It validates level reachability, boss fairness, and the end-to-end state flow.
- **Separating logic from rendering** made all of the above possible without a window.

**Needed refinement**
- An all-encompassing prompt needs an explicit **time budget**. "Polish relentlessly" and "90 minutes" conflict, and the AI resolved that the wrong way until told otherwise.
- Visual bugs (text overflow) only appear in rendered frames. "Render and look at real frames" deserves its own step in the prompt.

---

## Prompt 4 — Independent critical review

> "Act as an independent senior game-engineering reviewer and a highly critical PromptCraft competition judge. Your job is to find reasons why this submission could lose points or fail during the demonstration. Do not assume the previous implementation is correct..." (followed by a checklist: reinspect every system, try to break it, run every command, judge the first-time player experience, score against the rubric, fix the highest-value issues, keep the docs honest, and be quick).

Changing the AI's role from *builder* to *adversarial reviewer* found things the build pass had missed:

| Finding | Type | Fix |
| :--- | :--- | :--- |
| Victory screen could show "NEW HIGH SCORE" after a retry, using a record flag left over from the earlier game over | Real bug | `new_record` is now judged fresh for each ending, with a regression test |
| No controls reminder once the intro was skipped | UX | Pause menu now shows controls and the objective |
| No feedback when Echo recharged (only a small HUD icon) | UX | `ECHO READY` popup above K-09 |
| Low health was easy to miss | UX | Flashing red alarm border at 1 HP |
| Boss arrival had no build-up | Feel | Hazard-striped `!! WARNING !!` banner |
| Echo activation lacked impact | Feel | VHS `<< REWIND` tear lines for 8 frames |
| Three unused constants and one unused import | Dead code | Removed, or wired up (`BOSS_BODY_RADIUS` now drives the boss render) |

It also added 12 adversarial tests (`tests/test_review.py`):
- **Restarts and transitions:** restart from the pause menu, quit to title, and 40 rapid room transitions with an active echo and spores.
- **Ability edge cases:** death during an active echo plus pulse, and boss defeat while lanes, spores and motes are all active.
- **Long runs:** a 6,000-frame randomised boss stress run.
- **Movement and resources:** a 3,000-step corner-wiggle collision run, zero and maximum energy, and repeated upgrade activation.
- **Save failures:** a permission-denied save path.

**A visual check overruled the code.** The first CRT filter had a rolling scan band. Rendered at 160×120, it looked like a stray dotted line rather than a CRT effect. The band was removed, and the filter now defaults to **off** (toggle with C). Without looking at real frames, this would have shipped as a "feature" that made the game look broken.

## Prompt 5 — Push creative divergence and retro feel, fast

> "can you improve this creative divergence and retro craft and feel quickly in a minute soon"

Under time pressure, the AI picked additions that deepen the existing identity rather than bolting on new systems:

| Addition | Judging target | Why this one |
| :--- | :--- | :--- |
| **Echo Collapse**: the finished ghost detonates, stunning drones it lured (`ECHO TRAP xN`) | Creative divergence | Turns the decoy into a lure-then-trap combo. It adds depth to the signature mechanic without a new button. It only fires on natural expiry, never on death or exit (tested) |
| **Seeds regrow the garden**: each recovered seed leaves a sprout that grows and blooms in place | Retro craft and story | The "restore the garden" story becomes visible on screen, and it costs only a handful of pixels per seed |
| **2x-scale K-09 and echo on the title screen** | Retro craft | The hero and the mechanic are readable within the first second |

Three new tests: collapse stuns only nearby lured drones; no collapse when death clears the echo; exactly one sprout per seed. 61 tests and the self-test all pass. Screenshots were recaptured from real frames, adding `11_echo_trap.png`.

## Prompts during review and iteration

_Add each follow-up prompt here: what you asked, what changed, and whether it worked._

| # | Prompt | Result |
| :--- | :--- | :--- |
| 6 | | |

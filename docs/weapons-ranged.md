# Whip, bow, boomerang and javelin attacks of the three heroes (weapon types 4, 5, 6, 7; rows 36-71) - recovered from the ROM (Secret of Mana USA)

Tags: **[V]** means the real 65816 code was executed in `tools/cpu65816.py` (the whole per-frame routine `$C0:B08C` on a ZSNES save state with the controller word injected) and the numbers were read from the running objects; **[C]** means read from the disassembly, not executed. What is not determined is listed in section 10 and carries no guessed values. This document does for the four remaining weapon types what `docs/glove-attacks.md` and `docs/weapons-melee.md` do for the glove and for sword, axe and spear; those documents explain the shared machinery (the two clocks, boxes and hit test, the weapon gauge, the charge counter) and are referred to instead of repeated where the result is the same.

Addressing: 2 MiB HiROM, `$Cx:xxxx` = file offset `((x-0xC0)<<16)|xxxx`, `$01:xxxx` is the mirror of `$C1:xxxx`, `$02:xxxx` of `$C2:xxxx`. Animation scripts live in bank `$D1`. No ROM bytes are stored in the repository: scripts are described by decoded numbers. Object fields are offsets in the 0x200-byte object record at `$7E:E000 + slot*0x200` (`docs/rom-combat.md` section 1.1); heroes are slots 0, 1, 2, monsters start at slot 3. Weapon types: `type = row / 9`; rows 36-44 are the whip, 45-53 the bow, 54-62 the boomerang, 63-71 the javelin (`data/weapons.json`).

Time: **1 frame = 1/60.0988 s = 16.638 ms**. A hero advances its animation once per 5th frame (12.02 Hz); input, movement, the weapon gauge and the **projectile engine run every frame** (section 3). "Frame 0" of a timeline is the frame of the B press (or of the release of the charge button); the first animation step comes `(3 - $56) mod 5` frames later (0-4 frames, section 1.1).

Method: `tools/ranged_attacks.py` (library `tools/ranged_sim.py`, on top of `tools/glove_sim.py`) loads a save state, equips the weapon row with the game's own routines (`$C0:4530` stats, `$C0:EA41` animation tables), makes one hero the pad-1 hero and runs `$C0:B08C` once per video frame with the pad word injected where the game reads `$4218/$4219` (B = 0x8000). The attack animation is never forced: the real chooser `$C1:E40E` runs and the distance class and `$F4` parity are set so that it returns the wanted animation id (checked in every run). A dummy monster (id 0, HP 9999, AI step disabled) is created by the game's spawner `$C0:DE3B` when a hit is needed; it hops on the spot, so its body box moves up and down (a fact that matters for the hit tests of section 7). The save state had the three heroes idle on a map with nothing in front of them (Agi 79, 63, 57; atk 76, 62, 40 with the glove); the sound driver, PPU and DMA are not emulated. Data: `data/weapons_ranged.json`; tables below are printed from it by `tools/ranged_report.py`.

## 0. Summary

1. **Same input rules as the glove, plus one new one.** No combo, no buffering of presses, the d-pad is ignored during a swing (`E01C != 0`). A new swing is refused while the swing runs **or while a projectile of the previous volley still exists** (`E061 != 0`, `$C0:B29F` returns when `E01C | E061` is non-zero): five extra presses during a bow throw (frames 6, 12, 18, 30, 40; the arrow lives until frame 43) started nothing [V]. The hero can walk as soon as the swing state ends, with the projectile still flying [V].
2. **The whip is a melee weapon with no projectile.** One normal swing = **4 steps = 20 frames** after the first step (20-24 frames from the press), a **60 x 16 box active for only 5 frames** (frames 11-15 from the press, 26-86 px in front of the hero for a side facing), no movement, body box empty from frame 1 to 20. The animation ids 0-3 are two scripts (ids 0, 1 and ids 2, 3) with identical timing and boxes; the three distance classes of a charged attack are one script (no dash prefix) (section 2) [V].
3. **Bow, javelin and boomerang have no melee box in the normal attack; the animation launches projectiles with the script op `0xFB` (`JSL $C2:BF1D`).** The launcher fills up to three entries of a projectile table in WRAM (`$7E:D000 + 0x40 * hero + 0x10 * k`); the engine of bank `$C2` moves them every frame, tests them against the monsters, and **loads the weapon gauge and clears the charge stage `E19B` when the last entry is gone** (`$C2:C221-C24D`), not at the end of the swing (section 3) [V, C].
4. **Normal attack** (frames after the press, hero 0, side facing, press at `$56` = 2): bow swing ends at 36, arrow live from 21, hero free again at 43 (0.715 s); javelin swing ends at 26, spear live from 6, free at 35 (0.582 s); boomerang swing ends at 31, boomerang live from 16, free at 57 (0.948 s) (section 4-6) [V].
5. **Charged attacks.** The stage `s` at the release (1-8) selects the animation id `E011 = 4s + class` as for every weapon; the **bow has one script for all 40 ids** (the charged bow shot is the normal shot with more arrows), the javelin and boomerang have one script per stage (the 3 classes share it) with different wind-ups, jumps and, in some stages, melee boxes of the hero; the whip has one script per stage (section 2.3, 5, 6) [V].
6. **Number of projectiles is set by the stage when the launcher runs**: stages 0-2 one, stages 3-5 two (the second delayed by 10 frames), stages 6-8 three (delays 10 and 20 frames); the speed byte is `14 - stage`; range grows with the stage (bow, side facing, from 63 px at stage 0 to 129 px at stage 8) (section 3.3) [V].
7. **A projectile hits a monster when the two boxes overlap** (16 x 16 for arrows and boomerang, 32 x 32 for the javelin, against the monster's body box `E0CA/E0CB`; the test is `2|dx| < wp + tw` and `2|dy| < hp + th` on screen positions); the rule predicted hit / no hit of 80 random placements per case with 0 or 1 exceptions for the bow and javelin, and with exceptions explained by the hero's own melee box for the boomerang (section 7.1) [V]. **Arrows and javelins stop at the first target (they enter an 8-frame dying state); the boomerang pierces every target on its way out and is not tested at all on its way back** (section 7.2) [V].
8. **One hit per target per volley.** A mask in `E02E` (bit `k` = monster slot `3 + k`) keeps later projectiles of the same volley from flagging a target again; with the mask forced to 0 every arrow flags it again (section 7.3) [V].
9. **Damage is the glove formula** with the charge stage `E19B` read at the hit (it keeps its value while projectiles exist): multiplier `(2s+4)/4` = x1 ... x5; the crit base of types 5-7 is halved (section 7.4) [V].
10. **Status and knockback are the glove rules**: weapon status word with 80 % chance per damaging hit (measured 73-98 % over 60 hits per row), hurt code 0x89 and a 40 px push when the hit deals at least a quarter of the target's maximum HP (section 7.5) [V].
11. **Charge**: the counter starts when `E1ED`, `E01C` and `E061` are all 0, so for the projectile weapons the first stage comes later than for the glove by the flight time; stage `k` is reached **90 k - 3 frames after the gauge is empty** (section 8) [V].
12. **Hero vulnerability**: during a bow shot the body box stays non-empty (the hero can be hit in every frame); during the whip, javelin and boomerang normal attacks it is empty from frame 1 to the end of the swing (section 9) [V].
13. The three heroes share all scripts, speeds, weapon box sizes and projectile paths (compared for all stages, classes and facings). Differences: the gauge (Agi), the stats, the body boxes (they follow the sprite), and the weapon box of the whip, which becomes active one frame later for heroes 1 and 2 (frames 12-16) [V].

## 1. Shared machinery

### 1.1 Latency, press-phase table [V]
The first animation step happens `(3 - $56) mod 5` frames after the press frame (0 when the press falls in the frame in which the hero step runs), as measured for the sword, axe and spear in `docs/weapons-melee.md` section 1.1. Swing end and "hero free again" (`E01C = 0` and `E061 = 0`, the first frame in which a new press is accepted) for every phase of the press (animation id 0, side facing):

| `$56` at the press | first step after | whip: swing end | bow: swing end / free | boomerang: swing end / free | javelin: swing end / free |
|---|---|---|---|---|---|
| 0 | 3 | 23 | 38 / 45 | 33 / 59 | 28 / 37 |
| 1 | 2 | 22 | 37 / 44 | 32 / 58 | 27 / 36 |
| 2 | 1 | 21 | 36 / 43 | 31 / 57 | 26 / 35 |
| 3 | 0 | 20 | 35 / 42 | 30 / 56 | 25 / 34 |
| 4 | 4 | 24 | 39 / 46 | 34 / 60 | 29 / 38 |

### 1.2 Which animation plays [V]
`$C1:E40E` is the same routine as for every weapon: distance class of the nearest enemy (nearest `x` < 26 / 26-41 / >= 42 px, `y` < 24 / 24-39 / >= 40 px, no enemy = far), animation id = class value - parity of `$F4` for a normal attack, `4 * stage + class` for a charged one. Re-measured with the four weapons equipped: the thresholds, the facing independence and the stage rows are identical to the glove (`data/weapons_ranged.json`, `chooser`). The table `$D1:0480 + 40 * type` that maps the chooser's kind to the animation id is the identity for ids 0-35 in types 4-7 (ids 36-39 map to 0, 4, 8, 12, as for the other types).

What the animation id selects is different per weapon. Script of each animation id (side facing; the up and down scripts have the same shape and their own addresses, `data/weapons_ranged.json`, `structure`):

- whip: ids 0, 1 / 2, 3 = two normal scripts; ids `4s .. 4s+3` (the four classes of stage `s`, and ids 36-39) share one script per stage;
- bow: **all 40 ids are one script**;
- boomerang and javelin: ids 0-3 one script, ids `4s .. 4s+3` one script per stage.

So **the distance class never changes a charged attack of these four weapons** (no dash prefix as for the glove, sword, axe, spear), and the normal-attack variants differ only in the pictures of the whip (the timelines of ids 0-3 are identical in all four facings, checked for all four weapons) [V, C].

### 1.3 Weapon gauge `E1ED` [V]
The loading formula is the glove's: `E1ED = (100 - Agi)/2 + 50` (60, 68, 71 for Agi 79, 63, 57), frozen while `E01C & 0xA0 != 0`, -1 per frame, seen at 1 for 16 frames, then 0. **When it is loaded differs**: the whip loads it at the end of the swing (`$C0:F937`) like the glove; **bow, boomerang and javelin load it in the frame in which the last projectile entry disappears** (`$C2:C221`: all three entries of the hero empty -> `E061 = 0`, `E19B = 0`, `E1ED = (100 - Agi)/2 + 50`); at the end of their swing the script op `0xFF` skips the load because `E061 != 0` (`$C0:F932`). Because the projectile step runs before the gauge decrement, the first value seen is one lower (59, 67, 70), so the gauge is 0 **74 / 82 / 85 frames after the "free again" frame** (75 / 83 / 86 for the whip, counted from the swing end). From the press (hero 0, Agi 79): whip 96, bow 117, boomerang 131 (side facing), javelin 109 [V]. The effect of a non-zero gauge on damage is that of `docs/glove-attacks.md` section 2.4 (accuracy halved, no critical hit, `(v/2) * (AC - E1ED) / AC`); measured again with the real routine for these weapons:

| gauge `E1ED` at the hit | whip: stage 0 mean damage | bow | boomerang | javelin |
|---|---|---|---|---|
| 0 | 153.7 | 148.0 | 146.0 | 146.0 |
| 1 | 43.6 | 44.3 | 43.6 | 43.6 |
| 15 | 33.9 | 34.6 | 33.9 | 33.9 |
| 30 | 28.2 | 28.8 | 28.2 | 28.2 |
| 45 | 21.0 | 21.6 | 21.0 | 21.0 |
| 60 | 13.7 | 14.3 | 13.7 | 13.7 |
| 75 | 6.1 | 6.7 | 6.1 | 6.1 |
| 90 | 0.0 | 0.0 | 0.0 | 0.0 |

### 1.4 Boxes and hit flags [V, C]
The hero's weapon box `E0C0-E0C3`, body box `E0C8-E0CB` and the pair test `$C1:D14A` are as in `docs/glove-attacks.md` section 2.5. They matter for the whip and for the melee parts of the boomerang and javelin stages. Projectiles are not tested by that routine but by the engine of section 3.

## 2. Whip (type 4)

### 2.1 Normal attack [V]
Hero 0, press at `$56` = 2 (first step at frame 1), ids 0-3 (identical):

| facing | swing end | hero free again | first step | weapon box active (frames) | projectile first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|
| left | 21 | 21 | 1 | 11..15 | - | 24@11 |
| right | 21 | 21 | 1 | 11..15 | - | 24@11 |
| up | 21 | 21 | 1 | 11..15 | - | 24@11 |
| down | 21 | 21 | 1 | 11..15 | - | 24@11 |

Timeline (hero 0, left; right is the mirror image: velocity and box x negated; up and down have their own box shapes):

whip normal, animation id 0, facing left: end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | - | intangible | 0, 0, 0 |
| 11-15 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 16-20 | 0 | - | intangible | 0, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | 0, 0, 0 |

- The animation has 4 steps of one sprite frame each (script `$D1:7861`, 4 steps: sprite frames 73, 73, 74, 75; ids 2, 3: `$D1:788B`, sprite frames 91, 91, 92, 93), the sound 0x24 is requested at step 2 (frame 11, the start of the strike), the script ops `0x8D` at step 0 and `0x83` at step 4 enclose the strike (their meaning is not decoded).
- **Weapon box** (centre x, centre y, width, height, relative to the hero position; forward is negative x for a left-facing hero): left/right **+-56, -11, 60 x 16** (spans 26 to 86 px in front of the hero, 3 to 19 px above his position), up **0, -58, 16 x 40** (38 to 78 px above), down **0, 46, 16 x 48** (22 to 70 px below). It is active during **5 frames** (11-15 for hero 0, 12-16 for heroes 1 and 2) [V]. For a side facing a target closer than about 16 px or further than about 96 px is not touched (box 26-86 px plus the dummy's body box of 10 px on each side; the reach table of section 2.4 shows no hit at 14 or 100 px).
- **Body box**: non-empty in frame 0 and from frame 21, empty in between, so the hero can be hit by a monster weapon box only in frame 1 of the swing (section 9).
- **No movement**, the d-pad is ignored for the whole swing, a press during the swing is discarded, the next swing needs a new press after `E01C` has returned to 0 (with a press every second frame the second swing started at frame 22, the first even frame after the swing ended; presses at 6, 12 and 18 started nothing) [V].
- Gauge: loaded at frame 21 with 60 / 68 / 71 for hero 0 / 1 / 2.

### 2.2 Other normal-attack facts [V]
- The three heroes have identical timelines except the weapon box one frame later (hero 1, 2).
- All nine rows of the type have identical animations (the rows differ in the stats, `data/weapons.json`): atk 76, 80, 86, 91, 98, 104, 112, 121, 127 for hero 0 after the equip routine; rows 37 and 42 carry the status word 0x0004, 80 %.
- A swing started right after the previous one starts with the gauge at 60 (the frozen value of the previous swing; damage reduced as in section 1.3).

### 2.3 Charged attacks
The stage is the one reached when B is released (section 8); the attack plays in the release frame (`E01C = 0x80`). The three classes (`E011 = 4s, 4s+1, 4s+2`) run the same script: **8 distinct charged attacks**, and the timelines of all three heroes and all four facings were run for every class (no difference between classes in any of them) [V].

| stage | frames (s) | steps | move px (x, y) | max height | weapon box frames | first..last | box union x lo..hi, y lo..hi (left) | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|
| 1 | 41 (0.682) | 8 | (0, 0) | 0 | 5 | 31..35 | [-86, -26, -19, -3] | 3E@1 24@31 |
| 2 | 31 (0.516) | 6 | (-5, 0) | 0 | 5 | 21..25 | [-85, -21, -19, -3] | 24@21 |
| 3 | 56 (0.932) | 11 | (-15, 0) | 15 | 10 | 26..50 | [-101, -31, -34, -3] | 1C@1 1C@11 24@26 24@46 |
| 4 | 61 (1.015) | 12 | (0, 0) | 0 | 15 | 11..55 | [-86, -26, -19, -3] | 24@11 24@31 24@51 |
| 5 | 81 (1.348) | 16 | (0, 0) | 0 | 20 | 11..75 | [-86, 86, -78, 70] | 24@11 24@31 24@51 24@71 |
| 6 | 81 (1.348) | 16 | (-40, 0) | 0 | 15 | 11..75 | [-126, -26, -19, -3] | 24@11 24@41 24@71 |
| 7 | 106 (1.764) | 21 | (0, 0) | 10 | 20 | 36..100 | [-86, -26, -19, -3] | 3E@1 24@36 24@56 24@76 24@96 |
| 8 | 136 (2.263) | 27 | (-15, 0) | 15 | 30 | 26..130 | [-101, -31, -34, 11] | 1C@1 1C@11 24@26 24@46 24@66 24@86 24@106 24@126 |

Displacement (sum of the velocities, class 0), frames to swing end:

| stage | left (x, y) | right | up | down | frames to swing end left / up | hero free again left / up |
|---|---|---|---|---|---|---|
| 1 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 41 / 41 | 41 / 41 |
| 2 | (-5, 0) | (5, 0) | (0, -5) | (0, 5) | 31 / 31 | 31 / 31 |
| 3 | (-15, 0) | (15, 0) | (0, -15) | (0, 15) | 56 / 56 | 56 / 56 |
| 4 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 61 / 61 | 61 / 61 |
| 5 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 81 / 81 | 81 / 81 |
| 6 | (-40, 0) | (40, 0) | (0, -40) | (0, 40) | 81 / 81 | 81 / 81 |
| 7 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 106 / 106 | 106 / 106 |
| 8 | (-15, 0) | (15, 0) | (0, -15) | (0, 15) | 136 / 136 | 136 / 136 |

Scripts of the animation ids (side facing; steps = hero steps of 5 frames; velocity presets are rows of the 4-byte table at `$C2:AF05`, see `docs/glove-attacks.md` section 4.2):

| animation ids | script (bank $D1) | steps | shot (op FB) at step | sounds (step: id) | velocity presets (step: k) |
|---|---|---|---|---|---|
| 0,1 | $7861 | 4 | - | 2: 24 | - |
| 2,3 | $788B | 4 | - | 2: 24 | - |
| 4,5,6,7 | $78D3 | 8 | - | 0: 3E, 6: 24 | - |
| 8,9,10,11 | $78E8 | 6 | - | 4: 24 | 1: 7, 2: 25, 2: 1, 6: 25 |
| 12,13,14,15 | $7978 | 11 | - | 0: 1C, 2: 1C, 5: 24, 9: 24 | 1: 25, 2: 17, 3: 27, 5: 21, 6: 22, 7: 0 |
| 16,17,18,19 | $798D | 12 | - | 2: 24, 6: 24, 10: 24 | - |
| 20,21,22,23,36 | $79AB | 16 | - | 2: 24, 6: 24, 10: 24, 14: 24 | - |
| 24,25,26,27,37 | $79F0 | 16 | - | 2: 24, 8: 24, 14: 24 | 4: 2, 6: 0, 10: 2, 12: 0 |
| 28,29,30,31,38 | $7A32 | 21 | - | 0: 3E, 7: 24, 11: 24, 15: 24, 19: 24 | 0: 17, 2: 0, 2: 21, 4: 0 |
| 32,33,34,35,39 | $7A85 | 27 | - | 0: 1C, 2: 1C, 5: 24, 9: 24, 13: 24, 17: 24, 21: 24, 25: 24 | 1: 25, 2: 17, 3: 27, 5: 21, 6: 22, 7: 0, 11: 9, 15: 0, 15: 13, 19: 0, 19: 13, 23: 0, 23: 9, 27: 0 |

Timelines (hero 0, class 0, facing left):

whip power, stage 1 class 0, facing left: end of state at frame 41 (0.682 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-20 | 0 | - | tangible | 0, 0, 0 |
| 21-30 | 0 | - | intangible | 0, 0, 0 |
| 31-35 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 36-40 | 0 | - | intangible | 0, 0, 0 |
| 41-41 | 0, 0, -4 | - | tangible | 0, 0, 0 |

whip power, stage 2 class 0, facing left: end of state at frame 31 (0.516 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | 3, 0, 0 | - | tangible | 0, 0, 0 |
| 11-20 | -1, 0, 0 | - | intangible | 15, 0, 0 |
| 21-25 | -1, 0, 0 | -56, -11, 60, 16 | intangible | 5, 0, 0 |
| 26-30 | -1, 0, 0 | - | intangible | 0, 0, 0 |
| 31-31 | 0, 0, -4 | - | tangible | -5, 0, 0 |

whip power, stage 3 class 0, facing left: end of state at frame 56 (0.932 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 3, 0, 1 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 1 | - | tangible | 15, 0, 5 |
| 16-25 | -1, 0, 0 | - | intangible | 5, 0, 15 |
| 26-30 | -1, 0, -1 | -56, -26, 60, 16 | intangible | -5, 0, 15 |
| 31-35 | -1, 0, -2 | - | intangible | -10, 0, 10 |
| 36-45 | 0 | - | intangible | -15, 0, 0 |
| 46-50 | 0 | -56, -11, 60, 16 | intangible | -15, 0, 0 |
| 51-55 | 0 | - | intangible | -15, 0, 0 |
| 56-56 | 0, 0, -4 | - | tangible | -15, 0, 0 |

whip power, stage 4 class 0, facing left: end of state at frame 61 (1.015 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | - | intangible | 0, 0, 0 |
| 11-15 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 16-30 | 0 | - | intangible | 0, 0, 0 |
| 31-35 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 36-50 | 0 | - | intangible | 0, 0, 0 |
| 51-55 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 56-60 | 0 | - | intangible | 0, 0, 0 |
| 61-61 | 0, 0, -4 | - | tangible | 0, 0, 0 |

whip power, stage 5 class 0, facing left: end of state at frame 81 (1.348 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | - | intangible | 0, 0, 0 |
| 11-15 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 16-30 | 0 | - | intangible | 0, 0, 0 |
| 31-35 | 0 | 0, -58, 16, 40 | intangible | 0, 0, 0 |
| 36-50 | 0 | - | intangible | 0, 0, 0 |
| 51-55 | 0 | 56, -11, 60, 16 | intangible | 0, 0, 0 |
| 56-70 | 0 | - | intangible | 0, 0, 0 |
| 71-75 | 0 | 0, 46, 16, 48 | intangible | 0, 0, 0 |
| 76-80 | 0 | - | intangible | 0, 0, 0 |
| 81-81 | 0, 0, -4 | - | tangible | 0, 0, 0 |

whip power, stage 6 class 0, facing left: end of state at frame 81 (1.348 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | - | intangible | 0, 0, 0 |
| 11-15 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 16-20 | 0 | - | intangible | 0, 0, 0 |
| 21-30 | -2, 0, 0 | - | tangible | 0, 0, 0 |
| 31-40 | 0 | - | intangible | -20, 0, 0 |
| 41-45 | 0 | -56, -11, 60, 16 | intangible | -20, 0, 0 |
| 46-50 | 0 | - | intangible | -20, 0, 0 |
| 51-60 | -2, 0, 0 | - | tangible | -20, 0, 0 |
| 61-70 | 0 | - | intangible | -40, 0, 0 |
| 71-75 | 0 | -56, -11, 60, 16 | intangible | -40, 0, 0 |
| 76-80 | 0 | - | intangible | -40, 0, 0 |
| 81-81 | 0, 0, -4 | - | tangible | -40, 0, 0 |

whip power, stage 7 class 0, facing left: end of state at frame 106 (1.764 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0, 0, 1 | - | tangible | 0, 0, 0 |
| 11-20 | 0, 0, -1 | - | tangible | 0, 0, 10 |
| 21-25 | 0 | - | tangible | 0, 0, 0 |
| 26-35 | 0 | - | intangible | 0, 0, 0 |
| 36-40 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 41-55 | 0 | - | intangible | 0, 0, 0 |
| 56-60 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 61-75 | 0 | - | intangible | 0, 0, 0 |
| 76-80 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 81-95 | 0 | - | intangible | 0, 0, 0 |
| 96-100 | 0 | -56, -11, 60, 16 | intangible | 0, 0, 0 |
| 101-105 | 0 | - | intangible | 0, 0, 0 |
| 106-106 | 0, 0, -4 | - | tangible | 0, 0, 0 |

whip power, stage 8 class 0, facing left: end of state at frame 136 (2.263 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 3, 0, 1 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 1 | - | tangible | 15, 0, 5 |
| 16-25 | -1, 0, 0 | - | intangible | 5, 0, 15 |
| 26-30 | -1, 0, -1 | -56, -26, 60, 16 | intangible | -5, 0, 15 |
| 31-35 | -1, 0, -2 | - | intangible | -10, 0, 10 |
| 36-45 | 0 | - | intangible | -15, 0, 0 |
| 46-50 | 0 | -56, -11, 60, 16 | intangible | -15, 0, 0 |
| 51-55 | 0 | - | intangible | -15, 0, 0 |
| 56-65 | 0, 1, 0 | - | intangible | -15, 0, 0 |
| 66-70 | 0, 1, 0 | -56, -11, 60, 16 | intangible | -15, 10, 0 |
| 71-75 | 0, 1, 0 | - | intangible | -15, 15, 0 |
| 76-85 | 0, -1, 0 | - | intangible | -15, 20, 0 |
| 86-90 | 0, -1, 0 | -56, -11, 60, 16 | intangible | -15, 10, 0 |
| 91-105 | 0, -1, 0 | - | intangible | -15, 5, 0 |
| 106-110 | 0, -1, 0 | -56, -11, 60, 16 | intangible | -15, -10, 0 |
| 111-115 | 0, -1, 0 | - | intangible | -15, -15, 0 |
| 116-125 | 0, 1, 0 | - | intangible | -15, -20, 0 |
| 126-130 | 0, 1, 0 | -56, -11, 60, 16 | intangible | -15, -10, 0 |
| 131-135 | 0, 1, 0 | - | intangible | -15, -5, 0 |
| 136-136 | 0, 0, -4 | - | tangible | -15, 0, 0 |

### 2.4 Reach and hits [V]
Frame (counted from the release frame) in which a dummy standing straight ahead at the given distance was damaged (`-` = not hit within 260 frames), hero 0; stages 0, 4, 8:

| facing, stage | 14 px | 40 px | 70 px | 100 px | 130 px | 160 px | 200 px |
|---|---|---|---|---|---|---|---|
| up, stage 0 | 13 | 13 | 18 | - | - | - | - |
| up, stage 4 | 13 | 13 | 18 | - | - | - | - |
| up, stage 8 | 68 | 48 | 28 | 33 | 128 | - | - |
| down, stage 0 | - | 13 | 13 | 13 | - | - | - |
| down, stage 4 | - | 13 | 13 | 13 | - | - | - |
| down, stage 8 | 28 | 28 | 28 | 48 | 73 | - | - |
| right, stage 0 | - | 13 | 13 | - | - | - | - |
| right, stage 4 | - | 13 | 13 | - | - | - | - |
| right, stage 8 | 128 | 48 | 48 | 48 | 128 | - | - |
| left, stage 0 | - | 13 | 13 | - | - | - | - |
| left, stage 4 | - | 13 | 13 | - | - | - | - |
| left, stage 8 | 128 | 48 | 48 | 48 | - | - | - |

One hit per target per attack (the flag `E05A` of the hero is only cleared when the attack ends): in the 12 runs with two dummies in front of the hero (`two_targets` in the JSON) no dummy took more than one hit, and every dummy inside a box took exactly one. The damage frame is the first frame with `$56` = 0 at or after the frame in which the hit flag is set (section 7.1).

## 3. The projectile engine (bow, javelin, boomerang)

### 3.1 Launch [C, V]
- The animation scripts of the three weapons contain the one-byte op `0xFB` (`$C0:F987-F991`: `JSL $02BF1D`) once, at the step of the throw: bow step 4 of 7 (frame 21), javelin step 1 of 5 (frame 6), boomerang step 3 of 6 (frame 16) for the normal attack; the step differs per charged script (`structure.scripts[*].shot_steps` in the JSON).
- `$C2:BF1D` returns without doing anything when `E061 != 0` or when the **projectile kind** of the equipped weapon, `$7E:D030 + 0x40 * hero`, is 0. The kind is byte 3 of the 12-byte weapon row at `$D0:1000 + 12 * row`, copied by the equip routine (`$C0:EA7A`): whip 0 (nothing is launched, the op is not used), **bow 1, javelin 2, boomerang 3** (rows 54, 56, 58, 59) **or 5** (rows 55, 57, 60, 61, 62) [C, V: read from the ROM and from the object after the equip].
- Otherwise: `E02E = 0`, `E061` is incremented, entry 0 is initialised (`$C2:C021`), copied to entries 1 and 2 (`$C2:C000`), and the stage `E19B` selects how many are used: `E19B >= 6`: entry 1 gets the kind byte `| 0x50`, entry 2 `| 0xA0`; `3 <= E19B < 6`: only entry 1 (`| 0x50`); otherwise only entry 0. For the javelin the speed bytes of entries 1 and 2 are raised by 2 and 4. There is **no ammunition** in this path: it reads the stage and the facing and writes only the projectile table, `E061`, `E02E` and the sprite piece count `E08D` [C].
- The high five bits of the kind byte of an entry are a **delay counter**: `$C2:C26C` subtracts 8 per frame until they are 0, so entry 1 starts 10 frames after entry 0 (0x50 / 8) and entry 2 after 20 frames [V: delays 0, 10, 20].
- While `E061 != 0` the hero cannot start another swing (section 0, item 1), and the stage `E19B` is kept, so **the damage multiplier of the stage applies to every hit of the volley**; `E061` and `E19B` are cleared, and the gauge loaded, in the frame in which all three entries are empty (`$C2:C221`) [V].

### 3.2 Entry layout [C, V]
16 bytes per entry, at `$7E:D000 + 0x40 * hero + 0x10 * k`:

| offset | meaning |
|---|---|
| +0 | kind (1 bow, 2 javelin, 3 / 5 boomerang) in the low 3 bits; delay counter in the high 5 bits; 0 = free |
| +1 | facing: 0 up, 1 down, 2 right, 3 left, bit 7 = team flag copied from `E00B` bit 7 |
| +2, +4 | x and y position (words; world coordinates, y already includes the minus of the height) |
| +6 | height byte (30 for the bow and for up/down; 46 javelin and 38 boomerang for side facings at the start) |
| +7 | dying counter: set to 8 when the entry hit something or landed; counts down one per frame, the entry is freed at 0 |
| +8, +9, +A | flight parameters: +A = `0x0E - E19B` (the speed byte), +8 and +9 are accumulators that index a sine table at `$00:FD22` (+9 starts at 0x50 for the bow, 0x30 for the javelin, 0 for the boomerang); for the boomerang +8 reaching 0xFF starts the return phase |
| +B | copy of the initial height |
| +C, +D | piece offsets for drawing |
| +E, +F | OAM attribute / tile word of the sprite piece (tile number in the low 9 bits, flips in bits 14 and 15), changed by +2 when the entry starts to die |

The per-frame step `$C2:C27F` is: delayed -> count down; dying -> count down; otherwise hit test (`$C2:C526`), terrain lookup (`$C2:C183`, reads the tile attribute table at `$7F:B800/BC00` at the entry position; its use is not decoded), landing test (the height byte is compared with a threshold; the arrows and spears end their flight with the height byte at 15-16 [V]), then move. The position at spawn is offset from the hero by the facing: left `(-10, -14)` for the bow, `(-10, -30)` javelin, `(-10, -22)` boomerang; right the mirror; up `(0, -24)`, down `(0, -4)` for all three [V, all four facings, three heroes].

### 3.3 Flights without a target [V]
Hero 0 on open ground, a throw after the release at the stage shown; x and y are offsets from the hero's position in the same frame. Entries of one volley fly the same path, 10 frames apart. Left and right are mirror images (checked for all stages: exact for the bow and javelin; for the boomerang only the last frame differs, by 2 px, where the catch happens).

**Bow** (kind 1). The first step of the arrow is 8 px (481 px/s) and the step shrinks to 0 as the arrow lands; per-frame x displacement, stage 0: -8 -7 -6 -6 -5 -5 -4 -3 -3 -2 -2 -2, then 0 (the arrow stays on the ground, in its dying state, 8 frames); stage 8: -8 -8 -8 -7 -7 -7 -6 -6 -6 -6 -5 -5 -5 -5 -4 -4 -4 -4 -3 -3 -3 -3 -2, then 0. The stored y rises by 3 px (stage 0) or 7 px (stage 8) and falls back (the arc), the height byte goes 30 -> 33 -> 15 (stage 0) or 30 -> 37 -> 15 (stage 8).

| stage | entries | delays (frames) | flight frames per entry (first live..last) | end offset from the hero, left (x, y) | end offset, up (x, y) | end offset, down (x, y) | speed byte |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 21..41 | (-63, 1) | (0, -89) | (0, 49) | 14 |
| 1 | 1 | 0 | 21..42 | (-68, 2) | (0, -95) | (0, 54) | 13 |
| 2 | 1 | 0 | 21..42 | (-72, 0) | (0, -99) | (0, 58) | 12 |
| 3 | 2 | 0, 10 | 21..43, 31..53 | (-75, 0) | (0, -103) | (0, 61) | 11, 11 |
| 4 | 2 | 0, 10 | 21..45, 31..55 | (-85, 3) | (0, -115) | (0, 71) | 10, 10 |
| 5 | 2 | 0, 10 | 21..45, 31..55 | (-90, 0) | (0, -120) | (0, 76) | 9, 9 |
| 6 | 3 | 0, 10, 20 | 21..47, 31..57, 41..67 | (-100, 0) | (0, -132) | (0, 86) | 8, 8, 8 |
| 7 | 3 | 0, 10, 20 | 21..49, 31..59, 41..69 | (-111, 0) | (0, -145) | (0, 97) | 7, 7, 7 |
| 8 | 3 | 0, 10, 20 | 21..52, 31..62, 41..72 | (-129, 1) | (0, -166) | (0, 115) | 6, 6, 6 |

**Javelin** (kind 2), same horizontal steps, a higher arc (the height byte climbs from 46 to 53 at stage 0 and to 64 at stage 8, and falls to 16 / 15):

| stage | entries | delays (frames) | flight frames per entry (first live..last) | end offset from the hero, left (x, y) | end offset, up (x, y) | end offset, down (x, y) | speed byte |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 6..33 | (-68, 0) | (0, -95) | (0, 52) | 14 |
| 1 | 1 | 0 | 31..59 | (-73, 1) | (0, -101) | (0, 57) | 13 |
| 2 | 1 | 0 | 31..60 | (-80, 0) | (0, -108) | (0, 63) | 12 |
| 3 | 2 | 0, 10 | 16..46, 26..54 | (-84, 1) | (0, -112) | (0, 66) | 11, 13 |
| 4 | 2 | 0, 10 | 41..73, 51..80 | (-94, 0) | (0, -124) | (0, 76) | 10, 12 |
| 5 | 2 | 0, 10 | 31..65, 41..71 | (-103, 0) | (0, -135) | (0, 85) | 9, 11 |
| 6 | 3 | 0, 10, 20 | 26..66, 36..72, 46..79 | (-115, 0) | (0, -170) | (0, 84) | 8, 10, 12 |
| 7 | 3 | 0, 10, 20 | 51..90, 61..95, 71..101 | (-126, 0) | (0, -163) | (0, 108) | 7, 9, 11 |
| 8 | 3 | 0, 10, 20 | 46..90, 56..93, 66..98 | (-147, 1) | (0, -189) | (0, 129) | 6, 8, 10 |

**Boomerang** (kind 3 and 5 gave the same flights for the stages and facings compared): outbound the x steps are those of the bow, but the boomerang does not fall; at the end of the outbound phase (stage 0: 68 px out, after 18 frames; stage 8: 166 px out after 41 frames) it rests 4-5 frames and then returns with growing steps (stage 0: 1 1 1 2 2 3 3 3 4 4 4 5 5 5 5 6 6 6, stage 8 up to 7) **towards the hero's current position** (the path is relative to the hero in the engine: a hero who walks is followed) and disappears when it is within 8 px of the hero's centre (`$C2:C64E`). Vertical offset: -22 outbound, -14 on the way back. The flight lasts 40 frames at stage 0 (left), 74 at stage 8; up 42 and 79:

| stage | entries | delays (frames) | flight frames per entry (first live..last) | end offset from the hero, left (x, y) | end offset, up (x, y) | end offset, down (x, y) | speed byte |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 16..55 | (-2, -14) | (0, -22) | (0, -14) | 14 |
| 1 | 1 | 0 | 31..71 | (-7, -14) | (0, -21) | (0, -14) | 13 |
| 2 | 1 | 0 | 36..77 | (-20, -14) | (0, -37) | (0, 6) | 12 |
| 3 | 2 | 0, 10 | 36..82, 46..92 | (-5, -14) | (0, -22) | (0, -9) | 11, 11 |
| 4 | 2 | 0, 10 | 61..111, 71..121 | (-1, -14) | (0, -20) | (0, -14) | 10, 10 |
| 5 | 2 | 0, 10 | 41..95, 51..105 | (-4, -14) | (0, -19) | (0, -10) | 9, 9 |
| 6 | 3 | 0, 10, 20 | 76..135, 86..145, 96..155 | (-1, -14) | (0, -18) | (0, -14) | 8, 8, 8 |
| 7 | 3 | 0, 10, 20 | 36..102, 46..112, 56..122 | (-2, -14) | (0, -22) | (0, -12) | 7, 7, 7 |
| 8 | 3 | 0, 10, 20 | 51..124, 61..134, 71..144 | (-16, -14) | (0, -33) | (0, 1) | 6, 6, 6 |

For the boomerang the "end offset" is the last frame before the catch (about the hero's position: the catch happens within 8 px). Hero 1 facing down gave different paths at stages 2 and 8 from hero 0 (the other 22 comparisons were identical); the cause was not traced (section 10).

## 4. Bow (type 5)

### 4.1 Normal attack [V]
| facing | swing end | hero free again | first step | weapon box active (frames) | projectile first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|
| left | 36 | 43 | 1 | - | 21 | 47@11 9@21 A@36 |
| right | 36 | 43 | 1 | - | 21 | 47@11 9@21 A@36 |
| up | 36 | 43 | 1 | - | 21 | 47@11 9@21 A@36 |
| down | 36 | 43 | 1 | - | 21 | 47@11 9@21 A@36 |

Script `$D1:7AFD`, 7 steps: sound 0x47 (draw) at step 2 (frame 11), sound 0x09 and the launch (`0xFB`) at step 4 (frame 21), sound 0x0A at step 7 (frame 36, the end). The hero has **no movement and no weapon box** during the whole swing (body box non-empty throughout).

bow normal, animation id 0, facing left: end of state at frame 36 (0.599 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-35 | 0 | - | tangible | 0, 0, 0 |
| 36-36 | 0, 0, -4 | - | tangible | 0, 0, 0 |

### 4.2 Charged attacks [V]
There is no separate charged animation: the 40 animation ids are one script, so at every stage the hero plays the same 36-frame shot, and the stage only changes the number of arrows, their speed byte (`14 - stage`) and range (section 3.3). Swing end and "free again":

| stage | frames to swing end (s) | hero free again (E061 = 0) | steps | move px (x, y) | max height | weapon box frames (first..last) | projectile entries: first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|
| 0 | 36 (0.599) | 43 | 7 | (0, 0) | 0 | 0 | 21 | 47@11 9@21 A@36 |
| 1 | 36 (0.599) | 44 | 7 | (0, 0) | 0 | 0 | 21 | 47@11 9@21 A@36 |
| 2 | 36 (0.599) | 44 | 7 | (0, 0) | 0 | 0 | 21 | 47@11 9@21 A@36 |
| 3 | 36 (0.599) | 55 | 7 | (0, 0) | 0 | 0 | 21, 31 | 47@11 9@21 A@36 |
| 4 | 36 (0.599) | 57 | 7 | (0, 0) | 0 | 0 | 21, 31 | 47@11 9@21 A@36 |
| 5 | 36 (0.599) | 57 | 7 | (0, 0) | 0 | 0 | 21, 31 | 47@11 9@21 A@36 |
| 6 | 36 (0.599) | 69 | 7 | (0, 0) | 0 | 0 | 21, 31, 41 | 47@11 9@21 A@36 |
| 7 | 36 (0.599) | 71 | 7 | (0, 0) | 0 | 0 | 21, 31, 41 | 47@11 9@21 A@36 |
| 8 | 36 (0.599) | 74 | 7 | (0, 0) | 0 | 0 | 21, 31, 41 | 47@11 9@21 A@36 |

(The frame counts are the same in all four facings.)

## 5. Javelin (type 7)

### 5.1 Normal attack [V]
| facing | swing end | hero free again | first step | weapon box active (frames) | projectile first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|
| left | 26 | 35 | 1 | - | 6 | 2@6 |
| right | 26 | 35 | 1 | - | 6 | 2@6 |
| up | 26 | 31 | 1 | - | 6 | 2@6 |
| down | 26 | 31 | 1 | - | 6 | 2@6 |

Script `$D1:7D92`, 5 steps: the spear is thrown at step 1 (frame 6) with sound 0x02; the hero then stays 20 frames in the follow-through (swing end at 26) while the spear flies; the hero is free again when the spear has landed and its 8 dying frames are over (frame 35 side, 31 up and down). Body box empty from frame 1 to 25.

javelin normal, animation id 0, facing left: end of state at frame 26 (0.433 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-25 | 0 | - | intangible | 0, 0, 0 |
| 26-26 | 0, 0, -4 | - | tangible | 0, 0, 0 |

### 5.2 Charged attacks [V]
One script per stage (ids `4s .. 4s+3` share it); the throw (`0xFB`) comes at a step that depends on the stage.

| animation ids | script (bank $D1) | steps | shot (op FB) at step | sounds (step: id) | velocity presets (step: k) |
|---|---|---|---|---|---|
| 0,1,2,3 | $7D92 | 5 | 1 | 1: 2 | - |
| 4,5,6,7 | $7DE6 | 10 | 6 | 1: 1B, 3: 1B, 6: 2 | - |
| 8,9,10,11 | $7E1F | 10 | 6 | 0: 3E, 6: 2 | - |
| 12,13,14,15 | $7E34 | 7 | 3 | 3: 2 | 1: 7, 2: 25, 2: 1, 7: 25 |
| 16,17,18,19 | $7EB5 | 12 | 8 | 0: 1C, 2: 1C, 8: 2 | 1: 25, 2: 17, 3: 27, 5: 21, 6: 22, 7: 0 |
| 20,21,22,23,36 | $7EFD | 10 | 6 | 1: 1B, 3: 1B, 6: 2 | - |
| 24,25,26,27,37 | $7F12 | 10 | 5 | 1: 3E, 3: 3E, 5: 2 | 1: 17, 4: 27, 7: 21, 10: 27 |
| 28,29,30,31,38 | $7FCC | 14 | 10 | 1: 19, 3: 19, 5: 19, 7: 19, 10: 2 | - |
| 32,33,34,35,39 | $7FE1 | 11 | 9 | 3: 1B, 5: 1B, 7: 1B, 9: 2 | 1: 7, 2: 25, 5: 0, 5: 1, 7: 0, 9: 0 |

| stage | frames to swing end (s) | hero free again (E061 = 0) | steps | move px (x, y) | max height | weapon box frames (first..last) | projectile entries: first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|
| 0 | 26 (0.433) | 35 | 5 | (0, 0) | 0 | 0 | 6 | 2@6 |
| 1 | 51 (0.849) | 61 | 10 | (0, 0) | 0 | 0 | 31 | 1B@6 1B@16 2@31 |
| 2 | 51 (0.849) | 62 | 10 | (0, 0) | 0 | 0 | 31 | 3E@1 2@31 |
| 3 | 36 (0.599) | 56 | 7 | (-10, 0) | 0 | 0 | 16, 26 | 2@16 |
| 4 | 61 (1.015) | 82 | 12 | (-15, 0) | 15 | 0 | 41, 51 | 1C@1 1C@11 2@41 |
| 5 | 51 (0.849) | 73 | 10 | (0, 0) | 0 | 20 (6..25) | 31, 41 | 1B@6 1B@16 2@31 |
| 6 | 51 (0.849) | 81 | 10 | (0, 0) | 15 | 0 | 26, 36, 46 | 3E@6 3E@16 2@26 |
| 7 | 71 (1.181) | 103 | 14 | (0, 0) | 0 | 40 (6..45) | 51, 61, 71 | 19@6 19@16 19@26 19@36 2@51 |
| 8 | 56 (0.932) | 100 | 11 | (-15, 0) | 10 | 0 | 46, 56, 66 | 1B@16 1B@26 1B@36 2@46 |

Displacement of the hero (sum of the velocities, class 0):

| stage | left (x, y) | right | up | down | frames to swing end left / up | hero free again left / up |
|---|---|---|---|---|---|---|
| 1 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 51 / 51 | 61 / 57 |
| 2 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 51 / 51 | 62 / 58 |
| 3 | (-10, 0) | (10, 0) | (0, -10) | (0, 10) | 36 / 36 | 56 / 52 |
| 4 | (-15, 0) | (15, 0) | (0, -15) | (0, 15) | 61 / 61 | 82 / 78 |
| 5 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 51 / 51 | 73 / 69 |
| 6 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 51 / 51 | 81 / 77 |
| 7 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 71 / 71 | 103 / 99 |
| 8 | (-15, 0) | (15, 0) | (0, -15) | (0, 15) | 56 / 56 | 100 / 96 |

Timelines (hero 0, class 0, facing left):

javelin power, stage 1 class 0, facing left: end of state at frame 51 (0.849 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-25 | 0 | - | tangible | 0, 0, 0 |
| 26-50 | 0 | - | intangible | 0, 0, 0 |
| 51-51 | 0, 0, -4 | - | tangible | 0, 0, 0 |

javelin power, stage 2 class 0, facing left: end of state at frame 51 (0.849 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-25 | 0 | - | tangible | 0, 0, 0 |
| 26-50 | 0 | - | intangible | 0, 0, 0 |
| 51-51 | 0, 0, -4 | - | tangible | 0, 0, 0 |

javelin power, stage 3 class 0, facing left: end of state at frame 36 (0.599 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | 3, 0, 0 | - | tangible | 0, 0, 0 |
| 11-35 | -1, 0, 0 | - | intangible | 15, 0, 0 |
| 36-36 | 0, 0, -4 | - | tangible | -10, 0, 0 |

javelin power, stage 4 class 0, facing left: end of state at frame 61 (1.015 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 3, 0, 1 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 1 | - | tangible | 15, 0, 5 |
| 16-25 | -1, 0, 0 | - | intangible | 5, 0, 15 |
| 26-30 | -1, 0, -1 | - | intangible | -5, 0, 15 |
| 31-35 | -1, 0, -2 | - | intangible | -10, 0, 10 |
| 36-60 | 0 | - | intangible | -15, 0, 0 |
| 61-61 | 0, 0, -4 | - | tangible | -15, 0, 0 |

javelin power, stage 5 class 0, facing left: end of state at frame 51 (0.849 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-25 | 0 | 0, -26, 24, 24 | intangible | 0, 0, 0 |
| 26-50 | 0 | - | intangible | 0, 0, 0 |
| 51-51 | 0, 0, -4 | - | tangible | 0, 0, 0 |

javelin power, stage 6 class 0, facing left: end of state at frame 51 (0.849 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-20 | 0, 0, 1 | - | intangible | 0, 0, 0 |
| 21-35 | 0 | - | intangible | 0, 0, 15 |
| 36-50 | 0, 0, -1 | - | tangible | 0, 0, 15 |
| 51-51 | 0, 0, -4 | - | tangible | 0, 0, 0 |

javelin power, stage 7 class 0, facing left: end of state at frame 71 (1.181 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | 0 | -20, -11, 32, 12 | intangible | 0, 0, 0 |
| 11-15 | 0 | 0, -26, 12, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | 20, -11, 32, 12 | intangible | 0, 0, 0 |
| 21-25 | 0 | 0, 10, 12, 32 | intangible | 0, 0, 0 |
| 26-30 | 0 | -20, -11, 32, 12 | intangible | 0, 0, 0 |
| 31-35 | 0 | 0, -26, 12, 32 | intangible | 0, 0, 0 |
| 36-40 | 0 | 20, -11, 32, 12 | intangible | 0, 0, 0 |
| 41-45 | 0 | 0, 10, 12, 32 | intangible | 0, 0, 0 |
| 46-70 | 0 | - | intangible | 0, 0, 0 |
| 71-71 | 0, 0, -4 | - | tangible | 0, 0, 0 |

javelin power, stage 8 class 0, facing left: end of state at frame 56 (0.932 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | 3, 0, 0 | - | tangible | 0, 0, 0 |
| 11-15 | 0 | - | tangible | 15, 0, 0 |
| 16-25 | -1, 0, 1 | - | intangible | 15, 0, 0 |
| 26-35 | -1, 0, 0 | - | intangible | 5, 0, 10 |
| 36-37 | -1, 0, -7 | - | intangible | -5, 0, 10 |
| 38-45 | -1, 0, 0 | - | intangible | -7, 0, 0 |
| 46-55 | 0 | - | intangible | -15, 0, 0 |
| 56-56 | 0, 0, -4 | - | tangible | -15, 0, 0 |

## 6. Boomerang (type 6)

### 6.1 Normal attack [V]
| facing | swing end | hero free again | first step | weapon box active (frames) | projectile first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|
| left | 31 | 57 | 1 | - | 16 | 2@6 25@16 |
| right | 31 | 57 | 1 | - | 16 | 2@6 25@16 |
| up | 31 | 59 | 1 | - | 16 | 2@6 25@16 |
| down | 31 | 57 | 1 | - | 16 | 2@6 25@16 |

Script `$D1:7B10`, 6 steps: sound 0x02 at step 1, throw at step 3 (frame 16) with sound 0x25. Body box empty from frame 1 to 30. The boomerang is back (and the hero free) at frame 57 (side), 59 (up), 57 (down) for hero 0.

boomerang normal, animation id 0, facing left: end of state at frame 31 (0.516 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-30 | 0 | - | intangible | 0, 0, 0 |
| 31-31 | 0, 0, -4 | - | tangible | 0, 0, 0 |

### 6.2 Charged attacks [V]
| animation ids | script (bank $D1) | steps | shot (op FB) at step | sounds (step: id) | velocity presets (step: k) |
|---|---|---|---|---|---|
| 0,1,2,3 | $7B10 | 6 | 3 | 1: 2, 3: 25 | - |
| 4,5,6,7 | $7B7C | 9 | 6 | 0: 2, 4: 2, 6: 25 | - |
| 8,9,10,11 | $7B91 | 10 | 7 | 5: 2, 7: 25 | 1: 5, 3: 0, 4: 1, 10: 0 |
| 12,13,14,15 | $7BBB | 7 | 7 | 0: 1C, 7: 25 | 1: 25, 2: 17, 3: 27, 5: 21, 6: 22, 7: 0 |
| 16,17,18,19 | $7C1B | 15 | 12 | 0: 2, 3: 2, 6: 2, 10: 2, 12: 25 | - |
| 20,21,22,23,36 | $7C78 | 11 | 8 | 1: 19, 6: 2, 8: 25 | - |
| 24,25,26,27,37 | $7CAB | 18 | 15 | 0: 2, 0: 2, 3: 2, 6: 2, 6: 2, 9: 2, 13: 2, 15: 25 | - |
| 28,29,30,31,38 | $7CED | 9 | 7 | 1: 3E, 7: 25 | 3: 0, 7: 0 |
| 32,33,34,35,39 | $7D53 | 13 | 10 | 1: 1C, 1: 2, 4: 2, 8: 2, 10: 25 | 1: 17, 4: 27, 4: 21, 7: 27, 7: 1, 13: 0 |

| stage | frames to swing end (s) | hero free again (E061 = 0) | steps | move px (x, y) | max height | weapon box frames (first..last) | projectile entries: first live frame | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|
| 0 | 31 (0.516) | 57 | 6 | (0, 0) | 0 | 0 | 16 | 2@6 25@16 |
| 1 | 46 (0.765) | 73 | 9 | (0, 0) | 0 | 15 (1..15) | 31 | 2@1 2@21 25@31 |
| 2 | 51 (0.849) | 79 | 10 | (-20, 0) | 0 | 5 (16..20) | 36 | 2@26 25@36 |
| 3 | 36 (0.599) | 94 | 7 | (-15, 0) | 15 | 20 (16..35) | 36, 46 | 1C@1 25@36 |
| 4 | 76 (1.265) | 123 | 15 | (0, 0) | 0 | 45 (1..45) | 61, 71 | 2@1 2@16 2@31 2@51 25@61 |
| 5 | 56 (0.932) | 107 | 11 | (0, 0) | 0 | 0 | 41, 51 | 19@6 2@31 25@41 |
| 6 | 91 (1.514) | 157 | 18 | (0, 0) | 0 | 60 (1..60) | 76, 86, 96 | 2@1 2@1 2@16 2@31 2@31 2@46 2@66 25@76 |
| 7 | 46 (0.765) | 124 | 9 | (-20, 0) | 10 | 0 | 36, 46, 56 | 3E@6 25@36 |
| 8 | 66 (1.098) | 146 | 13 | (-30, 0) | 15 | 30 (6..35) | 51, 61, 71 | 1C@6 2@6 2@21 2@41 25@51 |

Displacement of the hero (sum of the velocities, class 0):

| stage | left (x, y) | right | up | down | frames to swing end left / up | hero free again left / up |
|---|---|---|---|---|---|---|
| 1 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 46 / 46 | 73 / 76 |
| 2 | (-20, 0) | (20, 0) | (0, -20) | (0, 20) | 51 / 51 | 79 / 82 |
| 3 | (-15, 0) | (15, 0) | (0, -15) | (0, 15) | 36 / 36 | 94 / 97 |
| 4 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 76 / 76 | 123 / 126 |
| 5 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 56 / 56 | 107 / 111 |
| 6 | (0, 0) | (0, 0) | (0, 0) | (0, 0) | 91 / 91 | 157 / 161 |
| 7 | (-20, 0) | (20, 0) | (0, -30) | (0, 20) | 46 / 46 | 124 / 128 |
| 8 | (-30, 0) | (30, 0) | (0, -30) | (0, 30) | 66 / 66 | 146 / 151 |

Timelines (hero 0, class 0, facing left):

boomerang power, stage 1 class 0, facing left: end of state at frame 46 (0.765 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -8, -30, 16, 16 | intangible | 0, 0, 0 |
| 6-10 | 0 | -12, -18, 28, 28 | intangible | 0, 0, 0 |
| 11-15 | 0 | -12, -3, 28, 28 | intangible | 0, 0, 0 |
| 16-45 | 0 | - | intangible | 0, 0, 0 |
| 46-46 | 0, 0, -4 | - | tangible | 0, 0, 0 |

boomerang power, stage 2 class 0, facing left: end of state at frame 51 (0.849 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-15 | 1, 0, 0 | - | tangible | 0, 0, 0 |
| 16-20 | 0 | 8, -7, 20, 20 | intangible | 10, 0, 0 |
| 21-50 | -1, 0, 0 | - | intangible | 10, 0, 0 |
| 51-51 | 0, 0, -4 | - | tangible | -20, 0, 0 |

boomerang power, stage 3 class 0, facing left: end of state at frame 36 (0.599 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 3, 0, 1 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 1 | - | tangible | 15, 0, 5 |
| 16-25 | -1, 0, 0 | -8, -45, 16, 16 | intangible | 5, 0, 15 |
| 26-30 | -1, 0, -1 | -12, -33, 28, 28 | intangible | -5, 0, 15 |
| 31-35 | -1, 0, -2 | -12, -13, 28, 28 | intangible | -10, 0, 10 |
| 36-36 | 0, 0, -4 | - | tangible | -15, 0, 0 |

boomerang power, stage 4 class 0, facing left: end of state at frame 76 (1.265 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -8, -30, 16, 16 | intangible | 0, 0, 0 |
| 6-10 | 0 | -12, -18, 28, 28 | intangible | 0, 0, 0 |
| 11-15 | 0 | -12, -3, 28, 28 | intangible | 0, 0, 0 |
| 16-20 | 0 | -8, -7, 20, 20 | intangible | 0, 0, 0 |
| 21-25 | 0 | 4, -3, 32, 20 | intangible | 0, 0, 0 |
| 26-30 | 0 | 20, -11, 24, 24 | intangible | 0, 0, 0 |
| 31-35 | 0 | -8, -30, 16, 16 | intangible | 0, 0, 0 |
| 36-40 | 0 | -12, -18, 28, 28 | intangible | 0, 0, 0 |
| 41-45 | 0 | -12, -3, 28, 28 | intangible | 0, 0, 0 |
| 46-75 | 0 | - | intangible | 0, 0, 0 |
| 76-76 | 0, 0, -4 | - | tangible | 0, 0, 0 |

boomerang power, stage 5 class 0, facing left: end of state at frame 56 (0.932 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-55 | 0 | - | intangible | 0, 0, 0 |
| 56-56 | 0, 0, -4 | - | tangible | 0, 0, 0 |

boomerang power, stage 6 class 0, facing left: end of state at frame 91 (1.514 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -16, -15, 20, 20 | intangible | 0, 0, 0 |
| 6-10 | 0 | -8, -30, 24, 24 | intangible | 0, 0, 0 |
| 11-15 | 0 | 12, -30, 24, 24 | intangible | 0, 0, 0 |
| 16-20 | 0 | 16, -7, 20, 20 | intangible | 0, 0, 0 |
| 21-25 | 0 | 8, -3, 24, 24 | intangible | 0, 0, 0 |
| 26-30 | 0 | -12, -3, 24, 24 | intangible | 0, 0, 0 |
| 31-35 | 0 | -16, -15, 20, 20 | intangible | 0, 0, 0 |
| 36-40 | 0 | -8, -30, 24, 24 | intangible | 0, 0, 0 |
| 41-45 | 0 | 12, -30, 24, 24 | intangible | 0, 0, 0 |
| 46-50 | 0 | 16, -7, 20, 20 | intangible | 0, 0, 0 |
| 51-55 | 0 | 8, -3, 24, 24 | intangible | 0, 0, 0 |
| 56-60 | 0 | -12, -3, 24, 24 | intangible | 0, 0, 0 |
| 61-90 | 0 | - | intangible | 0, 0, 0 |
| 91-91 | 0, 0, -4 | - | tangible | 0, 0, 0 |

boomerang power, stage 7 class 0, facing left: end of state at frame 46 (0.765 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 1 | - | intangible | 0, 0, 0 |
| 16-25 | 0 | - | intangible | -10, 0, 10 |
| 26-27 | -1, 0, -7 | - | intangible | -10, 0, 10 |
| 28-35 | -1, 0, 0 | - | intangible | -12, 0, 0 |
| 36-45 | 0 | - | intangible | -20, 0, 0 |
| 46-46 | 0, 0, -4 | - | tangible | -20, 0, 0 |

boomerang power, stage 8 class 0, facing left: end of state at frame 66 (1.098 s)

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | 0, 0, 1 | -16, -15, 20, 20 | intangible | 0, 0, 0 |
| 11-15 | 0, 0, 1 | -8, -35, 24, 24 | intangible | 0, 0, 5 |
| 16-20 | 0, 0, 1 | 12, -40, 24, 24 | intangible | 0, 0, 10 |
| 21-25 | 0, 0, -1 | 16, -22, 20, 20 | intangible | 0, 0, 15 |
| 26-30 | 0, 0, -1 | 8, -13, 24, 24 | intangible | 0, 0, 10 |
| 31-35 | 0, 0, -1 | -12, -8, 24, 24 | intangible | 0, 0, 5 |
| 36-65 | -1, 0, 0 | - | intangible | 0, 0, 0 |
| 66-66 | 0, 0, -4 | - | tangible | -30, 0, 0 |

Stages 1, 2, 4, 6 and 8 have a weapon box of the hero (as listed in the table above: frames with a non-empty box); the boxes of these melee parts are listed by the timelines above; they were not measured against targets one by one, but the hit-model test of section 7.1 shows them at work (targets damaged at frames 8-18 of the stage 8 attack, 33 frames before the first launch).

## 7. Hits, damage, status

### 7.1 When a projectile hits [V, C]
`$C2:C5B4` (called from the step `$C2:C526`) tests the entry against the monster slots 3, 4, 5 in this order (the hero's team flag must differ from the monster's `E00B` bit 7; monsters whose body box `E0CA/E0CB` is 0 are skipped; bits of `E02E` mark monsters already hit). A monster is hit when, with `(px, py)` = entry position - scroll (`$A8/$AA`) and the monster's screen position `(tx, ty)` = `E020`, `E022 - (E074 & 0x7F) - E045 - 1`:

`2 |tx - px| < wp + tw`   and   `2 |ty - py| < hp + th`   (both differences also < 96),

with `(tw, th)` = the monster's body box `E0CA, E0CB` and **`wp = hp` = 16 px for the bow and boomerang, 32 px for the javelin** (`$C2:C5C9-C5D6`). The effect is that of a 16 x 16 (32 x 32) box centred on the entry against the monster's body box. The test was applied to recorded flights against 80 random monster positions per case (stage 0 and 8 each, flights recorded frame by frame, the monster's own height and box taken from the frame): predicted hit or no hit equals the observed damage in all cases except those in the table (bow stage 0: one unexplained hit at (-59, +31); boomerang stage 8: five damaged targets that the model does not predict and two that were damaged earlier than predicted, all in frames 8-18, before the first launch at frame 51, i.e. hits of the hero's own weapon box, section 6.2):

| weapon | stage | placements | damaged | mismatches | damage frame minus test frame |
|---|---|---|---|---|---|
| bow | 0 | 80 | 21 | 1 | 0,1,2,3,4,5 |
| bow | 8 | 80 | 36 | 0 | 0,1,2,3,4,5 |
| boomerang | 0 | 80 | 12 | 0 | 0,1,2,3,4 |
| boomerang | 8 | 80 | 49 | 5 | -39,0,1,2,3,4 |
| javelin | 0 | 80 | 40 | 0 | 0,1,2,3,4 |
| javelin | 8 | 80 | 70 | 0 | 0,1,2,3,4 |

The test is made at the start of the entry's step in frame `i` with the position it had at the end of frame `i - 1` and the monster's fields of frame `i`. **The damage lands in the first frame with `$56` = 0 at or after the test frame** (the monster's combat tick): 0-5 frames after it (offsets 0-5 measured; 0 and 5 both occur when the test frame itself has `$56` = 0) [V]. Measured damage frames for a dummy straight ahead of a left-facing hero 30 px away: bow 23, javelin 8 (stage 0), boomerang 18 (frames from the press).

Reach of one normal throw / charged volley (frame of the first damage for a dummy straight ahead; `-` = no hit; see the JSON for all facings):

**Bow**

| facing, stage | 14 px | 40 px | 70 px | 100 px | 130 px | 160 px | 200 px |
|---|---|---|---|---|---|---|---|
| up, stage 0 | 23 | 23 | 28 | - | - | - | - |
| up, stage 4 | 23 | 23 | 28 | 38 | - | - | - |
| up, stage 8 | 23 | 23 | 28 | 33 | 38 | 48 | - |
| down, stage 0 | 23 | 28 | 33 | - | - | - | - |
| down, stage 4 | 23 | 28 | 33 | 38 | - | - | - |
| down, stage 8 | 23 | 28 | 33 | 33 | 38 | - | - |
| right, stage 0 | 23 | 28 | 33 | - | - | - | - |
| right, stage 4 | 23 | 28 | 33 | 48 | - | - | - |
| right, stage 8 | 23 | 28 | 28 | 33 | 43 | - | - |
| left, stage 0 | 23 | 28 | 33 | - | - | - | - |
| left, stage 4 | 23 | 28 | 33 | 48 | - | - | - |
| left, stage 8 | 23 | 28 | 28 | 33 | 43 | - | - |

**Javelin**

| facing, stage | 14 px | 40 px | 70 px | 100 px | 130 px | 160 px | 200 px |
|---|---|---|---|---|---|---|---|
| up, stage 0 | 8 | 13 | 13 | 18 | - | - | - |
| up, stage 4 | 43 | 43 | 48 | 48 | 53 | - | - |
| up, stage 8 | 48 | 48 | 53 | 53 | 58 | 63 | 78 |
| down, stage 0 | 8 | 8 | 13 | - | - | - | - |
| down, stage 4 | 43 | 43 | 48 | 53 | 63 | - | - |
| down, stage 8 | 48 | 48 | 53 | 58 | 63 | 68 | - |
| right, stage 0 | 8 | 8 | 13 | - | - | - | - |
| right, stage 4 | 43 | 43 | 48 | 58 | 63 | - | - |
| right, stage 8 | 48 | 48 | 63 | 68 | 68 | 68 | - |
| left, stage 0 | 8 | 8 | 13 | - | - | - | - |
| left, stage 4 | 43 | 43 | 48 | 58 | 63 | - | - |
| left, stage 8 | 48 | 48 | 63 | 68 | 68 | 68 | - |

**Boomerang** (the very early frames, 3-18, are hits by the hero's own weapon box in the stages that have one, section 6.2; the projectile arrives from about frame 50 at stages 4-8)

| facing, stage | 14 px | 40 px | 70 px | 100 px | 130 px | 160 px | 200 px |
|---|---|---|---|---|---|---|---|
| up, stage 0 | 18 | 18 | 23 | - | - | - | - |
| up, stage 4 | 3 | 3 | 73 | 78 | 83 | - | - |
| up, stage 8 | 8 | 18 | 58 | 63 | 68 | 73 | 78 |
| down, stage 0 | 18 | 23 | 33 | - | - | - | - |
| down, stage 4 | 8 | 13 | 68 | 83 | - | - | - |
| down, stage 8 | 8 | 53 | 58 | 63 | 68 | 78 | 113 |
| right, stage 0 | 18 | 23 | 28 | - | - | - | - |
| right, stage 4 | 8 | 68 | 73 | 78 | - | - | - |
| right, stage 8 | 8 | 53 | 58 | 63 | 68 | 78 | - |
| left, stage 0 | 18 | 23 | 28 | - | - | - | - |
| left, stage 4 | 8 | 68 | 73 | 78 | - | - | - |
| left, stage 8 | 8 | 53 | 58 | 63 | 68 | 78 | - |

### 7.2 What happens to the projectile [V]
- **Bow and javelin: the first target stops the entry.** The entry enters the dying state in the frame of the hit (dying counter 8 -> 0, 8 frames, sprite piece changes); the next entries of the volley go on. Two dummies one behind the other (-30 and -60 px): stage 0 damages only the near one (no second damage); stage 3 / 6 / 8 damage the far one with a later entry (bow: 16 frames later) [V]. Targets side by side (-45 px, 12 px above and below), stage 3: both damaged, the second 11 frames after the first (the second entry).
- **Boomerang: it flies through targets.** Two dummies in a line took one hit each, in the same frames (stage 3: frames 33 and 34), from the same boomerang, which went on. On the way back the entry is **not tested**: a dummy placed on a returning boomerang (E02E cleared) took 0 damage, the same placement on the way out took damage [V]. The engine branch is `$C2:C526`: `D008 == 0xFF` -> catch test `$C2:C64E` only [C].
- The projectile is also freed when it lands (arrows, spears: the dying state starts when the height byte reaches 15-16) or when the boomerang is caught (within 8 px of the hero).

### 7.3 One hit per target per volley [V]
The write of the monster's hit flag (`$C2:C649`, `ORA $E059,X`) was counted for a dummy 30 px in front of the hero for stages 3 and 8, once with the game's `E02E` and once with `E02E` forced to 0 every frame:

| weapon | stage | frames of the hit-flag writes, game mask | with E02E forced to 0 |
|---|---|---|---|
| bow | 3 | [23] | [23, 33] |
| bow | 8 | [23] | [23, 33, 43] |
| javelin | 3 | [29] | [29] |
| javelin | 8 | [47] | [47, 57, 67] |
| boomerang | 3 | [37] | [37, 38, 39, 40, 47, 48, 49, 50] |
| boomerang | 8 | [52] | [52, 53, 54, 62, 63, 64, 72, 73, 74] |

So the mask `E02E` is what makes a volley hit a target once (bit `k` of `E02E` = monster slot `3 + k`; for the bow the value after hitting the slot-3 monster was 1, after hitting slots 3 and 4, 3 [V]). (Without the mask a second flag would also be ignored while the dummy is in its hurt reaction, which lasts longer than a volley; measurements that count only HP changes cannot show it.)

### 7.4 Damage [V]
Damage per hit is the glove formula `docs/rom-combat.md` section 4.3 with `E19B` = the stage when the projectile hits: `v = atk * (2s + 4) >> 2`. `E19B` is 0 at the press and equal to the stage in every hit of a volley (it is cleared only when the last projectile is gone; sampled in the hit runs) [V]. Measured with the real hit routine on 300 random RNG states, hero 0 against a dummy with evade 0 and defense 0, weapon grade 0 of the type (atk 76 whip, 77 bow, 76 javelin and boomerang):

| stage | atk*(2s+4)>>2 | hit rate | min | mean | max |
|---|---|---|---|---|---|
| 0 | 77 | 1.00 | 72 | 149.5 | 296 |
| 1 | 115 | 1.00 | 108 | 185.7 | 378 |
| 2 | 154 | 1.00 | 144 | 228.9 | 460 |
| 3 | 192 | 1.00 | 180 | 266.9 | 542 |
| 4 | 231 | 1.00 | 217 | 311.2 | 622 |
| 5 | 269 | 1.00 | 252 | 362.7 | 702 |
| 6 | 308 | 1.00 | 289 | 395.4 | 786 |
| 7 | 346 | 1.00 | 325 | 439.7 | 868 |
| 8 | 385 | 1.00 | 361 | 488.2 | 948 |

(whip, javelin and boomerang: the same columns within the random spread; `data/weapons_ranged.json`, `hits`.) One hit is capped at 999.

**Crit base `E196`**: `3 * weapon level + row crit byte` for the glove, sword, axe, spear and whip, and **half of that sum (shifted right once) for the bow, boomerang and javelin** [V from the nine rows of each type after the equip routine: whip rows 21 and 31 (row 43, crit byte 10), bow 10 and 20 (row 52, crit 20), boomerang 9 and 14 (row 61 and 62, crit 10), javelin 9; these use the weapon levels of the save state]. The accuracy and attack byte are `min(99, Agi/4 + 75)` and `Str + row power` as for the other weapons.

### 7.5 Status and knockback [V]
- Weapon rows with a status word: whip 37 and 42 (0x0004), bow 48 and 51 (0x0080), boomerang 56 (0x0004) and 59 (0x2000), javelin 66 and 68 (0x0100); chance byte 80. For a stage 0 hit on the dummy with 60 random RNG states each, the target's status word changed in: whip 44 and 44 of 60, bow 54 and 59, boomerang 52 and 52, javelin 50 and 50 (a hit that does not change it can be the 20 % that fail or a status the dummy is immune to; the dummy's immunity word is 0x1600). The rule is that of `docs/rom-combat.md` section 7.
- Knockback of the target depends only on the damage against its maximum HP (hurt code `E011 = 0x89` and a push of 40 px when the hit takes at least a quarter of the maximum HP, 0x88 and no push otherwise), as for the glove (`docs/glove-attacks.md` section 5.5): dummy with 600 / 1000 / 2000 maximum HP, stage 0 / 4 / 8 hits (`target_knockback_by_damage_vs_max_hp` in the JSON) [V]. The weapons themselves apply no knockback.

## 8. Charge and the gauge [V]
The charge counter `$C0:B330` runs while B is held and does nothing while `E1ED`, `E01C`, `E061` or the pygmy bit are non-zero. For the projectile weapons this means: swing, then flight of the last projectile (`E061`), then the gauge countdown, and only then the stage counter (1 per 2 frames, 45 counts = 90 frames per stage, capped by the weapon level; the same code as for every weapon). **Stage `k` is reached `90 k - 3` frames after the gauge is empty** (frames counted from the press with B held from the press; hero 0, parity 0; heroes 1 and 2 face the way the save state has them, which changes the flight time of the boomerang and javelin):

| weapon | hero | Agi | swing end | projectile free (gauge loaded) | gauge empty | stage 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| whip | 0 | 79 | 21 | - | 96 | 183 | 273 | 363 | 453 | 543 | 633 | 723 | 813 |
| whip | 1 | 63 | 21 | - | 104 | 191 | 281 | 371 | 461 | 551 | 641 | 731 | 821 |
| whip | 2 | 57 | 21 | - | 107 | 194 | 284 | 374 | 464 | 554 | 644 | 734 | 824 |
| bow | 0 | 79 | 36 | 43 | 117 | 204 | 294 | 384 | 474 | 564 | 654 | 744 | 834 |
| bow | 1 | 63 | 36 | 43 | 125 | 212 | 302 | 392 | 482 | 572 | 662 | 752 | 842 |
| bow | 2 | 57 | 36 | 43 | 128 | 215 | 305 | 395 | 485 | 575 | 665 | 755 | 845 |
| boomerang | 0 | 79 | 31 | 57 | 131 | 218 | 308 | 398 | 488 | 578 | 668 | 758 | 848 |
| boomerang | 1 | 63 | 31 | 59 | 141 | 228 | 318 | 408 | 498 | 588 | 678 | 768 | 858 |
| boomerang | 2 | 57 | 31 | 57 | 142 | 229 | 319 | 409 | 499 | 589 | 679 | 769 | 859 |
| javelin | 0 | 79 | 26 | 35 | 109 | 196 | 286 | 376 | 466 | 556 | 646 | 736 | 826 |
| javelin | 1 | 63 | 26 | 31 | 113 | 200 | 290 | 380 | 470 | 560 | 650 | 740 | 830 |
| javelin | 2 | 57 | 26 | 31 | 116 | 203 | 293 | 383 | 473 | 563 | 653 | 743 | 833 |

Sounds while holding (hero 0, level 8): 0x26 when the gauge empties (frame 100 whip, 120 bow, 132 boomerang, 112 javelin), then 0x27 every 8 frames while the counter runs, 0x28 at stages 1, 3, 5, 7 and 8 [V] (`$C0:B3CB`, `$C0:BB11`). The weapon level only caps the stage (levels 1, 2, 5, 8 gave stages 1, 2, 5, 8 after 1200 frames); releasing B before stage 1 starts nothing (the state byte stayed 0); releasing at stage s starts the charged attack in the same frame [V].

## 9. When the hero can be hit [V]
The monster weapon test is skipped while the hero's body box is empty (section 1.4). Frames (from the press or release) in which the hero can be hit:

| attack | frames in which a monster box can hit |
|---|---|
| whip normal var0 | 1 |
| whip normal var2 | 1 |
| whip power stage8 cls2 | 1-16 |
| bow normal var0 | 1-36 |
| bow normal var2 | 1-36 |
| bow power stage8 cls2 | 1-36 |
| boomerang normal var0 | 1 |
| boomerang normal var2 | 1 |
| boomerang power stage8 cls2 | 1-6 |
| javelin normal var0 | 1 |
| javelin normal var2 | 1 |
| javelin power stage8 cls2 | 1-16 |

## 10. Open questions (no values claimed)
- Script ops `0x80-0x8E` and `0xB0-0xEF` (among them `0x8D` and `0x83`, which bracket the whip strike) and `0xFB`-related details beyond the launcher were not decoded one by one.
- The bow hit at (-59, +31) in the stage 0 model test (observed, not predicted) was not explained.
- The two kinds of boomerang (3 and 5, rows 54, 56, 58, 59 and 55, 57, 60-62): no difference in flight or hit timing was found for the facings and stages compared; what the kind byte changes was not determined.
- The value of `E02E` read at the damage frames of the boomerang was 0 although the table of section 7.3 shows that a mask is at work for it; where the boomerang keeps it was not determined.
- Hero 1 facing down at boomerang stages 2 and 8 flew a slightly different path (one frame longer at stage 8) than hero 0; the terrain test is the likely cause but it was not traced.
- The terrain lookup of the projectiles (`$C2:C183-C220`, tile attribute bits 0x30 of `$7F:B800` / `$7F:BC00`): what it does to a flight against a wall was not exercised.
- That the model mismatches of the boomerang at stage 8 are hits by the hero's melee box was inferred from their timing (frames 8-18, before any launch), not traced.
- The rule for choosing the swing animation with more than one enemy on screen (as for the glove).
- Whether a frame-skipping slowdown stretches these timings (the counts assume one main-loop pass per video frame).

## 11. Graphics
All hero animations of these four weapons and the projectile sprites were ripped with `tools/rip_ranged_anims.py` (frames are written outside the repository). Layout: `<weapon>/<hero>/<attack>_<level>_<dir>_<nn>.png` (RGBA, colour 0 transparent, same size for every frame of one animation, foot origin in the JSON) with `<attack>_<level>_<dir>.json` (per-frame durations in video frames, offsets of the hero, pieces, palettes, animation script steps; `swing_frames` and `projectile_frames` split the recording at the end of the attack state; the animation lasts until the last projectile is gone), `index.json`, `aliases.json` (animations with the same script as a ripped one: `normal1..3` = `normal0` for the bow, javelin and boomerang; `normal1` = `normal0` and `normal3` = `normal2` for the whip; `chargemidN` and `chargenearN` = `chargeN` for all four weapons) and `projectile/` (every distinct 16 x 16 projectile piece with its flips and the kinds and dying counters it was seen with). Per weapon and hero: whip 40 animations, bow, boomerang and javelin 36 each. Validation against the public sprite sheets (every opaque pixel of the frame, apart from the cycling effect palette, found in the sheet, on the 5-bit colours; `tools/compare_sheet.py`): **444 animations and 21,705 distinct pictures** were ripped (whip 120 animations and 4,392 pictures, bow 108 and 3,638, boomerang 108 and 8,722, javelin 108 and 4,953; 57 projectile pieces: bow 18, boomerang 15, javelin 24, whip none). Result of the comparison, frames found / frames compared: against the weaponless sheets of the three heroes **all frames of all four weapons match** (whip 1,368 / 1,512 / 1,512 for boy / girl / sprite, bow 1,142 / 1,248 / 1,248, boomerang 2,783 / 2,969 / 2,970, javelin 1,563 / 1,695 / 1,695); against the weapon-specific sheets of the boy: whip 1,368 of 1,368, bow 1,142 of 1,142, javelin 1,459 of 1,563 (the 104 missing are up and down views of charged attacks that the sheet does not show), boomerang row 55 (the "Var. B" sheet) 2,261 of 2,783 (the missing 522 are up and down views as well; the same sheet against row 54 matches 996 only, because the boomerang held in the hand is drawn with the other graphics of the row). Boomerang row 55 was ripped with `row=55`.

The sprite sheets cover the hero's body pictures; the projectile pieces and the effect palette (sprite palette 0, which cycles while an attack plays) are not part of the comparison, and the weapon-specific sheets lack some up and down views, so the frames were also compared with the "weaponless" sheets of each hero, which hold all body pictures.

## 12. Tools and commands
```
R=path/to/rom.sfc ; S=path/to/state.zs3        # a state with the three heroes idle on a map, nothing in front of them
python3 tools/ranged_attacks.py "$R" "$S" whip.json whip               # all sections, about 25 minutes per weapon
python3 tools/ranged_attacks.py "$R" "$S" out.json bow normal proj hits   # some sections
python3 tools/ranged_report.py merge data/weapons_ranged.json whip.json bow.json boomerang.json javelin.json
python3 tools/ranged_report.py data/weapons_ranged.json bow proj
python3 tools/ranged_report.py data/weapons_ranged.json javelin tl power 8 0 left
python3 tools/rip_ranged_anims.py "$R" "$S" OUTDIR bow boy normal0,charge3 left     # frames go outside the repository
```
`tools/ranged_sim.py` (library): `Ctx(type, grade).make/start(...)`, `proj_entries`, `sample`, `follow`. Sections of `ranged_attacks.py`: `structure normal chooser gauge charge power proj model hits probes invuln`. Data: `data/weapons_ranged.json`, keyed by weapon name (`whip`, `bow`, `boomerang`, `javelin`); keys per weapon: `structure` (script of every animation id and facing, steps, shot steps, sounds, presets), `normal_runs`, `chooser`, `gauge`, `charge`, `power` (`slotN` > stage > class > facing), `proj` (projectile paths), `model`, `hits`, `probes`, `invulnerability`. Segment rows have the fields of `SEG_FIELDS` in `tools/glove_attacks.py`; projectile paths are lists of `[dx, dy, z]` per frame.

## 13. Verified
Executed [V]: swing start, latency and the press-phase table; the animation ids and scripts of the four weapons; the gauge (loading frame, value, countdown) for the three heroes; extra presses during the swing and the projectile flight; charge timing per stage for the three heroes and the stage caps; all 8 stages x 3 classes x 4 facings x 3 heroes for each weapon (timing, movement, boxes, projectile paths, sounds); the number, delay, speed and range of the projectiles per stage; the hit model on random placements; piercing and stopping, the return phase of the boomerang, the hit mask; damage per stage and per gauge value with the real routines; status infliction and knockback by damage; the body-box vulnerability.
Read only [C]: the launcher and entry initialisation, the per-frame entry step, the catch test and the return branch of the boomerang, the absence of any ammunition write, the terrain lookup.


# Glove attacks of the three heroes (weapon type 0, rows 0-8) - recovered from the ROM (Secret of Mana USA)

Tags: **[V]** means the real 65816 code was executed in `tools/cpu65816.py` (the whole per-frame routine `$C0:B08C` on a ZSNES save state, with the controller word injected) and the numbers were read from the running objects; **[C]** means read from the disassembly, not executed. What is not determined is listed in section 9 and carries no guessed values.

Addressing: 2 MiB HiROM, `$Cx:xxxx` = file offset `((x-0xC0)<<16)|xxxx`, `$01:xxxx` is the mirror of `$C1:xxxx`, `$02:xxxx` of `$C2:xxxx`. Animation scripts live in bank `$D1`. No ROM bytes are stored in the repo: scripts are described by decoded numbers. Object fields are offsets in the 0x200-byte object record at `$7E:E000 + slot*0x200` (`docs/rom-combat.md` section 1.1). Heroes are slots 0, 1, 2 (ids 0x80, 0x81, 0x82), monsters start at slot 3.

Time: **1 frame = 1/60.0988 s = 16.638 ms**. Seconds in this document are frames / 60.0988. Section 1 explains the two clocks that matter: every frame (60.0988 Hz) and the hero animation step (every 5th frame, 12.02 Hz).

Method: `tools/glove_sim.py` loads a save state, equips glove row `r` with the game's own routines (`$C0:4530` stats, `$C0:EA41` animation tables), makes one hero the pad-1 hero and runs `$C0:B08C` once per video frame (the NMI waits are stubbed; PPU, DMA and the sound driver are not emulated). The pad word is injected where the game reads `$4218/$4219` (B = 0x8000), so the real input handler (`$C0:B69C`), the swing start (`$C0:B29F`), the charge gauge (`$C0:B330`), the release handler (`$C0:B21C`), the object step (`$C0:F4CB`), the animation interpreter (`$C0:F5A3`, `$C0:F90B`, `$C1:D5C0-D8F2`), the box test (`$C1:D14A`) and the damage routines run unmodified. A dummy monster (id 0, HP 9999, AI step disabled) is created by the game's spawner `$C0:DE3B` when a hit is needed. `tools/glove_attacks.py` runs all experiments and writes `data/glove_attacks.json`; `tools/glove_report.py` prints the tables below from that file. The save state had the three heroes idle on an open map (Agi 79, 63, 57); animation, boxes and speeds do not depend on the hero's stats, only the numbers marked "per hero" do.

## 0. Summary

1. **There is no combo.** One press of B starts exactly one swing; a press during the swing is discarded (not buffered); the next swing needs a new press after the state byte `E01C` has returned to 0. The swing is never blocked by the weapon gauge `E1ED`; the gauge only weakens the damage (section 2.4) [V].
2. **Normal swing** (`E01C = 0x20`): four scripts (variants 0-3) of **4 or 5 animation steps of 5 frames = 20 or 25 frames (0.333 or 0.416 s)** after the first step, plus 1-5 frames of latency from the press to the first step. Total press to end: **21-30 frames = 0.349-0.499 s** (table in section 1) [V].
3. Which variant plays is chosen at the press from the distance class of the nearest enemy (near / mid / far-or-none) minus the parity of the frame counter `$F4` (section 2.2) [V].
4. The hero moves **forward 5 or 10 px at 1 px per frame** during a variant 0, 1, 3 swing and does not move in variant 2 (section 1); the d-pad is ignored during a swing [V].
5. **After the swing** the gauge `E1ED = (100 - Agi)/2 + 50` is loaded, frozen while a swing runs, counts down 1 per frame, then stays at 1 for 15 more frames; 75 frames (1.248 s) for Agi 79, 83 for Agi 63, 86 for Agi 57. Only at `E1ED = 0` is a swing at full damage; the gauge also blocks charging (section 2.4) [V].
6. **Charge**: holding B, the stage counter only starts when the gauge is empty; stage `k` is reached `swing end + gauge frames + 90*k - 3` frames after the press; the weapon level only caps the stage (section 3) [V].
7. **Releasing B with stage s >= 1 starts the power attack of stage s in the same frame** (`E01C = 0x80`, variant `E011 = 4*s + class`). The attack depends on the stage, not on the weapon level (level 8 weapon released at stage 3 plays the stage-3 attack). Durations 66-201 frames (1.10-3.34 s), movement, boxes and sounds in section 4 [V].
8. **Every attack hits each target at most once** (one damage event per target per attack), however long the box stays active: the hit flag `E05A` of the hero is only cleared when the attack ends. Damage per hit is the normal formula with `E19B` = stage: multiplier `(2s+4)/4` = x1 ... x5 (section 5) [V].
9. **While the weapon box is active the hero's body box is empty** (width and height 0): the hero cannot be hit by monster weapon boxes in those frames (section 2.6) [V].
10. The three heroes share all animation scripts, speeds and box sizes. Differences: the gauge (Agi), the attack/accuracy/crit stats, and the weapon box becomes non-empty one frame later for heroes 1 and 2 than for hero 0 (section 2.7) [V].

## 1. Normal attack: exact timing (table)

### 1.0 In one table (side facing; the four variants are in 1.2)
| quantity | value |
|---|---|
| animation clock of a hero | one step every 5th frame: 5 frames = 83.2 ms (12.02 steps/s); movement and the gauge run every frame |
| press to first animation step | 1 to 5 frames (0.017-0.083 s), mean 3 frames |
| swing length after the first step | **4 steps = 20 frames = 0.333 s** (variants 0, 1 and 2 side) or **5 steps = 25 frames = 0.416 s** (variant 3, and variant 2 facing up or down) |
| press to end of the swing | 21-25 frames (0.349-0.416 s) for the 4-step family, 26-30 frames (0.433-0.499 s) for the 5-step family |
| hero acts again | at the end of the swing: `E01C` is cleared in that frame, so walking and a new swing are possible at once (a new swing deals reduced damage until the gauge is empty; charging starts only when it is empty) |
| sprite frames (steps each) | variant 0: 1+2+1; 1: 1+1+1+1; 2: 1+2+1 (up/down 1+2+2); 3: 1+2+1+1 (1 step = 0.0832 s) |
| weapon box active (frames after the first step) | variants 0 and 3: frames 5-19 (15 frames = 0.250 s; variant 3 then has 5 frames of recovery without a box); variant 1: frames 5-14 (10 frames = 0.166 s); variant 2: frames 0-19 (20 frames) |
| combo window | none: a press during a swing is discarded, a press after the swing starts a new, independent swing |
| movement during the swing | variants 0 and 3: 1 px per frame (60.1 px/s) forward for 10 frames from frame 5 (10 px); variant 1: 5 frames (5 px); variant 2: none; the d-pad is ignored |
| weapon gauge `E1ED` | loaded at the END of the swing with `(100 - Agi)/2 + 50` (60 for Agi 79), frozen during swings, -1 per frame, held at 1 for 15 frames, so empty after 75 frames (1.248 s) for Agi 79; damage is reduced while it is non-zero (2.4) |
| damage | one hit per target per swing, `atk` (stage 0 multiplier x1) |

Which of the variants is drawn as a punch and which as a kick is not in these numbers; what differs in timing is the 4-step family (variants 0, 1, 2 side) and the 5-step family (3, and 2 up or down).

### 1.1 The two clocks [V]
- The input handler, the swing start, the gauge, the movement (`E006/E007` added to the position) and the box test run **every frame**.
- A hero runs its object step (`$C0:F4CB`: animation interpreter, script ops, box assignment) only when the main-loop counter `$56` equals 3, i.e. **once every 5th frame = 12.02 steps per second** (`$C0:B0D3` [C], observed in every run). Animation durations are counted in these steps: **1 step = 5 frames = 83.2 ms**. The press frame itself still runs its hero step before the input handler, so the swing starts to animate at the next step: **1 to 5 frames after the press** (50 ms on average), depending on where in the 5-frame cycle the press falls.
- A swing ends at the step that executes the end op of the script: `E01C` is cleared and the gauge is loaded in that frame.

### 1.2 Variants (hero 0, facing left; all heroes alike except as noted)
Frames are counted from the first animation step (frame 0 = the frame of the first step); add the latency of 1-5 frames for the press.

| | variant 0 | variant 1 | variant 2 | variant 3 |
|---|---|---|---|---|
| animation steps (1 step = 5 frames) | 4 | 4 | 4 (side) / 5 (up, down) | 5 |
| sprite frames, steps each | 1+2+1 | 1+1+1+1 | 1+2+1 (side) / 1+2+2 (up, down) | 1+2+1+1 |
| first step to end of the swing | 20 fr = 0.333 s | 20 fr = 0.333 s | 20 fr = 0.333 s (side) / 25 fr = 0.416 s (up, down) | 25 fr = 0.416 s |
| press to end of the swing (latency 1..5 frames added) | 21..25 fr = 0.349..0.416 s | 21..25 fr = 0.349..0.416 s | 21..25 fr = 0.349..0.416 s (side) / 26..30 fr = 0.433..0.499 s (up, down) | 26..30 fr = 0.433..0.499 s |
| forward movement (frames counted from the first step) | 1 px/frame (60.1 px/s) for 10 frames from frame 5 = 10 px | 1 px/frame (60.1 px/s) for 5 frames from frame 5 = 5 px | none | 1 px/frame (60.1 px/s) for 10 frames from frame 5 = 10 px |
| weapon box, side facing (frames from the first step; w x h, forward offset of the centre, centre y) | frames 5-14: 24 x 24, forward 12, cy -15; frames 15-19: 24 x 24, forward 12, cy -15 | frames 5-9: 24 x 16, forward 12, cy -15; frames 10-14: 24 x 16, forward 16, cy -15 | frames 0-4: 16 x 16, forward 8, cy -7; frames 5-14: 28 x 20, forward 8, cy -15; frames 15-19: 16 x 16, forward 8, cy -7 | frames 5-14: 24 x 24, forward 12, cy -15; frames 15-19: 24 x 24, forward 12, cy -15 |
| weapon box active (hero 0; heroes 1 and 2 one frame later) | frames 5-19 (15 frames = 0.250 s) | frames 5-14 (10 frames = 0.166 s) | frames 0-19 (20 frames = 0.333 s) | frames 5-19 (15 frames = 0.250 s) |
| sound id | 0x99 at frame 5 | 0x99 at frame 5 | 0x32 at frame 5 | 0x32 at frame 5 |

Frames from the press to the end of the swing for every phase of the press inside the 5-frame cycle (`$56` of the press frame; the first step is at frame offset `1 + ((2 - $56) mod 5)`):

| press at `$56` = | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| frames until the first step | 3 | 2 | 1 | 5 | 4 |
| variant 0, side facing: frames from press to end | 23 | 22 | 21 | 25 | 24 |
| variant 1, side facing: frames from press to end | 23 | 22 | 21 | 25 | 24 |
| variant 2, side facing: frames from press to end | 23 | 22 | 21 | 25 | 24 |
| variant 3, side facing: frames from press to end | 28 | 27 | 26 | 25 | 29 |

Notes:
- "steps" are sprite frames times their durations: a frame word with duration code d lasts d+1 steps when d < 4 and 1 step otherwise [C `$C0:F5C8-F5DB`, V]; 1 step = 0.0832 s, 2 steps = 0.1664 s. Variant 0: three sprite frames of 1 + 2 + 1 steps; variant 1: four of 1 step; variant 2: 1 + 2 + 1 steps (side) or 1 + 2 + 2 (up, down); variant 3: 1 + 2 + 1 + 1.
- Facing codes in `E010`: 0 = up, 1 = down, 2 = right, 0x82 = left [V]. Right is the exact mirror of left in all 28 attacks measured (frame by frame: velocity and box x negated, box sizes, heights and sounds equal) [V]. Up and down are separate scripts with the same step counts as each other; they move along y (`E007`) and have their own box shapes (for example variant 2: 20 x 32 box facing up, 20 x 28 facing down). Compared with the side facing the only timing difference of the normal swing is variant 2 (5 steps instead of 4 facing up or down) [V].
- The sound is requested at frame 5 (the start of the strike) in every variant: sound id 0x99 in variants 0 and 1, 0x32 in variants 2 and 3 (section 6).
- The box coordinates are in pixels relative to the hero position (`E002/E004`), centre x (forward is negative for left), centre y (negative = up), width, height (section 2.5).

Timeline of each variant (hero 0, side facing left; `frames` counted from the press frame 0 with the first step at frame 1; "intangible" = body box empty; "hero offset" = measured displacement and height at the start of the row):

Variant 0:

variant 0, facing left: end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 0 | -12, -15, 24, 24 | intangible | 0, 0, 0 |
| 16-20 | 0 | -12, -15, 24, 24 | intangible | -10, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | -10, 0, 0 |

Sprite frames, duration of each in steps (3 frames, 4 steps): 1 2 1

Variant 1:

variant 1, facing left: end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | -1, 0, 0 | -12, -15, 24, 16 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, -15, 24, 16 | intangible | -5, 0, 0 |
| 16-20 | 0 | - | tangible | -5, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | -5, 0, 0 |

Sprite frames, duration of each in steps (4 frames, 4 steps): 1 1 1 1

Variant 2:

variant 2, facing left: end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -8, -7, 16, 16 | intangible | 0, 0, 0 |
| 6-15 | 0 | -8, -15, 28, 20 | intangible | 0, 0, 0 |
| 16-20 | 0 | -8, -7, 16, 16 | intangible | 0, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | 0, 0, 0 |

Sprite frames, duration of each in steps (3 frames, 4 steps): 1 2 1

Variant 3:

variant 3, facing left: end of state at frame 26 (0.433 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 0 | -12, -15, 24, 24 | intangible | 0, 0, 0 |
| 16-20 | 0 | -12, -15, 24, 24 | intangible | -10, 0, 0 |
| 21-25 | 0 | - | tangible | -10, 0, 0 |
| 26-26 | 0, 0, -4 | - | tangible | -10, 0, 0 |

Sprite frames, duration of each in steps (4 frames, 5 steps): 1 2 1 1

## 2. Normal attack: rules

### 2.1 Start [V, C]
B is the attack button (bit 7 of the high pad byte). The press edge is latched by `$C0:93F7-9411` into `$CC` bit 3; `$C0:B7AC` consumes it and calls `$C0:B851`, which first looks for an object in front of the hero that reacts to the button and otherwise jumps to `$C0:B29F` [C; the jump to `B29F` and everything after it V]. `B29F` returns without doing anything when `E01C | E061` is non-zero (already attacking, or a state flag). Otherwise, in the same frame: `E01C = 0x20`, `E006 = E007 = 0`, `E011 = ` the variant (`$C1:E40E`), the animation pointer is rebuilt (`$C1:CA04`), and if `E1ED == 0` the charge counter is started (`E01A = 1`; with `E1ED != 0` it is not, so a swing started during the recharge cannot be turned into a charge).

### 2.2 Which variant plays [V]
`$C1:E40E` is called at the press. For heroes it looks at the nearest monster (slots 3-5) and returns a class; the variant is `class value - parity`, where the class value is 1 (near), 2 (mid) or 3 (far, or no target) and the parity is bit 0 of the frame counter `$F4` (incremented once per frame by the NMI, so effectively alternating with the exact frame of the press):

| nearest enemy, along x | along y | class value | variant, `$F4` even | variant, `$F4` odd |
|---|---|---|---|---|
| < 26 px | < 24 px | 1 | 1 | 0 |
| 26-41 px | 24-39 px | 2 | 2 | 1 |
| >= 42 px, or no enemy | >= 40 px | 3 | 3 | 2 |

The class is the larger of the x class and the y class (grid test 4 x 4: dx = 20 with dy = 30 gives class 2; dx = 30 with dy = 0 gives class 2; dx = 45 anything gives 3) and does not depend on the facing (tested for the four facings) [V]. The distance is between the object positions (`E002/E004`) of hero and monster. With two monsters on screen all four combinations tried returned the near class; the rule for several monsters is not determined (section 9).

### 2.3 Presses during a swing, and the next swing [V]
- Three extra presses at frames 6, 12 and 18 of a swing started no second swing (swing starts: frame 0 only).
- Pressing every second frame (spam): the first swing started at frame 0, the next at frame 28 and then every 30 frames, each at the first press frame after `E01C` was cleared (the swings were variant 3: 26 frames). There is no minimum wait other than the swing itself.
- Holding B does not repeat the swing (a new press edge is needed).
- A direction pressed together with B (right, left, up, down) changes neither the facing nor the movement of the swing; the hero turns and walks only after `E01C` has cleared [V].

### 2.4 The weapon gauge `E1ED` [V]
| hero slot | Agi | atk E198 | acc E197 | crit base E196 | gauge start `(100-Agi)/2+50` | frames to empty (+15) | seconds |
|---|---|---|---|---|---|---|---|
| 0 | 79 | 76 | 94 | 18 | 60 | 75 | 1.248 |
| 1 | 63 | 62 | 90 | 18 | 68 | 83 | 1.381 |
| 2 | 57 | 40 | 89 | 15 | 71 | 86 | 1.431 |

- Loaded with `(100 - Agi) / 2 + 50` when the swing ends (`$C0:F937-F944` for `E01C` = 0x20 or 0x80; `$C1:CACD`), **not** at the start. The gauge value from before the swing is kept and frozen during a swing: the decrement `$C0:EB4F` runs only when `E01C & 0xA0 == 0` (measured: 30 frozen at 30 for the 24 frames of the next swing, then reloaded to 60).
- Counts down 1 per frame to 1, then holds 1 for 15 frames while the "gauge full" flash runs (`$C0:EBB6` re-increments it while `E063`'s high nibble steps 1..15), then 0. Total from the end of the swing to 0: `(100 - Agi)/2 + 50 + 15` frames: 75 (Agi 79), 83 (63), 86 (57). A sound request `0xA6` (sound 0x26) is made when it empties for the human-controlled hero [V].
- Effects of a non-zero gauge at the moment of the hit (`docs/rom-combat.md` section 4.2-4.3): accuracy is halved, no critical hit, and damage is `(v/2) * (AC - E1ED) / AC` with `AC = (99 - Agi)/2 + 80`. Measured with the real routines (300 random RNG states, hero 0 with atk 76 vs a dummy with evade 0 and defense 0):

| gauge E1ED at the hit | stage 0: hit rate, mean, max | stage 8: hit rate, mean, max |
|---|---|---|
| 0 | 1.00, 152.3, 294 | 1.00, 494.7, 936 |
| 1 | 1.00, 43.6, 72 | 1.00, 151.3, 232 |
| 15 | 1.00, 33.9, 60 | 1.00, 131.6, 195 |
| 30 | 1.00, 28.2, 48 | 1.00, 99.4, 156 |
| 45 | 1.00, 21.0, 36 | 1.00, 74.3, 117 |
| 60 | 1.00, 13.7, 24 | 1.00, 49.7, 78 |
| 75 | 1.00, 6.1, 12 | 1.00, 25.3, 39 |
| 90 | 1.00, 0.0, 0 | 1.00, 0.0, 0 |

  The gauge also keeps the charge counter from advancing (`$C0:B330` returns while `E1ED != 0`), so charging starts only after the gauge is empty (section 3).

### 2.5 Boxes and hit test [V, C]
- Each hero has three boxes in its object: weapon box `E0C0-E0C3`, body box `E0C8-E0CB`, and a third box `E0CC-E0CF` whose purpose is not determined. A box is (centre x, centre y, width, height) in pixels: two signed bytes (offsets from the object position `E002/E004`) and two unsigned bytes. The x offset is stored already mirrored for a left-facing hero (bit 7 of `E010`); y includes the sprite height `E045`. They are assigned from the sprite frame description each time the animation interpreter fetches a frame (`$C0:F42C-F4AA`) and cleared (width = height = 0) when the state ends.
- The pair test `$C1:D14A` runs every frame for each hero-monster pair: two boxes overlap when `|cx1 - cx2| < (w1 + w2)/2` and `|cy1 - cy2| < (h1 + h2)/2` (strict), with the centres = object position + offset. Checked by scanning a dummy (body box 20 x 20) over the whole range: normal variant 3 facing left hit for dummy offsets dx = -43..9 and dy = -29..28, exactly the union of the 24 x 24 box (moving 10 px) and the dummy's body box (whose y offset changed between -7 and -22 while it hurt) [V].
- A box assigned by the hero step in frame k is first tested in frame k+1 (the hit flag `E05A` of the hero was set exactly 1 frame after the first non-empty box, in all runs). The monster's combat tick then applies the damage: 1 frame later for a monster in slot 3, 2 for slot 4 (measured for all five press phases; slot 5 not measured). So from the step that sets the box: damage is applied after **2 frames (slot 3)**, 3 frames (slot 4) [V].
- On overlap: the monster's `E059` bit for this attacker is set, the attacker's `E05A` bit for this target is set, and **the same pair cannot hit again until `E05A` is cleared, which happens only when the state ends** (`$C0:F547` also clears it when `E010/E011` change, which does not happen inside an attack). Two monsters in front of the hero each took exactly one hit from a stage-8 attack, at the same frame; a single monster took one hit from every normal and power attack tested, although the boxes stay on it for up to 185 frames [V].

### 2.6 The body box: when the hero cannot be hit [V]
The monster weapon test compares the monster's weapon box with the hero's body box and skips the test when the body box has width and height zero (`$C1:D1F8`-`D21D`: `LDA E0CA,X / BEQ` [C]). Measured: with a large monster box placed on the hero for a single frame, the hero's hit flag fired at frame f exactly when the body box at frame f-1 was non-empty:

| attack | frames with a non-empty body box | frames in which the hero could be hit |
|---|---|---|
| normal variant 0 | 0-5, 21 | 1-6 |
| normal variant 2 | 0, 21 | 1 |
| power stage 8, class 2 | 0, 21-60, 201 | 1, 22-61 |

So the hero can be hit only while the body box is non-empty: normal variant 0 in frames 1-6 (safe from frame 7 to the end of the swing), variant 2 only in frame 1, stage 8 class 2 in frame 1 and frames 22-61 (safe for about 140 frames). The same information is the column "hero body" of the timelines ("intangible" = empty body box, the hit test is skipped one frame later).

### 2.7 Differences between the heroes [V]
The per-hero numbers are in the table of section 2.4 (Agi, attack, accuracy, crit base, gauge).
- Scripts, speeds, box sizes: identical for the three heroes and for the nine rows (the animation table pointer `E065`, the frame-description tables and the sprite set pointers are the same for glove rows 0-8 for all heroes).
- Hero 1 and 2 (girl, sprite): the weapon box is assigned one frame later than for hero 0 (variant 0: frames 7-21 instead of 6-20 counted from the press with latency 1); the body boxes differ a little with the sprite (the `body_*` columns of `normal_runs` in `data/glove_attacks.json`).
- The movement numbers in the tables are the sum of the velocities (`end_pos_nominal`, what happens on open ground); in the save state some runs were shortened by map walls (`end_pos_measured` in the json).
- Damage per hit: atk `E198 = (Str + row power) & 255` (rows 0-8 have power 2, 6, 11, 17, 24, 30, 38, 47, 53 and stat code bits that change no Str/Agi: `data/weapons.json`); accuracy `E197 = min(99, Agi/4 + 75)`; crit base `E196 = 3 * weapon level` (row crit byte is 0) plus 5 (heroes 0 and 2) or 10 (hero 1) in the roll [docs/rom-combat.md 4.3]. The weapon level changes nothing else in the normal swing.
- Status: rows 2 and 6 carry a status word (0x0010 and 0x2000, 80 % chance per damaging hit, `data/weapons.json`, `data/status_effects.json`); the fields `E199/E1F7` stayed constant over a whole stage-8 attack, so every hit of an attack uses the same chance [V].

## 3. Charging [V]
- While B is held, `$C0:B330` runs every frame. It does nothing while `E1ED`, `E01C`, `E061` or the pygmy bit are non-zero, so the counter starts only when the swing is over and the gauge is empty. `E01A` counts 1 per 2 frames up to 44, then the stage `E19B` (= `E01B`) is incremented: 45 counts = 90 frames per stage (`docs/rom-combat.md` 11.3). The stage is capped by the weapon level `E19C` (after 1000 frames of holding the stage was 1, 2, 5, 8 for levels 1, 2, 5, 8).
- Frames from the press to each stage when B is held from the press (swing variant 3, 26 frames, press at phase 2); stage k = swing end + gauge frames + 90 k - 3:

| hero | Agi | swing ends (frame, 26-frame swing) | gauge empty | stage 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 79 | 26 | 101 | 188 (3.128 s) | 278 (4.626 s) | 368 (6.123 s) | 458 (7.621 s) | 548 (9.118 s) | 638 (10.616 s) | 728 (12.113 s) | 818 (13.611 s) |
| 1 | 63 | 26 | 109 | 196 (3.261 s) | 286 (4.759 s) | 376 (6.256 s) | 466 (7.754 s) | 556 (9.251 s) | 646 (10.749 s) | 736 (12.247 s) | 826 (13.744 s) |
| 2 | 57 | 26 | 112 | 199 (3.311 s) | 289 (4.809 s) | 379 (6.306 s) | 469 (7.804 s) | 559 (9.301 s) | 649 (10.799 s) | 739 (12.296 s) | 829 (13.794 s) |

  With a 21-frame swing (variant 0-2 side) everything is 5 frames earlier; each unit of press latency adds one frame.
- Sounds while holding (hero 0, level 8): sound 0x26 when the gauge empties (frame 104), then sound 0x27 every 8 frames while the charge runs, and sound 0x28 when a stage is reached (observed at stages 1, 3, 5, 7 and 8; not at 2, 4, 6) (`$C0:B3CB`, `$C0:BB11` [C+V]).
- Release: the frame in which B is not held, `$C0:B21C` runs: with `E19B != 0` it starts the power attack in that same frame (`E01C = 0x80`, `E006 = E007 = 0`, `E011 = 4*stage + class`, `E1ED` untouched until the end). With stage 0 it does nothing (a release before stage 1 starts no attack and clears `E01A`).
- While the counter runs the hero walks at 1 px/frame per axis (`docs/hero-movement.md`).

## 4. Charged (power) attacks

### 4.1 Which attack [V]
The attack that plays is selected only by the stage reached when B is released and by the same distance class as the normal swing: `E011 = 4 * stage + (class value - 1)`, class value 1..3 as in section 2.2 (the parity of `$F4` has no effect). Tested for weapon levels 1, 4, 8 and every stage from 1 to the level: the variant is identical for the same stage and class. So **"the weapon level L attack" is the stage-L attack**, reachable only with a level >= L weapon; a level-8 glove released at stage 3 plays the stage-3 attack. Class 1 and 2 (mid and far/none) prepend one extra piece to the class 0 attack of stages 1-5 (a short dash: 10 px for class 1, 30 px for class 2, sound 0x0B); stages 6, 7 and 8 are identical for all three classes.

### 4.2 Structure: attacks are chains of pieces [C, V]
Each power attack script is a list of calls (`$F1`) to shorter scripts ("pieces"). Normal swings N0-N3 (section 1) are pieces too, so for example the stage-1 attack is three normal swings in a row (N3, N0, N2: 5 + 4 + 4 = 13 steps = 65 frames after the first step, matching the measured 66 frames). The static walk of the scripts (decoder `tools/glove_sim.py`, `tools/glove_attacks.py structure`) gives, for facing right/left (up and down have their own pieces; they differ only in lengths: 1 step more in stages 1, 3 and 4, 2 steps more in stage 5, equal in stages 2 and 6-8):

| E011 | stage, class | total steps | pieces in order (steps) |
|---|---|---|---|
| 4 | 1, 0 | 13 | N3(5) N0(4) N2(4) |
| 5 | 1, 1 | 14 | P0(1) N3(5) N0(4) N2(4) |
| 6 | 1, 2 | 15 | P1(2) N3(5) N0(4) N2(4) |
| 8 | 2, 0 | 16 | N1(4) N3(5) P2(7) |
| 9 | 2, 1 | 17 | P0(1) N1(4) N3(5) P2(7) |
| 10 | 2, 2 | 18 | P1(2) N1(4) N3(5) P2(7) |
| 12 | 3, 0 | 21 | N0(4) N2(4) N3(5) P3(8) |
| 13 | 3, 1 | 22 | P0(1) N0(4) N2(4) N3(5) P3(8) |
| 14 | 3, 2 | 23 | P1(2) N0(4) N2(4) N3(5) P3(8) |
| 16 | 4, 0 | 24 | P4(11) N1(4) N2(4) N3(5) |
| 17 | 4, 1 | 25 | P0(1) P4(11) N1(4) N2(4) N3(5) |
| 18 | 4, 2 | 26 | P1(2) P4(11) N1(4) N2(4) N3(5) |
| 20 | 5, 0 | 28 | P5(2) P6(6) N2(4) N2(4) P7(4) P7(4) P7(4) |
| 21 | 5, 1 | 29 | P8(2) P0(1) P6(6) N2(4) N2(4) P7(4) P7(4) P7(4) |
| 22 | 5, 2 | 30 | P9(2) P1(2) P6(6) N2(4) N2(4) P7(4) P7(4) P7(4) |
| 24 | 6, 0 | 30 | P10(0) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) |
| 25 | 6, 1 | 30 | P10(0) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) |
| 26 | 6, 2 | 30 | P10(0) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) P12(2) P11(2) |
| 28 | 7, 0 | 28 | P13(4) P14(4) N3(5) P2(7) P15(8) |
| 29 | 7, 1 | 28 | P13(4) P14(4) N3(5) P2(7) P15(8) |
| 30 | 7, 2 | 28 | P13(4) P14(4) N3(5) P2(7) P15(8) |
| 32 | 8, 0 | 40 | P16(0) P7(4) P15(8) P4(11) P17(17) |
| 33 | 8, 1 | 40 | P16(0) P7(4) P15(8) P4(11) P17(17) |
| 34 | 8, 2 | 40 | P16(0) P7(4) P15(8) P4(11) P17(17) |

Normal pieces:

| piece | script address | steps | sound ids | velocity presets |
|---|---|---|---|---|
| N0 | `$D1:62C9` | 4 | 0x99 | 1: 1,128,128; 25: 0,128,128 |
| N1 | `$D1:62ED` | 4 | 0x99 | 1: 1,128,128; 25: 0,128,128 |
| N2 | `$D1:6317` | 4 | 0x32 | - |
| N3 | `$D1:6335` | 5 | 0x32 | 1: 1,128,128; 25: 0,128,128 |

Other pieces (P0 and P1 are the class 1 / class 2 dash prefix; ids in the table above):

| piece | script address (bank $D1) | steps | sound ids | velocity presets k (vx, vy, vz of the table row; 128 = unchanged) |
|---|---|---|---|---|
| P0 | `$D1:637D` | 1 | 0xB | 2: 2,128,128; 25: 0,128,128 |
| P1 | `$D1:63BC` | 2 | 0xB | 3: 3,128,128; 25: 0,128,128 |
| P2 | `$D1:6401` | 7 | 0x33 | 0: 0,0,0 |
| P3 | `$D1:64A9` | 8 | 0x1B | 17: 128,128,1; 27: 128,128,0; 21: 128,128,255; 27: 128,128,0 |
| P4 | `$D1:6573` | 11 | 0x1B 0x1B 0x1B | 17: 128,128,1; 27: 128,128,0; 2: 2,128,128; 0: 0,0,0; 7: 131,128,128; 0: 0,0,0; 3: 3,128,128; 0: 0,0,0; 21: 128,128,255; 0: 0,0,0 |
| P5 | `$D1:66D5` | 2 | - | 18: 128,128,2; 0: 0,0,0; 22: 128,128,254; 0: 0,0,0 |
| P6 | `$D1:6669` | 6 | 0x1C | 17: 128,128,1; 27: 128,128,0; 21: 128,128,255; 22: 128,128,254; 0: 0,0,0 |
| P7 | `$D1:66AB` | 4 | 0x1B | - |
| P8 | `$D1:6726` | 2 | - | 18: 128,128,2; 0: 0,0,0; 22: 128,128,254; 0: 0,0,0 |
| P9 | `$D1:6780` | 2 | - | 18: 128,128,2; 0: 0,0,0; 22: 128,128,254; 0: 0,0,0 |
| P10 | `$D1:67DA` | 0 | - | 0: 0,0,0 |
| P11 | `$D1:6836` | 2 | 0x1B | - |
| P12 | `$D1:6840` | 2 | - | - |
| P13 | `$D1:6889` | 4 | - | 18: 128,128,2; 0: 0,0,0; 4: 4,128,128; 25: 0,128,128; 22: 128,128,254; 0: 0,0,0 |
| P14 | `$D1:68A0` | 4 | 0x3E | - |
| P15 | `$D1:6847` | 8 | 0x46 | 1: 1,128,128; 25: 0,128,128; 5: 129,128,128; 25: 0,128,128 |
| P16 | `$D1:6991` | 0 | - | 4: 4,128,128; 25: 0,128,128 |
| P17 | `$D1:68F2` | 17 | 0x99 0x99 0x99 0x99 0x99 0x99 0x99 0x99 0x99 | - |

Velocity preset k is a row of the 4-byte table at `$C2:AF05` (ROM offset 0x2AF05): vx, vy, vz in px/frame, value 128 = leave unchanged, otherwise sign-magnitude for x and y (bit 7 = negative, mirrored with the facing) and two's complement for z; preset 0 stops all three, 25/26/27 stop x/y/z. The script ops that change velocity otherwise (`$F0 aa bb`: signed 4-bit nibbles for vx, vy, vz) are used by stages 6 and 7.

### 4.3 Overview (hero 0, facing left; heroes 1 and 2 are identical except the weapon box starts one frame later) [V]
Frames are from the release frame (frame 0); the first step is at frame 1.

| stage | class | frames (s) | steps | move px (x, y) | max height | weapon box frames | first..last | box union x lo..hi, y lo..hi | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 66 (1.098) | 13 | (-20, 0) | 0 | 50 | 6..65 | [-44.0, 0.0, -27.0, 1.0] | 32@6 99@31 32@51 |
| 1 | 1 | 71 (1.181) | 14 | (-30, 0) | 0 | 50 | 11..70 | [-54.0, -10.0, -27.0, 1.0] | B@1 32@11 99@36 32@56 |
| 1 | 2 | 76 (1.265) | 15 | (-50, 0) | 0 | 50 | 16..75 | [-74.0, -30.0, -27.0, 1.0] | B@1 32@16 99@41 32@61 |
| 2 | 0 | 81 (1.348) | 16 | (-35, 0) | 0 | 50 | 6..80 | [-67.0, 0.0, -34.0, 5.0] | 99@6 32@26 33@61 |
| 2 | 1 | 86 (1.431) | 17 | (-45, 0) | 0 | 50 | 11..85 | [-77.0, -10.0, -34.0, 5.0] | B@1 99@11 32@31 33@66 |
| 2 | 2 | 91 (1.514) | 18 | (-65, 0) | 0 | 50 | 16..90 | [-97.0, -30.0, -34.0, 5.0] | B@1 99@16 32@36 33@71 |
| 3 | 0 | 106 (1.764) | 21 | (-20, 0) | 10 | 65 | 6..95 | [-44.0, 4.0, -49.0, 1.0] | 99@6 32@26 32@46 1B@81 |
| 3 | 1 | 111 (1.847) | 22 | (-30, 0) | 10 | 65 | 11..100 | [-54.0, -6.0, -49.0, 1.0] | B@1 99@11 32@31 32@51 1B@86 |
| 3 | 2 | 116 (1.930) | 23 | (-50, 0) | 10 | 65 | 16..105 | [-74.0, -26.0, -49.0, 1.0] | B@1 99@16 32@36 32@56 1B@91 |
| 4 | 0 | 121 (2.013) | 24 | (-35, 0) | 10 | 100 | 1..115 | [-59.0, 31.0, -37.0, 1.0] | 1B@11 1B@16 1B@26 99@61 32@81 32@101 |
| 4 | 1 | 126 (2.097) | 25 | (-45, 0) | 10 | 100 | 6..120 | [-69.0, 21.0, -37.0, 1.0] | B@1 1B@16 1B@21 1B@31 99@66 32@86 32@106 |
| 4 | 2 | 131 (2.180) | 26 | (-65, 0) | 10 | 100 | 11..125 | [-89.0, 1.0, -37.0, 1.0] | B@1 1B@21 1B@26 1B@36 99@71 32@91 32@111 |
| 5 | 0 | 141 (2.346) | 28 | (-30, 0) | 10 | 140 | 1..140 | [-54.0, 0.0, -49.0, 1.0] | 1C@6 32@36 32@56 1B@76 1B@96 1B@116 |
| 5 | 1 | 146 (2.429) | 29 | (-40, 0) | 10 | 140 | 6..145 | [-64.0, -10.0, -49.0, 1.0] | B@1 1C@11 32@41 32@61 1B@81 1B@101 1B@121 |
| 5 | 2 | 151 (2.513) | 30 | (-60, 0) | 10 | 140 | 11..150 | [-84.0, -30.0, -49.0, 1.0] | B@1 1C@16 32@46 32@66 1B@86 1B@106 1B@126 |
| 6 | 0 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-64.0, 54.0, -69.0, 39.0] | 1B@1 1B@21 1B@41 1B@61 1B@81 1B@101 1B@121 1B@141 |
| 6 | 1 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-64.0, 54.0, -69.0, 39.0] | 1B@1 1B@21 1B@41 1B@61 1B@81 1B@101 1B@121 1B@141 |
| 6 | 2 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-64.0, 54.0, -69.0, 39.0] | 1B@1 1B@21 1B@41 1B@61 1B@81 1B@101 1B@121 1B@141 |
| 7 | 0 | 141 (2.346) | 28 | (-105, 0) | 20 | 85 | 11..135 | [-147.0, 14.0, -80.0, 5.0] | 3E@11 32@46 33@81 46@106 |
| 7 | 1 | 141 (2.346) | 28 | (-105, 0) | 20 | 85 | 11..135 | [-147.0, 14.0, -80.0, 5.0] | 3E@11 32@46 33@81 46@106 |
| 7 | 2 | 141 (2.346) | 28 | (-105, 0) | 20 | 85 | 11..135 | [-147.0, 14.0, -80.0, 5.0] | 3E@11 32@46 33@81 46@106 |
| 8 | 0 | 201 (3.344) | 40 | (-95, 0) | 10 | 185 | 1..200 | [-131.0, 24.0, -39.0, 9.0] | 1B@1 46@26 1B@71 1B@76 1B@86 99@116 99@121 99@126 99@131 99@136 99@141 99@146 99@151 99@156 |
| 8 | 1 | 201 (3.344) | 40 | (-95, 0) | 10 | 185 | 1..200 | [-131.0, 24.0, -39.0, 9.0] | 1B@1 46@26 1B@71 1B@76 1B@86 99@116 99@121 99@126 99@131 99@136 99@141 99@146 99@151 99@156 |
| 8 | 2 | 201 (3.344) | 40 | (-95, 0) | 10 | 185 | 1..200 | [-131.0, 24.0, -39.0, 9.0] | 1B@1 46@26 1B@71 1B@76 1B@86 99@116 99@121 99@126 99@131 99@136 99@141 99@146 99@151 99@156 |

Displacement (sum of the velocities, class 0) per facing and total frames (class 1 adds 5 frames and 10 px, class 2 adds 10 frames and 30 px to stages 1-5, in every facing):

| stage | left (x, y) | right | up | down | frames left / up |
|---|---|---|---|---|---|
| 1 | (-20, 0) | (20, 0) | (0, -20) | (0, 20) | 66 / 71 |
| 2 | (-35, 0) | (35, 0) | (0, -35) | (0, 35) | 81 / 81 |
| 3 | (-20, 0) | (20, 0) | (0, -20) | (0, 20) | 106 / 111 |
| 4 | (-35, 0) | (35, 0) | (0, -15) | (0, 35) | 121 / 126 |
| 5 | (-30, 0) | (30, 0) | (0, -30) | (0, 30) | 141 / 151 |
| 6 | (-10, 0) | (10, 0) | (10, 0) | (10, 0) | 151 / 151 |
| 7 | (-105, 0) | (105, 0) | (0, -105) | (0, 105) | 141 / 141 |
| 8 | (-95, 0) | (95, 0) | (0, -75) | (0, 95) | 201 / 201 |

Up and down use their own pieces of the same total length; the paths differ in stages 4 (up 15 px, down 35 px), 6 and 8 (up 75 px, down 95 px).

`move px` is the sum of the velocities (open ground); `box union` is the union of the weapon boxes in world offsets from the hero's position at frame 0 (min x, max x, min y, max y; facing left, so forward is negative x; y negative is up) including the hero's own movement; `max height` is the maximum sprite height `E045` in pixels (jump). Sound ids are in hexadecimal; each is requested at the frame shown. Class 1/2 rows differ from class 0 only by the dash prefix (+5/+10 frames, +10/+30 px).

### 4.4 Frame-by-frame timelines (class 0, facing left) [V]
Columns as in section 1.2. `v` is px per frame; z is the vertical velocity of jumps; "hero offset" is the displacement at the start of the row.

Stage 1 (three normal swings, one hit):

stage 1, class 0, facing left: end of state at frame 66 (1.098 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 0 | -12, -15, 24, 24 | intangible | 0, 0, 0 |
| 16-20 | 0 | -12, -15, 24, 24 | intangible | -10, 0, 0 |
| 21-30 | 0 | - | tangible | -10, 0, 0 |
| 31-40 | -1, 0, 0 | -12, -15, 24, 24 | intangible | -10, 0, 0 |
| 41-45 | 0 | -12, -15, 24, 24 | intangible | -20, 0, 0 |
| 46-50 | 0 | -8, -7, 16, 16 | intangible | -20, 0, 0 |
| 51-60 | 0 | -8, -15, 28, 20 | intangible | -20, 0, 0 |
| 61-65 | 0 | -8, -7, 16, 16 | intangible | -20, 0, 0 |
| 66-66 | 0, 0, -4 | - | tangible | -20, 0, 0 |

Sprite frames, duration of each in steps (10 frames, 13 steps): 1 2 1 1 1 2 1 1 2 1

Stage 2:

stage 2, class 0, facing left: end of state at frame 81 (1.348 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-10 | -1, 0, 0 | -12, -15, 24, 16 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, -15, 24, 16 | intangible | -5, 0, 0 |
| 16-25 | 0 | - | tangible | -5, 0, 0 |
| 26-35 | -1, 0, 0 | -12, -15, 24, 24 | intangible | -5, 0, 0 |
| 36-40 | 0 | -12, -15, 24, 24 | intangible | -15, 0, 0 |
| 41-55 | 0 | - | tangible | -15, 0, 0 |
| 56-60 | -2, 0, 0 | -16, -11, 32, 32 | intangible | -15, 0, 0 |
| 61-65 | -2, 0, 0 | -16, -18, 32, 32 | intangible | -25, 0, 0 |
| 66-80 | 0 | -16, -18, 32, 32 | intangible | -35, 0, 0 |
| 81-81 | 0, 0, -4 | - | tangible | -35, 0, 0 |

Sprite frames, duration of each in steps (13 frames, 16 steps): 1 1 1 1 1 2 1 1 1 1 1 1 3

Stage 3 (adds a jump with a large box):

stage 3, class 0, facing left: end of state at frame 106 (1.764 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-15 | -1, 0, 0 | -12, -15, 24, 24 | intangible | 0, 0, 0 |
| 16-20 | 0 | -12, -15, 24, 24 | intangible | -10, 0, 0 |
| 21-25 | 0 | -8, -7, 16, 16 | intangible | -10, 0, 0 |
| 26-35 | 0 | -8, -15, 28, 20 | intangible | -10, 0, 0 |
| 36-40 | 0 | -8, -7, 16, 16 | intangible | -10, 0, 0 |
| 41-45 | 0 | - | tangible | -10, 0, 0 |
| 46-55 | -1, 0, 0 | -12, -15, 24, 24 | intangible | -10, 0, 0 |
| 56-60 | 0 | -12, -15, 24, 24 | intangible | -20, 0, 0 |
| 61-70 | 0 | - | tangible | -20, 0, 0 |
| 71-80 | 0, 0, 1 | - | tangible | -20, 0, 0 |
| 81-95 | 0 | 0, -25, 48, 48 | intangible | -20, 0, 10 |
| 96-105 | 0, 0, -1 | - | tangible | -20, 0, 10 |
| 106-106 | 0, 0, -4 | - | tangible | -20, 0, 0 |

Sprite frames, duration of each in steps (16 frames, 21 steps): 1 2 1 1 2 1 1 2 1 1 1 2 1 1 1 2

Stage 4:

stage 4, class 0, facing left: end of state at frame 121 (2.013 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | -1, 0, 1 | -12, -15, 24, 16 | intangible | 0, 0, 0 |
| 6-10 | -1, 0, 1 | -12, -20, 24, 16 | intangible | -5, 0, 5 |
| 11-15 | -2, 0, 0 | -12, -25, 24, 24 | intangible | -10, 0, 10 |
| 16-25 | 3, 0, 0 | 12, -25, 24, 24 | intangible | -20, 0, 10 |
| 26-35 | -3, 0, 0 | -12, -25, 24, 24 | intangible | 10, 0, 10 |
| 36-45 | 0 | -12, -25, 24, 24 | intangible | -20, 0, 10 |
| 46-55 | 0, 0, -1 | -12, -25, 24, 16 | intangible | -20, 0, 10 |
| 56-60 | 0 | - | tangible | -20, 0, 0 |
| 61-65 | -1, 0, 0 | -12, -15, 24, 16 | intangible | -20, 0, 0 |
| 66-70 | 0 | -16, -15, 24, 16 | intangible | -25, 0, 0 |
| 71-75 | 0 | - | tangible | -25, 0, 0 |
| 76-80 | 0 | -8, -7, 16, 16 | intangible | -25, 0, 0 |
| 81-90 | 0 | -8, -15, 28, 20 | intangible | -25, 0, 0 |
| 91-95 | 0 | -8, -7, 16, 16 | intangible | -25, 0, 0 |
| 96-100 | 0 | - | tangible | -25, 0, 0 |
| 101-110 | -1, 0, 0 | -12, -15, 24, 24 | intangible | -25, 0, 0 |
| 111-115 | 0 | -12, -15, 24, 24 | intangible | -35, 0, 0 |
| 116-120 | 0 | - | tangible | -35, 0, 0 |
| 121-121 | 0, 0, -4 | - | tangible | -35, 0, 0 |

Sprite frames, duration of each in steps (18 frames, 24 steps): 1 1 1 2 2 2 2 1 1 1 1 1 2 1 1 2 1 1

Stage 5:

stage 5, class 0, facing left: end of state at frame 141 (2.346 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | -1, 0, 1 | -12, -15, 24, 16 | intangible | 0, 0, 0 |
| 6-10 | -1, 0, 1 | -12, -20, 24, 24 | intangible | -5, 0, 5 |
| 11-20 | -1, 0, 0 | -12, -25, 24, 24 | intangible | -10, 0, 10 |
| 21-25 | -1, 0, -1 | -12, -25, 24, 24 | intangible | -20, 0, 10 |
| 26-28 | -1, 0, -2 | -12, -20, 24, 16 | intangible | -25, 0, 5 |
| 29-30 | -1, 0, 0 | -12, -20, 24, 16 | intangible | -28, 0, 0 |
| 31-35 | 0 | -8, -7, 16, 16 | intangible | -30, 0, 0 |
| 36-45 | 0 | -8, -15, 28, 20 | intangible | -30, 0, 0 |
| 46-55 | 0 | -8, -7, 16, 16 | intangible | -30, 0, 0 |
| 56-65 | 0 | -8, -15, 28, 20 | intangible | -30, 0, 0 |
| 66-70 | 0 | -8, -7, 16, 16 | intangible | -30, 0, 0 |
| 71-75 | 0, 0, 2 | -12, -15, 24, 16 | intangible | -30, 0, 0 |
| 76-135 | 0 | 0, -25, 48, 48 | intangible | -30, 0, 10 |
| 136-140 | 0, 0, -2 | -12, -25, 24, 16 | intangible | -30, 0, 10 |
| 141-141 | 0, 0, -4 | - | tangible | -30, 0, 0 |

Sprite frames, duration of each in steps (25 frames, 28 steps): 1 1 2 1 1 1 2 1 1 2 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1

Stage 6 (a closed loop of 1-2 px per frame, up to 40 px from the start in x and 30 px in y, with a 48 x 48 box for 150 frames and sound 0x1B every 20 frames):

stage 6, class 0, facing left: end of state at frame 151 (2.513 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | -1, -1, 0 | 0, -15, 48, 48 | intangible | 0, 0, 0 |
| 11-20 | 0, -1, 0 | 0, -15, 48, 48 | intangible | -10, -10, 0 |
| 21-30 | 1, -1, 0 | 0, -15, 48, 48 | intangible | -10, -20, 0 |
| 31-40 | 2, 1, 0 | 0, -15, 48, 48 | intangible | 0, -30, 0 |
| 41-50 | 1, 2, 0 | 0, -15, 48, 48 | intangible | 20, -20, 0 |
| 51-60 | -1, 2, 0 | 0, -15, 48, 48 | intangible | 30, 0, 0 |
| 61-70 | -2, 1, 0 | 0, -15, 48, 48 | intangible | 20, 20, 0 |
| 71-80 | -2, -1, 0 | 0, -15, 48, 48 | intangible | 0, 30, 0 |
| 81-90 | -2, -2, 0 | 0, -15, 48, 48 | intangible | -20, 20, 0 |
| 91-100 | 1, -2, 0 | 0, -15, 48, 48 | intangible | -40, 0, 0 |
| 101-110 | 2, -1, 0 | 0, -15, 48, 48 | intangible | -30, -20, 0 |
| 111-120 | 2, 1, 0 | 0, -15, 48, 48 | intangible | -10, -30, 0 |
| 121-130 | 0, 1, 0 | 0, -15, 48, 48 | intangible | 10, -20, 0 |
| 131-140 | -1, 1, 0 | 0, -15, 48, 48 | intangible | 10, -10, 0 |
| 141-150 | -1, 0, 0 | 0, -15, 48, 48 | intangible | 0, 0, 0 |
| 151-151 | 0, 0, -4 | - | tangible | -10, 0, 0 |

Sprite frames, duration of each in steps (30 frames, 30 steps): 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1

Stage 7 (jump and dash 80 px at 4 px/frame, then swings):

stage 7, class 0, facing left: end of state at frame 141 (2.346 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0, 0, 2 | - | tangible | 0, 0, 0 |
| 11-20 | -4, 0, 0 | 0, -31, 28, 28 | intangible | 0, 0, 20 |
| 21-25 | -4, 0, 0 | 0, -66, 28, 28 | intangible | -40, 0, 20 |
| 26-30 | -4, 0, 0 | 0, -38, 28, 28 | intangible | -60, 0, 20 |
| 31-40 | 0, 0, -2 | - | tangible | -80, 0, 20 |
| 41-45 | 0 | - | tangible | -80, 0, 0 |
| 46-55 | -1, 0, 0 | -12, -15, 24, 24 | intangible | -80, 0, 0 |
| 56-60 | 0 | -12, -15, 24, 24 | intangible | -90, 0, 0 |
| 61-75 | 0 | - | tangible | -90, 0, 0 |
| 76-80 | -2, 0, 0 | -16, -11, 32, 32 | intangible | -90, 0, 0 |
| 81-85 | -2, 0, 0 | -16, -18, 32, 32 | intangible | -100, 0, 0 |
| 86-100 | 0 | -16, -18, 32, 32 | intangible | -110, 0, 0 |
| 101-105 | 0 | - | tangible | -110, 0, 0 |
| 106-110 | -1, 0, 0 | - | tangible | -110, 0, 0 |
| 111-120 | 0 | -12, -15, 24, 32 | tangible | -111, 0, 0 |
| 121-130 | 1, 0, 0 | -20, -15, 32, 32 | tangible | -111, 0, 0 |
| 131-135 | 0 | -20, -15, 32, 32 | tangible | -101, 0, 0 |
| 136-140 | 0 | - | tangible | -101, 0, 0 |
| 141-141 | 0, 0, -4 | - | tangible | -101, 0, 0 |

Sprite frames, duration of each in steps (21 frames, 28 steps): 2 1 1 1 1 2 1 2 1 1 1 1 1 1 3 1 1 2 2 1 1

Stage 8 (the longest: 201 frames):

stage 8, class 0, facing left: end of state at frame 201 (3.344 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | -4, 0, 0 | 0, -15, 48, 48 | intangible | 0, 0, 0 |
| 21-25 | 0 | - | tangible | -80, 0, 0 |
| 26-30 | -1, 0, 0 | - | tangible | -80, 0, 0 |
| 31-40 | 0 | -12, -15, 24, 32 | tangible | -85, 0, 0 |
| 41-50 | 1, 0, 0 | -20, -15, 32, 32 | tangible | -85, 0, 0 |
| 51-55 | 0 | -20, -15, 32, 32 | tangible | -75, 0, 0 |
| 56-60 | 0 | - | tangible | -75, 0, 0 |
| 61-65 | -1, 0, 1 | -12, -15, 24, 16 | intangible | -75, 0, 0 |
| 66-70 | -1, 0, 1 | -12, -20, 24, 16 | intangible | -80, 0, 5 |
| 71-75 | -2, 0, 0 | -12, -25, 24, 24 | intangible | -85, 0, 10 |
| 76-85 | 3, 0, 0 | 12, -25, 24, 24 | intangible | -95, 0, 10 |
| 86-95 | -3, 0, 0 | -12, -25, 24, 24 | intangible | -65, 0, 10 |
| 96-105 | 0 | -12, -25, 24, 24 | intangible | -95, 0, 10 |
| 106-115 | 0, 0, -1 | -12, -25, 24, 16 | intangible | -95, 0, 10 |
| 116-120 | 0 | -8, -11, 16, 16 | intangible | -95, 0, 0 |
| 121-125 | 0 | -24, -11, 16, 16 | intangible | -95, 0, 0 |
| 126-130 | 0 | -8, -11, 16, 16 | intangible | -95, 0, 0 |
| 131-135 | 0 | -20, -15, 20, 16 | intangible | -95, 0, 0 |
| 136-140 | 0 | -8, -11, 16, 16 | intangible | -95, 0, 0 |
| 141-145 | 0 | -24, -11, 16, 24 | intangible | -95, 0, 0 |
| 146-150 | 0 | -8, -11, 16, 16 | intangible | -95, 0, 0 |
| 151-155 | 0 | -24, -15, 24, 28 | intangible | -95, 0, 0 |
| 156-160 | 0 | -8, -11, 16, 16 | intangible | -95, 0, 0 |
| 161-170 | 0 | -8, -15, 28, 20 | intangible | -95, 0, 0 |
| 171-200 | 0 | -8, -7, 16, 16 | intangible | -95, 0, 0 |
| 201-201 | 0, 0, -4 | - | tangible | -95, 0, 0 |

Sprite frames, duration of each in steps (29 frames, 40 steps): 1 1 1 1 1 1 2 2 1 1 1 1 1 2 2 2 2 1 1 1 1 1 1 1 1 1 2 3 3

### 4.5 What the stages are not [V]
- Loops "2x / 3x / 7x" seen on the sprite sheets are repeated pieces (stage 5: three copies of one piece; stage 6: fifteen alternations of two 2-step pieces; stage 8: a nine-sound piece), but each repetition is animation and sound only: the target is hit once per attack (section 5).
- The hero is airborne in stages 3, 4, 5, 7 and 8 (jump pieces with vz = +1/+2 and the end-of-jump -1/-2), up to 10 px (20 px in stage 7). The weapon box of the air pieces is placed at the sprite's height, so a ground target is hit only while the box overlaps it.

## 5. Hits, damage, status, sounds

### 5.1 One hit per target [V]
Measured with a dummy monster at 14 and 30 px in front, for stages 0-8: one HP change per attack (never two), at the frame listed below; with two dummies both are hit once. Damage frame = box frame + 2 for a slot-3 monster (section 2.5). The target's knockback is decided by the target's hurt reaction (section 5.5).

| stage | box first frame | hit flag frame | damage frame | damage (this RNG state) |
|---|---|---|---|---|
| 0 | 6 | 7 | 8 | 153 |
| 1 | 6 | 7 | 8 | 197 |
| 2 | 6 | 7 | 8 | 241 |
| 3 | 6 | 7 | 8 | 285 |
| 4 | 1 | 2 | 3 | 339 |
| 5 | 1 | 2 | 3 | 384 |
| 6 | 1 | 2 | 3 | 430 |
| 7 | 11 | 12 | 13 | 460 |
| 8 | 1 | 2 | 3 | 520 |

(stage 0 = a normal swing with the target near and an even `$F4`, i.e. variant 1; `box first frame` = first frame with a non-empty weapon box counted from the press/release frame; a target further away is hit later, when the moving box reaches it, e.g. stage 7 reached the dummy at 30 px at frame 18.)

### 5.2 Damage [V]
Each hit uses `docs/rom-combat.md` section 4.3 with the stage read from `E19B`: `v = atk * (2*stage + 4) >> 2` (x1.0, 1.5, 2.0, ... 5.0 for stage 0-8). `E19B` kept its stage value for the whole power attack (sampled every frame) and the stage is reset to 0 only at the end of the attack. Measured with the real routines on 300 random RNG states, hero 0 (atk 76, accuracy 94, crit base 18, `E1E6` = 8) against a dummy with evade 0 and defense 0, Saber nibble cleared:

| stage s | atk*(2s+4)>>2 | hit rate | min | mean | max |
|---|---|---|---|---|---|
| 0 | 76 | 1.00 | 71 | 151.8 | 294 |
| 1 | 114 | 1.00 | 107 | 190.5 | 376 |
| 2 | 152 | 1.00 | 142 | 238.0 | 456 |
| 3 | 190 | 1.00 | 178 | 271.3 | 536 |
| 4 | 228 | 1.00 | 214 | 316.8 | 618 |
| 5 | 266 | 1.00 | 250 | 370.2 | 698 |
| 6 | 304 | 1.00 | 285 | 402.5 | 780 |
| 7 | 342 | 1.00 | 321 | 457.1 | 860 |
| 8 | 380 | 1.00 | 357 | 502.3 | 940 |

(the spread is the random term, the `E1E6`^2 = 64 bonus and the critical hit, which doubles; the game caps one hit at 999.)

### 5.3 Status and element
The glove rows have weapon mask 0 and no element; rows 2 and 6 inflict status words 0x0010 / 0x2000 with 80 % per damaging hit (once per attack, since there is one hit) [V for the constancy of `E199/E1F7`, rows from `data/weapons.json`].

### 5.4 Sound ids (the pair written to `$1E01/$1E02` for the sound driver at `$C3:0004`; the third value is the pan/volume byte) [V]
| id | where |
|---|---|
| 0x99 | strike of normal variants 0 and 1, nine times in the stage-8 flurry (piece P17) |
| 0x32 | strike of normal variants 2 and 3 (and every N-piece inside power attacks) |
| 0x0B | class 1 / class 2 dash prefix |
| 0x33 | stage-2 final piece (7 steps) |
| 0x1B | stages 3-6, 8 jump and spin pieces |
| 0x1C | stage-5 first piece |
| 0x3E, 0x46 | stage 7 |
| 0x35 (second byte 0x0F, third 96) | the damage frame of a hit on the dummy |
| 0x26, 0x27, 0x28 | gauge empty, charge hum (every 8 frames), stage reached |

### 5.5 Knockback of the target [V]
The glove itself applies no knockback; the hurt reaction code of the target is chosen from the damage it takes (`$C0:4F2A-4F44`, `$C0:4EBC`): a hit of at least a quarter of the target's max HP gives hurt code `E011 = 0x89`, which pushes the target **40 px opposite to its own facing** (`docs/rabite.md` section 7: 3 px/frame for 10 frames, then 2 px/frame for 5), a smaller hit gives code 0x88 and no push. Measured on the dummy (facing down, pushed up):

| dummy max HP (quarter) | stage 0 damage 153 | stage 4 damage 339 | stage 8 damage 520 |
|---|---|---|---|
| 600 (150) | 0x89, pushed 40 px | 0x89, 40 px | 0x89, 40 px |
| 1000 (250) | 0x88, none | 0x89, 40 px | 0x89, 40 px |
| 2000 (500) | 0x88, none | 0x88, none | 0x89, 40 px |

(damage values are for one RNG state.) So a higher stage knocks back more targets only because it deals more damage. Separately, in the first run a dummy standing in the path of the 5-px lunge moved the same 5 px with the hero (a contact push); this was seen once and not measured further.

## 6. Script facts used (decoded from `$C0:F5A3-F6C0`, `$C0:F90B-F9C6`, `$C1:D48D-D8F2`)
- A script is a byte stream: a byte < 0x80 starts a frame word of two bytes (duration code in the low 3 bits of the first byte, sprite frame number in the second); 0x80-0xAF are one-byte ops, 0xB0-0xEF two-byte, 0xF0-0xF7 and 0xF9 three-byte, 0xF8 and 0xFA four-byte, 0xFB-0xFE one-byte, 0xFF ends the script (or returns from a call made with 0xF1) [C+V].
- Ops 0x8F + k, k = 0..27: velocity preset k (above) [V]. 0xF0: velocity from nibbles [C, V in stage 6/7]. 0xF1 lo hi: call. 0xF9 lo hi: sound request (id = lo + 256 hi). 0xFE, 0xFC: wait while a status bit is set [C]. Ops 0x80-0x8E and 0xB0-0xEF set palette/effect/flag variables of the hero and were not decoded one by one.
- The weapon box is not an op: it comes from the sprite frame description fetched with each frame word, so box timing is tied to the frame words (this is why the boxes change at step boundaries only).

## 7. Tools and commands
```
R=path/to/rom.sfc ; S=path/to/state.zs1        # a state with the three heroes idle on a map
python3 tools/glove_attacks.py "$R" "$S" data/glove_attacks.json            # all sections, ~25 min
python3 tools/glove_attacks.py "$R" "$S" out.json variants gauge             # some sections
python3 tools/glove_report.py data/glove_attacks.json power                 # tables
python3 tools/glove_report.py data/glove_attacks.json tl power 8 0 left     # one timeline
```
`tools/glove_sim.py` (library): `GloveSim(rom, state, slot, row, level, mon=(dx,dy))`, `.frame(pad)`, `.sample()`, `.events`.
Data: `data/glove_attacks.json`. Keys: `normal` (the short table of section 1: per variant and facing, steps, frames, seconds, movement, box, sound; `heroes`), `normal_runs` (the underlying per-hero runs), `chooser`, `gauge`, `charge`, `power` (`slotN` > stage > class > facing; segment rows have the fields listed in `SEG_FIELDS` of `tools/glove_attacks.py`), `structure` (pieces and their compositions), `hits`, `invulnerability`.

## 8. Verified and open
Verified by execution [V]: the swing start and its latency; the four normal variants (steps, frames, movement, boxes, sounds) for the three heroes and four facings; the variant chooser (distance thresholds on both axes, parity, class = larger of the two axes, independence of facing); no combo and no buffering of presses; the gauge (start value, freeze, countdown, 15-frame hold, damage and accuracy effect) for three Agi values; charge timing per stage for three heroes; the release into the power attack and the dependence on stage only; all 24 power attacks (stage 1-8, class 0-2) for facing left/right/up/down on hero 0 and their timing and weapon box timing on heroes 1 and 2; the box overlap rule on both axes; one hit per target; the damage per stage and per gauge value with the real hit routines; the knockback rule; the body-box vulnerability on three attacks.
Read from the disassembly only [C]: the ops 0xFB-0xFE semantics, the sound request mechanism (`$C0:BB11`), the role of `$C0:B851` before the swing start, the position of the NMI counter increment.

## 9. Open questions (no values claimed)
- The rule for choosing the swing variant with more than one enemy on screen (two enemies always gave the near class in the tests); the exact metric behind the x/y thresholds 26/42 and 24/40.
- Whether the knockback test is `damage >= max HP/4` or `>`: 153 against 150 pushed, equality was not produced.
- What the third box `E0CC-E0CF` does (it is non-empty during the strike frames); what ops 0x80-0x8E, 0xB0-0xEF do beyond the ones listed.
- Whether a frame-skipping slowdown in busy scenes (the main loop waiting for a second NMI) stretches these timings: the counts here assume one main-loop pass per video frame.

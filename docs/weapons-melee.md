# Sword, axe and spear attacks of the three heroes (weapon types 1, 2, 3; rows 9-35) - recovered from the ROM (Secret of Mana USA)

Tags: **[V]** means the real 65816 code was executed in `tools/cpu65816.py` (the whole per-frame routine `$C0:B08C` on a ZSNES save state with the controller word injected) and the numbers were read from the running objects; **[C]** means read from the disassembly, not executed. What is not determined is listed in section 10 and carries no guessed values. This document does for the three melee weapon types what `docs/glove-attacks.md` does for the glove; the glove document explains the shared machinery (two clocks, boxes, gauge, hit test) and is referred to instead of repeated where the result is the same.

Addressing: 2 MiB HiROM, `$Cx:xxxx` = file offset `((x-0xC0)<<16)|xxxx`, `$01:xxxx` is the mirror of `$C1:xxxx`. Animation scripts live in bank `$D1`. No ROM bytes are stored in the repo: scripts are described by decoded numbers. Object fields are offsets in the 0x200-byte object record at `$7E:E000 + slot*0x200` (`docs/rom-combat.md` section 1.1). Heroes are slots 0, 1, 2, monsters start at slot 3. Weapon types: `type = row / 9`; rows 9-17 are type 1, 18-26 type 2, 27-35 type 3 (`data/weapons.json`). The weapon types 4-7 (the other family) and the glove (type 0) are not covered here.

Time: **1 frame = 1/60.0988 s = 16.638 ms**. A hero advances its animation once per 5th frame (12.02 Hz); movement, the gauge and the input run every frame (`docs/glove-attacks.md` section 1.1).

Method: `tools/weapon_attacks.py` generalises `tools/glove_attacks.py`. It loads a save state, equips the weapon row with the game's own routines (`$C0:4530` stats, `$C0:EA41` animation tables), makes one hero the pad-1 hero and runs `$C0:B08C` once per video frame with the pad word injected where the game reads `$4218/$4219` (B = 0x8000). A dummy monster (id 0, HP 9999, AI step disabled) is created by the game's spawner `$C0:DE3B` when a hit is needed. Unlike the first version of the glove runs, the attack animation is **never forced**: the real chooser `$C1:E40E` runs, and the animation wanted is obtained by overriding the result of the distance routine `$C1:E4CC` (at `$C1:E418`) and by choosing the parity of the frame counter `$F4`, then checking that `E011` equals the wanted id. (Forcing `E011` after the start frame restarts the script when the press falls on `$56` = 3 and adds 5 frames; the weapon runs here do not have that artifact.) Run time: roughly 25 minutes per weapon. The save state had the three heroes idle on an open map (Agi 79, 63, 57); animation, boxes and speeds do not depend on the hero's stats, only the numbers marked "per hero" do. All measurements below are for hero 0 facing left unless stated; right is the exact mirror and up and down have their own scripts.

## 0. Summary

1. **No combo, no buffering.** One press of B starts exactly one swing; a press during the swing is discarded; the next swing needs a new press after the state byte `E01C` has returned to 0. The swing is never blocked by the weapon gauge `E1ED`, which only weakens damage (section 2.4) [V]. Same as the glove.
2. **The normal swing has four animation ids (0-3) per weapon, but ids 2 and 3 are the same script for all three weapons**, so there are three distinct swings. Sword: 3, 5 and 3 steps; axe: 4, 4 and 4 steps (three different pictures/boxes); spear: 3, 3 and 5 steps. One step = 5 frames. A swing lasts **15-25 frames after the first step** and **15-29 frames from the press** (section 1) [V].
3. **The first step comes 0-4 frames after the press: `(3 - $56) mod 5`** (press at `$56` = 3 starts the script in the press frame itself) [V]. The glove document gives 1-5 for this; see section 1.1.
4. **No normal swing moves the hero** (net 0 px in all four variants, all weapons); the d-pad is ignored for the whole swing and the facing cannot change [V].
5. Which variant plays is chosen exactly as for the glove: distance class of the nearest enemy (26/42 px along x, 24/40 px along y) and the parity of `$F4` (section 2.2) [V].
6. **After the swing** the gauge `E1ED = (100 - Agi)/2 + 50` is loaded (60 / 68 / 71 for Agi 79 / 63 / 57), frozen during swings, counts down 1 per frame and is seen at 1 for 16 frames: 75 / 83 / 86 frames until empty. Only at `E1ED = 0` is a swing at full damage, and only then does charging start [V].
7. **Charge**: identical to the glove; stage `k` is reached `swing end + gauge frames + 90 k - 3` frames after the press and the weapon level only caps the stage (section 3) [V].
8. **Releasing B with stage s >= 1 starts the charged attack `E011 = 4 s + class`** in the same frame; 8 stages x 3 distance classes = **24 charged attacks per weapon**, 31-151 frames (0.52-2.51 s) (section 4). Classes 1 and 2 add a short dash (10 px and 30 px, +5 and +10 frames, sound 0x0B) in front of the class 0 attack in stages 1-5; stages 6, 7 and 8 are identical for the three classes [V].
9. **Every attack hits each target at most once** (one damage event per target per attack) however long the box stays active: the hit flag `E05A` is only cleared when the attack ends. Damage per hit is the normal formula with `E19B` = stage: multiplier `(2s+4)/4` = x1 ... x5, identical for the three weapons and for the glove (section 5) [V].
10. **No projectile or other object is created** by any sword, axe or spear animation (objects in slots 3-31 were watched for all 28 animations; nothing appeared). The spear never throws anything (section 4.6) [V].
11. **The hero can be hit by a monster weapon box only in frames in which the body box of the previous frame was non-empty.** During most swings and charged attacks the body box is empty from frame 1 on; the exceptions are the wind-up of the sword id 1 (frames 1-11 and 22-26), of the axe id 1 (1-6) and a stretch of the axe stage 8 attack (62-71) (section 2.6) [V].
12. **All nine rows of a weapon type have identical animations and timelines** (checked for 10 attacks of every row); rows differ only in the stats (atk, hit, crit, Agi bonus, element/enemy-type mask, status). The only timing difference is the gauge: the Mana Sword row (Agi +5) loads 58 instead of 60 (section 2.7) [V].
13. The three heroes share all scripts, speeds and box sizes. Hero 1 and 2 have the weapon box active one frame later than hero 0 (section 2.7) [V].

## 1. Normal attacks

### 1.0 In one table (side facing, hero 0; frame counts are from the first animation step, 1 step = 5 frames)

| quantity | sword | axe | spear |
|---|---|---|---|
| distinct swings (animation ids) | 3 (ids 0, 1, 2 = 3) | 3 (ids 0, 1, 2 = 3) | 3 (ids 0, 1, 2 = 3) |
| steps, ids 0 / 1 / 2 (= 3), side | 3 / 5 / 3 | 4 / 4 / 4 | 3 / 3 / 5 |
| steps, ids 0 / 1 / 2 (= 3), up or down | 3 / 5 / 3 | 4 / 4 / 4 | 3 / 3 / 5 |
| sprite frames, steps each (ids 0 / 1 / 2) | 1+1+1 ; 1+1+2+1 ; 1+1+1 | 1+1+1+1 ; 1+3 ; 1+1+1+1 | 1+1+1 ; 1+1+1 ; 1+2+2 |
| first step to end of swing (frames) | 15 / 25 / 15 | 20 / 20 / 20 | 15 / 15 / 25 |
| press to end of swing, frames (latency 0-4 added) | 15-19 / 25-29 / 15-19 | 20-24 / 20-24 / 20-24 | 15-19 / 15-19 / 25-29 |
| same in seconds | 0.250-0.316 / 0.416-0.483 / 0.250-0.316 | 0.333-0.399 / 0.333-0.399 / 0.333-0.399 | 0.250-0.316 / 0.250-0.316 / 0.416-0.483 |
| weapon box active, frames after the first step (ids 0 / 1 / 2) | 0-14 / 10-19 / 0-14 | 0-19 / 5-19 / 0-19 | 0-14 / 0-14 / 0-24 |
| hero moves during the swing | no (net 0, 0 px, all ids and facings) | no (net 0, 0 px, all ids and facings) | no (net 0, 0 px, all ids and facings) |
| sound id at the first step (ids 0 / 1 / 2) | 0x4 / 0x2 / 0x3 | 0x8 / 0x8 / 0x8 | 0x1B / 0x1B / 0xB |
| combo window | none | none | none |
| d-pad | ignored until `E01C` returns to 0 | same | same |
| weapon gauge after the swing | 60 / 68 / 71 (Agi 79 / 63 / 57); empty after 75 / 83 / 86 frames | same | same |
| damage | one hit per target per swing, `atk` (x1), reduced while the gauge is non-zero | same | same |

All four facings: up and down have the same step counts as the side facing for every id (checked for the 12 animations) [V].

### 1.1 The clocks, and the latency [V]
The two clocks are those of `docs/glove-attacks.md` section 1.1 (hero object step every 5th frame, `$56` = 3; input, movement and gauge every frame). Measured here with real presses (no forced animation): the swing starts to animate in frame `(3 - $56) mod 5` after the press frame, i.e. 3, 2, 1, 0, 4 frames for a press at `$56` = 0, 1, 2, 3, 4 (mean 2 frames). For `$56` = 3 the hero step of the press frame runs after the input handler and already reads the first script entry. (The glove document gives "1 to 5" frames, and 25 frames for the press-phase-3 column of its variants 0-2. With real presses a glove id 2 pressed at `$56` = 3 ends after 20 frames and an id 3 after 25, measured here again with the glove row; forcing `E011` after the start frame, as the earlier runs did, restarts the script in that phase and gives 5 frames more.) A swing ends in the step that executes the end op: `E01C` is cleared and the gauge is loaded in that frame.

Frames from the press to the end of the swing for every phase (`$56` of the press frame):

**sword**

| `$56` at the press | frames until the first step | variant 0 | variant 1 | variant 2 | variant 3 |
|---|---|---|---|---|---|
| 0 | 3 | 18 | 28 | 18 | 18 |
| 1 | 2 | 17 | 27 | 17 | 17 |
| 2 | 1 | 16 | 26 | 16 | 16 |
| 3 | 0 | 15 | 25 | 15 | 15 |
| 4 | 4 | 19 | 29 | 19 | 19 |

**axe**

| `$56` at the press | frames until the first step | variant 0 | variant 1 | variant 2 | variant 3 |
|---|---|---|---|---|---|
| 0 | 3 | 23 | 23 | 23 | 23 |
| 1 | 2 | 22 | 22 | 22 | 22 |
| 2 | 1 | 21 | 21 | 21 | 21 |
| 3 | 0 | 20 | 20 | 20 | 20 |
| 4 | 4 | 24 | 24 | 24 | 24 |

**spear**

| `$56` at the press | frames until the first step | variant 0 | variant 1 | variant 2 | variant 3 |
|---|---|---|---|---|---|
| 0 | 3 | 18 | 18 | 28 | 28 |
| 1 | 2 | 17 | 17 | 27 | 27 |
| 2 | 1 | 16 | 16 | 26 | 26 |
| 3 | 0 | 15 | 15 | 25 | 25 |
| 4 | 4 | 19 | 19 | 29 | 29 |

Notes:
- A frame word with duration code d lasts d+1 steps when d < 4 and 1 step otherwise (`docs/glove-attacks.md` section 1.2); 1 step = 5 frames = 0.0832 s.
- Facing codes in `E010`: 0 = up, 1 = down, 2 = right, 0x82 = left. Right is the mirror of left for the velocities, the weapon box (centre x negated, size, y), the body box size and y and the displacement in the 4 normal ids and 24 charged attacks measured per weapon, with the exceptions below; the only differences are the body box x offset (mirrored sprite) in the pre-swing frame of the ids 1 and the last frame of the axe stage-8 attack, shortened by a wall of the map (-111 against +120 measured, -120 nominal) [V].
- Box coordinates are in pixels relative to the hero position, centre x (forward is negative for left), centre y (negative = up), width, height (`docs/glove-attacks.md` section 2.5).

### 1.2 The distinct swings, hero 0, facing left (frame 0 = press frame, first step at frame 1)

| weapon | id | steps | sprite frames, steps each | end of swing (frame) | weapon boxes (first frame, frames, centre x, y, w x h) | sound |
|---|---|---|---|---|---|---|
| sword | 0 | 3 | 1+1+1 | 16 | 1, 5: -16, -26, 32x32; 6, 5: -20, -15, 32x32; 11, 5: -16, 2, 32x32 | 0x4 |
| sword | 1 | 5 | 1+1+2+1 | 26 | 11, 10: -20, -11, 36x16 | 0x2 |
| sword | 2 = 3 | 3 | 1+1+1 | 16 | 1, 5: 4, -3, 28x28; 6, 5: -20, -7, 32x32; 11, 5: -12, -15, 28x28 | 0x3 |
| axe | 0 | 4 | 1+1+1+1 | 21 | 1, 10: 0, -30, 32x20; 11, 5: -16, -18, 32x32; 16, 5: 0, -3, 32x32 | 0x8 |
| axe | 1 | 4 | 1+3 | 21 | 6, 15: -16, -15, 32x16 | 0x8 |
| axe | 2 = 3 | 4 | 1+1+1+1 | 21 | 1, 10: 8, -11, 20x20; 11, 5: -4, -3, 36x24; 16, 5: -16, -15, 28x28 | 0x8 |
| spear | 0 | 3 | 1+1+1 | 16 | 1, 5: -4, -26, 48x28; 6, 5: -28, -18, 40x32; 11, 5: -16, 2, 36x36 | 0x1B |
| spear | 1 | 3 | 1+1+1 | 16 | 1, 5: 4, -3, 24x24; 6, 5: -20, -3, 40x24; 11, 5: -20, -15, 28x28 | 0x1B |
| spear | 2 = 3 | 5 | 1+2+2 | 26 | 1, 5: -4, -3, 32x12; 6, 10: -24, -11, 36x12; 16, 10: -4, -3, 32x12 | 0xB |

Facing up (centre x, y, w x h of the same boxes):

| weapon | id | weapon boxes up |
|---|---|---|
| sword | 0 | 1, 5: 0, -30, 32x32; 6, 5: 4, -26, 32x32; 11, 5: 12, -7, 32x32 |
| sword | 1 | 11, 10: 0, -22, 16x44 |
| sword | 2 | 1, 5: 12, -18, 28x28; 6, 5: 0, -30, 32x32; 11, 5: -12, -26, 28x28 |
| axe | 0 | 1, 10: -4, -34, 20x20; 11, 5: 0, -34, 20x32; 16, 5: 12, -18, 20x36 |
| axe | 1 | 6, 15: -4, -26, 16x32 |
| axe | 2 | 1, 10: 12, -7, 20x20; 11, 5: 4, -26, 36x24; 16, 5: -4, -30, 28x28 |
| spear | 0 | 1, 5: 4, -34, 32x32; 6, 5: 8, -26, 32x32; 11, 5: 8, -15, 36x36 |
| spear | 1 | 1, 5: 16, -18, 24x24; 6, 5: 4, -26, 32x32; 11, 5: -8, -18, 28x28 |
| spear | 2 | 1, 5: 8, -15, 12x32; 6, 10: 0, -34, 12x32; 16, 10: 8, -15, 12x32 |

Timelines (hero 0, facing left, class chosen so that the real chooser returns the id; `frames` counted from the press frame 0; "intangible" = body box empty; offsets are the measured displacement at the start of the row):

sword, id 0:

sword normal 0 0 left end of state at frame 16 (0.266 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 6-10 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 16-16 | 0, 0, -4 | - | tangible | 0, 0, 0 |

sword, id 1:

sword normal 1 0 left end of state at frame 26 (0.433 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-10 | 0 | - | tangible | 0, 0, 0 |
| 11-20 | 0 | -20, -11, 36, 16 | intangible | 0, 0, 0 |
| 21-25 | 0 | - | tangible | 0, 0, 0 |
| 26-26 | 0, 0, -4 | - | tangible | 0, 0, 0 |

sword, id 2:

sword normal 2 0 left end of state at frame 16 (0.266 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | 4, -3, 28, 28 | intangible | 0, 0, 0 |
| 6-10 | 0 | -20, -7, 32, 32 | intangible | 0, 0, 0 |
| 11-15 | 0 | -12, -15, 28, 28 | intangible | 0, 0, 0 |
| 16-16 | 0, 0, -4 | - | tangible | 0, 0, 0 |

axe, id 0:

axe normal 0 0 left end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | 0, -30, 32, 20 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, -18, 32, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | 0, -3, 32, 32 | intangible | 0, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | 0, 0, 0 |

axe, id 1:

axe normal 1 0 left end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-5 | 0 | - | tangible | 0, 0, 0 |
| 6-20 | 0 | -16, -15, 32, 16 | intangible | 0, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | 0, 0, 0 |

axe, id 2:

axe normal 2 0 left end of state at frame 21 (0.349 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | 8, -11, 20, 20 | intangible | 0, 0, 0 |
| 11-15 | 0 | -4, -3, 36, 24 | intangible | 0, 0, 0 |
| 16-20 | 0 | -16, -15, 28, 28 | intangible | 0, 0, 0 |
| 21-21 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, id 0:

spear normal 0 0 left end of state at frame 16 (0.266 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -4, -26, 48, 28 | intangible | 0, 0, 0 |
| 6-10 | 0 | -28, -18, 40, 32 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, 2, 36, 36 | intangible | 0, 0, 0 |
| 16-16 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, id 1:

spear normal 1 0 left end of state at frame 16 (0.266 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | 4, -3, 24, 24 | intangible | 0, 0, 0 |
| 6-10 | 0 | -20, -3, 40, 24 | intangible | 0, 0, 0 |
| 11-15 | 0 | -20, -15, 28, 28 | intangible | 0, 0, 0 |
| 16-16 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, id 2:

spear normal 2 0 left end of state at frame 26 (0.433 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 6-15 | 0 | -24, -11, 36, 12 | intangible | 0, 0, 0 |
| 16-25 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 26-26 | 0, 0, -4 | - | tangible | 0, 0, 0 |

## 2. Normal attack: rules

### 2.1 Start [V, C]
Same code path as the glove (`docs/glove-attacks.md` section 2.1): the press edge is latched into `$CC` bit 3, `$C0:B851` looks for an object in front that reacts to the button and otherwise `$C0:B29F` starts the swing: `E01C = 0x20`, `E006 = E007 = 0`, `E011` = the id from `$C1:E40E`, and if `E1ED == 0` the charge counter starts (`E01A = 1`). `B29F` returns when `E01C | E061` is non-zero.

### 2.2 Which swing plays [V, C]
The chooser `$C1:E40E` (`docs/graphics.md` section 4) computes `index = d * 144 + stage * 16 + status_variant * 4 + (target E1B1 & 2) + ($F4 & 1)`, `kind = $D1:0000[index]` and for heroes `anim = $D1:0480[E068 * 40 + kind]`. `E068` equals the weapon type after the equip refresh (1, 2, 3 measured), and the kind-to-animation map of types 1, 2 and 3 is the identity for kinds 0-35 and maps kinds 36-39 to 0, 4, 8, 12. The distance class `d` and the parity give, for an uncharged swing without a status on the target:

| nearest enemy, along x | along y | class `d` | id, `$F4` even | id, `$F4` odd |
|---|---|---|---|---|
| < 26 px | < 24 px | 0 | 1 | 0 |
| 26-41 px | 24-39 px | 1 | 2 | 1 |
| >= 42 px, or no enemy | >= 40 px | 2 or 3 | 3 | 2 |

The thresholds were scanned for all three weapons (class changes at x = 26 and 42, at y = 24 and 40; the class is the larger of the x and y classes; independent of the facing; no enemy gives the far class) and are identical to the glove [V]. The thresholds were scanned for the uncharged swing (the `E011` seen is the id for an even `$F4`, which equals `d + 1`); for the charged attacks the class was checked at 10, 36 and 100 px only. Because the scripts of ids 2 and 3 are the same, the swing seen is: near target: id 0 or 1; mid target: id 1 or 2; far or none: id 2 (both parities). Status-target variants (a target with status bit 0x01, 0x02 or 0x10 in `E190`) select kinds 7, 11 ... 35 and 36-39; for these three weapons they map to the scripts of the ordinary near attacks (section 4.2) [C]. Rule for several monsters and the `E1B1` bit: not determined.

### 2.3 Presses during a swing, and the next swing [V]
| test | sword | axe | spear |
|---|---|---|---|
| extra presses at frames 6, 12, 18 of a swing: swing starts (frames) | 0, 18 (the swing had ended at 16) | 0 | 0 |
| presses every 2nd frame: swing starts (frames) | 0, 18, 38, 58, 78 ... | 0, 22, 48, 72, 98 ... | 0, 28, 58, 88 ... |
| gauge value at the start of the repeated swings | 59 | 60, 59, 60, 59 ... | 59 |

A press during the swing is discarded; the next swing starts in the first press frame after `E01C` returned to 0. A direction pressed together with B, or pressed in the middle of the swing, changes neither the facing nor the position during the swing (spear, 26 frames, pad held for the whole swing: state 0x20 and displacement 0, 0 at frame 23; direction pressed from frame 8: facing unchanged and no walking while the state is non-zero for all three weapons); the hero turns and walks only after the state has cleared.

### 2.4 The weapon gauge `E1ED` [V]
Identical to the glove (`docs/glove-attacks.md` section 2.4). Per hero: Agi 79 / 63 / 57, loaded value `(100 - Agi)/2 + 50` = 60 / 68 / 71 (measured for the three weapons), counting down 1 per frame to 1, seen at 1 for 16 frames (this run counts 59 frames of countdown and 16 frames at 1, total 75 for Agi 79; the glove document counts the same total as 60 + 15), frozen while a swing runs (measured: 30 stays 30 for the whole next swing, then reloaded to 60). Damage with a non-zero gauge at the hit (`docs/rom-combat.md` 4.2-4.3), measured with the real hit routines on 300 random RNG states, hero 0 against a dummy with evade 0 and defense 0 (hit rate 1.00 in every row):

| gauge at the hit | sword stage 0: mean, max | sword stage 8 | axe stage 0 | axe stage 8 | spear stage 0 | spear stage 8 |
|---|---|---|---|---|---|---|
| 0 | 151.4, 296 | 493.3, 946 | 158.3, 298 | 507.7, 956 | 152.5, 298 | 498.7, 956 |
| 1 | 44.3, 73 | 153.1, 235 | 44.6, 73 | 154.3, 237 | 44.6, 73 | 154.3, 237 |
| 15 | 34.6, 61 | 133.1, 198 | 34.8, 61 | 134.2, 200 | 34.8, 61 | 134.2, 200 |
| 30 | 28.8, 49 | 100.8, 158 | 29.0, 49 | 101.5, 160 | 29.0, 49 | 101.5, 160 |
| 45 | 21.6, 37 | 75.5, 119 | 21.8, 37 | 76.0, 120 | 21.8, 37 | 76.0, 120 |
| 60 | 14.3, 24 | 50.6, 79 | 14.3, 24 | 51.0, 80 | 14.3, 24 | 51.0, 80 |
| 75 | 6.7, 12 | 26.0, 39 | 6.8, 12 | 26.3, 40 | 6.8, 12 | 26.3, 40 |
| 90 | 0.0, 0 | 0.0, 0 | 0.0, 0 | 0.0, 0 | 0.0, 0 | 0.0, 0 |

### 2.5 Boxes and hit test [V, C]
As for the glove (`docs/glove-attacks.md` 2.5): weapon box `E0C0-E0C3`, body box `E0C8-E0CB`, third box `E0CC-E0CF` (purpose not determined; it was non-empty, 8 x 16, during the whole sword id 0 swing), assigned from the sprite frame when the interpreter fetches a frame; two boxes overlap when `|cx1 - cx2| < (w1 + w2)/2` and `|cy1 - cy2| < (h1 + h2)/2`. A box assigned in frame k is first tested in frame k+1; the monster's tick applies the damage 1 frame later for slot 3 (hit flag = first non-empty box frame + 1, damage = + 2 whenever the target is inside the first box; section 5.1) [V]. The pair cannot hit again until `E05A` is cleared at the end of the attack.

### 2.6 The body box: when the hero cannot be hit [V]
A large monster weapon box was placed on the hero for a single frame f (monster weapon test `$C1:D1F8-D21D` skips the test when the body box is empty); the hero's hit flag fired in frame f exactly when the body box of frame f-1 was non-empty:

| attack | frames with a non-empty body box | frames in which the hero could be hit |
|---|---|---|
| sword normal var0 | 0, 16 | 1 |
| sword normal var1 | 0-10, 21-26 | 1-11, 22-26 |
| sword normal var2 | 0, 16 | 1 |
| sword power stage8 cls2 | 0, 81 | 1 |
| axe normal var0 | 0, 21 | 1 |
| axe normal var1 | 0-5, 21 | 1-6 |
| axe normal var2 | 0, 21 | 1 |
| axe power stage8 cls2 | 0, 61-70, 86 | 1, 62-71 |
| spear normal var0 | 0, 16 | 1 |
| spear normal var1 | 0, 16 | 1 |
| spear normal var2 | 0, 26 | 1 |
| spear power stage8 cls2 | 0, 141 | 1 |

So the hero can be hit in frame 1 (the frame after the press) and in the frames after a non-empty body box: sword id 1 frames 1-11 and 22-26, axe id 1 frames 1-6, the axe stage 8 class 2 attack frames 62-71; every other row above is safe from frame 2 to its end. "normal var N" rows use the id N of section 1.2 (ids 0, 1, 2).

### 2.7 Differences between heroes and between rows [V]
- Scripts, speeds, box sizes: identical for the three heroes. Hero 1 and 2 have the weapon box assigned one frame later than hero 0 in all 112 runs per weapon (4 ids x 4 facings + 24 charged attacks x 4 facings; for example sword id 0: frames 1-15 for hero 0, 2-16 for hero 1 and 2; box counts equal). Total frames, steps, movement and sounds are equal. The measured end positions differ in some runs only because of map walls (`end_pos_measured` in the JSON).
- Per hero (this save state, row 9 / 18 / 27): hero 0 Agi 79, atk 77 / 78 / 78, accuracy 94; hero 1 Agi 63, atk 63 / 64 / 64, accuracy 90; hero 2 Agi 57, atk 41 / 42 / 42, accuracy 89 (`atk = (Str + row power) & 255`, accuracy `min(99, Agi/4 + 75)`); crit base `E196` = 3 x the weapon level stored in the save state at equip time + the row crit byte (`docs/rom-combat.md` 4.3; hero 0 shows 15 for the sword and the spear and 24 for the axe in this state, and 25 for the sword row 14 whose crit byte is 10).
- **The nine rows of each type play the same animations**: the full summaries (all frames of the segments, boxes, sounds) of normal ids 0-3 and of the charged attacks 4, 6, 12, 14, 32, 34 were identical for rows 1-8 of the type compared with row 0 for the axe and the spear and for rows 1-7 for the sword. Sword row 17 (the last, `E1E8` = 17) differs only in `gauge_after`: 58 instead of 60, because its stat byte gives Agi +5 (`data/weapons.json`).
- Statuses: sword and axe rows carry none. Spear rows 29, 31, 32 carry the status words 0x0100, 0x0080, 0x0010 at 80 %; 100 uncharged hits on a dummy with random RNG states put the status on the target in 75 cases for each of the three rows (same RNG draws for each row) and `E199/E1F7` stayed constant during the swing [V].

## 3. Charging [V]
Identical to the glove (`docs/glove-attacks.md` section 3, `docs/rom-combat.md` 11.3). While B is held, `$C0:B330` runs every frame and does nothing while `E1ED`, `E01C`, `E061` or the pygmy bit are non-zero; `E01A` counts 1 per 2 frames to 44, then the stage `E19B` is incremented: 45 counts = 90 frames per stage; the stage is capped by the weapon level (after 1000 frames of holding: stage 1, 2, 5, 8 for levels 1, 2, 5, 8, all weapons). Frames from the press (swing = id 3 or 2, press at `$56` = 2) to each stage when B is held from the press; stage k = swing end + gauge frames + 90 k - 3:

| weapon, hero | Agi | swing ends | gauge empty | stage 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sword, hero 0 | 79 | 16 | 91 | 178 (2.962 s) | 268 (4.459 s) | 358 (5.957 s) | 448 (7.454 s) | 538 (8.952 s) | 628 (10.449 s) | 718 (11.947 s) | 808 (13.445 s) |
| sword, hero 1 | 63 | 16 | 99 | 186 (3.095 s) | 276 (4.592 s) | 366 (6.090 s) | 456 (7.588 s) | 546 (9.085 s) | 636 (10.583 s) | 726 (12.080 s) | 816 (13.578 s) |
| sword, hero 2 | 57 | 16 | 102 | 189 (3.145 s) | 279 (4.642 s) | 369 (6.140 s) | 459 (7.637 s) | 549 (9.135 s) | 639 (10.632 s) | 729 (12.130 s) | 819 (13.628 s) |
| axe, hero 0 | 79 | 21 | 96 | 183 (3.045 s) | 273 (4.543 s) | 363 (6.040 s) | 453 (7.538 s) | 543 (9.035 s) | 633 (10.533 s) | 723 (12.030 s) | 813 (13.528 s) |
| axe, hero 1 | 63 | 21 | 104 | 191 (3.178 s) | 281 (4.676 s) | 371 (6.173 s) | 461 (7.671 s) | 551 (9.168 s) | 641 (10.666 s) | 731 (12.163 s) | 821 (13.661 s) |
| axe, hero 2 | 57 | 21 | 107 | 194 (3.228 s) | 284 (4.726 s) | 374 (6.223 s) | 464 (7.721 s) | 554 (9.218 s) | 644 (10.716 s) | 734 (12.213 s) | 824 (13.711 s) |
| spear, hero 0 | 79 | 26 | 101 | 188 (3.128 s) | 278 (4.626 s) | 368 (6.123 s) | 458 (7.621 s) | 548 (9.118 s) | 638 (10.616 s) | 728 (12.113 s) | 818 (13.611 s) |
| spear, hero 1 | 63 | 26 | 109 | 196 (3.261 s) | 286 (4.759 s) | 376 (6.256 s) | 466 (7.754 s) | 556 (9.251 s) | 646 (10.749 s) | 736 (12.247 s) | 826 (13.744 s) |
| spear, hero 2 | 57 | 26 | 112 | 199 (3.311 s) | 289 (4.809 s) | 379 (6.306 s) | 469 (7.804 s) | 559 (9.301 s) | 649 (10.799 s) | 739 (12.296 s) | 829 (13.794 s) |

Parity 0 and 1 gave equal stage frames. Releasing B the frame after stage 1 was reached started the stage-1 attack in that frame (`E01C = 0x80`, `E011 = 6` for the far class: 4 s + 2); releasing before stage 1 started nothing (`E01C` stayed 0) [V]. Sounds while holding (hero 0, level 8, 900 frames): sound 0x26 when the gauge empties, then 0x27 every 8 frames while the charge runs, and 0x28 at some of the stage changes (frames since the press: sword 268, 448, 628, 808; axe 184, 364, 544, 724, 816; spear 188, 368, 548, 728, 820; the rule that picks them is not determined) (`$C0:B3CB`, `$C0:BB11` [C+V]). The first sound of the sequence at frame 1 is the strike sound of the swing.

## 4. Charged attacks

### 4.1 Which attack [V]
`E011 = 4 * stage + class` with the class 0 (near), 1 (mid), 2 (far or none) of section 2.2; the parity of `$F4` has no effect for stages >= 1. Tested for weapon levels 1, 4, 8 and every stage up to the level (sword, axe, spear identical): the attack depends only on the stage reached and the class, not on the weapon level. **"The weapon level L attack" is the stage-L attack**, reachable with a level >= L weapon. A target with a status (`E190` bits 0x02 / 0x10) selects the ids 4k+3 (7 for stages 0 and 1), which share the script of 4k for these weapons [C, scripts compared]. The 24 attacks per weapon are the ids 4..6, 8..10, ..., 32..34.

### 4.2 Structure: attacks are chains of pieces [C, V]
As for the glove: each charged attack script is a list of calls (`$F1`) to shorter scripts. The static walk (`tools/weapon_attacks.py structure`) gives, for the side facings (up and down have their own scripts; their total step counts are equal to the side facing's in all 36 animations of every weapon). "own(n)" is a run of n steps written directly in the script; N0-N2 are the normal swings of section 1.2 (N2 = id 2 = id 3); P-numbers are pieces numbered in order of first appearance.

**sword**

| animation | stage, class | total steps | items in order (steps) |
|---|---|---|---|
| 4 | 1, 0 | 6 | own(6) |
| 5 | 1, 1 | 7 | P2(1) P0(6) |
| 6 | 1, 2 | 8 | P4(2) P0(6) |
| 7 | 1, status target | 6 | own(6) |
| 8 | 2, 0 | 9 | P6(6) N0(3) |
| 9 | 2, 1 | 10 | P2(1) P6(6) N0(3) |
| 10 | 2, 2 | 11 | P4(2) P6(6) N0(3) |
| 11 | 2, status target | 9 | P6(6) N0(3) |
| 12 | 3, 0 | 12 | N0(3) N2(3) P0(6) |
| 13 | 3, 1 | 13 | P2(1) N0(3) N2(3) P0(6) |
| 14 | 3, 2 | 14 | P4(2) N0(3) N2(3) P0(6) |
| 15 | 3, status target | 12 | N0(3) N2(3) P0(6) |
| 16 | 4, 0 | 20 | P13(10) P13(10) |
| 17 | 4, 1 | 21 | P2(1) P13(10) P13(10) |
| 18 | 4, 2 | 22 | P4(2) P13(10) P13(10) |
| 19 | 4, status target | 20 | P13(10) P13(10) |
| 20 | 5, 0 | 16 | own(4) P17(4) P17(4) P17(4) |
| 21 | 5, 1 | 17 | P2(1) P16(16) |
| 22 | 5, 2 | 18 | P4(2) P16(16) |
| 23 | 5, status target | 16 | own(4) P17(4) P17(4) P17(4) |
| 24 | 6, 0 | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 25 | 6, 1 | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 26 | 6, 2 | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 27 | 6, status target | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 28 | 7, 0 | 18 | own(3) P17(4) N0(3) N2(3) N1(5) |
| 29 | 7, 1 | 18 | own(3) P17(4) N0(3) N2(3) N1(5) |
| 30 | 7, 2 | 18 | own(3) P17(4) N0(3) N2(3) N1(5) |
| 31 | 7, status target | 18 | own(3) P17(4) N0(3) N2(3) N1(5) |
| 32 | 8, 0 | 16 | P25(4) P17(4) P17(4) P17(4) |
| 33 | 8, 1 | 16 | P25(4) P17(4) P17(4) P17(4) |
| 34 | 8, 2 | 16 | P25(4) P17(4) P17(4) P17(4) |
| 35 | 8, status target | 16 | P25(4) P17(4) P17(4) P17(4) |

Pieces (velocity preset k is a row of the 4-byte table at `$C2:AF05`: vx, vy, vz in px/frame, 128 = unchanged, otherwise sign-magnitude for x and y and two's complement for z; 25 / 27 stop x / z, 0 stops all):

| piece | script address (bank $D1) | steps | sound ids | velocity presets k (vx, vy, vz of the table row; 128 = unchanged) | calls |
|---|---|---|---|---|---|
| N0 | `$D1:6A4E` | 3 | 0x4 | - | - |
| N1 | `$D1:6A72` | 5 | 0x2 | - | - |
| N2 | `$D1:6A96` | 3 | 0x3 | - | - |
| P0 | `$D1:6ABA` | 6 | 0x18 0x3 | 17: 128,128,1; 27: 128,128,0; 21: 128,128,255; 22: 128,128,254; 0: 0,0,0 | - |
| P1 | `$D1:6B23` | 7 | - | - | P2 P0 |
| P2 | `$D1:6B0B` | 1 | 0xB | 2: 2,128,128; 25: 0,128,128 | - |
| P3 | `$D1:6B56` | 8 | - | - | P4 P0 |
| P4 | `$D1:6B38` | 2 | 0xB | 3: 3,128,128; 25: 0,128,128 | - |
| P5 | `$D1:6BAA` | 9 | - | - | P6 N0 |
| P6 | `$D1:6B6B` | 6 | 0x4 0x4 | - | - |
| P7 | `$D1:6BBF` | 10 | - | - | P2 P6 N0 |
| P8 | `$D1:6BDD` | 11 | - | - | P4 P6 N0 |
| P9 | `$D1:6BFB` | 12 | - | - | N0 N2 P0 |
| P10 | `$D1:6C19` | 13 | - | - | P2 N0 N2 P0 |
| P11 | `$D1:6C40` | 14 | - | - | P4 N0 N2 P0 |
| P12 | `$D1:6CC7` | 20 | - | - | P13 P13 |
| P13 | `$D1:6C67` | 10 | 0x4 0x3 0x4 | - | - |
| P14 | `$D1:6CDC` | 21 | - | - | P2 P13 P13 |
| P15 | `$D1:6CFA` | 22 | - | - | P4 P13 P13 |
| P16 | `$D1:6D18` | 16 | - | - | P17 P17 P17 |
| P17 | `$D1:6D28` | 4 | 0x4 | - | - |
| P18 | `$D1:6D72` | 17 | - | - | P2 P16 |
| P19 | `$D1:6D87` | 18 | - | - | P4 P16 |
| P20 | `$D1:6D9C` | 30 | - | 0: 0,0,0 | P21 P22 P21 P22 P21 P22 P21 P22 P21 P22 P21 P22 P21 P22 P21 |
| P21 | `$D1:6DF8` | 2 | 0x4 | - | - |
| P22 | `$D1:6E02` | 2 | - | - | - |
| P23 | `$D1:6E09` | 18 | - | 4: 4,128,128; 25: 0,128,128 | P17 N0 N2 N1 |
| P24 | `$D1:6E42` | 16 | - | 4: 4,128,128; 25: 0,128,128 | P25 P17 P17 P17 |
| P25 | `$D1:6E51` | 4 | 0x18 0x18 | - | - |

**axe**

| animation | stage, class | total steps | items in order (steps) |
|---|---|---|---|
| 4 | 1, 0 | 10 | own(10) |
| 5 | 1, 1 | 11 | P2(1) P0(10) |
| 6 | 1, 2 | 12 | P4(2) P0(10) |
| 7 | 1, status target | 10 | own(10) |
| 8 | 2, 0 | 8 | N0(4) N2(4) |
| 9 | 2, 1 | 9 | P2(1) N0(4) N2(4) |
| 10 | 2, 2 | 10 | P4(2) N0(4) N2(4) |
| 11 | 2, status target | 8 | N0(4) N2(4) |
| 12 | 3, 0 | 14 | N0(4) N2(4) P9(6) |
| 13 | 3, 1 | 15 | P2(1) N0(4) N2(4) P9(6) |
| 14 | 3, 2 | 16 | P4(2) N0(4) N2(4) P9(6) |
| 15 | 3, status target | 14 | N0(4) N2(4) P9(6) |
| 16 | 4, 0 | 13 | N0(4) P13(4) own(1) N1(4) |
| 17 | 4, 1 | 14 | P2(1) P12(13) |
| 18 | 4, 2 | 15 | P4(2) P12(13) |
| 19 | 4, status target | 13 | N0(4) P13(4) own(1) N1(4) |
| 20 | 5, 0 | 12 | P17(4) P17(4) P17(4) |
| 21 | 5, 1 | 13 | P2(1) P16(12) |
| 22 | 5, 2 | 14 | P4(2) P16(12) |
| 23 | 5, status target | 12 | P17(4) P17(4) P17(4) |
| 24 | 6, 0 | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 25 | 6, 1 | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 26 | 6, 2 | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 27 | 6, status target | 30 | P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) P22(2) P21(2) |
| 28 | 7, 0 | 22 | own(2) P13(4) own(2) N0(4) N2(4) P9(6) |
| 29 | 7, 1 | 22 | own(2) P13(4) own(2) N0(4) N2(4) P9(6) |
| 30 | 7, 2 | 22 | own(2) P13(4) own(2) N0(4) N2(4) P9(6) |
| 31 | 7, status target | 22 | own(2) P13(4) own(2) N0(4) N2(4) P9(6) |
| 32 | 8, 0 | 17 | P21(2) P22(2) P12(13) |
| 33 | 8, 1 | 17 | P21(2) P22(2) P12(13) |
| 34 | 8, 2 | 17 | P21(2) P22(2) P12(13) |
| 35 | 8, status target | 17 | P21(2) P22(2) P12(13) |

Pieces (velocity preset k is a row of the 4-byte table at `$C2:AF05`: vx, vy, vz in px/frame, 128 = unchanged, otherwise sign-magnitude for x and y and two's complement for z; 25 / 27 stop x / z, 0 stops all):

| piece | script address (bank $D1) | steps | sound ids | velocity presets k (vx, vy, vz of the table row; 128 = unchanged) | calls |
|---|---|---|---|---|---|
| N0 | `$D1:6E9C` | 4 | 0x8 | - | - |
| N1 | `$D1:6EC6` | 4 | 0x8 | - | - |
| N2 | `$D1:6EDE` | 4 | 0x8 | - | - |
| P0 | `$D1:6F08` | 10 | 0x8 | - | - |
| P1 | `$D1:6F6E` | 11 | - | - | P2 P0 |
| P2 | `$D1:6F56` | 1 | 0xB | 2: 2,128,128; 25: 0,128,128 | - |
| P3 | `$D1:6FA1` | 12 | - | - | P4 P0 |
| P4 | `$D1:6F83` | 2 | 0xB | 3: 3,128,128; 25: 0,128,128 | - |
| P5 | `$D1:6FB6` | 8 | - | - | N0 N2 |
| P6 | `$D1:6FCB` | 9 | - | - | P2 N0 N2 |
| P7 | `$D1:6FE9` | 10 | - | - | P4 N0 N2 |
| P8 | `$D1:7058` | 14 | - | - | N0 N2 P9 |
| P9 | `$D1:7007` | 6 | 0x18 0x8 | 17: 128,128,1; 27: 128,128,0; 21: 128,128,255; 22: 128,128,254; 0: 0,0,0 | - |
| P10 | `$D1:7076` | 15 | - | - | P2 N0 N2 P9 |
| P11 | `$D1:709D` | 16 | - | - | P4 N0 N2 P9 |
| P12 | `$D1:70C4` | 13 | - | 0: 0,0,0; 24: 128,128,252; 0: 0,0,0; 3: 3,128,128; 0: 0,0,0 | N0 P13 N1 |
| P13 | `$D1:7215` | 4 | 0x8 0x8 | - | - |
| P14 | `$D1:7100` | 14 | - | - | P2 P12 |
| P15 | `$D1:7115` | 15 | - | - | P4 P12 |
| P16 | `$D1:712A` | 12 | - | - | P17 P17 P17 |
| P17 | `$D1:7134` | 4 | 0x8 0x8 | - | - |
| P18 | `$D1:717B` | 13 | - | - | P2 P16 |
| P19 | `$D1:7190` | 14 | - | - | P4 P16 |
| P20 | `$D1:71A5` | 30 | - | 0: 0,0,0 | P21 P22 P21 P22 P21 P22 P21 P22 P21 P22 P21 P22 P21 P22 P21 |
| P21 | `$D1:7201` | 2 | 0x8 | - | - |
| P22 | `$D1:720B` | 2 | 0x8 | - | - |
| P23 | `$D1:7248` | 22 | - | 18: 128,128,2; 0: 0,0,0; 4: 4,128,128; 25: 0,128,128; 22: 128,128,254; 0: 0,0,0 | P13 N0 N2 P9 |
| P24 | `$D1:728D` | 17 | - | 4: 4,128,128; 25: 0,128,128 | P21 P22 P12 |

**spear**

| animation | stage, class | total steps | items in order (steps) |
|---|---|---|---|
| 4 | 1, 0 | 11 | P1(6) N2(5) |
| 5 | 1, 1 | 12 | P3(1) P1(6) N2(5) |
| 6 | 1, 2 | 13 | P5(2) P1(6) N2(5) |
| 7 | 1, status target | 11 | P1(6) N2(5) |
| 8 | 2, 0 | 14 | P7(4) N2(5) N2(5) |
| 9 | 2, 1 | 15 | P7(4) P3(1) N2(5) N2(5) |
| 10 | 2, 2 | 16 | P7(4) P5(2) N2(5) N2(5) |
| 11 | 2, status target | 14 | P7(4) N2(5) N2(5) |
| 12 | 3, 0 | 22 | P1(6) N2(5) N2(5) P11(6) |
| 13 | 3, 1 | 23 | P1(6) P3(1) N2(5) N2(5) P11(6) |
| 14 | 3, 2 | 24 | P1(6) P5(2) N2(5) N2(5) P11(6) |
| 15 | 3, status target | 22 | P1(6) N2(5) N2(5) P11(6) |
| 16 | 4, 0 | 20 | P7(4) N0(3) N1(3) P15(4) P16(6) |
| 17 | 4, 1 | 21 | P7(4) P3(1) N0(3) N1(3) P15(4) P16(6) |
| 18 | 4, 2 | 22 | P7(4) P5(2) N0(3) N1(3) P15(4) P16(6) |
| 19 | 4, status target | 20 | P7(4) N0(3) N1(3) P15(4) P16(6) |
| 20 | 5, 0 | 15 | own(3) P20(4) P20(4) P20(4) |
| 21 | 5, 1 | 16 | P3(1) P19(15) |
| 22 | 5, 2 | 17 | P5(2) P19(15) |
| 23 | 5, status target | 15 | own(3) P20(4) P20(4) P20(4) |
| 24 | 6, 0 | 30 | P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) |
| 25 | 6, 1 | 30 | P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) |
| 26 | 6, 2 | 30 | P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) |
| 27 | 6, status target | 30 | P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) P25(2) P24(2) |
| 28 | 7, 0 | 20 | P7(4) P27(4) P20(4) P20(4) P20(4) |
| 29 | 7, 1 | 20 | P7(4) P27(4) P20(4) P20(4) P20(4) |
| 30 | 7, 2 | 20 | P7(4) P27(4) P20(4) P20(4) P20(4) |
| 31 | 7, status target | 20 | P7(4) P27(4) P20(4) P20(4) P20(4) |
| 32 | 8, 0 | 28 | own(3) P20(4) N2(5) P29(8) P29(8) |
| 33 | 8, 1 | 28 | own(3) P20(4) N2(5) P29(8) P29(8) |
| 34 | 8, 2 | 28 | own(3) P20(4) N2(5) P29(8) P29(8) |
| 35 | 8, status target | 28 | own(3) P20(4) N2(5) P29(8) P29(8) |

Pieces (velocity preset k is a row of the 4-byte table at `$C2:AF05`: vx, vy, vz in px/frame, 128 = unchanged, otherwise sign-magnitude for x and y and two's complement for z; 25 / 27 stop x / z, 0 stops all):

| piece | script address (bank $D1) | steps | sound ids | velocity presets k (vx, vy, vz of the table row; 128 = unchanged) | calls |
|---|---|---|---|---|---|
| N0 | `$D1:72B1` | 3 | 0x1B | - | - |
| N1 | `$D1:72D5` | 3 | 0x1B | - | - |
| N2 | `$D1:72F9` | 5 | 0xB | - | - |
| P0 | `$D1:7350` | 11 | - | - | P1 N2 |
| P1 | `$D1:7317` | 6 | 0xB 0xB | - | - |
| P2 | `$D1:737D` | 12 | - | - | P3 P1 N2 |
| P3 | `$D1:7365` | 1 | 0xB | 2: 2,128,128; 25: 0,128,128 | - |
| P4 | `$D1:73B9` | 13 | - | - | P5 P1 N2 |
| P5 | `$D1:739B` | 2 | 0xB | 3: 3,128,128; 25: 0,128,128 | - |
| P6 | `$D1:7410` | 14 | - | - | P7 N2 N2 |
| P7 | `$D1:73D7` | 4 | 0x19 0x1B | - | - |
| P8 | `$D1:742E` | 15 | - | - | P7 P3 N2 N2 |
| P9 | `$D1:7455` | 16 | - | - | P7 P5 N2 N2 |
| P10 | `$D1:74C7` | 22 | - | - | P1 N2 N2 P11 |
| P11 | `$D1:747C` | 6 | 0x18 0xB | 17: 128,128,1; 27: 128,128,0; 21: 128,128,255; 22: 128,128,254; 0: 0,0,0 | - |
| P12 | `$D1:74EE` | 23 | - | - | P1 P3 N2 N2 P11 |
| P13 | `$D1:751E` | 24 | - | - | P1 P5 N2 N2 P11 |
| P14 | `$D1:7596` | 20 | - | - | P7 N0 N1 P15 P16 |
| P15 | `$D1:754E` | 4 | 0xB | - | - |
| P16 | `$D1:756C` | 6 | 0xB | - | - |
| P17 | `$D1:75C6` | 21 | - | - | P7 P3 N0 N1 P15 P16 |
| P18 | `$D1:75FF` | 22 | - | - | P7 P5 N0 N1 P15 P16 |
| P19 | `$D1:7638` | 15 | - | - | P20 P20 P20 |
| P20 | `$D1:7646` | 4 | 0x19 0x19 | - | - |
| P21 | `$D1:7695` | 16 | - | - | P3 P19 |
| P22 | `$D1:76AA` | 17 | - | - | P5 P19 |
| P23 | `$D1:76BF` | 30 | - | 0: 0,0,0 | P24 P25 P24 P25 P24 P25 P24 P25 P24 P25 P24 P25 P24 P25 P24 |
| P24 | `$D1:771B` | 2 | 0x1B | - | - |
| P25 | `$D1:7725` | 2 | 0x1B | - | - |
| P26 | `$D1:772F` | 20 | - | 4: 4,128,128; 25: 0,128,128 | P7 P27 P20 P20 P20 |
| P27 | `$D1:7741` | 4 | 0x1C 0x1C | - | - |
| P28 | `$D1:7792` | 28 | - | 4: 4,128,128; 25: 0,128,128 | P20 N2 P29 P29 |
| P29 | `$D1:77CB` | 8 | 0xB 0x2 0x2 0x2 0x2 0x2 0x2 0x2 | - | - |

Scripts shared between animation ids (side facing; groups of ids with the same script address):

- sword: 2 = 3; 4 = 7; 8 = 11; 12 = 15; 16 = 19; 20 = 23 = 36; 24 = 25 = 26 = 27 = 37; 28 = 29 = 30 = 31 = 38; 32 = 33 = 34 = 35 = 39
- axe: 2 = 3; 4 = 7; 8 = 11; 12 = 15; 16 = 19; 20 = 23 = 36; 24 = 25 = 26 = 27 = 37; 28 = 29 = 30 = 31 = 38; 32 = 33 = 34 = 35 = 39
- spear: 2 = 3; 4 = 7; 8 = 11; 12 = 15; 16 = 19; 20 = 23 = 36; 24 = 25 = 26 = 27 = 37; 28 = 29 = 30 = 31 = 38; 32 = 33 = 34 = 35 = 39

The ids 36-39 are never selected for these types (the kind map sends kinds 36-39 to 0, 4, 8, 12); the ids 7, 11 ... 35 (status-target variants) run the script of 4k.

### 4.3 Overview (hero 0, facing left; heroes 1 and 2 identical except the weapon box starts one frame later) [V]
Frames are from the release frame (frame 0); the first step is at frame 1 (frame 0 when released at `$56` = 3). `move px` is the sum of the velocities (open ground); `box union` is the union of the weapon boxes in world offsets from the hero position at frame 0 including the hero's movement (min x, max x, min y, max y; forward is negative x; negative y is up); `max height` is the maximum sprite height `E045` (jump). Sound ids are hexadecimal, each at the frame it is requested.

**sword**

| stage | class | frames (s) | steps | move px (x, y) | max height | weapon box frames | first..last | box union x lo..hi, y lo..hi | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 31 (0.516) | 6 | (-30, 0) | 10 | 20 | 11..30 | [-61.0, -10.0, -52.0, 13.0] | 18@6 3@11 |
| 1 | 1 | 36 (0.599) | 7 | (-40, 0) | 10 | 20 | 16..35 | [-71.0, -20.0, -52.0, 13.0] | B@1 18@11 3@16 |
| 1 | 2 | 41 (0.682) | 8 | (-60, 0) | 10 | 20 | 21..40 | [-91.0, -40.0, -52.0, 13.0] | B@1 18@16 3@21 |
| 2 | 0 | 46 (0.765) | 9 | (0, 0) | 0 | 15 | 31..45 | [-36.0, 0.0, -42.0, 18.0] | 4@1 4@16 4@31 |
| 2 | 1 | 51 (0.849) | 10 | (-10, 0) | 0 | 15 | 36..50 | [-46.0, -10.0, -42.0, 18.0] | B@1 4@6 4@21 4@36 |
| 2 | 2 | 56 (0.932) | 11 | (-30, 0) | 0 | 15 | 41..55 | [-66.0, -30.0, -42.0, 18.0] | B@1 4@11 4@26 4@41 |
| 3 | 0 | 61 (1.015) | 12 | (-30, 0) | 10 | 50 | 1..60 | [-61.0, 18.0, -52.0, 18.0] | 4@1 3@16 18@36 3@41 |
| 3 | 1 | 66 (1.098) | 13 | (-40, 0) | 10 | 50 | 6..65 | [-71.0, 8.0, -52.0, 18.0] | B@1 4@6 3@21 18@41 3@46 |
| 3 | 2 | 71 (1.181) | 14 | (-60, 0) | 10 | 50 | 11..70 | [-91.0, -12.0, -52.0, 18.0] | B@1 4@11 3@26 18@46 3@51 |
| 4 | 0 | 101 (1.681) | 20 | (0, 0) | 0 | 100 | 1..100 | [-36.0, 36.0, -42.0, 18.0] | 4@1 3@21 4@36 4@51 3@71 4@86 |
| 4 | 1 | 106 (1.764) | 21 | (-10, 0) | 0 | 100 | 6..105 | [-46.0, 26.0, -42.0, 18.0] | B@1 4@6 3@26 4@41 4@56 3@76 4@91 |
| 4 | 2 | 111 (1.847) | 22 | (-30, 0) | 0 | 100 | 11..110 | [-66.0, 6.0, -42.0, 18.0] | B@1 4@11 3@31 4@46 4@61 3@81 4@96 |
| 5 | 0 | 81 (1.348) | 16 | (0, 0) | 0 | 60 | 21..80 | [-28.0, 28.0, -43.0, 13.0] | 4@21 4@41 4@61 |
| 5 | 1 | 86 (1.431) | 17 | (-10, 0) | 0 | 60 | 26..85 | [-38.0, 18.0, -43.0, 13.0] | B@1 4@26 4@46 4@66 |
| 5 | 2 | 91 (1.514) | 18 | (-30, 0) | 0 | 60 | 31..90 | [-58.0, -2.0, -43.0, 13.0] | B@1 4@31 4@51 4@71 |
| 6 | 0 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 4@1 4@21 4@41 4@61 4@81 4@101 4@121 4@141 |
| 6 | 1 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 4@1 4@21 4@41 4@61 4@81 4@101 4@121 4@141 |
| 6 | 2 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 4@1 4@21 4@41 4@61 4@81 4@101 4@121 4@141 |
| 7 | 0 | 91 (1.514) | 18 | (-80, 0) | 0 | 60 | 16..85 | [-118.0, 28.0, -43.0, 18.0] | 4@16 4@36 3@51 2@66 |
| 7 | 1 | 91 (1.514) | 18 | (-80, 0) | 0 | 60 | 16..85 | [-118.0, 28.0, -43.0, 18.0] | 4@16 4@36 3@51 2@66 |
| 7 | 2 | 91 (1.514) | 18 | (-80, 0) | 0 | 60 | 16..85 | [-118.0, 28.0, -43.0, 18.0] | 4@16 4@36 3@51 2@66 |
| 8 | 0 | 81 (1.348) | 16 | (-80, 0) | 0 | 80 | 1..80 | [-108.0, 0.0, -43.0, 13.0] | 18@1 18@11 4@21 4@41 4@61 |
| 8 | 1 | 81 (1.348) | 16 | (-80, 0) | 0 | 80 | 1..80 | [-108.0, 0.0, -43.0, 13.0] | 18@1 18@11 4@21 4@41 4@61 |
| 8 | 2 | 81 (1.348) | 16 | (-80, 0) | 0 | 80 | 1..80 | [-108.0, 0.0, -43.0, 13.0] | 18@1 18@11 4@21 4@41 4@61 |

**axe**

| stage | class | frames (s) | steps | move px (x, y) | max height | weapon box frames | first..last | box union x lo..hi, y lo..hi | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 51 (0.849) | 10 | (0, 0) | 0 | 15 | 36..50 | [-30.0, 18.0, -29.0, 9.0] | 8@36 |
| 1 | 1 | 56 (0.932) | 11 | (-10, 0) | 0 | 15 | 41..55 | [-40.0, 8.0, -29.0, 9.0] | B@1 8@41 |
| 1 | 2 | 61 (1.015) | 12 | (-30, 0) | 0 | 15 | 46..60 | [-60.0, -12.0, -29.0, 9.0] | B@1 8@46 |
| 2 | 0 | 41 (0.682) | 8 | (0, 0) | 0 | 40 | 1..40 | [-32.0, 18.0, -40.0, 13.0] | 8@1 8@21 |
| 2 | 1 | 46 (0.765) | 9 | (-10, 0) | 0 | 40 | 6..45 | [-42.0, 8.0, -40.0, 13.0] | B@1 8@6 8@26 |
| 2 | 2 | 51 (0.849) | 10 | (-30, 0) | 0 | 40 | 11..50 | [-62.0, -12.0, -40.0, 13.0] | B@1 8@11 8@31 |
| 3 | 0 | 71 (1.181) | 14 | (-30, 0) | 10 | 60 | 1..70 | [-61.0, 18.0, -50.0, 13.0] | 8@1 8@21 18@46 8@51 |
| 3 | 1 | 76 (1.265) | 15 | (-40, 0) | 10 | 60 | 6..75 | [-71.0, 8.0, -50.0, 13.0] | B@1 8@6 8@26 18@51 8@56 |
| 3 | 2 | 81 (1.348) | 16 | (-60, 0) | 10 | 60 | 11..80 | [-91.0, -12.0, -50.0, 13.0] | B@1 8@11 8@31 18@56 8@61 |
| 4 | 0 | 66 (1.098) | 13 | (-40, 0) | 20 | 55 | 1..65 | [-69.0, 35.0, -42.0, 13.0] | 8@1 8@21 8@31 8@46 |
| 4 | 1 | 71 (1.181) | 14 | (-50, 0) | 20 | 55 | 6..70 | [-79.0, 25.0, -42.0, 13.0] | B@1 8@6 8@26 8@36 8@51 |
| 4 | 2 | 76 (1.265) | 15 | (-70, 0) | 20 | 55 | 11..75 | [-99.0, 5.0, -42.0, 13.0] | B@1 8@11 8@31 8@41 8@56 |
| 5 | 0 | 61 (1.015) | 12 | (0, 0) | 0 | 60 | 1..60 | [-28.0, 28.0, -43.0, 13.0] | 8@1 8@11 8@21 8@31 8@41 8@51 |
| 5 | 1 | 66 (1.098) | 13 | (-10, 0) | 0 | 60 | 6..65 | [-38.0, 18.0, -43.0, 13.0] | B@1 8@6 8@16 8@26 8@36 8@46 8@56 |
| 5 | 2 | 71 (1.181) | 14 | (-30, 0) | 0 | 60 | 11..70 | [-58.0, -2.0, -43.0, 13.0] | B@1 8@11 8@21 8@31 8@41 8@51 8@61 |
| 6 | 0 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 8@1 8@11 8@21 8@31 8@41 8@51 8@61 8@71 8@81 8@91 8@101 8@111 8@121 8@131 8@141 |
| 6 | 1 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 8@1 8@11 8@21 8@31 8@41 8@51 8@61 8@71 8@81 8@91 8@101 8@111 8@121 8@131 8@141 |
| 6 | 2 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 8@1 8@11 8@21 8@31 8@41 8@51 8@61 8@71 8@81 8@91 8@101 8@111 8@121 8@131 8@141 |
| 7 | 0 | 111 (1.847) | 22 | (-110, 0) | 20 | 80 | 11..110 | [-141.0, 16.0, -50.0, 13.0] | 8@11 8@21 8@41 8@61 18@86 8@91 |
| 7 | 1 | 111 (1.847) | 22 | (-110, 0) | 20 | 80 | 11..110 | [-141.0, 16.0, -50.0, 13.0] | 8@11 8@21 8@41 8@61 18@86 8@91 |
| 7 | 2 | 111 (1.847) | 22 | (-110, 0) | 20 | 80 | 11..110 | [-141.0, 16.0, -50.0, 13.0] | 8@11 8@21 8@41 8@61 18@86 8@91 |
| 8 | 0 | 86 (1.431) | 17 | (-120, 0) | 20 | 75 | 1..85 | [-149.0, 28.0, -43.0, 13.0] | 8@1 8@11 8@21 8@41 8@51 8@66 |
| 8 | 1 | 86 (1.431) | 17 | (-120, 0) | 20 | 75 | 1..85 | [-149.0, 28.0, -43.0, 13.0] | 8@1 8@11 8@21 8@41 8@51 8@66 |
| 8 | 2 | 86 (1.431) | 17 | (-120, 0) | 20 | 75 | 1..85 | [-149.0, 28.0, -43.0, 13.0] | 8@1 8@11 8@21 8@41 8@51 8@66 |

**spear**

| stage | class | frames (s) | steps | move px (x, y) | max height | weapon box frames | first..last | box union x lo..hi, y lo..hi | sounds (id@frame) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 56 (0.932) | 11 | (0, 0) | 0 | 25 | 31..55 | [-42.0, 12.0, -17.0, 3.0] | B@11 B@21 B@31 |
| 1 | 1 | 61 (1.015) | 12 | (-10, 0) | 0 | 25 | 36..60 | [-52.0, 2.0, -17.0, 3.0] | B@1 B@16 B@26 B@36 |
| 1 | 2 | 66 (1.098) | 13 | (-30, 0) | 0 | 25 | 41..65 | [-72.0, -18.0, -17.0, 3.0] | B@1 B@21 B@31 B@41 |
| 2 | 0 | 71 (1.181) | 14 | (0, 0) | 0 | 50 | 21..70 | [-42.0, 12.0, -17.0, 3.0] | 19@1 1B@11 B@21 B@46 |
| 2 | 1 | 76 (1.265) | 15 | (-10, 0) | 0 | 50 | 26..75 | [-52.0, 2.0, -17.0, 3.0] | 19@1 1B@11 B@21 B@26 B@51 |
| 2 | 2 | 81 (1.348) | 16 | (-30, 0) | 0 | 50 | 31..80 | [-72.0, -18.0, -17.0, 3.0] | 19@1 1B@11 B@21 B@31 B@56 |
| 3 | 0 | 111 (1.847) | 22 | (-30, 0) | 10 | 80 | 31..110 | [-65.0, 12.0, -46.0, 3.0] | B@11 B@21 B@31 B@56 18@86 B@91 |
| 3 | 1 | 116 (1.930) | 23 | (-40, 0) | 10 | 80 | 36..115 | [-75.0, 2.0, -46.0, 3.0] | B@11 B@21 B@31 B@36 B@61 18@91 B@96 |
| 3 | 2 | 121 (2.013) | 24 | (-60, 0) | 10 | 80 | 41..120 | [-95.0, -18.0, -46.0, 3.0] | B@11 B@21 B@31 B@41 B@66 18@96 B@101 |
| 4 | 0 | 101 (1.681) | 20 | (0, 0) | 0 | 80 | 21..100 | [-48.0, 20.0, -40.0, 20.0] | 19@1 1B@11 1B@21 1B@36 B@56 B@76 |
| 4 | 1 | 106 (1.764) | 21 | (-10, 0) | 0 | 80 | 26..105 | [-58.0, 10.0, -40.0, 20.0] | 19@1 1B@11 B@21 1B@26 1B@41 B@61 B@81 |
| 4 | 2 | 111 (1.847) | 22 | (-30, 0) | 0 | 80 | 31..110 | [-78.0, -10.0, -40.0, 20.0] | 19@1 1B@11 B@21 1B@31 1B@46 B@66 B@86 |
| 5 | 0 | 76 (1.265) | 15 | (0, 0) | 0 | 75 | 1..75 | [-28.0, 28.0, -43.0, 13.0] | 19@16 19@26 19@36 19@46 19@56 19@66 |
| 5 | 1 | 81 (1.348) | 16 | (-10, 0) | 0 | 75 | 6..80 | [-38.0, 18.0, -43.0, 13.0] | B@1 19@21 19@31 19@41 19@51 19@61 19@71 |
| 5 | 2 | 86 (1.431) | 17 | (-30, 0) | 0 | 75 | 11..85 | [-58.0, -2.0, -43.0, 13.0] | B@1 19@26 19@36 19@46 19@56 19@66 19@76 |
| 6 | 0 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 1B@1 1B@11 1B@21 1B@31 1B@41 1B@51 1B@61 1B@71 1B@81 1B@91 1B@101 1B@111 1B@121 1B@131 1B@141 |
| 6 | 1 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 1B@1 1B@11 1B@21 1B@31 1B@41 1B@51 1B@61 1B@71 1B@81 1B@91 1B@101 1B@111 1B@121 1B@131 1B@141 |
| 6 | 2 | 151 (2.513) | 30 | (-10, 0) | 0 | 150 | 1..150 | [-68.0, 58.0, -73.0, 43.0] | 1B@1 1B@11 1B@21 1B@31 1B@41 1B@51 1B@61 1B@71 1B@81 1B@91 1B@101 1B@111 1B@121 1B@131 1B@141 |
| 7 | 0 | 101 (1.681) | 20 | (-80, 0) | 0 | 80 | 21..100 | [-108.0, 8.0, -43.0, 13.0] | 19@1 1B@11 1C@21 1C@31 19@41 19@51 19@61 19@71 19@81 19@91 |
| 7 | 1 | 101 (1.681) | 20 | (-80, 0) | 0 | 80 | 21..100 | [-108.0, 8.0, -43.0, 13.0] | 19@1 1B@11 1C@21 1C@31 19@41 19@51 19@61 19@71 19@81 19@91 |
| 7 | 2 | 101 (1.681) | 20 | (-80, 0) | 0 | 80 | 21..100 | [-108.0, 8.0, -43.0, 13.0] | 19@1 1B@11 1C@21 1C@31 19@41 19@51 19@61 19@71 19@81 19@91 |
| 8 | 0 | 141 (2.346) | 28 | (-80, 0) | 0 | 140 | 1..140 | [-128.0, 28.0, -43.0, 13.0] | 19@16 19@26 B@36 B@61 2@66 2@71 2@76 2@81 2@86 2@91 2@96 B@101 2@106 2@111 2@116 2@121 2@126 2@131 2@136 |
| 8 | 1 | 141 (2.346) | 28 | (-80, 0) | 0 | 140 | 1..140 | [-128.0, 28.0, -43.0, 13.0] | 19@16 19@26 B@36 B@61 2@66 2@71 2@76 2@81 2@86 2@91 2@96 B@101 2@106 2@111 2@116 2@121 2@126 2@131 2@136 |
| 8 | 2 | 141 (2.346) | 28 | (-80, 0) | 0 | 140 | 1..140 | [-128.0, 28.0, -43.0, 13.0] | 19@16 19@26 B@36 B@61 2@66 2@71 2@76 2@81 2@86 2@91 2@96 B@101 2@106 2@111 2@116 2@121 2@126 2@131 2@136 |

Displacement (sum of the velocities, class 0) per facing, left / right / up / down, and total frames left / up (class 1 adds 5 frames and 10 px, class 2 adds 10 frames and 30 px in stages 1-5 for every weapon and facing):

| stage | sword | axe | spear |
|---|---|---|---|
| 1 | (-30, 0) / (30, 0) / (0, -30) / (0, 30); 31 / 31 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 51 / 51 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 56 / 56 |
| 2 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 46 / 46 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 41 / 41 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 71 / 71 |
| 3 | (-30, 0) / (30, 0) / (0, -30) / (0, 30); 61 / 61 | (-30, 0) / (30, 0) / (0, -30) / (0, 30); 71 / 71 | (-30, 0) / (30, 0) / (0, -30) / (0, 30); 111 / 111 |
| 4 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 101 / 101 | (-40, 0) / (40, 0) / (0, -40) / (0, 40); 66 / 66 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 101 / 101 |
| 5 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 81 / 81 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 61 / 61 | (0, 0) / (0, 0) / (0, 0) / (0, 0); 76 / 76 |
| 6 | (-10, 0) / (10, 0) / (10, 0) / (10, 0); 151 / 151 | (-10, 0) / (10, 0) / (10, 0) / (10, 0); 151 / 151 | (-10, 0) / (10, 0) / (10, 0) / (10, 0); 151 / 151 |
| 7 | (-80, 0) / (80, 0) / (0, -80) / (0, 80); 91 / 91 | (-110, 0) / (110, 0) / (0, -110) / (0, 110); 111 / 111 | (-80, 0) / (80, 0) / (0, -80) / (0, 80); 101 / 101 |
| 8 | (-80, 0) / (80, 0) / (0, -80) / (0, 80); 81 / 81 | (-120, 0) / (120, 0) / (0, -120) / (0, 120); 86 / 86 | (-80, 0) / (80, 0) / (0, -80) / (0, 80); 141 / 141 |

Stage 6 shifts the hero by 10 px along x (-10 facing left, +10 in the other three facings; a loop of 1-2 px steps over 150 frames with a 56 x 56 weapon box); stages 7 and 8 are the dash attacks (80 px for the sword and the spear, 110 and 120 px for the axe).

### 4.4 Frame-by-frame timelines (class 0, facing left) [V]
Columns as in section 1.2; `v` is px per frame, z the vertical velocity of a jump. The other classes differ by the dash prefix (section 4.3); other facings by the rotated boxes and velocities (available through `tools/weapon_report.py ... tl`).

sword, stage 1:

sword power 1 0 left end of state at frame 31 (0.516 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | -1, 0, 1 | - | tangible | 0, 0, 0 |
| 11-20 | -1, 0, 0 | -16, -36, 32, 32 | intangible | -10, 0, 10 |
| 21-25 | -1, 0, -1 | -20, -25, 32, 32 | intangible | -20, 0, 10 |
| 26-28 | -1, 0, -2 | -16, -3, 32, 32 | intangible | -25, 0, 5 |
| 29-30 | -1, 0, 0 | -16, -3, 32, 32 | intangible | -28, 0, 0 |
| 31-31 | 0, 0, -4 | - | tangible | -30, 0, 0 |

sword, stage 2:

sword power 2 0 left end of state at frame 46 (0.765 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-30 | 0 | - | intangible | 0, 0, 0 |
| 31-35 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 36-40 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 41-45 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 46-46 | 0, 0, -4 | - | tangible | 0, 0, 0 |

sword, stage 3:

sword power 3 0 left end of state at frame 61 (1.015 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-5 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 6-10 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | 4, -3, 28, 28 | intangible | 0, 0, 0 |
| 21-25 | 0 | -20, -7, 32, 32 | intangible | 0, 0, 0 |
| 26-30 | 0 | -12, -15, 28, 28 | intangible | 0, 0, 0 |
| 31-40 | -1, 0, 1 | - | tangible | 0, 0, 0 |
| 41-50 | -1, 0, 0 | -16, -36, 32, 32 | intangible | -10, 0, 10 |
| 51-55 | -1, 0, -1 | -20, -25, 32, 32 | intangible | -20, 0, 10 |
| 56-58 | -1, 0, -2 | -16, -3, 32, 32 | intangible | -25, 0, 5 |
| 59-60 | -1, 0, 0 | -16, -3, 32, 32 | intangible | -28, 0, 0 |
| 61-61 | 0, 0, -4 | - | tangible | -30, 0, 0 |

sword, stage 4:

sword power 4 0 left end of state at frame 101 (1.681 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 11-15 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 21-25 | 0 | -4, -3, 28, 28 | intangible | 0, 0, 0 |
| 26-30 | 0 | 20, -7, 32, 32 | intangible | 0, 0, 0 |
| 31-35 | 0 | 12, -15, 28, 28 | intangible | 0, 0, 0 |
| 36-40 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 41-45 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 46-50 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 51-60 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 61-65 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 66-70 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 71-75 | 0 | -4, -3, 28, 28 | intangible | 0, 0, 0 |
| 76-80 | 0 | 20, -7, 32, 32 | intangible | 0, 0, 0 |
| 81-85 | 0 | 12, -15, 28, 28 | intangible | 0, 0, 0 |
| 86-90 | 0 | -16, -26, 32, 32 | intangible | 0, 0, 0 |
| 91-95 | 0 | -20, -15, 32, 32 | intangible | 0, 0, 0 |
| 96-100 | 0 | -16, 2, 32, 32 | intangible | 0, 0, 0 |
| 101-101 | 0, 0, -4 | - | tangible | 0, 0, 0 |

sword, stage 5:

sword power 5 0 left end of state at frame 81 (1.348 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | 0 | - | intangible | 0, 0, 0 |
| 21-80 | 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 81-81 | 0, 0, -4 | - | tangible | 0, 0, 0 |

sword, stage 6:

sword power 6 0 left end of state at frame 151 (2.513 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | -1, -1, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 11-20 | 0, -1, 0 | 0, -15, 56, 56 | intangible | -10, -10, 0 |
| 21-30 | 1, -1, 0 | 0, -15, 56, 56 | intangible | -10, -20, 0 |
| 31-40 | 2, 1, 0 | 0, -15, 56, 56 | intangible | 0, -30, 0 |
| 41-50 | 1, 2, 0 | 0, -15, 56, 56 | intangible | 20, -20, 0 |
| 51-60 | -1, 2, 0 | 0, -15, 56, 56 | intangible | 30, 0, 0 |
| 61-70 | -2, 1, 0 | 0, -15, 56, 56 | intangible | 20, 20, 0 |
| 71-80 | -2, -1, 0 | 0, -15, 56, 56 | intangible | 0, 30, 0 |
| 81-90 | -2, -2, 0 | 0, -15, 56, 56 | intangible | -20, 20, 0 |
| 91-100 | 1, -2, 0 | 0, -15, 56, 56 | intangible | -40, 0, 0 |
| 101-110 | 2, -1, 0 | 0, -15, 56, 56 | intangible | -30, -20, 0 |
| 111-120 | 2, 1, 0 | 0, -15, 56, 56 | intangible | -10, -30, 0 |
| 121-130 | 0, 1, 0 | 0, -15, 56, 56 | intangible | 10, -20, 0 |
| 131-140 | -1, 1, 0 | 0, -15, 56, 56 | intangible | 10, -10, 0 |
| 141-150 | -1, 0, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 151-151 | 0, 0, -4 | - | tangible | -10, 0, 0 |

sword, stage 7:

sword power 7 0 left end of state at frame 91 (1.514 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-15 | 0 | - | intangible | 0, 0, 0 |
| 16-35 | -4, 0, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 36-40 | 0 | -16, -26, 32, 32 | intangible | -80, 0, 0 |
| 41-45 | 0 | -20, -15, 32, 32 | intangible | -80, 0, 0 |
| 46-50 | 0 | -16, 2, 32, 32 | intangible | -80, 0, 0 |
| 51-55 | 0 | 4, -3, 28, 28 | intangible | -80, 0, 0 |
| 56-60 | 0 | -20, -7, 32, 32 | intangible | -80, 0, 0 |
| 61-65 | 0 | -12, -15, 28, 28 | intangible | -80, 0, 0 |
| 66-75 | 0 | - | tangible | -80, 0, 0 |
| 76-85 | 0 | -20, -11, 36, 16 | intangible | -80, 0, 0 |
| 86-90 | 0 | - | tangible | -80, 0, 0 |
| 91-91 | 0, 0, -4 | - | tangible | -80, 0, 0 |

sword, stage 8:

sword power 8 0 left end of state at frame 81 (1.348 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | -4, 0, 0 | -16, -15, 32, 24 | intangible | 0, 0, 0 |
| 21-80 | 0 | 0, -15, 56, 56 | intangible | -80, 0, 0 |
| 81-81 | 0, 0, -4 | - | tangible | -80, 0, 0 |

axe, stage 1:

axe power 1 0 left end of state at frame 51 (0.849 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-35 | 0 | - | tangible | 0, 0, 0 |
| 36-40 | 0 | 8, -11, 20, 20 | intangible | 0, 0, 0 |
| 41-45 | 0 | -4, -3, 36, 24 | intangible | 0, 0, 0 |
| 46-50 | 0 | -16, -15, 28, 28 | intangible | 0, 0, 0 |
| 51-51 | 0, 0, -4 | - | tangible | 0, 0, 0 |

axe, stage 2:

axe power 2 0 left end of state at frame 41 (0.682 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | 0, -30, 32, 20 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, -18, 32, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | 0, -3, 32, 32 | intangible | 0, 0, 0 |
| 21-30 | 0 | 8, -11, 20, 20 | intangible | 0, 0, 0 |
| 31-35 | 0 | -4, -3, 36, 24 | intangible | 0, 0, 0 |
| 36-40 | 0 | -16, -15, 28, 28 | intangible | 0, 0, 0 |
| 41-41 | 0, 0, -4 | - | tangible | 0, 0, 0 |

axe, stage 3:

axe power 3 0 left end of state at frame 71 (1.181 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | 0, -30, 32, 20 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, -18, 32, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | 0, -3, 32, 32 | intangible | 0, 0, 0 |
| 21-30 | 0 | 8, -11, 20, 20 | intangible | 0, 0, 0 |
| 31-35 | 0 | -4, -3, 36, 24 | intangible | 0, 0, 0 |
| 36-40 | 0 | -16, -15, 28, 28 | intangible | 0, 0, 0 |
| 41-50 | -1, 0, 1 | - | tangible | 0, 0, 0 |
| 51-60 | -1, 0, 0 | 0, -40, 32, 20 | intangible | -10, 0, 10 |
| 61-65 | -1, 0, -1 | 0, -40, 32, 20 | intangible | -20, 0, 10 |
| 66-68 | -1, 0, -2 | -16, -23, 32, 32 | intangible | -25, 0, 5 |
| 69-70 | -1, 0, 0 | -16, -23, 32, 32 | intangible | -28, 0, 0 |
| 71-71 | 0, 0, -4 | - | tangible | -30, 0, 0 |

axe, stage 4:

axe power 4 0 left end of state at frame 66 (1.098 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0 | 0, -30, 32, 20 | intangible | 0, 0, 0 |
| 11-15 | 0 | -16, -18, 32, 32 | intangible | 0, 0, 0 |
| 16-20 | 0 | 0, -3, 32, 32 | intangible | 0, 0, 0 |
| 21-25 | 1, 0, 1 | 0, -11, 32, 32 | intangible | 0, 0, 0 |
| 26-30 | 1, 0, 1 | 0, -16, 32, 32 | intangible | 5, 0, 5 |
| 31-35 | 1, 0, 1 | 0, -21, 32, 32 | intangible | 10, 0, 10 |
| 36-40 | 1, 0, 1 | 0, -26, 32, 32 | intangible | 15, 0, 15 |
| 41-45 | 0, 0, -4 | - | tangible | 20, 0, 20 |
| 46-50 | -3, 0, 0 | - | tangible | 20, 0, 0 |
| 51-65 | -3, 0, 0 | -16, -15, 32, 16 | intangible | 5, 0, 0 |
| 66-66 | 0, 0, -4 | - | tangible | -40, 0, 0 |

axe, stage 5:

axe power 5 0 left end of state at frame 61 (1.015 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-60 | 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 61-61 | 0, 0, -4 | - | tangible | 0, 0, 0 |

axe, stage 6:

axe power 6 0 left end of state at frame 151 (2.513 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | -1, -1, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 11-20 | 0, -1, 0 | 0, -15, 56, 56 | intangible | -10, -10, 0 |
| 21-30 | 1, -1, 0 | 0, -15, 56, 56 | intangible | -10, -20, 0 |
| 31-40 | 2, 1, 0 | 0, -15, 56, 56 | intangible | 0, -30, 0 |
| 41-50 | 1, 2, 0 | 0, -15, 56, 56 | intangible | 20, -20, 0 |
| 51-60 | -1, 2, 0 | 0, -15, 56, 56 | intangible | 30, 0, 0 |
| 61-70 | -2, 1, 0 | 0, -15, 56, 56 | intangible | 20, 20, 0 |
| 71-80 | -2, -1, 0 | 0, -15, 56, 56 | intangible | 0, 30, 0 |
| 81-90 | -2, -2, 0 | 0, -15, 56, 56 | intangible | -20, 20, 0 |
| 91-100 | 1, -2, 0 | 0, -15, 56, 56 | intangible | -40, 0, 0 |
| 101-110 | 2, -1, 0 | 0, -15, 56, 56 | intangible | -30, -20, 0 |
| 111-120 | 2, 1, 0 | 0, -15, 56, 56 | intangible | -10, -30, 0 |
| 121-130 | 0, 1, 0 | 0, -15, 56, 56 | intangible | 10, -20, 0 |
| 131-140 | -1, 1, 0 | 0, -15, 56, 56 | intangible | 10, -10, 0 |
| 141-150 | -1, 0, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 151-151 | 0, 0, -4 | - | tangible | -10, 0, 0 |

axe, stage 7:

axe power 7 0 left end of state at frame 111 (1.847 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | 0, 0, 2 | - | tangible | 0, 0, 0 |
| 11-30 | -4, 0, 0 | 0, -31, 32, 32 | intangible | 0, 0, 20 |
| 31-40 | 0, 0, -2 | - | tangible | -80, 0, 20 |
| 41-50 | 0 | 0, -30, 32, 20 | intangible | -80, 0, 0 |
| 51-55 | 0 | -16, -18, 32, 32 | intangible | -80, 0, 0 |
| 56-60 | 0 | 0, -3, 32, 32 | intangible | -80, 0, 0 |
| 61-70 | 0 | 8, -11, 20, 20 | intangible | -80, 0, 0 |
| 71-75 | 0 | -4, -3, 36, 24 | intangible | -80, 0, 0 |
| 76-80 | 0 | -16, -15, 28, 28 | intangible | -80, 0, 0 |
| 81-90 | -1, 0, 1 | - | tangible | -80, 0, 0 |
| 91-100 | -1, 0, 0 | 0, -40, 32, 20 | intangible | -90, 0, 10 |
| 101-105 | -1, 0, -1 | 0, -40, 32, 20 | intangible | -100, 0, 10 |
| 106-108 | -1, 0, -2 | -16, -23, 32, 32 | intangible | -105, 0, 5 |
| 109-110 | -1, 0, 0 | -16, -23, 32, 32 | intangible | -108, 0, 0 |
| 111-111 | 0, 0, -4 | - | tangible | -110, 0, 0 |

axe, stage 8:

axe power 8 0 left end of state at frame 86 (1.431 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | -4, 0, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 21-30 | 0 | 0, -30, 32, 20 | intangible | -80, 0, 0 |
| 31-35 | 0 | -16, -18, 32, 32 | intangible | -80, 0, 0 |
| 36-40 | 0 | 0, -3, 32, 32 | intangible | -80, 0, 0 |
| 41-45 | 1, 0, 1 | 0, -11, 32, 32 | intangible | -80, 0, 0 |
| 46-50 | 1, 0, 1 | 0, -16, 32, 32 | intangible | -75, 0, 5 |
| 51-55 | 1, 0, 1 | 0, -21, 32, 32 | intangible | -70, 0, 10 |
| 56-60 | 1, 0, 1 | 0, -26, 32, 32 | intangible | -65, 0, 15 |
| 61-65 | 0, 0, -4 | - | tangible | -60, 0, 20 |
| 66-70 | -3, 0, 0 | - | tangible | -60, 0, 0 |
| 71-85 | -3, 0, 0 | -16, -15, 32, 16 | intangible | -75, 0, 0 |
| 86-86 | 0, 0, -4 | - | tangible | -111, 0, 0 |

spear, stage 1:

spear power 1 0 left end of state at frame 56 (0.932 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-30 | 0 | - | tangible | 0, 0, 0 |
| 31-35 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 36-45 | 0 | -24, -11, 36, 12 | intangible | 0, 0, 0 |
| 46-55 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 56-56 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, stage 2:

spear power 2 0 left end of state at frame 71 (1.181 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | 0 | - | intangible | 0, 0, 0 |
| 21-25 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 26-35 | 0 | -24, -11, 36, 12 | intangible | 0, 0, 0 |
| 36-50 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 51-60 | 0 | -24, -11, 36, 12 | intangible | 0, 0, 0 |
| 61-70 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 71-71 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, stage 3:

spear power 3 0 left end of state at frame 111 (1.847 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-30 | 0 | - | tangible | 0, 0, 0 |
| 31-35 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 36-45 | 0 | -24, -11, 36, 12 | intangible | 0, 0, 0 |
| 46-60 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 61-70 | 0 | -24, -11, 36, 12 | intangible | 0, 0, 0 |
| 71-80 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 81-85 | -1, 0, 1 | -12, -22, 28, 28 | intangible | 0, 0, 0 |
| 86-90 | -1, 0, 1 | -12, -27, 28, 28 | intangible | -5, 0, 5 |
| 91-100 | -1, 0, 0 | -12, -32, 28, 28 | intangible | -10, 0, 10 |
| 101-105 | -1, 0, -1 | -20, -21, 32, 32 | intangible | -20, 0, 10 |
| 106-108 | -1, 0, -2 | -20, -16, 32, 32 | intangible | -25, 0, 5 |
| 109-110 | -1, 0, 0 | -20, -16, 32, 32 | intangible | -28, 0, 0 |
| 111-111 | 0, 0, -4 | - | tangible | -30, 0, 0 |

spear, stage 4:

spear power 4 0 left end of state at frame 101 (1.681 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | 0 | - | intangible | 0, 0, 0 |
| 21-25 | 0 | -4, -26, 48, 28 | intangible | 0, 0, 0 |
| 26-30 | 0 | -28, -18, 40, 32 | intangible | 0, 0, 0 |
| 31-35 | 0 | -16, 2, 36, 36 | intangible | 0, 0, 0 |
| 36-40 | 0 | 4, -3, 24, 24 | intangible | 0, 0, 0 |
| 41-45 | 0 | -20, -3, 40, 24 | intangible | 0, 0, 0 |
| 46-50 | 0 | -20, -15, 28, 28 | intangible | 0, 0, 0 |
| 51-55 | 0 | -12, -22, 28, 28 | intangible | 0, 0, 0 |
| 56-65 | 0 | -20, -11, 32, 32 | intangible | 0, 0, 0 |
| 66-70 | 0 | -12, -22, 28, 28 | intangible | 0, 0, 0 |
| 71-75 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 76-95 | 0 | -24, -11, 44, 20 | intangible | 0, 0, 0 |
| 96-100 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 101-101 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, stage 5:

spear power 5 0 left end of state at frame 76 (1.265 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-15 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 16-75 | 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 76-76 | 0, 0, -4 | - | tangible | 0, 0, 0 |

spear, stage 6:

spear power 6 0 left end of state at frame 151 (2.513 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-10 | -1, -1, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 11-20 | 0, -1, 0 | 0, -15, 56, 56 | intangible | -10, -10, 0 |
| 21-30 | 1, -1, 0 | 0, -15, 56, 56 | intangible | -10, -20, 0 |
| 31-40 | 2, 1, 0 | 0, -15, 56, 56 | intangible | 0, -30, 0 |
| 41-50 | 1, 2, 0 | 0, -15, 56, 56 | intangible | 20, -20, 0 |
| 51-60 | -1, 2, 0 | 0, -15, 56, 56 | intangible | 30, 0, 0 |
| 61-70 | -2, 1, 0 | 0, -15, 56, 56 | intangible | 20, 20, 0 |
| 71-80 | -2, -1, 0 | 0, -15, 56, 56 | intangible | 0, 30, 0 |
| 81-90 | -2, -2, 0 | 0, -15, 56, 56 | intangible | -20, 20, 0 |
| 91-100 | 1, -2, 0 | 0, -15, 56, 56 | intangible | -40, 0, 0 |
| 101-110 | 2, -1, 0 | 0, -15, 56, 56 | intangible | -30, -20, 0 |
| 111-120 | 2, 1, 0 | 0, -15, 56, 56 | intangible | -10, -30, 0 |
| 121-130 | 0, 1, 0 | 0, -15, 56, 56 | intangible | 10, -20, 0 |
| 131-140 | -1, 1, 0 | 0, -15, 56, 56 | intangible | 10, -10, 0 |
| 141-150 | -1, 0, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 151-151 | 0, 0, -4 | - | tangible | -10, 0, 0 |

spear, stage 7:

spear power 7 0 left end of state at frame 101 (1.681 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-20 | 0 | - | intangible | 0, 0, 0 |
| 21-40 | -4, 0, 0 | -12, -15, 40, 24 | intangible | 0, 0, 0 |
| 41-100 | 0 | 0, -15, 56, 56 | intangible | -80, 0, 0 |
| 101-101 | 0, 0, -4 | - | tangible | -80, 0, 0 |

spear, stage 8:

spear power 8 0 left end of state at frame 141 (2.346 s), gauge set to 60

| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |
|---|---|---|---|---|
| 0-0 | 0 | - | tangible | 0, 0, 0 |
| 1-15 | 0 | -4, -3, 32, 12 | intangible | 0, 0, 0 |
| 16-35 | -4, 0, 0 | 0, -15, 56, 56 | intangible | 0, 0, 0 |
| 36-40 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 41-50 | 0 | -24, -11, 36, 12 | intangible | -80, 0, 0 |
| 51-65 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 66-70 | 0 | -28, -11, 32, 16 | intangible | -80, 0, 0 |
| 71-75 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 76-80 | 0 | -28, -11, 32, 32 | intangible | -80, 0, 0 |
| 81-85 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 86-90 | 0 | -32, -15, 32, 32 | intangible | -80, 0, 0 |
| 91-95 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 96-100 | 0 | -32, -11, 32, 32 | intangible | -80, 0, 0 |
| 101-105 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 106-110 | 0 | -28, -11, 32, 16 | intangible | -80, 0, 0 |
| 111-115 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 116-120 | 0 | -28, -11, 32, 32 | intangible | -80, 0, 0 |
| 121-125 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 126-130 | 0 | -32, -15, 32, 32 | intangible | -80, 0, 0 |
| 131-135 | 0 | -4, -3, 32, 12 | intangible | -80, 0, 0 |
| 136-140 | 0 | -32, -11, 32, 32 | intangible | -80, 0, 0 |
| 141-141 | 0, 0, -4 | - | tangible | -80, 0, 0 |

### 4.5 What the stages are not [V]
- Repeated pieces (sword stage 4: two copies of a 10-step piece, stage 5: three copies of a 4-step piece; stage 6: fifteen alternations of two 2-step pieces for every weapon; spear stage 8: two copies of one piece) are animation and sound only: the target is hit once per attack (section 5.1).
- The hero is airborne in the sword stages 1, 3, the axe stages 3, 4, 7, 8 and the spear stage 3 (jump pieces with vz = +1/+2 and the end-of-jump -1/-2, 10-20 px high; max height column). The weapon box of an air piece is placed at the sprite's height, so a ground target is hit only while the box overlaps it.

### 4.6 Spawned objects: none [V]
For hero 0, facing left and up, all four normal ids and all 24 charged animations of each weapon were run while the object records in the slots 3-31 were watched: no slot changed its object id in any run (`spawn` in the JSON, empty lists). The weapon is drawn by the hero's own pieces (list 1 body pieces and list 2 effect pieces, `docs/graphics.md` section 5). The scripts of the three weapons contain no operation that creates an object: the operation bytes used are 0x83, 0x8D, 0x8F-0xAA (velocity presets and flags), 0xF0, 0xF1, 0xF9 and, in the spear only, 0xC0 (three uses; it writes `E104-E107` and calls the effect-palette routine `$C1:859B` [C]). Nothing in these animations throws the weapon; thrown weapons are a separate weapon type (type 7) outside this document.

## 5. Hits, damage, status, sounds

### 5.1 One hit per target [V]
Measured with a dummy 14 and 30 px in front, hero 0 facing left, level 8, stages 0-8 (stage 0 = a normal swing with the target near and `$F4` even), 400 frames each. Exactly one HP change per attack and per target, never two; with two dummies (20 and 26 px in front) both lost HP once, in the same frame. The animation chosen with the dummy at 14 px / 30 px was id 1 / 2 at stage 0 and 4k / 4k+1 at stage k (even `$F4`). Counting the calls of `$C0:4FED` with the dummy as defender gave 1 per attack in every run (`hit_routine_calls_on_slot3` in the JSON). First box frame (counted from the press or release frame), hero hit flag and damage frame:

| stage | sword: box, flag, damage frame (14 px) | axe | spear |
|---|---|---|---|
| 0 | 11, 12, 13 | 6, 7, 8 | 1, 2, 3 |
| 1 | 11, 12, 13 | 36, 42, 43 | 31, 32, 33 |
| 2 | 31, 32, 33 | 1, 4, 8 | 21, 22, 23 |
| 3 | 1, 2, 3 | 1, 4, 8 | 31, 32, 33 |
| 4 | 1, 2, 3 | 1, 4, 8 | 21, 22, 23 |
| 5 | 21, 22, 23 | 1, 2, 3 | 1, 2, 3 |
| 6 | 1, 2, 3 | 1, 2, 3 | 1, 2, 3 |
| 7 | 16, 17, 18 | 11, 12, 13 | 21, 22, 23 |
| 8 | 1, 2, 3 | 1, 2, 3 | 1, 2, 3 |

The damage frame is the first box frame + 2 for a slot-3 monster when the box overlaps the target at once; when the box has to travel (dash pieces) the first overlap is later (the flag frame is the first overlap, not the first box frame: for example the axe id 2 with the dummy at 30 px: box from frame 1, hit at frame 13). Reach: the frame of the hit for a dummy at distance d straight ahead in the facing direction (blank = no hit during the whole attack; hero 0, level 8):

| weapon, facing, stage | 14 px | 30 px | 50 px | 80 px | 110 px |
|---|---|---|---|---|---|
| sword, left, 0 | 13 | 8 | - | - | - |
| sword, left, 4 | 3 | 8 | 13 | - | - |
| sword, left, 8 | 3 | 3 | 8 | 13 | 23 |
| sword, up, 0 | 13 | 3 | - | - | - |
| sword, up, 4 | 3 | 8 | 13 | - | - |
| sword, up, 8 | 3 | 3 | 8 | 18 | 23 |
| axe, left, 0 | 8 | 13 | - | - | - |
| axe, left, 4 | 8 | 8 | 13 | 68 | - |
| axe, left, 8 | 3 | 3 | 8 | 13 | 23 |
| axe, up, 0 | 8 | 18 | - | - | - |
| axe, up, 4 | 3 | 8 | 13 | 23 | - |
| axe, up, 8 | 3 | 3 | 8 | 18 | 23 |
| spear, left, 0 | 3 | 8 | 8 | - | - |
| spear, left, 4 | 23 | 28 | 33 | 38 | - |
| spear, left, 8 | 3 | 18 | 23 | 33 | 38 |
| spear, up, 0 | 3 | 3 | - | - | - |
| spear, up, 4 | 23 | 28 | 33 | 33 | - |
| spear, up, 8 | 3 | 3 | 23 | 28 | 38 |

(right and down were measured too and are in the JSON.)

### 5.2 Damage [V]
Each hit uses `docs/rom-combat.md` 4.3 with the stage read from `E19B`: `v = atk * (2*stage + 4) >> 2` (x1.0, 1.5, ... 5.0), `E19B` keeping its stage for the whole attack (sampled every frame during the stage 8 attack: only 8). The weapon type changes nothing in this formula; the three weapons differ only by `atk`. Measured with the real routines on 300 random RNG states, hero 0, hit rate 1.00 for every cell (min / mean / max):

| stage | sword (atk 77) | axe (atk 78) | spear (atk 78) |
|---|---|---|---|
| 0 | 77: 72 / 152.4 / 296 | 78: 73 / 155.7 / 298 | 78: 73 / 153.5 / 298 |
| 1 | 115: 108 / 187.8 / 378 | 117: 109 / 199.8 / 382 | 117: 109 / 189.9 / 382 |
| 2 | 154: 144 / 238.7 / 460 | 156: 146 / 249.1 / 464 | 156: 146 / 240.8 / 464 |
| 3 | 192: 180 / 270.7 / 542 | 195: 183 / 284.4 / 548 | 195: 183 / 273.9 / 548 |
| 4 | 231: 217 / 317.3 / 622 | 234: 219 / 327.4 / 630 | 234: 219 / 320.4 / 628 |
| 5 | 269: 252 / 371.2 / 704 | 273: 256 / 388.8 / 714 | 273: 256 / 376.1 / 714 |
| 6 | 308: 289 / 399.2 / 786 | 312: 293 / 427.9 / 796 | 312: 293 / 403.4 / 794 |
| 7 | 346: 325 / 454.6 / 868 | 351: 329 / 477.0 / 878 | 351: 329 / 460.0 / 878 |
| 8 | 385: 361 / 495.9 / 952 | 390: 366 / 518.6 / 962 | 390: 366 / 501.3 / 962 |

(first number = `atk*(2s+4)>>2`; the spread is the random term, the `E1E6`^2 = 64 bonus and the critical hit, which doubles; one hit is capped at 999. Single hit values in the hit runs that are about twice the value of the same stage in the other run (for example 498 against 247 for the sword stage 2, dummy at 14 against 30 px) are consistent with a critical hit, which doubles; the routine ran once, so they are not two hits. That a critical hit was the cause was not separately checked.)

### 5.3 Status and element
Rows carry an enemy-type mask / element byte in `E194` and a status word with a chance (80 %, 99 % for row 17); sword and axe rows have no status word; spear rows 29, 31, 32 have (section 2.7). The table of all rows (atk, accuracy, crit base, status, mask after the equip routines for hero 0, level 8) is in `hits.rows_of_type_hero0_after_equip_level8` of the JSON; the base values are in `data/weapons.json`.

### 5.4 Sound ids (first byte of the request pair at `$C3:0004`, hexadecimal) [V]
Normal swings (first step): sword id 0 / 1 / 2 = 0x4 / 0x2 / 0x3, axe 0x8 for all ids, spear id 0 / 1 / 2 = 0x1B / 0x1B / 0xB. Charged attacks: stages (class 0, facing left) in which each id is requested:


| id | sword | axe | spear |
|---|---|---|---|
| 0x2 | 7 | - | 8 |
| 0x3 | 1,3,4,7 | - | - |
| 0x4 | 2,3,4,5,6,7,8 | - | - |
| 0x8 | - | 1,2,3,4,5,6,7,8 | - |
| 0xB | - | - | 1,2,3,4,8 |
| 0x18 | 1,3,8 | 3,7 | 3 |
| 0x19 | - | - | 2,4,5,7,8 |
| 0x1B | - | - | 2,4,6,7 |
| 0x1C | - | - | 7 |

Other sounds: 0x0B is also the class 1 / class 2 dash prefix of every weapon; 0x35 (second byte 0x0F, third 96) is requested in the damage frame of a hit on the dummy (seen in every hit run); 0x26, 0x27, 0x28 = gauge empty, charge hum (every 8 frames), stage reached. The per-attack lists with frames are in the last column of the tables of section 4.3.

### 5.5 Knockback of the target [V]
The weapons apply no knockback themselves. The hurt reaction of the target is chosen from the damage (`$C0:4F2A-4F44`): a hit of at least a quarter of the target's max HP gives hurt code `E011 = 0x89` (137), which pushes the target 40 px opposite to its facing; a smaller hit gives 0x88 (136) and no push. Measured on the dummy (facing down) for max HP 600 / 1000 / 2000 and stages 0 / 4 / 8 with all three weapons: the push (40 px) happened exactly when damage >= max HP / 4 in 26 of 27 cases (damages 154-680 against quarters 150, 250, 500); in the 27th the target died (spear stage 4 on 600 HP) and no hurt code was set. Equality was not produced. A higher stage knocks back more targets only because it deals more damage.

## 6. Script facts used
- Frame words, operations and the 0x8F+k velocity presets are as in `docs/glove-attacks.md` section 6. The operation bytes appearing in the sword, axe and spear scripts (any facing): 0x83, 0x8D, 0x8F, 0x91-0x93, 0x99-0x9B, 0x9D-0x9F, 0xA0, 0xA1 (axe), 0xA4, 0xA5, 0xA7 (axe), 0xA8-0xAA, 0xC0 (spear), 0xF0, 0xF1, 0xF9. Read from `$C1:D5C0` and `$C1:D7DF` [C]: 0x82/0x83 clear `E104` and call the effect-palette routine `$C1:859B` with `E069`; 0x84-0x85 OR bits into `E00E` and set `E039 = 0x10`; 0x8D clears `E047` and continues as 0xC0 with the argument `E069`; 0xC0-0xC7 store the argument and the next numbers in `E105-E107`, clear `E047` and call `$C1:859B`. What these fields do afterwards is not determined.
- Pieces are shared between facings only for the side scripts (left uses the right-facing script mirrored); up and down have their own pieces.
- The weapon box is not an operation: it comes with the sprite frame description fetched with each frame word, so boxes change at step boundaries only.

## 7. Tools and commands
```
R=path/to/rom.sfc ; S=path/to/state.zs3          # a state with the three heroes idle on a map
python3 tools/weapon_attacks.py "$R" "$S" sword.json sword                  # all sections, ~25 min (invuln ~4-6 min of it)
python3 tools/weapon_attacks.py "$R" "$S" axe.json axe structure variants   # some sections
python3 tools/weapon_report.py merge data/weapons_melee.json sword.json axe.json spear.json
python3 tools/weapon_report.py data/weapons_melee.json sword normal         # tables of section 1
python3 tools/weapon_report.py data/weapons_melee.json sword power          # section 4.3
python3 tools/weapon_report.py data/weapons_melee.json axe tl power 8 0 left   # one timeline
python3 tools/weapon_report.py data/weapons_melee.json spear structure      # section 4.2 (also: pieces, phase, shared, gauge, hits)
python3 tools/rip_weapon_anims.py "$R" "$S" outdir sword                    # graphics (section 8)
```
`tools/weapon_attacks.py` sections: `structure variants chooser gauge charge power spawn grades status hits invuln`. Data: `data/weapons_melee.json`, keyed by weapon name; each weapon has the keys of `data/glove_attacks.json` (`normal`, `normal_runs`, `chooser`, `gauge`, `charge`, `power` (`slotN` > stage > class > facing; segment rows have the fields of `SEG_FIELDS` in `tools/glove_attacks.py`), `structure`, `hits`, `invulnerability`) plus `spawn`, `grades`, `status`; `structure` additionally has the ordered call lists (`seq`) and the operation counts of every piece.

## 8. Graphics
Every normal and charged attack of the three weapons was ripped for the three heroes and four directions with `tools/rip_weapon_anims.py` (a thin wrapper of `tools/rip_hero_anims.py`; the output layout and the data structures are in `docs/graphics.md` sections 5-8): `OUTDIR/<hero>/<attack>_<level>_<dir>_<nn>.png` and `<attack>_<level>_<dir>.json`, plus `OUTDIR/index.json`, one output directory per weapon. Attack names: `normal0` ... `normal3` (animation ids 0-3), `charge1..8` (far or no target, id 4k+2), `chargemid1..8` (id 4k+1), `chargenear1..8` (id 4k). Each animation has per-frame durations, the actor offset per frame and the foot origin in the PNG. The weapon blade, the swing arcs and the effect flashes are pieces of the hero's own lists and are included in the PNGs; the effect pieces use sprite palette 0 whose colours cycle during the attack (the images keep the value of the frame in which they were recorded). The ground shadow is not drawn. The images are never stored in this repository.

Totals: 3 weapons x 3 heroes x 4 directions x 28 animations = 1,008 animations; distinct pictures: sword boy 6,637, girl 7,174, sprite 7,174; axe 6,528 / 7,028 / 7,028; spear 5,572 / 6,470 / 6,467. The static decoder `tools/hero_frames.py check` agrees with the recorded pieces (count, position, flips) for all script steps: checked script steps: sword 4,728, axe 4,596, spear 5,436, all matching, 0 differ [V].

Validation against the public sheets of The Spriters Resource with `tools/compare_sheet.py` (pixel for pixel on the 5-bit colours, effect-palette colours left out; "sheet" = the weapon sheet of the hero, "general" = the general sheet of the hero with all poses):

| weapon, hero | sheet | pictures found / ripped |
|---|---|---|
| sword, boy | Sword (Randi) | 6,637 / 6,637 |
| sword, boy | general Randi | 6,634 / 6,637 |
| sword, girl | Sword (Primm) | 6,208 / 7,174 (the sheet holds only part of the poses) |
| sword, girl | general Primm | 7,156 / 7,174 |
| sword, sprite | general Popoi | 7,156 / 7,174 |
| axe, boy | Axe (Randi) | 6,451 / 6,528 (all 77 missing pictures are up-facing charged attacks) |
| axe, boy / girl / sprite | general Randi / Primm / Popoi | 6,528 / 7,028 / 7,028, all found |
| spear, boy | Spear (Randi) | 5,572 / 5,572 |
| spear, boy / girl / sprite | general Randi / Primm / Popoi | 5,569 / 6,452 / 6,449 of 5,572 / 6,470 / 6,467 |

The pictures not found in a general sheet are a few poses of the spinning attacks (sword stage 8 facing down and sideways, spear stage 7 facing down and sideways); they are found in the weapon-specific boy sheets. A picture not found is either absent from the sheet or different; the two cases were not separated.

## 9. Verified
Verified by execution [V]: the swing start and its latency (0-4 frames by phase); the normal variants (steps, frames, boxes, sounds, no movement) for the three heroes and four facings for the three weapons; the variant chooser (thresholds on both axes, parity, independence of the facing); no combo and no buffering; the d-pad lock; the gauge (start value, freeze, countdown) for three Agi values; the charge timing per stage for three heroes; the release into the charged attack and its dependence on stage and class only; all 24 charged attacks of each weapon for the four facings on hero 0 and their timing and box timing on heroes 1 and 2; one hit per target; damage per stage and per gauge value with the real hit routines; the knockback rule; the body-box vulnerability on four attacks per weapon; the identity of the nine rows of a type; the absence of spawned objects; the pictures against the sheets.
Read from the disassembly only [C]: the meaning of operations 0x83-0x85, 0x8D, 0xC0; the chooser's use of `E1B1`.

## 10. Open questions (no values claimed)
- The rule for choosing the swing with more than one enemy on screen, and the metric behind the x/y thresholds 26/42 and 24/40.
- Whether the knockback test is `damage >= max HP/4` or `>` (equality not produced).
- What the third box `E0CC-E0CF` does, and what the operations 0x83-0x85, 0x8D, 0x99-0x9F, 0xA0-0xA7, 0xC0 do beyond what section 6 says.
- Which stage changes make sound 0x28 during the charge (it differs by weapon in these runs).
- The pictures listed in section 8 that no public sheet contains; the charge-up pose and stage-up flash were not ripped; full-screen flashes (HDMA, colour math) are not emulated.
- Whether a frame-skipping slowdown in busy scenes stretches these timings: the counts assume one main-loop pass per video frame.


# Polter Chair (monster id 0x0D = 13) - complete behavior recovered from the ROM (Secret of Mana USA)

Tags: **[V]** executed: the real 65816 code ran in `tools/cpu65816.py` (whole per-frame routine `$C0:B08C` on a ZSNES save state, or single AI handlers) and a model or decoder was compared with it; **[C]** read from the disassembly, not executed. What is not determined is in section 17 and carries no values. This document follows `docs/rabite.md` (AI engine, time base, shared ops) and `docs/monster-3.md` (the second monster, a ranged one; sections on commands, flags, reactions and graphics use the same method) and only describes what is specific here. Numbers come from `data/monster_13.json` (`tools/monster_report.py`).

Addressing as in `docs/rabite.md`; script addresses (pc) are offsets from ROM `0x104F15`. No ROM bytes are stored in the repo. Direction codes of commands: 1 right, 2 left, 4 down, 8 up. Name decoded from the ROM text (`tools/names.py`, name block index 0xDC). Seconds = frames / 60.0988; one AI step = 5 frames = 83.2 ms. Why this monster was chosen: `docs/monster-survey.md`.

## 1. Summary

- Object id 13, stat record `0x101C00 + 13 * 29` (level 8, HP 128, Str 12, Agi 10, EXP 21, gold 22, attack row 90), AI script entry pc `0x0B3E` (2878), 232 reachable instructions, 33 opcodes: 30 of the 33 that the Rabite script uses plus **three new ones: 34, BE, BF** [V: `tools/ai_ops.py --new`].
- It is an **ambusher that leaps**. After the spawn it stands and only turns in place (a 5-frame command repeated, nothing else) **until a hero is within 16 px or the chair has taken any damage**. Then it fights with leaps: a leap of 30 frames (30 px, up to a 20 px jump) or a double leap of 60 frames (up to 69 px) with a 24 x 24 weapon box, chosen by the distance to the target, and hops back or away in between. It never shoots.
- Attack: Str 12 + power 37 (row 90) = **attack 49**, accuracy 99, no crit, no status (chance byte 25 with an empty status word); against a hero with evade 0 and defense 0 the leap deals 49, 50 or 51.
- **Hit reaction**: hurt pose 105 frames (1.75 s) for a hit of at most max HP / 4 = 32; knock-back of 30 px and 140 frames (2.33 s) for a bigger hit. **Death**: about 105 frames (1.75 s), 21 EXP, 22 gold, chest 4/64.
- Verified: the AI model equals the real handlers in 9,000 of 9,000 random steps; the leap's weapon box test equals the observed hero hits in 200 of 200 random placements; 2,956 of its 3,620 ripped pictures are found exactly in the public sheet, 8 under a recolouring, and the 656 that are not found are the airborne tumbling poses, which the sheet does not contain (section 13).

## 2. Time base [V]
As the Rabite (`docs/rabite.md` section 2): AI step on every 5th frame, `frame mod 5` = 0 / 1 / 2 in slots 3 / 4 / 5 (72 steps each, `cadence` in the JSON). Command lengths are multiples of 5 frames; the flag byte of a command is a requested length in frames (`docs/monster-3.md` section 6), used here with `0x3C` = 60 frames.

## 3. ROM record and object entry

| item | value | tag |
|---|---|---|
| monster record `0x101C00 + 377` | level 8, HP 128, MP 0, Str 12, Agi 10, Int 21, Wis 21, evade 0, defense 0, magic evade 0, magic defense 0, type 2, element 128 (0x80), EXP 21, gold 22, status immunity word 0x1E20, attack rows 90 / 90, weapon level 0 | V (`data/monsters.json`, live object) |
| attack row 90 (`data/weapons.json`) | hit 99, power 37, crit 0, status empty (chance byte 25): **attack 49** (`obj+0x198`), accuracy 99, crit base 0 | V |
| object-table entry `0x100000 + 13 * 16` | tile source bank `$D9`, byte offset 0; piece-list offset 748; body height 13 (`obj+0x74` bits 0-6, bit 7 set); ordinary script table `$D1:5292`; attack script table `$D1:5A06`; AI entry pc 0x0B3E; shadow tables `$D1:44F6`; flags byte 0x35; palette at `$C8:1186` | C / V |
| drop row `0x103A50 + 65` | chest 4/64, trap threshold 24; contents 44 gold (57/64) or consumable id 10 (7/64) | V (section 11) |

## 4. Script ops, targets
The three new ops (`tools/ai_ops.py --new`, `tools/aidis.py --text`):

| op | length | behavior [V] |
|---|---|---|
| 34 off | 2-3 | jump unless the current target is on screen and within **16 px** (distance class 1: 16-bit sum of squares <= 256); 41 distances 0-39 checked, falls through exactly for d <= 16 |
| BE a b | 3 | command C1 turning toward the current target with a cardinal code (horizontal when `|dx| >= |dy|`), animation a, flag b; no target: no-op (1,680 placements, 0 mismatches) |
| BF a b | 3 | the same with the **opposite** cardinal code (away from the target) |

Targets, distance classes and the notes on "valid target" and on the 16-bit distance sum are as in `docs/monster-3.md` section 4 and `docs/rabite.md` section 4. The facing codes for ops that turn "toward" or "away" and the animation define the movement: with animation 1, 2 or 4 the actor hops forward along the facing, with animation 5 it hops **backwards** (so BE 05 = face the target and step back, BF 01 = face away and hop forward).

## 5. The script as a state machine [V]
The AI model `tools/ai_vm.py` (all ops of the script) equals the real AI step in **9,000 of 9,000** random steps (230 of 232 reachable instructions executed; the two others are a jump behind an unconditional jump (pc 0x0B6A) and a rare branch of the wander routine (pc 0x6858)); `tools/monster_model.py ROM STATE 13`.

### 5.1 Entry: the watch loop (pc 0x0B3E calls 0x0B6D)
```
0B6D  turn in place (E3 00 00, 5 frames)
0B70  acquire a target (wander hop if no valid hero is on screen)
0B73  turn in place (E3 00 00, 5 frames)
0B76  if HP > 127 (word obj+0x182; the chair has 128): if the target is NOT within 16 px, go to 0B70, else continue
0B81  pose 0 (E2 00, 5 frames), return to the main loop
```
So it sleeps while HP is 128 (never hit) and no valid hero is within 16 px. Leaving the loop: a hero at distance <= 16 (tested 10, 14, 16: left at frame 10; 17, 18, 24, 40, 80: still turning after 4 s) or **any damage** (a 1-point hit: the first AI step after the hurt pose is the pose at pc 0x0B81) [V]. With no valid hero at all (all off screen or disabled) the acquisition routine runs the wander hop, so the sleeping chair wanders while nobody is around (section 5.4).

### 5.2 Main loop (pc 0x0B41), evaluated after every command
`var3 = random 0..7`. With probability **1/8** (var3 = 0): idle, `E3 00 3C` = 60 frames (1.0 s) in the current facing, back to the top (no acquisition). Otherwise acquire a target and pick by its class:

| target | routine | what it does |
|---|---|---|
| <= 16 px | 0x0B84 | **gauge 0**: turn toward it (`BE 00 00`, 5 frames), hop back (`E3 05 00`: animation 5, 20 frames, 8 px backwards), then the attack check (swing 02, section 7). **Gauge > 0**: save the position, `BE 05 00` = face the target and hop back 8 px in 20 frames (`FD 05 00` = the diagonal-direction version when the position did not change since the last hop, i.e. blocked) |
| 17-32 px | 0x0BA1 | turn toward the target (`E4 00 00`, 5 frames). **Gauge 0**: `BE 00 00` (5 frames), `E3 05 00` (back hop 20 frames), swing. **Gauge > 0**: with probability 1/2 hop away with animation 1 (`BF 01 00` / `FE 01 00` when blocked: 25 frames, 15 px), with 1/2 dash away with animation 2 (`BF 02 00` / `FE 02 00`: 25 frames, 25 px) |
| 33-64 px | 0x0BD3 | `BE 00 00` (5 frames); **gauge 0**: `BE 00 00` (5 frames) and the swing; gauge > 0: `BE 00 00` (5 frames) and back to the loop |
| > 64 px | 0x0BE7 | repeat until the target is within 64 px: acquire; `var3 = random 0..2`: 1/3 `BE 02 00` (25 px dash toward, 25 frames), 1/3 `BE 04 00` (8 px, 20 frames), 1/3 `BE 01 00` (15 px, 25 frames); `FD ..` instead of `BE ..` when the position did not change (blocked) |

The leap itself is the swing: op E8 issues command 02 when the gauge is 0 and the game chooses the swing animation from the distance (section 7). In `trace` (hero at 12 px, 13 s) the sequence was: wake (pose 5 frames), turn, back hop 20 frames, leap 30 frames, back hop 20, idle 60 frames, dash away 25, idle 60, turn 10, leap 60 frames, back hop 20, ... [V].

### 5.3 Spawn
The first command is the turn `C1 04 00 00` (facing down in the harness) of the watch loop; there is no spawn animation and no sound. [V]

### 5.4 Wander (no valid hero), subroutine 0x67DF
As `docs/rabite.md` section 5.5 with this monster's hops: animation 4 = 20 frames / 8 px (the shortest), animation 1 = 25 frames / 15 px, animation 2 = 25 frames / 25 px, turn 5 frames, three turns in a row 15 frames. Seen with hero 0 disabled (status 0x0020, cleared by the game after about 7 s): about 20 wander commands in 6.6 s and then the watch loop again (`trace`) [V].

## 6. Commands (executed, `commands` in the JSON) [V]
Frames count from the AI step that issues the command (frame 0).

| command | frames (s) | movement | px/s |
|---|---|---|---|
| C1 anim 0 flag 0 (turn) | 5 (0.083) | none | 0 |
| C1 anim 0 flag 0x3C (idle) | 60 (0.998) | none | 0 |
| C1 anim 1 | 25 (0.416) | 15 px along the facing, 1 px/frame on frames 6-20 | 36.1 |
| C1 anim 2 | 25 (0.416) | 25 px, 1 px/frame on frames 1-25 | 60.1 |
| C1 anim 4 | 20 (0.333) | 8 px forward, 1 px/frame on frames 2-19 (not every frame) | 24.0 |
| C1 anim 5 | 20 (0.333) | 8 px **backward** (same frames as anim 4) | -24.0 |
| 40 pose 0 | 5 | none (the wake-up pose) | 0 |
| 40 pose 5 | 5 | none | 0 |
| 02 swing | 30 or 60 | section 7 | |

The diagonal codes (5, 6, 9, 10) give the horizontal movement of 1 / 2 only, for every animation [V: all 8 codes]. Flag byte: as in `docs/monster-3.md` section 6.

## 7. The leap (command 02, op E8) [V]
The swing animation is chosen by the real chooser from the distance to the target **along the facing axis**: for a target straight ahead (`swing.by_distance`, 45 distances from 10 to 98 px per facing):

| distance along the facing | animation | frames (s) | displacement |
|---|---|---|---|
| <= 40 px horizontal, <= 38 px vertical | 1 (single leap) | 30 (0.499) | about `distance - 10` px, at most 30 (the leap stops about 10 px short of the target): 0 px at 10, 30 px at 40 |
| >= 42 px horizontal, >= 40 px vertical | 2 (double leap) | 60 (0.998) | `distance - 10` up to 69 px (distance 80 and more: 69 px) |

Free-flight timeline of one leap (frames from the start of the command): frames 0-5 crouch (no movement); frames 6-10 1 px/frame, 11-15 2 px/frame, 16-20 1 px/frame, 21-25 2 px/frame (30 px in all); the jump height (`obj+0x45`) rises 3 px per frame from frame 6 (3, 6, 9, 12, 15), then 16, 17, 18, 19, 20 (frames 11-15), stays 20 until frame 20, falls 13, 6, 0 (frames 21-23), landing at frame 23; frames 25-29 recovery. The double leap repeats the same sequence from frame 30 (second jump 36-53, landing at 53, total 69 px: 30 + 5 + 34) [V].

Boxes (pixels relative to the object position, mirrored in x for the left facing; y includes the jump height): **weapon box 24 x 24, centre (0, -10) on the ground and (0, -25 / -30) in the air, present during the whole command**; body box 16 x 16 at (0, -6) on the ground, (0, -21 / -26) in the air. The weapon box starts in frame 0 of the command (an attack box exists even in the crouch). The hero is hit when the weapon box overlaps the hero's body box (`|cx1 - cx2| < (w1 + w2) / 2` and the same for y with the box of the previous frame, docs/glove-attacks.md section 2.5): against 50 random hero placements per facing (200 in all) prediction and observation agreed in **200 of 200** (hits 41 / 44 / 24 / 17), `contact.validation` [V]. Damage observed with a hero of evade 0 and defense 0: 49 (23 times), 50 (42), 51 (61) = attack 49 plus the random spread of docs/rom-combat.md section 4.

**Cooldown**: the gauge is loaded when the swing ends: `(100 - Agi) / 2 + 50 = 95` frames [C `$C0:F937`; V: 95 at the end of the swing, counting down one per frame]. The chair can attack again at the first AI step after the gauge reaches 0 (95 frames after the swing, i.e. about 1.6 s) if it chooses an attack branch.

**Sounds**: id **0x1C** (0.153 s) at frame 5 of each leap (frames 5 and 35 of the double leap); id **0x01** (0.189 s) at the frame in which the weapon box hits a hero (frame 28 in a double leap that reached the hero) [V].

## 8. State machine in seconds (summary)

| situation | what happens |
|---|---|
| spawn, HP 128, no hero within 16 px | turn command every 0.083 s (nothing else), indefinitely |
| hero within 16 px or any damage | wake pose 0.083 s, then the main loop |
| main loop, 1 pass in 8 | idle 1.0 s |
| hero <= 16 px, gauge 0 | turn 0.083 s, back hop 0.333 s (8 px), leap 0.499 s |
| hero <= 16 px, gauge > 0 | face the hero and hop back 8 px (0.333 s) |
| hero 17-32 px, gauge 0 | turn 0.083 s, turn 0.083 s, back hop 0.333 s, leap 0.499 s |
| hero 17-32 px, gauge > 0 | 1/2 hop away 0.416 s (15 px), 1/2 dash away 0.416 s (25 px) |
| hero 33-64 px | two turns 0.17 s, then the leap (anim 1 to about 40 px, else the double leap 0.998 s) when the gauge is 0 |
| hero > 64 px | approach steps 0.416 / 0.333 / 0.416 s (25 px / 8 px / 15 px, 1/3 each) until within 64 px |
| no valid hero | wander commands |
| hit | hurt 105 frames (1.75 s) for damage <= 32, else knock-back 30 px and 140 frames (2.33 s) |
| dead | about 105 frames (1.75 s), then the object is removed |

## 9. Hit reaction [V]
Same mechanism as the Chobin Hood (`docs/monster-3.md` section 9: `$C0:4EBC`, reaction code 8 for damage <= max HP / 4, else 9; stun counter `obj+0x1B4` = max(6, damage >> 3) ticks; hit sound 0x35):

| damage (hits measured) | animation | AI resumes | knock-back |
|---|---|---|---|
| 2, 5, 9, 13, 31 (<= 32) | 0x88 (ordinary animation 8: 35 frames) | frame 105 | none |
| 35, 39, 43, 75, 126 (> 32) | 0x89 (ordinary animation 9: 70 frames) | frame 140 | **30 px opposite to the facing** in all four facings (1 px/frame on frames 1-5, then 2 px/frame), shortened by walls; stun counter 6 (damage <= 55), 9 (damage 75), 15 (damage 126) |

The first AI step after a hit is the wake pose at pc 0x0B81 when the chair was asleep (HP drops below 128), otherwise the main loop. `AI resumes = max(105, animation + 70)` frames as for the Chobin Hood (35 + 70 = 105, 70 + 70 = 140) [V, 4 cases].

## 10. Death [V]
Lethal damage: status 0x8000, `obj+0x180` becomes 0xFB, sounds **0x35** (hit) and **0x9F** (1.452 s) at the kill frame, the death effect (blue flash, puffs, skeleton, bones: the same effect as the Chobin Hood, taken from the public Death Effects sheet) and the object is removed about 105 frames (1.75 s) later; the removal needs the AI step (the corpse script). **21 EXP** to every living hero (2,882,779 -> 2,882,800) and **22 gold** [V].

## 11. Drops [V]
Drop row 4 / 48 / 186 / 44 / 74: chest 4/64, trap threshold 24, 44 gold with probability 57/64 and consumable id 10 with 7/64; 300 runs of the real death routine: 27 chests (classes 2, 3, 4: 12, 9, 6); 300 runs of the content routine: 274 x 44 gold, 26 x item byte 0x4A [V].

## 12. Sound ids per action (rendered in `docs/audio.md`) [V]

| action | id (duration s) | when |
|---|---|---|
| leap | 0x1C (0.153) | frame 5 of each jump (frames 5 and 35 of the double leap) |
| hero hit by the weapon box | 0x01 (0.189) | the hit frame |
| chair hit by a hero | 0x35 (0.277) | the hit frame |
| death | 0x9F (1.452) | the kill frame |
| waking, turns, hops | none | |

## 13. Animations and graphics [V]
Tables (bank `$D1`): ordinary `$D1:5292` (21 animations), attack `$D1:5A06` (4 animations). How the table is chosen from the object state and the animation id: `docs/monster-3.md` section 13. Frames per animation (all facings equal):

| action | table, id | frames (s) |
|---|---|---|
| stand / turn | ordinary 0, 3 | one static picture per facing (a turn command lasts 5 frames) |
| hop 15 px / dash 25 px | ordinary 1 / 2 | 25 (0.416) each |
| hop forward / back 8 px | ordinary 4 / 5 | 20 (0.333) each |
| wake pose | attack 0 (state 0x40) | 5 |
| leap | attack 1 (state 0x80) | 30 (0.499) |
| double leap | attack 2 (state 0x80) | 60 in the frame loop (53 frames when the ripper plays the script alone, see section 17) |
| attack 3 | attack 3 | 60 (0.998), not used by the script |
| hurt (0x88) / knock-back (0x89) | ordinary 8 / 9 | 35 (0.583) / 70 (1.165) |
| ordinary 6, 7, 10-14 | | 25 / 55 / 20 / 35 / 25 / 35 / 35, not used by the script |
| ordinary 15, 16, 17 | | 110 / 110 / 120: the chair tumbling through the air (rotated pictures), not used |
| ordinary 18, 19, 20 | | 10 each; 19 is the grey pose |
| death | object 0xFB effect | 105-107 (1.75-1.78) |

Body: 4 pieces (16 x 16, tiles 64 / 66 / 68 / 70, palette row 5), ground shadow tile 0 palette 1 at (-8, -8), body height 13. The picture is 16 x 27 (stand) and 18 x 41 (leap) pixels with the foot point at (8, 24) / (9, 35). **Ripped animations**: `tools/rip_monster_anims.py ROM STATE OUTDIR 13`: **204 animations, 3,620 distinct pictures** (staged in `rom_gfx/monsters/13_polter_chair/`, outside this repository; per animation: PNGs with a transparent background and foot origin, JSON with per-picture durations in frames and seconds, displacement, boxes, velocity and sounds). Validation (`tools/validate_monster_gfx.py` against the public sheet "Polter Chair, Marmablue & Nemesis Owl" and the Death Effects sheet): **2,956 pictures found exactly, 8 only under a recolouring (the grey pose, ordinary 19), 656 not found**; all 656 are pictures of ordinary animations 15, 16 and 17 (the airborne tumbling, 328 distinct pictures, counted twice because the hurt set plays the same scripts) that the public sheet does not contain; every stand, hop, leap, double-leap, hurt, knock-back and death picture is found (the sheet shows the stance, the jump attack and the petrified chair).

## 14. What the Polter Chair does, for an implementation
1. Spawn: turn in place every 5 frames; do nothing else until a valid hero is within 16 px or HP < 128.
2. Then every AI step (5 frames) after each command: 1/8 idle 60 frames; otherwise pick the nearest valid hero and use the table of section 5.2 (back hop 8 px in 20 frames, hop away 15 px or dash away 25 px in 25 frames, approach 8 / 15 / 25 px, leap).
3. Leap: 30 frames (single, target <= 40 px along the facing) or 60 frames (double, farther); 24 x 24 weapon box for the whole command; jump arc 20 px; attack 49, accuracy 99; gauge 95 frames; sound 0x1C at +5 (and +35).
4. A hit: 105 frames hurt (damage <= 32) or knock-back 30 px and 140 frames; sound 0x35.
5. Death: 105 frames, 21 EXP, 22 gold, 6.25 % chest (44 gold or consumable 10), sound 0x9F.

## 15. Tools and how the numbers were obtained
- `tools/ai_ops.py ROM STATE --new`; `tools/ai_vm.py`, `tools/monster_model.py ROM STATE 13` (AI model against the real handlers).
- `tools/monster_report.py ROM STATE 13 data/monster_13.json --only record,model,cadence,commands,swing,contact,sleep,reaction,death,drops,trace`.
- `tools/rip_monster_anims.py`, `tools/validate_monster_gfx.py`, `tools/compare_sheet.py` (pictures).
- Save state: the map-246 arena state (`docs/rom-combat.md` section 19), hero 0 pinned; hits through `$C0:4F7B` with a chosen attack byte (hero `E1E6` bonus off).

## 16. Spawn and position conventions of the harness
The monster is created by the game's spawner `$C0:DE3B` from a map-object record at `$C830` (tile 20, 25 unless a hero offset is given: the monster is then placed at hero 0's position minus the offset); a monster placed at screen x < 0 or >= 256 behaves as "within 64 px" (docs/rabite.md section 4), so offsets that put it off screen were avoided [V].

## 17. Open questions (no values are claimed)
- Why the ripper's play of attack animation 2 lasts 53 frames while the command in the frame loop lasts 60 (the shorter script end was not traced).
- The AI-resume rule `animation + 70` (as in `docs/monster-3.md`).
- Whether the weapon box is "active" from frame 0 of the crouch in the sense of the hit test (the test of the previous frame's box against the hero's body box matched all 200 placements, so the observed hits are consistent with it).
- The effect of the element byte 128 and of the status immunity word 0x1E20 (not tested with spells).
- The tumbling animations 15-17 and the grey pose (19): the engine state that plays them (thrown by a spell, petrified) was not examined; the pictures are ripped.
- Terrain collision of leaps and hops (only arena walls were met).
- Heroes 1 and 2 as targets: through the model only.
- Real-time behavior under slowdown.

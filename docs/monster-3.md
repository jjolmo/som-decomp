# Chobin Hood (monster id 3) - complete behavior recovered from the ROM (Secret of Mana USA)

Tags: **[V]** executed: the real 65816 code ran in `tools/cpu65816.py` (whole per-frame routine `$C0:B08C` on a ZSNES save state, or single AI handlers), and a model or a decoder was compared with it; **[C]** read from the disassembly, not executed. What is not determined is in section 17 and carries no values. This document follows `docs/rabite.md` (read it first: AI engine, time base, ops shared by all monsters) and only adds what is different for this monster. Numbers come from `data/monster_3.json` (`tools/monster_report.py`).

Addressing: 2 MiB HiROM, `$Cx:xxxx` = file offset `((x-0xC0)<<16)|xxxx`, `$01:xxxx` is the mirror of `$C1:xxxx`, `$02:xxxx` of `$C2:xxxx`. Script addresses ("pc") are offsets from ROM `0x104F15`. No ROM bytes are stored in the repo. Coordinates: world position `obj+2 / obj+4`, screen position `obj+0x20` / `obj+0x22 - obj+0x45` in pixels. Direction codes of commands: 1 right, 2 left, 4 down, 8 up. Name decoded from the ROM text (`tools/names.py`, name block index 0xD2). Seconds are frames / 60.0988; one AI step = 5 frames = 83.2 ms. Why this monster was chosen: `docs/monster-survey.md`.

## 1. Summary

- Object id 3, stat record `0x101C00 + 3 * 29` (level 7, HP 60, Str 12, Agi 2, EXP 12, gold 17, attack row 77), AI script entry pc `0x0261` (609), 183 reachable instructions, 34 opcodes: 30 of the 33 that the Rabite script uses plus **four new ones: 6A, 73, BE, DC** [V: `tools/ai_ops.py --new`, 7,381 + 7,381 + 1,680 placements, 0 mismatches]. (The Polter Chair, `docs/monster-13.md`, adds 34, BE and BF.)
- It is an **archer**. It shoots one arrow with the bow animation of the object (swing animation 1, 40 frames) through the same projectile engine as the heroes' bow; the arrow flies 61 px (50-62 px depending on the direction), the hit test is the engine's 16 x 16 box against the hero's body box. It **keeps its distance**: it retreats while a hero is within 48 px, stands and turns toward a hero at 49-64 px and shoots when its weapon gauge is 0, and advances in 10 px steps while a hero is farther than 64 px, shooting on the way when the hero is in one of its lanes.
- **Spawn**: the first command is a 25-frame leap of 25 px in the spawn facing (animation 0 of the attack table, state 0x40), then it shoots at once (gauge forced to 0).
- **Hit reaction**: hurt pose 105 frames (1.75 s) for a hit of at most max HP / 4 = 15, hurt with a knock-back of 20-40 px and 145 frames (2.41 s) for a bigger hit. **Death**: about 105 frames (1.75 s) of death effect, then the object disappears; 12 EXP, 17 gold, chest 4/64.
- Verified by models: the AI model `tools/ai_vm.py` equals the real handlers in 9,000 random AI steps (0 mismatches); the arrow hit rule equals the observed hero hits in 240 of 240 random placements; all 3,208 pictures of its 212 ripped animations are found in the public sprite sheet (2,688 exactly, 520 under a recolouring that the game's flash palettes need).

## 2. Time base [V]

Same as the Rabite (`docs/rabite.md` section 2): the AI step runs on every 5th frame (12.02 steps/s), movement and animation every frame. Run for 6 s in each monster slot: the AI step frames are all `frame mod 5` = 0 (slot 3), 1 (slot 4), 2 (slot 5) [V, `cadence` in the JSON, 72 steps each]. Every command lasts a multiple of 5 frames. The flag byte of a command (section 6) is a requested duration in frames, rounded up to a multiple of 5.

## 3. ROM record and object entry

| item | value | tag |
|---|---|---|
| monster record `0x101C00 + 87` | level 7, HP 60, MP 0, Str 12, Agi 2, Int 7, Wis 7, evade 0, defense 0, magic evade 0, magic defense 0, type 1, element 0, EXP 12, gold 17, status immunity word 0x1600, attack rows 77 / 77, weapon level 0 | V (`data/monsters.json`, live object after the spawner) |
| attack row 77 (`data/weapons.json`) | hit 99, power 25, crit 0, no status (status chance byte 25 with an empty status word), so **attack = Str 12 + 25 = 37** (`obj+0x198`), accuracy 99 (`obj+0x197`), crit base 0 | V (live object) |
| object-table entry `0x100000 + 3 * 16` | tile source: bank `$D9`, byte offset 0x4D00 (word 308 << 6); piece-list offset 970 (`obj+0x72`); body height 11 (`obj+0x74` low 7 bits, bit 7 set); ordinary script table `$D1:4A34`; attack script table `$D1:54D8`; AI entry pc 0x0261; shadow tables `$D1:4658`; flags byte 0x35; palette 15 colours at `$C8:105A` (`$C8:1000 + 30 * id`) | C (spawn code `$C1:DFCF`, `$C1:E022`), V (values read from the spawned object) |
| drop row `0x103A50 + 15` | chest chance 4/64 (6.25 %), trap threshold 24, contents: 34 gold (89 %) or consumable id 0 (11 %) | V (`data/drops.json`, section 13) |

Tile and palette handling (spawn): `$C1:DFCF` copies the 16-byte entry to `obj+0x70..0x7F`; `obj+0x80` = (word 0 & 0x3FF) << 6 and `obj+0x82` = `$D5 + ((byte 1 >> 2) & 7)` are the tile pool, `$C1:E022` copies the 15 palette colours of `$C8:1000 + 30 * id` into a sprite palette row [C]. The tile uploads, the piece lists and the animation interpreter are those of the heroes (`docs/graphics.md` section 5; the monster's own tables: descriptors `$D1:[$D0:FFF0] + 2 * frame`, piece lists `$D2:[obj+0x72 + 2 * h]`) [V: the pictures drawn by the real code equal the public sheet].

## 4. Script ops, targets and distance classes

The script uses 34 opcodes. Those of `docs/rabite.md` section 3 are unchanged; the new ones, executed one by one by `tools/ai_ops.py --new` (`tools/aidis.py ... --text` prints them):

| op | length | behavior [V] |
|---|---|---|
| 6A off | 2-3 | jump unless the current target is on screen and in a **vertical lane**: `|dx| <= 15` and `|dx| < |dy|` (dx, dy = target minus monster on screen, dy with the jump heights subtracted) |
| 73 off | 2-3 | jump unless the current target is on screen and in a **horizontal lane**: `|dy| <= 15` and `|dy| <= |dx|` |
| BE a b | 3 | if the target is on screen: command C1 turning toward it with a **cardinal** code (right / left when `|dx| >= |dy|` by the sign of dx, else down / up by the sign of dy), animation a, flag b; yield. No target: no-op, continue |
| DC a b v | 4 | `byte(object a, offset b + 0x180) = v`, continue (the script uses `DC 80 6D 00`: own weapon gauge `obj+0x1ED` = 0) |

Checks: 6A and 73 over every (dx, dy) with the monster at screen (128, 112) and the target on screen (7,381 cases each, 0 mismatches against the stated rules); BE over 1,680 placements; DC: gauge 50 -> 0 and -> 7. The lane tests do not look at the distance.

Targets and distance classes are those of `docs/rabite.md` section 4 with two refinements found by running the model against the real handlers (the Rabite section carries the same note): the ops that test the **current** target (4C, 51, 56, 6A, 73, E4, FD, E6, FE, BE) use the weaker test `$C1:0526` (active and on screen; the hero's status word is not looked at), the status test (`0x8460`) belongs to the acquisition ops (A5, B1, B4, B7, 5D, 31-58); and the sum of the squares of the distance is a 16-bit sum, so a hero about 256 px away diagonally can be classified as adjacent (docs/rabite.md section 4) [V].

## 5. The script as a state machine [V]

The model `tools/ai_vm.py` (all ops of the script) was run against the real AI step `$C1:2552` in randomised worlds (random positions in and between the distance bands and near the screen limits, hero statuses, jump heights, facings, gauge 0 or not, three heroes, the RNG routine replaced by a list of bytes that the model consumes in the same order); command bytes, script pointer, call stack, variable 3, target slot, saved position and the number of random bytes drawn were equal in **9,000 of 9,000 steps** (182 of 183 reachable instructions executed; the 183rd, pc 0x027D, is a jump behind an unconditional jump). `tools/monster_model.py ROM STATE 3`.

Structure (pc = script address; the main loop is entered after the entry routine):

### 5.1 Entry (pc 0x0261, subroutine 0x0280)
`E2 00` (pose 0 of the attack table: the **spawn leap**, 25 frames, section 14), acquire a target, set the weapon gauge to 0 (`DC`), call the shot routine (op E8: swing command 02, 40 frames). Then the main loop.

### 5.2 Main loop (pc 0x0264), evaluated after every command
Acquire a target (subroutine 0x6AE1 of the shared library: the first valid hero in slot order within the tightest band <= 16, <= 32, <= 48, <= 64, anywhere on screen; with no valid hero it runs the wander hop and tries again), then by the class of the target:

| target | routine | what it does |
|---|---|---|
| <= 48 px | 0x028D **retreat** | repeat while the target is within 48 px: acquire, then hop **away** (`E6 02 05`: primary 8-way direction away from the target, animation 2, 5 frames = 10 px; `FE 02 05` = the alternate diagonal direction when the position did not change since the last hop, i.e. blocked) |
| 49-64 px | 0x02A1 **shoot** | if the gauge is above 0: turn toward the target (`BE 00 00`, 5 frames). If the gauge is 0: turn (`BE 00 00`, 5 frames), then the shot (E8: swing 02, 40 frames) |
| > 64 px | 0x02B2 **advance** | repeat until the target is within 64 px: if the gauge is 0 **and** the target is in a lane (6A: vertical lane, or 73: horizontal lane) turn toward it (`BE 00 05`, 5 frames) and shoot (E8); then acquire and hop **toward** it (`E4 02 05`, `FD 02 05` when blocked: animation 2, 5 frames = 10 px) |

Nothing is random except the wander hop. A pass that does nothing useful costs exactly one 5-frame turn. [V: model]

### 5.3 Wander (no valid hero), subroutine 0x67DF
The shared routine of `docs/rabite.md` section 5.5: hop length animation 4, 1 or 2 with probability 1/3 each; 1/8 a diagonal direction code, else 7/40 three turn-in-place commands (3 x 5 frames = 15 frames), else a cardinal direction. Durations and distances for this monster (section 6): animation 4 = 60 frames / 30 px, animation 1 = 30 frames / 30 px, animation 2 = 20 frames / 40 px. A diagonal code moves along the horizontal axis only (section 6). Seen in a run with hero 0 disabled (status 0x0020, which the game clears after about 7 s): 14 consecutive wander commands, then the normal loop [V].

## 6. Commands (measured by executing them, `commands` in the JSON) [V]

Frames count from the AI step that issues the command (frame 0); the movement of a hop starts on frame 1 (animation 2, 1) or frame 2 (animation 4); speeds are px per frame, the average is per command.

| command | frames (s) | movement | px/s |
|---|---|---|---|
| C1 anim 0, flag 0 or 5 (turn) | 5 (0.083) | none | 0 |
| C1 anim 1 | 30 (0.499) | 30 px along the facing, 1 px/frame, frames 1-30 | 60.1 |
| C1 anim 2, flag 0 | 20 (0.333) | 40 px, 2 px/frame, frames 1-20 | 120.2 |
| C1 anim 2, **flag 5** (the advance / retreat step) | 5 (0.083) | 10 px, 2 px/frame, frames 1-5 | 120.2 |
| C1 anim 4 | 60 (0.998) | 30 px, 1 px/frame on frames 2-60 (every other frame) | 30.1 |
| 40 pose 0 (spawn leap) | 25 (0.416) | 25 px in the facing, 1 px/frame, jump height 0 -> 15 -> 0 | 60.1 |
| 40 pose 5 | 5 | none | 0 |
| 02 swing (E8) | 40 (0.666) | none | 0 |

- The facing codes 1, 2, 4, 8 move along x (right +, left -) and y (down +, up -); the diagonal codes 5, 6, 9, 10 use the horizontal facing only (a diagonal code gives the same movement as 1 or 2: 5 and 9 = right, 6 and 10 = left) [V: all 8 codes for animations 1, 2, 4].
- **The flag byte (third byte of C1, `b` of E3 / E4 ...) is the requested length in frames**: flag 0 = natural length of the animation; `n > 0` = the command lasts `ceil(n / 5) * 5` frames and the movement of the animation repeats while it lasts (animation 2: flag 1-5 -> 5 frames / 10 px, 6-10 -> 10 frames / 20 px, 20 -> 20 frames / 40 px, 100 -> 100 frames / the wall stops it) [V: flags 1 .. 255 for animation 2].
- Each hop is blocked by walls; the engine stops the movement where the map blocks it (not studied further).

## 7. The shot [V]

Command 02 is issued by op E8 only when the gauge `obj+0x1ED` is 0; the swing is chosen the same way for every distance and facing: **animation 1 of the attack table (state 0x80), 40 frames, no movement** (`swing.by_distance`: 4 facings x 45 distances from 10 to 98 px, always animation 1, 40 frames, displacement 0). The swing script (`$D1:CC0E...`, 4 steps) in frames from the start:

| frames | picture / event |
|---|---|
| 0-4 | bow raised (script step 1), body box 20 x 20 at (+-4, -12) |
| 5-9 | step 2 |
| 10-29 | bow drawn (step 3, 20 frames); **sound 0x47** at frame 10 (bow draw, 0.171 s) |
| 30-39 | release (step 4); **sounds 0x09 and 0x0A** at frame 30 (release 0.298 s and end 0.077 s); **the arrow is launched at frame 30** (script op `0xFB` = `JSL $C2:BF1D`, docs/weapons-ranged.md section 3.1) |
| 40 | state ends, the actor is free |

The monster has **no weapon box** (`obj+0xC0..C3` stays 0 during the swing) so it deals no contact damage; the box at `obj+0xCC..CF` (a third box; purpose not determined) is 8 x 16 at x offset 20 (frames 0-9), 16 (10-29), 12 (30-39), y -12 (mirrored for left).

### 7.1 The arrow (projectile table entry `$7E:D000 + 0x40 * 3 + 0x10 k`) [V]
The shot uses entry 0 of the monster's table (slot 3 -> `$D0C0`). The engine is that of the heroes' bow (kind byte 1, speed byte `0x0E - obj+0x19B` = 14 because the weapon level nibble of the monster is 0; `E061` is set while the arrow lives, which is why a second swing command is refused). Measured flights (offset of the arrow from the monster position; first live frame 30 = launch frame):

| facing | launch offset (x, y) | end offset (x, y) | per-frame x or y displacement | height byte | frames |
|---|---|---|---|---|---|
| right | (+10, -11) | (+61, 0) | +8, +7, +6, +6, +5, +5, +4, +3, +3, +2, +2 | 27 -> 30 -> 16 | live 30-41, then 8 dying frames (freed at 49) |
| left | (-10, -11) | (-61, 0) | mirror | same | same |
| down | (0, -1) | (0, +50) | +8, +7, +6, +6, +5, +5, +4, +3, +3, +2, +2 (y) | same | same |
| up | (0, -21) | (0, -83) | -9, -8, -7, -7, -6, -6, -5, -4, -4, -3, -3 (y) | same | same |

(The y of left and right rises 3 px and falls back: -11, -12, -13, -14, -13, -12, -11, -10, -8, -6, -3, 0.) The range is 61 px (right, left), 51 px (down), 62 px (up) from the launch point; at the end the arrow lands (height byte 16), its dying counter runs 8 -> 1 and the entry is freed.

**Hit rule** (`$C2:C5B4`, docs/weapons-ranged.md section 7.1, applied to a monster-owned arrow against the heroes): in frame `i` the live arrow at its position of the end of frame `i - 1` hits hero 0 when `2 |tx - px| < 16 + tw` and `2 |ty - py| < 16 + th` (px, py = arrow position minus the scroll; tx, ty = hero screen x and y - body height - jump height - 1; tw, th = the hero's body box `E0CA/E0CB`, 8 x 16 for hero 0 standing; both differences also below 96), with the hero fields of the end of frame `i - 1`. Against 60 random hero placements per facing (240 in all; hits 8 / 11 / 4 / 15 for right / left / down / up) the model and the real engine agreed in **240 of 240** [V, `arrow.validation`]. The damage lands 0-5 frames after the test frame (the hero's combat tick); in the validation set the HP drop and the test frame coincided in the cases traced. A hero is protected while its body box is empty (docs/glove-attacks.md section 2.6) and while it is in its hurt state.

**Damage and hit chance**: the arrow resolves like any monster attack (`docs/rom-combat.md` section 4: attack 37, accuracy 99, no crit, element none). Against a hero with evade 0 and defense 0 the damage was 37 (27 of 38 hits) or 38 (11 of 38) [V, 240 placements]; against the save state's hero (defense 41, evade 95) it is lower; use the formula of section 4 of `docs/rom-combat.md`.

**Cooldown**: the weapon gauge is loaded only when the **arrow is gone**, not when the swing ends: `(100 - Agi) / 2 + 50 = 99` frames (formula `$C0:F937` [C]); measured: gauge 98 at frame 51 after the start of the swing (the arrow was freed at frame 50), 0 again at frame 150. A swing command (E8 with gauge 0) issued while the arrow still lives is **refused**: the command occupies 5 frames and nothing happens [V: seen at 225 in the 100 px run]. So the full cycle of "stand and shoot" is 150-155 frames: 40 swing + 10 + 99 = 155 frames = **2.58 s**.

## 8. State machine in seconds (summary)

| situation | cycle |
|---|---|
| spawn | pose 0 leap 0.416 s, then at once the shot (swing 0.666 s) |
| hero 49-64 px (on screen) | turn 0.083 s per AI step while the gauge is above 0; at gauge 0 turn 0.083 s + shot 0.666 s; one shot every **2.58 s** (155 frames) |
| hero <= 48 px | retreat steps `E6 02 05`: 10 px in 0.083 s (120 px/s) per step until the hero is more than 48 px away (a hero at 24 px: 2 steps = 0.17 s), then as above |
| hero > 64 px | advance steps `E4 02 05`: 10 px per 0.083 s (120 px/s) until within 64 px (hero 100 px away: 4-5 steps = 0.33-0.42 s); on the way a shot (turn 0.083 s + 0.666 s) whenever the gauge is 0 and the hero is in a lane |
| no valid hero | wander commands (turn 0.083 s, hops 0.499 / 0.333 / 0.998 s) |
| hit by a hero | hurt 105 frames (1.75 s) if the damage is at most 15, else knock-back and 145 frames (2.41 s); the script then restarts its main loop |
| dead | about 105 frames (1.75 s) effect, then the object is removed |

Runs with the hero 40-100 px away (`trace` in the JSON, 14 s each): the monster shot at frames 25, 180, 335, 490, 645, 800 (every 155 frames) while it stood 49-64 px from the hero; with the hero inside 48 px it first made 1-4 retreat steps; with the hero off the line it still turned toward it and shot (the shot is always fired along the cardinal direction toward the hero, so it misses unless the hero is within about 12 px of that line, see 7.1).

## 9. Hit reaction [V]

The hit resolver `$C0:4F7B` writes the pending damage; the combat tick applies it and `$C0:4EBC` chooses the reaction for an ordinary monster [C, V]:

- reaction code **8** (hurt animation 0x88) when the damage is at most max HP / 4 (15 for this monster), code **9** (0x89, knock-back) when it is larger [V: damage 2 .. 15 gave 0x88, 19 .. 46 gave 0x89];
- status low bits `obj+0x190`: 1 for code 8, 2 for code 9, with the countdown `obj+0x1B4` = max(6, damage >> 3) combat ticks (6 for every non-lethal hit of this monster: 6 ticks = 30 frames, shorter than the animation) [V, C];
- hit sound **0x35** (parameter 0x0F, pan from the screen position) at the frame of the hit [V].

| reaction | animation (state 0x40) | frames to the first AI step | movement |
|---|---|---|---|
| code 8 (small hit) | 0x88 = ordinary animation 8, one picture, 25 frames | 105 (1.75 s) | none |
| code 9 (big hit) | 0x89 = ordinary animation 9, 75 frames | 145 (2.41 s) | knock-back from frame 6: 1 px/frame on frames 6-10, then 2 px/frame: **opposite to the facing, 40 px for the side facings, 30 px (up-facing, pushed down) and 20 px (down-facing, pushed up)**; shortened by a wall |

The AI step resumes `max(105, animation frames + 70)` frames after the hit in the four cases measured (hurt 25 / 75 frames -> 105 / 145); why 70 was not determined (section 17). The hurt overlay of the damage number (`obj+0x60 = 0x40`) runs frames 6-103 after the hit. A pending-damage hit that does not come through the resolver (`obj+0x1F1` written directly) gives code 8, no stun counter and the same 105 frames [V].

## 10. Death [V]

HP 0 at the damage frame: status 0x8000, the object id byte (`obj+0x180`) becomes 0xFF, the hit sound 0x35 and the death sound **0x97** (0.918 s) are requested at the frame of the kill, the death effect plays (blue flash growing to four puffs and the skeleton, then the bones: 9 pictures per facing), the damage counter overlay runs frames 5-102 and the object is **removed about 105 frames (1.75 s) after the kill** (active until frame index 104 of the live run, 107 frames in the ripper's count). The removal is done by the corpse's AI script: with the AI step switched off the object stays [V]. Rewards paid at the kill: **12 EXP** to every living hero and **17 gold** (`obj+0x1C8`) [V: hero EXP 2,882,779 -> 2,882,791; gold `$7E:CC6A` +17, both seeds].

## 11. Drops [V]

Drop row 4 / 48 / 184 / 34 / 64: chest probability 4/64; trap threshold 24 (a hero with Agi below 24 triggers the trap with probability 1/2); chest class from the level (L < 10: classes 2, 3 or 4); contents 34 gold with probability 57/64 and consumable id 0 with 7/64. The real death routine `$C0:4203` was run on 300 RNG states (27 chests: classes 2, 3, 4 = 12, 9, 6) and the real content routine `$C8:E12C` on 300 states (274 x 34 gold, 26 x item byte 0x40) [V]. The complete drop model (every id) is in `docs/rom-combat.md` section 13.

## 12. Sound ids per action (rendered in `docs/audio.md`) [V]

| action | id (duration s) | when |
|---|---|---|
| bow draw | 0x47 (0.171) | swing frame 10 |
| arrow release and end | 0x09 (0.298) and 0x0A (0.077) | swing frame 30 |
| monster hit by a hero | 0x35 (0.277) | the hit frame (parameter 0x0F) |
| death | 0x97 (0.918) | the kill frame |
| spawn, hops, turns, hurt pose | none | no sound request was seen |

## 13. Animations and graphics [V]

Tables (bank `$D1`): ordinary states `$D1:4A34` (21 animations, scripts at `$D1:9B81...`; this table is shared with ids 2, 6, 11, 12, 14, 17, 28, 31, 37, 42, 52, 65, 67, 80), attack states `$D1:54D8` (5 animations; shared with id 28). An animation id `a` is played from the table `$D1:[table + (a * 3 + facing) * 2]` with facing 0 up, 1 down, 2 side (the left side is the mirrored side script); the object state decides the table: state 0 uses the ordinary table with the full id, a non-zero state with an id below 0x80 uses the attack table, with an id of 0x80 or more the ordinary table with `id & 0x7F` (`$C0:F550-F585` [C]). So a pose command `40 n` plays attack animation n, a swing plays attack animation n in state 0x80, a hit plays ordinary animation 8 or 9 (ids 0x88, 0x89), a hop command C1 plays ordinary animation n.

Frames per animation (down facing; the other facings have the same length; durations are multiples of 5 frames; "pictures" = distinct pictures of the animation over the 4 facings, `ripped` in the JSON):

| action | table, id | frames (s) | notes |
|---|---|---|---|
| turn / stand | ordinary 0 (static), 3 | 5 per command | one picture per facing |
| hop 30 px | ordinary 1 | 30 (0.499) loop | walk |
| dash | ordinary 2 | 20 (0.333) loop | the advance / retreat step plays 5 frames of it |
| hop 30 px, anim 4 and 5 | ordinary 4, 5 | 60 (0.998) | |
| spawn leap | attack 0 | 25 (0.416) | state 0x40 |
| shot | attack 1 (state 0x80) | 40 (0.666) | bow pictures, arrow launched at frame 30 |
| attack 2, 3, 4 | attack 2 / 3 / 4 | 100 / 70 / 20 | attack 2 is the casting flash (palette cycle); 3 and 4 are other states of the shared table; none is used by this script |
| hurt | ordinary 8 | 25 (0.416), one picture | played as 0x88 |
| knock-back | ordinary 9 | 75 (1.248) | played as 0x89 |
| ordinary 6, 7, 10-14 | | 25 / 60 / 25 / 40 / 25 / 25 / 25 | not used by this script |
| ordinary 15, 16, 17 | | 115 / 115 / 125 | tumbling / flying poses of the shared table, not used |
| ordinary 18, 19, 20 | | 10 each | single poses (19 is drawn with a changed palette) |
| death | object 0xFF effect | 105-107 (1.75-1.78) | 9 pictures per facing |

Pieces and tiles: the body is 4 sprite pieces (16 x 16: tiles 64 / 66 / 68 / 70, palette row 5) up to 13 in the large poses, plus the ground shadow (tile 0, palette 1, at -8, -8); the arrow is tile 232 (palette 4) drawn through the projectile table in 3 orientations (the up/down arrows are flips). The body height is 11 px above the foot point. Per animation the JSON of the ripper carries the foot origin, the per-picture durations in video frames and seconds, the actor displacement per frame, the weapon / body / third box per frame, velocity, sounds and the projectile pieces.

**Ripped animations**: `tools/rip_monster_anims.py ROM STATE OUTDIR 3` runs the real code and writes, per animation set (`ord NN`, `atk NN`, `hurt NN`, `swing NN`, `death`) and facing (up, down, right, left), RGBA PNGs with transparent background (equal size per animation, foot point = `origin` in the JSON) and one JSON per animation with the frame durations, plus `index.json` and the arrow pieces: **212 animations, 3,208 distinct pictures** (staged in `rom_gfx/monsters/03_chobin_hood/`, outside this repository). Validation with `tools/validate_monster_gfx.py` against the public sheet "Chobin Hood & Robin Foot" and the "Death Effects" sheet (5-bit colours, mirrored and flipped orientations): **2,688 pictures found pixel for pixel, 520 found only under a consistent recolouring** (the casting flash of attack animation 2 / swing 2, 168 of 200 pictures, the hit flash and the tumbling poses 9, 15-17 and 19, which the game draws with changing palettes), **0 not found** (the 36 death pictures, 9 per facing: the first of each facing is the live monster, the rest are looked up in the effects sheet and found).

## 14. Spawn [V]

`$C0:DE3B` creates the actor, `$C1:25B6` sets the script pc to 0x0261 and clears the variables. The first AI step runs on the spawn frame: pose 0 (state 0x40, animation 0 of the attack table) is a **leap of 25 px in the facing direction** with a jump height of 15 px at the top, 25 frames, no sound; the spawn facing is the one of the map-object record (down in the harness). The shot follows at frame 25 (gauge forced to 0 by the script).

## 15. What the Chobin Hood does, for an implementation

1. At the spawn leap 25 px along the facing in 25 frames (arc 15 px), then shoot once toward the nearest valid hero in the cardinal direction.
2. Every 5 frames (one AI step): pick the nearest valid hero (<= 16, 32, 48, 64 px bands, then anywhere on screen). Distance <= 48: step away 10 px (2 px/frame, 5 frames) along the 8-way direction away from the hero (horizontal part only for diagonals). 49-64: face the hero (cardinal) for 5 frames, shoot when the gauge is 0. > 64: step toward the hero 10 px per 5 frames; shoot (after a 5-frame turn) when the gauge is 0 and the hero is in a lane (|dx| <= 15 with |dx| < |dy|, or |dy| <= 15 with |dy| <= |dx|).
3. The shot: 40 frames; arrow launched at frame 30 at (+-10, -11) (down (0, -1), up (0, -21)), steps 8 7 6 6 5 5 4 3 3 2 2 px per frame, lands after 61 px (51 down, 62 up), lives 8 more frames; hits the hero when the boxes of 7.1 overlap; attack 37 (Str 12 + 25), accuracy 99. The gauge is loaded with 99 frames when the arrow has been freed.
4. A hit: sound 0x35; small hit (<= 15): 105 frames hurt; bigger: knock-back (20-40 px) and 145 frames.
5. Death: about 105 frames, 12 EXP, 17 gold, 6.25 % chest (34 gold or consumable 0).

## 16. Tools and how the numbers were obtained
- `tools/ai_ops.py ROM STATE --new`: the four new ops.
- `tools/ai_vm.py`, `tools/monster_model.py ROM STATE 3`: the AI model and its comparison with the real handlers.
- `tools/monster_report.py ROM STATE 3 data/monster_3.json --only record,model,cadence,commands,swing,arrow,reaction,death,drops,trace`: commands, shot timeline, arrow flights and hit validation, reaction table, death, drop checks, closed-loop runs.
- `tools/rip_monster_anims.py`, `tools/validate_monster_gfx.py`, `tools/compare_sheet.py`: the pictures.
- Save state: the map-246 arena state of `docs/rom-combat.md` section 19 (late-game heroes; hero 0 pinned, heroes 1 and 2 inactive). Hits were made through `$C0:4F7B` with hero 0's attack byte, accuracy 99 and no `E1E6` bonus set by the harness.

## 17. Open questions (no values are claimed)
- The purpose of the "third box" `obj+0xCC..0xCF` of the shot (it moves 20 -> 16 -> 12 px in front of the monster).
- Why the AI resumes `animation frames + 70` frames after a big hit (and 105 frames after a small one); the guard that holds the AI step while the damage overlay and the hurt scripts run was not traced.
- The knock-back of the up-facing case (30 px) was seen on open ground in one of four arena places; the other three were shortened by walls or objects; the down-facing 20 px and the side 40 px were identical in all four places.
- Animations 2, 3, 4 of the attack table (casting flash) and ordinary 6, 7, 10-17 are shared with Robin Foot (id 28); which of them this monster could use outside its script was not examined. The commands 0x43 / 0x44 are not issued by this script.
- Terrain collision of hops and arrows (only walls of the arena were met).
- What an arrow does when it meets a wall (the landing test `$C2:C183`).
- Hero 1 and 2 as targets: the slot-order rule is from the code and from the model; runs with more than one active hero were made only through the model.
- Real-time behavior under slowdown.

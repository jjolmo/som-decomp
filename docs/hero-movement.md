# Secret of Mana (USA) - how the heroes move

Companion of `docs/rom-combat.md`. Tags: **[V]** = measured by running the real ROM routines in the interpreter (`tools/hero_movement.py`: pad bytes in, hero position out, frame by frame); **[C]** = read from the disassembly, read, not executed. What is not known is in section 12 and carries no values. Numbers: `data/hero_movement.json`. Object fields are offsets inside the 0x200-byte actor record (`$7E:E000 + slot*0x200`; slots 0-2 are the heroes), as in `docs/rom-combat.md` section 1.1.

## 0. Summary

| quantity | value | tag |
|---|---|---|
| position unit | whole pixels, words `E002` (X) and `E004` (Y), no sub-pixel part | [V] |
| frame clock | 60.0988 Hz; movement runs once per frame | [C], section 1 |
| walking speed | 2 px per frame on each axis the pad presses = **120.20 px/s** | [V] |
| diagonal | both axes 2 px per frame, **not normalised**: 2.83 px per frame = **169.99 px/s** along the diagonal | [V] |
| running (A button) | **3 px per frame** on each pressed axis = **180.30 px/s**, diagonal (3,3) = 4.24 px per frame = **254.98 px/s**; starts on a new press of A, direction locked, ends when A is released or a wall stops it (section 4) | [V] |
| weapon charging | **1 px per frame** (60.10 px/s) per axis from the third frame the attack button is held; the first two frames run at 2 | [V] |
| statuses 0x0004 and 0x0400 | **1 px per frame** per axis | [V] |
| statuses 0x0020, 0x0040, 0x0100, 0x4000, 0x8000 | no walking at all | [V] |
| acceleration | none: 2 px (or 3 when running) on the first frame, 0 on the first frame after release | [V] |
| equipment, level, Agi | no effect on any speed; Agi only sets the length of the weapon gauge `E1ED` loaded after a run or a swing (section 4) | [V] |
| wall collision | per axis, tile based, hero box about 13 px wide and 9 px tall around (x, y) | [V] |
| knockback when hit | opposite to the facing, 55 px in 40 frames (3 px for 5 frames, 2 px for 5, 1 px for 30) = 0.67 s | [V] |
| facing on a diagonal | the horizontal direction wins | [V] |

px/s = px per frame x 60.0988: 1 -> 60.10, 2 -> 120.20, 3 -> 180.30, diagonal (2,2) -> 169.99, diagonal (3,3) -> 254.98, diagonal (1,1) -> 84.99.

## 1. The clock
- Region byte of the header (`$FFD9`) = 1 (USA, NTSC) [C].
- The main loop `$C0:B070-B08A` runs one iteration per NMI: it sets `$EC` bit 0, then spins on `BIT $EC` until the NMI handler clears it; the NMI handler (vector `00:0100`, a `JML $00C0A8` stub in RAM) increments the frame counter `$F4` and ends with `LDA #$FF / TRB $EC`. Every iteration calls the input handler `$C0:B69C` and the movement routine `$C0:D5C0` exactly once (`$C0:B0AF`, `$C0:B0B2`) [C].
- So the unit of movement is one NMI. NTSC with 262 lines of 1364 master clocks at 21.477272 MHz gives 60.0988 Hz, the figure used in `docs/rom-combat.md` 1.3. The slower 12.02 Hz "tick" of that document is the combat tick (`$56` cycles 0..4); movement is not on it [C].

## 2. The pipeline per frame [C, each stage also executed]
1. **Input handler `$C0:B69C`** reads the three pad pairs `$42/$43`, `$44/$45`, `$46/$47` (low byte, high byte of a pad) and the binding bytes `$D9/$DA/$DB` (bit 0 = hero 0, bit 1 = hero 1, bit 2 = hero 2; 0 = nobody; bit 7 set = pad inactive). The high byte holds Right (bit 0), Left (1), Down (2), Up (3), Start (4), Select (5), Y (6), B (7); `$C0:B710` turns the d-pad bits into the **velocity word** `E006` of the hero: low byte = X code, high byte = Y code, each `0x00` (still), `0x02` (+2 px) or `0x82` (-2 px) [V: all 8 directions]. The velocity bytes are sign-magnitude: bit 7 = negative, bits 0-6 = pixels per frame. The word is written only when the hero's `E01C | E060 | E00A` are all zero (not attacking, no state flag, no knockback/forced move) [V, `blockers` in the json]; otherwise `E006` keeps its value. Before that, `$02:B6CD` zeroes the pad bytes of a hero whose status word has any bit of `0xC160` (0x8000, 0x4000, 0x0100, 0x0040, 0x0020) [C].
2. **Movement `$C0:D5C0`** runs the three heroes (`$C0:D5ED`, slots 0, 1, 2) and then every other object (`$C0:D1FE`, slots 3 and up). Per object: `$1E,$1F` = `E006,E007`; the ground effect and the slowdowns of section 5 modify `$1E,$1F` (`$C0:D2E0`, `$C0:D482`); the party limit of section 9 (`$C0:D6C8`) and the tile collision of section 7 (`$C0:D74F`) may shrink them; `$C0:D890` adds `+-(v & 0x7F)` to `E002`/`E004` (wrapping at the map size `$C0`, `$C2`) [V].
3. An object with `E036 != 0` moves only on every `(E036+1)`-th call (`E037` is the down-counter) [C]; heroes have 0.

## 3. Speeds [V]
`data/hero_movement.json` `walk`: for each of the 8 directions the per-frame displacement over the first frames (all identical from frame 1).

| pad | displacement per frame | facing `E010` | animation `E011` |
|---|---|---|---|
| right | (+2, 0) | 0x02 | 1 |
| left | (-2, 0) | 0x82 | 1 |
| down | (0, +2) | 0x01 | 1 |
| up | (0, -2) | 0x00 | 1 |
| up+right / down+right | (+2, -2) / (+2, +2) | 0x02 | 1 |
| up+left / down+left | (-2, -2) / (-2, +2) | 0x82 | 1 |

- **No acceleration**: the first frame already moves 2 px; the first frame after releasing the pad moves 0 (`release_after_10_frames` = 2, 2, 0, 0, ...). The velocity fields `E008`/`E045` (a per-object acceleration accumulator, `$C0:D2C2`) are 0 for a hero.
- **Diagonal**: each axis is handled on its own, so a diagonal covers 2 px on both axes per frame, 41% faster along the diagonal than along an axis. There is no divisor.
- **Buttons**: with the right direction held, Start, Select, Y, X, L or R change nothing (2 px per frame); B starts the charge (section 4); A starts a run (section 4). The same speeds were measured for all three heroes in six save states (levels 65-70, different equipment), with Agi 1..99, level 0..98 and armor ids changed by hand: the velocity code of `$C0:B710` has no stat input [V].
- **Facing** `E010` is set from the velocity word each frame: the X code decides if it is non-zero (0x02 right, 0x82 left), otherwise the Y code (0x01 down, 0x00 up). A diagonal therefore faces left or right [V].
- `E011` (animation/state code, `$C0:D482`): 1 = walking at less than 3 px per frame, 2 = 3 px or more, 4 = slowed or charging, 3 = standing ready (weapon gauge empty), 0 = standing otherwise [V].

## 4. Running (A button) and weapon charging [V]

### 4.1 Running
The low pad byte holds A (bit 7), X (6), L (5), R (4). `$C0:93F7-9411` (the pad compose step of the frame) keeps a press-edge latch `$CC` (bit 7 = A newly pressed, bit 3 = B, bit 6 = X, bit 5 = L, bit 4 = R, bit 2 = Y, bit 1 = Select, bit 0 = Start) [C]. In `$02:B6CD` (called through `$02:B665` from `$C0:B799` every frame for each controlled hero) a run starts when the A edge latch is set, the hero is not charging (`E01A | E01B == 0`), and `E1ED | E01C | E00A == 0`, `E060 == 0` and no status of the mask `0xC160` [C, V]: the latch is consumed, `E063` bit 0 and `E011 = 2` are set and every non-zero velocity component is replaced by **magnitude 3** (sign kept); with no pad direction the facing `E010` is used (0x00 -> (0,-3), 0x01 -> (0,+3), 0x02 -> (+3,0), 0x82 -> (-3,0)). While `E011 == 2` and A stays held, `$C0:B761-B768` returns before it rewrites `E006`, so the velocity is **kept: the direction cannot be changed during the run** (pressing up while running right keeps running right) [V].

Measured (`dash` in the json; the latch is set by the harness for the frame of the A press, as the pad compose step would):
- all 8 directions: from (2,0), (-2,0), (0,2), (0,-2), (2,-2), ... to (3,0), (-3,0), (0,3), (0,-3), (3,-3), ... on the frame of the press; the run goes on at 180.30 px/s per axis for as long as A is held (checked for 30 frames);
- from a standstill facing down: (0,+3) per frame;
- **end**: releasing A, or a wall that stops the step (the velocity becomes 0 and the run does not restart while A stays held; a new press is needed). On release (`$C0:B77B-B78A`) the recharge gauge `E1ED = (100 - Agi) / 2 + 50` frames is loaded (99 for Agi 1, 75 for Agi 50, 50 for Agi 99; decremented once per frame by `$C0:EB4F`, `docs/rom-combat.md` 4.3); a new A press is ignored while `E1ED` is non-zero (the harness does not run the decrement) [V]. A swing is **not** blocked by `E1ED`: the swing start `$C0:B29F` does not read it, and the full-frame runs of `docs/glove-attacks.md` (sections 2.3 and 2.4) started swings with `E1ED` = 59 [V there; the swing path was not re-run for this document]. The gauge only weakens the damage of such a swing and keeps a charge from starting (`docs/rom-combat.md` 4.2-4.3);
- not possible while charging (`E01B != 0`, or `E01A != 0`; the speed is then 1, section 4.2); with the slow statuses 0x0004/0x0400 the run is 1 px per frame (section 5).

### 4.2 Weapon charging
The attack button is B (bit 7 of the high pad byte, `$C0:B7BD`). While it is held `$C0:B330` advances the gauge word `E01A/E01B` (`docs/rom-combat.md` 11.3: counter `E01A` 0..44 every second frame, stage `E01B` after 45 counts). In `$C0:D339-D357`, whenever `E01B != 0` or `E01A >= 2`, every non-zero velocity component is replaced by **magnitude 1** (sign kept):

| frame of holding B (right held) | 1 | 2 | 3 and later |
|---|---|---|---|
| displacement | 2 | 2 | 1 |
| `E01A` after the frame | 1 | 1 | 2, 2, 3, 3, ... |

So charging halves the walking speed to 60.10 px/s per axis after the gauge has counted twice (3 frames = 0.05 s), for every stage, and the animation becomes 4. The gauge needs a weapon level above 0 and `E061 == 0`. Releasing B ends the charge (`$C0:B21C` clears `E01A`) and the speed is 2 again. A swing sets `E01C` (0x20 or 0x80) and `E006 = 0`: the d-pad is ignored until the animation clears `E01C` [C; with `E01C` forced non-zero no movement happens, [V]]. The weapon-recharge gauge `E1ED` does **not** change the walking speed (it only blocks a new run; a swing is not blocked, `docs/glove-attacks.md` 2.4) [V].

## 5. Statuses and ground [V]
Walking right with the status word `E190` forced to a single bit and the timers held (`status_words` in the json; the hero is human controlled):

| bit(s) | displacement per frame |
|---|---|
| 0x0004, 0x0400 | **1** (both axes; also a run, 3 -> 1) |
| 0x0020, 0x0100, 0x4000, 0x8000 | 0 (pad masked) |
| 0x0040 | 0 while the bit is set (the status is dropped by the tick, then 2) |
| 0x0001, 0x0002, 0x0008, 0x0010, 0x0080, 0x0200, 0x0800, 0x1000, 0x2000 | 2 (no effect) |

The slowdown is in `$C0:D531-D57C` [C]: for `E190 | E191` bit 2 (the words 0x0004 and 0x0400) each non-zero component whose magnitude is at least 2 becomes magnitude 1; a dead hero (0x8000) has components of 3 or more reduced to 2. Spell 02 Speed Down inflicts 0x0004 (`docs/spells-non-damage.md`), so in this game it halves the walking speed and also lowers accuracy (`docs/rom-combat.md` 4.2); 0x0400 is toggled by consumable id 10 (section 16 there). Balloon (spell 16, 0x0100) and the stone/ice-like words 0x0020, 0x0040, 0x4000 stop the walk; Sleep Flower (0x0010) and Silence (0x0080) do not [V].

**Ground type** (byte 2 of the 4-byte tile attribute entry under the hero, copied to `E048`; `$C0:D359-D3E0`) [V, `ground_types`]:
- `0x30-0x3F` moving floor: the low nibble `k` adds `(k >> 2) + 1` px per frame (1..4) to one axis, direction `k & 3` = 0 up, 1 down, 2 left, 3 right, **only while the hero is walking** (idle: no drift). Example 0x30: walking right gives (+2, -1) per frame; 0x3C: (+2, -4).
- `0x20-0x2F`: bit 1 of the low nibble selects an axis; a hero walking along it loses 7 of every 16 frames (the effect depends on `$F4` bit 2), the other axis is deflected by 8 px per 16 frames; the sound 0xEF is played. Its purpose was not determined.
- `0x40-0x4F`, `0xD0-0xD2`: no effect on walking in this harness.

## 6. Equipment
No armor, weapon or accessory changes the speed: `$C0:B710` and the run start write constants, nothing in the movement path reads a stat, and the experiments above gave identical speeds with armor ids 0, 20/41/62 and 5/25/45 [V]. The only stat that matters is Agi, and only for the length of the gauge `E1ED` loaded after a run or a swing. No spell or item raises the walking speed; the speed changes are the run (4.1, up to 3), charging (4.2, down to 1) and the statuses 0x0004/0x0400 (5, down to 1).

## 7. Collision with the map [V]
The map is a 16 x 16 pixel tile grid: tile ids in `$7F:0000` (128 ids per row, `y>>4` rows), and a 4-byte attribute entry per id in `$7F:B800 + id*4` (bytes b0, b1, b2, b3; objects with `E00B` bit 7 use the second set `$7F:4000` / `$7F:BC00`, not tested). The probe code is `$01:B93E`, `$01:B9EA`, `$01:BAE2` through `$C0:D74F` [C].

**Which tiles stop the hero** (b0 sweep over 0..255, b1 and b2 sweeps, hero walking right into a block of tiles):
- `b0 & 7 == 3` stops the hero from every side (32 of 256 values: 3, 11, 19, ..., 251) [V]. b1 has no effect on walking (256 values tried). `b0 & 7` of 1 or 2 are direction-dependent in the code (compared with the low bits of `E00B`), 4-7 and 0 let the hero through; bit 3 (0x08) toggles the layer flag `$1B` of the hero and made the hero cover 6 px less in the test (not characterised).
- `b2` values 0x14-0x17 and 0x1C-0x1F are partial collision shapes (`b2` high nibble 1 and low three bits 4..7; the code compares them with the shape cases 4-9 of `$01:BE15`/`$01:BC37`); whether they stop, slow or divert the hero depends on where inside the tile it stands. In the sweep of the json (one start position, walking right) 0x16 and 0x1E stopped the hero and 0x15, 0x17, 0x1D, 0x1F slowed or diverted it; the other values changed the position only through the ground effects of section 5.

**Hero box** (the walls were a column or row of solid tiles; hero started at even and odd pixel positions, `wall_box` in the json):

| moving | the step is refused when | stop distance from the wall edge (even / odd start) |
|---|---|---|
| right | the tile at `x_new + 6` is solid | 8 / 7 px before the edge |
| left | the tile at `x_new - 6` is solid | 6 / 7 px after the edge |
| down | the tile at `y_new + 4` is solid | 6 / 5 px before the edge |
| up | the tile at `y_new - 4` is solid | 4 / 5 px after the edge |

(`x_new`, `y_new` = the position after the 2 px step.) So the leading edges are x +6 / -6 and y +4 / -4: a box 13 px wide and 9 px tall around the hero position.

**Other axis** (one solid tile, 16 px, hero walking at it; `single_tile_walk_*` in the json):
- walking right/left: contact when the hero's y is within -4 .. +19 of the tile's top row (24 px); the hero is stopped when y is within +4 .. +12 of the tile top, and is **deflected** otherwise;
- walking down/up: contact when x is within -6 .. +21 of the tile's left column; stopped when x is within +2 .. +14; deflected otherwise.

**Deflection (corner slide)**: when only one end of the leading edge touches a tile, the hero is moved sideways, away from the tile, by 2 px per frame (the walk component is lost) until the contact ends, then it continues: e.g. walking right at y = tile top + 3: 6 frames of (+2, 0), then 4 frames of (0, -2), then (+2, 0) again; at y = tile top + 13 the nudge is (0, +2) [V]. A diagonal that is refused falls back to the **X component alone**; if that is refused too, to the **Y component alone**; if both are refused the hero stays (`$01:BBFB-BC2B` [C]; [V]: wall on the right with up+right gives (+2,-2) until the contact, then (0,-2); wall above gives (+2,-2) until the contact, then (+2, 0); wall right and above stops after sliding). The box is the same for all three heroes; the half size is taken from `E089 & 3`: `$1A = ((E089 & 3) + 1) * 4 + 6` = 10 for a hero [C].

Movement is also refused or cancelled in these cases [C]: `$01:B93E` rejects a destination tile with attribute b1 bit 6 (0x40) or b1 bit 4 (0x10) for non-player objects; heroes ignore the party-order check when `$D0` (event mode) is non-zero.

## 8. Does anything else change the position?
The hero is not moved by anything but `E006/E007` (input, knockback script, AI partner steering) [C]. Positions wrap at the map size (`$C0`, `$C2`).

## 9. Party limit (leader versus partners) [C, V]
`$C0:D6C8` (called from `$C0:D65D`) keeps the party inside the screen window: with the camera position `$16/$18` (`$A8/$AA` copies), the screen-relative position of an object must stay inside x in `[0x38, 0xC8)` and y in `[0x48, 0xB0)` (constants of `$C0:D962`, `$C0:D9E8`, `$C0:D9AE`, `$C0:DA34`). When a human-controlled hero's step would leave that window, the step is cancelled on that axis unless every partner would stay inside the window after the same shift (`$C0:D9AE`, `$C0:DA34`). Measured with a fixed camera: a leader at screen x 0xC0 walking right with the partner at screen x 0x80 walked on freely; with the partner at 0x38-0x40 it stopped at screen x 198-206 (it stopped after 7 steps for a partner at 0x40: leader x = partner x + 0x8E) [V]. A non-human hero loses the component instead. The exact rule was not fully decoded (section 12).

## 10. Knockback when a hero is hit [V]
A damaging hit sets the status word low bits and `E1E5` (`$C0:4EBC`, `$C0:4F6E`); on the hero's next combat tick the object enters animation state `E011 = 0x8D` with `E01C = 0x40`, and the animation script engine (`$01:D6C4` writes `E007`) writes the knockback velocity into `E006/E007` [C, trace of the writes]. Measured by hitting a hero through the real hit routine (`E059` bit set, monster attacker) and watching the position (`knockback` in the json):

| property | value |
|---|---|
| direction | **opposite to the facing `E010`** at the time of the hit (facing up -> pushed down, right -> pushed left, ...); the attacker's position does not matter (16 facing x attacker combinations, all the same) |
| speed profile | frames 1-5: 3 px per frame, frames 6-10: 2 px, frames 11-40: 1 px (writes of the velocity code 0x83, 0x82, 0x81, 0x00 at script steps 5 and 10 and 40 frames after the start) |
| distance | 55 px (15 + 10 + 30) |
| duration | 40 frames of motion = 0.666 s; the motion starts at the hero's combat tick, which comes within 5 frames after the hit (the tick runs when `$56 == 3`) |
| dependence | none on the damage (1, 10, 60, 200), the attacker slot, or the pad: pressing a direction during the knockback has no effect (`E01C` is non-zero); a hero that was walking has both velocity components replaced (only the component along the facing is non-zero) |
| control | the d-pad is ignored while `E01C` / `E060` are non-zero (animation-driven, so its length was not measured) |
| walls | the knockback uses the same collision as walking (section 7) |

In 3 px per frame terms the first five frames are 180.3 px/s, then 120.2 px/s for five frames, then 60.1 px/s. A monster standing in the path stopped the hero about 9 px before its centre in one of two states tried (section 12).

## 11. Partners (AI heroes) [V observed, rule not decoded]
When the party is spread out the partners move with the same mover: velocity words seen were 0x0300 (3 px per frame), 0x0200 (2) and 0x0100 (1) along one axis, i.e. 180.3, 120.2 and 60.1 px/s, with the animation code `E011 = 2` at 3 px per frame. They start following after about 20 frames and walk at 2 px per frame (`$C0:EF8A`, `$C0:F000`, steering in `$C0:F124` and `$01:B729` write `E006`). The distance rule that chooses 1, 2 or 3 was not decoded.

## 12. Open questions (not determined)
These are unknown; no values or formulas are claimed for them.
1. The rule that chooses the speed (1, 2 or 3 px per frame) and the path of AI-controlled partners (`$C0:F124`, `$01:B729`).
2. Pushing: no state, speed or animation of "pushing" an object was found in the movement path; a blocked hero simply moves 0 px and takes `E011` 0 or 3. Whether some object kind is pushable through another code path was not searched.
2b. Where the press-edge latch `$CC` is combined with the real controller read, and what else consumes the other latch bits (the B edge `0x08` is consumed by `$C0:B7AC` for the swing).
3. The meaning of tile attribute bytes beyond the solid code `b0 & 7 == 3`, the moving floor and the partly blocking `b2` shapes: `b0 & 7` = 1, 2 (direction dependent), `b0` bit 3 (layer flag), `b1`, the shape cases 4-9 of `$01:BE15` / `$01:BC37`, ground types 0x20-0x2F and 0x40-0xDF, and the second tile set (`E00B` bit 7).
4. The exact party-limit rule of section 9 (what each of `$C0:D9AE`, `$C0:DA34` compares) and how it interacts with the camera scroll.
5. The animation script data that produces the 5 / 5 / 30 frame steps of the knockback, and what makes a monster block the knockback in one save state (measured in the state of the arena tests but not in a second one) while the plain walking collision with monsters was not tested.
6. The routine that fills the pad bytes `$42-$47` from the controller registers (the harness writes them), the swing/attack immobilisation length (`E01C` is cleared by the animation), and the movement of heroes on the second tile layer.
7. Hero speeds in PAL or other regions: only the USA ROM was examined.

## 13. Reproduce
```
python3 tools/hero_movement.py "$R" "$S" data/hero_movement.json     # ~2 minutes; S = any map save state
```
The harness forces hero 0 to be the controlled hero (`$D9 = 1`, `E02C = 1`), clears the event flags, rewrites the tile ids around the hero (floor id 0 with attribute entry 16,0,0,0; solid id 250 with entry 19,6,0,0) and calls `$C0:B69C`, `$C0:D5C0`, `$C0:B0D3` once per frame with the pad bytes set; the scene routine's frame wait `$01:E0F9` is replaced by a return.

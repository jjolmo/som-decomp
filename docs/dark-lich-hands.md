# Dark Lich (Secret of Mana USA) - the hands phase, the hurt reaction and the actions per phase

Tags: **[V]** reproduced by running the original 65816 code in `tools/lich_sim.py` (whole game frame `$C0:B08C`; see `docs/dark-lich.md` section 2 for the time base), or measured on a live object of that run. **[C]** read from the disassembly, not executed. Anything not determined is in the open questions (section 9); no value in this document is guessed.

Time base: the Lich runs one engine tick every 5 frames (12.02 ticks/s). 1 tick = 5 frames = 0.0832 s; seconds = frames / 60.0988. A "state of N ticks" is the time between two state starts of the Lich, counted in whole ticks (a state with `DURATION14 = n` lasts n+1 ticks [V]).

State ids, the generic state machine (`$82` mode, `$AD` / `$2D` action counter and threshold, `$7E` flags) and the body states are described in `docs/dark-lich.md`; this document adds the hands states 1E-27, the hurt reaction and the phase statistics. Numbers are also in `data/dark_lich_hands.json`.

## 1. Summary table

Durations are ticks (seconds) measured over all runs of section 8 (scenarios "none", "spread", "natural"). "Cut" means the state ended early because the action counter `$AD` reached the threshold `$2D` (49 ticks, section 3). Direction code = direction from the Lich to the nearest living hero: 0 right, 1 down (+y), 2 left, 3 up [V].

| State | What it is | Animation | Duration (ticks / seconds) | Movement | Hit reaction possible | Entered by |
|---|---|---|---|---|---|---|
| 1E | hands idle (low) | F4 (loop) | 37 / 3.08 s, or cut: 5, 13, 17, 25, 26, 34 observed (n=698) [V] | none | no (no hurt box) | hands chooser, bit 15 clear, direction 0/2, random 0 |
| 1F | hands move down | F4 | 25 / 2.08 s, cut: 13 (n=119) [V] | +1 px per frame (up to 125 px) | no | chooser, bit 15 clear, direction 1 |
| 26 | hands move up | F4 | 25 / 2.08 s, cut: 13, 17 (n=119) [V] | -1 px per frame | no | chooser, bit 15 clear, direction 3 |
| 20 | raise hands | F5 (plays once) | 4 / 0.33 s in 682 of 682 [V] | none | no | chooser, bit 15 clear, direction 0/2, random 1 |
| 21 | raised idle | F6 (loop) | 1-46 / 0.08-3.83 s: runs until `$AD` reaches 49, then 1 tick per call (n=1176) [V] | none | **yes** (hurt box present) | chooser, bit 15 set, direction 0/2, random 0 |
| 22 | raised, move down | F6 | 25 / 2.08 s, 1 tick when `$AD` is already past the threshold (n=29) [V] | +1 px per frame | **yes** | chooser, bit 15 set, direction 1 |
| 27 | raised, move up | F6 | 25 / 2.08 s by the script [C]; cut at 21, 13, 9, 5, 1 seen (n=13) [V] | -1 px per frame | **yes** | chooser, bit 15 set, direction 3 |
| 23 | lower hands | F8 (plays once) | 4 / 0.33 s, or 1 tick when cut (n=677: 302 x 4, 375 x 1) [V] | none | no | chooser, bit 15 set, direction 0/2, random 1 |
| 24 | slam (the action) | F9 (plays once) | 17 / 1.41 s in 1174 of 1174 [V] | none | no | action routine: bit 15 clear and `$AD` >= `$2D` |
| 25 | hurt (hands) | F7 (loop), ends by callback | 21 / 1.75 s in 25 of 25 natural hits [V] | none | no | hit flag consumed in mode 1 |
| 07 | hurt (body), for comparison | EA | 21 / 1.75 s in 99 of 99 natural hits [V] | none | no | same |

The body-to-hands transition (18, 19, 1A: 37 + 37 + 1 ticks = 6.24 s) and the hands-to-body transition (1B, 1C, 1D) are unchanged from `docs/dark-lich.md`; 18, 19, 1B and 1C set `$7C` bit 0 and are never cut (`$C2:368F`), 1A and 1D last 1 tick; none of them has a hurt box (section 5) [V].

## 2. The scripts

Decoded with `tools/statescript.py` / `tools/lich_hands.py build` (state script table `$C2:E896`). `ROW 110` is `C0_006C 006E`, the call that loads boss-attack row 110 (power 127, attack stat 201, status 0x0010 at 99%, `docs/dark-lich.md` section 8). All hands scripts except 25 load it at their start [C]; only state 24 has an attack box (section 6), so row 110 is used for contact damage only there [V].

| State | Script (op operand) |
|---|---|
| 1E | ANIM F4; DURATION14 0x24; ROW 110 |
| 1F | ANIM F4; FRAMES (word 4 = +1); SPEED90 `$36BC`; ROW 110; DURATION14 0x18 |
| 20 | ANIM F5; STORE `$7E` = 0x8001; ROW 110 |
| 21 | ANIM F6; ROW 110 |
| 22 | ANIM F6; FRAMES (word 4 = +1); SPEED90 `$36BC`; ROW 110; DURATION14 0x18 |
| 23 | ANIM F8; STORE `$7E` = 0x0001; ROW 110 |
| 24 | ANIM F9; ROW 110 |
| 25 | ANIM F7; F4A callback `$C2:34B9` |
| 26 | like 1F with word 4 = -1 |
| 27 | like 22 with word 4 = -1 |

- No hands script has a SPELL or a SPAWN op: the hands cast nothing and spawn no projectile [C]. Hands states never run the body action table of spells and projectiles (`$C2:6E82`, section 3).
- FRAMES word 4 is the per-frame y step, word 2 the x step; `SPEED90 = $36BC` makes the object pass add them every FRAME (not every tick): `$C2:36BC` adds the x step, undoes it if the tile test `$C2:15B7` or the object test `$C2:1723` blocks it, then does the same for y [C]. Measured 1 px per frame = 60.1 px/s: 1F 14735 px in 14735 frames, 26 14245 px, 22 265 px, 27 345 px, with 125 px for a full 25-tick state [V]. The arena wall stops the move (a state-27 run at y = 130 stayed at y = 128) [V].
- `STORE $7E`: the word `$7E` holds bit 0 (hands phase) and bit 15 (hands raised). State 20 sets both, state 23 keeps only bit 0, 1A sets `0001`, 1D clears everything (`docs/dark-lich.md`) [C], seen in every run [V].

## 3. How the Lich enters each state

Read from `$C2:6DFB` (chooser), `$C2:6E82` (action), `$C2:6EBA` (hurt) and the generic machine `$C2:35CC-36B2` [C]; the probabilities and the cases were counted on the interpreter (section 8) [V].

**Generic rules** (same as for the body, `docs/dark-lich.md` section 4):
- `$AD` counts ticks and is reset to 0 when a mode-0 sequence of states ends (an action state; `$C2:35E3-35F0`); the transitions leave mode 0 in their last state (1A, 1D) without resetting it, so the first call after them finds `$AD` above the threshold (75 and up) and runs the action routine at once; `$2D` = 49 (Speed 1).
- When a state sequence ends: if `$AD >= $2D` the action routine runs (mode 0); if it returns "no action" (carry set) or `$AD < $2D` the chooser runs (mode 1).
- A mode-1 state is cut as soon as `$AD >= $2D` (`$C2:368F`) unless `$7C` bit 0 is set. A state entered with action counter `a` therefore lasts min(its length, 49 - a + 1) ticks. This reproduces every duration in the table, e.g. 1E entered with `$AD` = 37 lasts 13 ticks, with 45 lasts 5, with 16 lasts 34 [V].
- Re-picking the state that is already running does not restart its script (`$C2:377A` returns at once when the id is unchanged) but restarts the age `$96` and so the DURATION14 count; 22 followed by 22 therefore moves on without a pause (46 ticks, 228 px in one run) [V].

**Hands chooser** (bit 15 of `$7E` = hands raised), after refreshing the target and its direction code (`$C2:3A52`) [C]:

| bit 15 | step | result |
|---|---|---|
| clear | `rand(0..4) == 0` (20%) | hands to body transition 1B, 1C, 1D |
| clear | otherwise, direction 1 | 1F |
| clear | otherwise, direction 3 | 26 |
| clear | otherwise, direction 0 or 2 | `rand(0..1)`: 0 gives 1E, 1 gives 20 |
| set | direction 1 | 22 |
| set | direction 3 | 27 |
| set | direction 0 or 2 | `rand(0..1)`: 0 gives 21, 1 gives 23 |

The transition can only be chosen while the hands are down. While they are raised the Lich keeps choosing among 21, 22, 23, 27 until 23 lowers them [C]; this is why raised stretches last until the random pick of 23: 21 -> 23 332 times, 21 -> 21 821 times in the runs [V].

**Hands action** (`$C2:6E82`, only when `$AD >= $2D`): bit 15 clear gives state 24 (the slam) and leaves the flag clear; bit 15 set returns "no action", which falls through to the chooser (mode 1) [C]. The first action of a hands phase is the slam right after 1A (1A ends with `$AD` = 75): every 1A was followed by 24 (482 of 482 transitions) [V].

**Direction code** [V, 14 hero placements]: 0 = hero to the right, 1 = below, 2 = left, 3 = above, chosen by the larger of |dx|, |dy| of the nearest living hero (Manhattan distance, `$C2:3224`); with |dx| = |dy| the code was 0 or 2 for a hero below and 3 for a hero above. `E479 = [0, 1F, 0, 26]`, `E471 = [1E, 20]`, `E481 = [0, 22, 0, 27]`, `E475 = [21, 23]` (index by code or random).

**Observed transition counts** (all scenarios; n = entries) [V]:

| From | To (count) |
|---|---|
| 24 | 1E 416, 20 379, 1B 235, 26 90, 1F 54 |
| 1E | 24 228, 20 186, 1E 172 (re-pick), 1B 109, 1F 2, 26 1 |
| 1F | 24 64, 26 27, 1B 23, 1E 3, 20 2 |
| 26 | 1F 62, 24 29, 1B 16, 1E 8, 20 3, 26 1 |
| 20 | 21 348, 23 328, 27 5, 22 1 |
| 21 | 21 821 (re-pick), 23 332, 25 22, 27 1 |
| 23 | 24 375, 1E 107, 20 112, 1B 82, 1F 1 |
| 22, 27 | 22 and 27 re-pick themselves or each other (24 and 5 times), 21 and 23 rarely, 25 after hits |
| 25 | 23 15, 21 7, 22 2, 27 1 |

26 is followed by 1F in 62 of 119 exits and 1F by 26 in 27 of 119, because after 125 px the Lich has passed the hero and the direction code flips.

## 4. Short states 20, 22, 23, 27 and 21

- **20 (raise)**: animation F5 has three entries (delays 1, 1, 0 ticks; the last one has delay 0, which ends the animation, and with it the state because the state has no DURATION14 and `$9E` becomes 0, `$C2:36A5`). Measured 4 ticks = 0.333 s in all 682 occurrences, never cut: its start `$AD` was at most 45 and the threshold is reached after the animation ended [V]. It sets `$7E` = 0x8001 at its start, so the hands count as raised from the first tick of the state; the hurt box appears only with state 21 (section 5) [V].
- **23 (lower)**: F8 plays the same two frames in reverse order (delays 1, 1, 0). 4 ticks = 0.333 s, or 1 tick when `$AD` is already at the threshold on entry (375 of 677) [V]. It sets `$7E` = 0x0001 at its start, so the next call can run the action routine: after 23 the slam 24 followed in 375 of 677 cases, 20 in 112, 1E in 107, the transition 1B in 82 [V].
- **21 (raised idle)**: F6 is a two-frame loop (delays 3, 3; 6 ticks per cycle), the state has no duration, so it ends only when `$AD` reaches 49: 46 ticks when entered right after 20 with `$AD` = 4, 9 ticks with 41, and then 1 tick per call because `$AD` stays past the threshold while the action routine keeps answering "no action" [V]. Hit box present for 100% of the frames [V].
- **22 / 27 (raised, move)**: the same F6 loop moving 1 px per frame down / up; 25 ticks (125 px) when not cut [V for 22: 1 sample of 25 ticks; 27 only seen cut at 21, 13, 9, 5 ticks, the script is identical to 22 with the sign of the step reversed]. Forced test (heroes moved below / above the Lich while the hands were raised): 22 for 46 ticks and 228 px, then 27; 27 for 46 ticks and -207 px, then 22 [V]. These states occurred 29 (22) and 13 (27) times in 3 x 24000 frames because they need the hero direction to change between 20 and the next chooser call (only moving heroes do that, scenario "natural") [V].

## 5. Hit conditions and the hurt reaction

### 5.1 When the Lich can be hit

A party weapon hit needs the weapon box of a hero to overlap a Lich hurt box. The test `$C2:052E` -> `$C2:055E` -> `$C2:06FE` returns "no contact" when `obj+$CA | obj+$CE` (the half-widths of the two hurt boxes at `$C8-$CB` and `$CC-$CF`) is zero [C]. The hurt box comes from the animation frame, so it follows the animation: measured as the share of frames with a hurt box, per state [V]:

| States | Hurt box |
|---|---|
| body stand, walk (00-06), spells (08-0E), projectiles (0F-17) | 100% of the frames: half sizes 16 x 16 centred on the Lich (state 02: `$C8..$CB` = 0, 0, 16, 16) |
| hands raised: 21, 22, 27 | 100% of the frames: one box, half sizes 12 x 15, centre offset -23 in y (state 21: 1, -23, 12, 15) |
| 18, 19, 1A, 1B, 1C, 1D (transitions) | 0% |
| 07, 25 (hurt) | 0% |
| 1E, 1F, 20, 23, 26 (hands low or moving between poses) | 0% |
| 24 (slam) | 0% |

So the hands can be hurt **only while they are raised** (states 21, 22, 27; bit 15 of `$7E` set apart from the one tick of 20, which has no box), and the Lich cannot be hurt during any transition, during the hurt reaction or during the slam. Natural party hits (scenario "natural", 24000 frames x 16 runs) landed in hands states 21 (22 hits), 22 (2) and 27 (2) and in no other hands state [V].

After contact, `$C0:002D` (damage and result, `$C0:3A79`) returns a result in the low byte (1: the floating number event, 2: the hit event) and a type in the high byte; for result 2 the routine `$C2:0F59` sets the reaction flag (`obj+$34` bit 0, and `obj+$100` = 0xC0) only when the type is 8 or 9 [C]. Observed in a run with the party fighting: type 8 hits all damaged the Lich and set the flag; two hits of type 0x0D (state 21, mode 1) left the Lich HP unchanged, showed the floating number (a "0", `docs/damage-counter.md` section 2) and gave no reaction; types 0x0C, 0x0E and 0x12 also occurred (HP not checked) [V]. What the type byte means is not determined (section 9).

### 5.2 Which mode reacts

`$C2:0501` consumes `obj+$34` bit 0 once per tick [C]. In the generic machine (`$C2:362D-366E`):
- mode 1 (every chooser-picked state, which includes all hands poses and the body stand/walk): the hit interrupts at once: mode 2, `$2D` = 0, the hurt sequence of the object record is selected (07 when `$7E` bit 0 is clear, 25 when it is set; `$C2:6EBA`) [C, V];
- mode 0 (action states 08-17 and 24, transitions): the flag is cleared and ignored unless `obj+$190` is negative (the check `$C2:34B0`), which was never the case in the runs [C, V: 88 hits during projectile states, 2 during a spell and 1 counted at the first frame of the transition 18 lowered the HP but changed no state];
- mode 2 (already hurt): not interruptible.

Injection test (`lich_hands.py hurt`: the hit flag set by hand in a state, nothing else) [V]:

| State at the injection | Mode | Result |
|---|---|---|
| 00, 02 (body stand / walk) | 1 | mode 2 after 1 tick (5 frames), hurt state 07 from +10 frames, then an action (projectile or spell) at +15 |
| 1E, 20, 21, 23, 26 (hands) | 1 | mode 2 after 5 frames, hurt state 25 from +10 frames, then 21 / 23 / 24 at +15 (1 tick of hurt, see 5.3) |
| 22, 27 (hands raised, moving; injected in the `force` scenario) | 1 | the same: 25 from +10 frames, back to the same state at +15 |
| 24 (slam), 18, 19, 1B (transitions) | 0 | no reaction, the state ran to its end |

Every hit that lowered the Lich HP in a mode-1 state produced the reaction: 125 of 125 (hurt entered from 00: 41, 01: 13, 02: 45, 21: 22, 22: 2, 27: 2) [V]. The damage itself is applied in all modes and the Lich is not made invulnerable in mode 0 (damage values 1 to 223 seen).

### 5.3 How long the hurt state lasts

Hurt states 07 and 25 have the same script (an animation and the F4A callback `$C2:34B9`); the callback ends the state when the age `$96` is 60 ticks or more, or when both `obj+$175` (low byte, the damage-number request) is 0 and `obj+$60` (low byte) is not 0x40 [C]. `obj+$60` = 0x40 is the state of the floating damage number: the hit makes the game create the number on the Lich (`$C1:8018` -> `$C1:810E`) and it clears `obj+$60` when its animation ends (`$C1:83F9`); the number is drawn for 97 frames (`docs/damage-counter.md` section 1) [C]. So the hurt state lasts as long as the damage number of the hit:
- measured: `obj+$60` = 0x40 for **98 frames** after every hit, in 11 of 11 hits of a run (including the 2 hits with zero damage, which show a "0") [V];
- the hurt state ran **21 ticks (105 frames)** in 99 of 99 body hits and 25 of 25 hands hits [V]: hit at frame 35, mode 2 at 36, hurt state from 41 to 146, number request at 35, marker set at 40 and cleared at 138 (the state notices the clear on the next tick boundary);
- the cap of 60 ticks of the callback is never reached [V].

An injected hit flag (`obj+$34` bit 0 set by hand: no damage, no number) leaves `obj+$60` at 0, so the callback ends the state at its first check: 1 tick, and the action routine ran 5 frames later [V, state 02; the 1-tick hurt of `docs/dark-lich.md` section 4 item 6]. Writing `obj+$60` = 0x40 by hand together with the flag ended the hurt state after 7 ticks (35 frames), not after 21 [V; not analysed further]. That settles the earlier open question: the 21 ticks (1.75 s) of the natural hurt are the life of the damage number of the hit, in the body (07) and in the hands (25) alike.

Order after a hurt state: `$2D` was set to 0, so the action routine fires at the end of the hurt state:
- body (07): action in 99 of 99 cases (projectile or spell by the alternating bit 15) [V];
- hands (25): bit 15 is still set (only raised hands can be hit), so the action routine answers "no action", the chooser picks among 21, 22, 23, 27 and each of them lasts 1 tick because `$AD >= $2D = 0`; 23 lowers the hands and the next call runs the slam 24. Seen 15 times 25 -> 23 -> 24 and 7 times 25 -> 21 -> ... -> 23 -> 24 [V]. `$2D` returns to 49 when the slam ends.

Net effect of a hit on raised hands: 1.75 s of hurt, then a lowering of about 0.1 s and a slam (1.41 s) within about 0.1 s of the hurt state ending.

## 6. The slam (state 24)

- Animation F9: 13 frames with delays 2, 1 (x10), 3, 0 (15 ticks); the state lasts 17 ticks = 85 frames = 1.41 s [V].
- The only attack box of the hands phase (`obj+$C0-$C3` = x offset, y offset, half width, half height): 0 for frames 0-24 of the state, then (0, -16, 40, 9) at frame 25 growing through (0, -16, 45, 11), (0, -16, 46, 13), (0, -18, 47, 13), (0, -17, 48, 13), (0, -16, 49, 16) to (1, -18, 52, 17) at frame 55, and 0 again from frame 60: tick 5 to tick 11, 35 frames = 0.58 s [V]. In 1174 slams the attack box existed for 41.2% of the frames (35 of 85) and in no other hands or body-transition state [V].
- Row 110 hits for 127 power, attack stat 201, status 0x0010 at 99% (`docs/dark-lich.md` section 8).

## 7. Animations used (frame records in bank CA, delays in ticks)

`tools/lich_hands.py ROM STATE anims`: the animation table at `$DB:F9A8` points to scripts in bank C1; an entry is a frame pointer (2 bytes) and a delay (1 byte); odd bytes are commands (`1A` restarts the animation, `0C` two argument bytes) [C].

| Id | Used by | Frames | Delays | Ends |
|---|---|---|---|---|
| E8, E9 | body 00-06 | 4 | 4, 3, 4, 3 | loop |
| EA | 07 (hurt, body) | 5 | 1, 1, 2, 2, 0 | end (the state is held by the callback) |
| F4 | 1E, 1F, 26 | 2 (`CA:DA14`, `CA:DA4C`) | 3, 3 | loop |
| F5 | 20 | 3 (`CA:DA84`, `CA:DAC4`, `CA:DAC4`) | 1, 1, 0 | end |
| F6 | 21, 22, 27 | 2 (`CA:DB04`, `CA:DB4E`) | 3, 3 | loop |
| F7 | 25 (hurt, hands) | 2 (`CA:DB98`, `CA:DBD0`) | 1, 1 | loop |
| F8 | 23 | 3 (`CA:DAC4`, `CA:DA84`, `CA:DA84`) | 1, 1, 0 | end |
| F9 | 24 | 13 (`CA:DC08` to `CA:DF2E`) | 2, 1 x 10, 3, 0 | end |

F5 and F8 use the same two frames in opposite order. Only the F6 frames (`CA:DB04`, `CA:DB4E`) carry a hurt box [V, section 5].

## 8. Actions per phase, phase lengths and their consistency

Method: `tools/lich_hands.py ... stats` runs the whole game frame (`$C0:B08C`), logs every state start (`$C2:377A`) with the handler that chose it (chooser, action, hurt, or the script of the previous state), and derives phases. Free body phase = from the end of 1D (the spawn for the first one) to the start of 18; free hands phase = from the end of 1A to the start of 1B; action = state started by the action routine (08-17 in the body, 24 in the hands). 16 runs of 24000 frames (399.4 s) per scenario; the run of RNG index 85 stops after about 1000 frames in every scenario because the interpreter reaches a stale object slot (`C2:CB00`, not valid code), so about 15 runs count. Scenarios: **none** (heroes far away and idle, their weapon hits off: the earlier measurement setting), **spread** (heroes idle at seed-dependent places, hits off: every direction code occurs), **natural** (heroes next to the Lich with their weapon hits on and the party AI running). The Lich HP is refilled below 2000 so that the fight never ends.

| Scenario | Body phases n | Body seconds min / mean / max | Body actions min / mean / max | Hands phases n | Hands seconds min / mean / max | Hands actions min / mean / max |
|---|---|---|---|---|---|---|
| none | 140 | 3.08 / 14.25 / 58.32 | 1 / 2.58 / 10 | 147 | 1.41 / 10.33 / 57.99 | 1 / 2.33 / 11 |
| spread | 158 | 3.08 / 13.29 / 66.22 | 1 / 2.46 / 11 | 169 | 1.41 / 10.58 / 42.01 | 1 / 2.44 / 8 |
| natural | 140 | 3.08 / 15.02 / 90.68 | 1 / 2.78 / 15 | 149 | 1.41 / 10.78 / 58.49 | 1 / 2.44 / 11 |
| none + spread | 298 | 3.08 / 13.74 / 66.22 | 1 / 2.51 / 11 | 316 | 1.41 / 10.47 / 57.99 | 1 / 2.39 / 11 |

Standard deviation of the number of actions: body 2.1, hands 1.7. The first body phase after the spawn (no immediate action; the first chooser call comes at 3.08 s and can already pick the transition) lasted 17.1 s (none, n = 16, 0 to 11 actions) and 18.0 s (spread, n = 16, 0 to 3 actions). Per body phase about 0.94 spells and 1.58 projectile attacks (the first action is always a projectile and the two alternate).

Distribution of the number of actions per free phase (none + spread):

| Actions | 1 | 2 | 3 | 4 | 5 | 6 | 7+ |
|---|---|---|---|---|---|---|---|
| Body (n = 298) | 131 | 71 | 31 | 22 | 12 | 8 | 23 |
| Hands (n = 316) | 133 | 73 | 43 | 30 | 19 | 6 | 12 |

**Consistency with the phase lengths** [V]:
- A body cycle after an action is: chooser call 1 (a stand or walk state of 37 ticks), chooser call 2 (cut at the threshold: 13 ticks), then the next action: 263 of the 417 cycles in the "none" run followed exactly this pattern (37, 13, action), 82 left after the 37-tick state and 72 left at once [V]. A full cycle is the action (37 ticks for a projectile, 11-17 for a spell, mean about 25) plus 50 ticks = about 75 ticks = 6.3 s; the last cycle of a phase is shorter (no wait, or 37 ticks only), which gives 13.7 s / 2.51 actions = 5.5 s per action [V].
- The chance of choosing the transition: the first call after an action picked it in 165 of 858 cases (19.2%), the second call in 162 of 689 (23.5%); in the hands phase 316 of 1417 calls with bit 15 clear (22.3%). The ROM rule is `rand(0..4) == 0`, 20%. The game's generator is a deterministic table generator and consecutive draws are not independent; the excess on the second call is 2.5 standard errors and is not explained [V].
- With the 20% rule alone, a tick-level model of the rules of section 3 (`tools/lich_hands_model.py`, no ROM needed) gives 2.77 actions / 15.2 s (body) and 2.78 / 12.6 s (hands); with the measured chance (0.21 body, 0.223 hands) it gives 2.65 actions / 14.4 s and 2.53 actions / 11.2 s. The measurements (2.51 +/- 0.12 actions / 13.7 s; 2.39 +/- 0.10 / 10.5 s) agree with the second model within about 1.4 standard errors, and with the 20% model within 2 (body) and 4 (hands) standard errors [V].
- The earlier summary ("2.9 actions in the body, 2.1 in the hands" over 37 and 33 phases of 8 runs) is consistent with this within its sampling error. It compared the action counts with phase lengths measured by the hands bit (`$7E` bit 0): that body phase (bit clear) also contains the transition 18-19 (6.16 s) and that hands phase (bit set) 1A, 1B and 1C (6.24 s). With the transitions the means are 19.9 s (body) and 16.7 s (hands) for the free lengths of the table, and the spawn phase (17.1-18.0 s free) makes the body mean of a short sample higher.

**Party hits do not change the statistics** much: scenario "natural" has body 15.0 s / 2.78 actions and hands 10.8 s / 2.44, against 13.7 s / 2.51 and 10.5 s / 2.39 with hits off. The differences are within 1.4 standard errors [V], although the hurt reaction itself (1.75 s per hit in mode 1) is added to the affected phases.

## 9. Open questions

- The meaning of the hit type (high byte of the result of `$C0:002D`): 8 sets the hurt flag (and damaged), 9 is read as setting it but was not seen, 0x0D came with zero damage and no reaction; whether 0x0C, 0x0E and 0x12 (seen, HP not checked) damage the Lich and why they set no flag is not determined. Which hero attack produces which value is not determined.
- Who sets bit 15 of `obj+$190`, the condition that lets a hit interrupt a mode-0 state (`$C2:34B0`) and makes `$C2:0501` report a hit every tick; it was never set in the runs, so whether a status of the Lich can make the actions interruptible is not determined.
- The chance of the transition at the second chooser call (23.5%) and at hands calls (22.3%) against the 20% of the rule: the table generator's structure was not analysed.
- The 2-pixel sideways displacement seen at some frames in states 1F and 26 (13 and 50 frames of the "spread" run) was not traced to its cause (collision push-out is the candidate, `$C2:152B` / `$C2:1571`).
- State 27 was never seen running its full 25 ticks, and 22 once; they follow the 1F / 26 pattern by script equality but are not directly confirmed beyond the figures above.
- The damage the party deals to raised hands against the body (the same hit routine; values 1-223 were seen in both) and the death of the Lich were not examined (the HP was refilled in all runs).
- The interpreter stops after about 1000 frames for the run of RNG index 85 (invalid object handler `C2:CB00` in a stale slot of the save state's object table); whether this is a limit of the harness or reachable in the game is not determined.
- Behaviour under lag on real hardware, as in `docs/dark-lich.md`.

## 10. Method and tools
- `tools/lich_hands.py ROM STATE anims | trace SEED FRAMES MODE | stats SEEDS FRAMES OUT.json MODE [EVENTS.json] [FIRST_INDEX] | restat EVENTS OUT MODE FRAMES | hurt OUT | force OUT | build OUT NAME=FILE...`: all take the ROM and a save state taken in the map-246 arena as arguments (`docs/dark-lich.md` section 6). `build` assembles `data/dark_lich_hands.json`.
- `tools/lich_hands_model.py [PHASES] [P_DIR13] [SEED] [P_LEAVE_BODY] [P_LEAVE_HANDS]`: the rule model of section 8, no ROM.
- Static facts were read with `tools/flowdis.py` (entries `C26DFB:00`, `C26E82:00`, `C26EBA:00`, `C2055E:00`, `C20501:00`, `C20F27:00`, `C2377A:00`) and `tools/statescript.py`.

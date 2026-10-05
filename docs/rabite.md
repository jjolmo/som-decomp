# Rabite (monster id 0) - complete behavior recovered from the ROM (Secret of Mana USA)

Tags: **[V]** executed: the real 65816 code ran in `tools/cpu65816.py` (whole per-frame routine `$C0:B08C` on a ZSNES save state, or the single AI handlers, see section 12); **[C]** read from the disassembly, read, not executed. What is not determined is in section 11 and carries no values.

Addressing: 2 MiB HiROM, `$Cx:xxxx` = file offset `((x-0xC0)<<16)|xxxx`, `$01:xxxx` is the mirror of `$C1:xxxx`. Script addresses ("pc") are offsets from ROM `0x104F15`. No ROM bytes are stored in the repo; the scripts are described by their decoded numbers.
Coordinates: world position `obj+2/obj+4` and screen position `obj+0x20` / `obj+0x22 - obj+0x45` in pixels (screen 256 x 224). Facing/direction codes of commands: 1 right, 2 left, 4 down, 8 up. Name "Rabite" is decoded from the ROM text (`tools/names.py`).

## 1. Summary

- Object id 0, stat record `0x101C00` (level 1, HP 20, Str 3, Agi 1, weapon rows 72/72, `data/monsters.json`). Its behavior is the enemy bytecode script (`docs/dark-lich.md` section 7) whose entry pc 0x0000 is the word at bytes 9-10 of its object-table entry (`ROM 0x100000 + id*16`) [V]. No other object id uses script pc 0x0000. The movement, target-acquisition and hop routines it calls (pc 0x67DF-0x6B22) are a library used by all ids 0x00-0x53 and 0x56 (section 10) [C].
- **Time base**: the AI of an ordinary monster runs one step every 5th video frame, **12.02 steps/s** (60.0988 / 5 = one step per 83.2 ms). Movement, animation and cooldown counters run every frame (60.0988 Hz). Evidence in section 2 [V].
- The script is a loop: `if HP > 9: 1/8 wander hop, else acquire a target and act according to its distance; if HP <= 9: flee`. There is no detection radius: any hero that is on screen and not disabled is a target (section 4) [V].
- It attacks with a lunge-bite (command 02) when the weapon cooldown gauge is 0 and the target is within 48 px, then backs off in two 6 px steps (section 6) [V].
- Hit reaction: 40 px knock back (weapon hit), about 1.75 s before the AI acts again (pending-damage hit); death: 105 frames (1.75 s) of death animation, then the object turns into object id 0xEA (section 7-8) [V].

## 2. Time base [V]

| fact | evidence |
|---|---|
| The monster slots 3, 4, 5 are stepped at `$56` = 0, 1, 2 (`$56` counts 0..4 once per frame) | read at `$C0:B0D3` [C]; run: AI steps of a Rabite in slot 3 / 4 / 5 fell on frames with `frame mod 5` = 0 / 1 / 2 in 15 of 15 cases each (`tools/ai_sim.py`) |
| AI step = `$C1:D942` (called from `$C0:F8B3` only when the actor is free) | run: the AI step is skipped while the actor executes a command (hop, swing, hurt, death) |
| Every command lasts a multiple of 5 frames | 2,080 commands in 10 runs of 90 s: 20, 25, 30, 35 frames (table in section 6) |
| Movement is integrated every frame, not per AI step | run: positions change on consecutive frames (1-2 px per frame) |
| Cooldown gauge `obj+0x1ED` counts down once per frame | run: 99, 98, 97 ... on consecutive frames |

Seconds in this document are frames / 60.0988. One AI step = 5 frames = 0.0832 s.

## 3. How the script is picked and run

- Spawn (map object -> actor, `$C0:DE3B`): `JSL $C1:0020` -> `$C1:25B6` loads the script pointer from the object table (`obj+0x144 = word at ROM 0x100009 + id*16`), clears variables `obj+0x146`, `0x14C`, `0x14E`, `0x14F` (call depth) and sets target `obj+0x1AC = FF` [C]. The first command of the Rabite is issued on the spawn frame [V].
- AI step (`$C1:2552`): runs ops (`$C1:251A`, table `$C1:2257`) until one **yields** (op handler returns 0) or 256 ops ran. Handlers return FF to continue. A yield issues a command that keeps the actor busy; the next AI step happens on the first AI-step frame after the command ended (always the same frame the command ended, because command lengths are multiples of 5 frames) [V].
- Error (call stack deeper than 16, return at depth 0, or 256 ops without a yield): `$C1:0100` restarts the script at entry+3 and clears the command [V; 256-op loop and 17-deep recursion both executed].
- Variables: `var3` = high nibble of `obj+0x147` (set by op 2C, tested by ops 05, 09, 0D); the target slot `obj+0x1AC` (FF = none); the saved screen position `obj+0x148/0x14A` (ops 9F/9D); the call stack `obj+0x150...` [V].
- Jump offsets: 1 byte (bit 7 set, 7-bit signed) or 2 bytes (15-bit signed, big endian), added to the address after the instruction [V, `tools/ai_ops.py`: +5, +32 and -63 executed].
- The random number is the game RNG (`docs/rom-combat.md` section 1.2) rejection-sampled on a 4-bit value: op 2C n gives a uniform value in 0..n [V: 4000 draws per n, flat].

Ops used by the Rabite script (33 opcodes, all executed by `tools/ai_ops.py`; length includes the jump offset where there is one):

| op | length | behavior [V] |
|---|---|---|
| 00 | 1 | return from CALL |
| FF hi lo | 3 | call (big-endian address), push depth |
| 01 off | 2-3 | jump |
| 05 off | 2-3 | jump if var3 != 0 |
| 09 off | 2-3 | jump if var3 == 0 |
| 0D n off | 3-4 | jump if var3 != n |
| 2C n | 2 | var3 = uniform random 0..n |
| 2F a b imm off | 5-6 | jump if byte(object a, offset 0x180+b) < imm |
| 30 a b imm off | 5-6 | jump if that byte > imm |
| BD a b lo hi off | 6-7 | jump if word(object a, offset 0x180+b) > imm (word) |
| 31 / 49 / 4E / 53 / 58 off | 2-3 | jump if there is NO valid hero within 16 / 32 / 48 / 64 px / anywhere on screen |
| 4C / 51 / 56 off | 2-3 | jump unless the current target is valid and within 32 / 48 / 64 px |
| A5 / B1 / B4 / B7 | 1 | target = first valid hero (slot order 0,1,2) within 16 / 32 / 48 / 64 px, FF if none |
| 5D | 1 | target = first valid hero farther than 64 px, FF if none |
| 9F | 1 | save own screen position |
| 9D off | 2-3 | jump if own screen position equals the saved one |
| E0 a b c | 4 | hop: command C1 (direction code a, animation b, flag c); yield |
| E2 n | 2 | pose: command 40 (animation n); yield |
| E3 a b | 3 | command C1 in the current facing direction (actor at rest), animation a, flag b; yield |
| E4 a b | 3 | if the target is valid: command C1 toward the target (primary direction), animation a, flag b; yield; else no-op |
| FD a b | 3 | same with the alternate direction |
| E6 a b / FE a b | 3 | like E4 / FD but away from the target |
| E8 | 1 | attack swing (command 02) if `obj+0x1ED` = 0 (yield), else no-op |

Object reference byte `a`: 0x00-0x7F object slot, 0x80 self, 0x81 / 0x82 the slot in `obj+0x1AC` / `obj+0x1AD` [C]; the Rabite uses 0x80 only (self+0x182 = HP word, self+0x1ED = cooldown gauge, self+0x1AC = target).
Direction codes of E4 / FD / E6 / FE (`$C1:0404`, executed for every whole angle with the hero at 40 px; angle 0 = hero to the right, 90 = above, counter-clockwise): primary code (E4) = 8-way direction toward the hero: 1 for 338..22 degrees, 9 for 23..67, 8 for 68..112, 10 for 113..157, 2 for 158..202, 6 for 203..247, 4 for 248..292, 5 for 293..337; alternate code (FD) = the diagonal of the quadrant: 9 for 1..90, 10 for 91..179, 6 for 180..269, 5 for 270..360 (0 included). E6 / FE give the codes for the opposite direction (E6 = 2 where E4 = 1) [V].

## 4. Targets, distance classes, "aggro" [V]

- A hero is a **valid target** if its object is active, its status word `obj+0x190` has none of the bits `0x8460`, and its screen position is inside the screen: `obj+0x20 < 256` and `obj+0x22 - obj+0x45 < 224` (`$C1:054A`) [C; executed with status 0x0020 (invalid) and with positions on and off the screen].
- Distance classes (`$C1:0358`, Euclidean distance between the screen positions of the two actors, thresholds inclusive): <= 16 px, <= 32, <= 48, <= 64, <= 96, farther [V: all boundaries 16/17, 32/33, 48/49, 64/65, 96/97 executed]. If the horizontal or vertical difference is 256 or more (a monster that is off screen) the class is "<= 64 px" whatever the real distance [V: a Rabite with screen x 0xFFFF chose the 49-64 px routine and approached the hero].
- **There is no detection radius.** Target acquisition (subroutine pc 0x6AE1, called by all ids): take the first valid hero in slot order within the tightest band that contains one of: <= 16, <= 32, <= 48, <= 64, anywhere on screen (op 5D). If no hero is valid at all (all off screen, dead or disabled) the monster runs a wander hop (subroutine 0x67DF) and tries again [V: run with hero 0 disabled; every hero distance from 10 to 200 px gave a target].
- Therefore the Rabite always engages a hero that is on the screen; the distance only chooses what it does (section 5.2).

## 5. The script as a state machine [V]

Script structure (pc = script address, numbers are decoded values; every branch below was executed). Probabilities were checked against 3,000 executions of the real AI step per case (`tools/rabite_model.py`: expected and measured agree within 1 percentage point).

### 5.1 Entry
`pc 0x0000`: call 0x0043 = three poses `E2 00` (3 x 30 frames = **90 frames = 1.497 s** standing, `cmd 40`), then the main loop at pc 0x0003.

### 5.2 Main loop (pc 0x0003), evaluated after every command
1. If `HP <= 9` (word `obj+0x182`, 45 % of the 20 maximum): **flee routine** (5.6).
2. Else with probability **1/8**: wander hop (5.5), then back to 1.
3. Else (7/8): acquire the target (4), then by the target's distance class:

| target | what it does |
|---|---|
| <= 32 px (class <= 2) | routine pc 0x004A: if the cooldown gauge is 0: with 3/4 **turn toward the target and bite** (5.3), with 1/4 skip the bite; if the gauge is > 0 skip the bite. Then always **two back-steps** (`FD 05 00`, alternate direction, animation 5 = 6 px backwards, 30 frames each) and the retreat loop (5.4) |
| 33-48 px | routine pc 0x0063: turn toward the target (`E4 00 00`, 20 frames) and, if the gauge is 0, bite; no retreat |
| 49-64 px | routine pc 0x0074: with 1/3 turn toward the target (20 frames); with 2/3 approach hop (5.7) |
| farther than 64 px | with 1/6 turn toward the target (20 frames); with 5/6 approach hop (5.7) |

Resulting probabilities of the first command of one pass (executed, 3,000 samples each): target <= 32, gauge 0: turn 0.678, back-step 0.219, hops 0.034 each (the 1/8 wander share); target <= 32, gauge > 0: back-step 0.875; 33-48 px: turn 0.897; 49-64 px: turn 0.314, approach hop 0.618; farther: turn 0.168, approach hop 0.764; no valid hero: hop animation 4 / 1 / 2 each 0.275, turn 0.175 (the model value is the same to 3 decimals in `tools/rabite_model.py`).

### 5.3 Bite (op E8, command 02)
Allowed when the cooldown gauge `obj+0x1ED` is 0. The swing animation is chosen from the distance to the target on the facing axis (`$C1:E40E`) [V, 1-px sweep, `data/ai_commands.json`]:

| distance along the facing axis | swing animation | frames | movement |
|---|---|---|---|
| < 26 px horizontal / < 24 px vertical | 3 | 20 (0.333 s) | none |
| 26-41 horizontal / 24-39 vertical | 1 | 25 (0.416 s) | lunge 2 px/frame from frame 6 until contact (about 10 px gap) |
| >= 42 horizontal / >= 40 vertical | 2 | 30 (0.499 s) | 1 px/frame (frames 1-5), 2 px/frame (6-25), 1 px/frame (26-30): 50 px unless blocked |

At the end of the swing the gauge is set to `(100 - Agi)/2 + 50` = **99 frames (1.647 s)** and counts down one per frame, so the next bite needs at least 99 frames after the previous one ended [V: 99, 98, ... observed; the formula is read at `$C0:F937`, [C]]. Weapon row 72: hit 99 %, power 7 (attack stat 10 = Str 3 + 7), status chance 25 % without a status word (`data/weapons.json`); damage follows `docs/rom-combat.md` section 4. In the runs the swing registered a hit on the hero (hero hurt state, `obj+0x59/0x5A` bits) 14 frames after the start of a lunge at 40 px [V]; the hit box geometry is not determined.

### 5.4 Retreat loop (pc 0x009C, after a bite or its skip)
While the target is within 32 px: acquire target, hop **away** (`E6 02 00`, or `FE 02 00` when the position did not change since the last hop = blocked: animation 2 = 30 px, 35 frames), then repeat if `HP > 9`; at `HP <= 9` it leaves the loop after one hop. [V: sequence seen in the logs]

### 5.5 Wander hop (subroutine 0x67DF), also used when no hero is valid
Choose the hop length with probability 1/3 each: animation 4 (6 px), 1 (15 px) or 2 (30 px). Then: 1/8 a diagonal code (up-right, up-left, down-right, down-left, 1/4 each), else 1/5 of the rest (7/40 overall) three turn-in-place commands in a row (`E3`, 3 x 20 frames = **60 frames = 1.0 s**), else (7/10 overall) one of the four cardinal directions (1/4 each) [V: counts]. A hop with a diagonal code moves along the horizontal axis only (the vertical part is dropped), except animations 4 and 5 which add a +-2 px vertical shift [V, `data/ai_commands.json`].

### 5.6 Flee routine (HP <= 9, pc 0x0081)
Acquire target (wander if none), hop away (E6 / FE, 30 px, 35 frames; the alternate direction if blocked), then while the target is within 32 px: re-acquire and wait one pose of animation 5 (**5 frames**), else loop. The Rabite never attacks in this state. [V: hero 30 px and 70 px away, 14 s: hops of 30 px every 35 frames until a wall]

### 5.7 Approach hop (subroutine pc 0x6902, used only by the Rabite)
If the position is unchanged since the last saved position (blocked) hop with the alternate direction else with the primary direction (`E4 02 00`), animation 2: **30 px in 35 frames** toward the target; the position is saved first (`9F`). [V]

## 6. Commands (numbers measured by executing them, `data/ai_commands.json`) [V]

| command | frames (s) | movement |
|---|---|---|
| C1 anim 0 (turn only) | 20 (0.333) | none |
| C1 anim 1 | 30 (0.499) | 15 px along the facing axis, 1 px/frame, frames 11-25 -> 30 px/s average over the command |
| C1 anim 2 | 35 (0.582) | 30 px, frames 11-30 (1 px/frame x5, 2 px/frame x10, 1 px/frame x5) -> 51.5 px/s average, 120 px/s peak |
| C1 anim 4 | 30 (0.499) | 6 px (1 px on frames 12, 14, 17, 19, 22, 24) -> 12 px/s |
| C1 anim 5 | 30 (0.499) | 6 px backwards (-1 px on the same frames) |
| 40 pose 0 | 30 (0.499) | none |
| 40 pose 5 | 5 (0.083) | none |
| 02 swing | 20 / 25 / 30 | section 5.3 |

Frame numbers count from the frame of the AI step (0). The direction code selects the facing: 1 right, 2 left, 4 down, 8 up; codes 5, 6, 9, 10 use the horizontal facing. Hops are blocked by walls (the hop stops where the map blocks it; observed at the arena wall) [V]. Average speeds are per command including the standing part; frames to seconds at 60.0988 Hz.

## 7. Hit reaction [V]

- Pending damage (`obj+0x1F1`) is applied on the monster's next AI-step frame. HP drops, the actor enters the hurt state (`obj+0x1C = 0x40`, animation 0x88, no movement) and **no AI step runs for 105-106 frames (1.75 s)**; `obj+0x60 = 0x40` during frames 6-104 [V: damage 1 and 50 injected into `obj+0x1F1`, identical timing].
- A weapon hit by a hero (hero AI of the save state) uses animation 0x89 and **knocks the Rabite back 40 px, opposite to the Rabite's own facing** (facing up -> pushed down, down -> up, right -> left, left -> right), independent of where the hero stands: 3 px/frame on frames 1-10, then 2 px/frame on frames 11-15 (40 px in 16 frames = 0.27 s); the push is shortened when a wall is in the way [V: 8 runs, 4 facings x 2 hero positions]. After a weapon hit by the save state's hero the AI resumed only after 250-345 frames, because `obj+0x190` held bit 0x0002 for about 224 frames after the hit; why the weapon hit sets that bit is not determined (section 11).
- A second hit on the actor while it was hurt was applied (HP 581 -> 515 -> 442 at 105-frame intervals in one run); whether a hit can be refused during the hurt state was not tested.

## 8. Death [V]

HP 0 at the damage frame: the object becomes object id 0xF9 immediately (script entry pc 0x585E), runs the death state (`obj+0x60 = 0x40`) for **105 frames (1.75 s)**, then becomes object id 0xEA (script pc 0x54F1) and stays active; 40 of 40 RNG seeds identical. What object 0xEA is for is not determined. EXP, gold, weapon progress and the drop roll happen in the death routine `$C0:4203` (`docs/rom-combat.md` sections 8, 11, 13); for the Rabite: 1 EXP, 2 gold, chest chance 12.5 % (`data/drops.json`).

## 9. State machine in seconds (summary)

| situation | cycle |
|---|---|
| spawn | stand 1.497 s |
| hero on screen, farther than 64 px | per pass: 1/6 turn 0.333 s, 5/6 approach hop 0.582 s (30 px), 1/8 of passes wander hop instead; approach speed 51.5 px/s |
| hero 49-64 px | per pass: 1/3 turn 0.333 s, 2/3 approach hop 0.582 s |
| hero 33-48 px | turn 0.333 s, then bite 0.333-0.499 s if the gauge is ready (otherwise turn again) |
| hero <= 32 px, gauge ready | turn 0.333 s, bite 0.333-0.499 s (3/4), two back-steps 2 x 0.499 s, hop away 0.582 s while the hero stays within 32 px |
| hero <= 32 px, gauge not ready | two back-steps 2 x 0.499 s, hop away 0.582 s |
| HP <= 9 | flee hops 0.582 s each, 30 px, 51.5 px/s |
| no valid hero | wander hops 0.499 / 0.499 / 0.582 s (6 / 15 / 30 px), 1.0 s turn-in-place with probability 7/40 per hop choice |
| hit | weapon: knock back 40 px (opposite to the facing) in 0.27 s; hurt until 1.75 s after a pending-damage hit |
| dead | 1.75 s death animation, then object 0xEA |

In the 90 s runs with the hero 24 px from the spawn point a bite occurred every 2.3-2.9 s (cycle turn 20 + bite 25 + back-steps 60 + hop away 35 + approach hop 35 frames) [V].

## 10. Other monsters

- The script at pc 0x0000 serves only object id 0 [C: object-table scan, all 128 entries; `data/ai_scripts.json`]. The ids that share a script pointer are 0x20, 0x2E, 0x3F, 0x56 (pc 0x5605) and 0x25, 0x7F (pc 0x20AD); the bosses 0x57-0x7E have filler entries.
- Subroutines used by the Rabite and **shared with other monsters** [C, static walk of every script, `data/ai_scripts.json`]: target acquisition 0x6AE1, wander 0x67DF and the six hop primitives 0x683C 0x685D 0x687E 0x689F 0x68C0 0x68E1 (animations 4, 1, 2 with diagonal / cardinal codes) are called by every script of ids 0x00-0x53 and 0x56 (ids 0x54 and 0x55 do not). The attack check 0x6B0F is called by 30 ids. The approach routine 0x6902 is used only by the Rabite. The library only issues commands with animation ids 0, 1, 2, 4; what they look like and how long they last belongs to each monster's own animation set [V: wander runs of 40 s with the hero disabled, frames per command (turn / anim 1 / anim 2 / anim 4)]: id 0 (Rabite) 20 / 30 / 35 / 30; id 1: 10 / 10 / 10 / 10; id 2: 5 / 30 / 20 / 60; id 3: 5 / 30 / 20 / 60; id 4: 30 / 40 / 20 / 40; id 0x0A: 40 / 40 / 20 / 40. So the structure of sections 4 and 5.5 (valid-hero rule, distance bands, hop choice probabilities) applies to all of them, the hop table of section 6 only to the Rabite; the other scripts differ in their main loops and use further ops (ids 1-0x1F each use 3 to 21 opcodes the Rabite does not use) that were **not** decoded here.

## 11. Open questions (no values are claimed)
- The pre-step guard `$C1:2457` (checks hero status bits `0xC57B` and hero animation state 2, can end the step without running ops): read, not understood; it never suppressed the script in any run here.
- The attack hit box and hurt box geometry (fields `obj+0xC0..0xCF` change per animation frame; which of them is the attack box).
- Why `obj+0x190` bit 0x0002 appears after a weapon hit by the hero of the save state and its effect on the stun length; the stun after a normal weapon hit without that bit was not isolated.
- Terrain collision of hops (only the arena wall was met); the arena of the harness is open ground.
- What object id 0xEA is and when it is removed.
- The sign test inside op E3 reads a byte of the stack page when the actor is moving (not decoded; the Rabite uses E3 only at rest).
- The animation tables that carry the per-frame velocities (`bank D1`): the numbers in section 6 are measured, the table format was not decoded.
- Heroes 1 and 2 were made inactive in all runs; the slot order rule is from the code.
- Real-time behavior under slowdown.

## 12. Method and tools
- `tools/ai_sim.py ROM STATE 0 SECONDS [--hero DX,DY] [--ops]`: spawns the monster with the game's spawner `$C0:DE3B` in a map-246 save state and runs the real per-frame routine `$C0:B08C` (NMI waits at `$C1:E0F9`, `$C1:E6AC` stubbed); logs every AI step.
- `tools/ai_ops.py ROM STATE`: executes each handler of the 33 ops on synthetic scripts patched into an in-memory copy of the ROM.
- `tools/rabite_model.py ROM STATE [N]`: exact probability model of the main loop vs. N real AI steps per case.
- `tools/ai_cmds.py ROM STATE 0 data/ai_commands.json`: executes each command and the swing at 1-px distance steps.
- `tools/ai_scripts.py ROM data/ai_scripts.json`, `tools/aidis.py ROM PC LEN --text`: script walker and lister with op descriptions.
- Save states: the map-246 arena state of `docs/rom-combat.md` section 19; the heroes of that state are late-game (hero HP 728), which does not influence the AI.

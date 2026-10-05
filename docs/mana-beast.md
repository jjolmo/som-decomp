# Mana Beast (Secret of Mana USA): boss id 0x7F, monster record 127

Tags: **[V]** reproduced by running the original 65816 code in `tools/mb_sim.py` (whole game frame `$C0:B08C` per frame, three RNG seeds unless noted) or measured on live objects. **[C]** read from the disassembly, read, not executed. **[forced]** a run that set a variable by hand (always stated). Anything not determined is in section 12 without values.

Addressing as in `docs/dark-lich.md`: `$Cx:xxxx` = file offset `((x-0xC0)<<16)|xxxx`. Object fields are offsets from the object record (`$7E:E600 + slot*0x200` for the C2 engine slots 0-8; the Mana Beast is slot 0). Numeric tables: `data/mana_beast.json`.

## 1. Time base [V]

- The game frame is one call of `$C0:B08C` with `$56` = 0..4 (`$C0:B070-B08A`). The C2 boss engine `$C2:0003` has a single call site, `$C0:FD12`, reached from `$C0:FC8C`, `$C0:FCB5`, `$C0:FCDE` only when `$ED` bit 7 and `$5C` bit 7 are set (`$5C` = 0x80 is written by the map-object spawner `$C0:DE0D` for ids 0x57-0x7F) and only for `$56` = 0, 1, 2 [C]. Inside, an object runs when `(flags_hi ^ $56) & 3 == 0` or flag 0x4000 is set (`$C2:0DB2`) [C].
- Mana Beast flags `0x180D` (high byte 0x18): ticks at `$56` = 0 only, **one tick per 5 frames = 12.02 ticks/s** (1 tick = 83.2 ms). Measured: phase 8 lasts 295 frames = 59 ticks; 4,400 frames give 880 ticks [V]. Second object (flags `0x3921`) ticks at `$56` = 1, third (flags `0x2A20`) at `$56` = 2, the four palette-effect objects (flags `0x6000`, bit 0x4000) on every call (3 per 5 frames).
- The same schedule applies to the Dark Lich (flags `0x9C01`): 12 ticks/s, not 24. `docs/dark-lich.md` and `docs/rom-combat.md` 1.3 were corrected and the Lich timings re-measured with the full game frame (120 ticks in 600 frames [V]).
- A second clock exists: for every active object with `obj+0 != 0` the per-frame object pass (`$C0:E38E` -> `$C2:0006` -> `$C2:0F91`) runs every frame (60.0988 Hz), and it applies the movement routine stored in `obj+0x90` (`$C2:11F4`) [C]. Velocities set by the phases ($3A/$3C x, $3E/$40 y, 16.16 fixed point per frame) act at 60.1 Hz; the phases that add to $2B/$32 directly (6, 0xD) act per tick. Position check: phase 1 (320 frames, vx = 0x3000/65536 px/frame, vy starts at 0x8000/65536 and loses 0x100/65536 per frame) moves (0x108,0x160) to about (0x144,0x138); the run ends at (0x142,0x134) [V].
- Frame/second conversion used below: seconds = frames / 60.0988; ticks measured between the frame the phase variable changes.

## 2. The object [V]

- Spawned by `$C2:0000` from map object id 0x7F (flags `0x180D`, no record pointers: the object is created through `$C2:0D53` with handler `$C2:8F33` in `obj+0x8E` [V]). `$C2:8F33` runs every tick: sets `$186/$187` (MP, max MP) to 99/99, writes `$00211A` = 0xC0 and `$0FAE` = 2, then jumps through the phase table `$C2:8F51` indexed by `$94`.
- Record 127: level 73, HP 9990 (`obj+0x182` = 0x2706 on the first frame), MP 99, Str 99, **Agi 1**, Int/Wis 99, evade 99, defense 450, magic defense 999, element byte 128, status immunity 0x7FFC (`data/monsters.json`). `$1FB` = 0x40 (boss), `$1E5` = 0xFF. The phase code never reads `$182/$184` [C]: no HP threshold exists. A run with HP 100 and runs with the heroes moved to (40,40) and (600,600) produced the same phase timeline as the baseline [V].
- Mode-7 style variables: `$B0` (grows/shrinks in steps), `$B2` (steps), `$B4-$BC` (used in phase 0x10); `$C2:979F` / `$C2:97FD` turn them into the four words at `$02CD/$02CF/$02D1/$02D3` through the sine table `$C2:2A59-2A92` [C]. Their effect on the screen is not verified (section 12).
- Active byte `obj+0` is 1 in phases 0, 8, 1 (until its last tick), 5, 0xE, 0xD, 6, 0xB, 0xC, 0xF, 7, 0x11, 0x12, 0x13, 0x10 and 0 in phases 2, 3, 4, 9, 0xA [V]. It is set to 0 at the end of phase 1 and back to 1 at the end of phase 0xA.
- The animation script id in `$9A` is played by `$C2:13EB` (ops in `$C2:142E`, decoder `tools/mb_anim.py`). The ids used by the phases (0x110-0x117) are loops of single sprite frames; id 0x111 also moves the object by (dx,dy) steps whose net effect is about -26 px in x (phase 2 duration = the length of that script, 9 ticks) [V].

## 3. Phase graph [V]

```
spawn -> 0 -> 8 -> 1 -> 2 -> 3 -> 4 -> 9 -> A -> 5 -> E -+-> 6 -+-> B -> C -> F -> 7 -> 11 -> 1 (cycle)
                                                           +-> D -+     |
                                                                         +-> 12 -> 13 -> 10 -> object removed
```
Phase 0x14 (handler `$C2:977B`) has no store of 0x14 into `$94` anywhere in the handlers [C]; it is never entered. The loop 1..11 repeats until the dead bit is seen in phase 0xB (section 8).

## 4. Phases (ticks as measured: 1 tick = 5 frames = 0.0832 s)

| ph | handler | duration | what it does | exit |
|---|---|---|---|---|
| 0 | 8F7B | 1 tick | `$00`=1, `$94`=8, `$0B`=2, matrix, creates the two helper objects (section 9) | immediately -> 8 |
| 8 | 924B | 59 ticks (295 f, 4.91 s) | stands at its spawn position, targetable (the map record's `16 * tile`: (0x120, 0x120) in the real map 253, [V] `docs/cutscene-mana-beast-intro.md`; (0x120, 0x150) in the harness run of this document, which spawned the boss with the Dark Lich record of map 246) | `$96`>=0x3C: pos (0x108,0x160), `$B0`=0, anim 0x114, vx 0x3000/65536 px/f, vy 0x8000/65536 px/f, motion routine 8FED, 4 palette-effect objects, sound request 0xD6 -> 1 |
| 1 | 8FB3 | 64 ticks (320 f, 5.32 s) | `$B0` += 0x20 per tick; motion 8FED every frame (x +11.3 px/s, y rises then falls: vy -14.1 px/s^2) | `$B0`>=0x800: `$00`=0, `$90`=0, `$B0`=0x200, anim 0x111 -> 2 |
| 2 | 9027 | 9 ticks (45 f, 0.75 s) | anim 0x111 plays (moves about -26 px in x) | `$9E`==0: anim 0x112 -> 3 |
| 3 | 904E | 60 ticks (300 f, 4.99 s) | waits at (0x128,0x138) | `$96`==0x3C: `$B0`=0x300, anim 0x116, palettes 0x62-0x65 into 4-7, sound 0xD6 -> 4 |
| 4 | 90AC | 32 ticks (160 f, 2.66 s) | per tick `$B2` += 0x80, `$B0` -= 0x18 | `$B0`<0x10: **attack row 0x72**, forced hit on all heroes (section 6), `$B0`=0 -> 9 |
| 9 | 92A8 | 12 ticks (60 f, 1.00 s) | waits | `$96`>=0xC: `$B0`=0x200, anim 0x112, palette 0x66 into 4-7 -> 0xA |
| 0xA | 92F6 | 60 ticks (300 f, 4.99 s) | waits | `$96`==0x3C: `$00`=1, `$B0`=0x800, anim 0x113, vy 0xC000/65536 px/f with motion routine 9158 (y only, same -1/256 px/f^2), 4 palette-effect objects, sound 0xD6 -> 5 |
| 5 | 910E | 33 ticks (165 f, 2.75 s) | `$B0` -= 0x40 per tick; y rises then falls (0x138 -> 0x17F) | `$B0`<0: x=0, `$B0`=0x80, anim 0x117, **attack row 0x71**, forced hit on all heroes, graphics request 0x1F, `$B6`=1 -> 0xE |
| 0xE | 94BE | 9 ticks (45 f, 0.75 s) | waits (loads graphics set 0x1F once when `$0364`!=0) | `$96`>=9: anim 0x110; `rand(0x10)` (returns 0..16) < 7 -> phase 6 at (0x128,0x70); else phase 0xD at (0x128,0x250). Of the 256 byte values of the RNG 106 give 0..6 [C]; seeds 1,3 took 0xD, seed 2 took 6 [V] |
| 6 | 917F | 121 ticks (605 f, 10.07 s) | y += 2 per tick (24.0 px/s) from 0x70 down | y>0x160 -> 0xB (`$96`=0) |
| 0xD | 9499 | 120 ticks (600 f, 9.98 s) | y -= 2 per tick (24.0 px/s) from 0x250 up | y<=0x160 -> 0xB |
| 0xB | 9381 | min. 240 ticks (1,200 f, 19.97 s) + cast pauses | stationary at (0x128,0x160); spell AI every 49 ticks (section 7) | dead bit -> 0x12; `$96`>=0xF0 -> 0xC |
| 0xC | 9463 | 17 ticks (85 f, 1.41 s) | `$B0` -= 8 per tick from 0x80 | `$B0`<0: x=0, `$B0`=0x80, anim 0x117, graphics request 0x20 -> 0xF |
| 0xF | 9539 | 9 ticks (45 f, 0.75 s) | waits (graphics 0x20 once) | `$96`>=9: x=0x228, **vx = -8 px/frame** (-480.8 px/s), motion routine 9224, `$B0`=0x80, anim 0x115, sound 0xD6 -> 7 |
| 7 | 91A4 | 13 ticks (65 f, 1.08 s) | flies right to left at 8 px/frame; when x<0x128 once: **attack row 0x6F** and `$59`=1 on all heroes (section 6) | x<=0x28: `$90`=0 -> 0x11 |
| 0x11 | 964B | 12 ticks (60 f, 1.00 s) | waits at x=0x20 | `$96`>=0xC: same set-up as the end of phase 8 (pos (0x108,0x160), anim 0x114, 8FED, palette-effect objects) -> **1** |
| 0x12 | 96A5 | 1 tick | waits for the boss `$60` low byte == 0 (end of a cast) | `$60`=0x20, the four palette objects set to palette 0x87, graphics 0x27, command 0x8B00 via `$C2:3963`, sound request 0xF0 -> 0x13 |
| 0x13 | 96F8 | 52 ticks (260 f, 4.33 s) | every 4th tick an explosion object (`$C2:0C33`, random offsets), palette rotation each tick, sound request 0x15 about every 20 frames | tick `$96`==0x18: `JSL $C0:006F`; `$96`>=0x34: `$B0`=`$B2`=0x80, 4 palette effects, command 0x8A00 -> 0x10 |
| 0x10 | 95BD | 103 ticks (514 f, 8.55 s) | `$B2` accelerates (`$BA` += 3 per tick, until `$B2`>=0x1000), then `$B0` accelerates (`$B8` += 3 per tick) | `$B0`>=0x1000: the event of the map record started (0x042D with the record of map 246 used by the harness, **0x042F** with the real record of map 253), object removed (section 8) |
| 0x14 | 977B | never entered | - | - |

One lap (phase 1 to the next phase 1) is 64+9+60+32+12+60+33+9+(121 or 120)+240+17+9+13+12 = 691 or 690 ticks, about 3,450 frames = 57.4 s (seed 1: phase 1 at frames 3,876 and 7,326; seed 2: 3,881 and 7,336) [V]. Phase 0xB of the first lap lasts 1,330 frames because of the Wall cast pause (section 7); later laps 1,200 frames.

## 5. Movement summary [V]

| phase | motion | speed |
|---|---|---|
| 8, 3, 4, 9, 0xA, 0xB, 0xC, 0xF, 0x11, 0x12, 0x13 | stationary (position changes only through anim 0x111 and the 8FED/9158 velocities listed above) | 0 |
| 1 | vx 0x3000/65536 px/frame, vy +0.5 px/frame decreasing 1/256 px/frame per frame | 11.3 px/s in x |
| 5 | vy 0.75 px/frame decreasing 1/256 px/frame per frame (9158) | about 45 px/s at the start |
| 6 | y += 2 per tick | 24.0 px/s down |
| 0xD | y -= 2 per tick | 24.0 px/s up |
| 7 | x -= 8 per frame (9224) | 480.8 px/s left |

## 6. Attacks: scripted hits, no contact [V]

- Rows are loaded with `JSL $C0:006C` (`docs/rom-combat.md` section 15.1). Stat = Str 99 + power (8 bit): row 0x72 = 114: power 120, accuracy 99 -> 219; row 0x71 = 113: power 92 -> 191; row 0x6F = 111: power 89 -> 188. Status word 0 on all three (no status is inflicted).
- `$C2:90E4` (end of phases 4 and 5) sets bit 0 of `$59` in the three hero objects and `$5A`=7 in the boss; phase 7 stores 1 in the three `$59` bytes. This is the same hit mask the contact test `$C2:052E`/`$058F` sets, so every hero is hit once through the normal damage code (hit roll against evade and defense apply, no position check). Executed on the save state (heroes HP 728/583/578): row 0x72 hit all three for 122/92/148 HP, row 0x71 for 26/8/48, row 0x6F hit heroes 0 and 2 for 7 and 22 and missed hero 1. The hero object enters hurt state `$60`=0x40 after the hit.
- Contact attacks never occur: the boss and its helpers have no attack or hurt rectangles in `obj+$C0..$CF` (all zero in 2,600 frames; flag 0x8000 is clear so the sprite-derived boxes of `$C2:1A81` are not built and no phase code writes them) [V][C]. Weapons therefore cannot hit it (the hit test needs `$CA|$CE` != 0, `$C2:06FE`) [C].

## 7. Spell AI (phase 0xB) [V]

- Every tick `$AD`++ (`$C2:0F86`). When `$AD` >= `$2D` the action runs: `$C2:3372` sets `$2D` = (100 - Agi)/2 = **49 ticks** (4.08 s), `$AD`=0, then `$C2:93CB`. On entry to phase 0xB `$AD` is already above the threshold (it counts since spawn), so the first action happens on the first tick (frame +4).
- `$C2:93CB` (executed 4,000 times per case with the real RNG):

| boss has Wall (`$1B1` bit 6) | nearest living hero (`$C2:3224`, Manhattan distance) has Wall | result |
|---|---|---|
| no | any | spell 0x22 Wall, parameter 0x0222 (target side = the boss's own side), 4,000 of 4,000 |
| yes | yes | spell 0x26 Dispel Magic, 0x0026 (single target = nearest hero), 4,000 of 4,000 |
| yes | no | `rand(2)` (0..2): 0 -> spell 0x28 Lucent Beam, 0x0028 (1,331 of 4,000, one third); otherwise no cast (2,669) |

  The table at `$C2:9416` has seven entries (Wall 0x22, Defender 0x05, Lunar Boost 0x1C, Speed Up 0x04, Lucid Barrier 0x29, Dispel Magic 0x26, Lucent Beam 0x28, parameters 0x0222, 0x0205, 0x021C, 0x0204, 0x0229, 0x0026, 0x0028); a code block at `$C2:93DD` that would pick entries 1-4 is not reachable from any branch [C]. Only entries 0, 5, 6 occurred.
- The cast: `JSR $C2:396D` (spell id in the low byte, level 7 shown in `$171` = 7 because level 8 runs at 7 for bosses, `docs/rom-combat.md` 5.1; high byte 2 = own side, 0 = single target) then `JSL $C0:001B`. MP is forced back to 99 every tick, so MP never runs out [V] (MP 99 -> 93 after Wall, back to 99 on the next tick).
- While casting, `$60` = 0xC0 and the engine skips the object (`$C0:FD07`). The Wall cast kept `$60`=0xC0 for 130 frames (2.2 s); Lucent Beam casts did not lengthen phase 0xB (lap 2 lasted exactly 1,200 frames with three beams). Damage reaches the hero 189 frames (3.1 s) after the cast frame (3 of 3 casts). Lucent Beam damage observed on this save state: 161, 1 and 126 HP on the targeted hero (hero dependent).
- Wall stays on the boss (`$1B1` = 0x42 from the cast until the end of the 9,500-frame run) [V], so Wall is cast once (first action of the first phase 0xB) and never again in the runs.
- Spell counts per phase 0xB in the runs: lap 1 = Wall + three attempts that all cast Lucent Beam (seed 1); lap 2 = three attempts, three casts (seed 1). With 240 ticks and a 49-tick threshold there are 5 action attempts per phase at most (first at tick 1, then 50, 99, 148, 197) [C].

## 8. Death and end of the fight [V]

- Damage path: pending HP damage `$1F1` is applied by `$C0:4004` through the generic tick `$C0:3A79` (called every tick from `$C2:0F2F`). It is applied in every phase whenever `$60` & 0xE0 == 0 (injected 3-point hits were applied in phases 8, 1, 2, 3, 4, 9, 0xA, 5, 0xE, 0xD, 0xB, 0xC, 0xF, 7, 0x11 [forced injection]); during the boss's own cast (`$60`=0xC0) and during its hurt state (`$60`=0x40, which is not cleared while `obj+0` is 0) the damage waits.
- At HP 0 the generic code sets the dead bit (`$190` = 0x8000, i.e. `$191` bit 7) at once [forced: HP 5, pending 50]; the phase machine does not react immediately. **Only phase 0xB reads `$190`** (`BMI` at `$C2:9386`). A dead bit set at frame 500 (phase 3 [forced]) did not change anything until the next entry into phase 0xB (frame 2,291), where the boss went to phase 0x12 on the first tick, without casting.
- With the dead bit set during a phase 0xB at frame 2,400 [forced]: phase 0x12 (after the running cast ended) -> 0x13 (52 ticks, 4.33 s) -> 0x10 (103 ticks, 8.55 s). Total from the first tick of phase 0x12 to the removal: 156 ticks, about 13 s. At the end `$C2:0C11` loads `obj+0x72` (= the event word of the map record: 0x042D with the record of map 246 that the harness used; **0x042F** with the real record of map 253, where the VM's first step comes 3 frames after the removal, `docs/cutscene-ending.md` section 2) into the event runner `$C1:8000` (`JSL $018000`, A = that event) after setting bit 7 of the first nonzero byte of `$D9-$DB`; the object returns carry set and the dispatcher frees the slot (`$C2:0E25`).
- `JSL $C0:006F` at tick 0x18 of phase 0x13 (executed): changes `$1D04` (0x00 -> 0x44), clears the 0x20-word buffer area at `$7E:9C2D-9DFD`, rewrites `$0381-$0386`, `$0A17C-$0A1D0`, `$0E144-$0E154`; its purpose is not determined.
- The only other end of the Mana Beast object is this one. No flag write other than those listed was found in the phase code [C].

## 9. Helper objects [V]

Created by phase 0 through `$C2:0D53` (slot search from slot 3 because of flag 0x2000/0x20):

| slot | flags | handler | what it does |
|---|---|---|---|
| 3 | 0x3921 | 986D | tick 1: position (0x128,0x190), `$00`=1, anim 0x172; every tick (12 Hz at `$56`=1) it rotates the four palette words at `$07B8-$07BE` and `$07D8-$07DE` by one place (observed every 5 frames) |
| 4 | 0x2A20 | 3D34 | first tick: `JSL $C0:009F` re-initialises its own sprite fields (`$00`=0, pos (0x68,0), anim 0x17A) and stores its pointer in `$1D14` (= 0xEE00) and `$1D16` (= 0xFA00); afterwards `JSL $C0:00A2` (a return) every tick |
| 5-8 | 0x6000 | 274C | created by `$C2:272D` four at a time (ends of phases 8, 0xA, 0x11): palette-effect workers (copy a palette row into 4-7) |

Both flags have bit 0x2000, so `$C2:0DB2` skips the contact/damage block (`$C2:0F27`) for them: **they cannot be hit and cannot hit**. The slot-3 sprite object does have boxes in `$C0-$CF` (a sprite-derived attack/hurt pair) but they are never tested. Explosion objects of phase 0x13 reuse free slots.

## 10. Invulnerability and targeting [V]

- Weapons: never (no hurt rectangle, section 6).
- Hero hostile spells use the target builder `$D0:DA60` (list of the three monster slots). Executed on a copy of the WRAM every frame: the boss is a valid target when `obj+0` == 1, screen x (`$20`) in [8,0xF8), screen y (`$22`) < 0xD8 and the dead bit is clear. Result per phase (seed 1, frames targetable / frames in phase): 8: 295/295, 1: 640/640 (two laps), 2: 0/90, 3: 0/360, 4: 0/160, 9: 0/60, 0xA: 0/300, 5: 165/165, 0xE: 0/45, 0xD: 430/600 (not targetable while screen y >= 0xD8, the first 170 frames), 0xB: 1330/1330, 0xC: 85/85, 0xF: 0/45, 7: 30/65 (only part of the flight, while screen x is inside the window), 0x11: 0/60.
- Phases 2, 3, 4, 9, 0xA (obj+0 = 0) and the first 170 frames of phase 0xD and 0xE, 0xF, 0x11 are therefore windows in which a hostile hero spell has no valid target, although pending damage would be applied.
- The boss's own Wall (`$1B1` bit 6) is set by its first cast; whether and how hero spells are reflected by it is not part of this document (section 12).
- No HP-dependent behaviour: runs with HP 100 and 9990 are identical [V]; the handlers do not read HP [C].

## 11. Does the Mana Beast run the enemy AI bytecode? [V]

No. The map-object table entry of id 0x7F points to an ordinary monster script, but the AI step `$C1:2552` is never called with a C2 slot object: in 4,400 frames it ran only for X = 0x0000 and 0x0200 (hero slots 0 and 1, the party AI) and never for 0x0600-0x0E00 (slots 0-8 of the boss engine). Objects of the C2 engine are not stepped by `$C0:F4CB` on this map ($5C bit 7 set), where the AI step lives [C]. The slot-3 and slot-4 helper objects do not run it either.

## 12. Open questions (no values)

- What the mode-7-style variables look like on screen, and the purpose of `$02D5/$02D7`, `$0FAE`, `$00211A`.
- Meaning of the sound requests (ids 0xD6, 0xF0, 0x15) and graphics requests (0x1F, 0x20, 0x27) and of the commands 0x8A00/0x8B00.
- Contents of event 0x042F: decoded and run in `docs/cutscene-ending.md`. `JSL $C0:006F`: who reads `$1D14/$1D16` set by the slot-4 object.
- How a hostile hero spell interacts with the boss's Wall, and whether the spell reflection returns damage to the caster; the full hero-side damage numbers (only injected damage and boss-to-hero damage were executed).
- Whether `$C2:93DD` (entries 1-4 of the spell table) is ever reached by a path through indirect jumps.
- Why the hurt state `$60`=0x40 is cleared only while `obj+0` is 1 (code that clears it not located).
- Whether map-event code outside the C2 phase handlers ever writes `$94` (not searched).
- Real-hardware timing under slowdown.

## 13. Method and tools

- `tools/mb_sim.py ROM STATE FRAMES [SEED] [hp=N] [hero=X,Y] [force=P@F] [dead=F]`: spawns the boss with `$C2:0000` in the map-246 state and runs the real main-loop body `$C0:B08C` per frame (NMI wait loops `BIT $EC` released; sound driver and PPU not emulated); logs phases with frame/tick counts, attack rows, spell requests, object creation, events, hero and boss HP/flag changes.
- `tools/mb_anim.py ROM ID[,ID]`: decodes the animation scripts (argument counts of the ops measured by running the handlers).
- `tools/statescript.py`, `tools/disasm65.py`, `tools/flowdis.py`, `tools/cpu65816.py`: as in the Dark Lich document.
- Experiments of this document: baseline laps (seeds 1-3, 9,000 frames), `dead=` runs, HP/hero-position runs, damage injection in every phase, `$C2:93CB` called 4,000 times per case, target-builder sampling every frame.

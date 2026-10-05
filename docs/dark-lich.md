# Dark Lich (Secret of Mana USA) - behavior extracted from the ROM

Tags: **[V]** verified: reproduced by running the original 65816 code in `tools/lich_sim.py` (whole game frame `$C0:B08C`; time base corrected, see section 2), or read from a ROM data table and cross-checked with the live engine object. **[C]** read from the disassembly, read, not executed. Items that are not determined are listed in section 6.

Addressing: the ROM is a 2 MiB HiROM image (header at 0xFFC0, no copier header). `$Cx:xxxx` for banks C0-DF = file offset `((x-0xC0)<<16)|xxxx`, so `$D0:1C00` = 0x101C00. Bank DC data (`$DC:xxxx`) = file offset 0x1Cxxxx.

## 1. How the Dark Lich is built (key finding)

- Enemy id 0x79 [V] (= 121; map object record byte +0xD; the arena is map 246, record at WRAM `$7E:C820` in the map-246 save state).
- Bosses (ids 0x57-0x7F) do NOT use the AI bytecode of the object table (`ROM 0x100000 + id*16`, script base 0x104F15). Their entries are identical filler. [C]
- Boss spawn path [C]: map object spawner `$C0:DE02` sees id in 0x57..0x7F -> `JSL $C2:0000` -> `$C2:0040` scans map objects, and for each boss id runs the loader script whose address is in two tables: `$C2:00EE + (id-0x54)*2` (A) and `$C2:0146 + ...` (B). Loader scripts live in bank C1 (interpreter `$C2:21B7`, ops table `$C2:21DA`). Lich: A = `$C1:64DC`, B = `$C1:64E0` (graphics/palette loads + `19 08 00` = create object record index 8).
- Object record 8 (`$C2:E82E`, built by `$C2:3438`) holds native handler pointers [C]: flags word 0x9C01; init `$C2:6DE7`; chooser `$C2:6DFB`; periodic action `$C2:6E82`; hurt response `$C2:6EBA`; first state sequence `$E848`; default hurt sequence `$E84A`; state script table `$C2:E896`.
- Behavior is therefore NATIVE 65816 code (`$C2:6DE7-$C2:73xx`) + tiny per-state scripts (`$C2:E8F6-$C2:EB4x`, decoder `tools/statescript.py`, opcode table `$C2:37CC`) + selection tables in bank DC (`$DC:E461-$DC:E4A8`). No HP-dependent logic exists in the Lich code (no reads of the HP fields in `$C2:6DE7-$C2:73FF`). [C]
- Generic object state machine `$C2:34B9-$C2:36B2` drives it: `obj+$94` phase, `$B0/$B2` current state sequence/index, `$82` mode (0 = action, 1 = movement/chooser, 2 = hurt), `$14` state duration, `$96` ticks in state, `$AD` ticks since last action reset, `$2D` action threshold. [C]

## 2. Time base

- Main loop (`$C0:B06C-B08A`) keeps `$56` counting 0..4 once per frame and calls the frame body `$C0:B08C`. [C]
- The C2 boss engine `$C2:0003` has a single call site, `$C0:FD12`, reached from `$C0:FC8C`, `$C0:FCB5`, `$C0:FCDE` (when `$ED` bit 7 and `$5C` bit 7 are set; `$5C` = 0x80 is written by the spawner `$C0:DE0D` for boss ids): **it is called only for `$56` = 0, 1, 2**. [C]
- Enemy loop `$C2:0DB2` runs an object's logic only when `(flags_hi ^ $56) & 3 == 0` (or flag 0x4000 set). Lich flags = 0x9C01, high byte 0x9C -> `&3 == 0` -> ticks at `$56` = 0 only: **one tick per 5 frames = 12.02 ticks/s**, 1 tick = 83.2 ms. [V: 120 ticks in 600 frames of the full-frame simulation]
- Correction: an earlier version of this document and of the simulator called `$C2:0003` for every `$56` value (ticks at `$56` = 0 and 4 = 24 ticks/s, 41.7 ms). That call pattern does not exist in the game; every duration given in ticks was therefore half as long in seconds as it really is. All seconds below were re-measured with the corrected harness.
- 36 ticks (the standing/walking script duration `0x24`) = 185 frames = **3.08 s** measured (36 ticks + the entry tick). [V]
- `obj+$2D` (action threshold) = `(100 - Speed)/2` ticks, `$C2:3372`. Lich Speed (agi) = 1 -> 49 ticks = 245 frames = **4.08 s**; the first action happened at frame 251 (4.18 s). [C, V for the first action]
- Movement has two clocks: walking states move with the per-tick callback (`F48` op, `$C2:36BC`), 1 px per tick = **12.02 px/s** (12 px in 13 ticks, [V]); the hands states use the per-frame routine (`SPEED90` op sets `obj+$90` = `$36BC`, run by the object pass `$C2:11F4` every frame): 1 px per frame = **60.1 px/s** (123 px in 125 frames, [V]).

## 3. Stats [V]
Stat record `0x101C00 + 0x79*29` (= 0x1029B5): level 72, HP 6666, MP 99, Str 74, Agi/Speed 1, Int 96, Wis 96, Eva 99, Def 200, MEv 99, MDef 423, type byte 0x20, element byte 0x10, weapon level 5, magic level 8 (also visible in the live engine object after spawn). Attack power in the object after init: 74 (Str) + 35 (weapon base) = 109; weapon-row accuracy byte 0x63. The damage formula is now documented in `docs/rom-combat.md` (§4; the Lich's basic attack is boss-attack row 0: power 35, accuracy 99, status 0x4000 at 99%).

## 4. State machine (read from the state-script tables and native code; durations marked [V] were measured with `tools/lich_sim.py` / `lich_stats.py` on the whole game frame, 8 seeds x 12,020 frames = 200 s each, heroes' weapon hits switched off and heroes immortal; seconds = frames / 60.0988)

States (decoded from `$C2:E896` table; run `tools/lich_dump.py ROM`):

| State | Meaning | Duration |
|---|---|---|
| 00,01,02 | stand facing target (variants) | 36 ticks = 3.08 s (state 02 at spawn: 185 frames), or cut at the action threshold (13-50 ticks seen = 1.08-4.16 s) [V] |
| 03-06 | walk toward target (1 px per tick = 12.02 px/s) | same [V] |
| 07 | hurt (body), after an injected hit | 1 tick = 5 frames = 0.083 s [V] |
| 08 (spell 0x24), 09 (0x08), 0A (0x25), 0B (0x26), 0C (0x13), 0D (0x00), 0E (0x06) | spell casts (spell ids index `data/spells.json`); magic level 8 | 11, 14, 13, 14, 12, 17, 15 ticks = 0.92, 1.16, 1.08, 1.16, 1.00, 1.41, 1.25 s; the spell is launched when the state ENDS (`$C2:0210-0221`) [V] |
| 0F-17 | 9 projectile attacks: SPAWN types 9,8,0x17,0x0F,0x16,0x10,0x12,0x0E,0x0F (type 0x0F appears twice, so it has 2/9 probability) with a sound each | 37 ticks = 185 frames = 3.08 s; projectile is spawned at state START [V] |
| 18,19,1A | body -> hands transition (palette fade, 3.08 s + 3.08 s + 1 tick, sets `$7E` bit0 = hands) | 6.2 s [V] |
| 1B,1C,1D | hands -> body transition (clears `$7E`) | 6.2 s [V] |
| 1E-23,26,27 | hands movement/poses (1F and 26 move 1 px per FRAME for 25 ticks = 2.08 s; 20 sets `$7E` bit15 = hands raised, 23 clears it); 1E and 21 are cut by the action threshold | 1F, 26: 2.08 s; 20: 0.33 s; 23: 0.08-0.33 s; 1E: 2.08-4.16 s; 21: 0.75-4.08 s [V] |
| 24 | hands slam/attack (anim only) | 17 ticks = 85 frames = 1.41 s [V] |
| 25 | hurt (hands) | 21 ticks = 1.75 s in the only sample (a run with party hits); not re-measured |

Selection logic [C] (native code `$C2:6DFB` chooser, `$C2:6E82` action, `$C2:6EBA` hurt):
1. When a state sequence ends: if `$AD < $2D` -> run the chooser (mode 1); otherwise reset and run the action routine (mode 0). Movement states are cut short as soon as `$AD >= $2D` (`$C2:367C-36A4`). After an action `$AD` restarts at 0.
2. Body chooser (hands flag clear): `rand(0..4)`; 0 (20%) -> start body->hands transition (18,19,1A). Else: nearest living player by Manhattan distance (`$C2:3224`, `|dx|+|dy|`), if distance/16 < 8 (i.e. < 128 px) -> face states `[02,00,01,00]` by 4-dir code, else walk states `[06,03,05,04]`.
3. Hands chooser: if `$7E` bit15 clear: `rand(0..4)==0` -> hands->body transition (1B,1C,1D); else by direction states 1F/26 (dir 1/3) or random of `[1E,20]`; if bit15 set: dir tables give 22/27, else random `[21,23]`.
4. Action routine, body phase: toggles `$7E` bit15 on every call; bit15 becomes SET -> projectile attack `rand(0..8)` uniform over states 0F-17; bit15 CLEAR -> spell `rand(0..6)` uniform over 08-0E. So actions strictly alternate projectile / spell; the first action after (re)entering the body phase is always a projectile (the toggle bit is cleared by state 1D and at spawn). Hands phase action: state 24 slam, only while bit15 is clear.
5. Spawn: no cast on spawn. State 02 for 37 ticks = 3.08 s, then chooser; first action at 4.18 s (frame 251) unless the first chooser call picks the hands transition (20%). [V]
6. Hurt reaction [V, re-run with the corrected harness, flag injected]: `$C2:0501` consumes bit0 of `obj+$34`. In mode 1 (movement) the hit interrupts: a hit injected at frame 40 gave mode 2 at frame 41, state 07 at frame 46 (1 tick = 0.083 s) and the first action at frame 51 (0.85 s after the hit); `$2D` is set to 0 so an action routine (spell/projectile alternate) fires right after the hurt state, `$AD` reset. In mode 0 (any action or transition) hits cause NO reaction (hits injected at frames 255 and 260 inside a projectile state and at 440 and 445 inside a transition were ignored). With the party's weapon hits enabled (the full frame runs the party AI) the state 07 / mode 2 segment lasted 21 ticks (1.75 s) in 11 of 11 occurrences, before a spell or a projectile; why it lasts longer than after an injected hit is not determined. The ROM sets no invulnerability flag anywhere in the Lich code; damage application is done by the generic actor code (`$C0:3A79`...), not decoded here.
7. Measured over 8 simulated runs x 200 s (different RNG start): body phase 9.3-64.6 s (mean 23.5 s, 37 phases), hands phase 7.7-37.6 s (mean 15.4 s, 33 phases); 2.9 actions per body phase (0-10), 2.1 per hands phase (1-6); action-to-action gap 5.1-5.6 s after a spell, 7.2 s after a projectile (3.08 s state + wait for the 49-tick threshold), 5.6-5.9 s after a hands slam; transition chance per chooser call 20% [C]. [V by simulation, depends on RNG; exact values vary]

## 5. Open questions
- What the 8 projectile types are: only the SPAWN type ids and sounds are known. Damage and status per state are in section 8.
- Which hits set the hit flag; the hands hitbox.
- Visual details (sprite frames), HDMA/palette effects of the transitions.
- Behavior when slowdown/lag occurs on real hardware.
- Why the hurt segment (state 07, mode 2) lasts 21 ticks after natural party hits but 1 tick after an injected hit; the hurt duration of state 25 (hands).
- Whether the party's weapon hits change the phase statistics (the statistics above switch them off).

## 6. Method and tools
- `tools/lich_sim.py`: runs the whole game frame (`$C0:B08C`, `$56` = frame mod 5, NMI wait loops released) from a ZSNES save state taken in the arena (WRAM at offset 0xC13, map 246), spawning the Lich with the game's own routine; the party's weapon hits are switched off (`$C2:052E` reports no contact) and the heroes' HP is refilled each frame by default; sound driver/PPU not emulated; RNG is the game's own table RNG (`$C2:300B/302C`).
- `tools/lich_stats.py`, `tools/lich_events.py`, `tools/lich_hit_test.py`, `tools/lich_walk_test.py`: experiments used above.
- `tools/lich_dump.py ROM`: prints record, sequences, tables and all state scripts.
- `tools/statescript.py`, `tools/disasm65.py`, `tools/cpu65816.py`, `tools/romio.py`: decoder, disassembler, CPU core, ROM loader (all take the ROM path as first argument).

## 7. Side notes: enemy AI bytecode (not used by bosses)
Regular enemies (ids 0x00-0x56) use a bytecode (`$C1:2257` handler table, script base 0x104F15); `tools/aidis.py` lists it (conditional ops: 1 + operand bytes + 1-2 byte offset; jump offsets 7-bit signed or 15-bit signed big-endian). The 33 opcodes of the Rabite script are decoded and executed in `docs/rabite.md`; the other opcodes are not described. Bosses can ignore it.

## 8. Attacks per state (boss attack rows, added in the second pass) [V]
Each state script sets the attack row of the hit with op `0x13` (`C0_006C` in `tools/statescript.py`, = `JSL $C0:006C`); rows are in `data/boss_attacks.json`, loaded by `$C0:45D6` into `E194/E197/E198/E199/E1F7` (all 115 rows were checked against the real routine). Lich attack stat = `74 + power` (8 bit). Chance = chance to inflict the status on a damaging hit (`rnd(100) < chance`, not blocked by the hero's immunity word). Tick = 5 frames = 0.083 s (section 2).

| state | SPAWN type | row | power | attack stat | status |
|---|---|---|---|---|---|
| 0F | 9 | 64 | 89 | 163 | 0x2000 99% |
| 10 | 8 | 59 | 89 | 163 | 0x0010 99% |
| 11 | 0x17 | 76 | 89 | 163 | 0x0004 99% |
| 12 | 0x0F | 15 | 89 | 163 | 0x0040 99% |
| 13 | 0x16 | 74 | 89 | 163 | 0x0200 99% |
| 14 | 0x10 | 71 | 89 | 163 | 0x0080 99% |
| 15 | 0x12 | 73 | 89 | 163 | 0x0100 99% |
| 16 | 0x0E | 14 | 93 | 167 | 0x0020 99% |
| 17 | 0x0F | 15 | 89 | 163 | 0x0040 99% |
| 1E-23, 24, 26, 27 (hands) | - | 110 | 127 | 201 | 0x0010 99% |

Spells (state 08-0E) are single-target (spell parameter flags 0): damage as in `docs/rom-combat.md` section 5 with Int/Wis 96 and spell power 44 (record bytes 18/19), at spell level 7 (level 8 runs at 7 for bosses); divisor 1 (section 14 there); the attack-row map of all bosses is in section 15 there.

# The ending after the Mana Beast (event 0x42F and the sequence it starts)

Tags: **[V]** measured by running the original 65816 code frame by frame with `tools/event_runs.py` on top of `tools/event_vm.py` (the harness and its limits are in `docs/cutscene-engine.md` section 10; the real frame body `$C0:B08C`, the map loader, the event VM `$C1:E8D3`, the text engine, the boss engine and the loop of the world-map mode `$C0:8064` run, the PPU, VRAM/CGRAM/OAM DMA and the sound CPU do not); **[C]** read from the disassembly, not executed. Numbers: `data/cutscene_ending.json` (written by `tools/event_runs.py ROM STATE ending OUT.json leader=0 frames=150000`). Everything that is not known is in section 12 without values.

Time: **frames** of 1/60.0988 s counted from frame 0 = the frame in which the Mana Beast's phase variable `$94` becomes 0x12, i.e. the tick of phase 0xB that sees the dead bit. The VM steps every fifth frame, so its commands run at frames = 3 mod 5 in the arena (as in `docs/cutscene-mana-beast-intro.md`) and at frame = (load frame + 4 + 5 k) after every map load. Seconds are frames / 60.0988. Button presses are assumed to happen in the first frame the VM waits for one: every dialog time is the minimum.

## 1. Summary

| frame | s | what |
|---|---|---|
| -5 | -0.08 | phase 0xB is entered (end of phase 0xD, position (296, 352)) |
| 0 | 0.00 | tick of phase 0xB: the dead bit is seen, `$94` = 0x12 |
| 5 | 0.08 | tick of phase 0x12 (it waits for the end of a cast: none here), `$94` = 0x13: sound request (raw command 0x80, parameter 0xF0), screen jitter `$49` = 0xE0 |
| 26-206 | 0.43-3.43 | seven explosion objects (two at a time, 40 frames each) around the Mana Beast at (296, 352), sound effect 0x15 at each creation; two palette-effect objects at 226 and 246 (sound effect 0x15 again) |
| 265 | 4.41 | phase 0x10 (the mode-7 style variables `$B0`/`$B2` accelerate, 515 frames); the jitter stops |
| 780 | 12.98 | **the Mana Beast object ends**: `$C2:0C11` locks the pad of the controlling hero and starts the event stored in its map record, **0x42F** |
| 783 | 13.03 | first VM step: `FLAG_INC 0x4E` (8 -> 9), `FLAG_INC 0xFF`, GOTO 0x3FF -> GOTO 0x4FD (the 2,834-byte ending script): FREEZE |
| 788-803 | 13.11-13.36 | GATHER (girl and sprite run to the controlled hero), sound effect 0x8B, raw sound command 0x80 / 0x80 |
| 808-1053 | 13.45-17.52 | palette fade `SCREEN 6` 0x3FFF (add, red and green 31, blue 15), 240-frame wait |
| 1063-1093 | 17.69-18.19 | canned event 0x41E: clears the status words `obj+0x190/0x191` of the three heroes, refills HP and MP, resets their statuses |
| 1098-1108 | 18.27-18.44 | `ACTOR_DELETE` slots 1 and 2, `ACTOR_CLONE` slot 1 from the controlled hero |
| 1113 | 18.52 | `MAP_CHANGE_D` arg 0x7E: fade-out (29 frames), then the game leaves the map mode |
| 1141-1652 | 18.99-27.49 | **world-map mode** (BG mode 7) for 511 frames (8.50 s); the VM is not stepped; sound effect 0x16 at 1388 and 1644 |
| 1652 | 27.49 | map 8 (256 x 224) loaded by the world-map code; music 0x3A (1671); 240-frame wait |
| 1916 | 31.88 | `MAP_CHANGE` transition 1023 -> map 180 (544 x 256): the first of 16 staff-roll scenes (frame 1973) |
| 1973-25022 | 32.8-416.3 | maps 180, 148, 149, 150, 108, 147, 146, 106, 151, 105, 152, 153, 104, 103, 102, 101 (sections 4 and 7): 18 staff-roll text blocks (1,897 bytes), walks, canned animations, music 0x32 (frame 9539), music 0x3A again (23736) |
| 25079 | 417.30 | `MAP_CHANGE` transition 620 -> map 107 (832 x 768): last scene |
| 25648 | 426.76 | `SCREEN 6` 0xFFFF: fade to black |
| 25973 | 432.17 | `GOTO 0x047` -> `PARTY_CMD` 0x11: **the game restarts** through the reset path (section 10) |

Total from the first tick of phase 0x12: **25,973 frames = 432.17 s (7 min 12.2 s)**; the event itself runs from frame 783 to 25973 (25,190 frames, 419.1 s). With the girl or the sprite as the controlled hero the total is 25,978 frames (section 9).

The run starts after the intro (`docs/cutscene-mana-beast-intro.md`) and a natural fight of the Mana Beast with the heroes' HP refilled every frame and the dead bit set by hand 10 frames after control returned; the dead bit is only read in phase 0xB, which this run entered at frame -5 (abs. frame 5,340 of the harness, 2,252 frames = 37.5 s after control returned) and read at frame 0. Positions of the heroes at the start are therefore those the intro left them in (section 5).

## 2. The Mana Beast's death sequence (frames 0-783) [V]

| frame | s | what |
|---|---|---|
| -5 | -0.08 | phase 0xD ends, phase 0xB is entered (position (296, 352) = (0x128, 0x160)) |
| 0 | 0.00 | the tick of phase 0xB sees the dead bit (`BMI` at `$C2:9386`) and sets `$94` = 0x12 |
| 5 | 0.08 | the tick of phase 0x12 (one tick) sets `$94` = 0x13: raw sound command (`$1E00` = 0x80, `$1E01` = 0xF0, parameter bytes 0x00 0x99); `$49` = 0xE0 (jitter) |
| 26, 46 | 0.43, 0.77 | first two explosion objects (object id 0x3F in slot 10, id 0x21 in slot 11) are created at (0, 0) and placed 4 frames later; each lives 40 frames; sound effect 0x15 (parameter bytes 0x0F 0x00) at each creation |
| 86, 106, 146, 166, 206 | 1.43-3.43 | the same pairs again; creation frames of the explosion objects: slot 10 at 26, 86, 146, 206, slot 11 at 46, 106, 166; placements (x, y): (273, 292), (311, 351), (298, 306), (306, 298), (317, 318), (275, 344), (274, 348) |
| 226, 246 | 3.76, 4.09 | two palette-effect objects (slots 8 and 9, id 0x00, removed at 266 and 286); sound effect 0x15 at 226 and 246 |
| 265 | 4.41 | phase 0x10 begins; `$49` = 0 (jitter off) |
| 780 | 12.98 | phase 0x10 ends (103 ticks = 515 frames): the Mana Beast object (slot 3, id 0x7F) is removed; `$C2:0C11` sets bit 7 of the controlling pad's byte (`pad_locked`) and starts event 0x42F (`JSL $01:8000`, A = the record's event word & 0xFFF = 0x42F) |
| 783 | 13.03 | the VM's first step: `FLAG_INC 0x4E` |

Phase lengths 5 (0x12), 260 (0x13) and 515 (0x10) frames are those of `docs/mana-beast.md` section 4 (1, 52 and 103 ticks) [V]; the whole sequence from the tick that sees the dead bit to the removal is 780 frames (12.98 s) plus 3 frames until the VM steps. The map record of the Mana Beast (map 253, record 0) carries the event word 0x442F; `docs/mana-beast.md` quoted 0x042D, the word of the Dark Lich record of map 246 where its harness spawned the boss. The explosion placements come from the boss engine's random numbers (`$C2:0C33`); they are listed for the state of the RNG of this run.

## 3. The scripts

- **Event 0x42F** (bank `$CA:155F`, 7 bytes): `FLAG_INC 0x4E` (8 -> 9), `FLAG_INC 0xFF` (**boss freeze**, `$CFFF` bit 0; irrelevant, the boss is gone), `GOTO 0x3FF`, `END` [V].
- **Event 0x3FF** is the last entry of the bank-`$C9` pointer table (`$C9:F2D4`, 3 bytes): `GOTO 0x4FD`, `END`. The table's own end marker is the next word, which is script data, so the generic extent rule gives an empty script for it; the event has to be decoded from its pointer [V: runs].
- **Event 0x4FD** (`$CA:4D95-$CA:58A6`, 2,834 bytes, 382 commands, 38 text blocks, no conditional command): the ending script. It runs linearly, **381 of its 382 commands execute, each exactly once** (the `END` after the final `GOTO` is never reached; 479 command executions in all with the called events), and it ends with `GOTO 0x047`. The commands that `docs/cutscene-engine.md` listed as "stall" opcodes in this event were the staff-roll text (section 6): the static decoder did not know the credits segments (`0x7D` ... `0x7E`) and read their ASCII-range bytes as commands; with the rule of `docs/cutscene-engine.md` section 8 (updated) the decoding is clean [V].
- **Event 0x047** (bank `$C9:1096`): `PARTY_CMD 0x11`, `END`.
- Called events (all canned, bank `$C9`/`$CA`): 0x41E (party reset), 0x052 / 0x053 / 0x054 / 0x055 (all three heroes turn up / down / right / left), 0x056 (all three play animation 0xA8, then a 40-frame wait), 0x058 / 0x059 / 0x05A (hero slot 0 / 1 / 2 plays animation 0xA8, then a 40-frame wait), 0x05C (slot 1, animation 0xA9, then a 40-frame wait; called once), 0x732 (music 0x32), 0x73A (music 0x3A), 0x73E (raw command 0x80 with parameter 0x20, then a 40-frame wait), 0x748 (raw command 0x80 with parameter 0x80) [V].

## 4. Maps and scenes

Frame of each map change command, transition and the map it loads (the start tile is the table's; the heroes are at `(16 * tileX + 8, 16 * tileY + 10)` at the load frame in every map, section 5), size, number of text blocks and bytes, music and raw sound requests, and the object ids of the other objects at entry (the NPC kinds of each scene; their names are not recorded). The first row is the arena of `docs/cutscene-mana-beast-intro.md`.

| map | via | load frame | load s | map px | start tile | frame of the next map change | frames in the map | dialog blocks (bytes) | music/raw sound | objects other than heroes at entry (ids) |
|---|---|---|---|---|---|---|---|---|---|---|
| 253 | (initial state) | 0 | 0.00 | 576x576 | - | 1113 | 1113 | 0 (0) | raw 0xF0@5, raw 0x80@803 | 3:0x7F, 6:0x00 |
| 8 | MAP_CHANGE_D arg 0x7E (world-map mode, then the map the world-map code selects) | 1652 | 27.49 | 256x224 | (8, 7) | 1916 | 264 | 0 (0) | music 0x3A@1671 | - |
| 180 | MAP_CHANGE transition 1023 | 1973 | 32.83 | 544x256 | (8, 6) | 7217 | 5244 | 23 (332) | - | - |
| 148 | MAP_CHANGE transition 1000 | 7274 | 121.03 | 1088x1024 | (25, 33) | 8288 | 1014 | 1 (79) | - | 3:0xA7, 4:0xC3, 5:0xC2, 6:0xCB |
| 149 | MAP_CHANGE transition 1001 | 8345 | 138.85 | 320x768 | (10, 34) | 9549 | 1204 | 1 (77) | raw 0x20@9404, music 0x32@9539 | 3:0xA0, 4:0xB7, 5:0xB7, 6:0xB7, 7:0xB7, 8:0xB7 |
| 150 | MAP_CHANGE transition 1006 | 9606 | 159.84 | 1024x1024 | (21, 37) | 10155 | 549 | 1 (16) | - | 3:0xA3, 4:0xA4, 5:0xA5, 6:0xA5 |
| 108 | MAP_CHANGE transition 623 | 10212 | 169.92 | 800x1120 | (21, 0) | 11166 | 954 | 1 (134) | - | 3:0xB9, 4:0xB8, 5:0xA8, 6:0xB7, 7:0xB7, 8:0xB7, 9:0xB7 |
| 147 | MAP_CHANGE transition 999 | 11223 | 186.74 | 576x800 | (17, 9) | 11952 | 729 | 1 (13) | - | 3:0xAE, 4:0xAD |
| 146 | MAP_CHANGE transition 998 | 12009 | 199.82 | 1920x1920 | (16, 51) | 13393 | 1384 | 1 (274) | - | 3:0x9E, 4:0xAF, 5:0xAF, 6:0xAF, 7:0xAF |
| 106 | MAP_CHANGE transition 345 | 13450 | 223.80 | 768x896 | (11, 22) | 14004 | 554 | 1 (19) | - | - |
| 151 | MAP_CHANGE transition 1007 | 14061 | 233.96 | 768x896 | (23, 32) | 15130 | 1069 | 1 (232) | - | 3:0xCA, 4:0x0D, 5:0x0D |
| 105 | MAP_CHANGE transition 68 | 15187 | 252.70 | 384x384 | (11, 7) | 15916 | 729 | 1 (21) | - | 3:0xD9, 4:0xDA, 5:0xDC, 6:0xDD, 7:0xDE, 8:0xCE, 9:0xCE, 10:0xCE, 11:0xCE |
| 152 | MAP_CHANGE transition 1008 | 15973 | 265.78 | 1536x1536 | (39, 42) | 17172 | 1199 | 1 (200) | - | 3:0x9C |
| 153 | MAP_CHANGE transition 1009 | 17229 | 286.68 | 768x640 | (9, 11) | 18668 | 1439 | 1 (105) | - | 3:0x99 |
| 104 | MAP_CHANGE transition 67 | 18725 | 311.57 | 1024x1152 | (9, 46) | 20959 | 2234 | 2 (200) | - | 3:0xBB, 4:0xA6, 5:0xC9, 6:0xCA |
| 103 | MAP_CHANGE transition 66 | 21016 | 349.69 | 960x1024 | (24, 52) | 22025 | 1009 | 1 (145) | - | 3:0xA1 |
| 102 | MAP_CHANGE transition 65 | 22082 | 367.43 | 832x832 | (6, 23) | 23741 | 1659 | 1 (227) | raw 0x80@23281, music 0x3A@23736 | 3:0xC0, 4:0xC1, 5:0xC9, 6:0xC8 |
| 101 | MAP_CHANGE transition 64 | 23798 | 395.98 | 896x1312 | (21, 67) | 25022 | 1224 | 0 (0) | - | - |
| 107 | MAP_CHANGE transition 620 | 25079 | 417.30 | 832x768 | (26, 35) | 25973 | 894 | 0 (0) | - | 3:0x8C |

## 5. Actors and coordinates at entry [V]

All three heroes are at the same pixel at every load (hero slots 0, 1, 2 = boy, girl, sprite; ids 0x80, 0x81, 0x82); the first row is the position at frame 0 of this run (where the intro left them); the other objects are the map records of each map (position `16 * tile + 4`, ids >= 0x80 = NPC kinds) or, in the arena, the Mana Beast (engine position). Map sizes are in section 4.

| frame | map | object | slot | id | x | y | facing |
|---|---|---|---|---|---|---|---|
| 0 | 253 | hero | 0 (boy) | 0x80 | 296 | 411 | up |
| 0 | 253 | hero | 1 (girl) | 0x81 | 264 | 411 | up |
| 0 | 253 | hero | 2 (sprite) | 0x82 | 312 | 411 | up |
| 0 | 253 | object | 3 | 0x7F | 296 | 352 | down (engine position 296,352, phase 0x12) |
| 0 | 253 | object | 6 | 0x00 | 296 | 400 | up |
| 1652 | 8 | hero | 0 (boy) | 0x80 | 136 | 122 | left |
| 1652 | 8 | hero | 1 (girl) | 0x81 | 136 | 122 | left |
| 1652 | 8 | hero | 2 (sprite) | 0x82 | 136 | 122 | left |
| 1973 | 180 | hero | 0 (boy) | 0x80 | 136 | 106 | down |
| 1973 | 180 | hero | 1 (girl) | 0x81 | 136 | 106 | down |
| 1973 | 180 | hero | 2 (sprite) | 0x82 | 136 | 106 | down |
| 7274 | 148 | hero | 0 (boy) | 0x80 | 408 | 538 | down |
| 7274 | 148 | hero | 1 (girl) | 0x81 | 408 | 538 | down |
| 7274 | 148 | hero | 2 (sprite) | 0x82 | 408 | 538 | down |
| 7274 | 148 | object | 3 | 0xA7 | 676 | 676 | up |
| 7274 | 148 | object | 4 | 0xC3 | 708 | 692 | left |
| 7274 | 148 | object | 5 | 0xC2 | 644 | 692 | right |
| 7274 | 148 | object | 6 | 0xCB | 676 | 644 | down |
| 8345 | 149 | hero | 0 (boy) | 0x80 | 168 | 554 | down |
| 8345 | 149 | hero | 1 (girl) | 0x81 | 168 | 554 | down |
| 8345 | 149 | hero | 2 (sprite) | 0x82 | 168 | 554 | down |
| 8345 | 149 | object | 3 | 0xA0 | 164 | 276 | down |
| 8345 | 149 | object | 4 | 0xB7 | 148 | 260 | down |
| 8345 | 149 | object | 5 | 0xB7 | 100 | 500 | left |
| 8345 | 149 | object | 6 | 0xB7 | 212 | 500 | right |
| 8345 | 149 | object | 7 | 0xB7 | 100 | 596 | down |
| 8345 | 149 | object | 8 | 0xB7 | 212 | 596 | down |
| 9606 | 150 | hero | 0 (boy) | 0x80 | 344 | 602 | down |
| 9606 | 150 | hero | 1 (girl) | 0x81 | 344 | 602 | down |
| 9606 | 150 | hero | 2 (sprite) | 0x82 | 344 | 602 | down |
| 9606 | 150 | object | 3 | 0xA3 | 436 | 196 | down |
| 9606 | 150 | object | 4 | 0xA4 | 260 | 500 | right |
| 9606 | 150 | object | 5 | 0xA5 | 244 | 500 | right |
| 9606 | 150 | object | 6 | 0xA5 | 228 | 500 | right |
| 10212 | 108 | hero | 0 (boy) | 0x80 | 344 | 10 | down |
| 10212 | 108 | hero | 1 (girl) | 0x81 | 344 | 10 | down |
| 10212 | 108 | hero | 2 (sprite) | 0x82 | 344 | 10 | down |
| 10212 | 108 | object | 3 | 0xB9 | 388 | 820 | down |
| 10212 | 108 | object | 4 | 0xB8 | 404 | 100 | down |
| 10212 | 108 | object | 5 | 0xA8 | 404 | 212 | up |
| 10212 | 108 | object | 6 | 0xB7 | 228 | 292 | down |
| 10212 | 108 | object | 7 | 0xB7 | 324 | 740 | left |
| 10212 | 108 | object | 8 | 0xB7 | 228 | 548 | down |
| 10212 | 108 | object | 9 | 0xB7 | 404 | 612 | up |
| 11223 | 147 | hero | 0 (boy) | 0x80 | 280 | 154 | down |
| 11223 | 147 | hero | 1 (girl) | 0x81 | 280 | 154 | down |
| 11223 | 147 | hero | 2 (sprite) | 0x82 | 280 | 154 | down |
| 11223 | 147 | object | 3 | 0xAE | 196 | 228 | right |
| 11223 | 147 | object | 4 | 0xAD | 260 | 180 | up |
| 12009 | 146 | hero | 0 (boy) | 0x80 | 264 | 826 | down |
| 12009 | 146 | hero | 1 (girl) | 0x81 | 264 | 826 | down |
| 12009 | 146 | hero | 2 (sprite) | 0x82 | 264 | 826 | down |
| 12009 | 146 | object | 3 | 0x9E | 260 | 532 | down |
| 12009 | 146 | object | 4 | 0xAF | 228 | 548 | up |
| 12009 | 146 | object | 5 | 0xAF | 292 | 548 | up |
| 12009 | 146 | object | 6 | 0xAF | 212 | 596 | up |
| 12009 | 146 | object | 7 | 0xAF | 324 | 596 | up |
| 13450 | 106 | hero | 0 (boy) | 0x80 | 184 | 362 | down |
| 13450 | 106 | hero | 1 (girl) | 0x81 | 184 | 362 | down |
| 13450 | 106 | hero | 2 (sprite) | 0x82 | 184 | 362 | down |
| 14061 | 151 | hero | 0 (boy) | 0x80 | 376 | 522 | down |
| 14061 | 151 | hero | 1 (girl) | 0x81 | 376 | 522 | down |
| 14061 | 151 | hero | 2 (sprite) | 0x82 | 376 | 522 | down |
| 14061 | 151 | object | 3 | 0xCA | 180 | 468 | right |
| 14061 | 151 | object | 4 | 0x0D | 180 | 468 | right |
| 14061 | 151 | object | 5 | 0x0D | 196 | 468 | right |
| 15187 | 105 | hero | 0 (boy) | 0x80 | 184 | 122 | down |
| 15187 | 105 | hero | 1 (girl) | 0x81 | 184 | 122 | down |
| 15187 | 105 | hero | 2 (sprite) | 0x82 | 184 | 122 | down |
| 15187 | 105 | object | 3 | 0xD9 | 212 | 116 | up |
| 15187 | 105 | object | 4 | 0xDA | 212 | 116 | up |
| 15187 | 105 | object | 5 | 0xDC | 212 | 116 | up |
| 15187 | 105 | object | 6 | 0xDD | 212 | 116 | up |
| 15187 | 105 | object | 7 | 0xDE | 212 | 116 | up |
| 15187 | 105 | object | 8 | 0xCE | 164 | 244 | down |
| 15187 | 105 | object | 9 | 0xCE | 148 | 276 | down |
| 15187 | 105 | object | 10 | 0xCE | 180 | 276 | down |
| 15187 | 105 | object | 11 | 0xCE | 164 | 260 | down |
| 15973 | 152 | hero | 0 (boy) | 0x80 | 632 | 682 | left |
| 15973 | 152 | hero | 1 (girl) | 0x81 | 632 | 682 | left |
| 15973 | 152 | hero | 2 (sprite) | 0x82 | 632 | 682 | left |
| 15973 | 152 | object | 3 | 0x9C | 564 | 676 | right |
| 17229 | 153 | hero | 0 (boy) | 0x80 | 152 | 186 | down |
| 17229 | 153 | hero | 1 (girl) | 0x81 | 152 | 186 | down |
| 17229 | 153 | hero | 2 (sprite) | 0x82 | 152 | 186 | down |
| 17229 | 153 | object | 3 | 0x99 | 308 | 308 | down |
| 18725 | 104 | hero | 0 (boy) | 0x80 | 152 | 746 | down |
| 18725 | 104 | hero | 1 (girl) | 0x81 | 152 | 746 | down |
| 18725 | 104 | hero | 2 (sprite) | 0x82 | 152 | 746 | down |
| 18725 | 104 | object | 3 | 0xBB | 532 | 708 | left |
| 18725 | 104 | object | 4 | 0xA6 | 356 | 692 | right |
| 18725 | 104 | object | 5 | 0xC9 | 356 | 660 | down |
| 18725 | 104 | object | 6 | 0xCA | 372 | 692 | left |
| 21016 | 103 | hero | 0 (boy) | 0x80 | 392 | 842 | down |
| 21016 | 103 | hero | 1 (girl) | 0x81 | 392 | 842 | down |
| 21016 | 103 | hero | 2 (sprite) | 0x82 | 392 | 842 | down |
| 21016 | 103 | object | 3 | 0xA1 | 388 | 468 | down |
| 22082 | 102 | hero | 0 (boy) | 0x80 | 104 | 378 | down |
| 22082 | 102 | hero | 1 (girl) | 0x81 | 104 | 378 | down |
| 22082 | 102 | hero | 2 (sprite) | 0x82 | 104 | 378 | down |
| 22082 | 102 | object | 3 | 0xC0 | 292 | 404 | left |
| 22082 | 102 | object | 4 | 0xC1 | 292 | 372 | left |
| 22082 | 102 | object | 5 | 0xC9 | 308 | 388 | left |
| 22082 | 102 | object | 6 | 0xC8 | 308 | 420 | left |
| 23798 | 101 | hero | 0 (boy) | 0x80 | 344 | 1082 | down |
| 23798 | 101 | hero | 1 (girl) | 0x81 | 344 | 1082 | down |
| 23798 | 101 | hero | 2 (sprite) | 0x82 | 344 | 1082 | down |
| 25079 | 107 | hero | 0 (boy) | 0x80 | 424 | 570 | down |
| 25079 | 107 | hero | 1 (girl) | 0x81 | 424 | 570 | down |
| 25079 | 107 | hero | 2 (sprite) | 0x82 | 424 | 570 | down |
| 25079 | 107 | object | 3 | 0x8C | 436 | 340 | down |

After the `ACTOR_DELETE` / `ACTOR_CLONE` of frames 1098-1108 (section 7) the scripts address only actors 1 (slot 0, the controlled hero) and 2 (slot 1, the clone) and the NPC slots; slot 2 stays deleted (`obj+0` = 0x80) while the canned party events 0x052-0x056 still address it. Rows of the timeline that name slot 2 after that frame are those commands acting on a deleted object.

## 6. Dialog blocks and the staff roll (address and length only)

38 text blocks, all in event 0x4FD. The first 20 (blocks 1-21 except the 18 marked "yes") are ordinary dialog blocks; **18 blocks contain credits segments** (code 0x7D, ASCII-range bytes through the first 0x7E; a block can chain several segments and ordinary text, e.g. blocks 10 and 34): 1,897 bytes, 13,270 frames of waiting (221.3 s) in total. The extent of every block equals the pointer the text engine left in `$1D01` (38 of 38) [V]. "frames" = time from the VM step that hands the block over until the next command: engine drawing and scrolling time (the staff-roll blocks run for hundreds of frames while the camera scrolls and the party walks) plus the VM's 5-frame granularity. Blocks of one byte are engine control codes. No text is recorded here.

| # | event+offset | address | bytes | start frame | start s | frames to next command | credits segment |
|---|---|---|---|---|---|---|---|
| 1 | 0x4FD+0032 | CA:4DC7 | 3 | 2017 | 33.561 | 25 |  |
| 2 | 0x4FD+0037 | CA:4DCC | 3 | 2202 | 36.640 | 15 |  |
| 3 | 0x4FD+003C | CA:4DD1 | 1 | 2377 | 39.552 | 5 |  |
| 4 | 0x4FD+0044 | CA:4DD9 | 16 | 2392 | 39.801 | 25 |  |
| 5 | 0x4FD+0056 | CA:4DEB | 1 | 2657 | 44.211 | 5 |  |
| 6 | 0x4FD+005B | CA:4DF0 | 27 | 2667 | 44.377 | 35 |  |
| 7 | 0x4FD+0078 | CA:4E0D | 1 | 2942 | 48.953 | 5 |  |
| 8 | 0x4FD+007D | CA:4E12 | 11 | 2952 | 49.119 | 30 |  |
| 9 | 0x4FD+008A | CA:4E1F | 1 | 3222 | 53.612 | 15 |  |
| 10 | 0x4FD+0094 | CA:4E29 | 32 | 3402 | 56.607 | 65 | yes |
| 11 | 0x4FD+00B6 | CA:4E4B | 2 | 3627 | 60.351 | 15 |  |
| 12 | 0x4FD+00BA | CA:4E4F | 5 | 3802 | 63.262 | 15 |  |
| 13 | 0x4FD+00C1 | CA:4E56 | 1 | 4057 | 67.506 | 5 |  |
| 14 | 0x4FD+00C4 | CA:4E59 | 11 | 4127 | 68.670 | 20 |  |
| 15 | 0x4FD+00D1 | CA:4E66 | 1 | 4307 | 71.665 | 5 |  |
| 16 | 0x4FD+00D6 | CA:4E6B | 4 | 4317 | 71.832 | 15 |  |
| 17 | 0x4FD+00DC | CA:4E71 | 18 | 4492 | 74.744 | 30 |  |
| 18 | 0x4FD+00F0 | CA:4E85 | 26 | 4762 | 79.236 | 40 |  |
| 19 | 0x4FD+010C | CA:4EA1 | 1 | 4962 | 82.564 | 15 |  |
| 20 | 0x4FD+011C | CA:4EB1 | 43 | 5372 | 89.386 | 70 |  |
| 21 | 0x4FD+0149 | CA:4EDE | 1 | 5602 | 93.213 | 15 |  |
| 22 | 0x4FD+016B | CA:4F00 | 16 | 5892 | 98.039 | 520 | yes |
| 23 | 0x4FD+0187 | CA:4F1C | 107 | 6427 | 106.941 | 740 | yes |
| 24 | 0x4FD+0234 | CA:4FC9 | 79 | 7673 | 127.673 | 615 | yes |
| 25 | 0x4FD+02A4 | CA:5039 | 77 | 8599 | 143.081 | 615 | yes |
| 26 | 0x4FD+0324 | CA:50B9 | 16 | 9635 | 160.319 | 520 | yes |
| 27 | 0x4FD+0340 | CA:50D5 | 134 | 10236 | 170.320 | 840 | yes |
| 28 | 0x4FD+03E7 | CA:517C | 13 | 11432 | 190.220 | 520 | yes |
| 29 | 0x4FD+0415 | CA:51AA | 274 | 12173 | 202.550 | 1220 | yes |
| 30 | 0x4FD+0531 | CA:52C6 | 19 | 13484 | 224.364 | 520 | yes |
| 31 | 0x4FD+055B | CA:52F0 | 232 | 14100 | 234.614 | 1030 | yes |
| 32 | 0x4FD+0662 | CA:53F7 | 21 | 15396 | 256.178 | 520 | yes |
| 33 | 0x4FD+068B | CA:5420 | 200 | 16237 | 270.172 | 935 | yes |
| 34 | 0x4FD+0770 | CA:5505 | 105 | 17443 | 290.239 | 1225 | yes |
| 35 | 0x4FD+07FE | CA:5593 | 106 | 18954 | 315.381 | 710 | yes |
| 36 | 0x4FD+086C | CA:5601 | 94 | 19669 | 327.278 | 840 | yes |
| 37 | 0x4FD+08EF | CA:5684 | 145 | 21220 | 353.085 | 805 | yes |
| 38 | 0x4FD+0996 | CA:572B | 227 | 22186 | 369.159 | 1030 | yes |

## 7. Timeline

Reference run: controlled hero = slot 0 (boy), hero weapon types 4 / 1 / 3 (the save state's). Row conventions as in `docs/cutscene-mana-beast-intro.md` section 4. In addition: `autonomous movement of the object` rows summarise NPC motion that no VM command causes (their own AI, random; only the extent is recorded); the sound effect 0x8B rows from the engine are the party-run effect (animation code 0x8A) and are collapsed; the world-map mode (frames 1141-1652) has no object or camera rows because its objects are not the map objects (the camera registers hold other quantities there); positions that wrap around the map edge are made continuous (the maps wrap in x and y, e.g. frame 6423 onwards in map 180: x runs past 544).

| frame | s | object | what |
|---|---|---|---|
| 0 | 0.000 | engine | map 253 loaded |
| 5 | 0.083 | engine | jitter_byte_49 224 |
| 5 | 0.083 | sound | raw id 0xF0 (cmd 128, params 0x00 0x99) from engine |
| 26 | 0.433 | slot10 | appears id 0x3F at (0,0) |
| 26 | 0.433 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 46 | 0.765 | slot11 | appears id 0x21 at (0,0) |
| 46 | 0.765 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 66 | 1.098 | slot10 | removed |
| 86 | 1.431 | slot10 | facing up (0x00) |
| 86 | 1.431 | slot10 | appears id 0x3F at (273,292) |
| 86 | 1.431 | slot10 | obj+0x0E = 0x00 |
| 86 | 1.431 | slot11 | removed |
| 86 | 1.431 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 90 | 1.498 | slot10 (id 0x3F) | autonomous movement of the object (its own AI, no VM command): 3 segments, frames 90-210, x 273..317, y 292..348 |
| 106 | 1.764 | slot11 | facing up (0x00) |
| 106 | 1.764 | slot11 | appears id 0x21 at (311,351) |
| 106 | 1.764 | slot11 | obj+0x0E = 0x00 |
| 106 | 1.764 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 110 | 1.830 | slot11 (id 0x21) | autonomous movement of the object (its own AI, no VM command): 2 segments, frames 110-170, x 275..311, y 298..351 |
| 126 | 2.097 | slot10 | removed |
| 146 | 2.429 | slot10 | facing up (0x00) |
| 146 | 2.429 | slot10 | appears id 0x3F at (298,306) |
| 146 | 2.429 | slot10 | obj+0x0E = 0x00 |
| 146 | 2.429 | slot11 | removed |
| 146 | 2.429 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 166 | 2.762 | slot11 | facing up (0x00) |
| 166 | 2.762 | slot11 | appears id 0x21 at (306,298) |
| 166 | 2.762 | slot11 | obj+0x0E = 0x00 |
| 166 | 2.762 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 186 | 3.095 | slot10 | removed |
| 206 | 3.428 | slot10 | facing up (0x00) |
| 206 | 3.428 | slot10 | appears id 0x3F at (317,318) |
| 206 | 3.428 | slot10 | obj+0x0E = 0x00 |
| 206 | 3.428 | slot11 | removed |
| 206 | 3.428 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 226 | 3.760 | slot8 | appears id 0x00 at (0,0) |
| 226 | 3.760 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 246 | 4.093 | slot9 | appears id 0x00 at (0,0) |
| 246 | 4.093 | slot10 | removed |
| 246 | 4.093 | sound | sfx id 0x15 (cmd 2, params 0x0F 0x00) from engine |
| 265 | 4.409 | engine | jitter_byte_49 0 |
| 266 | 4.426 | slot8 | removed |
| 286 | 4.759 | slot9 | removed |
| 780 | 12.979 | slot3 | removed |
| 780 | 12.979 | engine | pad_locked |
| 783 | 13.029 | VM 0x42F+0000 | FLAG_INC flag 0x4E |
| 783 | 13.029 | VM 0x42F+0002 | FLAG_INC flag 0xFF |
| 783 | 13.029 | VM 0x42F+0004 | GOTO_EVENT event 0x3FF |
| 783 | 13.029 | VM 0x3FF+0000 | GOTO_EVENT event 0x4FD |
| 783 | 13.029 | VM 0x4FD+0000 | FREEZE |
| 783 | 13.029 | engine | world_freeze_on |
| 783 | 13.029 | engine | boss_freeze_flag_set |
| 783 | 13.029 | flag | flag 0x4E 8 -> 9 |
| 783 | 13.029 | flag | flag 0xFF 0 -> 1 |
| 788 | 13.112 | VM 0x4FD+0001 | GATHER |
| 789 | 13.128 | hero1_girl (id 0x81) | walk (264, 411) -> (296, 411), 11 frames, 174.8 px/s, facing right/up, anim [1, 2], per-frame 10x(+3,+0) 1x(+2,+0) [0x4FD+0001 GATHER] |
| 789 | 13.128 | hero2_sprite (id 0x82) | walk (312, 411) -> (296, 411), 6 frames, 160.3 px/s, facing left, anim [1, 2], per-frame 5x(-3,+0) 1x(-1,+0) [0x4FD+0001 GATHER] |
| 798 | 13.278 | sound | sfx id 0x8B (party run effect, from the engine) x1, frames 798..798 |
| 799 | 13.295 | hero2_sprite | facing up (0x00) |
| 803 | 13.361 | VM 0x4FD+0002 | CALL_EVENT event 0x748 |
| 803 | 13.361 | VM 0x748+0000 | SOUND cmd 128 id 0x80 word 0x0000 |
| 803 | 13.361 | sound | raw id 0x80 (cmd 128, params 0x00 0x00) from vm_op |
| 808 | 13.445 | VM 0x4FD+0004 | SCREEN arg 6 word 0x3FFF |
| 808 | 13.445 | engine | palette_fade_mode_2A 96 (target word $010C = 0x3FFF) |
| 813 | 13.528 | VM 0x4FD+0008 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 1053 | 17.521 | VM 0x4FD+000A | FLAG_SET flag 0x00 = 0 |
| 1053 | 17.521 | flag | flag 0x00 1 -> 0 |
| 1058 | 17.604 | VM 0x4FD+000D | ACTOR_ANIM_LOOP actor 1 anim 0xAB |
| 1058 | 17.604 | VM 0x4FD+0010 | ACTOR_ANIM_LOOP actor 2 anim 0xAB |
| 1058 | 17.604 | hero0_boy | pose state 0x30 anim 0xAB |
| 1058 | 17.604 | hero1_girl | pose state 0x30 anim 0xAB |
| 1063 | 17.688 | VM 0x4FD+0014 | CALL_EVENT event 0x41E |
| 1063 | 17.688 | VM 0x41E+0000 | SET_FIELD_BYTE actor=0x01 b=0x90 c=0x00 |
| 1068 | 17.771 | VM 0x41E+0004 | SET_FIELD_BYTE actor=0x01 b=0x91 c=0x00 |
| 1073 | 17.854 | VM 0x41E+0008 | SET_FIELD_BYTE actor=0x02 b=0x90 c=0x00 |
| 1078 | 17.937 | VM 0x41E+000C | SET_FIELD_BYTE actor=0x02 b=0x91 c=0x00 |
| 1083 | 18.020 | VM 0x41E+0010 | SET_FIELD_BYTE actor=0x03 b=0x90 c=0x00 |
| 1088 | 18.104 | VM 0x41E+0014 | SET_FIELD_BYTE actor=0x03 b=0x91 c=0x00 |
| 1093 | 18.187 | VM 0x41E+0018 | HERO_REFILL arg 0x04 |
| 1093 | 18.187 | VM 0x41E+001A | HERO_REFILL arg 0x84 |
| 1093 | 18.187 | VM 0x41E+001C | HERO_REFILL arg 0x44 |
| 1093 | 18.187 | VM 0x41E+001E | CALL_E326 |
| 1098 | 18.270 | VM 0x4FD+0016 | ACTOR_DELETE arg 0x01 |
| 1103 | 18.353 | VM 0x4FD+0018 | ACTOR_DELETE arg 0x02 |
| 1108 | 18.436 | VM 0x4FD+001A | ACTOR_CLONE arg 0x01 |
| 1108 | 18.436 | hero1_girl | facing down (0x01) |
| 1113 | 18.520 | VM 0x4FD+001C | MAP_CHANGE_D arg 0x7E |
| 1113 | 18.520 | screen | fade_out brightness 15 -> 0, 29 frames |
| 1141 | 18.985 | engine | palette_fade_mode_2A 33 (target word $010C = 0x3FFF) |
| 1142 | 19.002 | screen | fade_in brightness 0 -> 15, 57 frames |
| 1388 | 23.095 | sound | sfx id 0x16 (cmd 2, params 0x00 0xA4) from engine |
| 1644 | 27.355 | sound | sfx id 0x16 (cmd 2, params 0x00 0xA4) from engine |
| 1652 | 27.488 | slot6 | removed |
| 1652 | 27.488 | screen | fade_out brightness 15 -> 0, 1 frames |
| 1652 | 27.488 | engine | palette_fade_mode_2A 0 (target word $010C = 0x3FFF) |
| 1652 | 27.488 | engine | map 8 loaded |
| 1653 | 27.505 | screen | fade_in brightness 0 -> 15, 15 frames |
| 1656 | 27.555 | hero0_boy | facing left (0x82) |
| 1656 | 27.555 | hero0_boy | pose idle |
| 1656 | 27.555 | hero1_girl | facing left (0x82) |
| 1656 | 27.555 | hero1_girl | pose idle |
| 1656 | 27.555 | hero2_sprite | facing left (0x82) |
| 1671 | 27.804 | VM 0x4FD+001E | CALL_EVENT event 0x73A |
| 1671 | 27.804 | VM 0x73A+0000 | SOUND cmd 1 id 0x3A word 0x8F1B |
| 1671 | 27.804 | sound | music id 0x3A (cmd 1, params 0x1B 0x8F) from vm_op |
| 1676 | 27.887 | VM 0x4FD+0020 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 1916 | 31.881 | VM 0x4FD+0022 | MAP_CHANGE transition 1023 |
| 1917 | 31.897 | screen | fade_out brightness 15 -> 0, 57 frames |
| 1973 | 32.829 | camera | set by the map loader to (8, 248) |
| 1973 | 32.829 | engine | map 180 loaded |
| 1974 | 32.846 | screen | fade_in brightness 0 -> 15, 15 frames |
| 1977 | 32.896 | hero0_boy | facing down (0x01) |
| 1977 | 32.896 | hero1_girl | facing down (0x01) |
| 1977 | 32.896 | hero2_sprite | facing down (0x01) |
| 1992 | 33.145 | VM 0x4FD+0024 | ACTOR_WALK actor 1 down 8 frames |
| 1992 | 33.145 | VM 0x4FD+0027 | ACTOR_WALK actor 2 down 16 frames |
| 1992 | 33.145 | hero0_boy (id 0x80) | walk (136, 106) -> (136, 122), 8 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 8x(+0,+2) [0x4FD+0024 ACTOR_WALK actor 1 down 8 frames] |
| 1992 | 33.145 | hero1_girl (id 0x81) | walk (136, 106) -> (136, 138), 16 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 16x(+0,+2) [0x4FD+0027 ACTOR_WALK actor 2 down 16 frames] |
| 2012 | 33.478 | VM 0x4FD+002B | ACTOR_WALK actor 1 left 4 frames |
| 2012 | 33.478 | VM 0x4FD+002E | ACTOR_WALK actor 2 right 4 frames |
| 2012 | 33.478 | hero0_boy (id 0x80) | walk (136, 122) -> (128, 122), 4 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 4x(-2,+0) [0x4FD+002B ACTOR_WALK actor 1 left 4 frames] |
| 2012 | 33.478 | hero1_girl (id 0x81) | walk (136, 138) -> (144, 138), 4 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 4x(+2,+0) [0x4FD+002E ACTOR_WALK actor 2 right 4 frames] |
| 2017 | 33.561 | dialog | 1 text block (#1-#1, CA:4DC7 ...), each followed by a wait for a button where the script has one; next command at frame 2042 |
| 2042 | 33.977 | VM 0x4FD+0035 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 2202 | 36.640 | dialog | 1 text block (#2-#2, CA:4DCC ...), each followed by a wait for a button where the script has one; next command at frame 2217 |
| 2217 | 36.889 | VM 0x4FD+003A | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 2377 | 39.552 | dialog | 1 text block (#3-#3, CA:4DD1 ...), each followed by a wait for a button where the script has one; next command at frame 2382 |
| 2382 | 39.635 | VM 0x4FD+003D | ACTOR_WALK actor 1 right 8 frames |
| 2382 | 39.635 | VM 0x4FD+0040 | ACTOR_WALK actor 2 left 8 frames |
| 2382 | 39.635 | hero0_boy (id 0x80) | walk (128, 122) -> (144, 122), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x4FD+003D ACTOR_WALK actor 1 right 8 frames] |
| 2382 | 39.635 | hero1_girl (id 0x81) | walk (144, 138) -> (128, 138), 8 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 8x(-2,+0) [0x4FD+0040 ACTOR_WALK actor 2 left 8 frames] |
| 2392 | 39.801 | dialog | 1 text block (#4-#4, CA:4DD9 ...), each followed by a wait for a button where the script has one; next command at frame 2417 |
| 2417 | 40.217 | VM 0x4FD+0054 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 2657 | 44.211 | dialog | 1 text block (#5-#5, CA:4DEB ...), each followed by a wait for a button where the script has one; next command at frame 2662 |
| 2662 | 44.294 | VM 0x4FD+0057 | ACTOR_WALK actor 1 down 0 frames |
| 2662 | 44.294 | hero0_boy | facing down (0x01) |
| 2667 | 44.377 | dialog | 1 text block (#6-#6, CA:4DF0 ...), each followed by a wait for a button where the script has one; next command at frame 2702 |
| 2702 | 44.959 | VM 0x4FD+0076 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 2942 | 48.953 | dialog | 1 text block (#7-#7, CA:4E0D ...), each followed by a wait for a button where the script has one; next command at frame 2947 |
| 2947 | 49.036 | VM 0x4FD+0079 | ACTOR_WALK actor 2 up 4 frames |
| 2947 | 49.036 | hero1_girl (id 0x81) | walk (128, 138) -> (128, 130), 4 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 4x(+0,-2) [0x4FD+0079 ACTOR_WALK actor 2 up 4 frames] |
| 2952 | 49.119 | dialog | 1 text block (#8-#8, CA:4E12 ...), each followed by a wait for a button where the script has one; next command at frame 2982 |
| 2982 | 49.618 | VM 0x4FD+0088 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 3222 | 53.612 | dialog | 1 text block (#9-#9, CA:4E1F ...), each followed by a wait for a button where the script has one; next command at frame 3237 |
| 3237 | 53.861 | VM 0x4FD+008B | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 3397 | 56.524 | VM 0x4FD+008D | ACTOR_WALK actor 1 up 0 frames |
| 3397 | 56.524 | VM 0x4FD+0090 | ACTOR_WALK actor 2 up 0 frames |
| 3397 | 56.524 | hero0_boy | facing up (0x00) |
| 3402 | 56.607 | dialog | 1 text block (#10-#10, CA:4E29 ...), each followed by a wait for a button where the script has one; next command at frame 3467 |
| 3467 | 57.688 | VM 0x4FD+00B4 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 3627 | 60.351 | dialog | 1 text block (#11-#11, CA:4E4B ...), each followed by a wait for a button where the script has one; next command at frame 3642 |
| 3642 | 60.600 | VM 0x4FD+00B8 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 3802 | 63.262 | dialog | 1 text block (#12-#12, CA:4E4F ...), each followed by a wait for a button where the script has one; next command at frame 3817 |
| 3817 | 63.512 | VM 0x4FD+00BF | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 4057 | 67.506 | dialog | 1 text block (#13-#13, CA:4E56 ...), each followed by a wait for a button where the script has one; next command at frame 4062 |
| 4062 | 67.589 | VM 0x4FD+00C2 | CALL_EVENT event 0x059 |
| 4062 | 67.589 | VM 0x059+0000 | ACTOR_ANIM actor 2 anim 0xA8 |
| 4062 | 67.589 | hero1_girl | pose state 0x40 anim 0xA8 |
| 4082 | 67.921 | hero1_girl | pose idle |
| 4087 | 68.005 | VM 0x059+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 4127 | 68.670 | dialog | 1 text block (#14-#14, CA:4E59 ...), each followed by a wait for a button where the script has one; next command at frame 4147 |
| 4147 | 69.003 | VM 0x4FD+00CF | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 4307 | 71.665 | dialog | 1 text block (#15-#15, CA:4E66 ...), each followed by a wait for a button where the script has one; next command at frame 4312 |
| 4312 | 71.749 | VM 0x4FD+00D2 | ACTOR_WALK actor 2 down 0 frames |
| 4312 | 71.749 | hero1_girl | facing down (0x01) |
| 4317 | 71.832 | dialog | 1 text block (#16-#16, CA:4E6B ...), each followed by a wait for a button where the script has one; next command at frame 4332 |
| 4332 | 72.081 | VM 0x4FD+00DA | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 4492 | 74.744 | dialog | 1 text block (#17-#17, CA:4E71 ...), each followed by a wait for a button where the script has one; next command at frame 4522 |
| 4522 | 75.243 | VM 0x4FD+00EE | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 4762 | 79.236 | dialog | 1 text block (#18-#18, CA:4E85 ...), each followed by a wait for a button where the script has one; next command at frame 4802 |
| 4802 | 79.902 | VM 0x4FD+010A | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 4962 | 82.564 | dialog | 1 text block (#19-#19, CA:4EA1 ...), each followed by a wait for a button where the script has one; next command at frame 4977 |
| 4977 | 82.814 | VM 0x4FD+010D | ACTOR_WALK actor 1 down 0 frames |
| 4977 | 82.814 | VM 0x4FD+0110 | ACTOR_WALK actor 2 up 0 frames |
| 4977 | 82.814 | hero0_boy | facing down (0x01) |
| 4977 | 82.814 | hero1_girl | facing up (0x00) |
| 4982 | 82.897 | VM 0x4FD+0114 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 5142 | 85.559 | VM 0x4FD+0116 | CALL_EVENT event 0x056 |
| 5142 | 85.559 | VM 0x056+0000 | ACTOR_ANIM actor 1 anim 0xA8 |
| 5142 | 85.559 | VM 0x056+0003 | ACTOR_ANIM actor 2 anim 0xA8 |
| 5142 | 85.559 | VM 0x056+0006 | ACTOR_ANIM actor 3 anim 0xA8 |
| 5142 | 85.559 | hero0_boy | pose state 0x40 anim 0xA8 |
| 5142 | 85.559 | hero1_girl | pose state 0x40 anim 0xA8 |
| 5142 | 85.559 | hero2_sprite | pose state 0x40 anim 0xA8 |
| 5162 | 85.892 | hero0_boy | pose idle |
| 5162 | 85.892 | hero1_girl | pose idle |
| 5162 | 85.892 | hero2_sprite | pose idle |
| 5167 | 85.975 | VM 0x056+000A | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5207 | 86.641 | VM 0x4FD+0118 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 5367 | 89.303 | VM 0x4FD+011A | CALL_EVENT event 0x052 |
| 5367 | 89.303 | VM 0x052+0000 | ACTOR_WALK actor 1 up 0 frames |
| 5367 | 89.303 | VM 0x052+0003 | ACTOR_WALK actor 2 up 0 frames |
| 5367 | 89.303 | VM 0x052+0006 | ACTOR_WALK actor 3 up 0 frames |
| 5367 | 89.303 | hero0_boy | facing up (0x00) |
| 5367 | 89.303 | hero2_sprite | facing up (0x00) |
| 5372 | 89.386 | dialog | 1 text block (#20-#20, CA:4EB1 ...), each followed by a wait for a button where the script has one; next command at frame 5442 |
| 5442 | 90.551 | VM 0x4FD+0147 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 5602 | 93.213 | dialog | 1 text block (#21-#21, CA:4EDE ...), each followed by a wait for a button where the script has one; next command at frame 5617 |
| 5617 | 93.463 | VM 0x4FD+014A | ACTOR_ANIM actor 1 anim 0xB2 |
| 5617 | 93.463 | VM 0x4FD+014D | ACTOR_ANIM actor 2 anim 0xB2 |
| 5617 | 93.463 | hero0_boy | pose state 0x40 anim 0xB2 |
| 5617 | 93.463 | hero1_girl | pose state 0x40 anim 0xB2 |
| 5637 | 93.796 | hero0_boy | pose idle |
| 5637 | 93.796 | hero1_girl | pose idle |
| 5642 | 93.879 | VM 0x4FD+0151 | FLAG_INC flag 0xF7 |
| 5642 | 93.879 | VM 0x4FD+0153 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5642 | 93.879 | flag | flag 0xF7 0 -> 1 |
| 5682 | 94.544 | VM 0x4FD+0155 | FLAG_INC flag 0xF7 |
| 5682 | 94.544 | VM 0x4FD+0157 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5682 | 94.544 | flag | flag 0xF7 1 -> 2 |
| 5722 | 95.210 | VM 0x4FD+0159 | FLAG_INC flag 0xF7 |
| 5722 | 95.210 | VM 0x4FD+015B | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5722 | 95.210 | flag | flag 0xF7 2 -> 3 |
| 5762 | 95.875 | VM 0x4FD+015D | FLAG_INC flag 0xF7 |
| 5762 | 95.875 | VM 0x4FD+015F | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5762 | 95.875 | flag | flag 0xF7 3 -> 4 |
| 5802 | 96.541 | VM 0x4FD+0161 | FLAG_SET flag 0xF7 = 6 |
| 5802 | 96.541 | flag | flag 0xF7 4 -> 6 |
| 5807 | 96.624 | VM 0x4FD+0164 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5847 | 97.290 | VM 0x4FD+0166 | FLAG_SET flag 0xF7 = 8 |
| 5847 | 97.290 | flag | flag 0xF7 6 -> 8 |
| 5852 | 97.373 | VM 0x4FD+0169 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 5892 | 98.039 | dialog | 1 text block (#22-#22, CA:4F00 ...), each followed by a wait for a button where the script has one; next command at frame 6412 |
| 6412 | 106.691 | VM 0x4FD+017B | FLAG_SET flag 0xF7 = 11 |
| 6412 | 106.691 | flag | flag 0xF7 8 -> 11 |
| 6417 | 106.774 | VM 0x4FD+017E | CALL_EVENT event 0x054 |
| 6417 | 106.774 | VM 0x054+0000 | ACTOR_WALK actor 1 right 0 frames |
| 6417 | 106.774 | VM 0x054+0003 | ACTOR_WALK actor 2 right 0 frames |
| 6417 | 106.774 | VM 0x054+0006 | ACTOR_WALK actor 3 right 0 frames |
| 6417 | 106.774 | hero0_boy | facing right (0x02) |
| 6417 | 106.774 | hero1_girl | facing right (0x02) |
| 6417 | 106.774 | hero2_sprite | facing right (0x02) |
| 6422 | 106.857 | VM 0x4FD+0180 | ACTOR_ANIM_LOOP actor 1 anim 0x89 |
| 6422 | 106.857 | VM 0x4FD+0183 | ACTOR_ANIM_LOOP actor 2 anim 0x89 |
| 6422 | 106.857 | hero0_boy | pose state 0x30 anim 0x89 |
| 6422 | 106.857 | hero1_girl | pose state 0x30 anim 0x89 |
| 6423 | 106.874 | hero0_boy (id 0x80) | walk (144, 122) -> (1945, 122), 851 frames, 127.2 px/s, facing right, anim [137, 138], per-frame 749x(+2,+0) 1x(+0,+0) 101x(+3,+0) [0x4FD+0180 ACTOR_ANIM_LOOP actor 1 anim 0x89] |
| 6423 | 106.874 | hero1_girl (id 0x81) | walk (128, 130) -> (1929, 130), 851 frames, 127.2 px/s, facing right, anim [137, 138], per-frame 749x(+2,+0) 1x(+0,+0) 101x(+3,+0) [0x4FD+0183 ACTOR_ANIM_LOOP actor 2 anim 0x89] |
| 6427 | 106.941 | dialog | 1 text block (#23-#23, CA:4F1C ...), each followed by a wait for a button where the script has one; next command at frame 7167 |
| 6454 | 107.390 | camera | scroll (8, 248) -> (488, 248), 763 frames |
| 7167 | 119.254 | VM 0x4FD+01F2 | FLAG_SET flag 0xF7 = 15 |
| 7167 | 119.254 | flag | flag 0xF7 11 -> 15 |
| 7172 | 119.337 | VM 0x4FD+01F5 | ACTOR_ANIM_LOOP actor 1 anim 0x8A |
| 7172 | 119.337 | VM 0x4FD+01F8 | ACTOR_ANIM_LOOP actor 2 anim 0x8A |
| 7172 | 119.337 | hero0_boy | pose state 0x30 anim 0x8A |
| 7172 | 119.337 | hero1_girl | pose state 0x30 anim 0x8A |
| 7177 | 119.420 | VM 0x4FD+01FC | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 7177 | 119.420 | sound | sfx id 0x8B (party run effect, from the engine) x4, frames 7177..7197 |
| 7217 | 120.086 | VM 0x4FD+01FE | MAP_CHANGE transition 1000 |
| 7217 | 120.086 | sound | sfx id 0x8B (party run effect, from the engine) x2, frames 7217..7217 |
| 7218 | 120.102 | screen | fade_out brightness 15 -> 0, 57 frames |
| 7237 | 120.418 | sound | sfx id 0x8B (party run effect, from the engine) x4, frames 7237..7257 |
| 7274 | 121.034 | slot3 | appears id 0xA7 at (676,676) |
| 7274 | 121.034 | slot3 | obj+0x0E = 0x00 |
| 7274 | 121.034 | slot4 | appears id 0xC3 at (708,692) |
| 7274 | 121.034 | slot5 | appears id 0xC2 at (644,692) |
| 7274 | 121.034 | slot6 | appears id 0xCB at (676,644) |
| 7274 | 121.034 | slot6 | obj+0x0E = 0x00 |
| 7274 | 121.034 | camera | set by the map loader to (280, 424) |
| 7274 | 121.034 | engine | map 148 loaded |
| 7275 | 121.051 | screen | fade_in brightness 0 -> 15, 15 frames |
| 7278 | 121.101 | hero0_boy | facing down (0x01) |
| 7278 | 121.101 | hero0_boy | pose idle |
| 7278 | 121.101 | hero1_girl | facing down (0x01) |
| 7278 | 121.101 | hero1_girl | pose idle |
| 7278 | 121.101 | hero2_sprite | facing down (0x01) |
| 7293 | 121.350 | VM 0x4FD+0200 | ACTOR_WALK actor 1 down 24 frames |
| 7293 | 121.350 | VM 0x4FD+0203 | ACTOR_WALK actor 2 down 16 frames |
| 7293 | 121.350 | hero0_boy (id 0x80) | walk (408, 538) -> (408, 712), 88 frames, 118.8 px/s, facing down, anim [0, 1], per-frame 24x(+0,+2) 1x(+0,+0) 63x(+0,+2) [0x4FD+0200 ACTOR_WALK actor 1 down 24 frames] |
| 7293 | 121.350 | hero1_girl (id 0x81) | walk (408, 538) -> (408, 570), 16 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 16x(+0,+2) [0x4FD+0203 ACTOR_WALK actor 2 down 16 frames] |
| 7318 | 121.766 | VM 0x4FD+0207 | ACTOR_WALK actor 1 down 63 frames |
| 7318 | 121.766 | VM 0x4FD+020A | ACTOR_WALK actor 2 down 63 frames |
| 7318 | 121.766 | hero1_girl (id 0x81) | walk (408, 570) -> (408, 696), 63 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 63x(+0,+2) [0x4FD+020A ACTOR_WALK actor 2 down 63 frames] |
| 7324 | 121.866 | camera | scroll (280, 424) -> (280, 538), 57 frames |
| 7383 | 122.848 | VM 0x4FD+020E | CALL_EVENT event 0x054 |
| 7383 | 122.848 | VM 0x054+0000 | ACTOR_WALK actor 1 right 0 frames |
| 7383 | 122.848 | VM 0x054+0003 | ACTOR_WALK actor 2 right 0 frames |
| 7383 | 122.848 | VM 0x054+0006 | ACTOR_WALK actor 3 right 0 frames |
| 7383 | 122.848 | hero0_boy | facing right (0x02) |
| 7383 | 122.848 | hero1_girl | facing right (0x02) |
| 7383 | 122.848 | hero2_sprite | facing right (0x02) |
| 7388 | 122.931 | VM 0x4FD+0210 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 7468 | 124.262 | VM 0x4FD+0212 | ACTOR_ANIM_LOOP actor 1 anim 0x8A |
| 7468 | 124.262 | VM 0x4FD+0215 | ACTOR_ANIM_LOOP actor 2 anim 0x8A |
| 7468 | 124.262 | hero0_boy | pose state 0x30 anim 0x8A |
| 7468 | 124.262 | hero1_girl | pose state 0x30 anim 0x8A |
| 7469 | 124.279 | hero0_boy (id 0x80) | walk (408, 712) -> (660, 712), 84 frames, 180.3 px/s, facing right, anim [138], per-frame 84x(+3,+0) [0x4FD+0212 ACTOR_ANIM_LOOP actor 1 anim 0x8A] |
| 7469 | 124.279 | hero1_girl (id 0x81) | walk (408, 696) -> (660, 696), 84 frames, 180.3 px/s, facing right, anim [138], per-frame 84x(+3,+0) [0x4FD+0215 ACTOR_ANIM_LOOP actor 2 anim 0x8A] |
| 7473 | 124.345 | VM 0x4FD+0219 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 7473 | 124.345 | sound | sfx id 0x8B (party run effect, from the engine) x2, frames 7473..7473 |
| 7492 | 124.661 | camera | scroll (280, 538) -> (463, 538), 61 frames |
| 7493 | 124.678 | sound | sfx id 0x8B (party run effect, from the engine) x6, frames 7493..7533 |
| 7553 | 125.676 | VM 0x4FD+021B | CALL_EVENT event 0x054 |
| 7553 | 125.676 | VM 0x054+0000 | ACTOR_WALK actor 1 right 0 frames |
| 7553 | 125.676 | VM 0x054+0003 | ACTOR_WALK actor 2 right 0 frames |
| 7553 | 125.676 | VM 0x054+0006 | ACTOR_WALK actor 3 right 0 frames |
| 7553 | 125.676 | hero0_boy | pose idle |
| 7553 | 125.676 | hero1_girl | pose idle |
| 7558 | 125.760 | VM 0x4FD+021D | ACTOR_WALK actor 4 down 0 frames |
| 7558 | 125.760 | VM 0x4FD+0220 | ACTOR_WALK actor 5 down 0 frames |
| 7558 | 125.760 | VM 0x4FD+0223 | ACTOR_WALK actor 6 down 0 frames |
| 7558 | 125.760 | VM 0x4FD+0226 | ACTOR_WALK actor 7 down 4 frames |
| 7558 | 125.760 | slot3 | facing down (0x01) |
| 7558 | 125.760 | slot6 (id 0xCB) | walk (676, 644) -> (676, 652), 4 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 4x(+0,+2) [0x4FD+0226 ACTOR_WALK actor 7 down 4 frames] |
| 7563 | 125.843 | VM 0x4FD+022A | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 7643 | 127.174 | VM 0x4FD+022C | ACTOR_WALK actor 4 down 24 frames |
| 7643 | 127.174 | slot3 (id 0xA7) | walk (676, 676) -> (676, 703), 24 frames, 67.6 px/s, facing down, anim [0, 1], per-frame 3x(+0,+2) 21x(+0,+1) [0x4FD+022C ACTOR_WALK actor 4 down 24 frames] |
| 7668 | 127.590 | VM 0x4FD+0230 | ACTOR_WALK actor 4 left 0 frames |
| 7668 | 127.590 | slot3 | facing left (0x82) |
| 7673 | 127.673 | dialog | 1 text block (#24-#24, CA:4FC9 ...), each followed by a wait for a button where the script has one; next command at frame 8288 |
| 8288 | 137.906 | VM 0x4FD+0283 | MAP_CHANGE transition 1001 |
| 8289 | 137.923 | screen | fade_out brightness 15 -> 0, 57 frames |
| 8345 | 138.855 | slot7 | appears id 0xB7 at (100,596) |
| 8345 | 138.855 | slot8 | appears id 0xB7 at (212,596) |
| 8345 | 138.855 | slot8 | obj+0x0E = 0x00 |
| 8345 | 138.855 | camera | set by the map loader to (40, 440) |
| 8345 | 138.855 | engine | map 149 loaded |
| 8346 | 138.871 | screen | fade_in brightness 0 -> 15, 15 frames |
| 8349 | 138.921 | hero0_boy | facing down (0x01) |
| 8349 | 138.921 | hero1_girl | facing down (0x01) |
| 8349 | 138.921 | hero2_sprite | facing down (0x01) |
| 8364 | 139.171 | VM 0x4FD+0285 | ACTOR_WALK actor 1 up 16 frames |
| 8364 | 139.171 | hero0_boy (id 0x80) | walk (168, 554) -> (168, 522), 16 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 16x(+0,-2) [0x4FD+0285 ACTOR_WALK actor 1 up 16 frames] |
| 8384 | 139.504 | VM 0x4FD+0289 | ACTOR_WALK actor 1 up 63 frames |
| 8384 | 139.504 | VM 0x4FD+028C | ACTOR_WALK actor 2 up 63 frames |
| 8384 | 139.504 | hero0_boy (id 0x80) | walk (168, 522) -> (168, 396), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+0289 ACTOR_WALK actor 1 up 63 frames] |
| 8384 | 139.504 | hero1_girl (id 0x81) | walk (168, 554) -> (168, 428), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+028C ACTOR_WALK actor 2 up 63 frames] |
| 8389 | 139.587 | camera | scroll (40, 440) -> (40, 324), 58 frames |
| 8449 | 140.585 | VM 0x4FD+0290 | ACTOR_WALK actor 1 up 40 frames |
| 8449 | 140.585 | VM 0x4FD+0293 | ACTOR_WALK actor 2 up 40 frames |
| 8449 | 140.585 | hero0_boy (id 0x80) | walk (168, 396) -> (168, 316), 40 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 40x(+0,-2) [0x4FD+0290 ACTOR_WALK actor 1 up 40 frames] |
| 8449 | 140.585 | hero1_girl (id 0x81) | walk (168, 428) -> (168, 348), 40 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 40x(+0,-2) [0x4FD+0293 ACTOR_WALK actor 2 up 40 frames] |
| 8449 | 140.585 | camera | scroll (40, 324) -> (40, 244), 40 frames |
| 8489 | 141.251 | VM 0x4FD+0297 | ACTOR_WALK actor 2 left 8 frames |
| 8489 | 141.251 | VM 0x4FD+029A | ACTOR_WALK actor 4 down 8 frames |
| 8489 | 141.251 | hero1_girl (id 0x81) | walk (168, 348) -> (152, 348), 8 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 8x(-2,+0) [0x4FD+0297 ACTOR_WALK actor 2 left 8 frames] |
| 8489 | 141.251 | slot3 (id 0xA0) | walk (164, 276) -> (164, 287), 8 frames, 82.6 px/s, facing down, anim [0, 1], per-frame 3x(+0,+2) 5x(+0,+1) [0x4FD+029A ACTOR_WALK actor 4 down 8 frames] |
| 8499 | 141.417 | VM 0x4FD+029E | ACTOR_WALK actor 2 up 16 frames |
| 8499 | 141.417 | hero1_girl (id 0x81) | walk (152, 348) -> (152, 316), 16 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 16x(+0,-2) [0x4FD+029E ACTOR_WALK actor 2 up 16 frames] |
| 8519 | 141.750 | VM 0x4FD+02A2 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 8599 | 143.081 | dialog | 1 text block (#25-#25, CA:5039 ...), each followed by a wait for a button where the script has one; next command at frame 9214 |
| 9214 | 153.314 | VM 0x4FD+02F1 | CALL_EVENT event 0x056 |
| 9214 | 153.314 | VM 0x056+0000 | ACTOR_ANIM actor 1 anim 0xA8 |
| 9214 | 153.314 | VM 0x056+0003 | ACTOR_ANIM actor 2 anim 0xA8 |
| 9214 | 153.314 | VM 0x056+0006 | ACTOR_ANIM actor 3 anim 0xA8 |
| 9214 | 153.314 | hero0_boy | pose state 0x40 anim 0xA8 |
| 9214 | 153.314 | hero1_girl | pose state 0x40 anim 0xA8 |
| 9214 | 153.314 | hero2_sprite | pose state 0x40 anim 0xA8 |
| 9234 | 153.647 | hero0_boy | pose idle |
| 9234 | 153.647 | hero1_girl | pose idle |
| 9234 | 153.647 | hero2_sprite | pose idle |
| 9239 | 153.730 | VM 0x056+000A | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 9279 | 154.396 | VM 0x4FD+02F3 | WAIT 24 ticks (= 120 frames, 1.997 s) |
| 9399 | 156.392 | VM 0x4FD+02F5 | SCREEN arg 6 word 0xFFFF |
| 9399 | 156.392 | engine | palette_fade_mode_2A 96 (target word $010C = 0xFFFF) |
| 9404 | 156.476 | VM 0x4FD+02F9 | CALL_EVENT event 0x73E |
| 9404 | 156.476 | VM 0x73E+0000 | SOUND cmd 128 id 0x20 word 0x0000 |
| 9404 | 156.476 | sound | raw id 0x20 (cmd 128, params 0x00 0x00) from vm_op |
| 9409 | 156.559 | VM 0x73E+0005 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 9449 | 157.224 | VM 0x4FD+02FB | CALL_EVENT event 0x053 |
| 9449 | 157.224 | VM 0x053+0000 | ACTOR_WALK actor 1 down 0 frames |
| 9449 | 157.224 | VM 0x053+0003 | ACTOR_WALK actor 2 down 0 frames |
| 9449 | 157.224 | VM 0x053+0006 | ACTOR_WALK actor 3 down 0 frames |
| 9449 | 157.224 | hero0_boy | facing down (0x01) |
| 9449 | 157.224 | hero1_girl | facing down (0x01) |
| 9454 | 157.308 | VM 0x4FD+02FD | ACTOR_ANIM_LOOP actor 1 anim 0x89 |
| 9454 | 157.308 | VM 0x4FD+0300 | ACTOR_ANIM_LOOP actor 2 anim 0x89 |
| 9454 | 157.308 | hero0_boy | pose state 0x30 anim 0x89 |
| 9454 | 157.308 | hero1_girl | pose state 0x30 anim 0x89 |
| 9455 | 157.324 | hero0_boy (id 0x80) | walk (168, 316) -> (168, 618), 151 frames, 120.2 px/s, facing down, anim [137], per-frame 151x(+0,+2) [0x4FD+02FD ACTOR_ANIM_LOOP actor 1 anim 0x89] |
| 9455 | 157.324 | hero1_girl (id 0x81) | walk (152, 316) -> (152, 618), 151 frames, 120.2 px/s, facing down, anim [137], per-frame 151x(+0,+2) [0x4FD+0300 ACTOR_ANIM_LOOP actor 2 anim 0x89] |
| 9459 | 157.391 | VM 0x4FD+0304 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 9506 | 158.173 | camera | scroll (40, 244) -> (40, 330), 43 frames |
| 9539 | 158.722 | VM 0x4FD+0306 | CALL_EVENT event 0x732 |
| 9539 | 158.722 | VM 0x732+0000 | SOUND cmd 1 id 0x32 word 0x8F15 |
| 9539 | 158.722 | sound | music id 0x32 (cmd 1, params 0x15 0x8F) from vm_op |
| 9544 | 158.805 | VM 0x4FD+0308 | TOGGLE_HERO_VIS |
| 9544 | 158.805 | hero0_boy | obj+0x0E = 0x80 |
| 9544 | 158.805 | hero1_girl | obj+0x0E = 0x80 |
| 9544 | 158.805 | hero2_sprite | obj+0x0E = 0x80 |
| 9549 | 158.888 | VM 0x4FD+0309 | FLAG_INC flag 0x01 |
| 9549 | 158.888 | VM 0x4FD+030B | MAP_CHANGE transition 1006 |
| 9549 | 158.888 | flag | flag 0x01 0 -> 1 |
| 9550 | 158.905 | screen | fade_out brightness 15 -> 0, 57 frames |
| 9606 | 159.837 | slot7 | removed |
| 9606 | 159.837 | slot8 | removed |
| 9606 | 159.837 | camera | set by the map loader to (216, 488) |
| 9606 | 159.837 | engine | palette_fade_mode_2A 0 (target word $010C = 0xFFFF) |
| 9606 | 159.837 | engine | map 150 loaded |
| 9607 | 159.853 | screen | fade_in brightness 0 -> 15, 15 frames |
| 9610 | 159.903 | hero0_boy | pose idle |
| 9610 | 159.903 | hero1_girl | pose idle |
| 9625 | 160.153 | VM 0x4FD+030D | ACTOR_WALK actor 1 up 0 frames |
| 9625 | 160.153 | VM 0x4FD+0310 | ACTOR_WALK actor 2 up 0 frames |
| 9625 | 160.153 | hero0_boy | facing up (0x00) |
| 9625 | 160.153 | hero1_girl | facing up (0x00) |
| 9630 | 160.236 | VM 0x4FD+0314 | ACTOR_ANIM_LOOP actor 1 anim 0x8B |
| 9630 | 160.236 | VM 0x4FD+0317 | ACTOR_ANIM_LOOP actor 2 anim 0x8B |
| 9630 | 160.236 | VM 0x4FD+031A | ACTOR_ANIM_LOOP actor 5 anim 0x81 |
| 9630 | 160.236 | VM 0x4FD+031D | ACTOR_ANIM_LOOP actor 6 anim 0x81 |
| 9630 | 160.236 | VM 0x4FD+0320 | ACTOR_ANIM_LOOP actor 7 anim 0x81 |
| 9630 | 160.236 | hero0_boy | pose state 0x30 anim 0x8B |
| 9630 | 160.236 | hero1_girl | pose state 0x30 anim 0x8B |
| 9630 | 160.236 | slot4 | facing right (0x02) |
| 9630 | 160.236 | slot4 | pose state 0x30 anim 0x81 |
| 9630 | 160.236 | slot5 | facing right (0x02) |
| 9630 | 160.236 | slot5 | pose state 0x30 anim 0x81 |
| 9630 | 160.236 | slot6 | facing right (0x02) |
| 9630 | 160.236 | slot6 | pose state 0x30 anim 0x81 |
| 9631 | 160.253 | hero0_boy (id 0x80) | walk (344, 602) -> (344, 21), 581 frames, 60.1 px/s, facing up, anim [139], per-frame 581x(+0,-1) [0x4FD+0314 ACTOR_ANIM_LOOP actor 1 anim 0x8B] |
| 9631 | 160.253 | hero1_girl (id 0x81) | walk (344, 602) -> (344, 21), 581 frames, 60.1 px/s, facing up, anim [139], per-frame 581x(+0,-1) [0x4FD+0317 ACTOR_ANIM_LOOP actor 2 anim 0x8B] |
| 9633 | 160.286 | slot4 (id 0xA4) | walk (260, 500) -> (522, 500), 262 frames, 60.1 px/s, facing right, anim [129], per-frame 262x(+1,+0) [0x4FD+031A ACTOR_ANIM_LOOP actor 5 anim 0x81] |
| 9633 | 160.286 | slot5 (id 0xA5) | walk (244, 500) -> (522, 500), 278 frames, 60.1 px/s, facing right, anim [129], per-frame 278x(+1,+0) [0x4FD+031D ACTOR_ANIM_LOOP actor 6 anim 0x81] |
| 9634 | 160.303 | slot6 (id 0xA5) | walk (228, 500) -> (522, 500), 294 frames, 60.1 px/s, facing right, anim [129], per-frame 294x(+1,+0) [0x4FD+0320 ACTOR_ANIM_LOOP actor 7 anim 0x81] |
| 9635 | 160.319 | dialog | 1 text block (#26-#26, CA:50B9 ...), each followed by a wait for a button where the script has one; next command at frame 10155 |
| 9673 | 160.952 | camera | scroll (216, 488) -> (216, 6), 482 frames |
| 10155 | 168.972 | VM 0x4FD+0334 | MAP_CHANGE transition 623 |
| 10156 | 168.988 | screen | fade_out brightness 15 -> 0, 57 frames |
| 10212 | 169.920 | slot7 | appears id 0xB7 at (324,740) |
| 10212 | 169.920 | slot7 | obj+0x0E = 0x00 |
| 10212 | 169.920 | slot8 | appears id 0xB7 at (228,548) |
| 10212 | 169.920 | slot8 | obj+0x0E = 0x00 |
| 10212 | 169.920 | slot9 | appears id 0xB7 at (404,612) |
| 10212 | 169.920 | slot9 | obj+0x0E = 0x00 |
| 10212 | 169.920 | camera | set by the map loader to (216, 1016) |
| 10212 | 169.920 | engine | map 108 loaded |
| 10213 | 169.937 | screen | fade_in brightness 0 -> 15, 15 frames |
| 10215 | 169.970 | slot9 | facing up (0x00) |
| 10216 | 169.987 | hero1_girl | facing down (0x01) |
| 10216 | 169.987 | hero1_girl | pose idle |
| 10231 | 170.236 | VM 0x4FD+0336 | ACTOR_ANIM_LOOP actor 1 anim 0x8B |
| 10231 | 170.236 | VM 0x4FD+0339 | ACTOR_ANIM_LOOP actor 2 anim 0x8B |
| 10231 | 170.236 | VM 0x4FD+033C | ACTOR_ANIM_LOOP actor 4 anim 0x81 |
| 10231 | 170.236 | hero0_boy | facing down (0x01) |
| 10231 | 170.236 | hero1_girl | pose state 0x30 anim 0x8B |
| 10231 | 170.236 | slot3 | pose state 0x30 anim 0x81 |
| 10232 | 170.253 | hero0_boy (id 0x80) | walk (344, 10) -> (344, 1001), 991 frames, 60.1 px/s, facing down, anim [139], per-frame 991x(+0,+1) [0x4FD+0336 ACTOR_ANIM_LOOP actor 1 anim 0x8B] |
| 10232 | 170.253 | hero1_girl (id 0x81) | walk (344, 10) -> (344, 1001), 991 frames, 60.1 px/s, facing down, anim [139], per-frame 991x(+0,+1) [0x4FD+0339 ACTOR_ANIM_LOOP actor 2 anim 0x8B] |
| 10236 | 170.320 | dialog | 1 text block (#27-#27, CA:50D5 ...), each followed by a wait for a button where the script has one; next command at frame 11076 |
| 10293 | 171.268 | camera | scroll (216, 1016) -> (216, 769), 873 frames |
| 11076 | 184.297 | VM 0x4FD+03C6 | ACTOR_WALK actor 4 left 0 frames |
| 11076 | 184.297 | slot3 | facing left (0x82) |
| 11076 | 184.297 | slot3 | pose idle |
| 11081 | 184.380 | VM 0x4FD+03CA | ACTOR_ANIM_LOOP actor 4 anim 0x81 |
| 11081 | 184.380 | slot3 | pose state 0x30 anim 0x81 |
| 11086 | 184.463 | VM 0x4FD+03CE | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 11166 | 185.794 | VM 0x4FD+03D0 | MAP_CHANGE transition 999 |
| 11167 | 185.811 | screen | fade_out brightness 15 -> 0, 57 frames |
| 11223 | 186.742 | slot5 | removed |
| 11223 | 186.742 | slot6 | removed |
| 11223 | 186.742 | slot7 | removed |
| 11223 | 186.742 | slot8 | removed |
| 11223 | 186.742 | slot9 | removed |
| 11223 | 186.742 | camera | set by the map loader to (152, 40) |
| 11223 | 186.742 | engine | map 147 loaded |
| 11224 | 186.759 | screen | fade_in brightness 0 -> 15, 15 frames |
| 11227 | 186.809 | hero0_boy | pose idle |
| 11227 | 186.809 | hero1_girl | pose idle |
| 11242 | 187.059 | VM 0x4FD+03D2 | TOGGLE_HERO_VIS |
| 11242 | 187.059 | hero0_boy | obj+0x0E = 0x00 |
| 11242 | 187.059 | hero1_girl | obj+0x0E = 0x00 |
| 11242 | 187.059 | hero2_sprite | obj+0x0E = 0x00 |
| 11247 | 187.142 | VM 0x4FD+03D3 | ACTOR_WALK actor 2 down 16 frames |
| 11247 | 187.142 | hero1_girl (id 0x81) | walk (280, 154) -> (280, 186), 16 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 16x(+0,+2) [0x4FD+03D3 ACTOR_WALK actor 2 down 16 frames] |
| 11267 | 187.475 | VM 0x4FD+03D7 | ACTOR_WALK actor 2 left 0 frames |
| 11267 | 187.475 | VM 0x4FD+03DA | ACTOR_WALK actor 5 right 0 frames |
| 11267 | 187.475 | VM 0x4FD+03DD | ACTOR_WALK actor 4 right 63 frames |
| 11267 | 187.475 | hero1_girl | facing left (0x82) |
| 11267 | 187.475 | slot3 (id 0xAE) | walk (196, 228) -> (262, 228), 63 frames, 63.0 px/s, facing right, anim [0, 1], per-frame 3x(+2,+0) 60x(+1,+0) [0x4FD+03DD ACTOR_WALK actor 4 right 63 frames] |
| 11267 | 187.475 | slot3 | pose idle |
| 11267 | 187.475 | slot4 | pose idle |
| 11332 | 188.556 | VM 0x4FD+03E1 | ACTOR_WALK actor 4 up 16 frames |
| 11332 | 188.556 | slot3 (id 0xAE) | walk (262, 228) -> (262, 209), 16 frames, 71.4 px/s, facing up, anim [0, 1], per-frame 3x(+0,-2) 13x(+0,-1) [0x4FD+03E1 ACTOR_WALK actor 4 up 16 frames] |
| 11352 | 188.889 | VM 0x4FD+03E5 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 11432 | 190.220 | dialog | 1 text block (#28-#28, CA:517C ...), each followed by a wait for a button where the script has one; next command at frame 11952 |
| 11952 | 198.873 | VM 0x4FD+03F4 | MAP_CHANGE transition 998 |
| 11953 | 198.889 | screen | fade_out brightness 15 -> 0, 57 frames |
| 12009 | 199.821 | slot5 | appears id 0xAF at (292,548) |
| 12009 | 199.821 | slot5 | obj+0x0E = 0x00 |
| 12009 | 199.821 | slot6 | appears id 0xAF at (212,596) |
| 12009 | 199.821 | slot6 | obj+0x0E = 0x00 |
| 12009 | 199.821 | slot7 | appears id 0xAF at (324,596) |
| 12009 | 199.821 | slot7 | obj+0x0E = 0x00 |
| 12009 | 199.821 | camera | set by the map loader to (136, 712) |
| 12009 | 199.821 | engine | map 146 loaded |
| 12010 | 199.838 | screen | fade_in brightness 0 -> 15, 15 frames |
| 12013 | 199.888 | hero1_girl | facing down (0x01) |
| 12028 | 200.137 | VM 0x4FD+03F6 | ACTOR_WALK actor 1 up 8 frames |
| 12028 | 200.137 | VM 0x4FD+03F9 | ACTOR_WALK actor 2 up 0 frames |
| 12028 | 200.137 | hero0_boy (id 0x80) | walk (264, 826) -> (264, 810), 8 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 8x(+0,-2) [0x4FD+03F6 ACTOR_WALK actor 1 up 8 frames] |
| 12028 | 200.137 | hero1_girl | facing up (0x00) |
| 12038 | 200.304 | VM 0x4FD+03FD | ACTOR_ANIM_LOOP actor 1 anim 0x89 |
| 12038 | 200.304 | VM 0x4FD+0400 | ACTOR_ANIM_LOOP actor 2 anim 0x89 |
| 12038 | 200.304 | hero0_boy | pose state 0x30 anim 0x89 |
| 12038 | 200.304 | hero1_girl | pose state 0x30 anim 0x89 |
| 12039 | 200.320 | hero0_boy (id 0x80) | walk (264, 810) -> (264, 562), 124 frames, 120.2 px/s, facing up, anim [137], per-frame 124x(+0,-2) [0x4FD+03FD ACTOR_ANIM_LOOP actor 1 anim 0x89] |
| 12039 | 200.320 | hero1_girl (id 0x81) | walk (264, 826) -> (264, 578), 124 frames, 120.2 px/s, facing up, anim [137], per-frame 124x(+0,-2) [0x4FD+0400 ACTOR_ANIM_LOOP actor 2 anim 0x89] |
| 12043 | 200.387 | VM 0x4FD+0404 | WAIT 24 ticks (= 120 frames, 1.997 s) |
| 12052 | 200.536 | camera | scroll (136, 712) -> (136, 490), 111 frames |
| 12163 | 202.383 | VM 0x4FD+0406 | CALL_EVENT event 0x052 |
| 12163 | 202.383 | VM 0x052+0000 | ACTOR_WALK actor 1 up 0 frames |
| 12163 | 202.383 | VM 0x052+0003 | ACTOR_WALK actor 2 up 0 frames |
| 12163 | 202.383 | VM 0x052+0006 | ACTOR_WALK actor 3 up 0 frames |
| 12163 | 202.383 | hero0_boy | pose idle |
| 12163 | 202.383 | hero1_girl | pose idle |
| 12163 | 202.383 | hero2_sprite | facing up (0x00) |
| 12168 | 202.467 | VM 0x4FD+0408 | ACTOR_WALK actor 5 down 0 frames |
| 12168 | 202.467 | VM 0x4FD+040B | ACTOR_WALK actor 6 down 0 frames |
| 12168 | 202.467 | VM 0x4FD+040E | ACTOR_WALK actor 7 down 0 frames |
| 12168 | 202.467 | VM 0x4FD+0411 | ACTOR_WALK actor 8 down 0 frames |
| 12168 | 202.467 | slot4 | facing down (0x01) |
| 12168 | 202.467 | slot5 | facing down (0x01) |
| 12168 | 202.467 | slot6 | facing down (0x01) |
| 12173 | 202.550 | dialog | 1 text block (#29-#29, CA:51AA ...), each followed by a wait for a button where the script has one; next command at frame 13393 |
| 13393 | 222.850 | VM 0x4FD+0527 | MAP_CHANGE transition 345 |
| 13394 | 222.866 | screen | fade_out brightness 15 -> 0, 57 frames |
| 13450 | 223.798 | slot3 | removed |
| 13450 | 223.798 | slot4 | removed |
| 13450 | 223.798 | slot5 | removed |
| 13450 | 223.798 | slot6 | removed |
| 13450 | 223.798 | slot7 | removed |
| 13450 | 223.798 | camera | set by the map loader to (56, 248) |
| 13450 | 223.798 | engine | map 106 loaded |
| 13451 | 223.815 | screen | fade_in brightness 0 -> 15, 15 frames |
| 13454 | 223.865 | hero2_sprite | facing down (0x01) |
| 13469 | 224.114 | VM 0x4FD+0529 | ACTOR_WALK actor 2 right 8 frames |
| 13469 | 224.114 | hero1_girl (id 0x81) | walk (184, 362) -> (200, 362), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x4FD+0529 ACTOR_WALK actor 2 right 8 frames] |
| 13479 | 224.281 | VM 0x4FD+052D | ACTOR_WALK actor 2 down 0 frames |
| 13479 | 224.281 | hero1_girl | facing down (0x01) |
| 13484 | 224.364 | dialog | 1 text block (#30-#30, CA:52C6 ...), each followed by a wait for a button where the script has one; next command at frame 14004 |
| 14004 | 233.016 | VM 0x4FD+0544 | MAP_CHANGE transition 1007 |
| 14005 | 233.033 | screen | fade_out brightness 15 -> 0, 57 frames |
| 14061 | 233.965 | slot3 | appears id 0xCA at (180,468) |
| 14061 | 233.965 | slot3 | obj+0x0E = 0x00 |
| 14061 | 233.965 | slot4 | appears id 0x0D at (180,468) |
| 14061 | 233.965 | slot4 | obj+0x0E = 0x00 |
| 14061 | 233.965 | slot5 | appears id 0x0D at (196,468) |
| 14061 | 233.965 | slot5 | obj+0x0E = 0x00 |
| 14061 | 233.965 | camera | set by the map loader to (248, 408) |
| 14061 | 233.965 | engine | map 151 loaded |
| 14062 | 233.981 | screen | fade_in brightness 0 -> 15, 15 frames |
| 14080 | 234.281 | VM 0x4FD+0546 | ACTOR_WALK actor 2 right 8 frames |
| 14080 | 234.281 | hero1_girl (id 0x81) | walk (376, 522) -> (392, 522), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x4FD+0546 ACTOR_WALK actor 2 right 8 frames] |
| 14090 | 234.447 | VM 0x4FD+054A | ACTOR_WALK actor 1 up 0 frames |
| 14090 | 234.447 | VM 0x4FD+054D | ACTOR_WALK actor 2 up 0 frames |
| 14090 | 234.447 | hero1_girl | facing up (0x00) |
| 14095 | 234.530 | VM 0x4FD+0551 | ACTOR_ANIM_LOOP actor 4 anim 0x81 |
| 14095 | 234.530 | VM 0x4FD+0554 | ACTOR_ANIM_LOOP actor 5 anim 0x81 |
| 14095 | 234.530 | VM 0x4FD+0557 | ACTOR_ANIM_LOOP actor 6 anim 0x81 |
| 14095 | 234.530 | slot3 | facing right (0x02) |
| 14095 | 234.530 | slot3 | pose state 0x30 anim 0x81 |
| 14095 | 234.530 | slot4 | facing right (0x02) |
| 14095 | 234.530 | slot4 | pose state 0x30 anim 0x81 |
| 14095 | 234.530 | slot5 | facing right (0x02) |
| 14095 | 234.530 | slot5 | pose state 0x30 anim 0x81 |
| 14098 | 234.580 | slot3 (id 0xCA) | walk (180, 468) -> (586, 468), 406 frames, 60.1 px/s, facing right, anim [129], per-frame 406x(+1,+0) [0x4FD+0551 ACTOR_ANIM_LOOP actor 4 anim 0x81] |
| 14100 | 234.614 | dialog | 1 text block (#31-#31, CA:52F0 ...), each followed by a wait for a button where the script has one; next command at frame 15130 |
| 14103 | 234.664 | slot4 (id 0x0D) | autonomous movement of the object (its own AI, no VM command): 28 segments, frames 14103-14778, x 180..586, y 468..468 |
| 14103 | 234.664 | slot5 (id 0x0D) | autonomous movement of the object (its own AI, no VM command): 26 segments, frames 14103-14742, x 196..586, y 468..468 |
| 15130 | 251.752 | VM 0x4FD+0643 | MAP_CHANGE transition 68 |
| 15131 | 251.769 | screen | fade_out brightness 15 -> 0, 57 frames |
| 15187 | 252.701 | slot6 | appears id 0xDD at (212,116) |
| 15187 | 252.701 | slot6 | obj+0x0E = 0x00 |
| 15187 | 252.701 | slot7 | appears id 0xDE at (212,116) |
| 15187 | 252.701 | slot7 | obj+0x0E = 0x00 |
| 15187 | 252.701 | slot8 | appears id 0xCE at (164,244) |
| 15187 | 252.701 | slot8 | obj+0x0E = 0x00 |
| 15187 | 252.701 | slot9 | appears id 0xCE at (148,276) |
| 15187 | 252.701 | slot9 | obj+0x0E = 0x00 |
| 15187 | 252.701 | slot10 | appears id 0xCE at (180,276) |
| 15187 | 252.701 | slot10 | obj+0x0E = 0x00 |
| 15187 | 252.701 | slot11 | appears id 0xCE at (164,260) |
| 15187 | 252.701 | slot11 | obj+0x0E = 0x00 |
| 15187 | 252.701 | camera | set by the map loader to (56, 8) |
| 15187 | 252.701 | engine | map 105 loaded |
| 15188 | 252.717 | screen | fade_in brightness 0 -> 15, 15 frames |
| 15190 | 252.750 | slot9 | facing down (0x01) |
| 15190 | 252.750 | slot10 | facing down (0x01) |
| 15190 | 252.750 | slot11 | facing down (0x01) |
| 15191 | 252.767 | hero0_boy | facing down (0x01) |
| 15191 | 252.767 | hero1_girl | facing down (0x01) |
| 15194 | 252.817 | slot8 | facing down (0x01) |
| 15206 | 253.017 | VM 0x4FD+0645 | ACTOR_WALK actor 1 down 28 frames |
| 15206 | 253.017 | hero0_boy (id 0x80) | walk (184, 122) -> (184, 178), 28 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 28x(+0,+2) [0x4FD+0645 ACTOR_WALK actor 1 down 28 frames] |
| 15236 | 253.516 | VM 0x4FD+0649 | ACTOR_WALK actor 1 right 12 frames |
| 15236 | 253.516 | VM 0x4FD+064C | ACTOR_WALK actor 2 down 28 frames |
| 15236 | 253.516 | hero0_boy (id 0x80) | walk (184, 178) -> (208, 178), 12 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 12x(+2,+0) [0x4FD+0649 ACTOR_WALK actor 1 right 12 frames] |
| 15236 | 253.516 | hero1_girl (id 0x81) | walk (184, 122) -> (184, 178), 28 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 28x(+0,+2) [0x4FD+064C ACTOR_WALK actor 2 down 28 frames] |
| 15266 | 254.015 | VM 0x4FD+0650 | ACTOR_WALK actor 1 down 63 frames |
| 15266 | 254.015 | VM 0x4FD+0653 | ACTOR_WALK actor 2 right 16 frames |
| 15266 | 254.015 | hero0_boy (id 0x80) | walk (208, 178) -> (208, 280), 51 frames, 120.2 px/s, facing down, anim [1], per-frame 51x(+0,+2) [0x4FD+0650 ACTOR_WALK actor 1 down 63 frames] |
| 15266 | 254.015 | hero1_girl (id 0x81) | walk (184, 178) -> (216, 178), 16 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 16x(+2,+0) [0x4FD+0653 ACTOR_WALK actor 2 right 16 frames] |
| 15268 | 254.048 | camera | scroll (56, 8) -> (56, 106), 49 frames |
| 15331 | 255.097 | VM 0x4FD+0657 | ACTOR_WALK actor 1 left 4 frames |
| 15331 | 255.097 | VM 0x4FD+065A | ACTOR_WALK actor 2 down 56 frames |
| 15331 | 255.097 | hero0_boy (id 0x80) | walk (208, 280) -> (200, 280), 4 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 4x(-2,+0) [0x4FD+0657 ACTOR_WALK actor 1 left 4 frames] |
| 15331 | 255.097 | hero1_girl (id 0x81) | walk (216, 178) -> (216, 280), 51 frames, 120.2 px/s, facing down, anim [1], per-frame 51x(+0,+2) [0x4FD+065A ACTOR_WALK actor 2 down 56 frames] |
| 15391 | 256.095 | VM 0x4FD+065E | ACTOR_WALK actor 2 left 0 frames |
| 15391 | 256.095 | hero1_girl | facing left (0x82) |
| 15396 | 256.178 | dialog | 1 text block (#32-#32, CA:53F7 ...), each followed by a wait for a button where the script has one; next command at frame 15916 |
| 15916 | 264.831 | VM 0x4FD+0677 | MAP_CHANGE transition 1008 |
| 15917 | 264.847 | screen | fade_out brightness 15 -> 0, 57 frames |
| 15973 | 265.779 | slot4 | removed |
| 15973 | 265.779 | slot5 | removed |
| 15973 | 265.779 | slot6 | removed |
| 15973 | 265.779 | slot7 | removed |
| 15973 | 265.779 | slot8 | removed |
| 15973 | 265.779 | slot9 | removed |
| 15973 | 265.779 | slot10 | removed |
| 15973 | 265.779 | slot11 | removed |
| 15973 | 265.779 | camera | set by the map loader to (504, 568) |
| 15973 | 265.779 | engine | map 152 loaded |
| 15974 | 265.796 | screen | fade_in brightness 0 -> 15, 15 frames |
| 15977 | 265.846 | hero2_sprite | facing left (0x82) |
| 15992 | 266.095 | VM 0x4FD+0679 | ACTOR_WALK actor 1 left 8 frames |
| 15992 | 266.095 | hero0_boy (id 0x80) | walk (632, 682) -> (616, 682), 8 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 8x(-2,+0) [0x4FD+0679 ACTOR_WALK actor 1 left 8 frames] |
| 16002 | 266.262 | VM 0x4FD+067D | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 16082 | 267.593 | VM 0x4FD+067F | CALL_EVENT event 0x056 |
| 16082 | 267.593 | VM 0x056+0000 | ACTOR_ANIM actor 1 anim 0xA8 |
| 16082 | 267.593 | VM 0x056+0003 | ACTOR_ANIM actor 2 anim 0xA8 |
| 16082 | 267.593 | VM 0x056+0006 | ACTOR_ANIM actor 3 anim 0xA8 |
| 16082 | 267.593 | hero0_boy | pose state 0x40 anim 0xA8 |
| 16082 | 267.593 | hero1_girl | pose state 0x40 anim 0xA8 |
| 16082 | 267.593 | hero2_sprite | pose state 0x40 anim 0xA8 |
| 16102 | 267.925 | hero0_boy | pose idle |
| 16102 | 267.925 | hero1_girl | pose idle |
| 16102 | 267.925 | hero2_sprite | pose idle |
| 16107 | 268.009 | VM 0x056+000A | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 16147 | 268.674 | VM 0x4FD+0681 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 16227 | 270.005 | VM 0x4FD+0683 | ACTOR_WALK actor 4 down 0 frames |
| 16227 | 270.005 | slot3 | facing down (0x01) |
| 16227 | 270.005 | slot3 | pose idle |
| 16232 | 270.089 | VM 0x4FD+0687 | ACTOR_ANIM_LOOP actor 4 anim 0x81 |
| 16232 | 270.089 | slot3 | pose state 0x30 anim 0x81 |
| 16235 | 270.139 | slot3 (id 0x9C) | walk (564, 676) -> (564, 843), 167 frames, 60.1 px/s, facing down, anim [129], per-frame 167x(+0,+1) [0x4FD+0687 ACTOR_ANIM_LOOP actor 4 anim 0x81] |
| 16237 | 270.172 | dialog | 1 text block (#33-#33, CA:5420 ...), each followed by a wait for a button where the script has one; next command at frame 17172 |
| 16402 | 272.917 | slot3 (id 0x9C) | autonomous movement of the object (its own AI, no VM command): 761 segments, frames 16402-17228, x 564..608, y 843..917 |
| 17172 | 285.729 | VM 0x4FD+0753 | MAP_CHANGE transition 1009 |
| 17173 | 285.746 | screen | fade_out brightness 15 -> 0, 57 frames |
| 17229 | 286.678 | camera | set by the map loader to (24, 72) |
| 17229 | 286.678 | engine | map 153 loaded |
| 17230 | 286.695 | screen | fade_in brightness 0 -> 15, 15 frames |
| 17233 | 286.744 | hero0_boy | facing down (0x01) |
| 17233 | 286.744 | hero1_girl | facing down (0x01) |
| 17233 | 286.744 | hero2_sprite | facing down (0x01) |
| 17248 | 286.994 | VM 0x4FD+0755 | ACTOR_WALK actor 1 right 8 frames |
| 17248 | 286.994 | hero0_boy (id 0x80) | walk (152, 186) -> (168, 186), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x4FD+0755 ACTOR_WALK actor 1 right 8 frames] |
| 17258 | 287.160 | VM 0x4FD+0759 | ACTOR_WALK actor 1 right 56 frames |
| 17258 | 287.160 | VM 0x4FD+075C | ACTOR_WALK actor 2 right 56 frames |
| 17258 | 287.160 | hero0_boy (id 0x80) | walk (168, 186) -> (280, 186), 56 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 56x(+2,+0) [0x4FD+0759 ACTOR_WALK actor 1 right 56 frames] |
| 17258 | 287.160 | hero1_girl (id 0x81) | walk (152, 186) -> (264, 186), 56 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 56x(+2,+0) [0x4FD+075C ACTOR_WALK actor 2 right 56 frames] |
| 17285 | 287.610 | camera | scroll (24, 72) -> (82, 72), 29 frames |
| 17318 | 288.159 | VM 0x4FD+0760 | ACTOR_WALK actor 1 right 56 frames |
| 17318 | 288.159 | VM 0x4FD+0763 | ACTOR_WALK actor 2 right 56 frames |
| 17318 | 288.159 | hero0_boy (id 0x80) | walk (280, 186) -> (392, 186), 56 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 56x(+2,+0) [0x4FD+0760 ACTOR_WALK actor 1 right 56 frames] |
| 17318 | 288.159 | hero1_girl (id 0x81) | walk (264, 186) -> (376, 186), 56 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 56x(+2,+0) [0x4FD+0763 ACTOR_WALK actor 2 right 56 frames] |
| 17318 | 288.159 | camera | scroll (82, 72) -> (194, 72), 56 frames |
| 17325 | 288.275 | slot3 | pose idle |
| 17378 | 289.157 | VM 0x4FD+0767 | ACTOR_WALK actor 1 down 48 frames |
| 17378 | 289.157 | VM 0x4FD+076A | ACTOR_WALK actor 2 down 56 frames |
| 17378 | 289.157 | hero0_boy (id 0x80) | walk (392, 186) -> (392, 282), 48 frames, 120.2 px/s, facing down, anim [0, 1], per-frame 48x(+0,+2) [0x4FD+0767 ACTOR_WALK actor 1 down 48 frames] |
| 17378 | 289.157 | hero1_girl (id 0x81) | walk (376, 186) -> (376, 282), 48 frames, 120.2 px/s, facing down, anim [1], per-frame 48x(+0,+2) [0x4FD+076A ACTOR_WALK actor 2 down 56 frames] |
| 17408 | 289.656 | camera | scroll (194, 72) -> (194, 108), 18 frames |
| 17438 | 290.156 | VM 0x4FD+076E | CALL_EVENT event 0x055 |
| 17438 | 290.156 | VM 0x055+0000 | ACTOR_WALK actor 1 left 0 frames |
| 17438 | 290.156 | VM 0x055+0003 | ACTOR_WALK actor 2 left 0 frames |
| 17438 | 290.156 | VM 0x055+0006 | ACTOR_WALK actor 3 left 0 frames |
| 17438 | 290.156 | hero0_boy | facing left (0x82) |
| 17438 | 290.156 | hero1_girl | facing left (0x82) |
| 17438 | 290.156 | hero2_sprite | facing left (0x82) |
| 17443 | 290.239 | dialog | 1 text block (#34-#34, CA:5505 ...), each followed by a wait for a button where the script has one; next command at frame 18668 |
| 18668 | 310.622 | VM 0x4FD+07D9 | MAP_CHANGE transition 67 |
| 18669 | 310.638 | screen | fade_out brightness 15 -> 0, 57 frames |
| 18725 | 311.570 | slot4 | appears id 0xA6 at (356,692) |
| 18725 | 311.570 | slot4 | obj+0x0E = 0x00 |
| 18725 | 311.570 | slot5 | appears id 0xC9 at (356,660) |
| 18725 | 311.570 | slot5 | obj+0x0E = 0x00 |
| 18725 | 311.570 | slot6 | appears id 0xCA at (372,692) |
| 18725 | 311.570 | slot6 | obj+0x0E = 0x00 |
| 18725 | 311.570 | camera | set by the map loader to (24, 632) |
| 18725 | 311.570 | engine | map 104 loaded |
| 18726 | 311.587 | screen | fade_in brightness 0 -> 15, 15 frames |
| 18729 | 311.637 | hero0_boy | facing down (0x01) |
| 18729 | 311.637 | hero1_girl | facing down (0x01) |
| 18729 | 311.637 | hero2_sprite | facing down (0x01) |
| 18744 | 311.886 | VM 0x4FD+07DB | ACTOR_WALK actor 1 up 9 frames |
| 18744 | 311.886 | VM 0x4FD+07DE | ACTOR_WALK actor 2 up 17 frames |
| 18744 | 311.886 | hero0_boy (id 0x80) | walk (152, 746) -> (152, 728), 9 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 9x(+0,-2) [0x4FD+07DB ACTOR_WALK actor 1 up 9 frames] |
| 18744 | 311.886 | hero1_girl (id 0x81) | walk (152, 746) -> (152, 712), 17 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 17x(+0,-2) [0x4FD+07DE ACTOR_WALK actor 2 up 17 frames] |
| 18764 | 312.219 | VM 0x4FD+07E2 | ACTOR_WALK actor 1 right 60 frames |
| 18764 | 312.219 | VM 0x4FD+07E5 | ACTOR_WALK actor 2 right 60 frames |
| 18764 | 312.219 | hero0_boy (id 0x80) | walk (152, 728) -> (504, 728), 176 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 176x(+2,+0) [0x4FD+07E2 ACTOR_WALK actor 1 right 60 frames] |
| 18764 | 312.219 | hero1_girl (id 0x81) | walk (152, 712) -> (504, 712), 176 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 176x(+2,+0) [0x4FD+07E5 ACTOR_WALK actor 2 right 60 frames] |
| 18799 | 312.802 | camera | scroll (24, 632) -> (306, 632), 141 frames |
| 18824 | 313.218 | VM 0x4FD+07E9 | ACTOR_WALK actor 1 right 60 frames |
| 18824 | 313.218 | VM 0x4FD+07EC | ACTOR_WALK actor 2 right 60 frames |
| 18884 | 314.216 | VM 0x4FD+07F0 | ACTOR_WALK actor 1 right 56 frames |
| 18884 | 314.216 | VM 0x4FD+07F3 | ACTOR_WALK actor 2 right 56 frames |
| 18944 | 315.214 | VM 0x4FD+07F7 | ACTOR_WALK actor 1 up 0 frames |
| 18944 | 315.214 | VM 0x4FD+07FA | ACTOR_WALK actor 4 left 8 frames |
| 18944 | 315.214 | hero0_boy | facing up (0x00) |
| 18944 | 315.214 | slot3 (id 0xBB) | walk (532, 708) -> (521, 708), 8 frames, 82.6 px/s, facing left, anim [0, 1], per-frame 3x(-2,+0) 5x(-1,+0) [0x4FD+07FA ACTOR_WALK actor 4 left 8 frames] |
| 18954 | 315.381 | dialog | 1 text block (#35-#35, CA:5593 ...), each followed by a wait for a button where the script has one; next command at frame 19664 |
| 19664 | 327.195 | VM 0x4FD+0868 | ACTOR_WALK actor 2 down 0 frames |
| 19664 | 327.195 | hero1_girl | facing down (0x01) |
| 19669 | 327.278 | dialog | 1 text block (#36-#36, CA:5601 ...), each followed by a wait for a button where the script has one; next command at frame 20509 |
| 20509 | 341.255 | VM 0x4FD+08CA | CALL_EVENT event 0x05C |
| 20509 | 341.255 | VM 0x05C+0000 | ACTOR_ANIM actor 2 anim 0xA9 |
| 20509 | 341.255 | hero1_girl | pose state 0x40 anim 0xA9 |
| 20549 | 341.920 | hero1_girl | pose idle |
| 20554 | 342.004 | VM 0x05C+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 20594 | 342.669 | VM 0x4FD+08CC | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 20674 | 344.000 | VM 0x4FD+08CE | CALL_EVENT event 0x059 |
| 20674 | 344.000 | VM 0x059+0000 | ACTOR_ANIM actor 2 anim 0xA8 |
| 20674 | 344.000 | hero1_girl | pose state 0x40 anim 0xA8 |
| 20694 | 344.333 | hero1_girl | pose idle |
| 20699 | 344.416 | VM 0x059+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 20739 | 345.082 | VM 0x4FD+08D0 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 20899 | 347.744 | VM 0x4FD+08D2 | ACTOR_DELETE arg 0x01 |
| 20904 | 347.827 | VM 0x4FD+08D4 | FLAG_INC flag 0x68 |
| 20904 | 347.827 | VM 0x4FD+08D6 | REFRESH_OBJECTS |
| 20904 | 347.827 | slot11 | facing left (0x82) |
| 20904 | 347.827 | slot11 | appears id 0x8B at (500,708) |
| 20904 | 347.827 | slot11 | obj+0x0E = 0x00 |
| 20904 | 347.827 | flag | flag 0x68 0 -> 1 |
| 20909 | 347.910 | VM 0x4FD+08D7 | ACTOR_WALK actor 1 left 0 frames |
| 20909 | 347.910 | hero0_boy | facing left (0x82) |
| 20914 | 347.994 | VM 0x4FD+08DB | ACTOR_ANIM_LOOP actor 1 anim 0x89 |
| 20914 | 347.994 | hero0_boy | pose state 0x30 anim 0x89 |
| 20915 | 348.010 | hero0_boy (id 0x80) | walk (504, 728) -> (302, 728), 101 frames, 120.2 px/s, facing left, anim [137], per-frame 101x(-2,+0) [0x4FD+08DB ACTOR_ANIM_LOOP actor 1 anim 0x89] |
| 20919 | 348.077 | VM 0x4FD+08DF | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 20959 | 348.742 | VM 0x4FD+08E1 | MAP_CHANGE transition 66 |
| 20960 | 348.759 | screen | fade_out brightness 15 -> 0, 57 frames |
| 21016 | 349.691 | slot4 | removed |
| 21016 | 349.691 | slot5 | removed |
| 21016 | 349.691 | slot6 | removed |
| 21016 | 349.691 | slot11 | removed |
| 21016 | 349.691 | camera | set by the map loader to (264, 728) |
| 21016 | 349.691 | engine | map 103 loaded |
| 21017 | 349.707 | screen | fade_in brightness 0 -> 15, 15 frames |
| 21020 | 349.757 | hero0_boy | facing down (0x01) |
| 21020 | 349.757 | hero0_boy | pose idle |
| 21035 | 350.007 | VM 0x4FD+08E3 | ACTOR_WALK actor 1 up 63 frames |
| 21035 | 350.007 | hero0_boy (id 0x80) | walk (392, 842) -> (392, 716), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+08E3 ACTOR_WALK actor 1 up 63 frames] |
| 21056 | 350.356 | camera | scroll (264, 728) -> (264, 644), 42 frames |
| 21100 | 351.089 | VM 0x4FD+08E7 | ACTOR_WALK actor 1 up 63 frames |
| 21100 | 351.089 | hero0_boy (id 0x80) | walk (392, 716) -> (392, 590), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+08E7 ACTOR_WALK actor 1 up 63 frames] |
| 21100 | 351.089 | camera | scroll (264, 644) -> (264, 518), 63 frames |
| 21165 | 352.170 | VM 0x4FD+08EB | ACTOR_WALK actor 1 up 52 frames |
| 21165 | 352.170 | hero0_boy (id 0x80) | walk (392, 590) -> (392, 486), 52 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 52x(+0,-2) [0x4FD+08EB ACTOR_WALK actor 1 up 52 frames] |
| 21165 | 352.170 | camera | scroll (264, 518) -> (264, 414), 52 frames |
| 21220 | 353.085 | dialog | 1 text block (#37-#37, CA:5684 ...), each followed by a wait for a button where the script has one; next command at frame 22025 |
| 22025 | 366.480 | VM 0x4FD+0980 | MAP_CHANGE transition 65 |
| 22026 | 366.497 | screen | fade_out brightness 15 -> 0, 57 frames |
| 22082 | 367.428 | slot4 | appears id 0xC1 at (292,372) |
| 22082 | 367.428 | slot4 | obj+0x0E = 0x00 |
| 22082 | 367.428 | slot5 | appears id 0xC9 at (308,388) |
| 22082 | 367.428 | slot5 | obj+0x0E = 0x00 |
| 22082 | 367.428 | slot6 | appears id 0xC8 at (308,420) |
| 22082 | 367.428 | slot6 | obj+0x0E = 0x00 |
| 22082 | 367.428 | camera | set by the map loader to (808, 264) |
| 22082 | 367.428 | engine | map 102 loaded |
| 22083 | 367.445 | screen | fade_in brightness 0 -> 15, 15 frames |
| 22101 | 367.744 | VM 0x4FD+0982 | ACTOR_WALK actor 1 right 63 frames |
| 22101 | 367.744 | hero0_boy (id 0x80) | walk (104, 378) -> (230, 378), 63 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 63x(+2,+0) [0x4FD+0982 ACTOR_WALK actor 1 right 63 frames] |
| 22136 | 368.327 | camera | scroll (808, 264) -> (32, 264), 28 frames |
| 22166 | 368.826 | VM 0x4FD+0986 | ACTOR_WALK actor 1 right 8 frames |
| 22166 | 368.826 | VM 0x4FD+0989 | ACTOR_WALK actor 4 left 16 frames |
| 22166 | 368.826 | VM 0x4FD+098C | ACTOR_WALK actor 5 left 16 frames |
| 22166 | 368.826 | VM 0x4FD+098F | ACTOR_WALK actor 6 left 16 frames |
| 22166 | 368.826 | VM 0x4FD+0992 | ACTOR_WALK actor 7 left 16 frames |
| 22166 | 368.826 | hero0_boy (id 0x80) | walk (230, 378) -> (246, 378), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x4FD+0986 ACTOR_WALK actor 1 right 8 frames] |
| 22166 | 368.826 | slot3 (id 0xC0) | walk (292, 404) -> (273, 404), 16 frames, 71.4 px/s, facing left, anim [0, 1], per-frame 3x(-2,+0) 13x(-1,+0) [0x4FD+0989 ACTOR_WALK actor 4 left 16 frames] |
| 22166 | 368.826 | slot4 (id 0xC1) | walk (292, 372) -> (273, 372), 16 frames, 71.4 px/s, facing left, anim [0, 1], per-frame 3x(-2,+0) 13x(-1,+0) [0x4FD+098C ACTOR_WALK actor 5 left 16 frames] |
| 22166 | 368.826 | slot5 (id 0xC9) | walk (308, 388) -> (289, 388), 16 frames, 71.4 px/s, facing left, anim [0, 1], per-frame 3x(-2,+0) 13x(-1,+0) [0x4FD+098F ACTOR_WALK actor 6 left 16 frames] |
| 22166 | 368.826 | slot6 (id 0xC8) | walk (308, 420) -> (288, 420), 16 frames, 75.1 px/s, facing left, anim [0, 1], per-frame 4x(-2,+0) 12x(-1,+0) [0x4FD+0992 ACTOR_WALK actor 7 left 16 frames] |
| 22166 | 368.826 | camera | scroll (32, 264) -> (48, 264), 8 frames |
| 22186 | 369.159 | dialog | 1 text block (#38-#38, CA:572B ...), each followed by a wait for a button where the script has one; next command at frame 23216 |
| 23216 | 386.297 | VM 0x4FD+0A79 | CALL_EVENT event 0x058 |
| 23216 | 386.297 | VM 0x058+0000 | ACTOR_ANIM actor 1 anim 0xA8 |
| 23216 | 386.297 | hero0_boy | pose state 0x40 anim 0xA8 |
| 23236 | 386.630 | hero0_boy | pose idle |
| 23241 | 386.713 | VM 0x058+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 23281 | 387.379 | VM 0x4FD+0A7B | CALL_EVENT event 0x748 |
| 23281 | 387.379 | VM 0x748+0000 | SOUND cmd 128 id 0x80 word 0x0000 |
| 23281 | 387.379 | sound | raw id 0x80 (cmd 128, params 0x00 0x00) from vm_op |
| 23286 | 387.462 | VM 0x4FD+0A7D | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 23326 | 388.128 | VM 0x4FD+0A7F | FLAG_SET flag 0xF7 = 12 |
| 23326 | 388.128 | flag | flag 0xF7 15 -> 12 |
| 23331 | 388.211 | VM 0x4FD+0A82 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 23371 | 388.876 | VM 0x4FD+0A84 | FLAG_SET flag 0xF7 = 10 |
| 23371 | 388.876 | flag | flag 0xF7 12 -> 10 |
| 23376 | 388.960 | VM 0x4FD+0A87 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 23416 | 389.625 | VM 0x4FD+0A89 | FLAG_SET flag 0xF7 = 8 |
| 23416 | 389.625 | flag | flag 0xF7 10 -> 8 |
| 23421 | 389.708 | VM 0x4FD+0A8C | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 23461 | 390.374 | VM 0x4FD+0A8E | FLAG_SET flag 0xF7 = 6 |
| 23461 | 390.374 | flag | flag 0xF7 8 -> 6 |
| 23466 | 390.457 | VM 0x4FD+0A91 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 23506 | 391.123 | VM 0x4FD+0A93 | FLAG_SET flag 0xF7 = 4 |
| 23506 | 391.123 | flag | flag 0xF7 6 -> 4 |
| 23511 | 391.206 | VM 0x4FD+0A96 | ACTOR_WALK actor 1 up 0 frames |
| 23511 | 391.206 | VM 0x4FD+0A99 | ACTOR_WALK actor 4 up 0 frames |
| 23511 | 391.206 | VM 0x4FD+0A9C | ACTOR_WALK actor 5 up 0 frames |
| 23511 | 391.206 | VM 0x4FD+0A9F | ACTOR_WALK actor 6 up 0 frames |
| 23511 | 391.206 | VM 0x4FD+0AA2 | ACTOR_WALK actor 7 up 0 frames |
| 23511 | 391.206 | hero0_boy | facing up (0x00) |
| 23511 | 391.206 | slot3 | facing up (0x00) |
| 23511 | 391.206 | slot4 | facing up (0x00) |
| 23511 | 391.206 | slot5 | facing up (0x00) |
| 23511 | 391.206 | slot6 | facing up (0x00) |
| 23516 | 391.289 | VM 0x4FD+0AA6 | WAIT 9 ticks (= 45 frames, 0.749 s) |
| 23561 | 392.038 | VM 0x4FD+0AA8 | FLAG_DEC flag 0xF7 |
| 23561 | 392.038 | VM 0x4FD+0AAA | WAIT 10 ticks (= 50 frames, 0.832 s) |
| 23561 | 392.038 | flag | flag 0xF7 4 -> 3 |
| 23611 | 392.870 | VM 0x4FD+0AAC | FLAG_DEC flag 0xF7 |
| 23611 | 392.870 | VM 0x4FD+0AAE | WAIT 11 ticks (= 55 frames, 0.915 s) |
| 23611 | 392.870 | flag | flag 0xF7 3 -> 2 |
| 23666 | 393.785 | VM 0x4FD+0AB0 | FLAG_DEC flag 0xF7 |
| 23666 | 393.785 | VM 0x4FD+0AB2 | WAIT 12 ticks (= 60 frames, 0.998 s) |
| 23666 | 393.785 | flag | flag 0xF7 2 -> 1 |
| 23726 | 394.783 | VM 0x4FD+0AB4 | FLAG_SET flag 0xF7 = 0 |
| 23726 | 394.783 | flag | flag 0xF7 1 -> 0 |
| 23731 | 394.866 | VM 0x4FD+0AB7 | ACTOR_WALK actor 1 up 0 frames |
| 23731 | 394.866 | VM 0x4FD+0ABA | ACTOR_WALK actor 4 up 0 frames |
| 23731 | 394.866 | VM 0x4FD+0ABD | ACTOR_WALK actor 5 up 0 frames |
| 23731 | 394.866 | VM 0x4FD+0AC0 | ACTOR_WALK actor 6 up 0 frames |
| 23731 | 394.866 | VM 0x4FD+0AC3 | ACTOR_WALK actor 7 up 0 frames |
| 23736 | 394.950 | VM 0x4FD+0AC7 | CALL_EVENT event 0x73A |
| 23736 | 394.950 | VM 0x73A+0000 | SOUND cmd 1 id 0x3A word 0x8F1B |
| 23736 | 394.950 | sound | music id 0x3A (cmd 1, params 0x1B 0x8F) from vm_op |
| 23741 | 395.033 | VM 0x4FD+0AC9 | MAP_CHANGE transition 64 |
| 23742 | 395.049 | screen | fade_out brightness 15 -> 0, 57 frames |
| 23798 | 395.981 | slot3 | removed |
| 23798 | 395.981 | slot4 | removed |
| 23798 | 395.981 | slot5 | removed |
| 23798 | 395.981 | slot6 | removed |
| 23798 | 395.981 | camera | set by the map loader to (216, 968) |
| 23798 | 395.981 | engine | map 101 loaded |
| 23799 | 395.998 | screen | fade_in brightness 0 -> 15, 15 frames |
| 23802 | 396.048 | hero0_boy | facing down (0x01) |
| 23817 | 396.297 | VM 0x4FD+0ACB | ACTOR_WALK actor 1 right 63 frames |
| 23817 | 396.297 | hero0_boy (id 0x80) | walk (344, 1082) -> (470, 1082), 63 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 63x(+2,+0) [0x4FD+0ACB ACTOR_WALK actor 1 right 63 frames] |
| 23852 | 396.880 | camera | scroll (216, 968) -> (272, 968), 28 frames |
| 23882 | 397.379 | VM 0x4FD+0ACF | ACTOR_WALK actor 1 right 63 frames |
| 23882 | 397.379 | hero0_boy (id 0x80) | walk (470, 1082) -> (596, 1082), 63 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 63x(+2,+0) [0x4FD+0ACF ACTOR_WALK actor 1 right 63 frames] |
| 23882 | 397.379 | camera | scroll (272, 968) -> (398, 968), 63 frames |
| 23947 | 398.461 | VM 0x4FD+0AD3 | ACTOR_WALK actor 1 right 16 frames |
| 23947 | 398.461 | hero0_boy (id 0x80) | walk (596, 1082) -> (628, 1082), 16 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 16x(+2,+0) [0x4FD+0AD3 ACTOR_WALK actor 1 right 16 frames] |
| 23947 | 398.461 | camera | scroll (398, 968) -> (430, 968), 16 frames |
| 23967 | 398.793 | VM 0x4FD+0AD7 | ACTOR_WALK actor 1 up 63 frames |
| 23967 | 398.793 | hero0_boy (id 0x80) | walk (628, 1082) -> (628, 956), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+0AD7 ACTOR_WALK actor 1 up 63 frames] |
| 23988 | 399.143 | camera | scroll (430, 968) -> (430, 884), 42 frames |
| 24032 | 399.875 | VM 0x4FD+0ADB | ACTOR_WALK actor 1 left 0 frames |
| 24032 | 399.875 | hero0_boy | facing left (0x82) |
| 24037 | 399.958 | VM 0x4FD+0ADF | SCREEN arg 6 word 0x3FFF |
| 24037 | 399.958 | engine | palette_fade_mode_2A 96 (target word $010C = 0x3FFF) |
| 24042 | 400.041 | VM 0x4FD+0AE3 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 24282 | 404.035 | VM 0x4FD+0AE5 | FLAG_INC flag 0x68 |
| 24282 | 404.035 | VM 0x4FD+0AE7 | REFRESH_OBJECTS |
| 24282 | 404.035 | slot11 | facing up (0x00) |
| 24282 | 404.035 | slot11 | appears id 0xD8 at (500,948) |
| 24282 | 404.035 | slot11 | obj+0x0E = 0x00 |
| 24282 | 404.035 | flag | flag 0x68 1 -> 2 |
| 24287 | 404.118 | VM 0x4FD+0AE8 | SCREEN arg 7 |
| 24287 | 404.118 | engine | palette_fade_mode_2A 224 (target word $010C = 0x3FFF) |
| 24292 | 404.201 | VM 0x4FD+0AEA | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 24443 | 406.714 | engine | palette_fade_mode_2A 0 (target word $010C = 0x3FFF) |
| 24532 | 408.195 | VM 0x4FD+0AEC | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 24772 | 412.188 | VM 0x4FD+0AEE | SCREEN arg 6 word 0x3FFF |
| 24772 | 412.188 | engine | palette_fade_mode_2A 96 (target word $010C = 0x3FFF) |
| 24777 | 412.271 | VM 0x4FD+0AF2 | WAIT 48 ticks (= 240 frames, 3.993 s) |
| 25017 | 416.265 | VM 0x4FD+0AF4 | TOGGLE_HERO_VIS |
| 25017 | 416.265 | hero0_boy | obj+0x0E = 0x80 |
| 25017 | 416.265 | hero1_girl | obj+0x0E = 0x80 |
| 25017 | 416.265 | hero2_sprite | obj+0x0E = 0x80 |
| 25022 | 416.348 | VM 0x4FD+0AF5 | MAP_CHANGE transition 620 |
| 25023 | 416.364 | screen | fade_out brightness 15 -> 0, 57 frames |
| 25079 | 417.296 | slot3 | appears id 0x8C at (436,340) |
| 25079 | 417.296 | slot3 | obj+0x0E = 0x00 |
| 25079 | 417.296 | slot11 | removed |
| 25079 | 417.296 | camera | set by the map loader to (296, 456) |
| 25079 | 417.296 | engine | palette_fade_mode_2A 0 (target word $010C = 0x3FFF) |
| 25079 | 417.296 | engine | map 107 loaded |
| 25080 | 417.313 | screen | fade_in brightness 0 -> 15, 15 frames |
| 25083 | 417.363 | hero0_boy | facing down (0x01) |
| 25098 | 417.612 | VM 0x4FD+0AF7 | ACTOR_ANIM actor 4 anim 0xAF |
| 25098 | 417.612 | slot3 | facing down (0x01) |
| 25098 | 417.612 | slot3 | pose state 0x40 anim 0xAF |
| 25100 | 417.646 | slot3 | obj+0x0E = 0x40 |
| 25105 | 417.729 | slot3 | pose idle |
| 25108 | 417.779 | VM 0x4FD+0AFB | ACTOR_WALK actor 1 up 63 frames |
| 25108 | 417.779 | hero0_boy (id 0x80) | walk (424, 570) -> (424, 444), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+0AFB ACTOR_WALK actor 1 up 63 frames] |
| 25129 | 418.128 | camera | scroll (296, 456) -> (296, 372), 42 frames |
| 25173 | 418.860 | VM 0x4FD+0AFF | ACTOR_WALK actor 1 up 63 frames |
| 25173 | 418.860 | hero0_boy (id 0x80) | walk (424, 444) -> (424, 318), 63 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 63x(+0,-2) [0x4FD+0AFF ACTOR_WALK actor 1 up 63 frames] |
| 25173 | 418.860 | camera | scroll (296, 372) -> (296, 246), 63 frames |
| 25238 | 419.942 | VM 0x4FD+0B03 | WAIT 64 ticks (= 320 frames, 5.325 s) |
| 25558 | 425.266 | VM 0x4FD+0B05 | ACTOR_ANIM actor 4 anim 0x96 |
| 25558 | 425.266 | slot3 | pose state 0x40 anim 0x96 |
| 25645 | 426.714 | slot3 | removed |
| 25648 | 426.764 | VM 0x4FD+0B09 | SCREEN arg 6 word 0xFFFF |
| 25648 | 426.764 | engine | palette_fade_mode_2A 96 (target word $010C = 0xFFFF) |
| 25653 | 426.847 | VM 0x4FD+0B0D | WAIT 64 ticks (= 320 frames, 5.325 s) |
| 25973 | 432.172 | VM 0x4FD+0B0F | GOTO_EVENT event 0x047 |
| 25973 | 432.172 | VM 0x047+0000 | PARTY_CMD arg 0x11 |

## 8. Details

### 8.1 The arena after the Mana Beast (frames 783-1113)

- FREEZE at 783, GATHER at 788 (the heroes stand at (264, 411), (296, 411), (312, 411); the controlled hero is the boy at x = 296: the girl runs 11 frames (3 px per frame, 32 px) and the sprite 6 frames (16 px)), sound effect 0x8B twice at 798 (the party-gather effect), raw sound 0x80 / 0x80 at 803 (event 0x748), `SCREEN 6` word 0x3FFF at 808 (palette fade, `$2A` = 0x60: 32 values of `$010A` reached at frame 959, i.e. +1 on each of red, green and (up to 15) blue every 5 frames), then `WAIT 48` (240 frames).
- Frame 1053: `FLAG_SET 0x00 = 0` (flag 0 was 1; `$C1:E339`, called by `CALL_E326`, returns at once when it is 0 [C]). Frame 1058: actors 1 and 2 (slots 0 and 1: boy and girl) start the looping pose 0xAB (state 0x30).
- Frame 1063: canned event 0x41E: `SET_FIELD_BYTE` of `obj+0x190` and `obj+0x191` = 0 for slots 0-2 (clears the status/dead word), `HERO_REFILL` 0x04 (HP of all three = max), 0x84 (MP = max), 0x44 (statuses reset through `$C1:80BA`, argument 0xFF; not decoded), `CALL_E326` (object initialisation `$C1:E326`) [V executed; C for the field meanings].
- Frames 1098 / 1103: `ACTOR_DELETE` 1 and 2 set `obj+0` = 0x80 in slots 1 and 2; frame 1108: `ACTOR_CLONE` 1 makes slot 1 active again (`obj+0` = 1, facing down) at the position of the object `$3A` with `obj+0x0B`, `obj+0x4C` and `obj+0x8E` copied from the controlled hero [V: `obj+0` and facing; C for the copied fields].

### 8.2 The world-map interlude (frames 1113-1652)

- `MAP_CHANGE_D` with argument 0x7E (event 0xD3E): bit 6 of the argument sets bit 0 of `$E3`; the table entry `$C6:7C80 + 4 * 0x3E` gives the position words 0xF63B and 0x77BA (`$FA` = 472, `$FC` = 1968, `$0110` = 0x77BA); `JSL $C0:BC01` starts the fade-out (`JSR $8B09`; 29 frames here, one level per 2 frames) and sets `$FF` = 0x81 [V: values; C: routines].
- `$C0:B5C1`: with `$FF` bit 7 set the main loop waits for the fade (`$E2` bit 0 clear), puts 0x80 in `$FE` (bit 0 of `$FF` was set), clears `$FF`, writes `$F8` = 0x44 and jumps to **`$C0:8038`**, the start of the world-map mode: it re-initialises the screen for **BG mode 7** (`$2105` = 7) and falls into the loop `$C0:8064` (`$C0:8B5E`, `83A8`, `983A`, `908B`, `95A0`, `9AB8`, `$C1:FDE4`, `$C0:87E0`, `8272`, `8093`). The event VM is stepped only from `$C0:B09C` (the map-mode frame body), so **it does not run in this mode**: `$D0` stays 1 and `$D1` points at the command after `MAP_CHANGE_D` for the whole interlude [V].
- Observed (the loop is run by `tools/event_runs.py` with the VM suspended): the fade-in of 57 frames starts at frame 1142; `$F8` = 0xDF in the first frames and counts down (every 2 frames, with a longer step now and then) to 0x10 in frame 1649; the loop then jumps to the map loader (`$C0:B03F`) in frame 1652 with the map taken from the world position bytes `$FB`/`$FD` through the table `$C6:7780` (`$C0:81ED-8249`): **map 8** (256 x 224 px, start tile (8, 7), flag byte 0xE0), after which the VM resumes (first step in frame 1671: music 0x3A). Two sound effects 0x16 (parameter bytes 0x00 0xA4) are requested by the loop at frames 1388 and 1644 [V]. What the player sees in the mode-7 loop was not examined (the PPU is not emulated).
- The interlude lasts 511 frames (8.50 s); the whole stretch from the `MAP_CHANGE_D` command to the first VM step in map 8 is 558 frames (9.29 s).

### 8.3 The staff-roll scenes (frames 1916-25022)

- 16 maps (180, 148, 149, 150, 108, 147, 146, 106, 151, 105, 152, 153, 104, 103, 102, 101) plus the last map 107. In each, the two actors under script control (slot 0 = actor 1, slot 1 = actor 2) walk along paths given by `ACTOR_WALK` counts (up to 63 per command) and by the looping animation codes of section 8.5 while the camera follows (`$C0:D8F2` window rule, `docs/cutscene-engine.md` section 7) and one or two staff-roll text blocks are on screen; NPCs of each map stand or wander by their own AI.
- Every map change of the staff roll (transitions 1023, 1000, 1001, 1006, 623, 999, 998, 345, 1007, 68, 1008, 1009, 67, 66, 65, 64, 620) takes exactly 57 frames between the command and the load: the flag byte of all these table entries is 0xA0 (0xE0 for 1008), exit code 0, so the party does not walk out and the fade starts at once (`docs/cutscene-engine.md` section 13.2).
- Staff-roll text: 18 blocks, the first at frame 5892 (block 22, 16 bytes, 520 frames), the longest block 29 (274 bytes at frame 12173, 1,220 frames).
- Flag 0xF7 is the counter that goes with the staff-roll window: 0 -> 1, 2, 3, 4 (every 40 frames from frame 5642), 6, 8, then 11 (frame 6412, when block 22 ends), 15 (frame 7167); in the last map it is lowered 15 -> 12, 10, 8, 6, 4 (every 45 frames from frame 23326), then 3, 2, 1 and 0 with `WAIT` 9, 10, 11, 12 ticks (frames 23561-23726). Its effect on the screen is not decoded.
- Other flag writes: flag 0x01 0 -> 1 (frame 9549), flag 0x68 0 -> 1 (frame 20904) and 1 -> 2 (frame 24282, with `REFRESH_OBJECTS` that makes the object id 0xD8 appear at (500, 948) in map 101).
- Hero visibility: `TOGGLE_HERO_VIS` sets bit 7 of `obj+0x0E` of the three heroes (hidden) at frame 9544 (before the change to map 150), toggles them back at 11242 (map 147) and hides them at 25017 (before map 107, where the last scene has only the NPC id 0x8C at (436, 340) in animation 0xAF, then 0x96, and the screen fades out).

### 8.4 Palette fades [V]

`SCREEN 6` (4-byte form) with the target word `$010C`; `$2A` = 0x60 (palette entries 16-255 of the 256, one step every 5 frames in the frame with `$56` = 4: `$010A` is the running offset of the three 5-bit channels, +1 per step in add mode (bit 15 of the word clear) or -1 in subtract mode (set), until each channel reaches its field of the word). `SCREEN 7` sets bit 7 of `$2A`: the offsets run back to 0 and `$2A` clears.

| frame | word | direction | steps | note |
|---|---|---|---|---|
| 808 | 0x3FFF | add | 32 values, last at 959 | arena; cut by the map change at 1113 |
| 9399 | 0xFFFF | subtract | 32 values, last at 9550 | before the change to map 150 |
| 24037 | 0x3FFF | add | 32 values, last at 24188 | map 101 |
| 24287 | `SCREEN 7` | back to 0 | 32 values (0x3FFF to 0), 5 frames each, `$2A` cleared at 24443 | map 101 |
| 24772 | 0x3FFF | add | 32 values, last at 24923 | map 101, before the change to map 107 |
| 25648 | 0xFFFF | subtract | 32 values, last at 25799 | map 107, the final fade; the script waits 320 more frames |

### 8.5 Animation codes observed [V]

| code | used by | effect |
|---|---|---|
| 0xA8 | hero slots (canned events 0x056, 0x058, 0x059, 0x05A), `ACTOR_ANIM` | pose of 20 frames in state 0x40, then idle |
| 0xA9 | girl (slot 1) | 40 frames in state 0x40 |
| 0xB2 | boy and girl | 20 frames in state 0x40 |
| 0xAF | NPC id 0x8C | 7 frames in state 0x40 |
| 0x96 | NPC id 0x8C | state 0x40, 87 frames until the object is removed |
| 0xAB | boy and girl, `ACTOR_ANIM_LOOP` | looping pose, no movement |
| 0x89 / 0x8A / 0x8B | boy and girl, `ACTOR_ANIM_LOOP` | the object walks in its facing direction at **2 / 3 / 1 px per frame** (animation codes 137 / 138 / 139), until another command changes it; 0x8A makes the engine request sound effect 0x8B every 20 frames |
| 0x81 | NPC kinds 0xA4, 0xA5 | walks at 1 px per frame |

### 8.6 What else changes during the ending

- Jitter `$49`: 0xE0 from frame 5 to frame 265 only. No flash (`$E2` bit 2), mosaic or colour effect occurs in the ending.
- `$CF4E` becomes 9 at frame 783 and stays; event flags written: 0x4E, 0xFF (783), 0x00 (1053), 0xF7 (many), 0x01, 0x68 (above), plus the party reset of event 0x41E.
- Music: **0x3A at frame 1671** (map 8), raw command 0x80 with parameter 0x20 at 9404 (event 0x73E; a stop or fade, not decoded) and **0x32 at 9539** (event 0x732), raw 0x80 with parameter 0x80 at 23281 (event 0x748) and **0x3A again at 23736** (event 0x73A, the same canned event as at 1671). The raw 0x80 / 0x80 at frame 803 (event 0x748) is the request that comes first after the Mana Beast's own raw 0x80 / 0xF0 (frame 5). These are all the music and raw requests of the ending (the sound-effect requests are 0x15 x 9, 0x8B x 19 and 0x16 x 2) [V].

## 9. Dependencies on the party [V]

| what | result |
|---|---|
| controlled hero | boy: 25,973 frames; girl or sprite: **25,978** (+5). Identical commands and movements; the GATHER at frame 788 takes 5 frames longer: the heroes stand at x = 264, 296, 312 (girl, boy, sprite); with the boy as the controlled hero the farthest hero is 32 px away (11 frames at 3 px per frame), with the girl or the sprite it is 48 px away (16 frames). Every later time shifts by +5 |
| positions at the start of the event | the heroes stand where the player left them: GATHER runs the two non-controlled heroes to the controlled one at 3 px per frame (animation code 2, sound effect 0x8B twice), so its length is `max distance / 3` frames; the rest of the ending does not depend on positions (every later scene starts at a map load, which places the party) |
| HP, MP, statuses | reset by event 0x41E (frame 1063): everything refilled and cleared |
| equipment, levels | not read |
| the time of the death | the length of the fight before the dead bit is seen; the earliest is frame -5 relative to the 37.5 s after control returned, see section 1 |
| player input | the pad is locked from frame 780 (pad byte bit 7) to the restart; text blocks wait for A, X, L, R, B or Y (the harness presses in the first frame: every dialog time is a minimum); staff-roll blocks (`0x7D`) are timed by the engine, they are not followed by a button wait in the script |
| flags | the script writes flags and reads none (no conditional command) |

## 10. How the game ends: PARTY_CMD 0x11 [C; V up to the jump]

- Frame 25973 (`GOTO 0x047`; event 0x047 is `PARTY_CMD` 0x11, `END`): the handler `$C1:EB63` takes the "other" branch for arguments above 0x10 and executes `JML $C0:0075` -> `JMP $C0:009B` -> `JML $C1:0018` -> `JML $C1:4CFA`. That routine sets the stack to 0x01FF, disables the NMI and interrupts (`$4200` = 0), sets forced blank (`$2100` = 0x80), loads the video/DMA registers (`$4201` = 0xFF, the registers `$4200-$420D` cleared by `$C1:4D0F`) and calls `$C1:4C30` with the source `$C7:7C00` and the destination `$7E:8000` (a copy or a decompression of a program into work RAM; its length and format were not read), then jumps to **`$7E:AF28`** inside that area.
- The reset vector (`$00:FFFC` = `$8004`) runs `JML $C1:0010` -> `JML $C1:4CE5`, which is the same sequence ending with `JML $7E:AF0B`. `PARTY_CMD` 0x11 is therefore a **software restart through the reset path** with the entry point 29 bytes after the cold-start one; whatever lies at `$7E:AF28` (the program that shows the title screen, or a variant of it) was not executed (the harness stops at `$C1:4CFA`). No save, no flag write and no map load follows the command: the game does **not** return to a map or to the player; control goes to the start-up program [C].
- `$F1`, the pad lock and `$D0` are not cleared by this path (no END runs): the ending never "hands control back" to the field.

## 11. Method

`python3 tools/event_runs.py ROM STATE ending OUT.json [leader=N] [dead=F] [frames=N] [snap=FILE] [resume=FILE] [raw=FILE]`: runs the intro (`docs/cutscene-mana-beast-intro.md` section 10), refills the heroes' HP every frame, waits `dead` frames (10), sets bit 7 of `obj+0x191` of the Mana Beast (the dead bit `$190` = 0x8000) and keeps stepping the real frame; the report starts at the frame in which `$94` becomes 0x12. The loop stops when the VM is idle, when the restart routine `$C1:4CFA` is reached (hooked: it re-initialises the machine), or after `frames` frames. `MAP_CHANGE_D` switches the harness into the world-map loop (`$C0:8038`, hooked at `$C0:8064` after its initialisation: the vblank flag `$4210` toggles on every read so that the loop's wait loops end), and `$C0:B03F` switches it back. `snap=` stores a state at that frame and `resume=` restarts from it (the three leader runs of this document took 8 minutes each).

## 12. Open questions (no values)

- What the mode-7 loop shows during the 511 frames, and why the loop ends when `$F8` reaches 0x10; the meaning of the position words of event 0xD3E; the content of map 8.
- What the staff-roll text engine does on screen (scroll speed, window), the meaning of flag 0xF7, and of the control codes of the one-byte blocks.
- The identities of music 0x3A and 0x32, of the raw commands 0x80 with parameters 0x20, 0x80 and 0xF0 (the table-driven handlers of the sound driver, `docs/audio.md`), of sound effects 0x15, 0x16 and 0xD6.
- The effect of `ACTOR_CLONE` on the appearance of slot 1 (which fields `obj+0x0B`, `+0x4C`, `+0x8E` are), and of `HERO_REFILL` 0x44 (`$C1:80BA`).
- What `$7E:AF28` is (title screen, credits end screen or a variant): the data at `$C7:7C00` that `$C1:4C30` puts at `$7E:8000` was not read.
- Which NPC kind each object id is (names are not recorded); the random wandering of the NPCs is not reproduced (it uses the game's RNG).
- The explosions' look, the effect of `$49` on screen (axis, amplitude), and the sound-effect volume/pan bytes.
- Real-hardware timing under slowdown.

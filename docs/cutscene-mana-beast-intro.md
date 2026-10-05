# The Mana Beast intro cutscene (maps 255 and 253)

Tags: **[V]** measured by running the original 65816 code frame by frame with `tools/event_runs.py` on top of `tools/event_vm.py` (the harness and its limits are in `docs/cutscene-engine.md` section 10; the real frame body `$C0:B08C`, the map loader, the event VM `$C1:E8D3`, the text engine and the boss engine run, the PPU, VRAM/CGRAM/OAM DMA and the sound CPU do not); **[C]** read from the disassembly, not executed. Numbers: `data/cutscene_mana_beast_intro.json` (written by `tools/event_runs.py ROM STATE intro OUT.json leader=0 after=900`). Everything that is not known is in section 11 without values. The VM, the opcodes and the state bytes are in `docs/cutscene-engine.md`; the fight itself is in `docs/mana-beast.md`; this document is the timeline of what happens from the start of the entry event until control returns with the fight running.

Time: **frames** of 1/60.0988 s counted from frame 0 = the frame in which the entry event 0x429 was started from the idle state of a save state taken in map 246 (the party stands in the Dark Lich room after its post-fight event, flag 0x4E = 8). The VM steps every fifth frame (12.02 Hz), so its commands run at frames = 3 mod 5 in the starting map, = 4 mod 5 in map 255 (loaded in frame 60) and = 3 mod 5 in map 253 (loaded in frame 2464); the 5-frame cycle restarts at every map load. Seconds are frames / 60.0988. Everything that depends on the player (button presses) assumes the press happens in the first frame the VM waits for one, so every dialog time here is the minimum.

## 1. Summary

| frame | s | what |
|---|---|---|
| 0 | 0.00 | state: map 246 (576 x 640 px), party near (261, 435), flag 0x4E = 8, screen-jitter byte `$49` = 0xE0 already on in the state (event 0x42D contains `SCREEN 2` commands [C]); event 0x429 started |
| 3 | 0.05 | first VM step: `IF_FLAG_RANGE` flag 0x4E in 0..7 (false), `MAP_CHANGE` transition 59 |
| 4-60 | 0.07-1.00 | fade-out, brightness 15 -> 0 in 57 frames |
| 60 | 1.00 | **map 255 loaded** (1536 x 1024 px, start tile (21, 13) = all three heroes at (344, 218)), camera (216, 104); the loader clears `$49` |
| 61-75 | 1.02-1.25 | fade-in |
| 79-114 | 1.31-1.90 | formation event 0x47C: FREEZE, GATHER (nothing to gather, the heroes share one pixel), camera re-centre (216, 104) -> (216, 90) in 7 frames, girl 16 px left to (328, 218), sprite 16 px right to (360, 218), all face down |
| 114 | 1.90 | music 0x37 |
| 119-195 | 1.98-3.24 | palette fade `SCREEN 6` with word 0x0010: red channel +1 every 5 frames up to +16 (17 values), stays until the map change |
| 124 | 2.06 | `SCREEN 2`: screen jitter `$49` = 0xE0 (40 frames), at 164 `SCREEN 3`: `$49` = 0x60, stays until the map load at 2464 |
| 244-1050 | 4.06-17.5 | dialog blocks #1-#13: girl and sprite walk 16 px up to y = 186 (frame 489), all turn down (549), boy turns up (609), girl and sprite turn (954, 979); boy walks 8 px up to (344, 202) at frame 1049 |
| 1064-2339 | 17.7-38.9 | dialog blocks #14-#28 with timed pauses; the sprite (frame 1969) and the girl (frame 2254) play animation 0xA8 (20 frames) |
| 2339 | 38.92 | `SCREEN 6` with word 0xFFFF: palette fade to black (subtract mode) |
| 2344 | 39.00 | music 0x39 |
| 2349 | 39.09 | `MAP_CHANGE` transition 188 (exit code 1 of the table entry: the party walks up while the screen waits) |
| 2408-2464 | 40.07-41.00 | fade-out (57 frames) |
| 2464 | 41.00 | **map 253 loaded** (576 x 576 px): heroes at (296, 472), the Mana Beast (object id 0x7F) is spawned from the map record with engine position (288, 288), phase 0 -> 8 at the next frame |
| 2465-2479 | 41.02-41.28 | fade-in |
| 2464-2500 | 41.00-41.60 | entry walk: all three heroes walk up 72 px (36 frames, 2 px per frame) to (296, 400) |
| 2503 | 41.65 | VM resumes: `FLAG_INC 0xFF` (boss freeze: the Mana Beast stops ticking), `FLAG_SET 0x0B = 15` |
| 2508-2518 | 41.73-41.90 | girl 16 px left to (280, 400), sprite 16 px right to (312, 400), all face up |
| 2523-3083 | 41.98-51.30 | 4 dialog blocks, each followed by a 160-frame pause (3 pauses) |
| 3088 | 51.38 | `FLAG_DEC 0xFF` (the Mana Beast resumes), **END: control returns**; `$F1` and the pad lock are cleared |
| 3345 | 55.66 | the Mana Beast leaves phase 8 for phase 1 (sound request 0xD6): its first move |

Total **3,088 frames = 51.38 s** for the reference run (controlled hero = boy); 3,080 frames for the girl or the sprite (section 8).

Maps and transitions in this scene:

| map | via | load frame | load s | map px | start tile | frame of the next map change | frames in the map | dialog blocks (bytes) | music/raw sound | objects other than heroes at entry (ids) |
|---|---|---|---|---|---|---|---|---|---|---|
| 246 | (initial state) | 0 | 0.00 | 576x640 | - | 3 | 3 | 0 (0) | - | - |
| 255 | MAP_CHANGE transition 59 | 60 | 1.00 | 1536x1024 | (21, 13) | 2349 | 2289 | 28 (866) | music 0x37@114, music 0x39@2344 | - |
| 253 | MAP_CHANGE transition 188 | 2464 | 41.00 | 576x576 | (18, 22) | 3088 | 624 | 4 (73) | - | 3:0x7F, 6:0x00 |

## 2. How the scene starts [V unless noted]

- The scene is **event 0x429**. Its first command is `IF_FLAG_RANGE flag 0x4E, 0..7`, which jumps to the empty event 0 (a lone END) when the story counter `$CF4E` is below 8; the scene therefore plays only with **flag 0x4E >= 8**. The counter reaches 8 at the end of the post-fight event of the Dark Lich (event 0x42D: `FLAG_INC 0x4E` twice, 6 -> 7 -> 8, `docs/cutscene-dark-lich.md` section 2) [C: decoded; V: the save state taken after that event has `$CF4E` = 8].
- Event 0x429 is **entry 1 of the event list of maps 245 and 246** (`[0x428, 0x429]`), i.e. a trigger tile of the Dark Lich rooms (`docs/cutscene-engine.md` section 4); which tile was not traced. The ROM state used here is such a state: map 246, flag 0x4E = 8, VM idle, party at (261, 437), (261, 469), (261, 435).
- Event 0x426 (`IF_FLAG_RANGE 0x4E in 8..15 -> GOTO 0x429`, else `MAP_CHANGE` transition 59) is a second way into map 255 (with flag 0x4E below 8 it is just the plain entry, without the scene); no map record or script refers to it, and the only event-list region that contains the value 0x426 is the last list region of the first table (words 68 and 69 after the list pointer of map 298, whose extent is unknown) [C: scanned all lists, records and scripts].
- Transition 59 = map 255, start tile (21, 13), flag byte 0xA0; transition 188 = map 253, start tile (18, 22), flag byte 0x81 (entries of `$C8:3000 + 4 * n`; byte 3 is the exit/entry code, section 7).
- The Mana Beast is **not** placed by the intro script: it is the only object record of map 253 (id 0x7F, flag 0x4E range 8..8, tile (18, 18), event word 0x442F) and is spawned by the boss spawner `$C2:0040` when the loader runs, because flag 0x4E is 8. The same record carries the post-fight event: **0x42F**, not 0x42D (`docs/mana-beast.md` section 8 corrected). Map 253 has header byte `$B8` = 0xF8, so it has no entry event; event 0x429 simply goes on running in the new map once the loader is done.
- Start-up effects of the VM start (`$C1:E88D`): pad bytes locked (`pad_locked` in frame 1), and from frame 79 the formation event 0x47C sets `$F1` bit 7 (FREEZE).

## 3. Coordinates and actors at entry [V]

- Map pixels as in `docs/cutscene-dark-lich.md` section 3: origin at the top-left corner, x to the right, y down, position = object words `obj+2` / `obj+4`, camera `$A8/$AA` = map pixel at the top-left of the 256 x 224 screen. Facing: 0 up, 1 down, 2 right, 0x82 left.
- Map sizes (`$C0/$C2`): map 246 576 x 640, **map 255 1536 x 1024**, **map 253 576 x 576**.
- The hero start formula `(16 * tileX + 8, 16 * tileY + 10)` holds for transition 59: tile (21, 13) -> **(344, 218)**. For transition 188 the heroes are placed at **(296, 472)** (x = 16 * 18 + 8; y is 110 px below the formula's 362) and walk in (section 5.3).
- The Mana Beast record is at tile (18, 18): spawn position `(16 * tileX, 16 * tileY)` = **(288, 288)**; this is its engine position (`obj+0x2B/+0x32`) during phase 8. (`docs/mana-beast.md` quotes (0x120, 0x150) for phase 8; that was the position of the Dark Lich record of map 246, where the harness of that document spawned the boss; the positions that the phase code writes itself, e.g. (0x108, 0x160) at the end of phase 8, are unchanged.)
- Camera at entry: map 255 (216, 104); map 253 (168, 248), which puts a hero at y = 400 at screen y = 152.

| frame | map | object | slot | id | x | y | facing |
|---|---|---|---|---|---|---|---|
| 0 | 246 | hero | 0 (boy) | 0x80 | 261 | 437 | left |
| 0 | 246 | hero | 1 (girl) | 0x81 | 261 | 469 | up |
| 0 | 246 | hero | 2 (sprite) | 0x82 | 261 | 435 | down |
| 60 | 255 | hero | 0 (boy) | 0x80 | 344 | 218 | down |
| 60 | 255 | hero | 1 (girl) | 0x81 | 344 | 218 | down |
| 60 | 255 | hero | 2 (sprite) | 0x82 | 344 | 218 | down |
| 2464 | 253 | hero | 0 (boy) | 0x80 | 296 | 472 | up |
| 2464 | 253 | hero | 1 (girl) | 0x81 | 296 | 472 | up |
| 2464 | 253 | hero | 2 (sprite) | 0x82 | 296 | 472 | up |
| 2464 | 253 | object | 3 | 0x7F | 0 | 0 | down (engine position 288,288, phase 0x00) |
| 2464 | 253 | object | 6 | 0x00 | 0 | 0 | up |

Object slots 3 and 6 of map 253: slot 3 is the Mana Beast (object id 0x7F, flags 0x180D); slot 6 (id 0x00, appears in frame 2466) and slot 7 (id 0x00, appears in frame 2546) are the two helper objects that phase 0 of the Mana Beast creates (`docs/mana-beast.md` section 9, there numbered 3 and 4): slot 7 is re-created at (104, 0) several times during the dialog (frames 2546, 2738, 2922; removed at 2733, 2917, 3084); its role is not known. None of them is hit or hits.

## 4. Timeline

Reference run: controlled hero = slot 0 (boy), hero weapon types 4 / 1 / 3 (the save state's). `VM event+offset` rows are the commands as executed (several commands can run in one frame; `WAIT_IDLE` and `RETURN` rows are left out); rows with an object name are what the real code did to that object, "caused by" in square brackets ties a movement to its command; `engine` rows are state changes of the game engine; `dialog` rows collapse consecutive text blocks (section 6 lists every block). Per-frame movement is written as `N x (dx, dy)`.

| frame | s | object | what |
|---|---|---|---|
| 0 | 0.000 | engine | map 246 loaded |
| 1 | 0.017 | engine | pad_locked |
| 3 | 0.050 | VM 0x429+0000 | IF_FLAG_RANGE flag 0x4E in 0..7 |
| 3 | 0.050 | VM 0x429+0005 | MAP_CHANGE transition 59 |
| 4 | 0.067 | screen | fade_out brightness 15 -> 0, 57 frames |
| 60 | 0.998 | camera | set by the map loader to (216, 104) |
| 60 | 0.998 | engine | jitter_byte_49 0 |
| 60 | 0.998 | engine | map 255 loaded |
| 61 | 1.015 | screen | fade_in brightness 0 -> 15, 15 frames |
| 64 | 1.065 | hero0_boy | facing down (0x01) |
| 64 | 1.065 | hero1_girl | facing down (0x01) |
| 79 | 1.315 | VM 0x429+0007 | CALL_EVENT event 0x47C |
| 79 | 1.315 | VM 0x47C+0000 | FREEZE |
| 79 | 1.315 | engine | world_freeze_on |
| 84 | 1.398 | VM 0x47C+0001 | GATHER |
| 89 | 1.481 | VM 0x47C+0002 | SCREEN arg 8 |
| 89 | 1.481 | camera | scroll (216, 104) -> (216, 90), 7 frames |
| 89 | 1.481 | engine | camera_recentre_start |
| 96 | 1.597 | engine | camera_recentre_done |
| 99 | 1.647 | VM 0x47C+0004 | ACTOR_WALK actor 1 down 0 frames |
| 99 | 1.647 | VM 0x47C+0007 | ACTOR_WALK actor 2 left 8 frames |
| 99 | 1.647 | VM 0x47C+000A | ACTOR_WALK actor 3 right 8 frames |
| 99 | 1.647 | hero1_girl (id 0x81) | walk (344, 218) -> (328, 218), 8 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 8x(-2,+0) [0x47C+0007 ACTOR_WALK actor 2 left 8 frames] |
| 99 | 1.647 | hero2_sprite (id 0x82) | walk (344, 218) -> (360, 218), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x47C+000A ACTOR_WALK actor 3 right 8 frames] |
| 109 | 1.814 | VM 0x47C+000E | ACTOR_WALK actor 1 down 0 frames |
| 109 | 1.814 | VM 0x47C+0011 | ACTOR_WALK actor 2 down 0 frames |
| 109 | 1.814 | VM 0x47C+0014 | ACTOR_WALK actor 3 down 0 frames |
| 109 | 1.814 | hero1_girl | facing down (0x01) |
| 109 | 1.814 | hero2_sprite | facing down (0x01) |
| 114 | 1.897 | VM 0x429+0009 | CALL_EVENT event 0x737 |
| 114 | 1.897 | VM 0x737+0000 | SOUND cmd 1 id 0x37 word 0x8F12 |
| 114 | 1.897 | sound | music id 0x37 (cmd 1, params 0x12 0x8F) from vm_op |
| 119 | 1.980 | VM 0x429+000B | SCREEN arg 6 word 0x0010 |
| 119 | 1.980 | engine | palette_fade_mode_2A 96 (target word $010C = 0x0010) |
| 124 | 2.063 | VM 0x429+000F | SCREEN arg 2 |
| 124 | 2.063 | VM 0x429+0011 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 124 | 2.063 | engine | jitter_byte_49 224 |
| 164 | 2.729 | VM 0x429+0013 | SCREEN arg 3 |
| 164 | 2.729 | VM 0x429+0015 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 164 | 2.729 | engine | jitter_byte_49 96 |
| 244 | 4.060 | dialog | 4 text blocks (#1-#4, CA:0FE0 ...), each followed by a wait for a button where the script has one; next command at frame 489 |
| 489 | 8.137 | VM 0x429+00AB | ACTOR_WALK actor 2 up 16 frames |
| 489 | 8.137 | VM 0x429+00AE | ACTOR_WALK actor 3 up 16 frames |
| 489 | 8.137 | hero1_girl (id 0x81) | walk (328, 218) -> (328, 186), 16 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 16x(+0,-2) [0x429+00AB ACTOR_WALK actor 2 up 16 frames] |
| 489 | 8.137 | hero2_sprite (id 0x82) | walk (360, 218) -> (360, 186), 16 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 16x(+0,-2) [0x429+00AE ACTOR_WALK actor 3 up 16 frames] |
| 509 | 8.469 | VM 0x429+00B2 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 549 | 9.135 | VM 0x429+00B4 | CALL_EVENT event 0x053 |
| 549 | 9.135 | VM 0x053+0000 | ACTOR_WALK actor 1 down 0 frames |
| 549 | 9.135 | VM 0x053+0003 | ACTOR_WALK actor 2 down 0 frames |
| 549 | 9.135 | VM 0x053+0006 | ACTOR_WALK actor 3 down 0 frames |
| 549 | 9.135 | hero1_girl | facing down (0x01) |
| 549 | 9.135 | hero2_sprite | facing down (0x01) |
| 554 | 9.218 | dialog | 2 text blocks (#5-#6, CA:107F ...), each followed by a wait for a button where the script has one; next command at frame 609 |
| 609 | 10.133 | VM 0x429+00CC | ACTOR_WALK actor 1 up 0 frames |
| 609 | 10.133 | hero0_boy | facing up (0x00) |
| 614 | 10.217 | dialog | 3 text blocks (#7-#9, CA:1099 ...), each followed by a wait for a button where the script has one; next command at frame 779 |
| 779 | 12.962 | VM 0x429+013A | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 859 | 14.293 | dialog | 2 text blocks (#10-#11, CA:1105 ...), each followed by a wait for a button where the script has one; next command at frame 954 |
| 954 | 15.874 | VM 0x429+017B | ACTOR_WALK actor 2 right 0 frames |
| 954 | 15.874 | dialog | 1 text block (#12-#12, CA:1147 ...), each followed by a wait for a button where the script has one; next command at frame 979 |
| 954 | 15.874 | hero1_girl | facing right (0x02) |
| 979 | 16.290 | VM 0x429+0187 | ACTOR_WALK actor 3 up 0 frames |
| 979 | 16.290 | VM 0x429+018A | WAIT for a button (state 0x83) |
| 979 | 16.290 | hero2_sprite | facing up (0x00) |
| 984 | 16.373 | dialog | 1 text block (#13-#13, CA:1155 ...), each followed by a wait for a button where the script has one; next command at frame 1049 |
| 1049 | 17.455 | VM 0x429+01B8 | ACTOR_WALK actor 1 up 8 frames |
| 1049 | 17.455 | hero0_boy (id 0x80) | walk (344, 218) -> (344, 202), 8 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 8x(+0,-2) [0x429+01B8 ACTOR_WALK actor 1 up 8 frames] |
| 1059 | 17.621 | VM 0x429+01BC | WAIT for a button (state 0x83) |
| 1064 | 17.704 | dialog | 1 text block (#14-#14, CA:1187 ...), each followed by a wait for a button where the script has one; next command at frame 1089 |
| 1089 | 18.120 | VM 0x429+01C5 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 1249 | 20.782 | dialog | 1 text block (#15-#15, CA:1190 ...), each followed by a wait for a button where the script has one; next command at frame 1264 |
| 1264 | 21.032 | VM 0x429+01CB | ACTOR_WALK actor 3 down 0 frames |
| 1264 | 21.032 | hero2_sprite | facing down (0x01) |
| 1269 | 21.115 | dialog | 5 text blocks (#16-#20, CA:1198 ...), each followed by a wait for a button where the script has one; next command at frame 1674 |
| 1674 | 27.854 | VM 0x429+02E8 | ACTOR_WALK actor 2 down 0 frames |
| 1674 | 27.854 | hero1_girl | facing down (0x01) |
| 1679 | 27.937 | dialog | 5 text blocks (#21-#25, CA:12B5 ...), each followed by a wait for a button where the script has one; next command at frame 1969 |
| 1969 | 32.763 | VM 0x429+03A6 | CALL_EVENT event 0x05A |
| 1969 | 32.763 | VM 0x05A+0000 | ACTOR_ANIM actor 3 anim 0xA8 |
| 1969 | 32.763 | hero2_sprite | pose state 0x40 anim 0xA8 |
| 1989 | 33.096 | hero2_sprite | pose idle |
| 1994 | 33.179 | VM 0x05A+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2034 | 33.844 | dialog | 1 text block (#26-#26, CA:1371 ...), each followed by a wait for a button where the script has one; next command at frame 2059 |
| 2059 | 34.260 | VM 0x429+03B6 | ACTOR_WALK actor 3 left 0 frames |
| 2059 | 34.260 | hero2_sprite | facing left (0x82) |
| 2064 | 34.343 | dialog | 1 text block (#27-#27, CA:1383 ...), each followed by a wait for a button where the script has one; next command at frame 2089 |
| 2089 | 34.759 | VM 0x429+03C5 | ACTOR_WALK actor 2 right 0 frames |
| 2089 | 34.759 | hero1_girl | facing right (0x02) |
| 2094 | 34.843 | VM 0x429+03C9 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 2254 | 37.505 | VM 0x429+03CB | CALL_EVENT event 0x059 |
| 2254 | 37.505 | VM 0x059+0000 | ACTOR_ANIM actor 2 anim 0xA8 |
| 2254 | 37.505 | hero1_girl | pose state 0x40 anim 0xA8 |
| 2274 | 37.838 | hero1_girl | pose idle |
| 2279 | 37.921 | VM 0x059+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2319 | 38.586 | VM 0x429+03CD | WAIT for a button (state 0x83) |
| 2324 | 38.670 | dialog | 1 text block (#28-#28, CA:1398 ...), each followed by a wait for a button where the script has one; next command at frame 2339 |
| 2339 | 38.919 | VM 0x429+03D0 | SCREEN arg 6 word 0xFFFF |
| 2344 | 39.002 | VM 0x429+03D4 | CALL_EVENT event 0x739 |
| 2344 | 39.002 | VM 0x739+0000 | SOUND cmd 1 id 0x39 word 0xFF14 |
| 2344 | 39.002 | sound | music id 0x39 (cmd 1, params 0x14 0xFF) from vm_op |
| 2349 | 39.086 | VM 0x429+03D6 | MAP_CHANGE transition 188 |
| 2350 | 39.102 | hero0_boy (id 0x80) | walk (344, 202) -> (344, 24), 89 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 89x(+0,-2) [engine: exit walk of the party during the map change started at frame 2349] |
| 2350 | 39.102 | hero1_girl (id 0x81) | walk (328, 186) -> (340, 196), 4 frames, 330.5 px/s, facing right, anim [2], per-frame 3x(+3,+3) 1x(+3,+1) [engine: exit walk of the party during the map change started at frame 2349] |
| 2350 | 39.102 | hero2_sprite (id 0x82) | walk (360, 186) -> (348, 196), 4 frames, 330.5 px/s, facing left, anim [2], per-frame 3x(-3,+3) 1x(-3,+1) [engine: exit walk of the party during the map change started at frame 2349] |
| 2354 | 39.169 | hero1_girl (id 0x81) | walk (340, 196) -> (344, 192), 2 frames, 240.4 px/s, facing right, anim [1, 2], per-frame 1x(+3,-2) 1x(+1,-2) [engine: exit walk of the party during the map change started at frame 2349] |
| 2354 | 39.169 | hero2_sprite (id 0x82) | walk (348, 196) -> (344, 192), 2 frames, 240.4 px/s, facing left, anim [1, 2], per-frame 1x(-3,-2) 1x(-1,-2) [engine: exit walk of the party during the map change started at frame 2349] |
| 2356 | 39.202 | hero1_girl (id 0x81) | walk (344, 192) -> (344, -24), 108 frames, 120.2 px/s, facing up, anim [1], per-frame 108x(+0,-2) [engine: exit walk of the party during the map change started at frame 2349] |
| 2356 | 39.202 | hero2_sprite (id 0x82) | walk (344, 192) -> (344, -24), 108 frames, 120.2 px/s, facing up, anim [1], per-frame 108x(+0,-2) [engine: exit walk of the party during the map change started at frame 2349] |
| 2408 | 40.067 | screen | fade_out brightness 15 -> 0, 57 frames |
| 2464 | 40.999 | slot3 | appears id 0x7F at (0,0) |
| 2464 | 40.999 | camera | set by the map loader to (168, 248) |
| 2464 | 40.999 | engine | jitter_byte_49 0 |
| 2464 | 40.999 | engine | palette_fade_mode_2A 0 (target word $010C = 0xFFFF) |
| 2464 | 40.999 | engine | map 253 loaded |
| 2465 | 41.016 | screen | fade_in brightness 0 -> 15, 15 frames |
| 2466 | 41.032 | slot6 | appears id 0x00 at (0,0) |
| 2467 | 41.049 | hero0_boy (id 0x80) | walk (296, 468) -> (296, 400), 34 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 34x(+0,-2) [engine: entry walk after the map load] |
| 2467 | 41.049 | hero1_girl (id 0x81) | walk (296, 468) -> (296, 400), 34 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 34x(+0,-2) [engine: entry walk after the map load] |
| 2467 | 41.049 | hero2_sprite (id 0x82) | walk (296, 468) -> (296, 400), 34 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 34x(+0,-2) [engine: entry walk after the map load] |
| 2503 | 41.648 | VM 0x429+03D8 | FLAG_INC flag 0xFF |
| 2503 | 41.648 | VM 0x429+03DA | FLAG_SET flag 0x0B = 15 |
| 2503 | 41.648 | engine | boss_freeze_flag_set |
| 2503 | 41.648 | flag | flag 0x0B 2 -> 15 |
| 2503 | 41.648 | flag | flag 0xFF 0 -> 1 |
| 2508 | 41.731 | VM 0x429+03DD | ACTOR_WALK actor 1 up 0 frames |
| 2508 | 41.731 | VM 0x429+03E0 | ACTOR_WALK actor 2 left 8 frames |
| 2508 | 41.731 | VM 0x429+03E3 | ACTOR_WALK actor 3 right 8 frames |
| 2508 | 41.731 | hero1_girl (id 0x81) | walk (296, 400) -> (280, 400), 8 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 8x(-2,+0) [0x429+03E0 ACTOR_WALK actor 2 left 8 frames] |
| 2508 | 41.731 | hero2_sprite (id 0x82) | walk (296, 400) -> (312, 400), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x429+03E3 ACTOR_WALK actor 3 right 8 frames] |
| 2518 | 41.898 | VM 0x429+03E7 | ACTOR_WALK actor 1 up 0 frames |
| 2518 | 41.898 | VM 0x429+03EA | ACTOR_WALK actor 2 up 0 frames |
| 2518 | 41.898 | VM 0x429+03ED | ACTOR_WALK actor 3 up 0 frames |
| 2518 | 41.898 | hero1_girl | facing up (0x00) |
| 2518 | 41.898 | hero2_sprite | facing up (0x00) |
| 2523 | 41.981 | dialog | 1 text block (#29-#29, CA:13BA ...), each followed by a wait for a button where the script has one; next command at frame 2548 |
| 2546 | 42.364 | slot7 | appears id 0x00 at (0,0) |
| 2548 | 42.397 | VM 0x429+0404 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 2708 | 45.059 | dialog | 1 text block (#30-#30, CA:13CF ...), each followed by a wait for a button where the script has one; next command at frame 2743 |
| 2733 | 45.475 | slot7 | removed |
| 2738 | 45.558 | slot7 | facing up (0x00) |
| 2738 | 45.558 | slot7 | appears id 0x00 at (104,0) |
| 2738 | 45.558 | slot7 | obj+0x0E = 0x00 |
| 2743 | 45.642 | VM 0x429+0423 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 2903 | 48.304 | dialog | 1 text block (#31-#31, CA:13EE ...), each followed by a wait for a button where the script has one; next command at frame 2923 |
| 2917 | 48.537 | slot7 | removed |
| 2922 | 48.620 | slot7 | facing up (0x00) |
| 2922 | 48.620 | slot7 | appears id 0x00 at (104,0) |
| 2922 | 48.620 | slot7 | obj+0x0E = 0x00 |
| 2923 | 48.637 | VM 0x429+043D | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 3083 | 51.299 | dialog | 1 text block (#32-#32, CA:1408 ...), each followed by a wait for a button where the script has one; next command at frame 3088 |
| 3084 | 51.316 | slot7 | removed |
| 3088 | 51.382 | VM 0x429+0440 | FLAG_DEC flag 0xFF |
| 3088 | 51.382 | VM 0x429+0442 | END |
| 3088 | 51.382 | engine | world_freeze_off |
| 3088 | 51.382 | engine | pad_released |
| 3088 | 51.382 | engine | boss_freeze_flag_cleared |
| 3088 | 51.382 | flag | flag 0xFF 1 -> 0 |

## 5. Details

### 5.1 Map 255 (frames 60-2349)

- All three heroes stand on the start tile (344, 218). Event 0x47C (called at frame 79) FREEZEs the party, GATHERs it (a no-op here), re-centres the camera on the controlled hero (`SCREEN 8`, 7 frames) and spreads the party: actor 2 (girl) 8 counts left, actor 3 (sprite) 8 counts right (16 px each), then all three turn down.
- Music 0x37 is requested in frame 114 (canned event 0x737). The rumble: `SCREEN 2` in frame 124 sets `$49` = 0xE0, `SCREEN 3` in frame 164 sets `$49` = 0x60 (a value with bit 7 clear, bit 6 and 5 set); nothing ever sends `SCREEN 4` (`$49` = 0), so the byte stays until the next map load clears it (frame 2464). `$49` makes the frame body write 0 or 6 into `$5E` (0x60) or `$5F` (0xE0) on alternate frames (`$C0:B51C-B563`) [C; V: the byte values]; which register the jitter ends up in was not traced.
- The tint: `SCREEN 6` (4-byte form) with word 0x0010 in frame 119: `$010C` = 0x0010, `$010A` = 0, `$2A` = 0x60; every fifth frame (the frame with `$56` = 4) `$C2:C820` adds 1 to each colour channel of the palette entries 16-255 (`$0600` -> `$BE00`; the first 16 entries are copied unchanged) whose target (`$010C`: red bits 0-4, green 5-9, blue 10-14) it has not reached; red reaches 16 after 16 steps, so `$010A` takes the 17 values 0..16, the last at frame 195 [V; C for the routine]. The dark fade at frame 2339 (word 0xFFFF: bit 15 set = subtract, all three channels 31) starts the same way and is cut by the map load at 2464 after 26 steps; `$2A` is cleared by the loader.
- Dialog: 28 text blocks (866 bytes) from event 0x429 (section 6), interleaved with: sprite and girl 16 px up (frame 489); all three turn down (event 0x053, frame 549); boy turns up (609); girl turns right (954), sprite up (979); boy 8 px up to (344, 202) (1049); sprite down (1264); girl down (1674); **animation 0xA8 of the sprite (frame 1969, canned event 0x05A) and of the girl (frame 2254, 0x059)**: 20 frames in state 0x40, then idle; the sprite turns left (2059), the girl right (2089).
- Positions of the heroes at frame 2339: boy (344, 202), girl (328, 186), sprite (360, 186). The ZSNES state `.zs2` of the save set was taken at frame 1982 of this scene (section 9).

### 5.2 The change of map (frames 2339-2464)

- Frame 2339: `SCREEN 6` word 0xFFFF; 2344 music 0x39 (canned event 0x739); 2349 `MAP_CHANGE` transition 188.
- The table entry's byte 3 (`$E0`) is 0x81: exit code 1. `$C0:B5E6-B5F2` finds `$E0` & 0x1F != 0x1F and branches to the exit walk (`$C0:B9C5-BAC2`): `$FF` becomes 0x60 (bit 5 = party walking), the **controlled hero walks up** (velocity byte 0x82 = -2 px per frame; its counter `obj+0x0A` = 31) and the other two heroes run to it (3 px per frame, animation 2, then follow at 2 px per frame): boy (344, 202) -> (344, 24) in 89 frames, girl and sprite (328, 186) / (360, 186) -> (344, 192) in 4 + 2 frames, then up for 96 frames [V]. When the exit walk is done `$E0` becomes 0x9F, the fade-out runs (brightness 15 -> 0, one level per 4 frames, frames 2408-2464, 57 frames) and the loader runs in the frame after it.
- So this transition takes 115 frames (1.91 s) between the command and the new map, against the 57-frame fade of transitions whose byte 3 is 0x80 or 0xA0 (exit code 0: the fade starts at once: transition 59 at frame 3-60, transitions 47 and 340 of `docs/cutscene-dark-lich.md`). The exit walk is shorter with the girl or the sprite as the controlled hero (section 8).

### 5.3 The arena, map 253 (frames 2464-3088)

- The loader places the three heroes at (296, 472) and sets `$FF` = 0x20 with `obj+0x0A` = 36 and velocity -2 px per frame: **entry walk**, 36 frames, to (296, 400) (frame 2500), facing up. The VM idles while `$FF` is non-zero, so its first step in the new map is frame 2503 (3 mod 5). Camera (168, 248) does not move.
- The Mana Beast spawns in frame 2464 (object id 0x7F, flags 0x180D, engine position (288, 288), phase 0) and enters phase 8 at frame 2465 (age counter 1). It ticks once every 5 frames from then.
- Frame 2503: `FLAG_INC 0xFF` sets the **boss freeze** (`$CFFF` bit 0): from the next tick the boss engine skips the Mana Beast (phase 8 had run 8 ticks, age 8 of 60); `FLAG_SET 0x0B = 15` (flag 0x0B was 2; no reader found).
- Frames 2508-2518: girl 8 counts left (-16 px) to (280, 400), sprite 8 counts right to (312, 400) (event 0x429+03E0/03E3), then all three face up.
- Dialog 29-32: 19, 29, 24 and 1 bytes at frames 2523, 2708, 2903, 3083, separated by three `WAIT 32` (160-frame) pauses. Block 32 is a one-byte control code.
- Frame 3088: `FLAG_DEC 0xFF`, `END`: `$F1` bit 7 and the bit 7 of the pad bytes `$D9-$DB` are cleared (`world_freeze_off`, `pad_released`), the Mana Beast resumes counting where it stopped.

### 5.4 Control returns and the fight starts

- At frame 3088 the heroes are at boy (296, 400), girl (280, 400), sprite (312, 400), facing up, the camera at (168, 248); the controlled hero is in animation 3 (standing ready), the others in 0.
- The Mana Beast (engine position (288, 288), phase 8, age 8): it still has 52 ticks of phase 8 to run (`docs/mana-beast.md` section 4: 59 ticks in all), so **phase 1 starts at frame 3345** (257 frames, 4.28 s after control returned) with the request of sound 0xD6, position (264, 352), and then follows the phase graph of that document. The earliest phase in which a hit can set the dead bit that the machine reads (0xB) is reached 2,252 frames (37.5 s) after control returned in the run of `docs/cutscene-ending.md` section 2.
- From frame 3358 the party AI moves the other heroes (not part of the scene); the first sound it causes is sound 0x8B at frame 3373.

## 6. Dialog blocks (address and length only)

32 text blocks, all from event 0x429 (bank `$CA`). "frames" is the time from the VM step that hands the block to the text engine until the next command executes (engine drawing time at the harness's text setting plus the VM's 5-frame granularity; a block that is followed by `WAIT 0` ends when the engine has drawn it; the button press itself adds 5 frames). The extent of each block equals the pointer the text engine left in `$1D01` in 32 of 32 blocks [V]. One-byte blocks (codes 0x51, 0x52, 0x7F) contain no character: they are engine control codes (window open/close or clear; not decoded).

| # | event+offset | address | bytes | start frame | start s | frames to next command | credits segment |
|---|---|---|---|---|---|---|---|
| 1 | 0x429+0017 | CA:0FE0 | 45 | 244 | 4.060 | 80 |  |
| 2 | 0x429+0046 | CA:100F | 46 | 329 | 5.474 | 65 |  |
| 3 | 0x429+0076 | CA:103F | 50 | 399 | 6.639 | 70 |  |
| 4 | 0x429+00AA | CA:1073 | 1 | 474 | 7.887 | 15 |  |
| 5 | 0x429+00B6 | CA:107F | 19 | 554 | 9.218 | 45 |  |
| 6 | 0x429+00CB | CA:1094 | 1 | 604 | 10.050 | 5 |  |
| 7 | 0x429+00D0 | CA:1099 | 54 | 614 | 10.217 | 75 |  |
| 8 | 0x429+0108 | CA:10D1 | 40 | 694 | 11.548 | 60 |  |
| 9 | 0x429+0132 | CA:10FB | 8 | 759 | 12.629 | 20 |  |
| 10 | 0x429+013C | CA:1105 | 60 | 859 | 14.293 | 85 |  |
| 11 | 0x429+017A | CA:1143 | 1 | 949 | 15.791 | 5 |  |
| 12 | 0x429+017E | CA:1147 | 9 | 954 | 15.874 | 25 |  |
| 13 | 0x429+018C | CA:1155 | 44 | 984 | 16.373 | 65 |  |
| 14 | 0x429+01BE | CA:1187 | 7 | 1064 | 17.704 | 25 |  |
| 15 | 0x429+01C7 | CA:1190 | 4 | 1249 | 20.782 | 15 |  |
| 16 | 0x429+01CF | CA:1198 | 47 | 1269 | 21.115 | 65 |  |
| 17 | 0x429+0200 | CA:11C9 | 78 | 1339 | 22.280 | 105 |  |
| 18 | 0x429+0250 | CA:1219 | 72 | 1449 | 24.110 | 105 |  |
| 19 | 0x429+029A | CA:1263 | 75 | 1559 | 25.941 | 105 |  |
| 20 | 0x429+02E7 | CA:12B0 | 1 | 1669 | 27.771 | 5 |  |
| 21 | 0x429+02EC | CA:12B5 | 74 | 1679 | 27.937 | 100 |  |
| 22 | 0x429+0338 | CA:1301 | 70 | 1784 | 29.684 | 100 |  |
| 23 | 0x429+0380 | CA:1349 | 16 | 1889 | 31.432 | 35 |  |
| 24 | 0x429+0392 | CA:135B | 17 | 1929 | 32.097 | 30 |  |
| 25 | 0x429+03A5 | CA:136E | 1 | 1964 | 32.680 | 5 |  |
| 26 | 0x429+03A8 | CA:1371 | 14 | 2034 | 33.844 | 25 |  |
| 27 | 0x429+03BA | CA:1383 | 11 | 2064 | 34.343 | 25 |  |
| 28 | 0x429+03CF | CA:1398 | 1 | 2324 | 38.670 | 15 |  |
| 29 | 0x429+03F1 | CA:13BA | 19 | 2523 | 41.981 | 25 |  |
| 30 | 0x429+0406 | CA:13CF | 29 | 2708 | 45.059 | 35 |  |
| 31 | 0x429+0425 | CA:13EE | 24 | 2903 | 48.304 | 20 |  |
| 32 | 0x429+043F | CA:1408 | 1 | 3083 | 51.299 | 5 |  |

Sum of the 32 "frames" values: 1,460 frames (24.3 s); the rest of the 3,088 frames are the scripted pauses (`WAIT n`, listed in the timeline), the fades, the walks and the map change.

## 7. Sound, screen and flags

| frame | s | what |
|---|---|---|
| 114 | 1.90 | music 0x37 (`SOUND` cmd 1, id 0x37, parameter bytes 0x12 0x8F) from canned event 0x737 |
| 2344 | 39.00 | music 0x39 (id 0x39, parameter bytes 0x14 0xFF) from canned event 0x739 |
| 3345 | 55.66 | sound effect 0xD6 (parameter bytes 0x00 0x01), requested by the Mana Beast engine at the end of phase 8 |

No other request is made by the scene itself. Screen effects:

| frame | effect |
|---|---|
| 1-60 (state) | `$49` = 0xE0 (jitter) is already on at frame 0 and is cleared by the map-255 loader |
| 4 | fade-out 57 frames (transition 59) |
| 61 | fade-in 15 frames (one level per frame) |
| 89 | camera re-centre, 7 frames |
| 119 | `SCREEN 6` 0x0010 palette fade, 17 values of `$010A`, last at 195 |
| 124 / 164 | `SCREEN 2` (`$49` = 0xE0, 40 frames) / `SCREEN 3` (`$49` = 0x60 until 2464) |
| 2339 | `SCREEN 6` 0xFFFF palette fade to black, cut at 2464 |
| 2408 | fade-out 57 frames (after the exit walk) |
| 2465 | fade-in 15 frames |

No flash, no mosaic and no colour effect (`$E2` bits 1, 2 and 4) occur in this scene. Event flag writes: flag 0x0B 2 -> 15 and flag 0xFF 0 -> 1 in frame 2503; flag 0xFF 1 -> 0 in frame 3088; `$CF4E` stays 8 (the arena record needs it).

The exit/entry byte of the transition table (`$C8:3000 + 4 * n + 3`, copied to `$E0`) as seen here: 0x80 / 0xA0 / 0x9F-0xBF (exit code 0, the fade starts at once; the loader's `$E0` | 0x1F is what later transitions see), 0x81 (exit code 1: the party walks up, [C] codes 1-4 = up, down, right, left at 2 px per frame, `$C0:BA06-BA4B`; codes 5 and above use other walk counts, `$C0:BA4C-BAD4`; not run). `$FF` values: 0x40 = map change pending, 0x20 = party walk in progress, 0x60 = both (exit walk).

## 8. Dependencies on the party [V]

| what | result |
|---|---|
| controlled hero | boy: 3,088 frames; girl or sprite: **3,080** frames. Everything is identical up to the map change at frame 2349; the exit walk (section 5.2) ends 8 frames earlier with the girl or the sprite, so map 253 loads at frame 2456 instead of 2464 and every later time moves by -8 |
| hero weapon types | none: runs with weapon types (4, 1, 3), (0, 0, 0) and (5, 7, 2) are identical in every VM command, movement and frame count (3,088). The scene uses animation codes 0xA8 (20 frames) and the walk code only; the weapon swing (code 0) is not used |
| hero HP, MP, statuses, levels, equipment | not read by the scene |
| flags | 0x4E >= 8 (else the event is the empty event 0); the Mana Beast exists only while `$CF4E` & 15 == 8 |
| player input | the pad is locked from frame 1; each text block waits for A, X, L, R, B or Y after the text is drawn (the harness presses in the first frame, so all dialog times are minimums); the controlled hero does not matter for the dialog |
| text speed | not determined: the harness uses the state's WRAM as it is |

## 9. Validation

- The ZSNES state `.zs2` of the save set is a real recording of this scene: map 255, VM state 0x85 (`WAIT_IDLE`) inside the canned event 0x05A, heroes at (344, 202), (328, 186), (360, 186), camera (216, 90), `$49` = 0x60, `$2A` = 0x60, `$010A` = `$010C` = 0x0010, flag 0x4E = 8, flag 0x0B = 2, controlled hero = the sprite. All of these are equal to what the run produces at frame 1982. Running the state forward with the harness reproduces the command times of the run to the frame (the command after the animation at +12 frames = frame 1994, the map change command at 2349) and loads map 253 at frame 2456, which is the time of the run with the sprite as controlled hero (section 8) [V].
- The extents of all 32 text blocks equal the engine's own end pointer [V]; the event is 1,091 bytes (`$CA:0FC9`-`$CA:140B`).
- The transition table, the map record formula and the loader placements agree with `docs/cutscene-engine.md` section 11 (transition 59: (344, 218)).

## 10. Method

`python3 tools/event_runs.py ROM STATE intro OUT.json [leader=N] [after=N] [weapons=A,B,C] [raw=FILE]` loads the WRAM of a ZSNES v143 state taken in map 246 with flag 0x4E = 8, sets the controlled hero, starts event 0x429 (`$C1:E76D`, as a trigger tile would), and steps the real frame body until the VM is idle; `after` more frames run to see the Mana Beast. Observers log every change of the 12 object slots, camera, screen bytes, the event flags and the sound requests. `tools/event_runs.py ROM report RAW.pkl OUT.json` rebuilds the report from the raw log; `tools/event_runs.py ROM md OUT.json` prints the timeline as the table of section 4.

## 11. Open questions (no values)

- Which tile of the Dark Lich rooms is entry 1 of the event list (the trigger-id to tile mapping was not traced), and who refers to event 0x426.
- The text engine: speed setting, the meaning of the control codes 0x51, 0x52, 0x7F and of the window commands, the time a real player needs.
- What the screen jitter `$49` does on screen (axis, amplitude) and what the helper objects of slots 6 and 7 do (the re-creation of slot 7 at (104, 0) during dialog).
- The visual content of animation 0xA8 and of the scene's two tint colours; the identities of music 0x37 and 0x39 and of sound 0xD6.
- Why the entry placement of transition 188 is (296, 472) and the walk-in covers 72 px (the loader's walk-in code `$C0:BA06-BAD4` was read only in part), and the meaning of `$E0` bits 5-7.
- The effect of flag 0x0B = 15 (no reader found).
- Real-hardware timing under slowdown.

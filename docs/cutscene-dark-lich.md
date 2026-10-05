# The Dark Lich arena cutscene (maps 245 and 246)

Tags: **[V]** measured by running the original 65816 code frame by frame with `tools/event_vm.py` (the harness and its limits are described in `docs/cutscene-engine.md` section 10); **[C]** read from the disassembly. Numbers: `data/cutscene_dark_lich.json` (produced by `tools/event_vm.py ROM STATE dark-lich out.json leader=0 variants=1`). Open items are in section 12 without values. The VM, the opcode names and the state bytes are in `docs/cutscene-engine.md`; this document is the timeline.

Time: **frames** of 1/60.0988 s counted from frame 0 = the frame in which the loader of map 245 returned (the first frame the party exists in the room); the VM only steps every fifth frame (12.02 Hz), so command times are frames = 4 mod 5 in map 245 (first step at frame 19) and = 0 mod 5 in map 246 (the 5-frame cycle restarts at the map load). Seconds are frames / 60.0988. Everything that depends on the player (button presses) assumes the press happens in the first frame the VM waits for one: the dialog times are the minimum.

## 1. Summary

| frame | s | what |
|---|---|---|
| 0 | 0.00 | map 245 loaded. Party (all three heroes on one pixel) at (280, 506) facing up; NPC 0xAC at (292, 388), NPC 0xBF at (276, 404), both facing down. Brightness fade-in, frames 1-15 (+1 per frame). The pad of the controlling hero is inactive from frame 0 |
| 19 | 0.32 | first VM step: entry event 0x428 -> 0x070 -> **0x4E1** (the scene). FREEZE: hero input off |
| 24 | 0.40 | music 0x1B |
| 29-68 | 0.48-1.13 | the controlled hero walks 80 px up to (280, 426) at 120.2 px/s (animation 1) |
| 74-101 | 1.23-1.68 | the other two heroes run up to the same point at 3 px per frame (animation 2); effect 0x8B twice (frame 84, requested by the engine while the two heroes run) |
| 104-132 | 1.73-2.20 | camera re-centres on the controlled hero ((152, 354) -> (152, 298)) |
| 134-141 | 2.23-2.35 | boy 16 px left to (264, 426), girl 16 px right to (296, 426); turn up at 144 |
| 149-679 | 2.48-11.30 | first dialog run: 8 text blocks |
| 679-780 | 11.30-12.98 | NPC 0xBF steps up four times by 4 px (to (276, 388)), turns right |
| 864-959 | 14.4-16.0 | 2 text blocks |
| 959-1010 | 15.96-16.8 | girl walks up 32 px to (296, 394), then 16 px right to (312, 394); **NPC 0xAC moves 35 px right** to (327, 388) in the same frames (979-1010): its own walk command (actor 4, right, 32 frames) is issued in the same VM step as the girl's, it is choreography, not a collision |
| 1019-1034 | 16.95-17.2 | girl plays her weapon swing (animation 0, state 0x40), effect 0x04 |
| 1039-1044 | 17.29-17.37 | white flash (5 frames) with effect 0x33 |
| 1044-1584 | 17.4-26.4 | 8 text blocks with timed pauses |
| 1584 | 26.36 | flag 0x4E 4 -> 5; REFRESH_OBJECTS: **NPC 0xBF is removed** |
| 1749 | 29.10 | music 0x08 |
| 1864 | 31.02 | raw sound command 0x80 (passed to the sound CPU unchanged, effect not decoded) |
| 2059 | 34.26 | music 0x04 |
| 2174-2194 | 36.2-36.5 | girl steps back 20 px (animation 0x8C, 1 px per frame), then animation 0xA9 (40 frames), then holds pose 0x80 until the map change |
| 2289-2329 | 38.1-38.8 | boy 24 px up and 16 px right to (296, 378); sprite 8 px up to (280, 410) |
| 2334-2358 | 38.84-39.2 | camera pan to (168, 250) |
| 2699 | 44.91 | music 0x29 |
| 3549 | 59.05 | music 0x33 |
| 3554 | 59.14 | flag 0x4E 5 -> 6; MAP_CHANGE transition 47 |
| 3555-3611 | 59.15-60.08 | fade-out 15 -> 0 (one level per 4 frames) |
| 3611 | 60.08 | **map 246 loaded: the Dark Lich is spawned** at (288, 336); heroes placed at (280, 426) facing up; camera (152, 312) |
| 3612-3626 | 60.10-60.35 | fade-in; the Lich AI ticks 4 times |
| 3630 | 60.40 | flag 0xFF raised (boss freeze), 3 text blocks |
| 3820 | 63.56 | flag 0xFF cleared, music 0x0C; **the Lich resumes** (first tick at frame 3822, 63.60 s) |
| 3825 | 63.65 | END: `$F1` and the pad lock are cleared, **control returns**, Lich alive and acting |

Total 3,825 frames = 63.65 s for the reference run (controlled hero = boy, girl with a sword); it varies by -15 to +20 frames with the party (section 11).

## 2. How the scene starts [V unless noted]

- The party arrives in map 245 through map transition 340 (`$C8:3000[340]` = map 245, start tile (17, 31)); the only reference found is entry 1 of the event list of map 251 (event 0x954 = 0x800 + 340) [C: found by scanning all event lists and all event scripts; which tile of map 251 triggers it was not traced].
- Maps 245 and 246 have the same event list `[0x428, 0x429]` and the same three map records. Entry event 0x428 = `IF_FLAG_RANGE flag 0x4E in 6..15` guarding a `GOTO 0` (event 0 is a lone END, so the scene is skipped when the flag is 6 or more), followed by `GOTO 0x070`; event 0x070 = `GOTO 0x4E1`. So **the scene plays when flag 0x4E is below 6**; the run starts with `$CF4E` = 4 [V]. Entry 1 of the list (event 0x429, a trigger tile) is another scene for flag values 8 and above (for 0-7 it jumps to the empty event 0); it is not examined here.
- Records (identical in both maps): record 0 = id 0xAC, flag 0x4E range 0-5, tile (18, 24); record 1 = id 0xBF, range 0-4, tile (17, 25); record 2 = id 0x79 (the Dark Lich boss), range 6-6, tile (18, 21), event word 0x442D (event 0x42D after its death). Hence the NPCs exist in map 245 while the counter is 4 (0xBF needs <= 4) and the Lich exists only after the script has raised the counter to 6, which it does just before the map change (flag 0x4E: 4 -> 5 at frame 1584, 5 -> 6 at frame 3554). Map 246 differs from 245 only in header byte 3 (`$B8` = 0xF4 instead of 0x04).
- Event 0x4E1 (the scene, 1,606 bytes, 48 text blocks): freeze, music, formation (event 0x47E), dialog, NPC and hero moves, flash, flags, music changes; at `$CA:313F` (= 0x4E1 + 0x5CF) the MAP_CHANGE to transition 47 (map 246, start tile (17, 26)); the rest of the script then runs in map 246: raise the boss freeze flag, three text blocks, lower it, GOTO event 0x70C (music 0x0C, END). The sub-events used: 0x7D7, 0x7D8, 0x7C4, 0x7DA, 0x733, 0x70C (music), 0x78E (effect 0x33), 0x748 (raw command 0x80), 0x47E (formation), 0x05C (girl animation 0xA9).

## 3. Coordinates

- **Map pixels**: origin at the top-left corner of the map, x to the right, y down. Both maps are 576 x 640 px (36 x 40 tiles of 16 px; `$C0` = 576, `$C2` = 640) [V]. An object's position is the pair of words `obj+2` (x) and `obj+4` (y); there is no separate room origin.
- Heroes are placed at the start tile of the transition at `(16 * tileX + 8, 16 * tileY + 10)`: tile (17, 31) -> **(280, 506)** in map 245, tile (17, 26) -> **(280, 426)** in map 246 [V]. NPC records are placed at `16 * tile + 4`: (18, 24) -> (292, 388), (17, 25) -> (276, 404). The boss record is spawned at `16 * tile`: tile (18, 21) -> **(288, 336)**.
- **Camera** `$A8/$AA` = map pixel at the top-left corner of the 256 x 224 screen; screen position = map position - camera. At entry the camera is the start tile origin minus (120, 104): (152, 392) in map 245 and (152, 312) in map 246, which puts a hero at screen (128, 114) [V]. In map 246 the Lich is at screen (136, 24), the heroes at (128, 114).
- Velocities are in pixels per frame (x 60.0988 = px/s); 2 px per frame = 120.2 px/s, 3 px per frame = 180.3 px/s, 1 px per frame = 60.1 px/s.
- Facing codes: 0 up, 1 down, 2 right, 0x82 left.

## 4. Actors at entry [V]

| object | slot | id | map | position | facing | animation |
|---|---|---|---|---|---|---|
| boy | 0 | 0x80 | 245 | (280, 506) | up | idle |
| girl | 1 | 0x81 | 245 | (280, 506) | up | idle |
| sprite | 2 | 0x82 | 245 | (280, 506) | up | idle |
| NPC, map record 0 | 3 | 0xAC | 245 | (292, 388) | down | idle |
| NPC, map record 1 | 4 | 0xBF | 245 | (276, 404) | down | idle |
| camera | - | - | 245 | (152, 392) | - | - |
| boy / girl / sprite | 0 / 1 / 2 | 0x80 / 0x81 / 0x82 | 246 | (280, 426) each | up | idle |
| Dark Lich | 3 | 0x79 | 246 | engine position (288, 336) (`obj+0x2B/+0x32`; `obj+2/+4` unused), flags `obj+0x98` = 0x9C01, phase `obj+0x94` = 0 at the spawn frame, facing down | - | stand, state 2 after its first tick (`docs/dark-lich.md` section 4) |
| helper object | 6 | 0x00 | 246 | (288, 335), appears at frame 3613 (flags 0x2909); follows the Lich's 1 px bob; role not determined | - | - |
| camera | - | - | 246 | (152, 312) | - | - |

The names of the two NPCs and of the speakers are not recorded here; the ids are all that is used. The girl is hero slot 1; she is the actor of the walk next to NPC 0xAC and of the weapon swing.

## 5. Timeline

Every row is a measured event of the reference run (state with `$CF4E` = 4, controlled hero = slot 0, hero weapons whip / sword / spear). `VM event+offset` rows are the commands as executed (several commands can run in one frame); rows with an object name are what the real code did to that object; "caused by" ties a movement to its command. `engine` rows are state changes of the game engine. "dialog" rows collapse consecutive text blocks (each of which is followed by a wait for a button); their positions, lengths and times are in section 7.

| frame | s | object | what |
|---|---|---|---|
| 0 | 0.000 | party | map 245 loaded, party placed at its start tile; fade-in brightness 0 -> 15 (+1 per frame, frames 1-15) |
| 1 | 0.017 | screen | fade_in brightness 0 -> 15, 15 frames |
| 19 | 0.316 | VM 0x428+0000 | IF_FLAG_RANGE flag 0x4E in 6..15 |
| 19 | 0.316 | VM 0x428+0005 | GOTO_EVENT event 0x070 |
| 19 | 0.316 | VM 0x070+0000 | GOTO_EVENT event 0x4E1 |
| 19 | 0.316 | VM 0x4E1+0000 | FREEZE |
| 19 | 0.316 | engine | world_freeze_on |
| 24 | 0.399 | VM 0x4E1+0001 | CALL_EVENT event 0x7D7 |
| 24 | 0.399 | VM 0x7D7+0000 | SOUND cmd 1 id 0x1B word 0x8F13 |
| 24 | 0.399 | sound | music id 0x1B (cmd 1, params 0x13 0x8F) from vm_op |
| 29 | 0.483 | VM 0x7D7+0005 | RETURN |
| 29 | 0.483 | VM 0x4E1+0003 | ACTOR_WALK actor 0 up 40 frames |
| 29 | 0.483 | VM 0x4E1+0006 | WAIT_IDLE (state 0x85) |
| 29 | 0.483 | boy (slot 0) | walk (280, 506) -> (280, 426), 40 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 40x(+0,-2) [0x4E1+0003 ACTOR_WALK actor 0 up 40 frames] |
| 50 | 0.832 | camera | scroll (152, 392) -> (152, 354), 19 frames |
| 69 | 1.148 | VM 0x4E1+0007 | CALL_EVENT event 0x47E |
| 69 | 1.148 | VM 0x47E+0000 | FREEZE |
| 74 | 1.231 | VM 0x47E+0001 | GATHER |
| 75 | 1.248 | girl (slot 1) | walk (280, 506) -> (280, 426), 27 frames, 178.1 px/s, facing up, anim [1, 2], per-frame 26x(+0,-3) 1x(+0,-2) [0x47E+0001 GATHER] |
| 75 | 1.248 | sprite (slot 2) | walk (280, 506) -> (280, 426), 27 frames, 178.1 px/s, facing up, anim [1, 2], per-frame 26x(+0,-3) 1x(+0,-2) [0x47E+0001 GATHER] |
| 84 | 1.398 | sound | sfx id 0x8B (cmd 2, params 0x0F 0x88) from engine |
| 84 | 1.398 | sound | sfx id 0x8B (cmd 2, params 0x0F 0x88) from engine |
| 104 | 1.730 | VM 0x47E+0002 | SCREEN arg 8 |
| 104 | 1.730 | camera | scroll (152, 354) -> (152, 298), 28 frames |
| 104 | 1.730 | engine | camera_recentre_start |
| 132 | 2.196 | engine | camera_recentre_done |
| 134 | 2.230 | VM 0x47E+0004 | ACTOR_WALK actor 3 up 0 frames |
| 134 | 2.230 | VM 0x47E+0007 | ACTOR_WALK actor 1 left 8 frames |
| 134 | 2.230 | VM 0x47E+000A | ACTOR_WALK actor 2 right 8 frames |
| 134 | 2.230 | VM 0x47E+000D | WAIT_IDLE (state 0x85) |
| 134 | 2.230 | boy (slot 0) | walk (280, 426) -> (264, 426), 8 frames, 120.2 px/s, facing left, anim [0, 1], per-frame 8x(-2,+0) [0x47E+0007 ACTOR_WALK actor 1 left 8 frames] |
| 134 | 2.230 | girl (slot 1) | walk (280, 426) -> (296, 426), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x47E+000A ACTOR_WALK actor 2 right 8 frames] |
| 144 | 2.396 | VM 0x47E+000E | ACTOR_WALK actor 3 up 0 frames |
| 144 | 2.396 | VM 0x47E+0011 | ACTOR_WALK actor 1 up 0 frames |
| 144 | 2.396 | VM 0x47E+0014 | ACTOR_WALK actor 2 up 0 frames |
| 144 | 2.396 | VM 0x47E+0017 | WAIT_IDLE (state 0x85) |
| 144 | 2.396 | boy (slot 0) | facing up (0x00) |
| 144 | 2.396 | girl (slot 1) | facing up (0x00) |
| 149 | 2.479 | VM 0x47E+0018 | RETURN |
| 149 | 2.479 | dialog | 8 text blocks from 0x4E1+0009, each followed by a wait for a button; the next command runs at frame 679 |
| 679 | 11.298 | VM 0x4E1+016A | ACTOR_WALK actor 5 up 2 frames |
| 679 | 11.298 | VM 0x4E1+016D | WAIT_IDLE (state 0x85) |
| 679 | 11.298 | slot 4 (id 0xBF) | walk (276, 404) -> (276, 400), 2 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 2x(+0,-2) [0x4E1+016A ACTOR_WALK actor 5 up 2 frames] |
| 684 | 11.381 | VM 0x4E1+016E | WAIT 4 ticks (= 20 frames, 0.333 s) |
| 704 | 11.714 | VM 0x4E1+0170 | ACTOR_WALK actor 5 up 2 frames |
| 704 | 11.714 | VM 0x4E1+0173 | WAIT_IDLE (state 0x85) |
| 704 | 11.714 | slot 4 (id 0xBF) | walk (276, 400) -> (276, 396), 2 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 2x(+0,-2) [0x4E1+0170 ACTOR_WALK actor 5 up 2 frames] |
| 709 | 11.797 | VM 0x4E1+0174 | WAIT 4 ticks (= 20 frames, 0.333 s) |
| 729 | 12.130 | VM 0x4E1+0176 | ACTOR_WALK actor 5 up 2 frames |
| 729 | 12.130 | VM 0x4E1+0179 | WAIT_IDLE (state 0x85) |
| 729 | 12.130 | slot 4 (id 0xBF) | walk (276, 396) -> (276, 392), 2 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 2x(+0,-2) [0x4E1+0176 ACTOR_WALK actor 5 up 2 frames] |
| 734 | 12.213 | VM 0x4E1+017A | WAIT 4 ticks (= 20 frames, 0.333 s) |
| 754 | 12.546 | VM 0x4E1+017C | ACTOR_WALK actor 5 up 2 frames |
| 754 | 12.546 | VM 0x4E1+017F | WAIT_IDLE (state 0x85) |
| 754 | 12.546 | slot 4 (id 0xBF) | walk (276, 392) -> (276, 388), 2 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 2x(+0,-2) [0x4E1+017C ACTOR_WALK actor 5 up 2 frames] |
| 759 | 12.629 | VM 0x4E1+0180 | WAIT 4 ticks (= 20 frames, 0.333 s) |
| 779 | 12.962 | VM 0x4E1+0182 | ACTOR_WALK actor 5 right 0 frames |
| 779 | 12.962 | VM 0x4E1+0185 | WAIT_IDLE (state 0x85) |
| 779 | 12.962 | slot 4 (id 0xBF) | facing right (0x02) |
| 784 | 13.045 | VM 0x4E1+0186 | WAIT 16 ticks (= 80 frames, 1.331 s) |
| 864 | 14.376 | dialog | 2 text blocks from 0x4E1+0188, each followed by a wait for a button; the next command runs at frame 959 |
| 959 | 15.957 | VM 0x4E1+01B7 | ACTOR_WALK actor 2 up 16 frames |
| 959 | 15.957 | VM 0x4E1+01BA | WAIT_IDLE (state 0x85) |
| 959 | 15.957 | girl (slot 1) | walk (296, 426) -> (296, 394), 16 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 16x(+0,-2) [0x4E1+01B7 ACTOR_WALK actor 2 up 16 frames] |
| 979 | 16.290 | VM 0x4E1+01BB | ACTOR_WALK actor 2 right 8 frames |
| 979 | 16.290 | VM 0x4E1+01BE | ACTOR_WALK actor 4 right 32 frames |
| 979 | 16.290 | VM 0x4E1+01C1 | WAIT_IDLE (state 0x85) |
| 979 | 16.290 | girl (slot 1) | walk (296, 394) -> (312, 394), 8 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 8x(+2,+0) [0x4E1+01BB ACTOR_WALK actor 2 right 8 frames] |
| 979 | 16.290 | slot 3 (id 0xAC) | walk (292, 388) -> (327, 388), 32 frames, 65.7 px/s, facing right, anim [0, 1], per-frame 3x(+2,+0) 29x(+1,+0) [0x4E1+01BE ACTOR_WALK actor 4 right 32 frames] |
| 1014 | 16.872 | VM 0x4E1+01C2 | ACTOR_WALK actor 2 left 0 frames |
| 1014 | 16.872 | VM 0x4E1+01C5 | ACTOR_WALK actor 4 down 0 frames |
| 1014 | 16.872 | VM 0x4E1+01C8 | WAIT_IDLE (state 0x85) |
| 1014 | 16.872 | girl (slot 1) | facing left (0x82) |
| 1014 | 16.872 | slot 3 (id 0xAC) | facing down (0x01) |
| 1019 | 16.955 | VM 0x4E1+01C9 | ACTOR_ANIM actor 2 anim 0x00 |
| 1019 | 16.955 | VM 0x4E1+01CC | WAIT_IDLE (state 0x85) |
| 1019 | 16.955 | girl (slot 1) | pose state 0x40 anim 0x00 |
| 1019 | 16.955 | sound | sfx id 0x04 (cmd 2, params 0x00 0xAA) from engine |
| 1034 | 17.205 | girl (slot 1) | pose idle |
| 1039 | 17.288 | VM 0x4E1+01CD | SCREEN arg 0 |
| 1039 | 17.288 | VM 0x4E1+01CF | CALL_EVENT event 0x78E |
| 1039 | 17.288 | VM 0x78E+0000 | SOUND cmd 2 id 0x33 word 0x8800 |
| 1039 | 17.288 | engine | flash_on |
| 1039 | 17.288 | sound | sfx id 0x33 (cmd 2, params 0x00 0x88) from vm_op |
| 1044 | 17.371 | VM 0x78E+0005 | RETURN |
| 1044 | 17.371 | VM 0x4E1+01D1 | SCREEN arg 1 |
| 1044 | 17.371 | dialog | 1 text block from 0x4E1+01D3, each followed by a wait for a button; the next command runs at frame 1114 |
| 1044 | 17.371 | engine | flash_off |
| 1114 | 18.536 | VM 0x4E1+01FA | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 1154 | 19.202 | dialog | 1 text block from 0x4E1+01FC, each followed by a wait for a button; the next command runs at frame 1174 |
| 1174 | 19.534 | VM 0x4E1+0204 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 1214 | 20.200 | dialog | 1 text block from 0x4E1+0206, each followed by a wait for a button; the next command runs at frame 1244 |
| 1244 | 20.699 | VM 0x4E1+0216 | WAIT 2 ticks (= 10 frames, 0.166 s) |
| 1254 | 20.866 | dialog | 2 text blocks from 0x4E1+0218, each followed by a wait for a button; the next command runs at frame 1309 |
| 1309 | 21.781 | VM 0x4E1+0233 | WAIT 2 ticks (= 10 frames, 0.166 s) |
| 1319 | 21.947 | dialog | 1 text block from 0x4E1+0235, each followed by a wait for a button; the next command runs at frame 1339 |
| 1339 | 22.280 | VM 0x4E1+0240 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 1379 | 22.946 | dialog | 1 text block from 0x4E1+0242, each followed by a wait for a button; the next command runs at frame 1409 |
| 1409 | 23.445 | VM 0x4E1+0255 | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 1569 | 26.107 | dialog | 1 text block from 0x4E1+0257, each followed by a wait for a button; the next command runs at frame 1584 |
| 1584 | 26.357 | VM 0x4E1+0258 | FLAG_INC flag 0x4E |
| 1584 | 26.357 | VM 0x4E1+025A | REFRESH_OBJECTS |
| 1584 | 26.357 | slot 4 (id 0xBF) | removed |
| 1584 | 26.357 | engine | flag_4E_changed 5 |
| 1589 | 26.440 | VM 0x4E1+025B | WAIT 32 ticks (= 160 frames, 2.662 s) |
| 1749 | 29.102 | VM 0x4E1+025D | CALL_EVENT event 0x7D8 |
| 1749 | 29.102 | VM 0x7D8+0000 | SOUND cmd 1 id 0x08 word 0x8F1B |
| 1749 | 29.102 | sound | music id 0x08 (cmd 1, params 0x1B 0x8F) from vm_op |
| 1754 | 29.185 | VM 0x7D8+0005 | RETURN |
| 1754 | 29.185 | VM 0x4E1+025F | ACTOR_WALK actor 2 right 0 frames |
| 1754 | 29.185 | VM 0x4E1+0262 | WAIT_IDLE (state 0x85) |
| 1754 | 29.185 | girl (slot 1) | facing right (0x02) |
| 1759 | 29.268 | dialog | 2 text blocks from 0x4E1+0263, each followed by a wait for a button; the next command runs at frame 1864 |
| 1864 | 31.016 | VM 0x4E1+029E | CALL_EVENT event 0x748 |
| 1864 | 31.016 | VM 0x748+0000 | SOUND cmd 128 id 0x80 word 0x0000 |
| 1864 | 31.016 | sound | raw id 0x80 (cmd 128, params 0x00 0x00) from vm_op |
| 1869 | 31.099 | VM 0x748+0005 | RETURN |
| 1869 | 31.099 | dialog | 1 text block from 0x4E1+02A0, each followed by a wait for a button; the next command runs at frame 1884 |
| 1884 | 31.348 | VM 0x4E1+02A4 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 1924 | 32.014 | dialog | 1 text block from 0x4E1+02A6, each followed by a wait for a button; the next command runs at frame 1939 |
| 1939 | 32.264 | VM 0x4E1+02A9 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 1979 | 32.929 | dialog | 1 text block from 0x4E1+02AB, each followed by a wait for a button; the next command runs at frame 1994 |
| 1994 | 33.179 | VM 0x4E1+02AE | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2034 | 33.844 | dialog | 1 text block from 0x4E1+02B0, each followed by a wait for a button; the next command runs at frame 2059 |
| 2059 | 34.260 | VM 0x4E1+02BD | CALL_EVENT event 0x7C4 |
| 2059 | 34.260 | VM 0x7C4+0000 | SOUND cmd 1 id 0x04 word 0xFF04 |
| 2059 | 34.260 | sound | music id 0x04 (cmd 1, params 0x04 0xFF) from vm_op |
| 2064 | 34.343 | VM 0x7C4+0005 | RETURN |
| 2064 | 34.343 | dialog | 1 text block from 0x4E1+02BF, each followed by a wait for a button; the next command runs at frame 2159 |
| 2159 | 35.924 | VM 0x4E1+0305 | ACTOR_WALK actor 4 left 0 frames |
| 2159 | 35.924 | VM 0x4E1+0308 | WAIT_IDLE (state 0x85) |
| 2159 | 35.924 | slot 3 (id 0xAC) | facing left (0x82) |
| 2164 | 36.007 | dialog | 1 text block from 0x4E1+0309, each followed by a wait for a button; the next command runs at frame 2174 |
| 2174 | 36.174 | VM 0x4E1+030C | ACTOR_ANIM actor 2 anim 0x8C |
| 2174 | 36.174 | VM 0x4E1+030F | WAIT_IDLE (state 0x85) |
| 2174 | 36.174 | girl (slot 1) | pose state 0x40 anim 0x8C |
| 2175 | 36.190 | girl (slot 1) | walk (312, 394) -> (292, 394), 20 frames, 60.1 px/s, facing right, anim [0, 140], per-frame 20x(-1,+0) [0x4E1+030C ACTOR_ANIM actor 2 anim 0x8C] |
| 2194 | 36.507 | girl (slot 1) | pose idle |
| 2199 | 36.590 | VM 0x4E1+0310 | CALL_EVENT event 0x05C |
| 2199 | 36.590 | VM 0x05C+0000 | ACTOR_ANIM actor 2 anim 0xA9 |
| 2199 | 36.590 | VM 0x05C+0003 | WAIT_IDLE (state 0x85) |
| 2199 | 36.590 | girl (slot 1) | pose state 0x40 anim 0xA9 |
| 2239 | 37.255 | girl (slot 1) | pose idle |
| 2244 | 37.339 | VM 0x05C+0004 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2284 | 38.004 | VM 0x05C+0006 | RETURN |
| 2284 | 38.004 | VM 0x4E1+0312 | ACTOR_ANIM_LOOP actor 2 anim 0x80 |
| 2284 | 38.004 | VM 0x4E1+0315 | WAIT_IDLE (state 0x85) |
| 2284 | 38.004 | girl (slot 1) | pose state 0x30 anim 0x80 |
| 2289 | 38.087 | VM 0x4E1+0316 | ACTOR_WALK actor 1 up 24 frames |
| 2289 | 38.087 | VM 0x4E1+0319 | ACTOR_WALK actor 3 up 8 frames |
| 2289 | 38.087 | VM 0x4E1+031C | WAIT_IDLE (state 0x85) |
| 2289 | 38.087 | boy (slot 0) | walk (264, 426) -> (264, 378), 24 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 24x(+0,-2) [0x4E1+0316 ACTOR_WALK actor 1 up 24 frames] |
| 2289 | 38.087 | sprite (slot 2) | walk (280, 426) -> (280, 410), 8 frames, 120.2 px/s, facing up, anim [0, 1], per-frame 8x(+0,-2) [0x4E1+0319 ACTOR_WALK actor 3 up 8 frames] |
| 2314 | 38.503 | VM 0x4E1+031D | ACTOR_WALK actor 1 right 16 frames |
| 2314 | 38.503 | VM 0x4E1+0320 | ACTOR_WALK actor 3 right 0 frames |
| 2314 | 38.503 | VM 0x4E1+0323 | WAIT_IDLE (state 0x85) |
| 2314 | 38.503 | boy (slot 0) | walk (264, 378) -> (296, 378), 16 frames, 120.2 px/s, facing right, anim [0, 1], per-frame 16x(+2,+0) [0x4E1+031D ACTOR_WALK actor 1 right 16 frames] |
| 2314 | 38.503 | sprite (slot 2) | facing right (0x02) |
| 2334 | 38.836 | VM 0x4E1+0324 | SCREEN arg 8 |
| 2334 | 38.836 | camera | scroll (152, 298) -> (168, 250), 24 frames |
| 2334 | 38.836 | engine | camera_recentre_start |
| 2358 | 39.235 | engine | camera_recentre_done |
| 2359 | 39.252 | dialog | 2 text blocks from 0x4E1+0326, each followed by a wait for a button; the next command runs at frame 2514 |
| 2514 | 41.831 | VM 0x4E1+0390 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2554 | 42.497 | dialog | 1 text block from 0x4E1+0392, each followed by a wait for a button; the next command runs at frame 2564 |
| 2564 | 42.663 | VM 0x4E1+0394 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2604 | 43.329 | dialog | 1 text block from 0x4E1+0396, each followed by a wait for a button; the next command runs at frame 2614 |
| 2614 | 43.495 | VM 0x4E1+0397 | WAIT 8 ticks (= 40 frames, 0.666 s) |
| 2654 | 44.161 | dialog | 2 text blocks from 0x4E1+0399, each followed by a wait for a button; the next command runs at frame 2699 |
| 2699 | 44.909 | VM 0x4E1+03AA | CALL_EVENT event 0x7DA |
| 2699 | 44.909 | VM 0x7DA+0000 | SOUND cmd 1 id 0x29 word 0x8F1C |
| 2699 | 44.909 | sound | music id 0x29 (cmd 1, params 0x1C 0x8F) from vm_op |
| 2704 | 44.993 | VM 0x7DA+0005 | RETURN |
| 2704 | 44.993 | VM 0x4E1+03AC | FLAG_INC flag 0xF8 |
| 2704 | 44.993 | dialog | 6 text blocks from 0x4E1+03AE, each followed by a wait for a button; the next command runs at frame 3184 |
| 3184 | 52.979 | VM 0x4E1+04F9 | FLAG_DEC flag 0xF8 |
| 3184 | 52.979 | dialog | 2 text blocks from 0x4E1+04FB, each followed by a wait for a button; the next command runs at frame 3249 |
| 3249 | 54.061 | VM 0x4E1+0515 | FLAG_INC flag 0xF8 |
| 3249 | 54.061 | dialog | 3 text blocks from 0x4E1+0517, each followed by a wait for a button; the next command runs at frame 3424 |
| 3424 | 56.973 | VM 0x4E1+0583 | FLAG_DEC flag 0xF8 |
| 3424 | 56.973 | dialog | 2 text blocks from 0x4E1+0585, each followed by a wait for a button; the next command runs at frame 3549 |
| 3549 | 59.053 | VM 0x4E1+05CB | CALL_EVENT event 0x733 |
| 3549 | 59.053 | VM 0x733+0000 | SOUND cmd 1 id 0x33 word 0x8F13 |
| 3549 | 59.053 | sound | music id 0x33 (cmd 1, params 0x13 0x8F) from vm_op |
| 3554 | 59.136 | VM 0x733+0005 | RETURN |
| 3554 | 59.136 | VM 0x4E1+05CD | FLAG_INC flag 0x4E |
| 3554 | 59.136 | VM 0x4E1+05CF | MAP_CHANGE transition 47 |
| 3554 | 59.136 | engine | flag_4E_changed 6 |
| 3555 | 59.153 | screen | fade_out brightness 15 -> 0, 57 frames |
| 3611 | 60.084 | camera | set by the map loader to (152, 312) |
| 3611 | 60.084 | Dark Lich | spawned by the boss spawner: engine position (288,336), flags 0x9C01 |
| 3612 | 60.101 | screen | fade_in brightness 0 -> 15, 15 frames |
| 3615 | 60.151 | girl (slot 1) | facing up (0x00) |
| 3615 | 60.151 | girl (slot 1) | pose idle |
| 3615 | 60.151 | sprite (slot 2) | facing up (0x00) |
| 3617 | 60.184 | slot 3 (id 0x79) | facing down (0x01) |
| 3630 | 60.401 | VM 0x4E1+05D1 | FLAG_INC flag 0xFF |
| 3630 | 60.401 | dialog | 3 text blocks from 0x4E1+05D3, each followed by a wait for a button; the next command runs at frame 3820 |
| 3630 | 60.401 | engine | boss_freeze_flag_set |
| 3820 | 63.562 | VM 0x4E1+0641 | FLAG_DEC flag 0xFF |
| 3820 | 63.562 | VM 0x4E1+0643 | GOTO_EVENT event 0x70C |
| 3820 | 63.562 | VM 0x70C+0000 | SOUND cmd 1 id 0x0C word 0xFF06 |
| 3820 | 63.562 | engine | boss_freeze_flag_cleared |
| 3820 | 63.562 | sound | music id 0x0C (cmd 1, params 0x06 0xFF) from vm_op |
| 3822 | 63.595 | Dark Lich | first AI tick after the freeze flag was cleared |
| 3825 | 63.645 | VM 0x70C+0005 | END |
| 3825 | 63.645 | engine | world_freeze_off |
| 3825 | 63.645 | engine | pad_released |

## 6. Movements

All walks are `ACTOR_WALK` (2 px per frame, one count = one frame) unless the cause says otherwise. "Per-frame displacement" lists run lengths of (dx, dy).

| object | frame start-end | s start | from | to | frames | px/s | facing | anim | per-frame displacement | caused by |
|---|---|---|---|---|---|---|---|---|---|---|
| boy (slot 0) | 29-68 | 0.48 | (280,506) | (280,426) | 40 | 120.2 | up | 0,1 | 40x(+0,-2) | 0x4E1+0003 ACTOR_WALK actor 0 up 40 frames |
| girl (slot 1) | 75-101 | 1.25 | (280,506) | (280,426) | 27 | 178.1 | up | 1,2 | 26x(+0,-3) 1x(+0,-2) | 0x47E+0001 GATHER |
| sprite (slot 2) | 75-101 | 1.25 | (280,506) | (280,426) | 27 | 178.1 | up | 1,2 | 26x(+0,-3) 1x(+0,-2) | 0x47E+0001 GATHER |
| boy (slot 0) | 134-141 | 2.23 | (280,426) | (264,426) | 8 | 120.2 | left | 0,1 | 8x(-2,+0) | 0x47E+0007 ACTOR_WALK actor 1 left 8 frames |
| girl (slot 1) | 134-141 | 2.23 | (280,426) | (296,426) | 8 | 120.2 | right | 0,1 | 8x(+2,+0) | 0x47E+000A ACTOR_WALK actor 2 right 8 frames |
| slot 4 (id 0xBF) | 679-680 | 11.30 | (276,404) | (276,400) | 2 | 120.2 | up | 0,1 | 2x(+0,-2) | 0x4E1+016A ACTOR_WALK actor 5 up 2 frames |
| slot 4 (id 0xBF) | 704-705 | 11.71 | (276,400) | (276,396) | 2 | 120.2 | up | 0,1 | 2x(+0,-2) | 0x4E1+0170 ACTOR_WALK actor 5 up 2 frames |
| slot 4 (id 0xBF) | 729-730 | 12.13 | (276,396) | (276,392) | 2 | 120.2 | up | 0,1 | 2x(+0,-2) | 0x4E1+0176 ACTOR_WALK actor 5 up 2 frames |
| slot 4 (id 0xBF) | 754-755 | 12.55 | (276,392) | (276,388) | 2 | 120.2 | up | 0,1 | 2x(+0,-2) | 0x4E1+017C ACTOR_WALK actor 5 up 2 frames |
| girl (slot 1) | 959-974 | 15.96 | (296,426) | (296,394) | 16 | 120.2 | up | 0,1 | 16x(+0,-2) | 0x4E1+01B7 ACTOR_WALK actor 2 up 16 frames |
| girl (slot 1) | 979-986 | 16.29 | (296,394) | (312,394) | 8 | 120.2 | right | 0,1 | 8x(+2,+0) | 0x4E1+01BB ACTOR_WALK actor 2 right 8 frames |
| slot 3 (id 0xAC) | 979-1010 | 16.29 | (292,388) | (327,388) | 32 | 65.7 | right | 0,1 | 3x(+2,+0) 29x(+1,+0) | 0x4E1+01BE ACTOR_WALK actor 4 right 32 frames |
| girl (slot 1) | 2175-2194 | 36.19 | (312,394) | (292,394) | 20 | 60.1 | right | 0,140 | 20x(-1,+0) | 0x4E1+030C ACTOR_ANIM actor 2 anim 0x8C |
| boy (slot 0) | 2289-2312 | 38.09 | (264,426) | (264,378) | 24 | 120.2 | up | 0,1 | 24x(+0,-2) | 0x4E1+0316 ACTOR_WALK actor 1 up 24 frames |
| sprite (slot 2) | 2289-2296 | 38.09 | (280,426) | (280,410) | 8 | 120.2 | up | 0,1 | 8x(+0,-2) | 0x4E1+0319 ACTOR_WALK actor 3 up 8 frames |
| boy (slot 0) | 2314-2329 | 38.50 | (264,378) | (296,378) | 16 | 120.2 | right | 0,1 | 16x(+2,+0) | 0x4E1+031D ACTOR_WALK actor 1 right 16 frames |

Notes: the gather run uses 3 px per frame (anim 2, 178 px/s average because the last frame is 2 px); the NPC 0xAC covers its 35 px in 32 frames because its velocity byte falls from 2 to 1 px per frame after the third frame; the girl's backwards step (anim 0x8C) is produced by the animation itself (facing stays right, 1 px per frame to the left).

## 7. Dialog blocks

The text is inline in the script, so there are no message ids; a block is identified by its script address (bank `$CA`) and byte length. "Start frame" is the frame of the VM step that handed the block to the text engine, "VM resumes" the frame of the next VM command (the block is then finished: the wait for a button or the next command). The A button is pressed in the first frame the VM waits, so the durations include only the typing time and the 5-frame step granularity.

| # | script address | bytes | start frame | start s | VM resumes at frame | frames |
|---|---|---|---|---|---|---|
| 1 | CA:2B79 | 11 | 149 | 2.48 | 184 | 35 |
| 2 | CA:2B86 | 44 | 189 | 3.14 | 249 | 60 |
| 3 | CA:2BB4 | 54 | 254 | 4.23 | 324 | 70 |
| 4 | CA:2BEC | 75 | 329 | 5.47 | 429 | 100 |
| 5 | CA:2C39 | 72 | 434 | 7.22 | 529 | 95 |
| 6 | CA:2C83 | 13 | 534 | 8.89 | 559 | 25 |
| 7 | CA:2C92 | 69 | 564 | 9.38 | 659 | 95 |
| 8 | CA:2CD9 | 1 | 664 | 11.05 | 679 | 15 |
| 9 | CA:2CF8 | 44 | 864 | 14.38 | 939 | 75 |
| 10 | CA:2D26 | 1 | 944 | 15.71 | 959 | 15 |
| 11 | CA:2D43 | 39 | 1044 | 17.37 | 1114 | 70 |
| 12 | CA:2D6C | 8 | 1154 | 19.20 | 1174 | 20 |
| 13 | CA:2D76 | 16 | 1214 | 20.20 | 1244 | 30 |
| 14 | CA:2D88 | 12 | 1254 | 20.87 | 1274 | 20 |
| 15 | CA:2D96 | 13 | 1279 | 21.28 | 1309 | 30 |
| 16 | CA:2DA5 | 11 | 1319 | 21.95 | 1339 | 20 |
| 17 | CA:2DB2 | 19 | 1379 | 22.95 | 1409 | 30 |
| 18 | CA:2DC7 | 1 | 1569 | 26.11 | 1584 | 15 |
| 19 | CA:2DD3 | 28 | 1759 | 29.27 | 1819 | 60 |
| 20 | CA:2DF1 | 29 | 1824 | 30.35 | 1864 | 40 |
| 21 | CA:2E10 | 4 | 1869 | 31.10 | 1884 | 15 |
| 22 | CA:2E16 | 3 | 1924 | 32.01 | 1939 | 15 |
| 23 | CA:2E1B | 3 | 1979 | 32.93 | 1994 | 15 |
| 24 | CA:2E20 | 13 | 2034 | 33.84 | 2059 | 25 |
| 25 | CA:2E31 | 68 | 2069 | 34.43 | 2159 | 90 |
| 26 | CA:2E7B | 1 | 2169 | 36.09 | 2174 | 5 |
| 27 | CA:2E96 | 47 | 2359 | 39.25 | 2429 | 70 |
| 28 | CA:2EC7 | 57 | 2434 | 40.50 | 2514 | 80 |
| 29 | CA:2F02 | 2 | 2554 | 42.50 | 2564 | 10 |
| 30 | CA:2F06 | 1 | 2604 | 43.33 | 2614 | 10 |
| 31 | CA:2F09 | 14 | 2654 | 44.16 | 2679 | 25 |
| 32 | CA:2F19 | 1 | 2684 | 44.66 | 2699 | 15 |
| 33 | CA:2F1E | 45 | 2704 | 44.99 | 2774 | 70 |
| 34 | CA:2F4D | 60 | 2779 | 46.24 | 2864 | 85 |
| 35 | CA:2F8B | 76 | 2869 | 47.74 | 2969 | 100 |
| 36 | CA:2FD9 | 64 | 2974 | 49.49 | 3064 | 90 |
| 37 | CA:301B | 75 | 3069 | 51.07 | 3169 | 100 |
| 38 | CA:3068 | 1 | 3174 | 52.81 | 3184 | 10 |
| 39 | CA:306B | 23 | 3184 | 52.98 | 3229 | 45 |
| 40 | CA:3084 | 1 | 3234 | 53.81 | 3249 | 15 |
| 41 | CA:3087 | 64 | 3249 | 54.06 | 3339 | 90 |
| 42 | CA:30C9 | 39 | 3344 | 55.64 | 3409 | 65 |
| 43 | CA:30F2 | 1 | 3414 | 56.81 | 3424 | 10 |
| 44 | CA:30F5 | 67 | 3424 | 56.97 | 3529 | 105 |
| 45 | CA:313A | 1 | 3534 | 58.80 | 3549 | 15 |
| 46 | CA:3143 | 75 | 3630 | 60.40 | 3740 | 110 |
| 47 | CA:3190 | 30 | 3745 | 62.31 | 3800 | 55 |
| 48 | CA:31B0 | 1 | 3805 | 63.31 | 3820 | 15 |

Dialog runs with the commands between them: see the `dialog` rows of section 5. Flag 0xF8 is raised before the block at 0x4E1+0x3AE (frame 2704), lowered at 0x4E1+0x4F9 (3184), raised at +0x515 (3249) and lowered at +0x583 (3424): the meaning is not determined.

## 8. Music and sound requests

`$1E00` = 1 starts music `$1E01`; 2 plays sound effect `$1E01`; other values are raw commands (`docs/audio.md` section 2). The word `$1E02/$1E03` is the parameter / pan pair of the request.

| frame | s | kind | id | `$1E00` | `$1E02` | `$1E03` | source |
|---|---|---|---|---|---|---|---|
| 24 | 0.40 | music | 0x1B | 1 | 0x13 | 0x8F | vm_op |
| 84 | 1.40 | sfx | 0x8B | 2 | 0x0F | 0x88 | engine |
| 84 | 1.40 | sfx | 0x8B | 2 | 0x0F | 0x88 | engine |
| 1019 | 16.96 | sfx | 0x04 | 2 | 0x00 | 0xAA | engine |
| 1039 | 17.29 | sfx | 0x33 | 2 | 0x00 | 0x88 | vm_op |
| 1749 | 29.10 | music | 0x08 | 1 | 0x1B | 0x8F | vm_op |
| 1864 | 31.02 | raw | 0x80 | 128 | 0x00 | 0x00 | vm_op |
| 2059 | 34.26 | music | 0x04 | 1 | 0x04 | 0xFF | vm_op |
| 2699 | 44.91 | music | 0x29 | 1 | 0x1C | 0x8F | vm_op |
| 3549 | 59.05 | music | 0x33 | 1 | 0x13 | 0x8F | vm_op |
| 3820 | 63.56 | music | 0x0C | 1 | 0x06 | 0xFF | vm_op |

Music ids requested by the scene: 0x1B (start), 0x08, 0x04, 0x29, 0x33, 0x0C (fight). Effect ids: 0x8B twice in frame 84 (not from a VM command: one request per running hero, ten frames after the gather started), 0x04 in frame 1019 (not from a VM command: the same frame as the start of the girl's swing animation), 0x33 in frame 1039 (command in event 0x78E). Raw command 0x80 in frame 1864 (event 0x748).

## 9. Camera, fades, flash, control lock

- Camera: scrolls with the controlled hero when the hero leaves the follow window (frames 50-68, 2 px per frame, (152, 392) -> (152, 354)); SCREEN 8 pans to put the controlled hero at the screen centre (frames 104-131, (152, 354) -> (152, 298), 28 frames; frames 2334-2357, (152, 298) -> (168, 250), 24 frames); the loader sets (152, 312) for map 246 at frame 3611 [V].
- Fades: fade-in frames 1-15 (brightness 0 -> 15, +1 per frame); fade-out frames 3555-3611 (15 -> 0, one level per 4 frames); fade-in frames 3612-3626 [V].
- Flash: SCREEN 0 at frame 1039, SCREEN 1 at frame 1044: the colour add toggles every frame in between (5 frames) [V].
- Control: the pad binding of the controlling hero has bit 7 set from frame 0 (set when the entry event starts), `$F1` bit 7 is set at frame 19 (FREEZE) and both are cleared by END at frame 3825 [V]. The VM state `$D0` is non-zero from frame 0 to 3825.

## 10. The Dark Lich: spawn, freeze, release

- Spawn: the loader of map 246 (frame 3611) finds the boss record (flag 0x4E = 6) and calls the boss spawner `$C2:0040`: object slot 3, id 0x79, flags 0x9C01, engine position (288, 336), phase 0. At the first tick (frame 3612) it enters phase 3, state 2 and moves to y = 335 (then bobs 1 px up and down) [V].
- It is visible as soon as the fade-in starts (frame 3612) and ticks at frames 3612, 3617, 3622, 3627 (every 5 frames, `$56` = 0) [V].
- Freeze: the script raises event flag 0xFF at frame 3630 (`$CFFF` = 1). `$C2:0E05` skips the tick of every boss-engine object whose phase `obj+0x94` is not 0 while `$CFFF` bit 0 is set, so the Lich does not act during the three text blocks [C; V: its age counter `obj+0x96` stays at 3 for frames 3627-3820].
- Release: the script lowers the flag at frame 3820 (63.562 s) in the same VM step that jumps to event 0x70C (music 0x0C). **The first Lich tick after the release is frame 3822 (63.595 s)**; END at frame 3825 (63.645 s) clears `$F1` and the pad lock: the hero input handler is live again from the next frame. When END runs the Lich has ticked once since the release (age 3 -> 4 at frame 3822) [V].
- First action [V, one run, the action choice is random]: the Lich's action timer (`obj+0xAD`, ticks since the spawn, threshold 49 = `docs/dark-lich.md` section 2) was 4 at the release; the stand state 2 ended at frame 3982 (timer 36, state 0 follows), the timer reached 49 at frame 4047 and the first attack, state 0x16 (one of the projectile attacks of `docs/dark-lich.md` section 4), started at frame 4052 = 232 frames (3.86 s) after the release and 227 frames after END. The harness keeps the party motionless for 360 frames after END to see this (`lich.after_release_state_changes` in the JSON).
- The heroes are not hit by anything during the scene (no hits were injected); weapon hits are disabled in the harness.

## 11. Dependencies on the party and on the save state

The command sequence (186 commands, all addresses) and every movement (positions, frames) are identical for five save states (three distinct equipment arrangements, different starting maps) and for all three controlled heroes [V]. Only these times move:

| controlled hero | total frames | END at frame | camera re-centre length at 0x4E1+0324 (frames) |
|---|---|---|---|
| slot 0 | 3825 | 3825 | 24 |
| slot 1 | 3820 | 3820 | 16 |
| slot 2 | 3810 | 3810 | 8 |

| weapon type of the girl | swing animation (frames) | total frames | END at frame |
|---|---|---|---|
| 0 (glove) | 20 | 3830 | 3830 |
| 1 (sword) | 15 | 3825 | 3825 |
| 2 (axe) | 20 | 3830 | 3830 |
| 3 (spear) | 15 | 3825 | 3825 |
| 4 (whip) | 20 | 3830 | 3830 |
| 5 (bow) | 35 | 3845 | 3845 |
| 6 (boomerang) | 30 | 3840 | 3840 |
| 7 (javelin) | 25 | 3835 | 3835 |

- The camera pan at 0x4E1+0324 (`SCREEN 8`) lasts as long as it takes to bring the controlled hero to the screen centre: 24, 16 or 8 frames for the boy, the girl and the sprite as controlled hero (the hero positions at that point are (296, 378), (292, 394), (280, 410): the camera moves 2 px per frame per axis, so the length is the larger axis distance / 2).
- The girl's `ACTOR_ANIM` with animation 0 (frame 1019) is her weapon swing: its length depends on her weapon type (15, 20, 25, 30 or 35 frames). Everything after frame 1019 shifts by the difference to the reference (15 frames, sword): +5, +10, +15, +20 [V: run for each weapon type, `E1E3` = type * 9 + 7].
- The scene requires `$CF4E` = 4 at entry for both NPCs to exist; with 5 the NPC 0xBF does not exist (its commands would address an empty slot, not tested); with a value of 6 or more the entry event does nothing.

## 12. Not decoded / open questions

- The identities (names) of NPC 0xAC and 0xBF, and of the speaker of each text block; the text itself is deliberately not recorded.
- The meaning of flag 0xF8 (raised and lowered around two stretches of dialog), of the helper object in slot 6 of map 246, of raw sound command 0x80, and of the parameters `$1E02/$1E03` of the music requests.
- Which exit of map 251 starts transition 340, and what the entry-list event 0x429 does for flag values of 8 and above (a second scene in the same rooms).
- The hero animation codes 0x8C, 0xA9 and 0x80 were identified only by id and measured length (20, 40 frames and held); their sprite frames were not decoded.
- Text speed: whether the text engine speed depends on a configuration setting (the harness uses the value in the save state), and the minimum time a human needs per block.
- Real-hardware timing under slowdown; the fade-out before frame 0 (the previous map's exit transition) and the loader's own duration are not part of the timeline.

# Event (cutscene) engine of Secret of Mana (USA)

Tags: **[V]** executed: the original 65816 code was run frame by frame in `tools/event_vm.py` (whole game frame `$C0:B08C`, map loader, text engine, actors) from a save state and the effect was measured. **[C]** read from the disassembly, not executed. Everything not determined is listed in section 12 without values. Sections 13 and 14 were added with the runs of the Mana Beast intro and ending (`docs/cutscene-mana-beast-intro.md`, `docs/cutscene-ending.md`, `tools/event_runs.py`). Addressing as in `docs/dark-lich.md`: `$Cx:xxxx` = ROM offset `((x-0xC0)<<16)|xxxx`, `$01:xxxx` is the mirror of `$C1:xxxx`, `$02:xxxx` of `$C2:xxxx`. WRAM addresses are `$7E:xxxx`; the direct page is 0, so `$D0` is `$7E:00D0`. Object fields are offsets in the 0x200-byte record at `$7E:E000 + slot*0x200` (slots 0-2 = boy, girl, sprite; slots 3.. = monsters, NPCs, bosses). No script text and no ROM bytes are reproduced here: dialog is recorded only as address and length.

## 1. Time base

| clock | rate | what runs on it |
|---|---|---|
| frame (one call of `$C0:B08C`, `$56` = 0..4) | 60.0988 Hz | actor movement and animation (`$C0:D5C0`, `$C0:D1FE`), camera scroll, the fade state machine `$C0:8B5E`, pad polling |
| **VM step** | **60.0988 / 5 = 12.02 Hz** (5 frames = 83.2 ms) | the event interpreter `$C1:E8D3` |
| NMI (once per frame, after the body) | 60.0988 Hz | the text engine `$C0:0006` (called from `$C0:C1E7` when `$1D04` bit 2 is set), `$F4` frame counter |

- The frame body starts with `LDA $D0 / BEQ / LDA $56 / CMP #3 / BNE / JSL $01:E8C7`: the VM is stepped only while `$D0` != 0 and only in the frame with `$56` == 3 (`$C0:B092-B09C`) [C]. Measured: every VM command of a 3,825-frame run executes in a frame with `(t - t_load) mod 5 == 3` (the first `$56` == 0 frame after a map load is frame 1 of that map) [V].
- One VM step runs commands until one of them yields (a wait state, a text block, a map change): several commands execute in the same frame, e.g. four ACTOR_WALK and a WAIT_IDLE at frame 134 of the Dark Lich cutscene [V].
- `WAIT n` (command 0x28) lasts exactly `n` VM steps = `5n` frames = `n/12.02` s: the command stores `$4F = n` and state 0x82 decrements it once per step; when it reaches 0 the next command runs in the same step [C; V: 19 waits in the Dark Lich run: `WAIT 2` = 10 frames, `WAIT 4` = 20, `WAIT 8` = 40, `WAIT 16` = 80, `WAIT 32` = 160].
- Everything an actor does between commands is on the frame clock: ACTOR_WALK counts frames, not steps (section 7).

## 2. Event ids and where the scripts live

`$C1:E77B` (A = id, called by `JSL $01:E76D` or `JSL $01:8000`) dispatches on the id [C]:

| id | meaning |
|---|---|
| 0x000-0x3FF | script in bank `$C9`; word pointer table at `$C9:0000`, entry `id`; the script ends where the next entry starts |
| 0x400-0x7FF | script in bank `$CA`; word pointer table at `$CA:0000`, entry `id - 0x400` |
| 0x800-0xBFF | **map transition** number `id & 0x3FF`: entry of the 4-byte table `$C8:3000`: bits 0-8 of the word = map id (`$DC`), byte 1 >> 1 = start tile X (`$DE`), word at +2 = `$DF` (low byte >> 1 = start tile Y); sets `$010E` = number, `$FF` = 0x40 (map change pending), `$E8` = 0 |
| 0xC00-0xCFF | warp inside the map (table `$C6:7A80`, sets camera origin `$FA/$FC`, `$E8` = 4) |
| 0xD00-0xD7F | position from the 4-byte table `$C6:7C80` (word -> `$FA/$FC` origin, second word -> `$0110`), `JSL $00:BC01` |
| 0xD80 and above | nothing |

The id tables were checked over all ids: **2,047 non-empty events** decode to command boundaries that coincide with the next table entry in every case with the lengths of section 6 (0 misaligned) [V, static].

A call or goto into an event while another one runs is ignored unless the VM is in the subroutine state (`$D0` = 0xFF, set by CALL) or was just reset by GOTO (`STZ $D0`) [C].

## 3. State bytes

| address | meaning |
|---|---|
| `$D0` | VM state: 0 idle, 1 running, 0x80 wait for `$4E` = 0 (party gather), 0x81 text block in progress (wait for `$48` = 0), 0x82 timed wait (`$4F`), 0x83 wait for a button, 0x84 resume at once, 0x85 wait until no actor is busy, 0x86 wait for the camera re-centre (`$E2` bit 3), 0x87-0x8F resume at once, 0xFF a CALL is being started [C; V for 0x80, 0x81, 0x82, 0x83, 0x85, 0x86] |
| `$D1/$D2/$D3` | script pointer (offset, bank `$C9`/`$CA`) |
| `$D6/$D7/$D8` | return pointer of the one-level CALL |
| `$D4` | the **current actor**: object offset (`slot * 0x200`) of the hero the player controls; command arg 0 means this object |
| `$3A` | the current NPC (the object that was talked to or touched); arg >= 0x80 means this object |
| `$D9/$DA/$DB` | pad binding of pads 1-3: bit k set = hero k is controlled by that pad; **bit 7 set = pad inactive**. Starting an event from idle sets bit 7 of the controlling pad's byte; END clears bit 7 of all three [C; V] |
| `$F1` | bit 7: the hero input handler `$C0:B69C` returns without reading the pad; set by FREEZE, cleared by END [C; V] |
| `$4E` | party gather request (0x80), cleared by the party AI when the other heroes have reached the actor |
| `$4F` | step counter of the timed wait |
| `$48` | text engine busy flag (set to 1 when a text block is handed over, cleared by the engine) |
| `$CC/$CD/$CE` | latched button presses of pads 1-3 (A 0x80, X 0x40, L 0x20, R 0x10, B 0x08, Y 0x04, Select 0x02, Start 0x01); the VM waits for `$CC,X & 0xFC` |
| `$7E:CF00 + n` | event flags: one byte each, used as 4-bit counters by FLAG_INC/DEC/SET (the high nibble is kept); read as whole bytes by the range tests |
| `$CF4E` | story counter of the Dark Lich rooms (section 5 and `docs/cutscene-dark-lich.md`) |
| `$CFFF` bit 0 | **boss freeze**: while set, boss-engine objects whose phase `obj+0x94` is not 0 do not tick (`$C2:0E05`); the Dark Lich cutscene raises and clears it with FLAG_INC/FLAG_DEC 0xFF [C; V: Lich AI age counter stops and restarts with it] |
| `$E2` | screen effect bits (see 9) |
| `$1D00-$1D05` | text engine state; `$1D01-$1D03` = script pointer the engine returns to |

## 4. How an event is started

- **Map entry event** [C; V for maps 245 and 246]: after a map is loaded, `$C0:BEAA` (called from the loader `$C0:B03F`) starts the first word of the map's event list: `$C8:4000 + 2*map` points into `$C8:0000` to the list; the event is `word & 0xFFF`. It runs only when bit 2 of the map header byte `$B8` is set, `$E8` bit 7 is clear and `$E8 & 3` != 3.
- **Trigger tiles** [C, not traced to the tile data]: `$C0:B63A` reads the per-hero byte `obj+0x4B` (trigger id of the tile under the hero) and starts list entry `2 * (id - $4D) + (($B8 & 4) >> 1)` of the same list, `$4D = 0xC0 - ($B8 & 3)`; for maps 245/246 entry 1 is event 0x429.
- **NPC contact or talk**: `$C0:B9AA` (a hero acts on the NPC) and `$C0:3F94-3FB8` (an effect applied to an object whose `$E1FB` has bit 4 set; not traced further) start the event `obj+0x3E & 0xFFF` of the NPC (the word at offset +6 of its map record); `$3A` = the NPC. `$C0:D449-D475` starts the event stored in `obj+0x48` of a hero (set by tile code) [C].
- **Boss death**: `$C2:0C11` loads `obj+0x72` (the map record word at +6, WRAM `$C80E`, low 12 bits; 0x042D for the Dark Lich of maps 245/246, **0x042F for the Mana Beast of map 253**) when the boss object ends (`docs/mana-beast.md` section 8) [C; V for 0x042F: the VM's first step is 3 frames after the removal, `docs/cutscene-ending.md` section 2].
- From another script: GOTO (0x10-0x17), CALL (0x20-0x27), MAP_CHANGE (0x18-0x1B).
- Scripts that start from idle (`$D0` = 0 in `$C1:E77B`) also run `$C1:E88D`: clear `$CC-$CE`, set bit 7 of the pad byte of the controlling hero [C; V].

## 5. Map object records and spawn rules

Each map has a header of 8 bytes at `$C8:0000 + word($C8:7000 + 2*map)` followed by 8-byte object records up to the next map's header (count = `($C8:7000[map+1] - ptr - 8) / 8`) [C]. Records are copied to WRAM `$C808 + 16*n` (offsets +8..+15), `$C800+16n` = 1 (present) and +7 flags (`$C0:DD55`). Record layout [C; V for maps 245/246]:

| byte | meaning |
|---|---|
| +0 | flag index `f` (event flag `$CF00 + f`) |
| +1 | bits 4-7 = minimum, bits 0-3 = maximum of the flag value for the object to exist |
| +2 | X in tiles (bits 0-6) |
| +3 | Y in tiles (bits 0-6) |
| +4 | bits 7-6 facing (0 up, 1 down, 2 left, 3 right), bits 5-4 layer, bit 3 -> `obj+0x0B` bit 7 |
| +5 | object id: 0x00-0x56 monsters, 0x57-0x7F bosses, >= 0x80 NPC kinds |
| +6/+7 | event word (low 12 bits = event id on contact; 0x442D = the post-fight event of the Lich) |

- Ordinary records spawn with `$C0:DE3B` at position `x = 16*tile + 4`, `y = 16*tile + 4` (the spawner computes `(4 * tile + 1) * 4`) when the test `$C2:C757` passes: `min <= $CF00[f] <= max` on the **whole flag byte** [C; V: NPC 0xAC appears for flag values 0-5, NPC 0xBF for 0-4].
- Boss records (ids 0x57-0x7F) are spawned by `$C2:0040` (through `$C0:DE02`) when `min <= ($CF00[f] & 15) <= max`, with the spawn position `(16 * tileX, 16 * tileY)` passed in `$0300/$0302`; the Dark Lich record (flag 0x4E, min = max = 6) therefore exists only while `$CF4E` = 6 [C; V].
- Removal: REFRESH_OBJECTS (0x09) re-tests every spawned record with `$C2:C757` and removes those that fail [V: NPC 0xBF disappears in the frame of the command after FLAG_INC 0x4E raised the flag to 5].

## 6. Command table

Length in bytes including the opcode. Operands are read as `a` (byte after the opcode) and `b`, `c`, ... Any byte >= 0x50 is text, see section 8. "actor" arguments: 0 = `$D4`, 1-0x7F = object slot `arg - 1` (1-3 heroes, 4 = slot 3, 5 = slot 4, ...), >= 0x80 = `$3A` [C; V for 4 and 5].

| op | name | len | tag | effect |
|---|---|---|---|---|
| 00 | END | 1 | V | clear `$F1`, `$D0`, `$4E`, `$3A/$3B`, `$CC-$CE`, bit 7 of `$D9-$DB`: the world and the pads are released |
| 01 | NOP | 1 | C | advance one byte |
| 02 | RETURN | 1 | V | `$D1-$D3 = $D6-$D8` (the CALL return pointer) |
| 03 | GATHER | 1 | V | `$4E = 0x80`, state 0x80; every hero other than `$D4` is stopped first (`$C1:CA6C`); the party AI then runs them to the actor (measured: 3 px per frame, animation code 1 then 2, sound effect 0x8B twice) and clears `$4E` |
| 04, 05 | TOGGLE_HERO_VIS | 1 | V | toggle bit 7 of `obj+0x0E` of the three heroes (bit 7 set = hidden) [V: `obj+0x0E` 0x00 <-> 0x80 in the ending] |
| 06 | FREEZE | 1 | V | set bit 7 of `$F1` (hero input is ignored), wait until no hero has a state flag `obj+0x60` (`$C2:B053`), zero the heroes velocities and `obj+0x1D` |
| 07 | UNFREEZE | 1 | C | clear bit 7 of `$F1` |
| 08 | WAIT_IDLE | 1 | V | state 0x85: wait until every active object (heroes included) has `obj+0x42` = 0 |
| 09 | REFRESH_OBJECTS | 1 | V (removal and respawn) | for object slots 3..: remove the object if its record fails the range test, then scan the records again (`$C0:E00C`) so that newly valid records appear |
| 0A | CAFF_SET | 1 | C | `JSL $C0:CAFF` with carry set (not decoded) |
| 0B, 0C | SAVE_TRANS, CLEAR_TRANS | 1 | C | `$0108 = $010E` / `$0108 = 0` |
| 0D | MAP_FROM_0108 | 1 | C | map change with event number `0x800 + $0108` |
| 0E, 0F | OBJ_FX | 1 | C | `JSL $C0:004B` / `$C0:004E` for the current NPC (not decoded) |
| 10-17 | GOTO_EVENT | 2 | V | continue with event `(op & 7) * 256 + a`; the old position is dropped |
| 18-1B | MAP_CHANGE | 2 | V | event `0x800 + (op & 3) * 256 + a` = map transition; the script keeps running in the new map once the loader is done (the VM idles while `$FF` is non-zero) |
| 1C | WARP | 2 | C | event `0xC00 + a`, then END |
| 1D | MAP_CHANGE_D | 2 | V | event `0xD00 + (a & 0x3F)`; bit 6 of `a` sets bit 0 of `$E3`; starts the fade-out and sets `$FF` = 0x81: the game switches to the world-map mode (section 13.3) |
| 1E | HERO_CMD | 2 | C | `JSL $C0:0051`, A = a, X = `$D4` (not decoded) |
| 1F | PARTY_CMD | 2 | C (0x11: V up to the jump) | by `a`: 0-2 hero init, 3-4 set `$FA/$FC`, 6 `JSL $C0:000C`, 7 `JML $00:8004`, 8-0xB `JSL $C0:005A`, 0xC `JSL $C0:0066`, 0x10 `JSL $C0:0072`, other (**0x11**: the ending) `JML $C0:0075` -> `$C1:4CFA`, a software restart through the reset path (section 13.5) |
| 20-27 | CALL_EVENT | 2 | V | `$D6-$D8` = pointer of the next command, then event `(op & 7) * 256 + a`; RETURN comes back; one level only |
| 28 | WAIT | 2 | V | `a` = 0: clear the latch of the controlling pad and wait for A, X, L, R, B or Y (state 0x83); `a` = n: wait n VM steps (state 0x82) |
| 29 | FLAG_INC | 2 | V | `$CF00[a]` low nibble + 1, capped at 15 (a = 0: toggles `$ED` bit 7 and clears `$CC-$CE`, not executed) |
| 2A | FLAG_DEC | 2 | V | low nibble - 1, floored at 0 |
| 2B | ACTOR_CLONE | 2 | V (`obj+0` and facing) | object slot `a & 15` becomes active (`obj+0` = 1) at the position of `$3A`, with `obj+0x0B/0x4C/0x8E` taken from `$D4` and the facing reversed [V: slot 1 active again in the frame of the command, facing down] |
| 2C | ACTOR_DELETE | 2 | V | object slot `a & 15`: `obj+0 = 0x80`, its pad binding is released [V: `obj+0` = 0x80 in the frame of the command] |
| 2D | SCREEN | 2 or 4 | V (0, 1, 2, 3, 6, 7, 8), C (rest) | see sections 9 and 13.1; length 4 for `a` = 5, 6 and 0x80-0x8F (the word at +2 goes to `$010C`) |
| 2E | ACTOR_FX | 2 | C | `JSL $C0:0048`, Y = a, for the current NPC (not decoded) |
| 2F | HERO_REFILL | 2 | V (executed), C (effect) | bit 7 of `a` clear and bit 6 clear: `obj+0x182 = obj+0x184` (HP = max); bit 7 set: `obj+0x186 = obj+0x187` (MP = max); bit 6 set (and 7 clear): `JSL $C1:80BA` with A = 0xFF for the selected heroes (a status reset, not decoded); hero `a & 0x3F` (0 = `$D4`, 1-3, 4 or more = all three) |
| 30 | FLAG_SET | 3 | V | low nibble of `$CF00[a]` = b [V: the flag byte changed from 2 to 15, from 1 to 0 and so on; the high nibble is kept] |
| 31 | ACTOR_ANIM | 3 | V | actor a: stop, `obj+0x1C = 0x40`, `obj+0x11 = b` (animation code), `obj+0x30 = 0xFF`, `obj+0x42 = 1` (busy until the animation clears `obj+0x1C`) |
| 32 | ACTOR_WALK | 3 | V | actor a: `obj+0x0A = b & 0x3F` frames, direction `b >> 6` (0 up, 1 down, 2 right, 3 left) at 2 px per frame (`obj+0x06/07` = 0x02 or 0x82), facing set, `obj+0x42 = 1`; `b & 0x3F` = 0 only turns the actor (and clears busy at once) |
| 33 | SET_0600 | 3 | C | `$0600 = b * 256 + a` |
| 34 | ACTOR_ANIM_LOOP | 3 | V | like 31 but `obj+0x1C = 0x30` and `obj+0x42 = 0`: the pose stays until another command changes it |
| 35 | CALL_E326 | 1 | V (executed) | `JSR $C1:E326` (object init; `$C1:E339` returns at once when flag 0 is 0) |
| 36, 37 | OBJ_CMD | 3 | C | `JSL $C0:0057` with A = word at +1 (not decoded) |
| 38 | IF_ACTOR | 2 | C | slot of `$D4` == a: continue; else skip the next 2-byte command |
| 39 | SET_FIELD_BYTE | 4 | V (executed) | actor a: `obj[0x100 + b] = c` (the ending's party reset writes 0 to `obj+0x190/0x191`) |
| 3A | SET_WORD_40 | 4 | C | actor a: word `obj+0x40` = bytes 2-3 |
| 3B | IF_PARTY | 2 | C | test of the pad bindings `$D9-$DB` selected by a; continue or skip the next 2-byte command (exact test not decoded) |
| 3C | IF_PARTY_SIZE | 2 | C | number of leading non-zero bindings == a: continue, else skip the next 2-byte command |
| 3D-3F, 44-47, 4F | STALL | 1 | C | the handler is a bare RTS, the VM stays here every step |
| 40 | SOUND | 5 | V | `$1E00 = a`, `$1E01 = b`, `$1E02/03 = word at +3`, `JSL $C3:0004`: cmd 1 = music `$1E01`, cmd 2 = sound effect `$1E01`, other = raw command (`docs/audio.md`) |
| 41 | CAFF_CLEAR | 5 | C | `JSL $C0:CAFF` with carry clear (not decoded) |
| 42 | IF_FLAG_RANGE | 3 | V | flag byte `$CF00[a]`; lo = b >> 4, hi = b & 15; if lo <= value <= hi the next 2-byte command runs, else it is skipped |
| 43 | FLAG_OP_WAIT | 3 | C | nibble operation selected by bits 5-7 of a (replace, or, xor) on a flag given by byte 2; repeats while the nibble is 0 |
| 48 | FLAG_OP_WAIT2 | 4 | C | like 43 with the flag index in byte 3 |
| 49-4E | IF_FIELD | 4 | C | compare an object field with a value (equal, ordering, and, or, xor), continue or skip the next 2-byte command |
| 50-5F | TEXT | var | V | text block, section 8 |

Commands marked C and not described in detail were not executed by any run in this repository.

## 7. Actors

- Positions are the object words `obj+2` (X) and `obj+4` (Y) in map pixels; velocities are sign-magnitude bytes `obj+6` (X) and `obj+7` (Y): `0x02` = +2 px per frame, `0x82` = -2 px per frame; facing `obj+0x10`: 0 up, 1 down, 2 right, 0x82 left; animation/state code `obj+0x11`: 0 standing, 1 walking at less than 3 px per frame, 2 walking at 3 px or more (running), 3 standing ready (weapon gauge empty), 0x80 and above scripted poses [V; `docs/hero-movement.md`].
- ACTOR_WALK moves at 2 px per frame regardless of the object, one frame per count: 40 frames = 80 px = 0.666 s. The counter `obj+0x0A` decrements every frame and `obj+0x42` is cleared when it reaches 0 [V: 13 walks with a count above 0 measured, e.g. count 40 gives 40 frames and 80 px for the hero, 16 gives 32 px, 2 gives 4 px].
- The speed of an NPC can differ from 2 px per frame: an NPC pushed right with a count of 32 moved 2 px in each of the first 3 frames and 1 px in each of the other 29 (35 px in 32 frames); its velocity byte changed from 2 to 1 by itself in frame 3 (its walk animation or the movement code, not determined) [V].
- ACTOR_ANIM plays animation code b of the actor in state 0x40: the code is looked up in the animation table of the object. For the heroes code 0 is the swing of the equipped weapon; the number of frames it takes depends on the weapon type (`docs/cutscene-dark-lich.md` section 11) [V].
- The camera follows a hero only when its screen position leaves the window x in [0x38, 0xC8), y in [0x48, 0xB0) (`$C0:D8F2-D95F`); it then scrolls by the hero's own step (2 px per frame in the measured case) [C; V: scroll started in the frame in which the hero reached screen y = 70 < 72].

## 8. Text blocks

- Any command byte >= 0x50 starts a text block: `$C1:F27A` stores the VM pointer in `$1D01-$1D03`, sets `$48 = 1`, `$D0 = 0x81`. The text engine (`$C0:0006`, once per NMI) consumes bytes: codes 0x50-0x5F are engine commands (0x57 and 0x59 take one argument byte), anything >= 0x60 is a character; **the code 0x7D opens a credits segment that runs through the first 0x7E and may contain bytes below 0x50** (the staff roll of the ending); the first other byte < 0x50 ends the block and is executed by the VM as a command [C; V: 38 of 38 blocks of the ending and 32 of 32 of the Mana Beast intro end where the engine's pointer is, with this rule; a block can chain several segments and ordinary text].
- A page break is encoded in the script as WAIT 0 (wait for a button) followed by another text block; short pauses inside speech are `WAIT n`.
- Block extents: the static rule "bytes >= 0x50 up to the first byte < 0x50, with 0x57 and 0x59 followed by one argument byte and credits segments 0x7D...0x7E skipped as a whole" gave the same end as the pointer the engine left in `$1D01` for all 48 blocks of the Dark Lich cutscene, all 32 of the Mana Beast intro and all 38 of the ending [V]. The first version of the rule (without the credits segments) mis-decoded the 2,834-byte event 0x4FD, which earlier appeared to contain "stall" opcodes; `tools/event_vm.py` was corrected.
- There are no message ids: the text is inline in the script. This repository records a block as `bank:offset` and length in bytes, never its content.
- While a block is being shown `$CFFF` is not touched by the engine; the boss freeze of the Dark Lich scene is an explicit FLAG_INC 0xFF around the dialog [V: the flag changed only at the two FLAG commands].
- How long a block takes depends on the text engine (characters per frame, possibly a configuration setting that was not located) and on the player: in the harness the A button is tapped in the first frame the VM waits for a button, so the durations in this repository are the minimum.

## 9. Screen, camera, map change, sound

- `$E2` bits [C; V for 0, 2, 3]: bit 0 brightness fade (`$E6` current, `$E7` target, `$E4` step timer reload `$E5`; the display register `$2100` follows `$E6`), bit 1 mosaic (`$1057`), bit 2 flash, bit 3 camera re-centre, bit 4 timed colour effect (`$105A`).
- SCREEN a = 0: `$1057 = 0`, `$1058 = $E6`, bit 2 of `$E2` set: the fixed-colour add is switched on and off every other frame (flash). a = 1: `$1057 = 1`: the next frame clears the flash. The flash is therefore as long as the time between the two commands plus one frame [V: 0-1 pair = 5 frames].
- SCREEN a = 8: bit 3 of `$E2` set, state 0x86: the camera scrolls 2 px per frame per axis until the hero `$D4` is at screen x 0x7F-0x81 and y 0x7F-0x81 (`$C0:8C00-8C50`), then the VM goes on [V: 56 px along y took 28 frames; 16 px along x with 48 px along y took 24 frames; the length is the larger axis distance / 2 and depends on the actor]. a = 2/3/4: `$49` = 0xE0 / 0x60 / 0; 5, 6, 0x80-0x8F: palette fade through `$C2:C806/C820` with the word at +2; 7: stop [C, not executed].
- Map change (MAP_CHANGE or any 0x800 id) [V; this is the case of exit code 0, see section 13.2 for the others]: `$FF = 0x40` at the command; the VM idles; brightness steps down 15 -> 0 one level per 4 frames (57 frames after the command), then the loader runs in one frame (`$C0:87C4, BC9B, BC0B, E9F8, BEAA` of `$C0:B03F`), the new map's heroes are placed on the start tile, brightness steps up 0 -> 15 one level per frame, and the VM resumes at the first step after the fade-in. The DMA clears of the loader that write the WRAM port are required (a harness that skips them leaves stale data in `$0E60-$0E68`, which the boss engine reads as slot flags).
- Hero start position on a map: `x = 16 * tileX + 8`, `y = 16 * tileY + 10`, all three heroes on the same pixel, facing up (0) [V for the transitions 340 and 47].
- Sound: SOUND commands (0x40) are mostly reached through short canned events in bank `$CA` that contain one SOUND and a RETURN (events 0x733, 0x748, 0x78E, 0x7C4, 0x7D7, 0x7D8, 0x7DA, 0x70C in the Dark Lich scene); music `$1E01` ids and effect ids are listed in `docs/cutscene-dark-lich.md`. Effects can also come from the actors' animation scripts (the hero swing requests effect 0x04, the party gather effect 0x8B twice) [V].

## 10. Tool

`tools/event_vm.py` (needs your ROM and a save state with the three heroes on any map):

```
python3 tools/event_vm.py ROM table                                  # the table of section 6
python3 tools/event_vm.py ROM decode 4E1 428                         # static listing, text blocks as lengths only
python3 tools/event_vm.py ROM STATE run 340 4E=4 leader=0            # send the party through transition 340 and log every VM command
python3 tools/event_vm.py ROM STATE dark-lich out.json leader=0 [variants=1] [md=1]
python3 tools/event_runs.py ROM STATE intro  out.json leader=0 [after=900] [weapons=A,B,C]   # Mana Beast intro (docs/cutscene-mana-beast-intro.md)
python3 tools/event_runs.py ROM STATE ending out.json leader=0 [frames=150000]               # death sequence and ending (docs/cutscene-ending.md)
python3 tools/event_runs.py ROM decode2 4FD                                                   # static listing with credits segments
```

`tools/event_runs.py` adds to the harness: 12 object slots, event flag changes, screen-effect bytes, palette fade runs, the world-map mode loop (section 13.3), hooks for the restart routine, snapshots (`snap=`, `resume=`), and a report builder (`report RAW.pkl OUT.json`, `md OUT.json`) that writes the same schema as `data/cutscene_dark_lich.json` plus `palette_fades`, `flags`, `boss`, `world_mode_intervals`.

What the harness does: `World` (library) runs the real frame body `$C0:B08C` with `$56` = frame mod 5, adds the two NMI duties that change game state (frame counter and text engine), answers the vblank/pad registers, executes DMA to the WRAM port, and runs the loader subroutines of `$C0:B03F` when the game jumps there (`$C0:B03F` itself resets the stack, so it is intercepted). The PPU, VRAM/CGRAM/OAM DMA, the sound CPU and everything on the screen are not emulated; sound requests are recorded (`$1E00-$1E03`) instead of being sent. The heroes are those of the state; `leader=N` sets `$D4`, `$D9` and `obj+0x2C` to make hero N the controlled one. The event flags in the state are the ones of the save; `FLAG=VALUE` arguments overwrite them before the transition. The A button is tapped for one frame whenever the VM enters state 0x83.

Validation: (1) the command lengths are consistent with all 2,047 events (section 2); (2) the text block rule matches the engine's own pointer in 48 of 48 blocks; (3) the Dark Lich cutscene was run from five save states (three equipment arrangements) and with all three heroes as controlled hero: the VM command sequence and every movement are identical; only two durations move (the length of the second camera re-centre with the controlled hero, and the length of the girl's weapon-swing animation with her weapon type) [V]; (4) the object positions at the entry of maps 245 and 246 agree with the map record formula and the loader's start tiles.

## 11. Cross-check with the record formulas

| item | formula | measured |
|---|---|---|
| NPC record at tile (18, 24) | `16 * tile + 4` | (292, 388) |
| NPC record at tile (17, 25) | `16 * tile + 4` | (276, 404) |
| boss record at tile (18, 21) | `16 * tile` | (288, 336) |
| party start tile (17, 31) | `(16 * 17 + 8, 16 * 31 + 10)` | (280, 506) |
| party start tile (17, 26) | `(16 * 17 + 8, 16 * 26 + 10)` | (280, 426) |

## 12. Open questions

- Commands executed by no run in this repository (marked C in section 6): 01, 07, 0A-0F, 1C, 1E, 2E, 33, 36-38, 3A-3C, 41, 43, 48-4E. Their lengths agree with the event data (section 2) but their effects come from reading only; the ones marked "not decoded" call routines in bank `$C0` that were not read. (The ops 0x3D-0x3F, 0x44-0x47 and 0x4F, formerly listed as stalls in event 0x4FD, are not commands: they were bytes of the staff-roll text, section 8.)
- The exact test of IF_PARTY (0x3B), IF_FIELD (0x49-0x4E), the meaning of flag 0xF8 (raised and lowered around two stretches of dialog in the Dark Lich scene), of flag 0xF7 (staff-roll counter) and of the helper objects that appear next to the Dark Lich and the Mana Beast.
- Text engine: the meaning of the commands 0x50-0x5F (only the argument counts of 0x57 and 0x59 were needed) and of the one-byte blocks 0x51, 0x52, 0x7F, the speed setting, the window opening times.
- Which trigger tile starts list entry 1 of a map (the trigger id to tile mapping was not traced), which exit of map 251 starts map transition 340 (its event list entry 1 is the map change), and who refers to event 0x426.
- The visual effect of `$49` (SCREEN 2/3), what the mode-7 loop of the world-map mode shows, the meaning of `$E0` bits 5-7 and of the exit codes 5 and above (section 13).
- Real-hardware timing under slowdown (frames that take longer than 1/60.0988 s).

## 13. Added by the Mana Beast intro and ending runs

### 13.1 SCREEN commands [V for values, C for the routines]

- `SCREEN 2` sets `$49` = 0xE0, `SCREEN 3` sets `$49` = 0x60, `SCREEN 4` sets it to 0 (`$C1:ED61-ED7B`). The frame body (`$C0:B518-B565`) clears `$5E` and `$5F` every frame and, while `$49` is non-zero, writes (frame counter `$F4` & 1) * 6 into `$5F` (bit 7 of `$49` set: 0xE0) or `$5E` (bit 7 clear: 0x60); the low 5 bits of `$49` are a countdown that does not exist for these two values (they are 0), so the effect stays until `SCREEN 4` or until a map load clears `$49` [C; V: the byte values and that the loader clears it]. It is a jitter of the screen on alternate frames; the register it ends up in was not traced.
- `SCREEN 6` (length 4, word `w`): `$2A` = 0x60, `$010C` = `w`, `$010A` = 0 after `JSL $C2:C806` (copies the palette `$0600-$07FF` to `$BE00`); `SCREEN 5` is the same with `$2A` = 0x20. Every fifth frame (the frame with `$56` = 4, `$C0:B0E2`) `JSL $C2:C820` rebuilds `$BE00` from `$0600` for the entries 16-255 (entries 0-15 are copied unchanged): add mode (bit 15 of `w` clear) adds `$010A` to each 5-bit channel with saturation at 31, subtract mode (set) subtracts it, and `$010A` grows by 1 in every channel that has not reached its field of `w` (red bits 0-4, green 5-9, blue 10-14). Examples measured: `w` = 0x0010: 17 values of `$010A` (0..16), the last 76 frames after the command; 0x3FFF: 32 values (red and green to 31, blue to 15), the last 151 frames after the command; 0xFFFF: subtract, 32 values, the last 151 frames after the command [V]. `SCREEN 7` sets bit 7 of `$2A`: the offsets then run back to 0 (32 values of 5 frames each, from 0x3FFF to 0) and `$2A` is cleared [V]. The map loader clears `$2A`.

### 13.2 Map change: exit and entry codes [V for values, C for the routines]

- The event runner stores the word at +2 of the transition entry (`$C8:3000 + 4 * n`) in `$DF/$E0` (`$C1:E7F2-E7F6`), so `$E0` = byte 3 of the entry, the **flag byte**. Values seen: 0x80 (transitions 47 and 340), 0xA0 (59 and 16 of the ending's transitions), 0xE0 (1008), 0x81 (188). Its low 5 bits are an **exit code**. With code 0 the fade-out starts at once and the routine sets the five low bits (`$E0` = 0xBF after transition 59, 0x9F in the saved states) [V]. With codes 1-4 the routine `$C0:B9C5-BA4B` makes the controlled hero walk before the fade: velocity byte `obj+0x07` = 0x82 (up, -2 px per frame) for code 1, and by the code table at `$C0:BA06-BA36` 0x0200 (down), 0x0002 (right), 0x0082 (left) for 2-4; `$FF` is then 0x60 (bit 5 = party walk, bit 6 = change pending) [C; V for code 1]. Codes 5 and above are handled by `$C0:BA4C-BAD4` (other counts), not run.
- Measured for code 1 (transition 188, controlled hero = boy): the command is at frame 2349; the boy walks up from (344, 202) to (344, 24) in 89 frames at 2 px per frame (counter `obj+0x0A` = 31 at the start); the girl and the sprite run 3 px per frame (animation 2) to the controlled hero and then follow it up at 2 px per frame; `$E0` becomes 0x9F at frame 2399-2407 and the fade-out (brightness 15 -> 0, one level per 4 frames) runs from frame 2408 to 2464, where the loader runs: **115 frames between the command and the new map**, against 57 for code 0 (transition 59: command at frame 3, load at frame 60). With the girl or the sprite as the controlled hero the walk is shorter and the load comes 8 frames earlier (115 -> 107) [V].
- After the load, the new map's entry for code 1 is an **entry walk**: all three heroes are placed at (296, 472) facing up (the formula `(16 * tileX + 8, 16 * tileY + 10)` would give (296, 362) for the entry's start tile (18, 22)), `$FF` = 0x20, `obj+0x0A` = 36 and velocity -2 px per frame: they walk 72 px up to (296, 400) and `$FF` is cleared when the controlled hero's counter reaches 0 (`$C0:B9B6`) [V; the rule that gives the placement was not traced]. The VM idles while `$FF` is non-zero. With code 0 the heroes are placed at `(16 * tileX + 8, 16 * tileY + 10)` and nothing walks (maps 255, 8, 180 and the 16 staff-roll maps of the ending).
- `$FF` values: 0x40 change pending, 0x20 party walk (entry), 0x60 both (exit walk), 0x81 world-map mode requested (`MAP_CHANGE_D`).
- After any load the VM steps in the frames `t` with `(t - load frame - 1)` mod 5 = 3 [V].

### 13.3 The world-map mode (`MAP_CHANGE_D`) [V for timing, C for routines]

- `MAP_CHANGE_D a` is `GOTO` event 0xD00 + (a & 0x3F): `$FA/$FC` = (low byte, high byte) of the first word of `$C6:7C80 + 4 * n` times 8, `$0110` = the second word, `JSL $C0:BC01` (`JSR $C0:8B09`, which starts the fade-out, and `$FF` = 0x81). The main loop then waits for the fade, stores `$FE` = 0x80 (bit 0 of `$FF`), clears `$FF`, sets `$F8` = 0x44 and jumps to `$C0:8038`: stack reset, screen set up for **BG mode 7** (`$2105` = 7), loop `$C0:8064` (`$C0:8B5E`, `83A8`, `983A`, `908B`, `95A0`, `9AB8`, `$C1:FDE4`, `$C0:87E0`, `8272`, `8093`).
- The VM is stepped from `$C0:B09C` only (map-mode frame body), so it is suspended in this mode: `$D0` = 1 and the script pointer stay where they were. The mode ends when the loop jumps to `$C0:B03F` (the map loader); the map comes from the table `$C6:7780` indexed by the world position bytes `$FB/$FD` (`$C0:81ED-8249`, which also sets `$E0` = 0xE0). In the ending: 511 frames (8.50 s), `$F8` runs 0xDF -> 0x10, map 8 (start tile (8, 7)) is loaded, and the script continues [V]. `tools/event_runs.py` emulates the loop with the vblank flag `$4210` toggling on every read.

### 13.4 Actor animation codes (`ACTOR_ANIM` / `ACTOR_ANIM_LOOP`) [V]

Hero slots: 0xA8 and 0xB2 20 frames, 0xA9 40 frames in state 0x40 (then idle); 0xAB a looping pose; **0x89 / 0x8A / 0x8B loop and move the object in its facing direction at 2 / 3 / 1 px per frame** (0x8A also triggers sound effect 0x8B every 20 frames); NPC kinds: 0x81 1 px per frame, 0xAF 7 frames, 0x96 87 frames. The looping codes set state 0x30 and no busy flag; the movement starts 3 frames after the command. Objects that leave the map edge wrap around (`x` modulo the map width, `y` modulo the height).

### 13.5 Restart: `PARTY_CMD 0x11` [C]

`$C1:EB63`: arguments above 0x10 that match none of the earlier cases run `JML $C0:0075` -> `JMP $C0:009B` -> `JML $C1:0018` -> `JML $C1:4CFA`: stack 0x01FF, `$4200` = 0, `$2100` = 0x80, registers cleared by `$C1:4D0F`, `$C1:4C30` called with the source `$C7:7C00` and the destination `$7E:8000` (a copy or a decompression of a program into work RAM; length and format not read), `JML $7E:AF28`. The reset vector (`$8004`) takes `$C1:0010` -> `$C1:4CE5`, the same sequence ending in `JML $7E:AF0B`. The ending of the game (`docs/cutscene-ending.md`) is the only user found (event 0x047).

### 13.6 Observed object effects [V]

`ACTOR_DELETE n`: `obj+0` = 0x80 in the same frame; `ACTOR_CLONE n`: `obj+0` = 1 and `obj+0x10` = 1 (facing down) at the position of the controlled hero; `TOGGLE_HERO_VIS`: `obj+0x0E` 0x00 <-> 0x80 on all three heroes; `HERO_REFILL`, `SET_FIELD_BYTE` and `CALL_E326` were executed (canned event 0x41E) but their effect on the WRAM was not examined beyond the values in the command stream.

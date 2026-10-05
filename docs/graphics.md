# Hero sprite graphics and the glove attack animations

How the three heroes are drawn (tile pools, palettes, sprite pieces, animation scripts) and every glove attack animation: the four normal attacks and the eight charged attacks, each in the three distance variants the game selects. Timing, boxes, damage and the choice of the variant are measured in `docs/glove-attacks.md`; this document is about the pictures and the data structures behind them. Everything below was obtained by running the original code in the interpreter from a save state (`tools/rip_hero_anims.py`) and by reading the disassembly; ROM data and images are never stored in this repository. The images produced by the tools go to a directory outside the repository that the caller chooses.

Tags: **[V]** executed in the interpreter and checked (a model, a decoder or pixel comparison against it); **[C]** read from the disassembly only. Banks: `$D1:3040` is the HiROM address, the file offset is `(bank - 0xC0) << 16 | address`.

Tools:
- `tools/gfx_decode.py`: 4bpp tile decoding, BGR555 palettes, OAM decoding, sprite rendering and a PNG writer / reader (standard library only).
- `tools/rip_hero_anims.py ROM STATE OUTDIR [heroes] [weapon_row] [attacks] [dirs]`: runs the attacks and writes PNG frames and JSON (section 7).
- `tools/hero_frames.py`: static decoder of the animation tables (no emulation), and a checker that compares it with the JSON written by the ripper (section 5; 6,180 of 6,180 script steps of the 336 ripped animations agree [V]).

## 1. Video set-up

| item | value | tag |
|---|---|---|
| OBJSEL (`$2101`) | `$7E:0091 = 0x63`: sprite sizes 16x16 (small) and 32x32 (large), name base word `0x6000`, second name table at word `0x7000` (gap 0). The code that builds it is `$C2:AAF0-AAFF` (`LDA #$60`, `LSR` x5, `ORA #$60`, `STA $91`, `STA $2101`) | V (value in the save states), C |
| hero pieces | all OAM entries of the heroes use the small size (the size bit of the high OAM table is never set), so every piece is 16x16 | V |
| tile number | 9 bits: OAM tile byte + bit 0 of the attribute byte (name table). Table 1 starts at VRAM word `0x7000`, so tile `0x1C0` is at word `0x7C00` | V |
| OAM | shadow at `$7E:0800` (512 + 32 bytes), copied by DMA in the NMI handler (`$C0:C124-C13B`) | C, V |
| CGRAM | shadow at `$7E:0600` (`$7E:BE00` while `$2A != 0`), copied by DMA in the NMI (`$C0:C0F0-C115`). Sprite palettes are CGRAM rows 8-15 (`128 + 16 * row`) | C, V |
| hero tile uploads | `$C1:950D` (called from the NMI, `$C0:C14E`) reads the tile tables of section 3 and DMAs 32 bytes per tile to VRAM | C, V |
| NMI / frame | the main loop body `$C0:B08C` runs once per NMI (60.0988 Hz); `$56` cycles 0-4. Phase 0: draw (`$C0:E8D7`, OAM), phase 3: animation tick of the actors (`$C0:F4AB`, dispatched from `$C0:B0D3`), phase 4: second piece list (`$C0:F1AE`) | C, V |

All times below are in video frames of 1/60.0988 s. **An actor's animation script advances once per five frames** (phase 3), so every script step lasts a multiple of 5 frames [V, all 336 animations].

## 2. Palettes

- A hero uses one sprite palette row for its body: boy OAM palette 1 (CGRAM row 9), girl 2 (row 10), sprite 3 (row 11) [V]. Colour 0 is transparent; the slot holds filler.
- ROM source of the three rows: 15 colours (indices 1-15, BGR555 little endian, 30 bytes) at `$C8:1F00` (boy), `$C8:1F1E` (girl), `$C8:1F3C` (sprite) (file offsets `0x81F00`, `0x81F1E`, `0x81F3C`). The bytes are identical to the CGRAM shadow rows of an idle hero [V]. Further copies of similar rows are at `0x8202C-0x82D10` (not examined).
- Weapon effect pieces (arcs, flashes) use sprite palette 0 (row 8). While an attack plays, colours 10-15 of that row change every few frames: the routine `$C1:859B` copies a 5-colour set from `$D1:F600 + 10 * n` into the shadow [C]; the captured row cycles through six values and the images keep the value of the frame in which they were recorded [V]. Using weapon row 0 and weapon row 8 gives byte-identical PNGs [V], so the glove-specific flash colour is not produced by the equip refresh `$C0:E9F8` (section 10).
- The PNGs use the plain `c5 * 255 / 31` expansion of the 5-bit channels; the public sprite sheets use `c5 << 3`, so comparisons are made on the 5-bit values.

## 3. Tiles

- 4bpp planar tiles, 32 bytes: row `y` has plane 0 at byte `2y`, plane 1 at `2y+1`, plane 2 at `16+2y`, plane 3 at `17+2y`; bit 7 is the left pixel [V: decoded images are identical to the public sheets].
- **The hero tile pools are not compressed.** Each pool is a de-duplicated set of 8x8 tiles; frames pick tiles one by one (the tile order inside a pool has no relation to the picture layout) [V]:

| hero | pool | file offset |
|---|---|---|
| boy | `$D5:0000-7FFF` | `0x150000` |
| girl | `$D5:8000-FFFF` | `0x158000` |
| sprite | `$D6:0000-7FFF` | `0x160000` |

  The last tile of each 32 KiB window (`7FE0`) is all zero and is used as the "empty" tile [V]. Only the tiles of the glove animations were examined; the pools are 32 KiB windows, the frame data picks the tiles.
- Per hero, `$C0:F66E-F6BE` writes a table of 16 words into WRAM (`$0C00` boy, `$0C20` girl, `$0C40` sprite): a 16-bit offset into the pool for every 8x8 tile of the current frame. Four entries per piece in the order top-left, top-right, bottom-left, bottom-right. A hero therefore shows at most 4 pieces (16 tiles) at a time. The NMI uploads the table to VRAM tile slots (OAM tile numbers): boy `0x1C0-0x1C7` / `0x1D0-0x1D7`, girl `0x1C8-0x1CF` / `0x1D8-0x1DF`, sprite `0x1E0-0x1E7` / `0x1F0-0x1F7`; piece `k` of a hero uses the 2x2 block starting at slot tile `base + 2k` [V: DMA sources and destinations logged for every frame of the 336 animations].
- Table entry formats (`$C0:F66E-F6BE`) [C, V against 6,180 frames]: a word without bit 15 is `(w & 0x3FF0) << 1` (byte offset of one tile in the pool). A word with bit 15 is a run of `(w & 15) + 1` entries: with bit 14 set the offsets `(w << 1) & 0x7FE0` + 0x20 * k (consecutive tiles), with bit 14 clear the same offset repeated.
- **Weapon effect tiles** (the glove arcs, flashes) are 3-byte-per-row graphics in bank `$D4` starting at `$D4:0000` for weapon type 0. The equip refresh (`$C0:EA34`, `JSL $C1:C599` with bank `$D4`, `Y` = source offset = 24 x the word at `$D4:C000 + 4 * weapon type`, `X` = destination, 0x40 tiles) expands them to 4bpp into a per-actor WRAM buffer (`$7E:2000` boy, `$7E:3000` girl, `$7E:4000` sprite). For the heroes the expansion is `$C1:C8A9`: with source bytes `a b c` of a row, plane 0 = `~(b & c) & a`, plane 1 = `~b`, plane 2 = `b ^ c`, plane 3 = `~(b & c)`. A source pixel `(a,b,c)` therefore becomes colour 10 (0,0,0), 14 (0,0,1), 12 (0,1,0), 0 (0,1,1), 11 (1,0,0), 15 (1,0,1), 13 (1,1,0), 0 (1,1,1) [C, from the formulas]. These tiles reach VRAM from the buffer into tile slots `0x144` (boy), `0x168` (girl), `0x18C` (sprite) [V]. The variants `$C1:C5D1` and `$C1:C731` are other colour maps of the same loader and were not used here.

## 4. Choosing the animation of an attack

The attack start is in `$C0:B21C-B2F6`. A tap of B (button edge) starts a normal swing at once (`$C0:B29F`: attack state `+0x1C = 0x20`). While B stays held and the weapon gauge (`+0x1ED`) is zero, the charge stage `+0x19B` rises; releasing B with stage > 0 starts the charged attack (`$C0:B24A`: `+0x1C = 0x80`). The animation id (`+0x11`) comes from `$C1:E40E` [C, V]:

```
distance class d = min over the active monster slots of max(byte +0x50+3h, byte +0x51+3h), >> 4, clamped to 3      ($C1:E4CC; 3 with no monster)
index  = d * 144 + stage * 16 + status_variant * 4 + (target +0x1B1 & 2) + ($F4 & 1)
kind   = $D1:0000[index]                      (576 bytes)
anim   = $D1:0480[weapon_type * 40 + kind]    (320 bytes; for weapon type 0 the table is the identity, so kind == animation id)
```
`status_variant` is 1, 2 or 3 when the target has status bit `0x01`, `0x02` or `0x10` in its `+0x190`; `h` is the hero index. The meaning of the two distance bytes of the monster record was not traced; the thresholds in pixels that this gives (measured with a dummy monster) are in `docs/glove-attacks.md` section 2.2, where "variant n" is the animation id n below and the class value there is `d + 1`.

Results for weapon type 0 (the glove group), read from the tables [C] and observed with the target-less sandbox [V]:

| attack | animation id | selected when |
|---|---|---|
| normal 0 "hook" | 0 | d = 0, `$F4` odd |
| normal 1 "jab" | 1 | d = 0, `$F4` even; d = 1, `$F4` odd |
| normal 2 "kick" | 2 | d = 1, `$F4` even; d >= 2, `$F4` odd |
| normal 3 "lunge" | 3 | d >= 2, `$F4` even |
| charge, stage k = 1..8, variant "near" | 4k | d = 0 |
| charge, variant "mid" | 4k + 1 | d = 1 |
| charge, variant "far" (also no target) | 4k + 2 | d >= 2 |
| ids 7, 11, 15 ... 35 | target with status `0x02` or `0x10` (any distance class; stage 0 and 1 give 7, stage k >= 2 gives 4k + 3); not ripped |
| ids 36-39 | distance class 0, target with status `0x01`, odd `$F4`, stage 0-3; not ripped |

The names hook/jab/kick/lunge describe the pictures; the game has no names. The variants differ in duration and in how far the hero moves: stage 1 near/mid/far = 65 / 70 / 75 frames and 20 / 30 / 50 px of movement for the boy facing right [V].

## 5. Animation data

Actor record: `$7E:E000 + 0x200 * slot`, slots 0-2 = boy, girl, sprite (section 1 of `rom-combat.md`). Fields used here [C, V]:

| offset | meaning |
|---|---|
| `+0x02` / `+0x04` | world x / y (words); the screen position `+0x20/+0x22` is world minus the camera `$A8/$AA` (`$C0:E443-E46E`) |
| `+0x10` | facing: 0 up, 1 down, 2 side, bit 7 = mirrored (left). The script table index uses the low nibble |
| `+0x11` | animation id (section 4) |
| `+0x12` | remaining extra ticks of the current script step |
| `+0x16` | script pointer after the entry just read |
| `+0x1C` | attack state: 0 none, 0x20 normal swing, 0x80 charged attack |
| `+0x20` / `+0x22` | x / y on screen (the foot point) |
| `+0x26` | frame index * 2 |
| `+0x28` | frame flags: bit 7 vertical, bit 6 horizontal mirror |
| `+0x2A` | frame descriptor table (bank `$D1`), `0x2040 + 0x200 * type` (word table `$D0:FFD0` indexed by weapon type) |
| `+0x45` | jump height |
| `+0x65`, `+0x75` | script pointer tables: attack/charge states (`0x3040 + 240 * type`) and ordinary states (`0x37CC`), bank `$D1` |
| `+0x72` | per-hero offset into the piece-list pointer table in bank `$D2`: 0x000 boy, 0x200 girl, 0x400 sprite |
| `+0x74` | low 7 bits: body height 14 (all three heroes); the pieces are drawn that many pixels above the foot point |
| `+0x83` / `+0x84` | piece count of list 1 / list 2 |
| `+0x86`, `+0x8A` | first tile (and attribute byte) of list 2 / list 1: list 2 tiles 0x144, 0x168, 0x18C (the effect tiles), list 1 attribute `0x23` / `0x25` / `0x27` (priority 2, palette 1 / 2 / 3, name table 1) and tiles 0x1C0, 0x1C8, 0x1E0 |
| `+0x90` | list 1: up to 15 OAM-ready entries `x, y, tile, attribute` (the hero body pieces) |
| `+0xD0` | list 2: the ground shadow (tile 0, palette 1, at -8,-8) and, during attacks, the effect pieces |
| `+0x19B` / `+0x19C` | charge stage / weapon level |
| `+0x1E3` | equipped weapon row id (not the weapon type: `$C0:EA41` reads `$D0:1000 + 12 * row`, byte 0 = weapon type) |
| `+0x1ED` | weapon gauge |

Reading a frame (`$C0:F4CB-F6C0`, executed in `$C0:F4AB` every tick):

1. **Script.** The script of an animation is at `$D1:[table + (anim * 3 + (facing & 15)) * 2]` (a word). Entries are 2 bytes: `b0` (bit 7 clear), `b1` = frame index (0-255). Duration: if `b0 & 7` < 4 the step lasts `(b0 & 7) + 1` ticks, otherwise 1 tick. `b0` bits 6 and 5 are the vertical and horizontal flip of the frame; bit 5 is inverted when the actor faces left (+0x10 bit 7), so left uses the right-facing script mirrored. An entry with bit 7 set is an operation (`$C0:F90B`): `FF` ends the script (clears `+0x1C` and the animation id and, after a swing, loads the weapon gauge `+0x1ED`), `FE` repeats the operation on the next tick while the actor's status bits `0x7B` are set, `F1 lo hi` jumps inside the bank; the others are dispatched by the first byte to `$01:D5C0` (`80`-`AF`, for example `90`, `A8`), `$01:D6DC` (`B0`-`EF`), `$01:D52A` (`F0`-`F7`) and `$01:D48D` (`F8` and up, for example `F9 xx yy`); their arguments were not decoded here (`docs/glove-attacks.md` describes the velocity, box and sound operations the glove scripts use) [C, V against the operations met in the traces].
2. **Descriptor.** `$D1:[+0x2A + 2 * frame]` is a word: low byte bits 7-6 = frame flips (XORed with the script flags), high byte `h` selects the piece list: pointer = word at `$D2:[+0x72 + 2 * h]`. The same descriptors serve the three heroes; only the piece lists differ.
3. **Piece list** (bank `$D2`): header byte (low nibble = piece count, 0 means 1; bits 6 and 5 announce a body box and a further box after the pieces, read into `+0xC8-0xCB` and `+0xCC-0xCF` (bit 4 selects byte or nibble coordinates), not used for drawing [C]; the boxes are described in `docs/glove-attacks.md`); the tile words of section 3 (4 per piece); then 2 bytes per piece `lo, hi`: `y = signed 7-bit (lo & 0x7F)`, `x = signed 7-bit (hi & 0x7F)`, bit 7 of `hi` = horizontal flip of the piece; bit 7 of `lo` is not used. With a frame flip the position is mirrored (`v -> -v - 16`) and the flip bit toggled.
4. **Placement.** OAM x = `+0x20` + x; OAM y = `+0x22` - (`+0x74 & 0x7F`) - `+0x45` + y. The pieces get consecutive tile numbers `base, base + 2, ...` (when bit 4 of the number is set 0x10 is added, so a row holds 8 pieces) and the attribute from `+0x8A` / `+0x86` [C].
5. List 2 is built the same way by `$C0:F1CF-F409` from `$D4:[+0x6A]` tables (ground shadow and effect pieces); its coordinates are 4-bit pairs in `$D1:[+0x7E + frame]`.

`tools/hero_frames.py` implements steps 2-4 and its output equals the recorded pieces of all 6,180 script steps in the 336 ripped animations (position, flips, piece count) [V].

## 6. The glove animations

All values were produced by `tools/rip_hero_anims.py` from a save state with the sandbox of section 8 and are identical for the three heroes (timing, movement and jump height of all 112 animations of each hero are equal [V]). "Frames" are video frames from the first script step to the end of the attack state; add `latency_frames` (1-5, depending on where in the five-frame cycle the button is pressed) for the time from the press. The names hook / jab / kick / lunge describe the pictures (hook: a short swinging punch, jab: a straight punch in four pictures, kick: a high side kick, lunge: a step-in punch); the game has no names. Left is the exact mirror image of right in every frame and has the same timing [V, 5,148 of 5,148 right-facing pictures compared]. The "near / mid / far" variants of stages 1-5 differ by a short dash in front of the attack (20 / 30 / 50 px at stage 1) and 5 frames each; stages 6, 7 and 8 are identical in the three variants (the dash is not present).

| attack | anim id | frames, up / down | frames, left / right | seconds, up-down / left-right | pictures per direction | net movement px, boy: up / down / left / right | farthest point px (up, down, left, right) | max jump |
|---|---|---|---|---|---|---|---|---|
| hook | 0 | 20 / 20 | 20 / 20 | 0.333 / 0.333 | 2-2 | 0,-10; 0,10; -10,0; 10,0 | 10, 10, 10, 10 | 0 |
| jab | 1 | 20 / 20 | 20 / 20 | 0.333 / 0.333 | 4-4 | 0,-5; 0,5; -5,0; 5,0 | 5, 5, 5, 5 | 0 |
| kick | 2 | 25 / 25 | 20 / 20 | 0.416 / 0.333 | 3-3 | 0,0; 0,0; 0,0; 0,0 | 0, 0, 0, 0 | 0 |
| lunge | 3 | 25 / 25 | 25 / 25 | 0.416 / 0.416 | 3-3 | 0,-10; 0,10; -10,0; 10,0 | 10, 10, 10, 10 | 0 |
| charge near, stage 1 | 4 | 70 / 70 | 65 / 65 | 1.165 / 1.082 | 8-8 | 0,-20; 0,20; -20,0; 20,0 | 20, 20, 20, 20 | 0 |
| charge mid, stage 1 | 5 | 75 / 75 | 70 / 70 | 1.248 / 1.165 | 9-9 | 0,-30; 0,30; -30,0; 30,0 | 30, 30, 30, 30 | 0 |
| charge far, stage 1 | 6 | 80 / 80 | 75 / 75 | 1.331 / 1.248 | 9-9 | 0,-50; 0,50; -50,0; 50,0 | 50, 50, 50, 50 | 0 |
| charge near, stage 2 | 8 | 80 / 80 | 80 / 80 | 1.331 / 1.331 | 33-34 | 0,-35; 0,35; -35,0; 35,0 | 35, 35, 35, 35 | 0 |
| charge mid, stage 2 | 9 | 85 / 85 | 85 / 85 | 1.414 / 1.414 | 34-35 | 0,-45; 0,45; -45,0; 45,0 | 45, 45, 45, 45 | 0 |
| charge far, stage 2 | 10 | 90 / 90 | 90 / 90 | 1.498 / 1.498 | 34-35 | 0,-65; 0,65; -65,0; 65,0 | 65, 65, 65, 65 | 0 |
| charge near, stage 3 | 12 | 110 / 110 | 105 / 105 | 1.83 / 1.747 | 43-43 | 0,-20; 0,20; -20,0; 20,0 | 20, 20, 20, 20 | 10 |
| charge mid, stage 3 | 13 | 115 / 115 | 110 / 110 | 1.914 / 1.83 | 44-44 | 0,-30; 0,30; -30,0; 30,0 | 30, 30, 30, 30 | 10 |
| charge far, stage 3 | 14 | 120 / 120 | 115 / 115 | 1.997 / 1.914 | 44-44 | 0,-50; 0,50; -50,0; 50,0 | 50, 50, 50, 50 | 10 |
| charge near, stage 4 | 16 | 125 / 125 | 120 / 120 | 2.08 / 1.997 | 33-33 | 0,-15; 0,35; -35,0; 35,0 | 30, 35, 35, 35 | 10 |
| charge mid, stage 4 | 17 | 130 / 130 | 125 / 125 | 2.163 / 2.08 | 34-34 | 0,-25; 0,45; -45,0; 45,0 | 40, 45, 45, 45 | 10 |
| charge far, stage 4 | 18 | 135 / 135 | 130 / 130 | 2.246 / 2.163 | 34-34 | 0,-45; 0,65; -65,0; 65,0 | 60, 65, 65, 65 | 10 |
| charge near, stage 5 | 20 | 150 / 150 | 140 / 140 | 2.496 / 2.329 | 91-94 | 0,-30; 0,30; -30,0; 30,0 | 30, 30, 30, 30 | 10 |
| charge mid, stage 5 | 21 | 155 / 155 | 145 / 145 | 2.579 / 2.413 | 92-95 | 0,-40; 0,40; -40,0; 40,0 | 40, 40, 40, 40 | 10 |
| charge far, stage 5 | 22 | 160 / 160 | 150 / 150 | 2.662 / 2.496 | 92-95 | 0,-60; 0,60; -60,0; 60,0 | 60, 60, 60, 60 | 10 |
| charge near, stage 6 | 24 | 150 / 150 | 150 / 150 | 2.496 / 2.496 | 135-150 | 9,0; 9,0; -9,0; 9,0 | 30, 30, 40, 40 | 0 |
| charge mid, stage 6 | 25 | 150 / 150 | 150 / 150 | 2.496 / 2.496 | 135-150 | 9,0; 9,0; -9,0; 9,0 | 30, 30, 40, 40 | 0 |
| charge far, stage 6 | 26 | 150 / 150 | 150 / 150 | 2.496 / 2.496 | 135-150 | 9,0; 9,0; -9,0; 9,0 | 30, 30, 40, 40 | 0 |
| charge near, stage 7 | 28 | 140 / 140 | 140 / 140 | 2.329 / 2.329 | 85-88 | 0,-105; 0,105; -105,0; 105,0 | 115, 115, 115, 115 | 20 |
| charge mid, stage 7 | 29 | 140 / 140 | 140 / 140 | 2.329 / 2.329 | 85-88 | 0,-105; 0,105; -105,0; 105,0 | 115, 115, 115, 115 | 20 |
| charge far, stage 7 | 30 | 140 / 140 | 140 / 140 | 2.329 / 2.329 | 85-88 | 0,-105; 0,105; -105,0; 105,0 | 115, 115, 115, 115 | 20 |
| charge near, stage 8 | 32 | 200 / 200 | 200 / 200 | 3.328 / 3.328 | 120-125 | 0,-75; 0,95; -95,0; 95,0 | 105, 95, 95, 95 | 10 |
| charge mid, stage 8 | 33 | 200 / 200 | 200 / 200 | 3.328 / 3.328 | 120-125 | 0,-75; 0,95; -95,0; 95,0 | 105, 95, 95, 95 | 10 |
| charge far, stage 8 | 34 | 200 / 200 | 200 / 200 | 3.328 / 3.328 | 120-125 | 0,-75; 0,95; -95,0; 95,0 | 105, 95, 95, 95 | 10 |

Totals: 3 heroes x 4 directions x (4 normal + 8 stages x 3 variants) = **336 animations and 20,610 distinct pictures** (boy 6,670, girl 6,970, sprite 6,970). The normal attacks last 0.333-0.416 s, the charged attacks 1.08-3.33 s. A hero has at most 4 body pieces and at most 4 effect pieces on screen at a time. The longest picture sequences are stage 6 (135-150 pictures, two-step alternations) and stage 8 (120-125). "Net movement" is the displacement at the end of the attack state, "farthest point" the largest displacement during it (px, boy): in the up versions of stages 4 and 8 the hero moves part of the way back, so the net value is smaller. Stage 6 shifts the hero by 9 px along x whatever the facing. The jump height column is the largest value of `+0x45` (the sprite is drawn that many pixels above the foot point).

## 7. Output files

`OUTDIR/<hero>/<attack>_<level>_<dir>_<nn>.png` and `<attack>_<level>_<dir>.json`, plus `OUTDIR/index.json`.

- `<hero>` boy / girl / sprite; `<attack>` hook, jab, kick, lunge (level 0) or charge / chargemid / chargenear (level 1-8); `<dir>` up, down, left, right.
- One PNG per distinct picture (consecutive identical frames are merged), RGBA with colour 0 transparent, 1:1 pixels, every PNG of an animation has the same size (union box of the animation). `origin` in the JSON is the foot point (actor position) inside the PNG. Effect pieces are included; the ground shadow is not.
- JSON: `frames[]` (file, `start_frame`, `frames` = duration in video frames, `seconds` = frames / 60.0988, actor position and movement, animation id, script position, palettes of the sprite rows used, pieces with `list` 90 or D0, `dx`, `dy` relative to the foot point, tile, palette, priority, flips, `ground_shadow`), `script_steps[]` (every change of script position / frame index with its duration and PNG), `per_frame` (PNG index, actor movement and jump height for every video frame), `latency_frames` (frames between the button press and the first script step, during which the previous pose stays), `start_world_position` and `movement_during_latency` (world coordinates `+0x02/+0x04`), `distance_class`, `total_frames`, `total_seconds`. All offsets are world pixels (the screen scroll is not included).

## 8. Running it

```
python3 tools/rip_hero_anims.py /path/to/rom.sfc /path/to/state.zs3 /path/to/outdir "" 0 "" "" 128,112
python3 tools/hero_frames.py    /path/to/rom.sfc check /path/to/outdir
python3 tools/hero_frames.py    /path/to/rom.sfc sprite 0 3 side
python3 tools/compare_sheet.py  /path/to/sheet.png /path/to/outdir boy
```
(the empty arguments of the first command mean "all heroes", "all attacks", "all directions"). A full run takes about 10 minutes per hero. The state must be a ZSNES v143 save state taken during play with the three heroes active (object slots 0-2 non-zero in `+0x00`).

What the tool does to the save state (all of it only inside the interpreter) [V]:
- deactivates every other actor (so there is no monster and no partner), makes the hero the pad-1 hero (`$D9`, `$D4`) and presses B through the joypad registers (`$4218/$4219`); the polling is stubbed, the NMI handler `$C0:C0A8` runs once per frame with the DMA and PPU register writes captured;
- sets the hero position (`+0x02`, `+0x04` = screen position + camera `$A8/$AA`) 40-45 px behind the centre of the lunges, opposite to the facing, and the facing `+0x10`;
- equips weapon row `row` (`+0x1E3`, `+0x1E4`, `+0x1E8`, weapon level `+0x19C` = 8, charge limit `$CC7D+slot` = 8) and runs the engine's own refresh `$C0:E9F8` (this loads the animation tables, the frame-table pointers and the effect tiles of section 3), clears the attack, status and gauge fields, runs 30 frames;
- removes everything that would shorten a lunge: the party window `$C0:D6C8` (section 9 of `hero-movement.md`) is replaced by an RTS and the solid-tile codes of the tile attribute table are cleared (`$7F:B800`, bytes b0 and b2). Without this the stage 7 and 8 attacks stop at the screen window `x 56-199, y 72-175` [V];
- forces the distance class by overriding the result of `$C1:E4CC` at `$C1:E418`, and the `$F4` parity by choosing the press frame; a charged attack is produced by holding B (the stage rises by itself, every 90 frames after the first; about 185 frames for the first with the boy), snapshotting the state when each stage is reached and releasing B from the snapshot.

Two different save states (a boss arena and a field map) gave identical PNGs and durations for the boy [V]. All three heroes give identical timing, movement and jump height in all 112 animations; the split of the video frames into runs of identical pictures differs for the girl and the sprite in some animations only because their pieces are different pictures.

## 9. Validation against public sprite sheets [V]

Each frame was compared pixel by pixel (5-bit colours, in the sheet orientation or mirrored) with the public sprite sheets of the glove animations ("Glove (Randi)" for the boy, "Glove (Popoi)" for the sprite, "Primm" for the girl, from The Spriters Resource). For a frame with effect pieces the effect palette colours are left out of the comparison (the sheets show one palette phase). Result with `tools/compare_sheet.py` (frames with fewer than 40 body pixels would be skipped; none occurred): **boy 6,670 of 6,670, girl 6,970 of 6,970, sprite 6,970 of 6,970 distinct pictures are found pixel for pixel in the sheets**, including every up and down picture (the girl's sheet is a collection of loose sprites, not organised by attack and direction, but it holds every picture). On average 95-96 % of the opaque pixels of a picture take part (the rest are effect colours). Negative controls: changing one pixel of a picture, or looking for a boy picture in the girl's sheet, finds nothing. The effect pieces themselves were compared separately for the sprite hero by replacing the six cycling effect colours by one marker colour on both sides (union of body and effect pieces: exact for the frames tried; the sheets do not show the colour cycle). What the sheets cannot tell is the timing, the order and the movement, which come only from the game code.

## 10. Open questions

- The operations of the animation scripts (`90`, `A8`, `F9 xx yy`, `F0`-`F8`): arguments and effects (sounds, hit timing, spawning) were not decoded here; `docs/glove-attacks.md` has what the glove scripts use.
- Variants 4k+3 and 36-39 (target with a status) were not ripped; they can be produced by forcing `$00` at `$C1:E45C`.
- How the monster record fills the two distance bytes at `+0x50+3h` / `+0x51+3h` (units, axis).
- The flash colour per glove (the public sheet says it depends on the glove): rows 0 and 8 gave identical colours here; `$D1:F600` holds the colour sets but the code that picks the set for a glove was not traced.
- The HUD sprites (charge gauge), HDMA, colour math and window effects are not emulated and are not in the images; any full-screen flash of the highest charge levels is therefore missing.
- The charge-up pose while B is held (a single static pose at every stage in this capture) and the stage-up flash were not ripped.
- Weapon types other than 0 share the same tables (section 4) and should work with `weapon_row` 9-71, but only the glove group was run.
- The meaning of bits 4 and 3 of `b0` in a script step and of the value `+0x89` that is written when `b0 & 7 >= 4`.

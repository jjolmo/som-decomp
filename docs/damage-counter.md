# Floating damage / heal counter (Secret of Mana USA)

Tags: **[V]** verified by running the real 65816 code in `tools/cpu65816.py` on a ZSNES save state (`tools/damage_counter.py`), results identical for 12 combinations of value, type and slot (see 9). **[C]** read from the disassembly, not executed. Anything not determined is listed in section 10.

ROM: 2 MiB HiROM without header, `$Cx:xxxx` = file offset `((bank-0xC0)<<16)|addr`. `$01:xxxx` is the mirror of `$C1:xxxx`, `$00:FD22` of `$C0:FD22`. No ROM bytes or table dumps are stored here, only addresses and derived numbers.

## 1. Summary

- The counter is an overlay of the creature object itself (state `E060 = 0x40`, 3 digit sprite slots), not a separate object. One counter per creature; a new hit restarts it [V/C].
- It runs on the **per-frame (NMI, 60.0988 Hz) clock**, not on the 12 Hz combat tick. Only its creation happens inside the 12 Hz tick [V].
- **There is no per-digit delay.** All digits bounce at the same time with the same phase. The digits differ only in amplitude: left slot 1/2, middle slot 1, right slot 3/4 of the bounce height [V].
- The bounce is a chain of 5 half-sine arcs, each lasting half as long and half as high as the one before: 32/16/8/4/2 frames, peaks 39/19/9/4/1 px (for the middle digit) [V].
- Total life: 97 frames drawn = 1.614 s (about 0.5 s for the first arc alone). Bounce part 61 frames = 1.015 s, then 36 frames = 0.599 s of rest + colour fade + horizontal collapse [V].
- Size is chosen by value: **< 50 small, 50..199 medium, >= 200 large** (not 49/99) [V]. Colour is chosen by the type code only (`D0` HP damage, `D8` HP heal, `E0` MP damage, `E8` MP heal, see section 7); hero vs enemy makes no difference [V].
- Rest position = creature origin (`E022 - E045`), the number starts there, rises up to 39 px and settles 1 px above it [V].

## 2. Pipeline

| step | address | what | tag |
|---|---|---|---|
| apply pending HP/MP | `$C0:4004` | writes the amount into `E17B` (word) and the effect type into `E175` | V |
| HP heal | `$C0:401B-4052` | `E17B = E1F3` (capped 999, NOT clipped to missing HP), `E175 = D8` | V |
| HP damage | `$C0:4053-40DD` | `E17B = E1F1` (capped 999, not clipped to remaining HP), `E175 = D0` | V |
| MP heal | `$C0:40DE-411B` | `E17B = E1F6` (cap 99), `E175 = E8` | V |
| MP damage | `$C0:411C-4155` | `E17B = E1F5` (cap 99), `E175 = E0` | V |
| zero damage | `$C0:5174-5199` | if the net damage is 0 and the defender has `E1FB` bit 7 clear (a monster, see `docs/rom-combat.md`), shows "0": `E17B = 0`, `E175 = D0`. Heroes get no "0". Misses (`$C0:505B` fails) call `$C0:4E6B` and show no number | C |
| absorbed hits | `$C0:4068-40A8` | defenders with `E1B0` bit 0x1000 (and `E1F0` >= 0) take the hit into a counter `E1BD` and no `E175` is set, so no number | C |
| event out | `$C0:3B8A-3B9E` (inside combat tick `$C0:3A79`) | if `E175 != 0` returns A=1, X=`E175`, Y=`E17B`, clears `E175` | V |
| event in | `$C1:8089`, case 1 at `$C1:80C5-80D3` | `E04F = type`, `$1E = value`, `JSR $810E` | V |
| gating | `$C1:8089-80B7` | no counter while `$52|$FF != 0`, `$F1` bit 7, `$E8` bit 2, or for the object excluded by `$D0/$D4/$3A`; monsters (X >= 0x600) additionally need `$ED` bit 7, heroes do not | C |
| creation | `$C1:810E-818E` | see 3 | V |
| per-frame update | `$C1:833A` (state `0x40` branch at `$C1:8355-83F8`) | see 4 | V |
| caller | `$C0:EB7D` (slots 0,1,2 via `$C0:EB36`) and `$C0:FBEA` (monsters, `$C0:FB8F`), both from `$C0:EB06`, which `$C0:B0C7` calls once per frame inside `$C0:B08C` | | V (static) |
| draw | `$C0:E4C1 -> E527 -> E640` | one OAM entry per slot | C |

Delay hit -> number: the counter is created by the next combat tick after the amount was applied (12 Hz, up to 83 ms). In the harness the same tick first returned the hit-reaction event (A=2) and the counter event (A=1) came 5 frames (83 ms) later [V in harness].

## 3. Creation (`$C1:810E`)

[V] after the call: `E060 = 0x40`, `E084 = 3` (3 overlay entries), `E118 = 0` (x shift), `E11A = E074 & 0x7F` (cancels the object height, see 6), `E11C = 0x08` (phase step), `E11D = 0x28 = 40` (amplitude), `E11E = 0` (phase), `E11F = 0` (hold timer). Slot x offsets (bytes at `E0D0, E0D4, E0D8`) = 0xF4, 0xFC, 0x04 = **-12, -4, +4**; slot y offsets (`E0D1, E0D5, E0D9`) = 0.
If `E060` already is `0x40` the object is re-initialised (the old number is replaced and the animation restarts from n=0); any other nonzero `E060` (0x80/0xC0/0xE0 overlays) blocks the counter [C]. When the creature is not already in the overlay state (`E060 == 0`) the digit font is uploaded first (`$C1:85F1`, DMA request with source `$D1:F100`); a restart skips the upload [C].

Digits (`$C1:84C9-8528`) [V]: value `v = $1E` (0..999) is split with the hardware divider into ones, tens, hundreds. Slot 0 = hundreds, slot 1 = tens, slot 2 = ones. Blank slots get glyph `0xCB00`.
- 3 digits: slots 0,1,2 used, `E118 = 0`: digit x offsets -12, -4, +4.
- 2 digits: slot 0 blank, `E118 = -4` (`$C1:8522`): tens at -8, ones at 0.
- 1 digit (also the value 0): only slot 1 is filled: x = -4.
So the group is always centred on the creature x (`E020`), 8 px advance per digit [V]. Glyph pixel dimensions are not known (see 10).

## 4. Motion (`$C1:8355-83F8`, called once per frame) [V]

State: `E11E` phase (8 bit), `E11C` phase step, `E11D` amplitude, `E11F` hold timer.

```
while bouncing (E11F == 0), each frame:
    phase = (phase + step) & 255
    if phase == 0:                      # arc finished
        step = (step * 2) & 255         # 8,16,32,64,128, then 0
        amp  = amp >> 1                 # 40,20,10,5,2, then 1
        if amp < 2: E11F = 0xF8 (hold phase, see below)
    p  = phase if phase < 128 else 255 - phase     # fold, 0..127
    T  = min(255, T0[p])                # T0[p] = round(256 * sin(pi * p / 256)), table at $C0:FD22 (4-byte stride, first word)
    up = (T * amp) >> 8                 # pixels above the origin, middle digit
    group_y   = -up                     # E11A = (E074 & 0x7F) - up   (the object height cancels)
    slot0_y   = +(up >> 1)  (down)  -> effective height up - (up >> 1)
    slot1_y   = 0                       -> effective height up
    slot2_y   = +(up >> 2)  (down)  -> effective height up - (up >> 2)
```

Hold phase (`E11F != 0`): every frame `E11F -= 7`; offsets stay frozen at the last value (1 px up for all slots). When `E11F < 0x38` (n = 89) the outer slots slide 1 px per frame towards the middle slot's x (`E0D0++`, `E0D8--` until they equal `E0D4`, `$C1:83DB-83F8`); when `E11F - 7` borrows (n = 97) the overlay is removed (`E060 = E084 = 0`, `$C1:83F9`).

Peak heights in pixels (middle digit, left, right): arc 1 39/20/30, arc 2 19/10/15, arc 3 9/5/7, arc 4 4/2/3, arc 5 1/1/1.

Frame -> seconds: **1 frame = 1 / 60.0988 s = 16.638 ms** (NTSC). The counter does not run on the 12 Hz combat tick: `$C0:EB06` is called from `$C0:B0C7` inside `$C0:B08C`, which the main loop `$C0:B070` runs once per NMI [C], and the harness calls `$C1:833A` once per frame to reproduce it [V].

## 5. Per-frame y sequence (n = update index after creation, n = 0 is the first update)

Heights are pixels above the creature origin (up = positive). At creation (before n = 0) all digits are at height 0. Values are identical for every number, type and creature slot [V]. "Colour step" is the palette row added to the base code (section 7).

| n | phase E11E | step E11C | amp E11D | middle digit (px up) | left digit | right digit | colour step |
|---|---|---|---|---|---|---|---|
| 0 | 8 | 8 | 40 | 3 | 2 | 3 | +0 |
| 1 | 16 | 8 | 40 | 7 | 4 | 6 | +0 |
| 2 | 24 | 8 | 40 | 11 | 6 | 9 | +0 |
| 3 | 32 | 8 | 40 | 15 | 8 | 12 | +0 |
| 4 | 40 | 8 | 40 | 18 | 9 | 14 | +0 |
| 5 | 48 | 8 | 40 | 22 | 11 | 17 | +1 |
| 6 | 56 | 8 | 40 | 25 | 13 | 19 | +1 |
| 7 | 64 | 8 | 40 | 28 | 14 | 21 | +1 |
| 8 | 72 | 8 | 40 | 30 | 15 | 23 | +1 |
| 9 | 80 | 8 | 40 | 33 | 17 | 25 | +1 |
| 10 | 88 | 8 | 40 | 35 | 18 | 27 | +1 |
| 11 | 96 | 8 | 40 | 37 | 19 | 28 | +1 |
| 12 | 104 | 8 | 40 | 38 | 19 | 29 | +1 |
| 13 | 112 | 8 | 40 | 39 | 20 | 30 | +1 |
| 14 | 120 | 8 | 40 | 39 | 20 | 30 | +1 |
| 15 | 128 | 8 | 40 | 39 | 20 | 30 | +2 |
| 16 | 136 | 8 | 40 | 39 | 20 | 30 | +2 |
| 17 | 144 | 8 | 40 | 39 | 20 | 30 | +2 |
| 18 | 152 | 8 | 40 | 38 | 19 | 29 | +2 |
| 19 | 160 | 8 | 40 | 36 | 18 | 27 | +2 |
| 20 | 168 | 8 | 40 | 35 | 18 | 27 | +2 |
| 21 | 176 | 8 | 40 | 32 | 16 | 24 | +2 |
| 22 | 184 | 8 | 40 | 30 | 15 | 23 | +2 |
| 23 | 192 | 8 | 40 | 27 | 14 | 21 | +2 |
| 24 | 200 | 8 | 40 | 25 | 13 | 19 | +2 |
| 25 | 208 | 8 | 40 | 21 | 11 | 16 | +2 |
| 26 | 216 | 8 | 40 | 18 | 9 | 14 | +2 |
| 27 | 224 | 8 | 40 | 14 | 7 | 11 | +2 |
| 28 | 232 | 8 | 40 | 11 | 6 | 9 | +2 |
| 29 | 240 | 8 | 40 | 7 | 4 | 6 | +2 |
| 30 | 248 | 8 | 40 | 3 | 2 | 3 | +2 |
| 31 | 0 | 16 | 20 | 0 | 0 | 0 | +1 |
| 32 | 16 | 16 | 20 | 3 | 2 | 3 | +1 |
| 33 | 32 | 16 | 20 | 7 | 4 | 6 | +1 |
| 34 | 48 | 16 | 20 | 11 | 6 | 9 | +1 |
| 35 | 64 | 16 | 20 | 14 | 7 | 11 | +1 |
| 36 | 80 | 16 | 20 | 16 | 8 | 12 | +1 |
| 37 | 96 | 16 | 20 | 18 | 9 | 14 | +1 |
| 38 | 112 | 16 | 20 | 19 | 10 | 15 | +1 |
| 39 | 128 | 16 | 20 | 19 | 10 | 15 | +1 |
| 40 | 144 | 16 | 20 | 19 | 10 | 15 | +1 |
| 41 | 160 | 16 | 20 | 18 | 9 | 14 | +1 |
| 42 | 176 | 16 | 20 | 16 | 8 | 12 | +1 |
| 43 | 192 | 16 | 20 | 13 | 7 | 10 | +1 |
| 44 | 208 | 16 | 20 | 10 | 5 | 8 | +1 |
| 45 | 224 | 16 | 20 | 7 | 4 | 6 | +1 |
| 46 | 240 | 16 | 20 | 3 | 2 | 3 | +1 |
| 47 | 0 | 32 | 10 | 0 | 0 | 0 | +1 |
| 48 | 32 | 32 | 10 | 3 | 2 | 3 | +1 |
| 49 | 64 | 32 | 10 | 7 | 4 | 6 | +1 |
| 50 | 96 | 32 | 10 | 9 | 5 | 7 | +1 |
| 51 | 128 | 32 | 10 | 9 | 5 | 7 | +1 |
| 52 | 160 | 32 | 10 | 9 | 5 | 7 | +1 |
| 53 | 192 | 32 | 10 | 6 | 3 | 5 | +1 |
| 54 | 224 | 32 | 10 | 3 | 2 | 3 | +1 |
| 55 | 0 | 64 | 5 | 0 | 0 | 0 | +1 |
| 56 | 64 | 64 | 5 | 3 | 2 | 3 | +1 |
| 57 | 128 | 64 | 5 | 4 | 2 | 3 | +1 |
| 58 | 192 | 64 | 5 | 3 | 2 | 3 | +1 |
| 59 | 0 | 128 | 2 | 0 | 0 | 0 | +1 |
| 60 | 128 | 128 | 2 | 1 | 1 | 1 | +1 |
Rest/fade part (identical for all slots, heights 1 px for all three digits):

| n | `E11F` | colour step | digit x of slot 0 / slot 2 (3-digit case) |
|---|---|---|---|
| 61 | 248 | +1 | -12 / +4 |
| 62-73 | 241 ... 164 (-7 per frame) | +1 | -12 / +4 |
| 74-78 | 157 ... 129 | +3 | -12 / +4 |
| 79-82 | 122 ... 101 | +4 | -12 / +4 |
| 83-87 | 94 ... 66 | +5 | -12 / +4 |
| 88 | 59 | +6 | -12 / +4 |
| 89-91 | 52, 45, 38 | +6 | -11/+3, -10/+2, -9/+1 |
| 92-96 | 31, 24, 17, 10, 3 | +7 | -8/0, -7/-1, -6/-2, -5/-3, -4/-4 |
| 97 | 252 (underflow) | | removed |

Colour step rule (`$C1:8564-8598`) [V]: while bouncing, arc 1 (`E11C == 8`): phase < 48: +0, 48..127: +1, >= 128: +2; arcs 2-5: +1. In the hold phase: `E11F >= 0xE0` or `(E11F >> 5) ^ 7 < 3` gives +1, otherwise `(E11F >> 5) ^ 7` (3..7).

## 6. Position on screen

Sprite top-left y = `E022 - (E074 & 0x7F) - E045 + E11A + slot_y` [V code `$C0:E527-E546`, `$C0:E640`], with `E11A = (E074 & 0x7F) - up`, so **y = E022 - E045 - up + slot_y**: relative to the object y (`E022`, the screen y of the creature) and minus the jump height `E045`. x = `E020 + E118 + slot_x`. The counter therefore starts at the object origin, rises up to 39 px, falls back and rests 1 px above the origin [V]. Digit sprites are plain OAM entries (the size bit is never set; only the x bit 8 is) and the tile word high byte is `0x21` for the first hero slot [C].

## 7. Colours (`$C1:859B`, table at `$D1:F600`, 10 bytes = 5 BGR555 colours per row, row = type code + colour step)

The row is copied into the object's CGRAM staging slot (`E0FA`). Base type code (`E175`, stored in `E04F`) and the main fill colour (third word of the row), as 5-bit RGB:

| code | effect | step +0 | step +1 | step +2 | steps +3..+7 |
|---|---|---|---|---|---|
| `D0` | HP damage (also the "0" damage) | (11,4,0) dark red | (31,12,10) light red | (31,28,28) pinkish white | fade-out rows: main colour shifts out, ends transparent with a grey (0x4A52) outline entry |
| `D8` | HP heal | (0,4,12) dark blue | (4,26,31) cyan | (26,28,31) pale blue | same fade scheme |
| `E0` | MP damage | (11,4,0) dark red | (31,26,4) yellow | (31,30,23) pale yellow | same |
| `E8` | MP heal | (4,11,0) dark green | (14,31,14) light green | (28,31,26) pale green | same |

[V] that the rows are as listed and chosen as above (executed for D0, D8, E0, E8). The effect column follows the pipeline of section 2 (which pending field feeds each type code). Colour is the same for hero and monster targets.

## 8. Size selection (`$C1:8425-84C8`) [V]

By the value (`$1E`), compared as a 16-bit number: `< 50` small, `50 .. 199` medium, `>= 200` large. Glyph base words in the per-object tile list (digit `d` -> base + d * step): small `0x2D00 + d*0x20`, one tile per digit; medium `0x2A80 + d*0x40`, two tiles per digit (second tile = +0x20); large `0x2800 + d*0x40`, two tiles per digit. (For the first hero slot; other slots add a slot offset.) So small digits are one tile tall, medium and large two. What distinguishes medium from large visually (glyph art) was not decoded.

## 9. Validation

`python3 tools/damage_counter.py ROM STATE value type slot` runs the creation routine and then the frame update 98 times and prints phase, hold, colour row and per-slot offsets. The y sequence, phase/step/amp/hold sequence and colour steps are identical for values 1, 7, 25, 123, 250, 999, types D0/D8/E0/E8, slots 0-4, on the save states `.zs2` and `.z10` (12 combinations plus two monster slots) [V].

## 10. Not determined

- Pixel size of the glyphs (8x8 vs 8x16 tiles, and the artwork difference between medium and large). The OAM size select register (`$2101` at `$C0:2819`, `$C6:4037`) was not traced; digit slots are 8 px apart, body parts 16 px.
- What `E022` corresponds to on screen (the sprite art was not examined).
- Exact real-time ordering between the hit-reaction event and the counter event (harness showed +1 combat tick).
- Whether the palette staging slot `E0FA` aliases a colour range of the creature itself.
- Gating variables `$52`, `$FF`, `$F1`, `$E8`, `$D0`, `$D4`, `$3A` were not given meanings.

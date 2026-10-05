# Sound effects: request protocol, sound driver, rendering

How the game asks for a sound effect, where the SPC700 sound driver, the effect table and the samples come from, and how every effect was rendered to a WAV file from the ROM alone. Tags: **[V]** = executed or measured, **[C]** = read from the disassembly (SPC700 code read with `tools/spc700.py`, 65816 code with `tools/disasm65.py`), not executed. Unknowns are in the last section.

No audio is stored in this repository: `tools/sfx_extract.py` refuses to write inside it and everything it writes (WAV, `.spc`, JSON) goes to a directory of your choice outside it. Numbers below are measurements (durations, levels), not game data.

Tools: `tools/sfx_extract.py` (everything), `tools/spc700.py` (SPC700 opcode table and disassembler). They need the ROM path as first argument; a save state is optional and only used for a cross-check. libgme (`libgme.so.0`, used through `ctypes`) must be installed; numpy is not needed.

```
python3 tools/sfx_extract.py ROM OUTDIR [--ids all|0x99,0x32] [--pan 0x77] [--state STATE] [--keep-gain]
python3 tools/sfx_extract.py ROM OUTDIR --dump-spc 0x99      # write sfx_99.spc (for any SPC player)
python3 tools/sfx_extract.py --selftest                       # checks the libgme gain with a hand-computed voice
python3 tools/spc700.py RAM.bin 0CAF 40                       # disassemble a 64 KiB APU RAM image (.spc bytes 0x100-0x100FF)
```

## 1. Summary

- The 65816 asks for an effect with `JSL $C3:0004` after filling `$1E00..$1E03` (`$1E00` = 2, `$1E01` = effect id, `$1E02` = parameter, `$1E03` = pan byte). The routine sends the three bytes to APU ports 1-3 and the command to port 0 with an echo handshake [C]. The effect id is simply the byte the animation scripts and game code pass; no mapping table is involved on the 65816 side.
- The SPC700 driver, the effect table (256 entries), the effect sequences and the 11 BRR samples the effects use are uploaded once at boot from six blocks in bank `$C3` [V: identical to the APU RAM of seven save states]. Effects need nothing that the music loader adds later [V, with one caveat in section 6].
- Rendering: the six blocks are put at their APU addresses, a `.spc` is built that starts at the driver entry (0x0200), a 30-byte stub injects the request, and libgme plays it [V]. **192 of the 193 ids that have a sequence are audible (0x8A produces nothing); 64 of the 256 requests are silent.** Three built-in sequences (commands 0x10-0x12) were rendered too.

## 2. The request, 65816 side [C unless noted]

| item | value |
|---|---|
| entry | `JSL $C3:0004` (a `JMP $0160`); `$C3:0000` is the boot upload |
| request block | `$1E00` command, `$1E01`, `$1E02`, `$1E03` (direct page is set to `$1E00` inside the routine) |
| `$1E00` = 0 | nothing |
| `$1E00` = 1 | start music `$1E01` (loads the song data and instrument sets with a triple-byte block protocol; not needed for effects) |
| `$1E00` = 2 | **sound effect**: `$1E01` = id, `$1E02` = parameter, `$1E03` = pan byte |
| `$1E00` = 3..0x6F, >= 0x80 | passed unchanged to ports 0-3 (`$C3:059F`) |
| `$1E00` = 0x70 + n | rewritten to "start music n" with ports 2/3 = 0x08, 0x0F (`$C3:05F3`, 16 rows) |

Effect requests from the game seen in the weapon runs [V from `data/glove_attacks.json`, `data/weapons_*.json`]: `$1E00` = 2, `$1E01` = the id of the animation op `0xF9`, `$1E02` = 0, `$1E03` = a byte with both nibbles equal (0x33, 0x44, ..., 0xCC; 0x77 is the most frequent). The hit sound 0x35 is requested with `$1E02` = 0x0F and `$1E03` = 0x50 or 0x60. The routine `$C0:BB11` builds the replicated byte (`$0119` = high nibble of an object byte `$E020` in both nibbles) [C].

Port protocol (`$C3:059F`) [C]: write port 1 = `$1E01`, port 2 = `$1E02`, port 3 = `$1E03`; wait while port 0 reads back the command byte (previous message still acknowledged with the same value); write port 0 = command; wait until port 0 reads back the command (the driver echoes it); write port 0 = 0.

## 3. Boot upload and APU RAM layout [V]

`$C3:0000` is run once [C for the protocol, V for the result]. It waits for the SPC IPL signature 0xBBAA on ports 0/1, then uploads six blocks with the standard IPL transfer (destination on ports 2/3, one byte per round trip on port 1, counter on port 0) and finally starts the program at APU address 0x0200. Block table: pointers (offsets inside bank `$C3`, 6 words) at `$C3:0008`, APU destinations (6 words) at `$C3:0014`; each block starts with its length (word). Resulting layout:

| APU address | length | content |
|---|---|---|
| 0x0200 | 0x1398 | the sound driver (code and its tables); entry point 0x0200 |
| 0x1800, 0x1880 | 0x18 each | two small tables (purpose not determined) |
| 0x1900 | 0x2C | BRR sample directory, 11 entries (DIR register = 0x19); start addresses 0x4800-0x4D61 |
| 0x2C00 | 0x1C00 | effect table (256 x 4 bytes, 0x2C00-0x2FFF) followed by the effect sequences (0x3000-0x47FF) |
| 0x4800 | 0x5F1 | BRR sample data of the 11 samples |
| 0x4DF1 on | - | free after boot; the 65816 music loader puts song data and instrument sets here (pointer starts at 0x4800 + the length of the last block) |
| 0xEA00-0xF9FF | 0x1000 | echo buffer (the driver sets EDL = 2, ESA = 0xEA and clears it at start) [C] |
| 0xFA00-0xFFFF | | per-track runtime arrays of the driver |

The six boot blocks equal the APU RAM of all seven ZSNES states available, byte for byte (the RAM is at file offset 0x30C13 of a v143 state, right after WRAM and VRAM) [V]. The save states also contain music data above 0x4DF1 that the boot upload does not have (section 6).

## 4. The driver and the effect request, APU side [C]

Main loop: after initialising the DSP (master volume 0x7F, echo, directory), the driver loops at 0x0279: `CALL $0CAF` (command reader), wait for the timer-0 tick, update tracks. The command reader takes port 0:

| port 0 | action |
|---|---|
| 0 | nothing |
| 1 | start music (`$0CF1`) |
| **2** | **effect**: copies ports 1-3 to `$B5..$B7`, jumps to `$0E10` |
| 0x10-0x1F | start the built-in sequence number (cmd - 0x10) from a 16-entry pointer table at 0x153B; only entries 0, 1, 2 are non-zero (`$0EF6`) |
| >= 0x80 | table-driven handlers (`$0FF9`, table at 0x14B2; not decoded) |

Effect start (`$0E10`): `$2C/$2D` = 0x2C00 + 4 x id. The 4 bytes are two 16-bit pointers to sequences; a pointer is used when its high byte is non-zero, so an effect has 0, 1 or 2 tracks. The driver allocates effect tracks from the top (`X` = 0x1C, 0x1E in `$0E4C`, `$0F11`) [C]; measured: every effect plays on DSP voices 6 and 7 only (one track = voice 7) [V]. In the 256-entry table 193 entries have at least one pointer, 63 are empty. A parameter low nibble in port 2 (0x0F for the hit sound) makes the driver look for an effect with the same id already running and reuse its track (`$0FCE`) [C, not run]. Port 3: both nibbles feed the pan/volume split (`$0F91`); measured: the **high nibble** sets the left/right balance and the low nibble changes nothing (0x77 and 0x73, 0x00 and 0x07 render identically); 0x00 gives equal left and right, 0x77 is slightly left (left/right peak ratio 1.27 for 0x99), 0xCC clearly right [V].

## 5. Rendering procedure [V]

1. APU RAM = the six blocks at their destinations (`boot_ram`).
2. `.spc` file (header 0x100 bytes, RAM, 128 DSP registers = 0): SPC700 PC = 0x0200, SP = 0xEF, IPL ROM off. The driver initialises the DSP itself.
3. The driver clears the ports at start (`MOV $F1,#$F0` at 0x0248) [C], and a file with a request in the port bytes rendered silence [V], so a request cannot be pre-loaded in the port bytes of the file. A stub (30 bytes) in a free page (0x2800) is called instead of the first `CALL $0CAF`: it restores that call, writes the four port values to `$B4..$B7` and jumps to the effect handler `$0E10` (built-in sequences: `X` = command, `$0EF6`). This replaces the reading of the ports and the echo handshake; everything after that point is the driver's own code. The tool checks that the driver is at the expected addresses before patching.
4. libgme (game-music-emu 0.6.4) runs it at 32000 Hz stereo for 30 s (no music is loaded, so only the effect sounds). libgme multiplies the DSP output by 1.4: `--selftest` runs a voice with a constant BRR block and compares libgme with the hand-computed DSP value (ratios 1.398-1.401) [V]; the tool divides it out (use `--keep-gain` to keep it). No filter is applied by libgme (a constant level stays constant) [V].
5. The sound ends at the last sample with absolute value > 2 (libgme scale); the file is cut there. Effects that still sound in the last 5 s are marked looping and written truncated to 10 s (ids 0x12, 0x1E, 0x22). No normalisation, no resampling, no leading trim (the first sound starts 4-29 ms after the request: driver start-up plus the next timer tick, 10.6-10.8 ms for most).
6. Voices used are found by muting seven of the eight voices (libgme honours the mask only when set before the track starts) and checking for output.

Output (outside the repo): `sfx_<id hex>.wav` (16-bit, 32000 Hz, stereo, pan byte 0x77, the value most requests use), `cmd_10/11/12.wav` (the built-in sequences), `index.json` (request bytes, tracks, duration, onset, peak, left/right peak, voices, looping), `contact_sheet.txt`. A second run with `--pan 0x00` gives left = right.

ffmpeg can play the same `.spc` (`ffmpeg -i x.spc -sample_rate 32000 out.wav`, libgme demuxer) and gave sample-identical output for id 0x99, but it stopped after 2.1 s in that test (the effect ends at 0.11 s; presumably libgme's silence detection) and keeps the 1.4 gain.

### Checks
- Boot-built RAM vs the RAM of a save state taken in play: **250 of 256 ids render sample-identical**; the other six (0x40, 0x9E, 0xB0, 0xB1, 0xC5, 0xC8) differ only through two driver variables, `$FDDE` and `$FDDF` (bisected: copying only these two bytes from the state changes the render; copying the whole 0xFA00-0xFFFF area makes all six identical). They hold a leftover value of the last effect track that the effect start does not reset (`$FDDE` = `!$FDC0+X` and `$FDDF` = `!$FDC1+X` with X = 0x1E, accessed at 0x041F, 0x0446, 0x0AD6, 0x0B47 [C]); after boot they are 0, which is what the files use [V].
- Per-voice peaks of those six are equal in both renders; the waveforms differ in detail.
- Plausibility (no reference recording was available): the swing 0x99 is a low-pass noise burst (spectral flatness 0.08, centroid 1.6 kHz, 0.113 s), the hit 0x35 a broadband noise burst (flatness 0.74, centroid 5.9 kHz, 0.277 s), 0x28 ("stage reached") a short high tone (peak at 5.4 kHz, 0.077 s). The levels are in the range 3000-17000 of 32767 [V as measurements, not as proof of fidelity].

## 6. Sound ids used by the attacks (durations of the rendered effect)

| id | duration (s) | tracks | used by (from the weapon documents) |
|---|---|---|---|
| 0x99 | 0.113 | 2 | glove normal swing variants 0, 1 and the nine hits of the stage-8 flurry |
| 0x32 | 0.171 | 2 | glove normal swing variants 2, 3 and the N pieces of the charged attacks |
| 0x0B | 0.113 | 2 | class 1/2 dash prefix; spear normal swing id 2 |
| 0x33 | 0.260 | 2 | glove stage-2 final piece |
| 0x1B | 0.335 | 1 | glove stages 3-6 and 8 jump/spin pieces (every 20 frames in stage 6); spear normal ids 0, 1 |
| 0x1C | 0.153 | 2 | glove stage-5 first piece; spear stage 7; whip stages 3, 8 |
| 0x3E | 0.153 | 2 | glove stage 7; whip stages 1, 7 |
| 0x46 | 0.567 | 2 | glove stage 7 |
| 0x35 | 0.277 | 2 | hit on a target (requested with `$1E02` = 0x0F, `$1E03` = 0x50/0x60); rendered with those bytes |
| 0x26 | 0.109 | 2 | gauge empty |
| 0x27 | 0.342 | 2 | charge hum, every 8 frames |
| 0x28 | 0.077 | 2 | charge stage reached |
| 0x04 / 0x02 / 0x03 | 0.230 / 0.167 / 0.166 | 2 / 1 / 2 | sword normal swing ids 0 / 1 / 2 (0x02 also spear and boomerang throw, 0x03 sword stages) |
| 0x08 | 0.488 | 2 | axe normal swing and stages 1-8 |
| 0x18 / 0x19 | 0.140 / 0.459 | 2 / 2 | 0x18: sword, axe and spear charged attacks; 0x19: spear charged attacks |
| 0x24 | 0.264 | 1 | whip strike |
| 0x47 / 0x09 / 0x0A | 0.171 / 0.298 / 0.077 | 1 / 1 / 2 | bow draw / release / end |
| 0x25 | 0.800 | 1 | boomerang throw |
| 0x4C, 0xAA | 0.171, 0.153 | 2, 2 | seen in the recorded runs (`data/`), `$1E03` 0x55/0x66 and 0x44-0x66 |

Not an effect: 0x62 is silent (no sequence in the table), 0x70 is audible (0.758 s); 0xEF (named in `docs/hero-movement.md`) is silent.

### All audible effects, duration in seconds (`*` = still sounding after 30 s, rendered 10 s)

```
00 0.445  01 0.189  02 0.167  03 0.166  04 0.230  05 2.176  06 1.987  07 0.691  08 0.488  09 0.298  0a 0.077  0b 0.113
0c 0.077  0d 0.095  0e 0.260  0f 3.210  10 5.748  11 0.174  12 *      13 0.306  14 0.306  15 0.644  16 2.284  17 0.881
18 0.140  19 0.459  1a 0.533  1b 0.335  1c 0.153  1d 1.052  1e *      1f 1.103  20 1.166  21 0.131  22 *      23 1.812
24 0.264  25 0.800  26 0.109  27 0.342  28 0.077  29 0.077  2a 0.707  2b 0.878  2c 0.834  2d 0.572  2e 1.803  2f 0.707
30 0.261  31 1.689  32 0.171  33 0.260  34 1.014  35 0.277  36 0.434  37 0.207  38 0.284  39 0.054  3a 0.171  3b 0.266
3c 0.131  3d 0.131  3e 0.153  3f 0.918  40 1.436  41 0.459  42 0.153  43 0.800  44 0.113  45 0.207  46 0.567  47 0.171
48 1.244  49 0.915  4a 0.879  4b 0.230  4c 0.171  4d 1.494  4e 1.276  4f 0.222  50 0.533  51 0.140  52 0.647  53 0.689
54 0.230  55 0.476  56 1.568  57 1.330  58 0.265  59 0.265  5a 0.712  60 0.265  68 0.110  69 0.110  6a 0.722  6b 0.722
6f 0.027  70 0.758  71 1.835  72 0.131  73 0.223  80 1.488  81 1.334  82 0.303  83 1.671  84 3.755  85 2.736  86 0.518
87 1.605  88 0.153  89 5.559  8b 0.036  8c 0.935  8d 0.838  8e 0.572  8f 1.467  90 1.142  91 2.038  92 1.935  93 0.685
94 0.306  95 0.680  96 0.913  97 0.918  98 0.990  99 0.113  9a 0.912  9b 0.913  9c 0.999  9d 1.526  9e 1.026  9f 1.452
a0 1.674  a1 2.513  a2 0.996  a3 0.705  a4 0.394  a5 2.544  a6 1.066  a7 0.562  a8 0.337  a9 1.094  aa 0.153  ab 0.189
ac 0.890  ad 3.196  ae 2.603  af 1.378  b0 3.102  b1 1.141  b2 1.018  b3 4.137  b4 1.225  b5 1.837  b6 3.835  b7 2.887
b8 2.373  b9 1.064  ba 1.239  bb 0.533  bc 0.377  bd 1.995  be 0.748  bf 0.342  c0 0.590  c1 1.108  c2 1.970  c3 2.136
c4 2.460  c5 1.805  c6 1.662  c7 2.222  c8 0.904  c9 1.908  ca 1.958  cb 0.222  cc 1.249  cd 1.055  ce 1.262  cf 1.355
d0 0.401  d1 3.452  d2 2.832  d3 1.206  d4 1.148  d5 1.736  d6 1.244  d7 0.930  d8 1.108  d9 0.359  da 1.309  db 12.891
cmd 0x10 0.077   cmd 0x11 0.131   cmd 0x12 0.260
```

Silent: 0x5B-0x5F, 0x61-0x67, 0x6C-0x6E, 0x74-0x7F, 0x8A, 0xDC-0xFF. All of them have an empty table entry except 0x8A, whose table entry points to a sequence that produces no output (63 empty entries, 1 non-empty silent).

## 7. Open questions

- **Looping effects**: 0x12, 0x1E and 0x22 never end by themselves (0x1E has a repeating pattern with 1 s gaps); how the game stops them (a stop command through ports, command >= 0x80?) was not determined, and neither were their loop lengths.
- **Stale variable**: six effects read `$FDDE/$FDDF`, which keeps a value from earlier effects; in play it is not always 0, so their sound in the game can differ slightly from the files (which use the boot value 0). What the variable is (a per-track value written at 0x041F/0x0446 and used at 0x0AD6/0x0B47) was not decoded.
- **Instrument sets**: the music loader adds instruments above 0x4DF1. No effect was found to use them (250 ids identical with a save state that has a set loaded; the remaining six differ because of the stale variable), but the instrument numbers used by the sequences were not decoded, so this is an observation, not a proof, for save states with other sets.
- **libgme is an emulator**, not the hardware: the Gaussian interpolation, envelopes, noise and echo are as libgme implements them. The 1.4 gain was measured on one kind of voice (constant BRR, GAIN mode) and divided out as a constant; no recording of the console was available to compare.
- The effect request injection skips the port reading and handshake of the driver (section 5); that path was read, not run.
- The sequence data format (note, instrument, volume commands), the tempo, and which instruments each effect uses were not decoded; only the table layout (two pointers per id) and the track count are known.
- The meaning of port 2 (`$1E02`) beyond "low nibble 0x0F on the hit sound reuses a running effect", the role of the two 0x18-byte tables at 0x1800/0x1880, the table-driven commands >= 0x80 and whether the game ever requests the built-in sequences 0x10-0x12 (or commands 3-0x6F) were not determined.
- Which effect ids the game requests outside the attack code (monsters, menu, map) was not enumerated; the files cover every id of the table.

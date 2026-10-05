# Survey of the ordinary monsters 0x00-0x1F and the choice of the Chobin Hood and the Polter Chair

Tags: **[V]** executed in the interpreter, **[C]** read from the disassembly. Names are decoded from the ROM text block at run time (`tools/names.py`), as in `docs/rabite.md`; the tables of this repository use the ids.

Tool: `tools/monster_survey.py ROM STATE OUT.json` (writes `data/monster_survey.json`). For every id from 0x00 to 0x1F it takes the stat record (`data/monsters.json`), walks the AI script statically (`tools/aidis.py`, all reachable instructions, both branches of every conditional) and counts the opcodes that the Rabite script (id 0, 33 opcodes) does not use. It also **runs** the monster for 8 s in the real frame loop (`tools/ai_sim.py`: the monster is created by the game's spawner in slot 3, hero 0 pinned, the monster 60 px to the right of the hero and on screen, RNG index 1) and counts the commands it issued and whether it used the projectile table (`$7E:D000 + 0x40 * 3 + 0x10 k`). The effort column is a rule on the static numbers only: **low** = at most 4 new opcodes, **medium** = 5-10, **high** = more than 10 new opcodes or more than 300 instructions.

## 1. Table [V for the run columns, C for the static columns]

Columns: id, name, level, HP, Str, Agi, EXP, gold, attack rows (`data/weapons.json`), reachable script instructions, new opcodes (not in the Rabite script), effort, commands issued in the 8 s run with the hero standing 60 px away, projectile table used.

| id | name | lvl | HP | Str | Agi | EXP | gold | rows | instr. | new ops | effort | 8 s run, hero at 60 px | proj. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00 | Rabite | 1 | 20 | 3 | 1 | 1 | 2 | 72 | 215 | 0 | low | move 9, pose 3, swing 1, turn 5 | no |
| 01 | Buzz Bee | 4 | 65 | 8 | 8 | 4 | 11 | 73/74 | 254 | 7 | medium | move 41, pose 1, swing 2, turn 1 | no |
| 02 | Mushboom | 3 | 60 | 7 | 5 | 3 | 7 | 75/76 | 216 | 6 | medium | move 22, pose 1, swing 2, turn 6 | no |
| 03 | Chobin Hood | 7 | 60 | 12 | 2 | 12 | 17 | 77 | 183 | 4 | low | move 1, pose 1, swing 6, turn 63 | yes |
| 04 | Lullabud | 2 | 36 | 5 | 3 | 3 | 8 | 78 | 226 | 10 | medium | pose 96 | no |
| 05 | Iffish | 10 | 140 | 17 | 17 | 35 | 29 | 79/80 | 257 | 8 | medium | move 6, pose 1, swing 3, turn 15 | no |
| 06 | Kid Goblin | 5 | 64 | 15 | 5 | 8 | 14 | 81/82 | 248 | 7 | medium | pose 11 | no |
| 07 | Eye Spy | 8 | 100 | 13 | 1 | 28 | 30 | 83 | 194 | 14 | high | other43 2, pose 3, turn 60 | no |
| 08 | Green Drop | 6 | 40 | 12 | 4 | 10 | 12 | 84 | 223 | 11 | high | move 14, other43 1, pose 2, swing 1, turn 8 | no |
| 09 | Specter | 27 | 200 | 12 | 26 | 330 | 213 | 85 | 209 | 13 | high | pose 96 | no |
| 0A | Blat | 5 | 55 | 6 | 10 | 7 | 10 | 86 | 390 | 18 | high | move 9, pose 1, turn 10 | no |
| 0B | Goblin | 12 | 130 | 21 | 1 | 42 | 60 | 87/88 | 286 | 21 | high | move 2, other43 2, other44 1, pose 3, swing 3, turn 15 | yes |
| 0C | Water Thug | 16 | 145 | 24 | 1 | 77 | 65 | 89 | 293 | 15 | high | move 8, pose 1, swing 4, turn 47 | yes |
| 0D | Polter Chair | 8 | 128 | 12 | 10 | 21 | 22 | 90 | 232 | 3 | low | turn 96 | no |
| 0E | Ma Goblin | 11 | 150 | 24 | 1 | 38 | 36 | 91/92 | 268 | 15 | high | move 26, pose 1, swing 4, turn 36 | yes |
| 0F | Dark Funk | 25 | 100 | 23 | 12 | 268 | 192 | 93 | 227 | 11 | high | move 3, pose 1, turn 9 | no |
| 10 | Crawler | 19 | 100 | 27 | 13 | 124 | 97 | 94/95 | 258 | 12 | high | move 14, pose 1, turn 35 | no |
| 11 | Ice Thug | 57 | 440 | 57 | 49 | 2680 | 2850 | 96 | 297 | 16 | high | pose 1, swing 3, turn 74 | yes |
| 12 | Zombie | 13 | 150 | 12 | 8 | 50 | 48 | 97/98 | 260 | 15 | high | move 12, swing 2, turn 10 | no |
| 13 | Kimono Bird | 20 | 160 | 17 | 25 | 145 | 120 | 99 | 232 | 15 | high | other43 2, other44 1, pose 3, turn 28 | no |
| 14 | Silktail | 17 | 130 | 21 | 36 | 91 | 79 | 100 | 252 | 7 | medium | move 5, other44 1, pose 1, swing 1, turn 6 | no |
| 15 | Nemesis Owl | 18 | 122 | 21 | 21 | 100 | 88 | 101 | 405 | 11 | high | other44 1, pose 1, turn 50 | no |
| 16 | Pebbler | 19 | 186 | 28 | 30 | 125 | 96 | 102/103 | 289 | 5 | medium | move 2, pose 1, swing 1, turn 16 | no |
| 17 | Pumpkin Bomb | 21 | 160 | 22 | 5 | 1 | 12 | 104 | 156 | 6 | medium | move 5, other44 1, other81 1, pose 3, turn 1 | no |
| 18 | Steamed Crab | 18 | 110 | 20 | 20 | 110 | 180 | 105/106 | 242 | 11 | high | other44 1, pose 1, swing 1, turn 2 | no |
| 19 | Chess Knight | 12 | 135 | 22 | 20 | 36 | 38 | 107 | 261 | 10 | medium | move 2, other44 1, pose 2, swing 2, turn 8 | no |
| 1A | Wizard Eye | 32 | 200 | 35 | 22 | 530 | 504 | 108 | 216 | 18 | high | other43 2, pose 3, swing 2, turn 28 | no |
| 1B | Howler | 24 | 190 | 22 | 28 | 240 | 180 | 109 | 220 | 5 | medium | move 11, pose 1, swing 2, turn 19 | no |
| 1C | Robin Foot | 28 | 125 | 32 | 35 | 368 | 240 | 110 | 227 | 14 | high | move 15, pose 1, swing 3, turn 40 | yes |
| 1D | LA Funk | 25 | 100 | 23 | 12 | 265 | 190 | 111 | 241 | 12 | high | move 3, pose 1, turn 6 | no |
| 1E | Grave Bat | 30 | 210 | 32 | 38 | 446 | 258 | 112 | 404 | 20 | high | move 3, pose 1, swing 2, turn 12 | no |
| 1F | Werewolf | 9 | 140 | 15 | 15 | 30 | 36 | 113 | 262 | 11 | high | move 18, pose 2, swing 4, turn 8 | no |

Command kinds: `turn` = command C1 with animation 0, `move` = C1 with animation 1-5, `pose` = command 0x40, `swing` = command 02 (op E8); `other43`, `other44`, `other81` are commands 0x43, 0x44 and 0x81 which only the scripts with undecoded ops issue (not decoded here).

Reading the run column: a monster that issues only `pose` or only `turn` commands in the 8 s stood still. Specter, Lullabud (pose 96) and the Polter Chair (turn 96) did nothing at 60 px: their scripts start with a wait loop (the Polter Chair is analysed in `docs/monster-13.md`; the other two were not analysed). Kid Goblin issued 11 poses and nothing else.

## 2. Sprites on The Spriters Resource

Every one of the 32 monsters has a sheet in the "Enemies" category of the public sprite site for the game (sheets hold two or three monsters each, for example "Chobin Hood & Robin Foot", "Polter Chair, Marmablue & Nemesis Owl", "Buzz Bee & Bomb Bee", "Mushboom, Mushgloom & Matango Residents", "Lullabud & Trap Flower", "Rabite & Silktail"). The pages were read with a browser User-Agent; the sheets were downloaded into a scratch directory outside this repository and are used only by `tools/compare_sheet.py` / `tools/validate_monster_gfx.py` to check the ripped pictures.

## 3. The choice

Requirements: the two monsters must behave differently from each other and from the Rabite (which hops, bites at close range and backs off), must be tractable with the existing tooling and must have sprites on the site; no bosses.

- **Chobin Hood (id 3)** is the only one of the 32 that is a *ranged* attacker with a very small script: 4 new opcodes (6A, 73, BE, DC), 183 instructions, and its swing launches an arrow through the projectile engine that the bow, javelin and boomerang of the heroes use (`docs/weapons-ranged.md` section 3). It keeps its distance (retreats inside 48 px, shoots from 49-64 px, advances while it is farther away). Of the monsters that used the projectile table in the survey (Chobin Hood, Goblin, Water Thug, Ma Goblin, Ice Thug, Robin Foot) it is the one with the smallest script (the others have 14-21 new opcodes).
- **Polter Chair (id 0x0D)** is a *stationary ambusher that leaps*: it turns in place, doing nothing, until the hero is within 16 px or it has been hit, then fights with leaps (jump arc of 20 px height, 30 or 60 frames). It has the fewest new opcodes of all 32 monsters (3: 34, BE, BF); at 60 px it only turns in place (96 turn commands in 8 s), while Lullabud and Specter only issue poses.
- Not chosen: Buzz Bee (flying, 7 new opcodes, a 254-instruction script with a 17-subroutine call tree; a good third candidate), Mushboom (6 new opcodes), Lullabud (10 new opcodes, stationary), Kid Goblin / Specter (stationary at 60 px but 7 and 13 new opcodes).

Chobin Hood and Polter Chair differ from each other (ranged kiter against melee ambusher, 4 against 3 new opcodes, projectile against body box) and from the Rabite (the Rabite has no ranged attack, no dormant state and no leap).

## 4. What the survey does not say

- Whether the 8 s runs show the typical behavior of a monster: the run has one hero in one place; scripts that wait for a condition (Specter, Lullabud, Kid Goblin) were not triggered.
- The commands 0x43, 0x44, 0x81 and the ops behind them (casting, special attacks) are not decoded; a monster that issues them is rated by its opcode count only.
- The effort rule counts opcodes and instructions; it does not know whether an undecoded opcode is simple.

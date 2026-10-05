# som-decomp

Notes and tools for reverse engineering Secret of Mana (SNES, USA): combat and stat formulas, hero and monster tables, status effects, drops, the Dark Lich and other boss engines, and the floating damage numbers.

Every claim in the notes is tagged. **[V]** means the routine was executed in the interpreter in `tools/` and a model was checked against it, or a value was cross-checked against live game objects. **[C]** means it was read from the disassembly, read, not executed. What is not known is listed under "Open questions" in each document and is stated there as unknown.

## Contents

### `tools/`
Python 3, standard library only.
- `cpu65816.py`: a small 65816 interpreter used to run routines from the ROM.
- `disasm65.py`, `flowdis.py`, `aidis.py`, `hsum.py`, `statescript.py`: disassemblers and bytecode decoders (recursive-descent disassembly with M/X tracking, enemy AI bytecode lister, boss state-script decoder).
- `combat_env.py`, `zsnes_state.py`: harness that runs any ROM routine on top of the WRAM of a ZSNES v143 save state.
- `rng.py`, `phys_model.py`, `magic_model.py`, `hero_stats.py`, `weapon_level.py`: Python models of the game's random number generator, physical damage, spell damage, hero stat build and weapon level-up.
- `romio.py`: ROM loader shared by the tools (the ROM path is always the first command-line argument).
- `validate_phys.py`, `validate_magic.py`, `validate_magic_level.py`, `validate_exp.py`, `validate_drops.py`, `validate_status_rules.py`, `validate_boss_attacks.py`, `charge_timing.py`, `status_timing.py`: run the real routines with random inputs and compare them with the models.
- `dump_tables.py`, `dump_gap_tables.py`, `boss_records.py`: write the JSON tables in `data/`.
- `boss_sim.py`, `lich_dump.py`, `lich_sim.py`, `lich_events.py`, `lich_hit_test.py`, `lich_stats.py`, `lich_walk_test.py`: step the boss engine from a save state taken in the Dark Lich arena (map 246); `lich_sim.py` runs the game's whole frame (`$C0:B08C`); the others log its events, inject hits, collect statistics over many seeds and test its walking.
- `vmprobe.py`: runs single enemy AI bytecode handlers (`$C1:251A`) on a synthetic object and script.
- `mb_sim.py`, `mb_anim.py`: run the Mana Beast (boss id 0x7F) through its 21-phase machine with phase/event logging, hero and boss HP tracking, forced dead bit; decode the per-object animation scripts.
- `ai_sim.py`, `ai_ops.py`, `ai_cmds.py`, `rabite_model.py`, `ai_scripts.py`: run an ordinary monster in the real per-frame routine and log its AI bytecode, execute every AI opcode handler on synthetic scripts, measure every command it can issue, check the Rabite decision model against the real handlers, list the scripts of all object ids (`aidis.py` prints the opcode descriptions with `--text`).
- `spell_effects.py`: runs every non-damage spell handler on random caster and target objects and checks a model of each (buffs, statuses, sabers, cures, drains, Wall, Lucid Barrier, Lunar Magic, ...).
- `hero_movement.py`: feeds pad bytes to the real input and movement routines and records hero speeds, running, charging, status slowdowns, wall collision and knockback.
- `damage_counter.py`: runs the damage/heal number routines frame by frame.
- `glove_sim.py`, `glove_attacks.py`, `glove_report.py`: run the whole frame routine with an injected pad word to measure the glove attacks of the three heroes (swing variants, weapon gauge, charge stages, the 24 charged attacks, boxes, damage); `glove_sim.py` is the library, `glove_attacks.py` writes `data/glove_attacks.json`, `glove_report.py` prints tables from it.
- `weapon_attacks.py`, `weapon_report.py`, `rip_weapon_anims.py`: the glove experiments generalised to the sword, axe and spear (real chooser, swings, gauge, charge, the 24 charged attacks per weapon, boxes, damage, spawned objects); `weapon_report.py` merges the runs into `data/weapons_melee.json` and prints tables; `rip_weapon_anims.py` rips the attack animations of any weapon type.
- `ranged_attacks.py`, `ranged_sim.py`, `ranged_report.py`, `rip_ranged_anims.py`: the same experiments for the whip, bow, boomerang and javelin, plus the projectile engine (launch, flight per stage, hit model, piercing and return of the boomerang, hit mask); `ranged_report.py merge` builds `data/weapons_ranged.json`; the ripper also writes the projectiles in flight and the projectile sprites.
- `event_vm.py`: the event (cutscene) virtual machine `$C1:E8D3`: opcode table and static event decoder (no text is printed), and a harness that sends the party through a map transition with the game's own loader and steps the real code frame by frame (VM, text engine, actors, camera, fades, sound requests) from a save state with the three heroes; `dark-lich` writes the Dark Lich arena timeline.
- `event_runs.py`: the cutscenes around the Mana Beast on top of `event_vm.py`: `intro` (event 0x429: maps 255 and 253, from the entry until control returns with the fight running), `ending` (the death sequence, event 0x42F and the whole ending script 0x4FD until the game restarts); it adds 12 object slots, flag and screen-effect observers, palette-fade runs, the world-map-mode loop, a restart hook, snapshots, `decode2` (static listing that knows the staff-roll text segments) and the report builder (`report`, `md`).
- `names.py`, `monster_stats.py`: local decoding helpers (names are decoded at run time and never stored).
- `example_damage.py`: Monte-Carlo examples with the physical model (needs no ROM).
- `gfx_decode.py`, `rip_hero_anims.py`, `hero_frames.py`, `compare_sheet.py`: sprite graphics. Tile, palette and OAM decoding with a PNG writer; a ripper that runs the hero attack code from a save state and records every drawn frame into an output directory outside the repository; a static decoder of the hero animation tables; a pixel comparison of the frames with a sprite sheet you provide.

### `docs/`
- `glove-attacks.md`: the glove attacks (weapon type 0): swing timing and variants, no combo, the weapon gauge `E1ED`, charge stages, the 24 charged attacks, boxes, hits and damage.
- `weapons-melee.md`: the sword, axe and spear attacks (weapon types 1-3): swing timing and variants, no combo, gauge, charge, the 24 charged attacks per weapon with timelines, boxes, hits, damage, no spawned objects, and the ripped animations checked against public sheets.
- `weapons-ranged.md`: the whip, bow, boomerang and javelin attacks (weapon types 4-7): swing timing, the projectile engine (arrows, spears, boomerang), number and range of projectiles per charge stage, hit rules, damage, charge timing, the 32 charged attacks with timelines, and the ripped animations checked against public sprite sheets.
- `rom-combat.md`: damage, hit and crit rules, spells, elements, statuses, level-up, weapon and magic levels, drops, boss attack rows, consumables, timing in seconds.
- `dark-lich.md`: how the Dark Lich is built, its state machine, timing (12.02 ticks/s) and attacks.
- `dark-lich-hands.md`: the Dark Lich hands phase (states 1E-27 with durations, movement, entry rules), the hurt reaction (why it lasts 21 ticks), hit conditions, and actions per phase (`data/dark_lich_hands.json`, `tools/lich_hands.py`, `tools/lich_hands_model.py`).
- `mana-beast.md`: the Mana Beast (boss id 0x7F): tick rate, phase graph with durations and movement, scripted hits, spell AI, hit windows, death and end of the fight.
- `cutscene-engine.md`: the event VM: clock (12.02 Hz steps from the frame body), event id spaces and tables, state bytes, opcode table with lengths and effects, text blocks, actor commands, fades/flash/camera, map change sequence, how events are started.
- `cutscene-dark-lich.md`: the cutscene that plays when the party enters the Dark Lich rooms (maps 245/246): triggers, actors and coordinates at entry, the complete timeline (movements, speeds, animations, camera, fades, flash, music and sound ids, dialog blocks), the Lich spawn and release, dependencies on the party, open questions.
- `cutscene-mana-beast-intro.md`: the scene that starts event 0x429 (flag 0x4E >= 8): map 255 (rumble, red tint, dialog), the change to the Mana Beast arena (map 253), the entry walk, the boss freeze, the four dialog blocks and the instant control returns (frame 3,088, 51.4 s); actors and coordinates at entry, sounds, screen effects, party dependencies, validation against a ZSNES state taken inside the scene.
- `cutscene-ending.md`: the Mana Beast's death sequence (780 frames), event 0x42F and the ending script 0x4FD (25,973 frames, 7 min 12 s): party reset, the world-map-mode interlude, 17 maps with the staff roll (38 text blocks, address and length only), music and sound requests, fades, flags, and how the game ends (`PARTY_CMD` 0x11, a software restart through the reset path).
- `rabite.md`: the Rabite (monster id 0): AI engine tick rate, script opcodes, target acquisition, the full behavior as a state machine in seconds, hit reaction, death.
- `spells-non-damage.md`: the exact effect of the spells that do more than damage: value formula, buff and status timers in seconds, saber, cure, drain, Wall, Lucid Barrier, the weapon change of spells 20 and 23, Lunar Magic, per-level tables.
- `hero-movement.md`: hero walking, running, charging and status speeds in pixels per second, diagonal and facing rules, wall collision box, party limit, knockback.
- `damage-counter.md`: how the floating damage/heal numbers are created, sized, coloured and animated.
- `graphics.md`: how the heroes are drawn (4bpp tile pools, palettes, sprite pieces, animation scripts) and the structure of the glove attack animations.
- `audio.md`: how the game requests a sound effect (`$1E00-$1E03`, `JSL $C3:0004`, APU ports 0-3), the SPC700 driver, effect table and sample layout uploaded at boot, and how every effect id was rendered to WAV from the ROM (`tools/sfx_extract.py`, `tools/spc700.py`; needs libgme), with durations and the ids used by the attacks.
- `sources.md`: public documentation and repositories about the game.

### `data/`
Gameplay-number tables dumped from the ROM (numbers only: no graphics, no text). Each file carries a `source` field with the ROM offsets.
- Raw table bytes, as stored in the ROM: `monsters.json` (29-byte records and drop rows; `unk22` and `flags25` are untouched bytes), `weapons.json`, `armors.json` (`unk9` is an untouched byte), `spells.json`, `boss_attacks.json`, `hero_levels.json`, `items.json` (effect byte), `prices.json`, and the `weapon_level_progress_threshold`, `element_opposite_pairs`, `ai_party_stat_tweak_by_CC7A` and `kill_item_class_table` entries of `misc.json`.
- `dark_lich_timings.json`: Dark Lich state durations in ticks, frames and seconds (12.02 ticks/s), phase and action-gap statistics.
- `mana_beast.json`: phase table of the Mana Beast (handler addresses, ticks, frames, exits, spell table, scripted hit rows).
- `ai_scripts.json` (script entry pointer, opcodes used and CALL targets of every object id), `ai_commands.json` (frames, seconds and displacement of every command the Rabite script issues, and the swing animation by distance).
- `glove_attacks.json`: measured timelines of the glove swings, gauge, charge and charged attacks for the three heroes.
- `weapons_melee.json`: measured timelines of the sword, axe and spear swings, gauge, charge and charged attacks for the three heroes.
- `weapons_ranged.json`: measured timelines of the whip, bow, boomerang and javelin attacks, projectile paths, hit model checks and probes for the three heroes.
- `cutscene_dark_lich.json`: the Dark Lich arena cutscene as measured by `tools/event_vm.py dark-lich`: VM commands with decoded operands, dialog block positions and lengths (no text), sound ids, per-actor movement segments, camera and fade segments, Lich spawn and release instants.
- `cutscene_mana_beast_intro.json`, `cutscene_ending.json`: the Mana Beast intro and the ending as measured by `tools/event_runs.py`: VM commands with decoded operands, dialog block positions and lengths (no text), sound ids, per-actor movement segments (scripted and autonomous), camera, fades, palette fades, flags, boss phases, map loads with sizes and start tiles, the world-map-mode interval, variants by controlled hero and weapon type.
- `spell_effects.json`: per-level constants and value ranges of the non-damage spells, validation counts, timer lifetimes; `hero_movement.json`: measured per-frame displacements for walking, running, charging, statuses, collisions and knockback.
- Decoded from routines that were executed or read: `drops.json`, `item_effects.json` (measured by running the item routine), `weapon_levels.json`, `status_effects.json` (bit masks with the spells, weapon rows and attack rows that set them), `boss_records.json` (static decode plus engine runs).

## Running the tools

You need a dump of your own cartridge: a 2 MiB HiROM image, with or without a 512-byte copier header. Pass its path as the first argument of every tool that reads the ROM. Nothing is read from fixed paths or environment variables.

```
python3 tools/dump_tables.py  /path/to/rom.sfc data
python3 tools/flowdis.py      /path/to/rom.sfc out.txt --auto
python3 tools/statescript.py  /path/to/rom.sfc E8F6
python3 tools/lich_dump.py    /path/to/rom.sfc
python3 tools/aidis.py        /path/to/rom.sfc 0 60 --text
```

Tools that execute ROM routines also need a save state as the second argument. They read the WRAM of a ZSNES v143 save state (file offset 0xC13); the state must come from the same ROM and be taken during play with the party on a map (`event_vm.py` needs the three heroes and no event running). The boss tools (`boss_sim.py`, `lich_*.py`, `validate_boss_attacks.py`) need a state taken in the map-246 arena; `event_runs.py intro` and `ending` need a state in map 246 after the Dark Lich's post-fight event (event flag 0x4E = 8). For example:

```
python3 tools/validate_phys.py /path/to/rom.sfc /path/to/state.zs2 800
python3 tools/boss_sim.py      /path/to/rom.sfc /path/to/arena.zs3 3000 1,2 79,7f
python3 tools/hero_stats.py    /path/to/rom.sfc /path/to/states/*.zs?
python3 tools/event_vm.py      /path/to/rom.sfc decode 4E1             # static listing of an event script (text blocks as lengths only)
python3 tools/event_vm.py      /path/to/rom.sfc /path/to/state.zs3 dark-lich out.json leader=0 md=1
python3 tools/event_runs.py    /path/to/rom.sfc /path/to/state.zs3 intro  out.json leader=0 after=900   # needs a state in map 246 with flag 0x4E = 8
python3 tools/event_runs.py    /path/to/rom.sfc /path/to/state.zs3 ending out.json leader=0 frames=150000  # about 10 minutes
python3 tools/event_runs.py    /path/to/rom.sfc decode2 4FD                                           # ending script, static
```

Per topic (`$R` = your ROM, `$S` = a save state taken during play on a map with the party):

```
python3 tools/glove_attacks.py   "$R" "$S" out.json [section ...]       # all sections take about 25 minutes
python3 tools/glove_report.py    data/glove_attacks.json [normal|gauge|charge|power]
python3 tools/hero_movement.py   "$R" "$S" out.json
python3 tools/spell_effects.py   "$R" "$S" 300 out.json
python3 tools/ai_sim.py          "$R" "$S" 0 30                          # Rabite (monster id 0) for 30 s
python3 tools/mb_sim.py          "$R" "$S" 4400                          # Mana Beast, 4,400 frames
python3 tools/damage_counter.py  "$R" "$S" 25
python3 tools/rip_hero_anims.py  "$R" "$S" OUTDIR                        # frames are written outside the repository
python3 tools/hero_frames.py     "$R" boy 0 0 side
python3 tools/compare_sheet.py   SHEET.png OUTDIR boy                    # needs a sprite sheet you provide
```

The full list of commands and what each validates is in section 19 of `docs/rom-combat.md`.

## License

Copyright (C) 2026 cidwel, released under the GPL v3 or any later version.

The project follows the guidelines of Cidwel's
[LLM Manifesto](https://cidwel.com/blog/llm_manifesto.html).

Secret of Mana is a trademark and work of its owners. This repository contains no ROM data, graphics, music or text from the game, only notes, tools and numeric tables. You must supply your own ROM, dumped from your own cartridge.

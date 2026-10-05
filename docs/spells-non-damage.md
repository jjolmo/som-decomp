# Secret of Mana (USA) - spells that do more than damage

Companion of `docs/rom-combat.md` (same conventions, same object layout, same tick clock). Tags: **[V]** = the real handler was executed in the interpreter (`tools/spell_effects.py`, random caster and target objects, the effect checked against a Python model written from the disassembly; case counts in section 12); **[C]** = read from the disassembly, read, not executed. Names of spells are the ones decoded from the ROM text block at run time; everything else is an id, an address or a mask. Numeric tables: `data/spell_effects.json`.

ROM addresses are `$Cx:xxxx`, object fields are offsets inside the 0x200-byte actor record (`$7E:E000 + slot*0x200`; slots 0-2 heroes, 3-5 monsters). `V` below always means the "spell value" of section 2, `L` the level stored in the cast (`E171`, 0..8), `n` the number of targets of the cast (`E176`, 1..3), `L' = L // n`.

## 0. Summary

Every spell row is 64 bytes at `0x102AD0 + id*64` (`data/spells.json`); the handler is the word at `0x08E801 + id*2` in bank C8. Spells 00 01 06 0C 0D 0E 12 13 1F 25 28 only deal damage (`docs/rom-combat.md` section 5). The others:

| id | name | MP | stat | target flags | handler | what it does | tag |
|---|---|---|---|---|---|---|---|
| 02 | Speed Down | 1 | Int | 81 | EA97 | **status only**, no damage: word 0x0004 (section 4) | [V] |
| 03 | Stone Saber | 4 | Wis | 01 | EAA3 | saber, element bit 0x01 into `E195`, status word 0x0040 into `E199` (section 5) | [V] |
| 04 | Speed Up | 3 | Wis | 01 | EB04 | EVA +25% and ACC +25% buffs, timers `E1BB`/`E1BA` = V>>2 (section 3) | [V] |
| 05 | Defender | 2 | Wis | 01 | EB20 | DEF +25% buff, timer `E1BC` = V>>2 | [V] |
| 07 | Acid Storm | 3 | Int | 81 | EB39 | damage (section 2 formula, element multiplier) and DEF -25% debuff; the 0x2000 word of the row is **not** applied | [V] |
| 08 | Energy Absorb | 2 | Int | 81 | EB54 | HP drain (section 7) | [V] |
| 09 | Ice Saber | 2 | Wis | 01 | EAA8 | saber, element bit 0x04, status word 0x0020 | [V] |
| 0A | Remedy | 1 | Wis | 01 | EB9F | status cure (section 6) | [V] |
| 0B | Cure Water | 2 | Wis | 01 | EBB3 | HP heal V (section 6) | [V] |
| 0F | Flame Saber | 2 | Wis | 01 | EAAD | saber, element bit 0x08, status word 0x4000 | [V] |
| 10 | Fire Bouquet | 3 | Wis | 81 | EBCA | damage and ATK -25% debuff, timer `E1B7` = V>>2 | [V] |
| 11 | Blaze Wall | 4 | Wis | 81 | EBE5 | damage and status word 0x4000 | [V] |
| 14 | Silence | 2 | Int | 81 | EBF4 | **status only**: word 0x0080 | [V] |
| 15 | Thunder Saber | 3 | Wis | 01 | EAB2 | saber, element bit 0x02, no status word | [V] |
| 16 | Balloon | 2 | Wis | 81 | EBF4 | **status only**: word 0x0100 | [V] |
| 17 | Analyzer | 1 | Wis | A0 | EC00 | builds an information message, writes no gameplay field (section 11) | [V] writes, [C] message |
| 18 | Change Form | 5 | Int | 81 | EBF4 | **status only**: word 0x0800; a monster that keeps the bit is replaced by another object (section 4.3) | [V] |
| 19 | Magic Absorb | 1 | Int | 81 | EC3B | MP drain (section 7) | [V] |
| 1A | Lunar Magic | 8 | Int | 81 | EEF5 | one of 8 equally likely random effects (section 10) | [V] |
| 1B | Moon Saber | 3 | Wis | 01 | EABC | saber, element bit 0x40 = the weapon drain flag | [V] |
| 1C | Lunar Boost | 2 | Wis | 01 | ECB5 | ATK +25% and EVA -25% buffs, timers `E1B7`/`E1BB` = V>>2 | [V] |
| 1D | Moon Energy | 2 | Wis | 00 | ECD1 | L'+1 forced critical hits (section 8.3) | [V] |
| 1E | Sleep Flower | 2 | Int | 81 | EBF4 | **status only**: word 0x0010 | [V] |
| 20 | (name in `names.py`) | 1 | Int | 40 | ECEA | first half of a two-spell weapon change (section 9) | [V] |
| 21 | Revivifier | 10 | Wis | 01 | ED04 | revive, cure, heal V/(9-L') (section 6.3) | [V] |
| 22 | Wall | 6 | Wis | 01 | ED53 | blocks the next L'+2 spell hits (section 8.1) | [V] |
| 23 | (name in `names.py`) | 1 | Wis | 40 | ED68 | second half of the weapon change | [V] |
| 24 | Evil Gate | 8 | Int | 81 | ED82 | damage = half of (HP + max HP) / (10 - L') (section 8.2) | [V] |
| 26 | Dispel Magic | 4 | Int | 81 | EDCB | scrubs buffs, saber hits and Wall (section 8.4) | [V] |
| 27 | Light Saber | 5 | Wis | 01 | EAB7 | saber, element bit 0x20, no status word | [V] |
| 29 | Lucid Barrier | 4 | Wis | 01 | EEB7 | absorbs physical damage up to a pool (section 8.5) | [V] |

"stat" is the caster stat the handler uses: spell id % 6 < 3 uses Int (`E18B`), otherwise Wis (`E18C`) (`$C8:E855`). Target flags are the row byte 8 (`docs/rom-combat.md` section 14). No spell of the table summons an actor; the only transformations are Change Form (monsters) and the two-spell weapon change of section 9.

## 1. What every cast does

Entry `$C8:E6D4` runs once per target, called with X = caster object, Y = target object [V, every case of section 12 goes through it]:

1. `E1F8` of caster and target = 0x10 (hit flash timers) [C].
2. **First target of the cast** (all of `E172-E174` are 0xFF): for hero casters the magic level progress `$D0:4DCD` (`docs/rom-combat.md` 11.5), and the MP is paid: `E186 = max(0, E186 - row[15])` (no check here, the check is the cast request `$C0:3F6C`) [V].
3. The target is added to the caster's hit list `E172-E174`; a target already in the list is skipped (a spell hits an actor once per cast) [V].
4. Nothing happens if the caster is dead, or if the target is dead (except spell 21) [C]. For the objects flagged `E1FB` bit 4 (ids 0x55-0x56) a different branch runs (not traced).
5. `$C8:E7A7`: the **pending HP damage word `E1F1` of a hero target and of a hero caster is set to 0** before the handler runs [V]. Hero casters read the spell power from the row (byte 10); monster casters use the record bytes 18/19 (`E1FD`/`E1FE`) [V, both caster kinds in section 12].
6. If `E176` (n) is 0 nothing else happens. Otherwise the handler runs, then a message is built for the buff bits that are new in `E1B0` (`$C0:5921`, display only) [C].

Result: effects land on the pending fields (`E1F1` damage, `E1F3` heal, `E1F5` MP damage, `E1F6` MP heal) or directly on the status, buff and flag fields; `$C0:4004` applies the pending ones on the target's next tick (`docs/rom-combat.md` 5.4).

**Level.** `L = E171` of the caster: hero = nibble of `E1C4..E1C7`; a hero or boss cast at level 8 is stored as 8 only when `(R>>1)+1 < progress` (`progress = E1D8[element index]`, 0..99), otherwise as 7: the chance of 8 is `(progress-1)/128` (0 for progress 0 and 1, 76.6% at 99) [V: `$D0:4EAC` run on all 256 RNG bytes for 7 progress values, 0 mismatches of 1,792]. A monster that is not a boss casts at its record level (8 stays 8) [V].

**Number of targets.** `n = E176` (1..3, `docs/rom-combat.md` section 14). Every handler that builds on V divides V by n; Saber, Remedy, Revivifier, Wall, Moon Energy, Evil Gate and the Lucid Barrier guard use `L' = L // n` instead of `L` [V]. So the same spell cast at all three targets is weaker per target.

## 2. The spell value V

Same arithmetic as the damage spells (`docs/rom-combat.md` 5.2, `$C8:E8C0`), checked on every non-damage handler [V]:

```
stat  = Int (id % 6 < 3) or Wis ;  p = row[10] (hero caster) or record byte 18 / 19 (monster caster)
acc   = min(99, (stat>>2) + 75)
v     = min(999, ((p + stat) & 255) * (L + 2) >> 1)
r = rnd(101);   r >= acc : v = acc * v // 100                          (glancing)
                r <  acc : v = v + E1E6^2 ; v = v + rnd((v >> 4) & 255)
m     = 4 for handlers that force it (the "fixed m=4" ones below), otherwise 1/2/4 from the element test of $C8:E8A0
V     = min(999, ((v * m) >> 1) // n)
```
`m = 4` makes V twice the damage-spell value: Speed Up, Defender, Lunar Boost, Cure Water, Remedy, Revivifier, the three saber kinds, Moon Energy, Wall, spells 20 and 23, Lucid Barrier [V]. Handlers that call the element test (`m` = 1 if the spell element mask hits the target's resist mask `E1A3`, 4 if it hits the weak mask `E1A1`, else 2): Speed Down, Acid Storm, Energy Absorb, Fire Bouquet, Blaze Wall, Silence, Balloon, Analyzer, Change Form, Magic Absorb, Lunar Magic, Sleep Flower, Evil Gate, Dispel Magic [V]. A random number is drawn for the target magic defence roll first (it is used by the damage and drain handlers only).

`data/spell_effects.json` `value_ranges` has V for stats 10..99 in steps of 10, power 61 and 250, `m` = 2 and 4, `E1E6` = 0 and 8, levels 0..8: `[glancing, non-glancing minimum, non-glancing maximum]`. Example, Wis 60, power 61, `m` = 4, `E1E6` = 0 (Cure Water value):

| L | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| V (non-glancing) | 242-254 | 362-382 | 484-512 | 604-638 | 726-768 | 846-896 | 968-999 | 999 | 999 |

`E1E6` is the hero constant of `docs/rom-combat.md` 11.6 (0 at a new game, 8 in all the late-game states: it adds 64 before the multiplication).

## 3. Buffs and debuffs (`E1B0`)

`E1B0` holds eight buff bits in four pairs, each pair with its own timer in "timer units" (section 3.2): DEF `01`/`02` timer `E1BC`; EVA `04`/`08` timer `E1BB`; ACC `10`/`20` timer `E1BA`; ATK `40`/`80` timer `E1B7`. A pair is "up" or "down", never both, because the handlers clear the pair before setting a bit. Effect of the bits in the combat code (`docs/rom-combat.md` 4.2-4.3): `01` defense += defense>>2, `02` defense -= defense>>2, `04` evade += evade>>2 (cap 99), `08` evade -= evade>>2, `40` attack += attack>>2, `80` attack -= attack>>2 [C]. The accuracy pair `10`/`20` changes the hit test by `q` (added for `10`, subtracted for `20`), where `q = E190>>2` of the attacker unless the attacker has status 0x0004, in which case `q = acc>>2` (4.2): for an attacker without status bits the accuracy pair therefore has almost no effect.

### 3.1 Which handler writes what [V]

| id | `E1B0` after (old = value before the cast) | timers (units) |
|---|---|---|
| 04 Speed Up | `(old & C3) \| 14` : EVA up, ACC up (EVA/ACC down bits cleared, DEF/ATK pairs kept) | `E1BB` = `E1BA` = V>>2 |
| 05 Defender | `(old & FC) \| 01` : DEF up | `E1BC` = V>>2 |
| 1C Lunar Boost | `(old & 33) \| 48` : ATK up and **EVA down** (EVA/ATK pairs replaced, DEF/ACC kept) | `E1B7` = `E1BB` = V>>2 |
| 07 Acid Storm | `(old & FC) \| 02` : DEF down (after the damage) | `E1BC` = V>>2 |
| 10 Fire Bouquet | `(old & 3F) \| 80` : ATK down (after the damage) | `E1B7` = V>>2 |

V is the "fixed m=4" value for 04/05/1C and the element value for 07/10. The timer is `(V>>2)` as a byte, so 0..249. The spell hits always land: there is no resist or evasion roll for buffs (V only changes through the random accuracy roll of section 2). A hero target loses its pending damage; a monster target keeps it.

### 3.2 Timer units, lifetimes and seconds [V]
All timers run in the combat tick `$C0:3A79` (`docs/rom-combat.md` 1.3: once per 5 frames, 12.02 ticks/s at 60.0988 Hz). The tick decrements the per-actor counter `E1B9` every time, and only when `E1B9 & 3 == 0` (every 4th tick, 20 frames) it decrements the timers `E1B2/E1B3/E1B5/E1B6` (statuses) and `E1B7/E1BA/E1BB/E1BC` (buffs); a bit is removed when its timer reaches 0 [C, and measured below]. One timer unit = 4 ticks = 20 frames = 0.3328 s.

The first decrement comes 1 to 4 ticks after the cast (it depends on the phase of `E1B9`; the status application routine resets `E1B9` to 5, which makes it exactly 1 tick). So a timer value `t` lives `4(t-1)+k` ticks with `k` = 1..4 (`k` = 1 for statuses) [V: real tick, 8 phases]:

| t | 1 | 2 | 5 | 20 | 125 | 249 | 0 (set without a timer) |
|---|---|---|---|---|---|---|---|
| ticks | 1-4 | 5-8 | 17-20 | 77-80 | 497-500 | 993-996 | 1021 |
| seconds | 0.08-0.33 | 0.42-0.67 | 1.4-1.7 | 6.4-6.7 | 41.3-41.6 | 82.6-82.9 | 85.0 |

Seconds = ticks / 12.0198. A timer of 0 wraps to 255 on its first decrement (lifetime `4*255+1` = 1021 ticks).

Buff durations of the buff spells (Wis 99, power 61, `E1E6` = 0, timer `T = V>>2`): level 0: 80-84 units (26.4-28.0 s), level 1: 120-127 (39.7-42.3 s), level 2: 160-169 (53.0-56.2 s), level 3: 200-212 (66.3-70.6 s), level 4 and up: 240-249 (79.6-82.9 s); with Wis 60 the cap of 249 is reached at level 6-7 (`data/spell_effects.json` has the whole grid). A cast on three targets divides V by 3. A new cast replaces the pair bits and the timers of the pairs it writes (it does not add).

## 4. Status spells (02 Speed Down, 14 Silence, 16 Balloon, 18 Change Form, 1E Sleep Flower, 11 Blaze Wall)

These call `$C8:E88E` (the row's status word -> `$9A`) then `$C8:E301`, the routine validated in `docs/rom-combat.md` 12.2 [V]. The first five do **not** call the damage part: they change no HP. Blaze Wall adds the damage `max(1, V - D)` to `E1F1` (D = the target magic defence roll of 5.2).

- **Application**: `new = status & ~E1AA`, `E1AA` = the target immunity word (monster record bytes 20-21; heroes: OR of the three armor words, always including 0x0800). There is **no accuracy or evasion roll**: the status lands unless the bit is in the immunity word [V]. Only after that does the exclusivity cascade of 12.2 run, so an already present stronger status can remove the new one (for instance 0x0040 > 0x0020 > 0x0010 > 0x0008 > 0x0004 in the low byte).
- **Duration**: `d = max(20, ((V >> 2) - (E1A8 >> 1)) low byte)` with V the spell value of section 2 (not the spell power as a constant): the timer of the group is loaded only for bits that were not set before: `E1B2` for bits `007C`, `E1B3` for `0180`, `E1B5` for `1C00`, `E1B6` for `6000`. Because `d` is at least 20, a status lasts at least 77 ticks (6.4 s); at most 993 ticks (82.6 s) with V = 999 and a magic defence of 0 [V]. `E1A8` is the target's magic defence, so a high magic defence shortens every status spell. A status that is already running keeps its timer (a second cast does not refresh it).
- The status of the spell rows: 02 -> 0x0004 (timer `E1B2`), 1E -> 0x0010 (`E1B2`), 14 -> 0x0080 (`E1B3`), 16 -> 0x0100 (`E1B3`), 18 -> 0x0800 (`E1B5`, heroes are always immune), 11 -> 0x4000 (`E1B6`, also removes 0x2000). A later damaging hit removes 0x0010 (`$C0:5119`).
- **What the bits do** is in `docs/rom-combat.md` 12.1. In this document: 0x0004 lowers the attacker's accuracy by 1/16 (4.2); 0x0100 stops the actor acting (mask C160 in the input handler); 0x4000 costs 1 HP per timer drop and stops the actor acting. The effect of 0x0080 is only seen in the per-tick routine `$C0:3F2C` (section 4.4), whose purpose is not determined.

### 4.3 Change Form (0x0800) on a monster [V]
When `E301` leaves the bit set on a living monster (and the status word has no 0x0020), `$C8:E52F` replaces the monster object id `E180` by `table[R & 7]` (R = the next raw RNG byte, so each of the 8 entries has probability 1/8; table at `$C8:E5F3`: `00 02 04 06 08 0C 16 17`), marks the sprite for refresh, rebuilds the stats from that id (`$C0:4530`: Str, Agi, Int, Wis, evade, defence, element masks, type, weapon rows change; HP is kept) and takes the weapon row of the new id. When the status word has 0x0020 the object id becomes 0x83; in every other case `E52F` puts `E1E7` (the original id) back. `E52F` runs again on every status change of the monster, so a later status application re-rolls the table entry while the bit is still set.

### 4.4 The silence-like status 0x0080 [C]
`$C0:3B19` calls `$C0:3F2C` every tick for an actor with `E190` bit 7 set; `3F2C` copies `$CC6D-$CC6F` into `$EE-$F0` and, for each human-controlled hero with that bit set, XORs 3 into its byte (`$EE + player`). What `$EE-$F0` controls was not traced (section 13).

## 5. Saber spells (03 09 0F 15 1B 27) [V]
Handlers `$C8:EAA3-EABC`. In order: `E19D = 0`, the stats are rebuilt from the equipment (`$C0:4530`, which wipes the previous saber element, status and counter), V is computed with `m = 4` (only to consume the random numbers; nothing else uses it), then

```
E195 |= element bit   (03: 01, 09: 04, 0F: 08, 15: 02, 27: 20, 1B: 40)
E199 |= row status word (03: 0040, 09: 0020, 0F: 4000, 15 / 1B / 27: none)
E19D  = (L' + 1) * 4              # remaining hits
E1AE  = (E1AE & F0) | L'          # level for the damage bonus
CC78/CC79 = 0                     # also cancels a running two-spell weapon change (section 9)
```
- **Hits**: `E19D` is decremented once per weapon hit the hero lands (`$C0:50EF`); at 0 the level nibble is cleared, the stats are rebuilt (element, status and bonus disappear). There is no time limit. L' = 0..8 gives 4, 8, 12, ..., 36 hits.
- **Damage bonus**: `n = E1AE & 15`; when `n != 0` the hit damage gets `+ base // (10 - n)` (`docs/rom-combat.md` 4.3). So level 0 adds nothing, level 1 adds 1/9 ... level 8 adds 1/2 of the pre-buff damage; the figure "n = 1..9, up to +100%" of 4.6 is wrong: `n` is the level 0..8 (maximum +50%).
- **Status**: every landing weapon hit then has the chance `E1F7` (80% for the weapons, `docs/rom-combat.md` 12.4) of inflicting the word in `E199` through the immunity test.
- **Element bits**: `E195` bit 0x01/0x02/0x04/0x08/0x20 are the element bits of the spells, but the physical element test reads the **defender's own** `E194/E195` (4.6 / 6 quirk), so these bits have no effect on weapon damage in the code paths found.
- **Moon Saber** sets `E195` bit 0x40, the weapon drain flag: a hit adds its damage to the attacker's pending heal `E1F3`; if the defender type byte has bit 0x20 the roles are swapped (the attacker takes the damage, the defender is healed) [V: weapon hit on a monster with the flag: damage 390, heal 390; with type bit 0x20: 390 damage on the attacker, 390 heal on the defender; flags 0x04 and 0x20 change nothing].

## 6. Heal and cure spells

### 6.1 Cure Water [V]
`E1F3 += V` (`m = 4`, no defence). The pending heal is applied capped at 999 and at max HP (`docs/rom-combat.md` 5.4). V per level as in section 2 (Wis 60: 242-254 at L = 0, 726-768 at L = 4, 999 from L = 7). With three targets each gets V/3.

### 6.2 Remedy [V] (also the first half of Revivifier)
```
E191 &= ~0x02                                  # removes status 0x0200 whatever the level
if L' == 8 or (L' >= 4 and n == 1):            # full cure
    E1B2..E1B6 = 1 ; E190 &= 0x8400            # keeps the dead flag 0x8000 and 0x0400; clears 0x0003 as well
else:
    a = (V >> 2) & 255 ; E1Bk = max(1, E1Bk - a)   for k = 2..6 ; E190 unchanged
```
So below level 4 (or when cast on several targets) Remedy only shortens every running status by `V>>2` units, and the status ends at the next timer drop if its timer reaches 1; 0x0200 has no timer and is always removed. The status words are not tested for "is present": the timers are lowered anyway. Remedy has no healing and no revive effect.

### 6.3 Revivifier [V]
Only a target with `E1FB & 0xC0` (a hero or a boss) is affected; for anything else the handler returns at once (the MP is still paid). It is the one spell that may target a dead actor. Order: `E191 &= ~0x02`, the same cure as 6.2 (with the same L' rule), then

```
E191 &= 0x7F                      # alive again
E1F3  = V // (9 - L')             # pending heal (V with m = 4 and the division by n)
if E182 == 0 : E182 = 1           # HP becomes 1 now, the heal is applied on the next tick
E1F1  = 0
```
The heal is therefore `V/(9-L')`: 9, 8, 7, ... 1 as L' = 0..8. With Wis 60 and E1E6 = 0 (non-glancing): 26-28 HP at L = 0, 45-47, 69-73, 100-106, 145-153, 211-224, 322-333, 499, and 999 at L = 8; with Wis 99: 35-37, 60-63, 91-96, 133-141, 192-199, 249, 333, 499, 999 (`data/spell_effects.json` has the grid). A living target is healed the same way.

## 7. Drain spells [V]
Both call the element test, so the element multiplier (x0.5, x1, x2) is part of V (section 2), and both use the target magic defence roll D (5.2).

**Energy Absorb (08)**:
```
if target type byte (E192) & 0x20 : roles swap and D is rolled again with the CASTER's magic evade/defence
a = V - D ; if a <= 0 : a = 1 ; a = min(a, current HP E182 of the source)
source E1F1 = a (pending damage, replaces the word) ; destination E1F3 += a
```
Normally source = target, destination = caster; with the type bit 0x20 (the same bit that reverses the weapon drain) the caster loses the HP and the target gains it. The cap is the current HP of the source, so a drain can never be larger than the HP the source has. The healed side is capped at its max HP and 999 when the pending value is applied.

**Magic Absorb (19)**: `a = max(V - D, 0) // 10`, at least 1, at most the MP of the source (`E186`, after the MP cost of the cast was paid when the source is the caster). Source `E1F5 += a` (pending MP damage), destination `E1F6 += a`; the source is the target unless the target type byte has bit 0x40 (then it is the caster) [V]. Pending MP values are applied capped at 99 (`docs/rom-combat.md` 5.4).

Examples (Int 60, power 43, m = 2, E1E6 = 0, non-glancing): V = 103-108 at L = 0 ... 515-546 at L = 8, so Magic Absorb takes at most (V-D)/10 = 10 .. 54 MP before the source MP and defence limits.

## 8. Other defensive and utility spells

### 8.1 Wall (22) [V]
Handler: `E1B1 |= 0x40`, `E1B8 = L' + 2` (2..10), no V use. The block itself is in the spell hit wrapper `$D0:4C82` (stub `$C0:3866`), which calls `$C8:E6D4` for a normal hit [V, executed as a unit; the callers of the wrapper were not traced, open question 1]:

- a spell whose **target list** contains the Wall holder consumes one point of `E1B8` per hit (when it reaches 0, `E1B1` bit 6 is cleared), whoever cast it and whatever the spell does (damage, status, heal, buff);
- spells **20, 23 and 26** bypass it (they are not counted and not blocked);
- physical hits are unaffected;
- after counting, the wrapper tries up to 3 candidates among the three actors of the side opposite to the Wall holder (random order, 4 possible orders): an actor that exists (`E000 == 1`), is alive, has `E1FB & 0x30 == 0`, `$ED` bit 7 set (always in play) and is within `|dx| + |dy| < 0xF0` pixels of the Wall holder. If one is found the wrapper returns `A = 0xFF`, `X` = that actor's object base and applies nothing to the Wall holder or to the candidate; otherwise it returns `A = 0`, `X = 0` and the spell hits the Wall holder normally (the point was still consumed) [V: monster caster at distance 100 -> A = 0xFF, X = 0x0600, no damage; at distance 300 -> A = 0, damage applied].
- the code that receives `A = 0xFF` / `X` was not found (open question 1).

Data: `wall_wrapper` in `data/spell_effects.json` (the only candidate in those rows is the caster itself, so "candidate dead" there means a dead caster).

### 8.2 Evil Gate (24) [V]
`E1F1 += ((E182 + E184) >> 1) / (10 - L')` (word division; HP and max HP of the target), `1` instead when the target has `E1FB` bit 6 (boss). No defence, no minimum other than the boss case; the pending value is capped at 999 when applied. L' = 0..8 divides by 10, 9, ... 2: at full HP 1000 the damage is 100, 111, 125, 142, 166, 200, 250, 333, 500. The value V of the handler (and its element test) is computed and discarded.

### 8.3 Moon Energy (1D) [V]
`E1AE = (E1AE & 0x0F) | ((L' + 1) << 4)`: the next L'+1 weapon hits of the target are **forced critical** (the high nibble is decremented per hit and a non-zero nibble forces the crit, `docs/rom-combat.md` 4.3), also while the weapon gauge is not empty. Target flags 00 (the caster).

### 8.4 Dispel Magic (26) [V]
Clears the target's charge stage (`E19B = 0`), computes V (element multiplier), sets `E1FA` bit 2 (refresh), then

```
if L == 8 or (L >= 4 and n == 1):              # note: raw L, not L'
    E1B7 = E1BA = E1BB = E1BC = 1 ; E19D = 0 ; E1B8 = 0
else:
    a = max(0, (V >> 2) - (E1A8 >> 1)) low byte
    E1B7,E1BA,E1BB,E1BC = max(1, t - a)  ; E19D = max(0, E19D - (L+1)*4) ; E1B8 = max(0, E1B8 - (L+2))
if E1B8 == 0 : E1B1 &= ~0x40                    # Wall gone
if E19D == 0 : stats rebuilt (the saber element/status/bonus disappear)
```
The buff bits stay set until their timer reaches 0 (at most 4 ticks later when it was set to 1). Dispel does not touch the Lucid Barrier (E1B1 bit 4) or statuses, and it passes through a Wall.

### 8.5 Lucid Barrier (29) [V; the absorbing code `$C0:4004` / `$C0:541B` executed]
```
E1B1 |= 0x10
E1BD = min(V, E184)                    # absorb pool (word, V with m = 4)
E1BF = ((E1A5 >> 1) // n) low byte     # flat guard per hit: the target's defence / 2 / number of targets
```
While `E1B1` bit 4 is set: every **weapon** hit on the target (the last attacker index `E1F0` is 0..5) has its damage reduced by `E1BF` with the target's normal defence ignored (`$C0:541B`), and the remaining damage is taken from the pool `E1BD` instead of from HP; the target's pending damage is cleared. The barrier ends (bit cleared) when the pool reaches 0; the part of a hit that is larger than the pool is lost. **Spell hits** (`E1F0` = 0xFF) ignore the barrier completely and do full damage. There is no timer [V: guard 10 / pool 100 / hit 104 -> hit 94, pool 6, HP 500; pool 30 -> pool 0, barrier off, HP 500; the same hit as a spell: HP 406, pool unchanged]. Pool and guard per level follow V (grid in the json) and the target's defence.

## 9. Spells 20 and 23: the two-spell weapon change [V]
Two spells with the same name in the ROM text (id and address are used here instead), row power 250, MP 1, both with target flags 0x40. Handlers `ECEA` / `ED68`: they do nothing unless the weapon type of hero slot 0 (`E1E4`, the absolute address of the first hero) is 1; then `E19D = 0` (slot 0), V with `m = 4`, and `$CC78 = V>>2` (spell 20) or `$CC79 = V>>2` (spell 23). The power byte wraps (`(250 + stat) & 255`), so with Int 60 the value is that of a power-54 spell. In `$C0:3F94` (the step after the cast), when `$CC78` and `$CC79` are both non-zero: the weapon row of hero 0 `E1E8` is saved in `$CC77` (unless it is already row 17) and **set to row 17**, the stats are rebuilt. Hero 0's combat tick then decrements `$CC78` and `$CC79` once per timer drop (every 4 ticks), and when either reaches 0 `$C0:3C88` puts `$CC77` back into `E1E8` and rebuilds [V: timers forced to 3 -> the weapon row came back after 9 ticks = 4*(3-1)+1].

Observed: any Saber spell clears `$CC78/$CC79` (`STZ $CC78` as a word) without calling the restore, so the weapon row stays at 17 after the timers are gone (`weapon_change_20_23` rows of the json: after `Stone Saber` the row is still 17). Whether another routine restores it later (for instance the equipment screen) was not traced.

## 10. Lunar Magic (1A) [V]
Handler `EEF5`: `E8A0` + `E8C0` (random draws, V), then `i = rnd(8)` (0..7, each 1/8) selects a routine of the table at `$C8:EF19`; the table has a ninth entry (halves the caster's maximum MP byte `E187`) that `rnd(8)` can never select.

| i | effect | tag |
|---|---|---|
| 0 | `E1F3 = E184` (pending full heal) for every living actor in slots 0-5, **monsters included** | [V] |
| 1 | the target gets `E1B0 = 0x55` (all four "up" bits) and the four timers `E1B7 E1BA E1BB E1BC` = V>>2 | [V] |
| 2 | the target gets `E1B0 = 0xAA` (all four "down" bits), same timers | [V] |
| 3 | `E190 \|= 0x80` (status 0x0080) on all six slots | [V] |
| 4 | `E191 \|= 0x10` (status 0x1000) on all six slots | [V] |
| 5 | `E191 \|= 0x02` (status 0x0200) on the three heroes | [V] |
| 6 | `E191 \|= 0x08` (status 0x0800) on the monster slots 3-5 | [V] |
| 7 | `E190 \|= 0x10` (status 0x0010) on all six slots | [V] |

Effects 3-7 write the status bit directly: no immunity test, no cascade, no timer is loaded; the bit leaves when the timer of its group (whatever value it holds, 0 if none ran) reaches 0, i.e. 1021 ticks (85.0 s) from a zero timer for 0x0080, 0x1000, 0x0800 and 0x0010, and **never** for 0x0200 (no timer exists for it; it is removed by Remedy, Revivifier and the consumable that toggles it) [V: real tick]. Distribution over 300 random casts: 38 / 30 / 29 / 39 / 48 / 28 / 52 / 36.

## 11. Analyzer (17) [V writes, C message]
Handler `EC00`: for objects with `E1E7 >= 0x83` nothing happens; for object id 0xEA (`E180`) it instead compares the low nibble of byte 1 of the table row at `$D0:3A50 + E1CA*5` with the cast level and, when that is not larger than the level, sets the low byte of the maximum HP `E184` to 0xFF (purpose not determined); for every other object it runs `$C0:599D`, which builds a text message: current HP and max HP, MP and max MP, for non-hero targets the EXP reward (word `E18D`) and the gold (`E1C8`), then one text per set bit of the weak-element mask `E1A1`, in bit order 7..0. **No gameplay field is written** besides the common bookkeeping (hit list, MP, level progress, `E1EC`, `E1F8`, and `E00A` for boss-flagged targets): 100 random casts compared before/after over all six objects [V]. The spell has no resist or evasion roll.

## 11b. Per-level constants (L = 0..8 as stored in the cast; `data/spell_effects.json` `per_level`)
The level-up message prints the stored nibble itself (`docs/rom-combat.md` 11.7), so these are the "levels" of the game; `L'` replaces `L` when the cast has several targets.

| L' | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Saber hits (4(L'+1)) | 4 | 8 | 12 | 16 | 20 | 24 | 28 | 32 | 36 |
| Saber bonus, fraction of the base hit (1/(10-L')) | none | 1/9 | 1/8 | 1/7 | 1/6 | 1/5 | 1/4 | 1/3 | 1/2 |
| Wall: spell hits blocked (L'+2) | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| Moon Energy: forced critical hits (L'+1) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| Evil Gate divisor (10-L') | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 |
| Revivifier divisor (9-L') | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
| Remedy / Revivifier full cure (one target) | no | no | no | no | yes | yes | yes | yes | yes |
| Remedy / Revivifier full cure (several targets) | no | no | no | no | no | no | no | no | yes |
| Dispel Magic full scrub (uses L, one target) | no | no | no | no | yes | yes | yes | yes | yes |
| Dispel Magic partial: saber hits removed 4(L+1), Wall hits removed L+2 | 4 / 2 | 8 / 3 | 12 / 4 | 16 / 5 | - | - | - | - | - |
| Buff, status and absorb magnitudes | through V (section 2), grid in the json | | | | | | | | |

## 12. Validation
`python3 tools/spell_effects.py ROM STATE 300 data/spell_effects.json` : 300 random cases per handler (random caster slot, stats, `E1E6`, level 0..8, n = 1..3, ~30% monster casters, random target stats, immunity, buffs, statuses, timers, Wall, saber state; dead targets for 21), 0 mismatches for 02 03 04 05 07 08 09 0A 0B 0F 10 11 14 15 16 18 19 1A 1B 1C 1D 1E 21 22 24 26 27 29; the fields compared are those listed in the tables above (plus MP spent, and the pending-damage clearing of hero targets). Special set-ups: Wall wrapper (8 rows), Lucid Barrier through `$C0:4004` (5 rows), the weapon change of spells 20 and 23 (`$C0:3F94` and the tick), weapon drain flag (5 rows), level 8 roll (1,792 casts), tick lifetimes (buff timers 1/2/5/20/125/249 over 8 `E1B9` phases, five directly set statuses). The harness runs on late-game save states (`E1E6 = 8`, `$CFFC = 8`).

## 13. Open questions (not determined)
These are unknown; no values or formulas are claimed for them.
1. What the caller of the spell hit wrapper `$D0:4C82` does with its return (`A = 0xFF`, `X` = candidate object) when a Wall absorbs a spell, and where the wrapper is called from.
2. What the bytes `$EE-$F0` (toggled by status 0x0080, `$C0:3F2C`) control.
3. The code that writes `E170-E177` of a hero at cast request (the spell id, level, target list and the element index `E177`); the level-up message prints the text `0x2A + E177` (a name of the element text block), but which `E177` value belongs to which element mask is not determined (`docs/rom-combat.md` 18).
4. The purpose of the object-id-0xEA branch of Analyzer, the texts it prints, and the special branch for `E1FB` bit 4 objects (ids 0x55-0x56) in the hit entry.
5. Whether a stuck weapon row 17 after a Saber cast over the weapon change of spells 20 and 23 is repaired by another routine.
6. The visual/sound parts of the handlers (buff messages `$C0:5921`, the sprite size by level in `$C8:E665`).
7. How the AI and the menus choose which spell and which target to use (only the target flag byte and `E176` are covered).
8. The effect of status 0x0080 on the actor besides the `$C0:3F2C` toggle, and the effect of the accuracy buff pair beyond the quirk of 4.2 (`docs/rom-combat.md` 18).

## 14. Corrections to earlier sections of `docs/rom-combat.md`
Found while running the handlers: 5.5 lists 02, 14, 16, 18 and 1E as "damage + status": they deal **no** damage. 07 and 10 are damage plus a buff-byte change (the status word of the row 07 is not applied). 12.2 states that spells always load d = 20 and that the buff bytes get "the same d": the status duration is `max(20, (V>>2) - mdef/2)` with V the spell value, the buff timers are `V>>2`. 4.6 gives the Saber level as 1..9 with up to +100%: the level is 0..8, level 0 adds nothing and level 8 adds 1/2.

# Secret of Mana (USA) - combat and stat formulas extracted from the ROM

Tags: **[V]** verified = the arithmetic was reproduced by a Python model that was checked against the REAL 65816 routine of the ROM running in `tools/cpu65816.py` with randomised inputs (counts given per section), or the value was cross-checked against live game objects stored in ZSNES save states. **[C]** read from the disassembly, read, not executed. Anything not determined is listed in section 18 and stated there as unknown.

The repo contains only code, notes, and the gameplay-number tables in `data/*.json` (raw table bytes and values computed by the routines; no graphics, no text).
ROM: 2 MiB HiROM, `$Cx:xxxx` (banks C0-DF) = file offset `((bank-0xC0)<<16)|addr`. All file offsets below are file offsets (e.g. `0x101C00`). Save states used: six ZSNES save states of a late-game session (see README).

## 0. Summary

All values are integers; `rnd(n) = (R * n) >> 8` where `R` is the next byte of the game's RNG (0..255). "cap999" = `min(v, 999)`.

```
# --- per-hit physical damage, attacker A, defender D (all [V], §4)
A.atk  = (str + weapon.power) & 255          A.acc = min(99, agi//4 + weapon.hit)      # heroes; monsters: rec stats + their weapon row
D.eva  = min(99, agi//4 + sum(armor.evade))  D.def = min(999, con + sum(armor.def))    # heroes; monsters: record bytes 8, 9-10
ev  = D.eva  +-25% if D has Speed-Up/Down buff (E1B0 bit2/bit3), cap 99
df  = D.def  +-25% if Defender/Acid buff (E1B0 bit0/bit1);  df //= 4 if D is Pygmized;  cap 999
acc = A.acc, -25%/+25% only when A has bit E190&4 (quirk, §4.2), cap 99; acc //= 2 if A's weapon gauge E1ED != 0
HIT iff acc >= ev//2 + rnd(ev//2)                                                      # no other miss roll
m   = 2 normally (1 if resisted, 4 if weak; see §6 for the quirk)                      # i.e. x1, x0.5, x2
v   = A.atk * (2*stage + 4) // 4              # stage = charge stage of the swing (0..weapon level)  == atk*(1+stage/2)
v  += or -= 25% for ATK-up/down buff (E1B0 bit6/bit7);   v += base // (10 - n)  if saber level n=1..9 active
v   = cap999(v * m // 2);  if A is Pygmized: v = 1
roll = rnd(101); if roll >= acc:  v = cap999(acc * v // 100)         # "glancing": reduced by accuracy
                 else:            v = cap999(v + (E1E6)^2 + rnd(v//16))   # E1E6 = $CFFC for heroes: 0 at new game, 8 in all six saves (+64); $CFFB for monsters (0). See §11.6
roll = rnd(100); if roll >= ev:   D' = cap999(ev * df // 100)        # evade says how often defense is applied in full
                 else:            D' = cap999(df + rnd(df//16))
crit (not if E1ED != 0): chance = (E196 [*2 if D.E190&0x10] [+5 for hero attackers, +10 when the attacker is hero slot 1]) / 256   -> v *= 2 (after the caps)
v  -= D.E1BF if D has the flat-guard flag (E1B1 bit4) and then D'=0
damage = max(0, v - D')                        # NO minimum of 1 for weapons; applied damage is capped to 999 per hit
```
Magic (§5): `power = (p + stat) & 255` (p = spell row byte 10 for heroes, monster record byte 18/19), `v = cap999(power * (level+2) // 2)`, accuracy roll `rnd(101) >= acc` (acc = min(99, stat//4 + 75)) -> `acc*v//100` else `v + E1E6^2 + rnd(v//16)`, `* m // 2`, `// divisor`, cap 999, then `damage = max(1, v - mdef')` (magic has a minimum of 1), `mdef'` as the defense roll with MEv. Heal spells ignore the target defense (`m = 4`).

Weapon and magic levels, drops, statuses, boss rows, items (new, all executed unless tagged): weapon progress `+= 9 - level` per kill (halved vs lower-level monsters, others get half), cap `grade + 1`, max 8 (§11.2); one charge stage = 90 frames = 1.5 s (§11.3); spells level only while `level < $CFFC` and `$CFFC` also adds `+CFFC^2` (64 in late saves) to every non-glancing hit (§11.5-11.6); chest chance 4/64 for 77 monsters, content bytes decoded (§13); statuses timers drop every 4th tick (12 ticks/s -> d = 20 lasts 6.4 s), poison/engulf 1 HP per drop (§12); spell divisor = number of valid targets 1..3 (§14); 115 boss attack rows and the boss -> row map (§15); item effects (§16).

Level-up (§8): NO random growth. Every hero stat per level is a fixed ROM table (`data/hero_levels.json`); every living hero receives the full monster EXP; EXP/GP cap 9,999,999; level cap 99 (internal index 98); HP is fully restored on level-up.

## 1. Conventions

### 1.1 Objects
All actors are 0x200-byte records at `$7E:E000 + slot*0x200` ([V] harness runs on save states). Slots 0,1,2 = boy, girl, sprite (object id `E1E7` = 0x80,0x81,0x82); slots 3,4,5 (`$E600,$E800,$EA00`) = monsters/bosses (the Lich sits in slot 3). Offsets (relative to the record) used by the combat code:

| off | meaning | tag |
|---|---|---|
| 0x181 | level, 0-based internal (display = +1) | [V] row 0 of the hero table is the starting stats |
| 0x182 / 0x184 | HP / max HP (word) | [V] |
| 0x186 / 0x187 | MP / max MP | [V] |
| 0x188 0x189 0x18A 0x18B 0x18C | Str, Agi, Con, Int, Wis (monsters: Con = 0) | [V] |
| 0x17D | EXP needed for the next level (24-bit) | [V] |
| 0x18D | EXP: heroes = total, monsters = reward (24-bit) | [V] |
| 0x190, 0x191 | status words/flags (see §7, §12) | [V] |
| 0x192 / 0x193 | monster type / monster element byte (resist) | [V] |
| 0x194 / 0x195 | weapon byte-5 mask / weapon flags (bit 6 of 0x195 = drain, §4.7; Saber spells OR an element bit into 0x195, §4.6) | [V] code |
| 0x196 | crit base | [V] |
| 0x197 | accuracy | [V] |
| 0x198 | attack power | [V] |
| 0x199 | status word inflicted by hits | [V] |
| 0x19B | charge stage of the current swing | [V] (sim of `$C0:B330`) |
| 0x19C | weapon level of the equipped weapon type (0..8) | [V] |
| 0x19D | remaining hits of an active Saber enchant | [V] |
| 0x1A0 / 0x1A2 | weak-element / resist-element words (the useful bytes are 0x1A1 and 0x1A3) | [V] |
| 0x1A4 | evade (0..99) | [V] |
| 0x1A5 | defense (word, <=999) | [V] |
| 0x1A7 | magic evade | [V] |
| 0x1A8 | magic defense (word) | [V] |
| 0x1AA | status immunity word | [V] |
| 0x1AE | low nibble = Saber level n, high nibble = counter that forces a crit and is decremented per hit (§4.3) | [V] code |
| 0x1B0 | buff bits: 01 DEF+25%, 02 DEF-25%, 04 EVA+25%, 08 EVA-25%, 10 ACC+25%, 20 ACC-25%, 40 ATK+25%, 80 ATK-25% | [V] |
| 0x1B1 | flags: bit4 = flat damage reduction active (E1BF); bit1 not determined | [V] |
| 0x1B2-0x1B6 | status timers (see §7) | [V] |
| 0x1C0-0x1C3 | weapon levels, 8 nibbles (even weapon type = high nibble, odd = low) | [V] |
| 0x1C4-0x1C7 | magic levels, 8 nibbles by element index (same nibble rule) | [V] |
| 0x1C8 | monster: gold reward | [V] |
| 0x1D0-0x1D7 / 0x1D8-0x1DF | weapon-level progress / magic-level progress per type/element (0..99) | [V] |
| 0x1E0 0x1E1 0x1E2 | equipped head / body / accessory armor ids | [V] |
| 0x1E4 / 0x1E8 0x1E9 | weapon type (hero) / weapon row ids (short, long range) | [V] |
| 0x1E6 | `$CFFB` (monsters) / `$CFFC` (heroes). New game: 0 (`$C0:5787`); the six save states all have `$CFFC = 8`, `$CFFB = 0`. Added as `E1E6^2` to every non-glancing hit and is also the spell-level cap (§11.5, §11.6) | [V] |
| 0x1ED | weapon-recharge gauge | [V] |
| 0x1F1 0x1F3 0x1F5 0x1F6 | pending: HP damage, HP heal, MP damage, MP heal | [V] |
| 0x1F7 | status chance of the weapon (%) | [V] |
| 0x1FB | bit7 hero, bit6 boss (`id >= 0x57`), bit4 set for object ids `0x55-0x56`; bit5 not determined | [V] |
| 0x1FD 0x1FE | monster spell power (Int-class / Wis-class spells) | [V] |
| 0x170 0x171 0x176 0x177 | caster object: spell id, spell level, damage divisor, element index | [V] |

### 1.2 RNG [V]
`$C0:38A0`: 15 bytes at `$03F1-$03FF` with index `$03F0` (0..14): `t[i-1] += t[i]` (index wraps 0 -> 14), returns the new byte, index increments. `$C0:3884` with `A=n` returns `(R*n)>>8`. Model: `tools/rng.py` (bit exact, used by all validators).

### 1.3 Timing [C]
The main loop (`$C0:B070-B08A`) runs once per NMI (60.0988 Hz NTSC) and keeps `$56` = 0..4. Per-frame work (input handler `$C0:B69C`, charge gauge `$C0:B330`, weapon recharge gauge `E1ED` at `$C0:EB4F`) runs every frame. The per-actor combat tick `$C0:3A79` (hit resolution, status timers, damage over time, pending HP) is called from the object step `$C0:F4CB`, which `$C0:B0D3` dispatches by `$56`: monster slots 3, 4, 5 at `$56` = 0, 1, 2 and the three heroes at `$56` = 3 (when `$ED` bit 7 is set, as in all save states). So **every ordinary actor ticks once per 5 frames = 12.02 Hz**. The C2 boss engine (`$C2:0003`, single call site `$C0:FD12`, reached from the same three dispatch entries) is called only for `$56` = 0, 1, 2 and runs an object when `(flags_hi ^ $56) & 3 == 0` (or flag 0x4000): objects with flags high byte `&3 == 0` (Dark Lich `0x9C`, Mana Beast `0x18`) tick at `$56` = 0 only, **12.02 ticks/s as well**; high byte `&3 == 1` and `2` tick at `$56` = 1 and 2; `&3 == 3` never ticks unless flag 0x4000 is set (`docs/mana-beast.md` section 1, re-verified by re-running the Lich with the full frame `$C0:B08C`). "Object tick" below means this 12 Hz tick unless a section says "frame". Section 17 lists all durations in seconds.

## 2. Data tables (all dumped to `data/`, see `tools/dump_tables.py`)

| table | file offset | layout | JSON |
|---|---|---|---|
| Monster stat records | `0x101C00 + id*29`, ids 0-0x7F | §2.1 | `monsters.json` |
| Monster drop rows | `0x103A50 + id*5` | §2.1 | in `monsters.json` |
| Weapon rows | `0x101000 + id*12` (ids 0-71 player weapons, 72+ monster attacks) | §2.2 | `weapons.json` |
| Armor rows | `0x103ED0 + id*10` (head 0-20, body 21-41, accessory 42-62) | §2.3 | `armors.json` |
| Spell rows | `0x102AD0 + id*64`, ids 0-0x29 | §2.4 | `spells.json` |
| Hero level tables | `0x104210 + hero*0x318 + level*8` | §2.5 | `hero_levels.json` |
| EXP table | `0x104B58 + level*3` (24-bit) | §2.5 | `hero_levels.json` |
| Boss/special attacks | `0x10BDC1 + id*7` | §2.6 | `boss_attacks.json` |
| Consumables | effect byte `0x104152 + id*16` | §9 | `items.json` |

### 2.1 Monster record, 29 bytes [V] (copy code `$C0:55EC`, `$C0:474F`; checked against the Lich and by running the init on 11 ids)
```
0 level            1-2 max HP         3 MP (also starting MP)
4 Str  5 Agi  6 Int  7 Wis            (Con is not stored: 0)
8 evade            9-10 defense       11 magic evade      12-13 magic defense
14 type byte  (obj+0x192; bit 0x20 reverses drain weapons, see §4.7)
15 element byte (obj+0x193 = resist mask, weakness = opposite element, see §6)
16-17 EXP reward   18 spell power for Int-class spells (spell id % 6 < 3)   19 same for Wis-class
20-21 status immunity word            22 not determined (0 for all records seen)
23 weapon row id, short range         24 weapon row id, long range      (rows of §2.2, monster rows start at id 72)
25 flag byte (bit0 -> E1B1 bit0, bit7 -> E1B1 bit1, bit6 -> E1B1 bit3, whole byte -> E1CA) [C]
26 high nibble = weapon level, low nibble = magic level
27-28 gold reward (obj+0x1C8)
```
Drop row (5 bytes, D0:3A50 + id*5): fully decoded and validated in §13 (`data/drops.json`). `0xFF` rows = no drop.

Boss records also carry the Lich-style fields; bosses (`id >= 0x57`) read their ATTACK numbers from the boss attack table (§2.6) instead of the weapon table.

### 2.2 Weapon row, 12 bytes [V] (`$C0:49AA`, `$C0:4A0C`, `$C0:4AFF`, `$C0:48B4`)
```
0 weapon type 0-7 (ids 0-71 = 8 types x 9)
1 stat bits: Agi = tbl[b>>6], Con = tbl[(b>>4)&3], Int = tbl[(b>>2)&3], Wis = tbl[b&3]       tbl = [0,+1,+5,-5]  (at $C0:4B79)
2 bits0-1: Str = tbl[b&3];  other bits not determined (0xC0/0xC1/0xC2 in all rows)
3,4 graphics (not dumped)
5 mask copied to obj+0x194, 6 crit base, 7 hit %, 8 power
9-10 status word inflicted, 11 status chance %
```
Examples [V from the dump]: every player weapon has hit 75 (0x4B) except id 17 with 99; powers run 2..127 (id 17: 127); only 13 player weapons have a status word (all with chance 80%); the byte-5 masks are single bits.

### 2.3 Armor row, 10 bytes [V] (`$C0:4860`, `$C0:4B7D`, `$C0:4A2D`, `$C0:4A75`)
```
0 flags: bits 4,3,2,1 = +5 Str / Agi / Con / Int   (0x40 is set on every row; its "-2" use is a quirk, see §3)
1 defense  2 evade  3 magic defense  4 magic evade
5 equip mask (0x80 boy, 0x40 girl, 0x20 sprite)   6 element resist mask   7-8 status immunity word   9 unknown
```
The evade/magic-evade columns are constants per slot (head 23, body 37, accessory 15 -> sum 75; magic evade the same), so a fully dressed hero has `eva = agi//4 + 75`.

### 2.4 Spell row, 64 bytes [V for fields used by the validated handlers]
`10` power (hero casters), `11` accuracy base (75 for all), `12` element mask, `13-14` status word, `15` MP cost, plus pointers/graphics (not dumped). `$C8:E801 + id*2` = handler address (listed in `spells.json`). Table in §5.5.

### 2.5 Hero tables [V against 16 hero objects]
`HP(word), MP, Str, Agi, Con, Int, Wis` per internal level 0..98 and hero (boy/girl/sprite), Row 0 = starting stats (boy 50 HP, 15/15/13/5/5). Max level row: boy HP 999 / 99 Str, girl and sprite 800 HP. EXP to next level: `ex[level]` = 16, 47, 105, 204, ... 9,999,999 (the table entry used is `ex[E181]`, with E181 the 0-based level).

### 2.6 Boss / special attack rows, 7 bytes [V] (`$C0:45D6`)
`0-1` word -> obj+0x194/0x195, `2` accuracy (99), `3` power (atk = Str + power), `4-5` status word, `6` status chance. The Dark Lich uses id 0: power 35 (-> attack 74+35 = 109, as in `docs/dark-lich.md`), status 0x4000, chance 99%. The table has 115 rows (ids 0-0x72, `data/boss_attacks.json`); all 115 were loaded through the real routine and compared [V, `tools/validate_boss_attacks.py`]. Which boss uses which row: §15.

## 3. Hero stat build ([V]: `tools/hero_stats.py` reproduces Str/Agi/Con/Int/Wis, max HP/MP, accuracy, attack, evade, defense, magic evade, magic defense and the immunity word of all 16 hero objects found in six save states)
Order (`$C0:4530`):
1. base = hero table row `[hero][level]` (`$C0:464F`).
2. If the hero is NOT driven by a human controller (`$D9-$DB` low nibbles do not point at it): add a per-hero tweak byte `tbl[$CC7A+hero]` from the 16-byte table at `$C0:473F` (`35 04 04 17 32 00 00 23 32 00 00 23 35 04 04 17`): 2-bit fields add `[0,+1,+2,-1]` to Str, Agi, Con. With the usual `$CC7A=0` that is **+1 Str, +1 Agi, -1 Con for computer-controlled party members** [V]; the meaning of `$CC7A` is not determined.
3. Armor flags (`$C0:4B7D`): each of the three pieces: bit4 -> Str +5, bit3 -> Agi +5, bit2 -> Con +5, bit1 -> Int +5 [V]. (The routine tests `BIT $0040`, i.e. WRAM `$7E:0040`, for a "-2" variant; it was zero in every state; its meaning is not determined.)
4. Weapon stat codes (§2.2) added to Str/Agi/Con/Int/Wis.
5. If status bit `E190 & 8`: Agi -= Agi/16. Then Str..Wis clamped to 1..99.
6. Derived: `acc = min(99, agi//4 + weapon.hit)`, `atk = (str + weapon.power) & 255`, `crit base = 3*weaponLevel + weapon.crit` (halved when the weapon type is > 4: bow, boomerang, javelin), `eva = min(99, agi//4 + armor evade sum)`, `def = min(999, con + armor def sum)`, `mev = min(99, wis//4 + armor mev sum)`, `mdef = min(999, wis + armor mdef sum)`, immunity = OR of the three armor words | 0x0800, resist mask = OR of the three armor `[6]` bytes.
Equipment bonuses therefore combine **additively before the 99 clamp**; defense/evade values are plain sums.

## 4. Physical damage (`$C0:4F7B` dispatcher -> `$C0:4FED`, `505B`, `50CA`, `514B` [51E7, 52E7, 532C, 541B], `5119`)

Validation [V]: `tools/validate_phys.py` runs the real routines and `tools/phys_model.py` on 1,600 random attacker/defender pairs (monster ids 0-0x79, both directions, random buffs/statuses/gauge/stage/RNG state) on three save states: 0 mismatches. The ROM objects are real (heroes from the saves, monsters created by the game's own `$C0:55EC`).

### 4.1 Roles
`X` = defender (owner of the hit mask `E059`, bit i = attacker slot), `Y` = attacker. Hero defenders are hit by slots 3-5, monster defenders by slots 0-2 (`E1FB` bit 7 selects). Pending result goes to the defender's `E1F1`.

### 4.2 Hit test (`4FED`, `505B`) [V]
```
ev = D.E1A4;  ev += ev>>2 if D.E1B0&4; ev -= ev>>2 if D.E1B0&8;  ev = min(ev, 99)
acc = A.E197
if A.E190 & 4: acc -= acc>>4;  q = acc>>2        else:  q = A.E190 >> 2     # ROM quirk: A still holds E190 at $C0:5076
if A.E1B0 & 0x10: acc += q  elif A.E1B0 & 0x20: acc -= q ;   acc = min(acc, 99)
if A.E1ED != 0: acc >>= 1
hit  iff  acc >= (ev>>1) + ((R * (ev>>1)) >> 8)        # R = one RNG byte
```
So the "buff/debuff 25%" on accuracy only bites when the attacker has E190 bit 2 set, otherwise it adds `E190>>2` (normally 0). Hit probability for `ev` and `acc`: `T = ev//2 + floor(R*(ev//2)/256)`, e.g. acc 92 vs ev 99 -> T in [49,97], P(hit) = 230/256 = 89.8%.

### 4.3 Damage (`51E7`, `52E7`, `532C`, `541B`, `514B`) [V]
```
stage = A.E19B (+ $CC76 once per hit when the attacker is hero slot 0; what `$CC76` holds is not determined)
v = (A.E198 * (2*stage + 4)) >> 2            # integer, 16 bit
base = v;  v -= v>>2 if A.E1B0w & 0x80  elif  v += v>>2 if A.E1B0w & 0x40
n = A.E1AE & 15;  if n: v += base // (10 - n)           # n = Saber spell level (note: uses the pre-+-25% value)
v = ((v * m) & 0xFFFF) >> 1;  v = min(v, 999)            # m from §6: 1,2 or 4
if A.E191 & 2: v = 1                                     # Pygmized attackers always do 1
r = rnd(101)
if r >= acc:  v = min(999, acc * v // 100)               # acc is the value after 4.2 (incl. gauge halving)
else:         v = min(999, (E1E6*E1E6 + v + rnd((v + E1E6^2)>>4 & 255)) & 0xFFFF)
# defense (52E7)
df = D.E1A5 (+-25% from D.E1B0w bit0/bit1, //4 if D.E191&2, min 999)
r = rnd(100)
if r >= ev:   D' = min(999, ev * df // 100)
else:         D' = min(999, df + rnd((df>>4) & 255))
# crit / gauge (532C)
if A.E1AE & 0xF0:  A.E1AE -= 0x10; crit
elif A.E1ED == 0:  c = A.E196; if D.E190&0x10: c = 2c; if A is hero: c += 10 if attacker slot==1 else 5;  crit iff R < c & 255
else:  v = (v>>1) * (AC - A.E1ED) // AC,  AC = (99-Agi)//2 + 80       # no crit at all while the gauge is not empty
if crit: v *= 2
# flat guard (541B)
if D.E1B1 & 0x10: v -= (D.E1BF & 255); D' = 0
damage = v - D'  if v > D' else 0
```
- Maximum: every intermediate is capped at 999, but the final doubling for crits is applied after the cap; when the pending value is applied (`$C0:4004`) it is capped again to **999 per hit** [V, executed].
- Weapon damage has **no minimum**: `v <= D'` gives 0 damage (a "0" number is shown for monsters, see `docs/damage-counter.md`).
- The result is *not* divided by anything for several enemies; each contact is resolved separately.
- `E19B` (stage): `$C0:B330` raises it while the attack button is held: a counter 0..44 advances every second call (one call per frame), then stage++ up to the weapon level `E19C`; stage 0 = uncharged swing [V by execution]. Timing in seconds: §11.3 and §17. `E1ED` is loaded with `(100-Agi)/2 + 50` when a swing ENDS (`$C0:F937-F944`, `$C1:CACD`; `docs/glove-attacks.md` 2.4, not at its start; also when a run is released, `$C0:B77B-B78A`, `docs/hero-movement.md` 4.1) and decremented once per FRAME (`$C0:EB4F`, called from the per-frame `$C0:EB06`; Agi 50 -> 75 frames = 1.25 s, Agi 99 -> 50 frames = 0.83 s): a new swing is never blocked by the gauge (it only blocks a run and the start of a charge); a swing made before it reaches 0 deals `(AC-E1ED)/AC` of half damage and cannot crit, and accuracy is halved [V].

### 4.4 Worked examples (model, 20,000 trials, `tools/example_damage.py`) [V model]
- Lv66 boy, atk 135, acc 92 vs Dark Lich (eva 99, def 200), `E1E6 = 0`: stage 0 -> 90% hit, mean 9 damage; stage 8 -> 90% hit, mean ~577, median 492, max 1232 (capped to 999 when applied). With `E1E6 = 8` (the value in the late-game saves, §11.6): stage 0 mean 27, stage 8 mean 645, median 558, max 1368. With the gauge at 30 the hit chance is 0% (acc halves to 46 < 49).
- Lv1-like atk 17 vs eva 0/def 0: always hits, mean 17 (`E1E6 = 0`, the new-game value); with `E1E6 = 8` the same swing averages 79.

### 4.5 Status on hit (`5119`) [V]
After a damaging hit: if `A.E199 & D.E1AA == 0` (not immune), `rnd(100) < A.E1F7` and damage > 0, then `A.E199` is queued as the status to apply (`$9A`). Weapon rows carry the status word and chance (0x50 = 80% is the default chance byte, only rows with a status word matter).

### 4.6 Saber buffs [V]
Handlers `$C8:EAA3-EABC` (ids 3, 9, 0xF, 0x15, 0x1B, 0x27): `E195 |= element bit`, `E199 |= spell status word`, `E19D = (level+1)*4`, `E1AE low nibble = level`. The remaining-hit counter `E19D` is decremented once per hit by the attacker (`$C0:50EF`), the buff ends at 0. The *numerical* effect of a Saber is the `+ base/(10-n)` term (n = 1..9: +11% .. +100%).

### 4.7 Drain weapons [C]
Attacker `E195 & 0x40`: the defender takes the damage and the attacker gets the same amount as HP heal (`E1F3`), unless the defender has type bit `0x20`, in which case the roles are swapped.

## 5. Magic (`$C8:E6D4-E7A6` hit entry, `E7A7`, `E855`, `E8A0`, `E8C0`, `E990`, `E9DF`, handlers in `$C8:EA8B-EF..`)

Validation [V]: `tools/validate_magic.py` - damage handlers `EA8B/EB39/EBCA/EBE5` ids {0,1,6,7,0xC,0xD,0xE,0x10,0x11,0x12,0x13,0x1F,0x25,0x28} and the heal handler `EBB3` (id 0x0B), caster hero or monster, random levels/divisors/elements/defenses/RNG: 800 random cases on three states, 0 mismatches.

### 5.1 Casting
- MP cost = spell row byte 15, subtracted at cast time (`$C0:3F6C` compares `MP - cost >= 0`, the monster AI uses the same table at `$C1:1E41`) [C].
- Spell level `L` (`$D0:4E6E`, `$D0:4EAC`) [C, plus sim]: heroes: nibble of `E1C4..E1C7` for the spell's element index (`E177`), even index = high nibble; monsters: `E1C4` (record low nibble). The level actually stored in the cast (`E171`, used as `$9D` in the damage formula) is `L`, except for heroes and bosses (`E1FB & 0xC0`) with `L == 8`: `E171 = 8` only if `(R>>1) + 1 < progress`, else 7, where `progress = E1D8[element]` (0..99). Bosses/monsters have progress 0, so **boss level-8 spells run at level 7**: confirmed in the boss-engine simulation (the Lich's Dispel Magic cast wrote `E171 = 7`) [V sim].
- Progress: every spell (first hit of a cast, `$D0:4DCD`, heroes only) adds `9 - L` to `E1D8[elem]` (halved unless `$ED` bit7), at 100 the level goes up (nibble++), at level 8 the progress sticks at 99 [C].

### 5.2 Damage (E8C0 + E9DF) [V]
```
stat  = caster Int (spell id % 6 < 3) or Wis (>=3)                       # E18B / E18C
p     = spell.power (hero casters)  |  record byte 18 / 19 (monster casters)
acc   = min(99, ((stat>>2) + spell.accuracy) & 255)                        # 8 bit add
v     = min(999, ((p + stat) & 255) * (L + 2) >> 1)                       # (p+stat) wraps at 256 (power 250 spells)
r = rnd(101);  v = acc*v//100 if r >= acc  else  (E1E6^2 + v) + rnd(...)  # same as physical
v = ((v * m) & 0xFFFF) >> 1;  v //= divisor (obj E176, 1 for single hits);  v = min(v, 999)
D' (E990): r = rnd(101); if r < target.mev:  D' = min(999, mdef + rnd(mdef>>4))
                         else:               D' = mev * (mdef + (mdef>>2)) // 100
damage = max(1, v - D')                                                    # magic always does at least 1
```
Spells never "miss": `acc` only scales damage. Element multiplier `m` (§6) uses the spell's element mask against the target's `E1A3` (resist -> 1) and `E1A1` (weak -> 4).

### 5.3 Healing [V]
Cure Water (id 0x0B, handler `EBB3`): same computation with `m = 4`, target defense unused, result added to `E1F3` (HP heal), applied capped at 999 and at max HP. At `L=0`: `Wis 74, p 61 -> (135*2/2)*4/2 = 270`; at L=8: 999 (cap). Other restorative handlers (`EB9F`, `ED04`, `ECD1`) are not modelled.

### 5.4 Item/regeneration application (`$C0:4004`) [V executed]
Pending heal is applied before pending damage (one of them per tick): heal: `E1F3` capped 999, `HP = min(maxHP, HP + heal)`; damage: `E1F1` capped 999, `HP = max(0, HP - dmg)`; MP heal `E1F6` capped 99 and to max MP; MP damage `E1F5` capped 99 floors at 0.

### 5.5 Spell table (power/accuracy/MP from the ROM; "class" from the handler code, [C] unless in the validated list; handlers that were not read in detail are marked "not modelled")
| id | name | element mask | power | MP | status word | handler | class |
|---|---|---|---|---|---|---|---|
| 00 | Earth Slide | 0x01 | 61 | 3 | - | EA8B | damage [V] |
| 01 | Gem Missile | 0x01 | 43 | 2 | - | EA8B | damage [V] |
| 02 | Speed Down | 0x01 | 61 | 1 | 0004 | EA97 | damage + status |
| 03 | Stone Saber | 0x01 | 61 | 4 | 0040 | EAA3 | saber |
| 04 | Speed Up | 0x01 | 61 | 3 | - | EB04 | buff: EVA+25% & ACC+25% |
| 05 | Defender | 0x01 | 61 | 2 | - | EB20 | buff: DEF+25% |
| 06 | Freeze | 0x04 | 61 | 2 | - | EA8B | damage [V] |
| 07 | Acid Storm | 0x04 | 43 | 3 | 2000 | EB39 | damage [V] + DEF-25% |
| 08 | Energy Absorb | 0x04 | 43 | 2 | - | EB54 | not modelled |
| 09 | Ice Saber | 0x04 | 61 | 2 | 0020 | EAA8 | saber |
| 0A | Remedy | 0x04 | 61 | 1 | - | EB9F | not modelled |
| 0B | Cure Water | 0x04 | 61 | 2 | - | EBB3 | heal [V] |
| 0C | Fireball | 0x08 | 52 | 2 | - | EA8B | damage [V] |
| 0D | Exploder | 0x08 | 61 | 4 | - | EA8B | damage [V] |
| 0E | Lava Wave | 0x08 | 43 | 3 | - | EA8B | damage [V] |
| 0F | Flame Saber | 0x08 | 61 | 2 | 4000 | EAAD | saber |
| 10 | Fire Bouquet | 0x08 | 43 | 3 | - | EBCA | damage [V] + ATK-25% |
| 11 | Blaze Wall | 0x08 | 32 | 4 | 4000 | EBE5 | damage [V] + status |
| 12 | Air Blast | 0x02 | 43 | 2 | - | EA8B | damage [V] |
| 13 | Thunderbolt | 0x02 | 61 | 4 | - | EA8B | damage [V] |
| 14 | Silence | 0x02 | 61 | 2 | 0080 | EBF4 | damage + status |
| 15 | Thunder Saber | 0x02 | 61 | 3 | - | EAB2 | saber |
| 16 | Balloon | 0x02 | 61 | 2 | 0100 | EBF4 | damage + status |
| 17 | Analyzer | 0x02 | 61 | 1 | - | EC00 | not modelled |
| 18 | Change Form | 0x40 | 61 | 5 | 0800 | EBF4 | damage + status |
| 19 | Magic Absorb | 0x40 | 43 | 1 | - | EC3B | not modelled |
| 1A | Lunar Magic | 0x40 | 61 | 8 | - | EEF5 | not modelled |
| 1B | Moon Saber | 0x40 | 61 | 3 | - | EABC | saber |
| 1C | Lunar Boost | 0x40 | 61 | 2 | - | ECB5 | not modelled |
| 1D | Moon Energy | 0x40 | 61 | 2 | - | ECD1 | not modelled |
| 1E | Sleep Flower | 0x80 | 61 | 2 | 0010 | EBF4 | damage + status |
| 1F | Burst | 0x80 | 100 | 4 | - | EA8B | damage [V] |
| 20 | (see `names.py`) | 0x80 | 250 | 1 | - | ECEA | not modelled |
| 21 | Revivifier | 0x80 | 61 | 10 | 8000 | ED04 | not modelled |
| 22 | Wall | 0x80 | 61 | 6 | - | ED53 | not modelled |
| 23 | (see `names.py`) | 0x80 | 250 | 1 | - | ED68 | not modelled |
| 24 | Evil Gate | 0x10 | 61 | 8 | - | ED82 | not modelled |
| 25 | Dark Force | 0x10 | 61 | 2 | - | EA8B | damage [V] |
| 26 | Dispel Magic | 0x10 | 61 | 4 | - | EDCB | not modelled |
| 27 | Light Saber | 0x20 | 61 | 5 | - | EAB7 | saber |
| 28 | Lucent Beam | 0x20 | 61 | 8 | - | EA8B | damage [V] |
| 29 | Lucid Barrier | 0x20 | 61 | 4 | - | EEB7 | not modelled |

Accuracy base is 75 for every spell. Names are as decoded from the ROM text block at run time by `tools/names.py`.

## 6. Elements [V for the spell path, see quirk for weapons]
Bits (spell rows, monster element byte, armor resist byte): `0x01 .. 0x80`. Only the six low bits have opposites in the weak-mask formula below: 0x01<->0x02, 0x04<->0x08, 0x10<->0x20 (0x40 and 0x80 have none).
- Resist mask `E1A3` = monster record byte 15 (or the OR of the armor resist bytes); weak mask `E1A1 = ((m<<1)&0x2A) | ((m>>1)&0x15)` masked to 6 bits: **a creature with element bit X is weak to the opposite bit** (Dark Lich: element byte 0x10 -> resists 0x10, weak to 0x20).
- Multiplier for spells: `m = 1` if `spell.element & resist`, `m = 4` if `& weak`, else 2; the damage formula uses `v*m/2`, so it is **x0.5 / x1 / x2**. The check order is resist first.
- Quirk [V, `$C0:50CA`]: for physical hits the routine tests the word `E194/E195` of the SAME object as `E1A2/E1A0` (the defender's own, since `X` is the defender), the only live byte pair being `E195 & E1A3` / `E1A1`. No code path was found that copies the attacker's weapon element or its Saber bits into the defender before the test (searched all writers of `E194/E195`). Practical consequence in vanilla code: physical hits against monsters always have `m = 2`; the weapon "enemy type" byte and the Saber element bits have no effect on weapon damage by themselves [V as code]. Related finding [V as code]: `$C0:4A53` loads the monster type byte (`LDA E192,X`) and then stores ZERO into `E1A2` (`STZ`), so the low byte of the `E1A2` mask - the one the weapon enemy-type byte `E194` would be tested against - is always 0. As a result the byte-5 test cannot trigger in the code paths read [V as code]. Whether another code path handles it was not found.

## 7. Status effects
- Application (`$C8:E301`, via `E88E` after a spell, or `5119` for weapons) [C+V partly]: `new = status & ~target.E1AA` (immunity word: monster record bytes 20-21, hero armor words | 0x0800); no random roll for spells (spells always inflict unless immune); for weapons the roll is §4.5.
- Spell status words by spell id: 02 -> 0004, 1E -> 0010, 09 -> 0020, 03 -> 0040, 14 -> 0080, 16 -> 0100, 18 -> 0800, 07 -> 2000, 0F and 11 -> 4000, 21 -> 8000 (bit 0x8000 is cleared by that handler). Boss attacks: `data/boss_attacks.json` (statuses 0004, 0010, 0020, 0040, 0100, 0200, 1000, 2000, 4000 with chances 33/50/80/99%).
- Duration (`$C8:E3A9`): `d = max(20, ($96>>2) - (target.mdef>>1))` where `$96` is the damage value *before* defense of the hit; stored in the timer of the status group: bits `0x007C -> E1B2`, `0x0180 -> E1B3`, `0x1C00 -> E1B5`, `0x6000 -> E1B6` (group bits all end together when the timer reaches 0). Executed and validated in §12 (timers drop every 4th combat tick = 12 ticks/s / 4, so d = 20 lasts 6.4 s). Bit names, cascade, immunity, damage over time: §12.
- Effects found in the code [V/C]: `E190&4` accuracy -1/16; `E190&8` Agi -1/16; `E191&2`: own damage = 1 and Def/4; `E191&4`: no hits resolved; `E190&0x10` (target) doubles the target's crit exposure; bits `E191 & 0x60` deal 1 HP per tick (never kills: stops at 1 HP) [C].
- Item id 4 clears `E190` and keeps only bit 7 of `E191`; item id 5 also clears bit 7 [V executed, §9].
- The sources (spells, items, attack rows) of every status bit: §12.1.

## 8. Rewards, level-up and growth
- Kill reward (`$C0:4459`, `$C0:44F0`) [V executed, `tools/validate_exp.py`, 60 cases]: for every hero that is alive (HP>0): `exp += monster.exp` (24-bit, cap 9,999,999). **Full EXP to each living hero** (no splitting). While `level < 98` and `exp >= ex[level]`: `level++`, stats rebuilt from the hero table (§3), HP set to max HP. Level cap 99 (index 98). Gold: `+= monster.gold`, cap 9,999,999 (`$C0:39A4`).
- Stat growth per level: none computed; the whole curve is the table in `data/hero_levels.json` (HP, MP, Str, Agi, Con, Int, Wis per level and hero). Equipment adds on top (§3).
- Weapon level: fully specified and validated in §11.2 (progress `+= 9 - level of the killer's weapon`, halved against lower-level monsters, the other living heroes get half, threshold 99, cap `CFB0[type] + 1` and maximum 8; kills by spells give none).
- Magic level: §11.5 (validated); the old text in §5.1 about the progress remains correct.

## 9. Consumables [V executed on a save state, `$C0:54E7`] (full table with dead-hero behaviour: §16)
Item ids 0-11: id 0 adds 100 HP (`0x64`), id 1 adds 250 HP, id 2 sets HP to max (`E1F3 = max`), id 3 adds 50 MP (via `E1F6`), id 4 clears the status words (timers reset to 1, `E190 = 0`), id 5 sets HP to max and clears the KO bit, id 8 toggles `E191` bit 4, id 9 toggles bit 1, id 10 toggles bit 2; ids 6 and 7 have no combat effect in this routine. Prices: the price tables are in `data/prices.json` (consumable price word table at `0x18FB9C`, `0xFFFF` = not sold); which item id each price entry belongs to was not verified (see §18).

## 10. Scope
This document describes only what the ROM code and tables do; every formula was executed or read in the ROM as tagged.

## 11. Weapon level, weapon grade (orbs), charge gauge, magic level

Validation: `tools/weapon_level.py` (3,000 random kills incl. dead heroes, caps and the `$A6` quirk: 0 mismatches), `tools/validate_magic_level.py` (1,500 random casts: 0 mismatches), `tools/charge_timing.py` (real `$C0:B330`).

### 11.1 Storage [V]
| where | meaning |
|---|---|
| `E1C0-E1C3` (hero object) | weapon level of the 8 weapon types, 4 bits each: type `t` = byte `t>>1`, HIGH nibble for even `t`, low nibble for odd `t`. Range 0..8 |
| `E1D0 + t` | weapon-level progress of type `t`, 0..98 (99 is only reachable at level 8) |
| `E1E4` | weapon type of the equipped weapon; `E1E8` = equipped weapon row id = `type*9 + grade` (checked in 3 saves) |
| `E19C` | level of the equipped type, rebuilt from the nibble by `$C0:48F0` after every level-up and equipment change |
| `E19B` | current charge stage of the swing (0..`E19C`) |
| `E1C4-E1C7`, `E1D8 + e` | magic level nibbles (same packing) and progress 0..99 per element index `e` = `E177` of the cast, 0..7 (`E177` = 1 for spell ids 06 and 0B in a save); the mapping of every index to an element mask is not determined |
| `$CFB0 + t` | **weapon grade** of type `t` (0..8) = index of the owned weapon inside its 9-row group; level cap is derived from it (11.4) |
| `$CFB8 + t` | orbs found for type `t` (0..8). The upgrade shop needs `CFB0 < CFB8` |
| `$CFC0 + t` | 9 for every type except sword (8) in all saves; an orb drop of type `t` is only kept while `CFB8[t] + 1 < CFC0[t]` (11.4). Initial value and writer not found |
| `$CC54 + t` | shop/inventory slot of the weapon of type `t`: bits 0-5 = grade (mirrors `CFB0`), bits 6-7 = equipped-by flags |
| `$CC7D + hero` | player-chosen charge level for the AI-controlled hero (11.3); set from `E19C` by `$C0:7A4A` and clamped to the weapon level in the menu (`$C7:6C18`) |

### 11.2 Weapon level-up [V] (`$C0:4358`, per-hero part `$C0:43B7`)
Triggered when a monster dies (`$C0:4247-4255`, right before the EXP and gold routines) and its `E1F0` is 0..2. `E1F0` = index of the hero whose WEAPON hit landed last (`$C0:4FD2`); every spell hit overwrites it with 0xFF (`$C8:E785`), so **a kill by a spell gives EXP/gold but no weapon progress**. Boss kills run the same code.
```
a6 = 9 - E19C(killer)                       # killer's CURRENT weapon level, not the other heroes' levels
if monster.level < killer.level: a6 >>= 1   # lower-level monsters give half
killer gets a6; then a6 >>= 1; the other two heroes get that (each on its OWN equipped weapon type)
for each hero that exists and is not dead (E191 bit 7 clear):
    t = E1E4;  wl = nibble(E1C0.., t);  cap = CFB0[t] + 1
    if wl == cap:             progress[t] = 0                  # frozen at the cap, progress is wiped
    else:                     p = progress[t] + a6             # byte add
         if p < 99:           progress[t] = p
         elif wl == 8:        progress[t] = 99                 # maximum level: sticks at 99
         else:                progress[t] = 0; nibble += 1     # LEVEL UP
```
The threshold is 99 for all nine levels (`$C0:43AC`, `data/weapon_levels.json`). ROM quirk reproduced by the model: the level-up message code leaves the NEW level (0..8, one digit) in the scratch byte `$A6`, so every hero processed after a level-up within the same kill gets `new_level` (already halved once if the level-up was the killer's) instead of `9 - wl`.
Kills needed per level: `ceil(99 / (9 - wl))` (x2 against lower-level monsters): level 0 -> 11, level 4 -> 20, level 7 -> 50, level 8 -> none.
A level-up rebuilds the stats (`$C0:4530`) and plays the sound/message `$CE`.

### 11.3 Charge gauge and stage [V executed]
`$C0:B330` is called once per frame for every hero whose attack button is held (heroes with `E02C != 0`, which was 1 for the controlled hero in the saves; stage cap = `E19C`) and for AI-controlled heroes (`E02C == 0`, cap = `$CC7D + hero`, 0 = never charge). It does nothing while the recharge gauge `E1ED`, `E01C`, `E061` or the pygmy bit (`E191 & 2`) are non-zero.
The gauge word `E01A` = (stage << 8) | counter: it acts on every 2nd call (`E01F`), counter 0..44 (0x2C); the act after counter 44 sets stage+1 and counter 0, until stage == cap (then counter parks at 44). So **one stage = 45 acts = 90 frames = 1.50 s** (90 / 60.0988 = 1.4976 s), and stage `s` is reached on call `90*s - 1`:

| stage | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| frames | 89 | 179 | 269 | 359 | 449 | 539 | 629 | 719 |
| seconds @ 60.0988 Hz | 1.48 | 2.98 | 4.47 | 5.97 | 7.47 | 8.97 | 10.47 | 11.96 |

Damage uses `v = atk * (2*stage + 4) / 4` (§4.3).

### 11.4 Grade, orbs, level cap [C + checked against saves]
- **Level cap (0-based nibble) = `CFB0[type] + 1`, absolute maximum 8.** With grade 0 (first weapon of the type) the level can reach 1, with grade 7 it can reach 8; grade 8 changes nothing more. Seen in saves: `CFB0 = 7` and a hero with level nibble 8 on that type.
- The grade is raised by the upgrade shop (`$C0:7B9B-7C49`): allowed when `CFB0[t] < 8` and `CFB0[t] < CFB8[t]`; price = `orb_price[CFB0[t]]` = 200, 400, 800, 1600, 3000, 6500, 12500, 25000 gold (word table `D8:FCFB`, `data/weapon_levels.json` / `data/prices.json`; 65535 at grade 8). On purchase: `CFB0[t]++`, the slot byte `CC54+t` is incremented and the equipped weapon row of the heroes flagged in bits 6-7 is recomputed (`$C0:6481`). The purchase routine was read, not executed [C].
- Orbs are found as monster drops (drop byte `0x80 + t`, §13) and chest/event items; `CFB8[t]` is the count found. Where `CFB8` is incremented on pickup (class-8 chest object, `$C8:E2F6` -> object action) was **not** traced.
- Orb drop gate (`$C8:E199`, executed in §13): a drop of type `t` becomes a plain consumable id 0 when `CFB8[t] + 1 >= CFC0[t]`.

### 11.5 Magic level [V] (`$D0:4DCD`, called on the first hit of every hero spell)
```
L = level nibble of the spell's element, prog = E1D8[e]            # e = E177
cap = $CFFC; if cap == 8: cap = 9
if L >= cap:       nothing
else:              gain = 9 - L;  if $ED bit 7 clear: gain >>= 1   # $ED bit 7 is set in play (all saves), so 9 - L
                   p = prog + gain
                   if p < 100:      prog = p
                   elif L == 8:     prog = 99
                   else:            prog = 0; L += 1                # level up (message + sound)
```
So spells only level while `L < CFFC` (CFFC = 8 means no cap); with `CFFC = 0` (new game) magic never levels. Casts needed (first hits): `ceil(100 / (9 - L))` per level: 12 at level 0, 20 at level 4, 50 at level 7; level 8 never advances. The cast itself uses `L` (and 7 instead of 8 for heroes/bosses with the 50% roll of §5.1).

### 11.6 `$CFFC` / `E1E6` [V]
`E1E6` of every hero is loaded from `$CFFC` at object init (`$C0:4850`), of every monster from `$CFFB` (`$C0:4819`). New game sets `$CFFC = 0` (`$C0:5787`); all six save states have `$CFFC = 8`, `$CFFB = 0`. `E1E6` enters the damage of every non-glancing physical or magic hit as `+ E1E6^2` (and in the `rnd` bound): **+64 for heroes with `$CFFC = 8`**, 0 for monsters. This replaces the earlier statement that it is 0 in normal play; the model and validators already take `E1E6` from the objects. What raises `$CFFC` during the story is not determined (no routine examined writes it after the new-game init).

### 11.7 Display rules [C]
The level-up message prints the nibble itself (weapon level 0..8, spell level 0..8; no +1): the scratch digit left in `$A6` equals the new nibble. The upgrade screen (`$C7:6461`) prints `CFB0+1` and `CFB8+1`. No routine that draws progress from `E1D0`/`E1D8` was found; progress is 0..98/99 as stored.

## 12. Status effects

Validation: `tools/validate_status_rules.py` runs the real apply routine `$C8:E301` on 1,500 random (current status, new status, immunity, damage, magic defense) tuples and compares the resulting status word and the four timers with the model below: 0 mismatches. `tools/status_timing.py` runs the real combat tick `$C0:3A79` until each status clears. Data: `data/status_effects.json`.

### 12.1 The status word and its bits
`word = E191 << 8 | E190` (16 bit). Bits are identified by mask only; the sources are rows of the spell, weapon, attack and item tables.

| mask | evidence / effect | timer |
|---|---|---|
| 0x0001, 0x0002 | `E190 & 3`: dying/removal countdown `E1B4`; a chest object sets bit 0 when opened. Not part of the status cascade; item id 4 clears the whole low byte, so it clears them too | `E1B4` |
| 0x0004 | set by spell 02, player weapons 37/42/56, boss rows 23/75/76 [V]; effect found: attacker accuracy -1/16 in the hit test (§4.2) | `E1B2` |
| 0x0008 | no spell/attack sets it; the stat build subtracts `Agi/16` while it is set | `E1B2` |
| 0x0010 | set by spell 1E [V]; cleared by any damaging hit (`$C0:5119`); doubles the crit chance against the target (`$C0:533D`) | `E1B2` |
| 0x0020 | set by spell 09, boss rows 1/14/55/86/107; cannot act (mask `C160`) | `E1B2` |
| 0x0040 | set by spell 03, boss rows 7/15/58; cannot act; applying it halves HP (`HP = HP/2 + 1`, `$C8:E491`) | `E1B2` |
| 0x0080 | set by spell 14, player weapons 31/48/51, boss row 71 [V]; effect not determined | `E1B3` |
| 0x0100 | set by spell 16, boss rows 18/73 [V]; cannot act; sprite size by spell level (<4, <8, 8) | `E1B3` |
| 0x0200 | toggled by item id 9, set by monster/boss attacks [V]; own damage forced to 1, defense /4 | none (until cleared) |
| 0x0400 | toggled by item id 10 [V]; no hit is resolved on the actor (`$C0:4F7B`) | none |
| 0x0800 | set by spell 18 [V]; monsters become one of 8 random sprites (`$C8:E5F3` table); heroes are always immune (their immunity word always includes 0x0800) | `E1B5` |
| 0x1000 | toggled by item id 8; set by monsters and boss rows 16/21/24/47-49; sprite offset +0x70 | `E1B5` |
| 0x2000 | set by spell 07, monster attacks (25-80%), boss rows 4/9/30/31/64/77/84/98 [V]; 1 HP per timer drop | `E1B6` |
| 0x4000 | set by spells 0F and 11, monster attacks, boss rows 0/11/53/54/85/108 [V]; same drain as 0x2000; cannot act (`$C0:BD46` mask `C160`); removes 0x2000 | `E1B6` |
| 0x8000 | KO flag; clears every other bit; removed by spell 21 and item id 5 | - |

### 12.2 Applying a status (`$C8:E301`, model in `validate_status_rules.py`)
```
new  = add & ~immunity                      # immunity = E1AA: monsters = record bytes 20-21, heroes = OR of the 3 armor words | 0x0800
w    = (current | new) & ~immunity          # the target also LOSES any current bit it is immune to
if w & 0x8000: w &= 0x8000                  # dead overrides everything
cascade (each rule only looks at the bits left by the previous one):
  0x0040 -> w &= 0x9AC0 ; HP = HP/2+1      0x0020 -> w &= 0x9AE0     0x0010 -> w &= 0xFBF0 (+E1B1 bit0)
  0x0008 -> w &= 0xFBF0                     0x0004 -> w &= 0xFFFC
  0x1000 -> w &= 0x92FF
  0x0800 -> w &= 0xF7FF if w & 0x0260 else w &= 0x9A13
  0x0400 -> w &= 0xFBFF if w & 0x617B
  0x4000 -> w &= 0xDAFF                     0x2000 -> w &= 0xDFFF if w & 0x1860
```
So the low-byte bits are mutually exclusive in the order 0x0040 > 0x0020 > 0x0010 > 0x0008 > 0x0004; bit 0x1000 wipes `0x6D00`; bit 0x4000 wipes `0x2500`; bits 0x0040, 0x0020, 0x0800 and 0x1000 remove 0x2000 (`0x1860`).
A timer is (re)loaded only for bits that were not already set: `E1B2` for `0x007C`, `E1B3` for `0x0180`, `E1B5` when `0x1C00` is new (only `0x1800` is counted down), `E1B6` for `0x6000`. The same cast re-applied does not refresh a running timer.

**Duration** `d = max(20, low byte of ((V >> 2) - (magic_defense >> 1)))`, 20 when the difference is negative, where `V` is the damage value before defense of the hit (`$96`; weapons: the capped pre-defense damage, hero spells: the spell power byte, monster spells: record byte 18/19). Spells (power 61): always 20. Weapon hits: `V >> 2` is up to 249 (damage 999), so strong hits give longer statuses (e.g. damage 300 and mdef 0: 75 timer units).
Timer drop: once every 4th combat tick (first drop on tick 1): lifetime `4d - 3` ticks (77 ticks for d = 20) [V executed]. At 12.02 ticks/s that is **6.4 s** for d = 20 (ordinary actors; bosses of the C2 engine with flags high byte `&3 == 0` tick at the same 12.02 Hz, other flag classes at `$56` = 1 or 2: §1.3).
Buff/debuff bytes `E1B0` (DEF/EVA/ACC/ATK +-25%, §1.1) use the same cadence: DEF `E1BC`, EVA `E1BB`, ACC `E1BA`, ATK `E1B7`, loaded with the same `d` by the buff handlers (`$C8:EB04`, EB20, EB39, EBCA).

### 12.3 Damage over time [V executed]
Status bits 0x2000 and 0x4000 are the same code (`E191 & 0x60`, `$C0:3D5F`): on every timer drop the actor loses **1 HP** (sound `0x39`) and the status is removed instead when the HP would reach 0 (so it never kills; stops at 1 HP). 3 HP/s at 12 ticks/s (1 HP per 4 ticks); at most `d` HP per application (19 for d = 20). Heroes and monsters alike.

### 12.4 Which hits inflict a status
- Weapon hit (`$C0:5119`): if `attacker.E199 & defender.E1AA != 0` nothing happens (ONE shared bit blocks the whole word); otherwise with `rnd(100) < E1F7` and pending damage > 0 the word `E199` is queued. Hero weapons: 80% for all 72 rows (99% for row 17); a Saber spell ORs its status word into `E199` for its hit counter (`E19D = (level+1)*4` hits), so every Saber hit has the weapon's chance (80%, 99% for row 17). Monster attack rows: 25/50/60/80/99% per row (`data/weapons.json` ids 72+), boss rows: `data/boss_attacks.json`.
- Spell hit: no roll; the status word of the spell row is applied bitwise through the immunity mask on the first hit of the cast (§5). Statuses by spell: `data/spells.json` / §7.
- Immunity words: monsters `data/monsters.json` `status_immunity` (41 records are immune to everything but bits 0-1: 0x7FFC), heroes `data/armors.json` `status_immunity` (accessory rows 43, 46, 59, 60...).

## 13. Monster drops

Everything here was executed: `tools/validate_drops.py` runs the real death routine `$C0:4203` on 3,360 (monster id, RNG state) pairs, the real chest-content routine `$C8:E12C` on 840 pairs (with random orb counters) and compares with the model: 0 mismatches. Data: `data/drops.json` (one entry per monster id 0-0x56 with a drop row: raw bytes, decoded fields and the outcome probabilities).

### 13.1 Row format (5 bytes at `D0:3A50 + monster_id*5`, `0xFF` row = never drops)
| byte | meaning |
|---|---|
| 0 | bits 0-5 `chance`: a chest appears when `chance >= (rnd_byte & 63) + 1`, i.e. probability `chance / 64`; bit 6: always (skip the roll); bit 7: the chest object gets 255 HP instead of 0 (`$C0:42A8`), purpose not determined (set for 32 monsters, levels 6-69) |
| 1 | high nibble `n`: trap threshold `t = n * 8` (`(b & 0xF0) >> 1`); low nibble: not read by any routine examined |
| 2 | bits 3-5 `a` (0..7): content roll threshold; bits 6-7 `mode` (below); bits 0-2 unused |
| 3, 4 | the two possible contents, byte 3 when the content roll `r = rnd_byte & 63` satisfies `r >= a` (prob. `(64-a)/64`), byte 4 otherwise |

`mode` decides what each byte is: 0 = gold, gold; 1 = item, item; 2 = byte 3 gold, byte 4 item; 3 = byte 3 item, byte 4 gold.
- **Gold**: the byte is the amount added to the party gold, 1..255 (it is about twice the monster's kill gold, e.g. 14 vs 7).
- **Item byte** (same encoding as the inventory-add routine `$C0:6420`): `0x00-0x14` head armor row, `0x15-0x29` body, `0x2A-0x3E` accessory (so the byte is the armor row id of `data/armors.json`), `0x40-0x4B` consumable id (byte - 0x40, see §16), `0x80-0x87` weapon orb of type byte-0x80. An orb drop is replaced by consumable byte 0x40 (id 0) when `CFB8[t] + 1 >= CFC0[t]` (§11.4), otherwise the chest object becomes an orb pickup (class 8).

### 13.2 What happens on death (`$C0:4203`)
1. Only ordinary monsters roll (not heroes `E1FB & 0x80`, not bosses `& 0x40`, not object ids 0x20/0x2E/0x3F marked `& 0x01`). EXP, gold (`E1C8` = record bytes 27-28, added immediately) and weapon progress are paid first (§8, §11.2).
2. Chest roll: `chance >= (rnd & 63) + 1`, or bit 6. No chest -> nothing.
3. Chest class (the trap kind, `E1C8` of the chest object) from the monster level `L`: `L < 10`: index = rnd(3) (0..2); `L >= 10`: 2; `L >= 15`: 3; `L >= 25`: 4; `L >= 30`: 5; `L >= 36`: 6, and 1/8 (`rnd < 0x20`) 7; the class is `[2,3,4,1,5,7,6,0][index]` (`data/misc.json` `kill_item_class_table`). So L < 10: classes 2, 3 or 4; 10-14: 4; 15-24: 1; 25-29: 5; 30-35: 7; >= 36: 6 (0 with probability 1/8).
4. The monster object becomes the chest: level 0, max HP 0, `E1B1 = 0x80`.

### 13.3 Opening the chest (`$C8:E0B0`, contents `$C8:E12C`) [V for contents, C for the rest]
- A chest dropped by a monster (max HP 0) may be a **trap**: when `t >= opener.Agi` (t from byte 1) the opening hero triggers it with probability 1/2 (RNG bit 0 clear) and receives no loot; otherwise the loot is paid (no check when Agi > t).
- Trap effect by class (`$C8:E259`): 0 and 7 none; 1 one status chosen at random from {0x0200, 0x1000, 0x0010}; 2 and 4 HP damage `((rnd & 7) + hero_level_index + 1) & 255`; 3 sets bit 0x2000 (no timer set); 5 sets bit 0x0040; 6 with 1/8 HP damage equal to the hero's current HP, otherwise HP set to 1; 8 spawns the orb pickup. [C]
- Loot: roll `r = rnd & 63`; pick byte 3 or byte 4 per 13.1; gold is added at once, items go through `$C0:6420` (inventory-add; with a message). A full inventory leaves `CF0F` non-zero and shows the other message variant.

### 13.4 Summary of the drop table
84 monster ids have a row (0-0x53); ids 0x54-0x56 and the bosses have `FF` rows (bosses give no chest). Chest probability is 4/64 = 6.25% for 77 monsters, 8/64 = 12.5% for id 0, and 0 for ids 5, 32, 44, 46, 63 and 79 (no row uses the "always" bit). Row 0, for example: 12.5% chest, content 89% consumable id 0 / 11% 4 gold. All rows: `data/drops.json`.

## 14. Area / multi-target spells: the damage divisor (`E176`)

**There is no per-spell constant.** `E176` of the caster is the number of valid targets of THIS cast (1..3) and is the final divisor of the damage and heal formulas (§5.2, `v //= E176` at `$C8:E969`; the handler is skipped altogether when `E176 == 0`, `$C8:E7DD`). It is written when the cast starts, together with the target list `E178-E17A` (target slot + 1, 0 = empty) and the "already hit" list `E172-E174` (a target is hit at most once per cast, `$C8:E739`). Cross-checked on a save state: Cure Water with `E176 = 3`, `E178..E17A = 1,2,3`, hit list `0,1,2`; Freeze with `E176 = 1`, one target.

| caster | how the count is made |
|---|---|
| hero, hostile spell (spell row byte 8 = `0x81`, 24 spells) | target list is built automatically by `$D0:DA60` from the 3 monster slots: valid = object present, on screen (`8 <= x < 0xF8`, `y < 0xD8`), alive (`E191` bit 7 clear) or object id 0x54/0x55; the count of valid targets (1..3) is stored in `E006` by `$C0:7364` and becomes `E176` |
| hero, ally spell (byte 8 = `0x01`, 14 spells) | same list built over the 3 heroes; the player's target choice (`1818`: one or all) gives 1 or the number of valid allies; `0x40` (2 spells, ids 20 and 23), `0xA0` (Analyzer, hostile + object test), `0x00` (Moon Energy, self) |
| monster, AI bytecode (`$C1:1E47` single / `$C1:1E98` area) | single: `E176 = 1`, target = the one stored in `E1AD`; area: `E176` = number of valid opposing actors found by the scan (1..3), 0 = cast fails |
| boss state script op `0x0E` (`$C2:396D`) | parameter bit 8 = area: `E176` = number of alive actors on the target side (1..3); clear: `E176 = 1` at the stored target; bit 9 = target side is the monsters (own side buffs/heals). Per-boss lists: `data/boss_records.json` |

So an area spell does `damage / n_targets` per target (rounded down after the element multiplier, before the defense roll): with 3 valid targets each takes one third; with one target the full damage. The same holds for the party-wide healing of Cure Water (`/3` with three allies). Spell row byte 8 per spell: `data/spells.json` `target_flags`.
Spells whose damage uses this divisor: every row with `0x81` (ids 00 01 02 06 07 08 0C 0D 0E 10 11 12 13 14 16 18 19 1A 1E 1F 24 25 26 28) and spells 0A and 0B when several allies are targeted.
Not determined: the exact in-engine hero code that copies the list count into `E176` (observed in a save and in the targeting code, not executed end to end); whether the 3-target cap leaves a 4th monster untouched (only 3 monster slots exist, so it cannot occur).

## 15. Boss attack rows, boss records, boss id 0x7F

Tools: `tools/boss_records.py` (static decode of the 15 native boss records and their state scripts), `tools/boss_sim.py` (spawns a boss with the game's own spawner `$C2:0000` on the map-246 save state and steps the real engine; the attack-row loader call `JSL $C0:006C` is intercepted and logged; no hero is hit), `tools/validate_boss_attacks.py`. Data: `data/boss_records.json`, `data/boss_attacks.json` (115 rows).

### 15.1 How a boss picks the attack numbers [V]
- A boss never uses the weapon table. `JSL $C0:006C` (= `$C0:45D6`) takes a row id, stores it in `E1E3`, and copies row `D0:BDC1 + id*7` into the object: `E194` = word 0, `E197` = accuracy, `E198` = Str + power (8 bit), `E199` = status word, `E1F7` = status chance. All 115 rows were loaded through the real routine and compared with `data/boss_attacks.json` (0 mismatches).
- The row is set by state-script op `0x13` (named `C0_006C` in `tools/statescript.py`; op `0x0C` (`SET_E1E3` in `statescript.py`) only stores the row id in `E1E3` without loading it and is unused by the 15 records) and by native handlers (`LDA #id / JSL $C0:006C`; 17 call sites in bank C2 besides the op handler `$C2:3947`).
- A boss record whose weapon bytes (23, 24) are 0 starts with row 0 (power 35, status 0x4000 at 99%) until a state script changes it; all 41 boss records have 0 there.
- Which rows each of the 15 native boss records uses (static, from the state scripts; native handlers add the rows marked in the sim table):

| record | C2 address | flags | attack rows in its state scripts / handlers (static) | spells (a = area, o = own side) |
|---|---|---|---|---|
| 0 | C2:D080 | 1C11 | 3(12) 10(11) 11(11,4000,99%) 68(7) 99(10,0010,99%) | 01 01a 1Co |
| 1 | C2:D658 | 9C01 | 7(65,0040,99%) 39(70) 40(84) 41(94,0010,33%) 43(98,0010,99%) 44(94) 45(103,0010,33%) | 00 00a 05o |
| 2 | C2:D20A | 1C11 | 47(48,1000,33%) 48(43,1000,33%) 49(52,1000,33%) | 1Co |
| 3 | C2:DF9E | 9C11 | 1(34,0020,99%) 2(125) 53(40,4000,50%) 72(34) | 12 13 14 15 06a 07a 09a 0Ca 0Da 0Ea |
| 4 | C2:E5AD | 9C02 | 19(81,0010,99%) 75(76,0004,99%) 77(76,2000,99%) 78(85,0010,33%) 81(81) 82(95) | 06 08 25 26 |
| 5 | C2:DD35 | 9C11 | 36(35) | 0Bo 0Bao |
| 6 | C2:D451 | 1C11 | 13(124) 50(106,0010,33%) 52(111,0010,50%) | 1Co 29o |
| 7 | C2:EB49 | 9C01 | 25(93) 26(69) 63(44,0010,33%) 65(46,0010,33%) 66(36,0010,33%) 70(60) | 04o 22o |
| 8 | C2:E82E | 9C01 | 14(93,0020,99%) 15(89,0040,99%) 59(89,0010,99%) 64(89,2000,99%) 71(89,0080,99%) 73(89,0100,99%) 74(89,0200,99%) 76(89,0004,99%) 110(127,0010,99%) | 00 06 08 13 24 25 26 |
| 9 | C2:E120 | 1C11 | 22(71,0200,99%) 100(71) | 00 01 06 07 0C 0E 12 14 26 |
| 10 | C2:ECFD | 1811 | 18(67,0100,80%) 58(68,0040,99%) 60(40) 61(59,0200,99%) 62(50,1200,50%) | 00 01 |
| 11 | C2:F00C | 1801 | 2(125) 16(0,1000,50%) 18(67,0100,80%) 20(0,0010,50%) 54(120,4000,99%) 55(120,0020,99%) 103(123) 109(125) | 06 0D 13 |
| 12 | C2:DAEA | 9C11 | 0(35,4000,99%) 5(37) 21(22,1000,99%) 33(34,0010,50%) 34(36,0010,33%) 35(33) | 0C 10 |
| 13 | C2:E2F5 | 1801 | 8(33,0010,99%) 17(37,0010,99%) 56(20) 57(48) | 0C 0E 10 16 12a 13a 14a |
| 14 | C2:D8D8 | 1C19 | 79(100) 92(120) 93(110) 95(120) | 1E 1F 22o |

### 15.2 Boss id -> record -> rows (runtime, 2 seeds x 3,000 frames each, no heroes on the arena)
`record` = index into the 15 records (matched through the init handler of the spawned object); `-` = no native record (object created with flags `0x1811`, `0x9C11` or `0x180D` and no handler pointers; these bosses are driven by the AI bytecode engine or by code reached from other tables).

| boss id | record | attack rows seen in the real engine (power, status, chance) | spells seen |
|---|---|---|---|
| 0x57 | 0 | 68(7) 99(10,0010,99%) | 01 |
| 0x58 | - | 10(11) 23(22,0004,50%) | 06 08 0B |
| 0x59 | - | 28(30) 30(25,2000,33%) | - |
| 0x5A | 1 | 39(70) 40(84) | 05 |
| 0x5B | 12 | 34(36,0010,33%) | - |
| 0x5C | - | 96(33) 97(42,0010,50%) | - |
| 0x5D | 13 | 56(20) | 13 |
| 0x5E | 3 | 1(34,0020,99%) 72(34) | 06 |
| 0x5F | 5 | - | - |
| 0x60 | 7 | 63(44,0010,33%) | 04 |
| 0x61 | - | 16(0,1000,50%) 23(22,0004,50%) | 08 0B 13 |
| 0x62 | 4 | - | - |
| 0x63 | 0 | 68(7) 99(10,0010,99%) | 01 |
| 0x64 | 7 | 63(44,0010,33%) 65(46,0010,33%) 66(36,0010,33%) | 04 |
| 0x65 | 2 | 47(48,1000,33%) 48(43,1000,33%) 49(52,1000,33%) | 1C |
| 0x66 | 1 | 39(70) 40(84) | 05 |
| 0x67 | - | 28(30) 30(25,2000,33%) | - |
| 0x68 | - | 29(89) 30(25,2000,33%) | 1E 1F |
| 0x69 | 10 | 60(40) | 01 |
| 0x6A | - | 83(88) 84(88,2000,99%) 85(88,4000,66%) 86(88,0020,66%) | 24 25 26 90 |
| 0x6B | 12 | 34(36,0010,33%) | - |
| 0x6C | - | - | - |
| 0x6D | - | 96(33) 97(42,0010,50%) | - |
| 0x6E | 14 | 95(120) | 1F 22 |
| 0x6F | 9 | 22(71,0200,99%) 100(71) | 26 |
| 0x70 | 6 | 50(106,0010,33%) 52(111,0010,50%) | 1C 29 |
| 0x71 | 5 | 36(35) | - |
| 0x72 | 7 | 63(44,0010,33%) 65(46,0010,33%) 66(36,0010,33%) | 22 |
| 0x73 | 11 | - | - |
| 0x74 | 3 | 53(40,4000,50%) 72(34) | 0D |
| 0x75 | 11 | - | - |
| 0x76 | 13 | 56(20) 57(48) | 0E |
| 0x77 | 11 | - | - |
| 0x78 | 4 | - | - |
| 0x79 | 8 | 14(93,0020,99%) 15(89,0040,99%) 59(89,0010,99%) 64(89,2000,99%) 76(89,0004,99%) 110(127,0010,99%) | 24 |
| 0x7A | 5 | 36(35) | - |
| 0x7B | 10 | 18(67,0100,80%) 58(68,0040,99%) 60(40) | - |
| 0x7C | - | - | 07 |
| 0x7D | 3 | 2(125) 72(34) | 13 |
| 0x7E | - | - | - |
| 0x7F | - | 113(92) 114(120) | 22 28 |

Caveat: this table was produced with the earlier harness that called the boss engine on every frame (twice the real tick rate, see §1.3); the rows and spells seen per boss are valid, but a boss that fires rarely may have been seen in too few ticks of a 3,000-frame run under the real schedule. Per-boss runs have not been repeated.

Notes: the same record serves several bosses (e.g. record 7 = ids 0x60, 0x64, 0x72; record 3 = 0x5E, 0x74, 0x7D; record 12 = 0x5B, 0x6B); the rows listed for a boss in the first table may be a subset of its record (only what the unattended boss actually fired). Bosses 0x6C and 0x7E created no object in this state (spawn gate) and 0x5F/0x62/0x73/0x75/0x77/0x78 never fired an attack row in 3,000 frames without heroes; why is not determined.
The Dark Lich (record 8) in full, state by state (state ids of `docs/dark-lich.md`): projectile states 0F-17 use rows 64 (power 89, status 0x2000 99%), 59 (89, 0x0010 99%), 76 (89, 0x0004 99%), 15 (89, 0x0040 99%), 74 (89, 0x0200 99%), 71 (89, 0x0080 99%), 73 (89, 0x0100 99%), 14 (93, 0x0020 99%), 15; every hands state (1E-27) uses row 110 (power 127, 0x0010 99%). Attack = `Str + power & 255` = 74 + power (so 163 and 201).

### 15.3 Boss id 0x7F [full description in `docs/mana-beast.md`]
- Record: level 73, HP 9990, MP 99, Str 99, spell power 45/45, magic level 8, weapon level 4 (`data/monsters.json` id 127). Spawned object: flags `0x180D`; logic = the 21-phase machine in bank C2 (table `C2:8F51`), which loops until the dead bit is seen in phase 0xB.
- Attack rows set by that code: 114 (power 120) at the end of phase 4, 113 (power 92) at the end of phase 5, 111 (power 89) in phase 7; each is a scripted hit on all three heroes, never a contact attack. Spells: Wall (0x22), Dispel Magic (0x26) and Lucent Beam (0x28) from phase 0xB (`C2:93CB`, choice by the Wall status of the boss and of the nearest hero).
- Earlier versions of this section said the boss idled in its intro phases; that came from calling the engine without the game's frame loop. With the full frame (`$C0:B08C`) it cycles through all phases. Timings, hit windows and the end of the fight are in `docs/mana-beast.md`.

## 16. Consumable items (ids 0-11)

Executed: `tools/dump_gap_tables.py` runs `$C0:54E7` on a hero (500 max HP, 100 HP, 50 max MP, status words 0x0010, 0x0100 and 0x2000 set) and on a dead hero, for every id; results in `data/item_effects.json`.

| id | effect on a living hero (pending value, applied by `$C0:4004` next tick) | on a dead hero |
|---|---|---|
| 0 | HP +100 (`E1F3`) | nothing (heal is skipped for dead actors) |
| 1 | HP +250 | nothing |
| 2 | HP set to max (`E1F3` = max HP) | nothing |
| 3 | MP +50 (`E1F6`, cap 99 and max MP) | nothing |
| 4 | clears `E190` and every `E191` bit except bit 7; timers `E1B2-E1B6` set to 1; HP unchanged | nothing |
| 5 | HP to max AND clears the dead flag (`E191` bit 7) | **revives** at max HP |
| 6, 7 | no effect in this routine | - |
| 8 | toggles `E191` bit 4 (status 0x1000), `E1B5 = 0xFF` | toggles |
| 9 | toggles `E191` bit 1 (status 0x0200), `E1B5 = 0xFF` | toggles |
| 10 | toggles `E191` bit 2 (status 0x0400) | toggles |
| 11 | none | - |

`item_effects.json` also stores the effect byte of each item row (`D0:4152 + id*16`: 100, 250, 1, 50, 1, 250, 1...): it is used only by ids 0, 1 and 3 (HP/MP amount); id 2/5 use the max-HP shortcut and 4 ignores it. Heal values are subject to the application rules of §5.4 (cap 999 HP / 99 MP, max HP). The toggles are an XOR of the bit, so a second use removes the bit; the 0xFF timer of 8 and 9 is irrelevant for 0x0200 (no timer) and counts down only for 0x1000 (1020 ticks). Which routine decides when an item can be used from the menu was not determined.
Prices: `data/prices.json` holds the raw price word tables (range table `D8:FB84`, read at `$C0:7CA5`), in table order: consumables, armor rows (head 0-20, body 21-41, accessory 42-62) and the orb price table. The consumable entries are listed in table order only; the pairing of each entry with an item id above was not verified.

## 17. Everything in seconds (60.0988 Hz frames; ordinary actors tick every 5th frame)

| quantity | frames / ticks | seconds | status |
|---|---|---|---|
| charge, one stage | 90 frames | 1.50 | [V executed] |
| charge, stages 1..8 | 89, 179, ..., 719 frames | 1.48 ... 11.96 | [V executed] |
| weapon recharge gauge `E1ED` after a swing | `(100-Agi)/2 + 50` frames (Agi 50: 75, Agi 99: 50) | 1.25 / 0.83 | [V] |
| status timer unit | 4 ticks = 20 frames | 0.333 | [V executed] |
| status/buff duration, d = 20 (all hero spells) | 77 ticks | 6.4 | [V executed ticks; seconds = ticks / 12.02] |
| status duration, damage 300, mdef 0 | 4*75-3 = 297 ticks | 24.7 | [V formula] |
| poison / engulf damage | 1 HP per 4 ticks | 3.0 HP/s | [V executed] |
| Dark Lich / C2 bosses with flags 0x9C or 0x18 | tick on 1 of 5 frames (`$56` = 0) | 12.02 ticks/s | [V, `docs/dark-lich.md`, `docs/mana-beast.md`] |
| weapon level, kills per level | `ceil(99/(9-wl))` kills, x2 on lower-level monsters | - | [V] |
| spell level, casts per level | `ceil(100/(9-L))` first-hits | - | [V] |

## 18. Open questions (not determined)
These are unknown; no values or formulas are claimed for them.
- What writes `$CFFC` during the story after the new-game init; where `$CFB8` is incremented on pickup; where the initial `$CFC0` table (9,8,9,9,9,9,9,9 in every save) comes from; the class-8 chest object (orb pickup).
- Which in-game ailment each status bit is (only the sources are listed, §12.1); the sources of bit 0x0008; the effect of bit 0x0080.
- Whether the tick rate of ordinary monsters (12 Hz, §1.3) holds in a running frame loop; it comes from reading the dispatcher.
- Boss id 0x7F: see `docs/mana-beast.md` section 12. Other bosses: attack rows are those fired unattended in 3,000 frames plus the static rows of their record; bosses 0x58/0x59/0x5C/0x61/0x67/0x68/0x6A/0x6D/0x7C use no native record and 0x6C/0x7E created no object in the test state.
- Drop row byte 1 low nibble; the purpose of byte 0 bit 7; the trap-spring code path (`$C8:E1ED`, read, not executed); the hero code that copies the target count to `E176`.
- The weapon byte-5 and element bytes in physical damage (§6), the `BIT $0040` armor branch, `$CC7A`, `$CC76`, monster record byte 22, weapon-row byte 2 upper bits, `E1B1` bit 1, `E1FB` bit 5.
- How monster projectile/ranged attacks reach `$C0:4F7B`; all contact attacks follow §4, spell hits §5, both executed on real routines with synthetic objects, not in a live battle (the save states contain no live monsters).
- Menu-level item restrictions; the upgrade-shop purchase routine was read, not executed.
- The pairing of price table entries with item ids (§16) and of the `E177` element index with element masks (§11.1).
- The harness never runs the PPU/sound; `$C3:0000/0004` are stubbed. All save states are late-game (levels 66-71, `$CFFC = 8`); anything that depends on story variables was checked only at those values.

## 19. Reproduce
Set `R` to your ROM, `S` to a ZSNES save state of a late-game session with the party on a map, `A` to a save state taken in the map-246 arena, and `D` to a directory with save states.
```
R=path/to/rom.sfc; S=path/to/state.zs2; A=path/to/arena.zs3; D=path/to/states
python3 tools/validate_phys.py  "$R" "$S" 800      # physical model vs ROM
python3 tools/validate_magic.py "$R" "$S" 400      # magic/heal model vs ROM
python3 tools/validate_exp.py   "$R" "$S"          # EXP / level-up
python3 tools/hero_stats.py     "$R" "$D"/*.z1? "$D"/*.zs?      # stat build vs live hero objects
python3 tools/weapon_level.py   "$R" "$S" 2000     # weapon level-up rule vs $C0:4358
python3 tools/validate_magic_level.py "$R" "$S"    # spell level rule vs $D0:4DCD
python3 tools/charge_timing.py  "$R" "$S" 8        # charge stage timing from $C0:B330
python3 tools/validate_drops.py "$R" "$S"          # death + chest routines vs drop model
python3 tools/validate_status_rules.py "$R" "$S"   # $C8:E301 cascade, immunity, timers
python3 tools/status_timing.py  "$R" "$S" 20       # real combat tick: lifetime and damage over time
python3 tools/validate_boss_attacks.py "$R" "$A"   # all 115 boss attack rows through $C0:45D6
python3 tools/boss_sim.py "$R" "$A" 3000 1,2 79,7f > sim.jsonl ; python3 tools/boss_records.py "$R" data/boss_records.json sim.jsonl
python3 tools/dump_tables.py    "$R" data          # regenerate data/*.json (monsters, weapons, armors, spells, boss attacks, ...)
python3 tools/dump_gap_tables.py "$R" "$S" data    # drops, item effects, weapon levels, status effects, prices
python3 tools/flowdis.py        "$R" out.txt --auto C04004:10 C0514B:10    # recursive disassembly (ADDR:MX seeds)
```
Tools: `combat_env.py` (harness: run any routine on a save state), `rng.py`, `phys_model.py`, `magic_model.py`, `hero_stats.py`, `example_damage.py`, `names.py`, `flowdis.py`, `dump_tables.py`, `weapon_level.py`, `validate_magic_level.py`, `charge_timing.py`, `validate_drops.py`, `validate_status_rules.py`, `status_timing.py`, `validate_boss_attacks.py`, `boss_sim.py`, `boss_records.py`, `dump_gap_tables.py`.

## 20. Spells without direct damage (details in `docs/spells-non-damage.md`)
The class column of the spell table in section 5.5 is superseded for the non-damage spells by `docs/spells-non-damage.md` (every handler was executed on random caster and target objects and compared with a model, `tools/spell_effects.py`, tables in `data/spell_effects.json`). Short version [V]:
- Common value `V` = the heal-style spell value of 5.2/5.3 (`m = 4` for Speed Up, Defender, Lunar Boost, Cure Water, Remedy, Revivifier, sabers, Moon Energy, Wall, spells 20 and 23, Lucid Barrier; the element test for the others), divided by the number of targets. Buff timers are `V>>2`; status durations are `max(20, (V>>2) - (magic defence>>1))` timer units of 4 ticks.
- 02 Speed Down, 14 Silence, 16 Balloon, 18 Change Form and 1E Sleep Flower do no damage, they only apply a status word (no accuracy roll, only the immunity word). 07 Acid Storm and 10 Fire Bouquet deal damage and write a DEF-25% / ATK-25% buff byte (the 0x2000 word of row 07 is not applied); 11 Blaze Wall deals damage and applies 0x4000.
- Sabers: `E19D = 4(L'+1)` weapon hits, `E1AE` low nibble = `L'`, damage bonus `base/(10-L')` for `L' >= 1` (up to +50%), element bit into `E195` (Moon Saber = the drain flag 0x40), status word into `E199`.
- Remedy / Revivifier cure by shortening all status timers by `V>>2` units, or completely at `L' == 8` (or `L' >= 4` on one target); Revivifier revives a hero or boss and heals `V/(9-L')`. Wall blocks the next `L'+2` spell hits (spells 20, 23 and 26 pass); Lucid Barrier absorbs weapon damage (not spell damage) into a pool of `min(V, max HP)` with a flat guard of `defence/2/n` per hit.
- Corrections to earlier sections: 5.5 calls 02, 14, 16, 18, 1E "damage + status" (they deal no damage); 12.2 says spell durations are always 20 and buff timers use "the same d" (they follow V as above); 4.6 gives the Saber level as 1..9 with up to +100% (the level is 0..8, level 0 adds nothing, level 8 adds 1/2).
- Reproduce: `python3 tools/spell_effects.py "$R" "$S" 300 data/spell_effects.json`.

## 21. Hero movement (details in `docs/hero-movement.md`)
Movement is per frame (60.0988 Hz), not on the 12.02 Hz combat tick, in whole pixels (`E002/E004`); the velocity word `E006` is set by `$C0:B710` from the pad and applied by `$C0:D5C0` [V, `tools/hero_movement.py`, numbers in `data/hero_movement.json`]:
- walking 2 px per frame per pressed axis (120.20 px/s, no acceleration, diagonal not normalised: 169.99 px/s); running on a new press of the A button 3 px per frame (180.30 px/s, direction locked until A is released, then a recharge of `(100 - Agi)/2 + 50` frames in `E1ED`); charging a weapon (`E01B != 0` or `E01A >= 2`) and the statuses 0x0004 and 0x0400 make it 1 px per frame; 0x0020, 0x0040, 0x0100, 0x4000, 0x8000 stop it; equipment and level do not matter.
- wall collision is per axis on 16 px tiles with a probe box of x +6/-6 and y +4/-4; a refused diagonal keeps the X component, then the Y component; a corner contact nudges the hero sideways by 2 px per frame; facing on a diagonal is the horizontal direction.
- knockback when hit: opposite to the facing, 55 px in 40 frames (3, 2, 1 px per frame for 5, 5, 30 frames), whatever the damage or the attacker position.
- Reproduce: `python3 tools/hero_movement.py "$R" "$S" data/hero_movement.json`.

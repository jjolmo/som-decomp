"""Dump the gameplay-number tables of Secret of Mana (USA) to JSON (numbers only: no graphics, no text).
usage: dump_tables.py ROM OUTDIR
Writes monsters.json weapons.json armors.json spells.json hero_levels.json items.json misc.json.  File offsets are given inside each file."""
import sys, os, json, struct, romio
def u16(d, o): return d[o] | d[o + 1] << 8
def main(rom, out):
    os.makedirs(out, exist_ok=True)
    def w(name, obj):
        with open(os.path.join(out, name), 'w') as f: json.dump(obj, f, indent=1, sort_keys=False); f.write('\n')
    # ---- monsters: 29-byte records at 0x101C00 + id*29 (ids 0x00-0x7F) and the 5-byte drop rows at 0x103A50 + id*5
    mons = []
    for i in range(128):
        o = 0x101C00 + i * 29; r = rom[o:o + 29]
        mons.append(dict(id=i, level=r[0], hp=u16(r, 1), mp=r[3], str=r[4], agi=r[5], int=r[6], wis=r[7], eva=r[8], defense=u16(r, 9), mev=r[11], mdef=u16(r, 12),
                         type=r[14], element=r[15], exp=u16(r, 16), spell_power_int=r[18], spell_power_wis=r[19], status_immunity=u16(r, 20), unk22=r[22],
                         weapon_a=r[23], weapon_b=r[24], flags25=r[25], weapon_level=r[26] >> 4, magic_level=r[26] & 15, gold=u16(r, 27),
                         drop_row=list(rom[0x103A50 + i * 5: 0x103A50 + i * 5 + 5])))
    w('monsters.json', dict(source='record = 0x101C00 + id*29; drop_row = 0x103A50 + id*5', records=mons))
    # ---- weapons: 12-byte rows at 0x101000 (ids 0-71 player weapons, 72+ monster attacks)
    wp = []
    for i in range(256):
        o = 0x101000 + i * 12; r = rom[o:o + 12]
        wp.append(dict(id=i, type=r[0], stat_a=r[1], stat_b=r[2], enemy_type_mask=r[5], crit=r[6], hit=r[7], power=r[8], status=u16(r, 9), status_chance=r[11]))
    w('weapons.json', dict(source='row = 0x101000 + id*12 (graphics bytes 3,4 omitted); ids 0-71 player weapons in 8 types x 9, 72+ monster weapons',
                           stat_delta_table=list(rom[0x4B79:0x4B7D]), rows=wp))
    # ---- armors: 10-byte rows at 0x103ED0 (ids 0-63)
    ar = []
    for i in range(64):
        o = 0x103ED0 + i * 10; r = rom[o:o + 10]
        ar.append(dict(id=i, flags=r[0], defense=r[1], evade=r[2], mdef=r[3], mev=r[4], equip_mask=r[5], element_resist=r[6], status_immunity=u16(r, 7), unk9=r[9]))
    w('armors.json', dict(source='row = 0x103ED0 + id*10; ids 0-20 head, 21-41 body, 42-62 accessory (63 empty)', rows=ar))
    # ---- spells: 64-byte rows at 0x102AD0
    sp = []
    for i in range(42):
        o = 0x102AD0 + i * 64; r = rom[o:o + 64]
        h = u16(rom, 0x8E801 + 2 * i)
        sp.append(dict(id=i, power=r[10], accuracy=r[11], element=r[12], status=u16(r, 13), mp_cost=r[15], target_flags=r[8], handler=h))
    w('spells.json', dict(source='row = 0x102AD0 + id*64; handler = 16-bit address in bank C8 from table 0x08E801', rows=sp))
    # ---- boss / special attack table: 7-byte rows at 0x10BDC1 (read by $C0:45D6 with the attack id in E1E3)
    ba = []
    for i in range(115):
        o = 0x10BDC1 + i * 7; r = rom[o:o + 7]
        ba.append(dict(id=i, flags=u16(r, 0), accuracy=r[2], power=r[3], status=u16(r, 4), status_chance=r[6]))
    w('boss_attacks.json', dict(source='row = 0x10BDC1 + id*7 (115 rows, ids 0-0x72; the bytes after row 0x72 are a pointer table, not attack rows); atk = Str + power, E1E3 = id', rows=ba))
    # ---- hero level tables
    hl = {}
    for h, name in enumerate(('boy', 'girl', 'sprite')):
        rows = []
        for L in range(99):
            o = 0x104210 + h * 0x318 + L * 8
            rows.append([u16(rom, o), rom[o + 2], rom[o + 3], rom[o + 4], rom[o + 5], rom[o + 6], rom[o + 7]])
        hl[name] = rows
    ex = [rom[0x104B58 + 3 * i] | rom[0x104B58 + 3 * i + 1] << 8 | rom[0x104B58 + 3 * i + 2] << 16 for i in range(99)]
    w('hero_levels.json', dict(source='rows 0x104210 + hero*0x318 + level*8 (level is the 0-based internal level, displayed level = index+1); exp table 0x104B58 + level*3',
                               columns=['max_hp', 'max_mp', 'str', 'agi', 'con', 'int', 'wis'], heroes=hl, exp_to_next=ex,
                               exp_cap=9999999, gold_cap=9999999))
    # ---- consumables
    items = []
    for i in range(12):
        items.append(dict(id=i, effect_value=rom[0x104152 + i * 16]))
    w('items.json', dict(source='effect byte at 0x104152 + id*16 (read as HP for ids 0-1 and MP for id 3, see docs/rom-combat.md section 16)', rows=items))
    # ---- misc constants
    w('misc.json', dict(
        weapon_level_progress_threshold=list(rom[0x43AC:0x43B6]),
        element_opposite_pairs=[[1, 2], [4, 8], [16, 32]],
        ai_party_stat_tweak_by_CC7A=list(rom[0x473F:0x474F]),
        kill_item_class_table=list(rom[0x430D:0x4315])))
if __name__ == '__main__':
    rom = romio.rom_from_argv(); main(rom, sys.argv[1])

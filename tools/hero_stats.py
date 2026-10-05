"""Python model of the hero stat build ($C0:4530 -> 464F, 4B7D, 4AFF, 4BBE, 49AA, 4A0C, 4A2D, 4A75, 4BF9) from the ROM tables, and a check against hero
objects stored in ZSNES save states.   usage: hero_stats.py ROM STATE...
Tables (file offsets): level table 0x104210 + hero*0x318 + level*8; weapons 0x101000 + id*12; armor 0x103ED0 + id*10; exp 0x104B58 + level*3."""
import sys, romio, zsnes_state
STAT_DELTA = [0, 1, 5, -5]       # $C0:4B79
def table_row(rom, hero, level):
    o = 0x104210 + hero * 0x318 + level * 8
    return dict(maxhp=rom[o] | rom[o + 1] << 8, maxmp=rom[o + 2], str=rom[o + 3], agi=rom[o + 4], con=rom[o + 5], int=rom[o + 6], wis=rom[o + 7])
def clamp(v, lo, hi): return max(lo, min(hi, v))
def build(rom, hero, level, weapon, armors, status190=0, ai_tweak=None):
    """returns dict of derived stats.  armors = (E1E0, E1E1, E1E2) ids"""
    t = table_row(rom, hero, level)
    s = [t['str'], t['agi'], t['con'], t['int'], t['wis']]
    if ai_tweak is not None:                       # $C0:46D5-473E, only for party members not driven by a human controller
        for i, sh in enumerate((0, 2, 4)):
            s[i] += [0, 1, 2, -1][(ai_tweak >> sh) & 3]
    w = rom[0x101000 + weapon * 12: 0x101000 + weapon * 12 + 12]
    ar = [rom[0x103ED0 + a * 10: 0x103ED0 + a * 10 + 10] for a in armors]
    # 4B7D: armor flag byte bits 4..1 -> +5 to Str, Agi, Con, Int  (the "bit 6 -> -2" branch tests memory $0040, assumed 0)
    for a in ar:
        f = a[0]
        for i in range(4):
            if f & (0x10 >> i): s[i] = (s[i] + 5) & 0xFF
    # 4AFF: weapon stat codes
    s[0] = (s[0] + STAT_DELTA[w[2] & 3]) & 0xFF
    s[1] = (s[1] + STAT_DELTA[w[1] >> 6]) & 0xFF
    s[2] = (s[2] + STAT_DELTA[(w[1] >> 4) & 3]) & 0xFF
    s[3] = (s[3] + STAT_DELTA[(w[1] >> 2) & 3]) & 0xFF
    s[4] = (s[4] + STAT_DELTA[w[1] & 3]) & 0xFF
    # 4BBE
    if status190 & 0x08: s[1] -= s[1] >> 4
    s = [clamp(v if v < 128 else v - 256, 1, 99) for v in s]       # 8-bit wrap treated as signed, then clamp 1..99
    St, Ag, Co, In, Wi = s
    out = dict(str=St, agi=Ag, con=Co, int=In, wis=Wi, maxhp=t['maxhp'], maxmp=t['maxmp'])
    out['acc'] = min(99, (Ag >> 2) + w[7])            # E197 ($C0:49AA)
    out['atk'] = (St + w[8]) & 0xFF                    # E198
    out['status_inflict'] = w[9] | w[10] << 8           # E199
    out['status_chance'] = w[11]                       # E1F7
    out['eva'] = min(99, (Ag >> 2) + sum(a[2] for a in ar))        # E1A4
    out['def'] = min(999, Co + sum(a[1] for a in ar))              # E1A5
    out['mev'] = min(99, (Wi >> 2) + sum(a[4] for a in ar))        # E1A7
    out['mdef'] = min(999, Wi + sum(a[3] for a in ar))             # E1A8
    out['immune'] = ar[0][7] | ar[0][8] << 8 | ar[1][7] | ar[1][8] << 8 | ar[2][7] | ar[2][8] << 8 | 0x0800
    out['elem_resist'] = ar[0][6] | ar[1][6] | ar[2][6]
    return out
if __name__ == '__main__':
    rom = romio.rom_from_argv()
    for st in sys.argv[1:]:
        w = zsnes_state.load_wram(st)
        for s in range(3):
            b = 0xE000 + 0x200 * s
            if not w[b] : continue
            g = lambda o: w[b + o]
            g16 = lambda o: w[b + o] | w[b + o + 1] << 8
            wid = g(0x1E8) if (g(0x1E4) & 0x80) == 0 else g(0x1E9)
            a4 = s + 1 + (1 if s + 1 == 3 else 0)          # controller assignment nibbles $D9-$DB
            human = any((w[0xD9 + k] & 0x0F) == a4 for k in range(3))
            tweak = None if human else rom[0x473F + w[0xCC7A + s]]
            m = build(rom, g(0x1E7) - 0x80, g(0x181), wid, (g(0x1E0), g(0x1E1), g(0x1E2)), g(0x190), tweak)
            real = dict(str=g(0x188), agi=g(0x189), con=g(0x18A), int=g(0x18B), wis=g(0x18C), maxhp=g16(0x184), maxmp=g(0x187), acc=g(0x197), atk=g(0x198),
                        eva=g(0x1A4), **{'def': g16(0x1A5)}, mev=g(0x1A7), mdef=g16(0x1A8), immune=g16(0x1AA))
            diff = {k: (m[k], real[k]) for k in real if m[k] != real[k]}
            print(st[-6:], 'hero', s, 'lvl', g(0x181), 'weapon', wid, 'OK' if not diff else 'DIFF %s' % diff)

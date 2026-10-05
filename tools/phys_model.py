"""Python model of the SoM physical-hit resolution, derived from ROM routines $C0:4FED, $C0:505B, $C0:50CA, $C0:514B (+51E7, 52E7, 532C, 541B, 5119).
Every field name is the object offset from $7E:E000+slot*0x200 (see docs/rom-combat.md).  Validated against the real ROM code by validate_phys.py.
A "unit" is a dict with the object fields used (attacker = a, defender = d)."""
from rng import Rng
def cap(v, m): return m if v > m else v
def def_terms(d):
    """$C0:4FED -> (evade8E, defense87) of the DEFENDER"""
    ev = d['A4']
    q = ev >> 2
    if d['B0'] & 0x04: ev = (ev + q) & 0xFF
    elif d['B0'] & 0x08: ev = (ev - q) & 0xFF
    ev = cap(ev, 99)
    df = d['A5']; q = df >> 2
    if d['B0'] & 0x0001: df = (df + q) & 0xFFFF
    elif d['B0'] & 0x0002: df = (df - q) & 0xFFFF
    if d['E191'] & 0x02: df >>= 2
    return ev, cap(df, 999)
def acc_term(a):
    """$C0:505B first half: attacker accuracy $8D"""
    v = a['E197']
    if a['E190'] & 0x04:
        v -= v >> 4
        q = v >> 2
    else:
        q = a['E190'] >> 2      # ROM quirk: A still holds E190 here ($C0:5076), not $8D
    if a['B0'] & 0x10: v = (v + q) & 0xFF
    elif a['B0'] & 0x20: v = (v - q) & 0xFF
    v = cap(v, 99)
    if a['ED']: v >>= 1
    return v
def hit_test(a, ev, rng):
    acc = acc_term(a)
    r = rng.byte()
    half = ev >> 1
    t = ((r * half) >> 8) + half
    return acc >= t, acc
def elem_mult(a, d):
    """$C0:50CA -> $8F: 1 resisted, 4 weak, 2 normal.  NOTE the ROM tests the DEFENDER's own E194/E195 word against the defender's masks."""
    if d['E194'] & d['A2']: return 1
    if d['E194'] & d['A0']: return 4
    return 2
def mul100(p, q):   # $C0:543B: (p*q)/100 with p 8-bit, q 16-bit
    return (p * q) // 100
def damage(a, d, m8F, acc, ev, df, rng, slot_att, a_is_hero):
    """returns final damage (0 if not positive)"""
    E19B = a['E19B']
    if slot_att == 0 and a.get('CC76', 0): E19B = (E19B + a['CC76']) & 0xFF   # $C0:51EB
    atk = a['E198']
    D0 = ((E19B << 1) & 0xFF) + 4
    prod = D0 * atk
    v = (prod >> 2) & 0xFFFF
    base = v
    q = v >> 2
    if a['B0w'] & 0x0080: v = (v - q) & 0xFFFF
    elif a['B0w'] & 0x0040: v = (v + q) & 0xFFFF
    n = a['AE'] & 0x0F
    if n: v = (base // (10 - n) + v) & 0xFFFF
    v = ((v * m8F) & 0xFFFF) >> 1   # loop adds v m8F times, 16-bit, then LSR
    v = cap(v, 0x3E7)
    if a['E191'] & 0x02: v = 1
    # glancing / full roll
    r = rng.below(0x65)
    if r >= acc:
        v = cap(mul100(acc, v), 999)
    else:
        v = (a['E6'] * a['E6'] + v) & 0xFFFF
        v = (v + rng.below((v >> 4) & 0xFF)) & 0xFFFF
        v = cap(v, 999)
    # 52E7: defense with random
    r = rng.below(100)
    D = df
    if r >= ev:
        D = cap(mul100(ev, D), 999)
    else:
        D = cap((D + rng.below((D >> 4) & 0xFF)) & 0xFFFF, 999)
    # 532C: crit
    crit = False
    if (a['AE'] & 0xF0):
        crit = True; a['AE'] -= 0x10
    elif a['ED'] == 0:
        c = a['E196']
        if d['E190'] & 0x10: c = (c << 1) & 0xFF
        if a_is_hero: c = (c + (10 if slot_att == 1 else 5)) & 0xFF
        if rng.byte() < c: crit = True
    else:
        # $C0:5381 weapon-gauge path: no crit, half damage scaled by gauge (AC-E1ED)/AC, AC=(99-Agi)/2+80 (8-bit)
        v >>= 1
        ac = ((((99 - a['E189']) & 0xFF) >> 1) + 0x50) & 0xFF
        v = (v * ((ac - a['ED']) & 0xFF)) // ac
    if crit: v = (v << 1) & 0xFFFF
    # 541B
    if d['B1'] & 0x10:
        v = (v - (d['BF'] & 0xFF)) & 0xFFFF; D = 0
    sv = v - 0x10000 if v & 0x8000 else v
    return (sv - D if sv > D else 0), crit

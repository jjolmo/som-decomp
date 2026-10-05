"""Spells that do more than damage: run the real handlers and check a model of each one against the ROM code.
usage: spell_effects.py ROM STATE [N=300] [OUT.json]

Every case builds a caster (hero slot 0-2, or a monster made by the game's own $C0:55EC) and a target with random stats, casts through the
real hit entry $C8:E6D4 (hit list, MP, level progress, handler, pending-damage clearing) and compares the fields the handler writes with a
Python model written from the disassembly.  One line per spell id with the number of mismatches; the checks that need a special set-up
(Wall wrapper $D0:4C82, Lucid Barrier through $C0:4004, the weapon change of spells 20/23 through $C0:3F94, the level 8 roll $D0:4EAC, timer lifetimes through the
combat tick $C0:3A79) follow.  With OUT.json the numeric tables of data/spell_effects.json are written.
Documented in docs/spells-non-damage.md."""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, combat_env as ce, rng as R, magic_model as M
import validate_phys as VP

SPELL_ROW = 0x102AD0
TICK_HZ = 60.0988 / 5            # ordinary actors tick once per 5 frames (docs/rom-combat.md section 1.3)


def row(rom, sid):
    o = SPELL_ROW + sid * 64
    return dict(id=sid, power=rom[o + 10], acc=rom[o + 11], elem=rom[o + 12], status=rom[o + 13] | rom[o + 14] << 8, mp=rom[o + 15], tf=rom[o + 8])


def cap(v, m): return m if v > m else v


# ------------------------------------------------------------------ value pipeline ($C8:E8A0 + E8C0 + E990, same arithmetic as magic_model.py)
def elem_mult(elem, tu):
    if elem & tu['RES']: return 1
    if elem & tu['WEAK']: return 4
    return 2


def value(cu, tu, r, level, div, rng, fixed_m=None, hero_c=True):
    """returns (V, d94, m): V = $89 = $96 after $C8:E8C0 (before the target defense), d94 = target magic defense roll"""
    stat, p = M.spell_stat(cu, r['id'])
    if hero_c: p = r['power']
    d94 = M.target_mdef(tu, rng)
    acc = cap(((stat >> 2) + r['acc']) & 0xFF, 99)
    v = cap(((level + 2) * ((p + stat) & 0xFF)) >> 1, 999)
    if rng.below(0x65) >= acc:
        v = (acc * v) // 100
    else:
        v = (cu['E6'] * cu['E6'] + v) & 0xFFFF
        v = (v + rng.below((v >> 4) & 0xFF)) & 0xFFFF
    m = fixed_m if fixed_m else elem_mult(r['elem'], tu)
    v = (((v * m) & 0xFFFF) >> 1) // div
    return cap(v, 999), d94, m


def value_range(stat, power, level, m, e6):
    """(glancing, nonglancing_min, nonglancing_max, accuracy) of V for div = 1: the outcomes of the accuracy roll"""
    acc = cap(((stat >> 2) + 75) & 0xFF, 99)
    v = cap(((level + 2) * ((power + stat) & 0xFF)) >> 1, 999)
    g = cap((((acc * v) // 100) * m) >> 1, 999)
    b = (e6 * e6 + v) & 0xFFFF
    lo = cap(((b * m) & 0xFFFF) >> 1, 999)
    n = (b >> 4) & 0xFF
    hi = cap((((b + max(n - 1, 0)) * m) & 0xFFFF) >> 1, 999)
    return g, lo, hi, acc


def status_model(cur, add, imm):
    new = add & ~imm & 0xFFFF
    w_ = (cur | new) & ~imm & 0xFFFF
    if w_ & 0x8000:
        w_ &= 0x8000; new &= 0x8000
    if w_ & 0x0040: w_ &= 0x9AC0
    elif w_ & 0x0020: w_ &= 0x9AE0
    elif w_ & 0x0010: w_ &= 0xFBF0
    elif w_ & 0x0008: w_ &= 0xFBF0
    elif w_ & 0x0004: w_ &= 0xFFFC
    if w_ & 0x1000: w_ &= 0x92FF
    elif w_ & 0x0800: w_ &= 0xF7FF if w_ & 0x0260 else 0x9A13
    elif w_ & 0x0400:
        if w_ & 0x617B: w_ &= 0xFBFF
    if w_ & 0x4000: w_ &= 0xDAFF
    elif w_ & 0x2000:
        if w_ & 0x1860: w_ &= 0xDFFF
    return w_, new & w_


def status_duration(v, mdef):
    t = (v >> 2) - (mdef >> 1)
    return max(0 if t < 0 else t & 0xFF, 20)


def timer_groups(newbits):
    out = []
    if newbits & 0x6000: out.append(0x1B6)
    if (newbits >> 8) & 0x1C: out.append(0x1B5)
    if newbits & 0x0180: out.append(0x1B3)
    if newbits & 0x007C: out.append(0x1B2)
    return out


def w(s, off): return s[off] | s[off + 1] << 8


def snapshot(env, slot):
    o = env.obj(slot)
    return {off: o.b(off) for off in range(0x200)}


# ------------------------------------------------------------------ case construction
RESET = (0x190, 0x191, 0x1B0, 0x1B1, 0x19D, 0x1AE, 0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6, 0x1B7, 0x1B8, 0x1BA, 0x1BB, 0x1BC, 0x1BD, 0x1BE, 0x1BF,
         0x1F1, 0x1F2, 0x1F3, 0x1F4, 0x1F5, 0x1F6, 0x1EE, 0x1EF, 0x19E, 0x19F)


class Case: pass


def build(rom, state, rnd, sid, level, div, monster_caster=False):
    r = row(rom, sid)
    env = ce.Env(rom, state); c = env.c
    k = Case(); k.env, k.r, k.level, k.div = env, r, level, div
    hostile = bool(r['tf'] & 0x80) and sid != 0x21
    mids = [0x00, 0x05, 0x12, 0x30, 0x40, 0x50, 0x79]
    if monster_caster:
        env.call(0xC055EC, A=rnd.choice(mids), X=0x600, m=1, x=0)
        k.ci = 3
        if hostile: k.ti = rnd.choice([0, 1, 2])
        else:
            env.call(0xC055EC, A=rnd.choice(mids), X=0x800, m=1, x=0)
            k.ti = rnd.choice([3, 4])
    else:
        k.ci = rnd.choice([0, 1, 2])
        if hostile:
            env.call(0xC055EC, A=rnd.choice(mids), X=0x600, m=1, x=0); k.ti = 3
        else:
            k.ti = rnd.choice([j for j in (0, 1, 2) if j != k.ci])
    C, T = env.obj(k.ci), env.obj(k.ti)
    for j in range(5):
        o = env.obj(j)
        if o.b(0x1FB) & 0x80 or (j >= 3 and o.b(0x180) != 0) or j == k.ti:
            for off in RESET: o.sb(off, 0)
    k.hero_c = bool(C.b(0x1FB) & 0x80); k.hero_t = bool(T.b(0x1FB) & 0x80)
    C.sb(0x18B, rnd.randrange(1, 100)); C.sb(0x18C, rnd.randrange(1, 100)); C.sb(0x1E6, rnd.choice([0, 0, 2, 8]))
    C.sb(0x186, rnd.randrange(30, 100)); C.sb(0x177, rnd.randrange(8))
    if not k.hero_c: C.sb(0x1FD, rnd.randrange(1, 255)); C.sb(0x1FE, rnd.randrange(1, 255))
    for j in range(8): C.sb(0x1D8 + j, rnd.randrange(100))
    for j in range(4): C.sb(0x1C4 + j, 0x88 if rnd.random() < 0.5 else 0)
    T.sw(0x1A5, rnd.randrange(0, 1000)); T.sw(0x1A8, rnd.randrange(0, 1000)); T.sb(0x1A7, rnd.randrange(0, 100))
    T.sb(0x1A1, rnd.choice([0, 0, 0x01, 0x04, 0x10, 0x3F])); T.sb(0x1A3, rnd.choice([0, 0, 0x02, 0x08, 0x20]))
    T.sw(0x184, rnd.randrange(50, 1000)); T.sw(0x182, rnd.randrange(1, T.w(0x184) + 1))
    T.sb(0x187, rnd.randrange(10, 100)); T.sb(0x186, rnd.randrange(0, T.b(0x187) + 1))
    T.sw(0x1AA, rnd.choice([0, 0, 0, 0x0800, 0x2010, 0x7FFC]))
    T.sb(0x192, rnd.choice([0, 0x01, 0x20, 0x40, 0x60, 0x08]))
    if not k.hero_t: T.sb(0x1FB, rnd.choice([0x00, 0x00, 0x40]))
    if rnd.random() < 0.6:                       # existing buffs, saber, wall, status
        T.sb(0x1B0, rnd.randrange(256))
        for off in (0x1B7, 0x1BA, 0x1BB, 0x1BC): T.sb(off, rnd.randrange(1, 200))
        T.sb(0x19D, rnd.randrange(0, 40)); T.sb(0x1AE, rnd.randrange(256)); T.sb(0x1B8, rnd.randrange(0, 10))
        T.sb(0x1B1, rnd.choice([0, 0x40, 0x10, 0x50]))
        w_, _ = status_model(rnd.choice([0, 0x0010, 0x0080, 0x2000, 0x0100, 0x4000, 0x0020]), 0, 0)
        T.sw(0x190, w_); T.sw(0x1EE, w_ & 0xFFFC); T.sw(0x19E, w_)
        for off in (0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6): T.sb(off, rnd.randrange(1, 200))
    if sid == 0x21 and rnd.random() < 0.7:        # dead target
        T.sw(0x182, 0); T.sb(0x191, T.b(0x191) | 0x80)
    for i in range(0x3F1, 0x400): c.wram[i] = rnd.randrange(256)
    c.wram[0x3F0] = rnd.randrange(15)
    C.sb(0x170, sid); C.sb(0x171, level); C.sb(0x176, div)
    for off in (0x172, 0x173, 0x174): C.sb(off, 0xFF)
    return k


def cast(env, ci, ti):
    env.call(0xC8E6D4, X=0x200 * ci, Y=0x200 * ti, m=1, x=0, D=0x300)


# ------------------------------------------------------------------ per-spell models: {('T', offset, size): expected value, ...}
def expected(rom, k, C, T, rng):
    sid, r, level, div, hero_t, hc = k.r['id'], k.r, k.level, k.div, k.hero_t, k.hero_c
    cu = dict(INT=C[0x18B], WIS=C[0x18C], E1FD=C[0x1FD], E1FE=C[0x1FE], E6=C[0x1E6])
    tu = dict(MDEF=w(T, 0x1A8), MEV=T[0x1A7], RES=T[0x1A3], WEAK=T[0x1A1])
    E = {}
    Lp = level // div
    pend = 0 if hero_t else w(T, 0x1F1)             # a hero target loses its pending damage word when a spell hits it

    def V4(): return value(cu, tu, r, level, div, rng, fixed_m=4, hero_c=hc)
    def VE(): return value(cu, tu, r, level, div, rng, hero_c=hc)
    if sid in (0x04, 0x05, 0x1C):
        V, _, _ = V4(); Tm = (V >> 2) & 0xFF
        E[('T', 0x1B0, 1)] = {0x04: (T[0x1B0] & 0xC3) | 0x14, 0x05: (T[0x1B0] & 0xFC) | 0x01, 0x1C: (T[0x1B0] & 0x33) | 0x48}[sid]
        if sid == 0x04: E[('T', 0x1BA, 1)] = Tm; E[('T', 0x1BB, 1)] = Tm
        if sid == 0x05: E[('T', 0x1BC, 1)] = Tm
        if sid == 0x1C: E[('T', 0x1B7, 1)] = Tm; E[('T', 0x1BB, 1)] = Tm
    elif sid in (0x07, 0x10):
        V, d94, _ = VE(); Tm = (V >> 2) & 0xFF
        E[('T', 0x1F1, 2)] = (pend + max(1, V - d94)) & 0xFFFF
        if sid == 0x07: E[('T', 0x1B0, 1)] = (T[0x1B0] & 0xFC) | 0x02; E[('T', 0x1BC, 1)] = Tm
        else: E[('T', 0x1B0, 1)] = (T[0x1B0] & 0x3F) | 0x80; E[('T', 0x1B7, 1)] = Tm
    elif sid == 0x0B:
        V, _, _ = V4()
        E[('T', 0x1F3, 2)] = (w(T, 0x1F3) + V) & 0xFFFF
    elif sid in (0x02, 0x11, 0x14, 0x16, 0x18, 0x1E):
        V, d94, _ = VE()
        if sid == 0x11: E[('T', 0x1F1, 2)] = (pend + max(1, V - d94)) & 0xFFFF
        wd, new = status_model(w(T, 0x190), r['status'], w(T, 0x1AA))
        if sid != 0x18: E[('T', 0x190, 2)] = wd
        d = status_duration(V, w(T, 0x1A8))
        for t in timer_groups(new): E[('T', t, 1)] = d
        if sid == 0x18:
            E['cf'] = None
            if not hero_t and new and not (T[0x191] & 0x80):
                if wd & 0x20: E['cf'] = 0x83
                elif wd & 0x0800: E['cf'] = rom[0x08E5F3 + (rng.byte() & 7)]
                else: E['cf'] = T[0x1E7]
    elif sid in (0x03, 0x09, 0x0F, 0x15, 0x1B, 0x27):
        V4()
        E[('T', 0x19D, 1)] = ((Lp + 1) * 4) & 0xFF
        E['saber'] = (Lp, {0x03: 0x01, 0x09: 0x04, 0x0F: 0x08, 0x15: 0x02, 0x1B: 0x40, 0x27: 0x20}[sid], r['status'])
    elif sid in (0x0A, 0x21):
        if sid == 0x21 and not (T[0x1FB] & 0xC0): return E      # the handler returns at once for a non-hero, non-boss target
        V, _, _ = V4()
        if Lp == 8 or (Lp >= 4 and div == 1):
            for t in (0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6): E[('T', t, 1)] = 1
            E[('T', 0x190, 2)] = (w(T, 0x190) & 0x8400) & (0x7FFF if sid == 0x21 else 0xFFFF)
        else:
            a4 = (V >> 2) & 0xFF
            E[('T', 0x190, 2)] = w(T, 0x190) & 0xFDFF & (0x7FFF if sid == 0x21 else 0xFFFF)
            for t in (0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6):
                x = T[t] - a4
                E[('T', t, 1)] = 1 if x <= 0 else x
        if sid == 0x21:
            E[('T', 0x1F3, 2)] = V // (9 - Lp); E[('T', 0x1F1, 2)] = 0
            E['alive'] = True
    elif sid == 0x24:
        VE()
        dm = 1 if T[0x1FB] & 0x40 else ((w(T, 0x182) + w(T, 0x184)) >> 1) // (10 - Lp)
        E[('T', 0x1F1, 2)] = (pend + dm) & 0xFFFF
    elif sid == 0x29:
        V, _, _ = V4()
        E[('T', 0x1B1, 1)] = T[0x1B1] | 0x10
        E[('T', 0x1BD, 2)] = min(V, w(T, 0x184))
        E[('T', 0x1BF, 1)] = ((w(T, 0x1A5) >> 1) // div) & 0xFF
    elif sid == 0x22:
        E[('T', 0x1B1, 1)] = T[0x1B1] | 0x40
        E[('T', 0x1B8, 1)] = Lp + 2
    elif sid == 0x1D:
        E[('T', 0x1AE, 1)] = (T[0x1AE] & 0x0F) | (((Lp + 1) << 4) & 0xFF)
    if sid in (0x03, 0x04, 0x05, 0x07, 0x09, 0x0B, 0x0F, 0x10, 0x15, 0x1B, 0x1C, 0x1D, 0x22, 0x24, 0x27, 0x29) and ('T', 0x190, 2) not in E:
        E[('T', 0x190, 2)] = w(T, 0x190)                # these handlers never touch the status word (Acid Storm and Fire Bouquet included)
    return E


def check_case(rom, state, rnd, sid, level, div, monster_caster=False):
    k = build(rom, state, rnd, sid, level, div, monster_caster)
    env, r = k.env, k.r
    C0, T0 = snapshot(env, k.ci), snapshot(env, k.ti)
    rng = R.Rng.from_wram(env.c.wram)
    E = expected(rom, k, C0, T0, rng)
    cast(env, k.ci, k.ti)
    C1, T1 = snapshot(env, k.ci), snapshot(env, k.ti)
    bad = []
    for key, v in E.items():
        if not isinstance(key, tuple): continue
        _, off, sz = key
        got = T1[off] if sz == 1 else w(T1, off)
        if got != v: bad.append((hex(off), v, got))
    if 'saber' in E:
        Lp, bit, st = E['saber']
        if (T1[0x1AE] & 15) != Lp or not (T1[0x195] & bit) or (w(T1, 0x199) & st) != st: bad.append(('saber', E['saber'], (T1[0x1AE], T1[0x195], w(T1, 0x199))))
    if E.get('alive') and (T1[0x191] & 0x80 or w(T1, 0x182) == 0): bad.append(('revive', 0, (T1[0x191], w(T1, 0x182))))
    if 'cf' in E and E['cf'] is not None and T1[0x180] != E['cf']: bad.append(('change form id', E['cf'], T1[0x180]))
    if C1[0x186] != max(0, C0[0x186] - r['mp']): bad.append(('mp', max(0, C0[0x186] - r['mp']), C1[0x186]))
    if k.hero_t and w(T1, 0x1F1) != E.get(('T', 0x1F1, 2), 0):
        bad.append(('hero target pending damage', E.get(('T', 0x1F1, 2), 0), w(T1, 0x1F1)))
    changed = set(o for o in range(0x200) if T0[o] != T1[o]), set(o for o in range(0x200) if C0[o] != C1[o])
    return bad, changed


def absorb_case(rom, state, rnd, sid, level, div, monster_caster=False):
    k = build(rom, state, rnd, sid, level, div, monster_caster)
    env, r = k.env, k.r
    C = env.obj(k.ci)
    C.sw(0x182, rnd.randrange(1, 400)); C.sw(0x184, 999)
    C0, T0 = snapshot(env, k.ci), snapshot(env, k.ti)
    cu = dict(INT=C0[0x18B], WIS=C0[0x18C], E1FD=C0[0x1FD], E1FE=C0[0x1FE], E6=C0[0x1E6])
    tu = dict(MDEF=w(T0, 0x1A8), MEV=T0[0x1A7], RES=T0[0x1A3], WEAK=T0[0x1A1])
    rng = R.Rng.from_wram(env.c.wram)
    V, d94, m = value(cu, tu, r, level, div, rng, hero_c=k.hero_c)
    rev = bool(T0[0x192] & (0x20 if sid == 0x08 else 0x40))
    dm, he = (k.ci, k.ti) if rev else (k.ti, k.ci)
    if sid == 0x08:
        if rev:
            d94 = M.target_mdef(dict(MDEF=w(C0, 0x1A8), MEV=C0[0x1A7], RES=0, WEAK=0), rng)
        a = V - d94
        a = 1 if a <= 0 else a
        a = min(a, w(C0 if rev else T0, 0x182))
    else:
        a = max(V - d94, 0) // 10
        a = max(a, 1)
        a = min(a, max(0, C0[0x186] - r['mp']) if rev else T0[0x186])
    h0 = snapshot(env, he)
    cast(env, k.ci, k.ti)
    D1, H1 = snapshot(env, dm), snapshot(env, he)
    if sid == 0x08: got = (w(D1, 0x1F1), w(H1, 0x1F3) - w(h0, 0x1F3))
    else: got = (D1[0x1F5], H1[0x1F6] - h0[0x1F6])
    return [] if got == (a, a) else [(hex(sid), rev, (a, a), got)]


def dispel_case(rom, state, rnd, level, div, monster_caster=False):
    k = build(rom, state, rnd, 0x26, level, div, monster_caster)
    env, r = k.env, k.r
    T = env.obj(k.ti)
    T.sb(0x1B1, T.b(0x1B1) | rnd.choice([0, 0x40])); T.sb(0x1B8, rnd.randrange(0, 10)); T.sb(0x19D, rnd.randrange(0, 40))
    C0, T0 = snapshot(env, k.ci), snapshot(env, k.ti)
    cu = dict(INT=C0[0x18B], WIS=C0[0x18C], E1FD=C0[0x1FD], E1FE=C0[0x1FE], E6=C0[0x1E6])
    tu = dict(MDEF=w(T0, 0x1A8), MEV=T0[0x1A7], RES=T0[0x1A3], WEAK=T0[0x1A1])
    V, d94, m = value(cu, tu, r, level, div, R.Rng.from_wram(env.c.wram), hero_c=k.hero_c)
    cast(env, k.ci, k.ti)
    T1 = snapshot(env, k.ti)
    E = {}
    if level == 8 or (level >= 4 and div == 1):
        for o in (0x1B7, 0x1BA, 0x1BB, 0x1BC): E[o] = 1
        E[0x19D] = 0; E[0x1B8] = 0
    else:
        a4 = max(0, (V >> 2) - (w(T0, 0x1A8) >> 1)) & 0xFF
        for o in (0x1B7, 0x1BA, 0x1BB, 0x1BC):
            x = T0[o] - a4; E[o] = 1 if x <= 0 else x
        x = T0[0x19D] - (level + 1) * 4; E[0x19D] = 0 if x < 0 else x
        x = T0[0x1B8] - (level + 2); E[0x1B8] = 0 if x < 0 else x
    bad = [(hex(o), v, T1[o]) for o, v in E.items() if T1[o] != v]
    wall = (T0[0x1B1] & 0x40) and E[0x1B8] != 0
    if bool(T1[0x1B1] & 0x40) != bool(wall): bad.append(('wall bit', bool(wall), T1[0x1B1]))
    if E[0x19D] != 0 and T1[0x19B] != 0: bad.append(('E19B', 0, T1[0x19B]))
    return bad


def lunar_case(rom, state, rnd, level, div, monster_caster=False):
    k = build(rom, state, rnd, 0x1A, level, div, monster_caster)
    env, r = k.env, k.r
    for sl in (4, 5):
        if env.obj(sl).b(0x180) == 0: env.obj(sl).sb(0x191, 0); env.obj(sl).sw(0x184, 0)
    pre = [snapshot(env, j) for j in range(6)]
    C0, T0 = pre[k.ci], pre[k.ti]
    cu = dict(INT=C0[0x18B], WIS=C0[0x18C], E1FD=C0[0x1FD], E1FE=C0[0x1FE], E6=C0[0x1E6])
    tu = dict(MDEF=w(T0, 0x1A8), MEV=T0[0x1A7], RES=T0[0x1A3], WEAK=T0[0x1A1])
    rng = R.Rng.from_wram(env.c.wram)
    V, d94, m = value(cu, tu, r, level, div, rng, hero_c=k.hero_c)
    idx = rng.below(8)
    cast(env, k.ci, k.ti)
    post = [snapshot(env, j) for j in range(6)]
    bad = []
    for j in range(6):
        a, b = pre[j], post[j]
        if idx == 0:
            e = w(a, 0x1F3) if (a[0x191] & 0x80) else w(a, 0x184)
            if w(b, 0x1F3) != e: bad.append((idx, j, 'E1F3', e, w(b, 0x1F3)))
        elif idx in (1, 2):
            if j == k.ti and (b[0x1B0] != (0x55 if idx == 1 else 0xAA) or any(b[o] != ((V >> 2) & 0xFF) for o in (0x1B7, 0x1BA, 0x1BB, 0x1BC))): bad.append((idx, j, 'buff'))
        else:
            off, bit, slots = {3: (0x190, 0x80, range(6)), 4: (0x191, 0x10, range(6)), 5: (0x191, 0x02, range(3)), 6: (0x191, 0x08, range(3, 6)), 7: (0x190, 0x10, range(6))}[idx]
            e = a[off] | bit if j in slots else a[off]
            if b[off] != e: bad.append((idx, j, hex(off), e, b[off]))
    return idx, bad


def analyzer_changes(rom, state, rnd, level, div):
    k = build(rom, state, rnd, 0x17, level, div, False)
    env = k.env
    before = [snapshot(env, j) for j in range(6)]
    cast(env, k.ci, k.ti)
    after = [snapshot(env, j) for j in range(6)]
    ch = set()
    for j in range(6):
        for o in range(0x200):
            if before[j][o] != after[j][o]: ch.add(((j == k.ci and 'caster') or (j == k.ti and 'target') or 'other', o))
    return ch


# ------------------------------------------------------------------ special set-ups
def wall_wrapper(rom, state):
    """$D0:4C82 (reached through the stub $C0:3866): a monster casts at a hero that carries Wall."""
    def run(sid, n, dist, alive=True, e1fb=0):
        env = ce.Env(rom, state); c = env.c
        env.call(0xC055EC, A=0x12, X=0x600, m=1, x=0)
        Cc = env.obj(3); T = env.obj(2)
        Cc.sb(0, 1); Cc.sw(2, 360 + dist); Cc.sw(4, 186); Cc.sb(0x1FB, e1fb)
        if not alive: Cc.sb(0x191, 0x80)
        for off in RESET: T.sb(off, 0)
        T.sb(0x1B1, 0x40); T.sb(0x1B8, n); T.sw(0x182, 500); T.sw(0x184, 500)
        Cc.sb(0x170, sid); Cc.sb(0x171, 3); Cc.sb(0x176, 1)
        for off in (0x172, 0x173, 0x174): Cc.sb(off, 0xFF)
        Cc.sb(0x178, 3); Cc.sb(0x179, 0); Cc.sb(0x17A, 0)
        env.call(0xD04C82, X=0x600, Y=0x400, m=1, x=0, D=0x300)
        return dict(spell=sid, wall_count_before=n, candidate_distance=dist, candidate_alive=alive, candidate_E1FB=e1fb, A=c.A & 0xFF, X=c.X,
                    wall_count_after=T.b(0x1B8), wall_bit_after=bool(T.b(0x1B1) & 0x40), pending_damage=T.w(0x1F1), pending_heal=T.w(0x1F3))
    return [run(0x00, 3, 100), run(0x00, 3, 300), run(0x00, 3, 100, alive=False), run(0x00, 3, 100, e1fb=0x10), run(0x00, 1, 100),
            run(0x0B, 3, 100), run(0x20, 3, 100), run(0x26, 3, 100)]


def barrier_rows(rom, state):
    rows = []
    for guard, pool, spell in ((0, 100, False), (10, 100, False), (10, 30, False), (50, 1000, False), (10, 100, True)):
        env = ce.Env(rom, state); c = env.c
        env.call(0xC055EC, A=0x12, X=0x600, m=1, x=0)
        A = env.obj(3); D = env.obj(2)
        for off in (0x190, 0x191, 0x1B0, 0x1B1, 0x1F1, 0x1F2, 0x1F3, 0x175): D.sb(off, 0)
        D.sw(0x182, 500); D.sw(0x184, 500); D.sw(0x1A5, 0); D.sb(0x1B1, 0x10); D.sw(0x1BD, pool); D.sb(0x1BF, guard); D.sb(0x1A4, 0)
        A.sb(0x198, 100); A.sb(0x197, 99)
        for i in range(0x3F1, 0x400): c.wram[i] = (7 + i * 13) & 255
        VP.rom_hit(env, 3, 2)
        D.sb(0x1F0, 0xFF if spell else 3); D.sb(0x1E5, 0xFF)
        pending = D.w(0x1F1)
        env.call(0xC04004, X=0x400, m=1, x=0, D=0x300, long=False)
        rows.append(dict(guard=guard, pool=pool, hit_by='spell' if spell else 'weapon', pending_damage_after_guard=pending, hp_after=D.w(0x182),
                         pool_after=D.w(0x1BD), barrier_bit_after=bool(D.b(0x1B1) & 0x10)))
    return rows


def weapon_change(rom, state):
    env = ce.Env(rom, state); c = env.c
    for j in range(3):
        for off in RESET: env.obj(j).sb(off, 0)
    B = env.obj(0); B.sb(0x1E4, 1)
    steps = [dict(after='start', boy_weapon_row=B.b(0x1E8))]

    def go(e, sid, ci, ti, lv=5):
        C = e.obj(ci); C.sb(0x170, sid); C.sb(0x171, lv); C.sb(0x176, 1)
        for off in (0x172, 0x173, 0x174): C.sb(off, 0xFF)
        cast(e, ci, ti)
        e.c.wram[0x381] = ti; e.c.wram[0x382] = ci
        e.call(0xC03F94, X=0x200 * ti, Y=0x200 * ci, m=1, x=0, D=0x300)
    for sid, ci, ti in ((0x20, 1, 0), (0x23, 2, 0), (0x03, 1, 2)):
        go(env, sid, ci, ti)
        steps.append(dict(after='cast %02X' % sid, CC77=c.wram[0xCC77], CC78=c.wram[0xCC78], CC79=c.wram[0xCC79], boy_weapon_row=B.b(0x1E8)))
    env2 = ce.Env(rom, state); c2 = env2.c
    for j in range(3):
        for off in RESET: env2.obj(j).sb(off, 0)
        env2.obj(j).sw(0x182, 500)
    B2 = env2.obj(0); B2.sb(0x1E4, 1)
    prev = B2.b(0x1E8)
    go(env2, 0x20, 1, 0); go(env2, 0x23, 2, 0)
    timers = (c2.wram[0xCC78], c2.wram[0xCC79])
    c2.wram[0xCC78] = c2.wram[0xCC79] = 3
    B2.sb(0x1B9, 5)
    life = None
    for n in range(1, 200):
        env2.call(0xC03A79, A=0, X=0, m=0, x=0, long=True)
        if B2.b(0x1E8) == prev: life = n; break
    steps.append(dict(after='both timers forced to 3, slot 0 combat ticks', ticks_until_weapon_row_restored=life, restored_row_equals_previous=B2.b(0x1E8) == prev,
                      timers_before_forcing=list(timers)))
    return steps


def level8_roll(rom, state):
    """$D0:4EAC: hero casters (E1FB bit 7) and bosses (bit 6): a level 8 cast is stored as 8 only if (R>>1)+1 < progress, else 7."""
    bad = n = 0
    table = {}
    for prog in (0, 1, 2, 10, 50, 98, 99):
        k8 = 0
        for seed in range(256):
            env = ce.Env(rom, state); c = env.c
            for i in range(0x3F1, 0x400): c.wram[i] = (seed * 37 + i * 11) & 255
            c.wram[0x3F0] = seed % 15
            C = env.obj(1); C.sb(0x1FB, 0x80)
            c.wram[0x39D] = 8; c.wram[0x39E] = prog
            rg = R.Rng.from_wram(c.wram)
            env.call(0xD04EAC, X=0x200, m=1, x=0, D=0x300, long=False)
            exp = 8 if ((rg.byte() >> 1) + 1) < prog else 7
            n += 1; bad += C.b(0x171) != exp; k8 += C.b(0x171) == 8
        table[prog] = k8
    return bad, n, table


def lifetimes(rom, state):
    """timer units -> combat ticks, measured with the real tick $C0:3A79 on a hero with a buff bit set"""
    def life(setup, check, maxn=1500, slot=2):
        env = ce.Env(rom, state); h = env.obj(slot)
        for j in (0, 1, 2):
            for off in RESET: env.obj(j).sb(off, 0)
            if j != slot: env.obj(j).sw(0x182, 0)
        h.sw(0x182, 500); h.sw(0x184, 500); h.sw(0x1AA, 0)
        setup(h)
        for n in range(1, maxn):
            env.call(0xC03A79, A=slot, X=0x200 * slot, m=0, x=0, long=True)
            if check(h): return n
        return None
    out = {}

    def mk(t, ph):
        def f(h): h.sb(0x1B0, 0x04); h.sb(0x1BB, t); h.sb(0x1B9, ph)
        return f
    for t in (1, 2, 5, 20, 125, 249):
        out['buff_timer_%d_over_8_tick_phases' % t] = sorted(set(life(mk(t, ph), lambda h: not (h.b(0x1B0) & 4)) for ph in range(8)))
    for name, (off, bit) in {'0x0080': (0x190, 0x80), '0x1000': (0x191, 0x10), '0x0200': (0x191, 0x02), '0x0800': (0x191, 0x08), '0x0010': (0x190, 0x10)}.items():
        def f(h, off=off, bit=bit): h.sb(off, bit); h.sw(0x19E, h.w(0x190)); h.sw(0x1EE, h.w(0x190) & 0xFFFC); h.sb(0x1B9, 5)
        out['status_%s_set_directly_timer_0' % name] = life(f, lambda h, off=off, bit=bit: not (h.b(off) & bit))
    return out


def drain_rows(rom, state):
    """Moon Saber sets E195 bit 0x40 (the drain flag of $C0:519C): a weapon hit by a hero on a monster, with and without it"""
    rows = []
    for flag, mtype in ((0x00, 0x00), (0x40, 0x00), (0x40, 0x20), (0x20, 0x00), (0x04, 0x00)):
        env = ce.Env(rom, state); c = env.c
        env.call(0xC055EC, A=0x12, X=0x600, m=1, x=0)
        A, D = env.obj(0), env.obj(3)
        for off in RESET: A.sb(off, 0)
        D.sb(0x192, mtype); A.sb(0x195, flag)
        D.sb(0x1A4, 0); D.sw(0x1A5, 0)
        for i in range(0x3F1, 0x400): c.wram[i] = (3 * 7 + i * 13) & 255
        hit, dmg = VP.rom_hit(env, 0, 3)
        rows.append(dict(E195=flag, defender_type_byte=mtype, hit=hit, pending_damage_defender=D.w(0x1F1), pending_damage_attacker=A.w(0x1F1),
                         pending_heal_attacker=A.w(0x1F3), pending_heal_defender=D.w(0x1F3)))
    return rows


# ------------------------------------------------------------------ numeric tables
def tables(rom):
    stats = [10, 20, 30, 40, 50, 60, 70, 80, 90, 99]
    vt = {}
    for power in (61, 250):
        for m in (2, 4):
            for e6 in (0, 8):
                vt['power%d_m%d_E1E6_%d' % (power, m, e6)] = {str(s): [list(value_range(s, power, L, m, e6)[:3]) for L in range(9)] for s in stats}
    acc = {str(s): cap(((s >> 2) + 75) & 0xFF, 99) for s in stats}
    spells = {}
    for sid in range(0x2A):
        r = row(rom, sid)
        spells['%02X' % sid] = dict(mp=r['mp'], power=r['power'], element_mask=r['elem'], status_word=r['status'], target_flags=r['tf'], stat='INT' if sid % 6 < 3 else 'WIS')
    return dict(value_ranges=dict(layout='[glancing, nonglancing_min, nonglancing_max] of V for caster stat s and level 0..8, number of targets 1; V = $89 after $C8:E8C0',
                                  accuracy_percent_by_stat=acc, tables=vt), spell_rows=spells)


def effects():
    """what each handler writes into the target object (offsets from the object base), as modelled and validated above"""
    def f(off, op): return dict(offset=off, op=op)
    st = lambda timer: [f('0x190', 'status word: new bits through the immunity word E1AA and the exclusivity cascade'), f(timer, 'timer = max(20, (V>>2) - (E1A8>>1)) low byte, only for newly set bits')]
    return {
        '02': dict(handler='C8:EA97', kind='status only (no damage)', status_word='0x0004', target=st('0x1B2')),
        '03': dict(handler='C8:EAA3', kind='saber', element_bit_into_E195='0x01', status_word_into_E199='0x0040'),
        '04': dict(handler='C8:EB04', kind='buff', value_mode='fixed m=4', target=[f('0x1B0', '(old & 0xC3) | 0x14: EVA+25% and ACC+25%'), f('0x1BB', 'timer = V>>2'), f('0x1BA', 'timer = V>>2')]),
        '05': dict(handler='C8:EB20', kind='buff', value_mode='fixed m=4', target=[f('0x1B0', '(old & 0xFC) | 0x01: DEF+25%'), f('0x1BC', 'timer = V>>2')]),
        '07': dict(handler='C8:EB39', kind='damage + debuff', value_mode='element m', target=[f('0x1F1', 'pending damage += max(1, V - D)'), f('0x1B0', '(old & 0xFC) | 0x02: DEF-25%'), f('0x1BC', 'timer = V>>2')], note='the status word 0x2000 of the spell row is not applied by the handler'),
        '08': dict(handler='C8:EB54', kind='HP drain', value_mode='element m'),
        '09': dict(handler='C8:EAA8', kind='saber', element_bit_into_E195='0x04', status_word_into_E199='0x0020'),
        '0A': dict(handler='C8:EB9F', kind='status cure', value_mode='fixed m=4'),
        '0B': dict(handler='C8:EBB3', kind='heal', value_mode='fixed m=4', target=[f('0x1F3', 'pending heal += V')]),
        '0F': dict(handler='C8:EAAD', kind='saber', element_bit_into_E195='0x08', status_word_into_E199='0x4000'),
        '10': dict(handler='C8:EBCA', kind='damage + debuff', value_mode='element m', target=[f('0x1F1', 'pending damage += max(1, V - D)'), f('0x1B0', '(old & 0x3F) | 0x80: ATK-25%'), f('0x1B7', 'timer = V>>2')]),
        '11': dict(handler='C8:EBE5', kind='damage + status', value_mode='element m', status_word='0x4000', target=[f('0x1F1', 'pending damage += max(1, V - D)')] + st('0x1B6')),
        '14': dict(handler='C8:EBF4', kind='status only (no damage)', status_word='0x0080', target=st('0x1B3')),
        '15': dict(handler='C8:EAB2', kind='saber', element_bit_into_E195='0x02', status_word_into_E199='0x0000'),
        '16': dict(handler='C8:EBF4', kind='status only (no damage)', status_word='0x0100', target=st('0x1B3')),
        '17': dict(handler='C8:EC00', kind='analyzer: builds the message, writes no gameplay field'),
        '18': dict(handler='C8:EBF4', kind='status only (no damage)', status_word='0x0800', target=st('0x1B5'), note='a monster that keeps the bit becomes the object whose id is table[R&7], table at C8:E5F3 = 00 02 04 06 08 0C 16 17'),
        '19': dict(handler='C8:EC3B', kind='MP drain', value_mode='element m'),
        '1A': dict(handler='C8:EEF5', kind='random effect 0..7', value_mode='element m (value only used by effect 1 and 2)'),
        '1B': dict(handler='C8:EABC', kind='saber', element_bit_into_E195='0x40', status_word_into_E199='0x0000', note='E195 bit 0x40 is the weapon drain flag'),
        '1C': dict(handler='C8:ECB5', kind='buff', value_mode='fixed m=4', target=[f('0x1B0', '(old & 0x33) | 0x48: ATK+25% and EVA-25%'), f('0x1B7', 'timer = V>>2'), f('0x1BB', 'timer = V>>2')]),
        '1D': dict(handler='C8:ECD1', kind='forced critical hits', target=[f('0x1AE', 'high nibble = (L+1)')]),
        '1E': dict(handler='C8:EBF4', kind='status only (no damage)', status_word='0x0010', target=st('0x1B2')),
        '20': dict(handler='C8:ECEA', kind='first half of a two-spell weapon change', value_mode='fixed m=4', writes='$CC78 = V>>2'),
        '21': dict(handler='C8:ED04', kind='revive + cure + heal', value_mode='fixed m=4'),
        '22': dict(handler='C8:ED53', kind='spell block', target=[f('0x1B1', '|= 0x40'), f('0x1B8', '= L+2')]),
        '23': dict(handler='C8:ED68', kind='second half of a two-spell weapon change', value_mode='fixed m=4', writes='$CC79 = V>>2'),
        '24': dict(handler='C8:ED82', kind='fraction of current HP', target=[f('0x1F1', 'pending damage += ((HP+maxHP)>>1)/(10-L), 1 for a boss')]),
        '26': dict(handler='C8:EDCB', kind='buff / saber / wall scrub', value_mode='element m'),
        '27': dict(handler='C8:EAB7', kind='saber', element_bit_into_E195='0x20', status_word_into_E199='0x0000'),
        '29': dict(handler='C8:EEB7', kind='physical damage absorber', value_mode='fixed m=4', target=[f('0x1B1', '|= 0x10'), f('0x1BD', 'pool = min(V, maxHP) (word)'), f('0x1BF', 'guard = ((E1A5>>1)/targets) low byte')]),
    }


def per_level():
    """level-dependent constants of the handlers (Lp = level // number_of_targets, see the document)"""
    L = range(9)
    return dict(
        saber_hits=[(l + 1) * 4 for l in L], saber_damage_bonus_divisor=[None] + [10 - l for l in range(1, 9)],
        wall_hits=[l + 2 for l in L], moon_energy_forced_crits=[l + 1 for l in L],
        evil_gate_divisor=[10 - l for l in L], revivifier_divisor=[9 - l for l in L],
        dispel_removes_saber_hits=[(l + 1) * 4 for l in L], dispel_removes_wall_hits=[l + 2 for l in L],
        remedy_full_cure_single_target=[l >= 4 for l in L], remedy_full_cure_any_targets=[l == 8 for l in L])


if __name__ == '__main__':
    rom = romio.load(sys.argv[1]); state = sys.argv[2]
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    outp = sys.argv[4] if len(sys.argv) > 4 else None
    rnd = random.Random(11)
    ids = [0x02, 0x03, 0x04, 0x05, 0x07, 0x09, 0x0A, 0x0B, 0x0F, 0x10, 0x11, 0x14, 0x15, 0x16, 0x18, 0x1B, 0x1C, 0x1D, 0x1E, 0x21, 0x22, 0x24, 0x27, 0x29]
    written = {}; summary = {}
    for sid in ids:
        bad = n = 0; tw = set(); cw = set()
        for _ in range(N):
            level = rnd.randrange(9); div = rnd.choice([1, 1, 2, 3]); mc = rnd.random() < 0.3 and sid != 0x21
            res, (t_ch, c_ch) = check_case(rom, state, rnd, sid, level, div, mc)
            n += 1; tw |= t_ch; cw |= c_ch
            if res:
                bad += 1
                if bad <= 3: print('  MISMATCH %02X L%d div%d monster_caster=%s' % (sid, level, div, mc), res)
        written[sid] = (sorted(tw), sorted(cw)); summary[sid] = (n, bad)
        print('spell %02X cases %d mismatches %d' % (sid, n, bad))
    for sid in (0x08, 0x19):
        bad = n = 0
        for _ in range(N):
            level = rnd.randrange(9); div = rnd.choice([1, 1, 2, 3]); mc = rnd.random() < 0.3
            res = absorb_case(rom, state, rnd, sid, level, div, mc); n += 1
            if res:
                bad += 1
                if bad <= 3: print('  MISMATCH %02X L%d div%d' % (sid, level, div), res)
        summary[sid] = (n, bad); print('spell %02X cases %d mismatches %d' % (sid, n, bad))
    bad = 0
    for _ in range(N):
        level = rnd.randrange(9); div = rnd.choice([1, 1, 2, 3]); res = dispel_case(rom, state, rnd, level, div, rnd.random() < 0.3)
        if res:
            bad += 1
            if bad <= 3: print('  MISMATCH 26 L%d div%d' % (level, div), res)
    summary[0x26] = (N, bad); print('spell 26 cases %d mismatches %d' % (N, bad))
    cnt = {}; bad = 0
    for _ in range(N):
        level = rnd.randrange(9); div = rnd.choice([1, 1, 2, 3]); idx, res = lunar_case(rom, state, rnd, level, div, rnd.random() < 0.3)
        cnt[idx] = cnt.get(idx, 0) + 1
        if res:
            bad += 1
            if bad <= 3: print('  MISMATCH 1A', res)
    summary[0x1A] = (N, bad); print('spell 1A cases %d mismatches %d effect counts %s' % (N, bad, dict(sorted(cnt.items()))))
    chs = set()
    for _ in range(max(N // 3, 1)): chs |= analyzer_changes(rom, state, rnd, rnd.randrange(9), 1)
    print('spell 17 offsets written:', sorted((a, hex(o)) for a, o in chs))
    ww = wall_wrapper(rom, state); br = barrier_rows(rom, state); mm = weapon_change(rom, state); dr = drain_rows(rom, state)
    l8 = level8_roll(rom, state); lt = lifetimes(rom, state)
    print('wall wrapper:'); [print('  ', x) for x in ww]
    print('barrier through $C0:4004:'); [print('  ', x) for x in br]
    print('weapon change, spells 20 and 23:'); [print('  ', x) for x in mm]
    print('drain flag (Moon Saber) on a weapon hit:'); [print('  ', x) for x in dr]
    print('level 8 roll: mismatches %d of %d; level 8 stored out of 256 rolls by progress %s' % (l8[0], l8[1], l8[2]))
    print('lifetimes (combat ticks):', lt)
    if outp:
        d = dict(source='numbers measured by running the real spell handlers; layout and meaning: docs/spells-non-damage.md',
                 tick_hz=round(TICK_HZ, 4), frame_hz=60.0988, timer_unit_ticks=4,
                 per_level=per_level(), validation={('%02X' % k_): dict(cases=v[0], mismatches=v[1]) for k_, v in sorted(summary.items())},
                 effects=effects(),
                 spell_17_fields_written=sorted([a + ' ' + hex(o) for a, o in chs]),
                 wall_wrapper=ww, barrier=br, weapon_change_20_23=mm, drain_flag=dr,
                 level8_roll=dict(mismatches=l8[0], cases=l8[1], level8_out_of_256_by_progress={str(a): b for a, b in l8[2].items()}),
                 lifetimes_ticks=lt, lunar_magic_effect_counts=dict(sorted(cnt.items())))
        d.update(tables(rom))
        json.dump(d, open(outp, 'w'), indent=1, sort_keys=True)
        print('wrote', outp)

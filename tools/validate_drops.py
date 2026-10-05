"""Validate the monster drop model against the REAL ROM routines.
usage: validate_drops.py ROM STATE
 1. $C0:4203 (death): chest yes/no and chest class, 40 random RNG states per monster id.
 2. $C8:E12C (chest contents): gold amount / item byte / orb gate, 10 random RNG states per monster id and random orb counters.
Model: docs/rom-combat.md section 13."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce, rng
rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
TBL = list(rom[0x430D:0x4315])
rnd = random.Random(11)


def row(mid): return list(rom[0x103A50 + 5 * mid:0x103A50 + 5 * mid + 5])


def fresh(seed_idx=None):
    env = ce.Env(rom, state); w = env.c.wram
    for j in range(15): w[0x3F1 + j] = rnd.randrange(256)
    w[0x3F0] = rnd.randrange(15)
    return env, w


bad = tot = 0
for mid in range(0x54):
    r = row(mid)
    if r[0] == 0xFF: continue
    lvl = rom[0x101C00 + mid * 29]
    for _ in range(40):
        env, w = fresh()
        env.call(0xC055EC, A=mid, X=0x600, m=1, x=0)
        m = env.obj(3); w[0x385] = 0; w[0x386] = 6; m.sb(0x1F0, 0); m.sb(0x1CF, 0)
        R = rng.Rng.from_wram(w)
        a8 = (R.byte() & 0x3F) + 1
        drop = bool(r[0] & 0x40) or (r[0] & 0x3F) >= a8
        cls = None
        if drop:
            a4 = R.below(3)
            if lvl >= 10:
                a4 = 2
                if lvl >= 15: a4 = 3
                if lvl >= 25: a4 = 4
                if lvl >= 30: a4 = 5
                if lvl >= 36:
                    a4 = 6
                    if R.byte() < 0x20: a4 = 7
            cls = TBL[a4]
        env.call(0xC04203, X=0x600, m=1, x=0, D=0x300, long=False)
        got = m.b(0x1B1) == 0x80 and m.b(0x184) == 0 and m.b(0x181) == 0
        tot += 1
        if got != drop or (got and m.b(0x1C8) != cls):
            bad += 1
            if bad < 5: print('DEATH MISMATCH', mid, drop, cls, got, m.b(0x1C8))
print('death routine: cases', tot, 'mismatches', bad)

CFC0 = [9, 8, 9, 9, 9, 9, 9, 9]
def rtl(cp):
    cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True
bad = tot = 0
for mid in range(0x54):
    r = row(mid)
    if r[0] == 0xFF: continue
    for _ in range(10):
        env, w = fresh(); c = env.c
        cfb8 = [rnd.choice([0, 3, 7, 8]) for _ in range(8)]
        for t in range(8): w[0xCFB8 + t] = cfb8[t]; w[0xCFC0 + t] = CFC0[t]
        log = []
        for name, addr in (('add', 0xC06420), ('msg', 0xC058DB), ('msg2', 0xC058F1), ('gold', 0xC039CF), ('goldmsg', 0xC058C8)):
            c.hooks[addr] = (lambda n: (lambda cp: (log.append((n, cp.A & 0xFF)), rtl(cp))[1]))(name)
        w[0x385] = 0; w[0x386] = 6; w[0xCF0F] = 0
        rr = rng.Rng.from_wram(w).byte() & 0x3F
        a4 = (r[2] >> 3) & 7; carry = rr >= a4; mode = r[2] >> 6
        kind, v = {0: ('gold', r[3] if carry else r[4]), 1: ('item', r[3] if carry else r[4]), 2: ('gold', r[3]) if carry else ('item', r[4]), 3: ('item', r[3]) if carry else ('gold', r[4])}[mode]
        if kind == 'item' and v >= 0x80:
            t = v - 0x80
            exp = ('orb', t) if cfb8[t] + 1 < CFC0[t] else ('item', 0x40)
        else: exp = (kind, v)
        env.call(0xC8E12C, X=mid * 5, m=1, x=0, D=0x300, long=False)
        got = None
        for n, a in log:
            if n == 'add': got = ('item', a)
            if n == 'gold': got = ('gold', a)
        if got is None and env.obj(3).b(0x1C8) == 8: got = ('orb', env.obj(3).b(0x1C9))
        tot += 1
        if got != exp:
            bad += 1
            if bad < 5: print('CONTENT MISMATCH', mid, [hex(x) for x in r], rr, exp, got)
print('chest contents routine: cases', tot, 'mismatches', bad)

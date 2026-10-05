"""Validate the status application rules against the REAL routine $C8:E301.
usage: validate_status_rules.py ROM STATE [N=2000]
Model: new bits are masked by the immunity word; the result is merged and then filtered by the exclusivity cascade of $C8:E487 / E4D7 / E50F;
timers are (re)loaded only for bits that were NOT already set. Duration d = max(20, ($96 >> 2) - (magic defense >> 1)) low byte, see docs/rom-combat.md section 12."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce


def model(cur, add, imm):
    new = add & ~imm & 0xFFFF
    w = (cur | new) & ~imm & 0xFFFF
    if w & 0x8000:
        w &= 0x8000; new &= 0x8000      # dead overrides everything; a new death flag is the only "new" bit that survives
    if w & 0x0040: w &= 0x9AC0
    elif w & 0x0020: w &= 0x9AE0
    elif w & 0x0010: w &= 0xFBF0
    elif w & 0x0008: w &= 0xFBF0
    elif w & 0x0004: w &= 0xFFFC
    if w & 0x1000: w &= 0x92FF
    elif w & 0x0800:
        w &= 0xF7FF if w & 0x0260 else 0x9A13
    elif w & 0x0400:
        if w & 0x617B: w &= 0xFBFF
    if w & 0x4000: w &= 0xDAFF
    elif w & 0x2000:
        if w & 0x1860: w &= 0xDFFF
    return w, new & w


def duration(v96, mdef):
    t = (v96 >> 2) - (mdef >> 1)
    d = 0 if t < 0 else t & 0xFF
    return max(d, 20)


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    rnd = random.Random(7); bad = 0; badt = 0
    BITS = [1 << i for i in range(2, 16)]
    for _ in range(n):
        env = ce.Env(rom, state); h = env.obj(0)
        cur = 0
        for b in BITS:
            if rnd.random() < 0.15: cur |= b
        cur &= ~0x8000 if rnd.random() < 0.9 else 0xFFFF
        add = 0
        for b in BITS:
            if rnd.random() < 0.12: add |= b
        add &= ~0x8000 if rnd.random() < 0.9 else 0xFFFF
        imm = rnd.choice([0, 0, 0x0800, 0x2010, 0x7FFC, rnd.randrange(65536)]) & ~0x8000
        v96 = rnd.randrange(0, 1000); mdef = rnd.randrange(0, 1000)
        cur, _x = model(cur, 0, 0)         # make the starting word self-consistent
        h.sw(0x190, cur); h.sw(0x1EE, cur & 0xFFFC); h.sw(0x19E, cur); h.sw(0x1AA, imm); h.sw(0x1A8, mdef)
        for k in range(0x1B2, 0x1BA): h.sb(k, 0)
        h.sw(0x182, 300); h.sw(0x184, 300)
        c = env.c; c.wram[0x300 + 0x9A] = add & 255; c.wram[0x300 + 0x9B] = add >> 8; c.wram[0x300 + 0x96] = v96 & 255; c.wram[0x300 + 0x97] = v96 >> 8
        c.wram[0x385] = 0; c.wram[0x386] = 0       # $85 = object pointer (hero 0)
        env.call(0xC8E301, X=0, m=1, x=0, D=0x300)
        exp, newbits = model(cur, add, imm)
        got = h.w(0x190)
        if got != exp:
            bad += 1
            if bad < 6: print('STATUS MISMATCH cur %04X add %04X imm %04X -> rom %04X model %04X' % (cur, add, imm, got, exp))
        d = duration(v96, mdef)
        # a timer is loaded for new bits of its group (only checked when the status survived and nothing special happened)
        if got == exp and not (exp & 0x8000):
            for mask, off in ((0x007C, 0x1B2), (0x0180, 0x1B3), (0x1C00, 0x1B5), (0x6000, 0x1B6)):
                want = d if (newbits & mask) else 0
                if h.b(off) != want:
                    badt += 1
                    if badt < 6: print('TIMER MISMATCH off %X cur %04X add %04X imm %04X got %d want %d' % (off, cur, add, imm, h.b(off), want))
    print('cases', n, 'status mismatches', bad, 'timer mismatches', badt)

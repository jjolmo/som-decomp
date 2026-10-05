"""Validate the spell-level progress rule against the REAL routine $D0:4DCD (called on the first hit of every hero spell).
usage: validate_magic_level.py ROM STATE [N=1500]
Model (docs/rom-combat.md section 11.5): L = level of the spell's element, cap C = $CFFC (8 means no cap); if L < (9 if C == 8 else C):
progress += (9 - L) (halved when $ED bit7 is clear); at >= 100 the level goes up and progress resets to 0; at L == 8 progress sticks at 99."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce


def model(L, prog, cffc, ed7):
    a6 = 9 if cffc == 8 else cffc
    if L >= a6: return L, prog
    ac = 9 - L
    if not ed7: ac >>= 1
    p = prog + ac
    if p < 100: return L, p
    if L == 8: return L, 99
    return L + 1, 0


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    rnd = random.Random(3); bad = 0
    for _ in range(n):
        env = ce.Env(rom, state); h = env.obj(rnd.randrange(3)); slot = (h.base - 0xE000)
        idx = rnd.randrange(8); L = rnd.randrange(9); prog = rnd.randrange(100); cffc = rnd.choice([0, 1, 3, 5, 7, 8, 8, 8]); ed7 = rnd.random() < 0.5
        env.c.wram[0xCFFC] = cffc
        env.c.wram[0xED] = 0x80 if ed7 else 0
        for j in range(4): h.sb(0x1C4 + j, 0)
        b = h.b(0x1C4 + (idx >> 1)); b = (b & 0x0F) | L << 4 if idx % 2 == 0 else (b & 0xF0) | L
        h.sb(0x1C4 + (idx >> 1), b)
        for j in range(8): h.sb(0x1D8 + j, rnd.randrange(100))
        h.sb(0x1D8 + idx, prog); h.sb(0x177, idx)
        env.c.wram[0x383] = slot & 255; env.c.wram[0x384] = slot >> 8
        env.call(0xD04DCD, Y=slot, m=1, x=0, D=0x300)
        byte = h.b(0x1C4 + (idx >> 1)); got = (byte >> 4 if idx % 2 == 0 else byte & 15, h.b(0x1D8 + idx))
        exp = model(L, prog, cffc, ed7)
        if got != exp:
            bad += 1
            if bad < 6: print('MISMATCH idx', idx, 'L', L, 'prog', prog, 'cffc', cffc, 'ed7', ed7, 'rom', got, 'model', exp)
    print('cases', n, 'mismatches', bad)

"""Validate phys_model.py against the REAL ROM routines.  usage: validate_phys.py ROM STATE [N]
Runs $C0:4FED/505B/50CA/514B/5119 in the 65816 interpreter with randomised attacker/defender objects and compares with the Python model."""
import sys, random, romio, combat_env, rng as R, phys_model as P
def units(env, ai, di):
    A, Dn = env.obj(ai), env.obj(di)
    def g(o, s):
        return dict(A4=o.b(0x1A4), A5=o.w(0x1A5), B0=o.w(0x1B0), B0w=o.w(0x1B0), E191=o.b(0x191), E190=o.b(0x190), E197=o.b(0x197), E198=o.b(0x198),
                    ED=o.b(0x1ED), E19B=o.b(0x19B), E189=o.b(0x189), AE=o.b(0x1AE), E6=o.b(0x1E6), E196=o.b(0x196), E194=o.w(0x194), A2=o.w(0x1A2), A0=o.w(0x1A0),
                    B1=o.b(0x1B1), BF=o.b(0x1BF), CC76=env.c.wram[0xCC76], hero=bool(o.b(0x1FB) & 0x80))
    return g(A, ai), g(Dn, di)
def rom_hit(env, ai, di):
    c = env.c
    A, Dn = env.obj(ai), env.obj(di)
    X, Y = 0x200 * di, 0x200 * ai
    c.wram[0x385] = X & 0xFF; c.wram[0x386] = X >> 8     # DP = $0300
    c.wram[0x382] = ai; c.wram[0x383] = Y & 0xFF; c.wram[0x384] = Y >> 8
    Dn.sw(0x1F1, 0); Dn.sw(0x1F3, 0)
    env.call(0xC04FED, X=X, Y=Y, m=1, x=0, D=0x300, long=False)
    env.call(0xC0505B, X=X, Y=Y, m=1, x=0, D=0x300, long=False)
    hit = c.C
    if not hit: return False, 0
    env.call(0xC050CA, X=X, Y=Y, m=1, x=0, D=0x300, long=False)
    env.call(0xC0514B, X=X, Y=Y, m=1, x=0, D=0x300, long=False)
    return True, Dn.w(0x1F1)
if __name__ == '__main__':
    rom = romio.rom_from_argv(); state = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    ok = bad = 0
    random.seed(1)
    for t in range(N):
        env = combat_env.Env(rom, state)
        c = env.c
        mid = random.choice([0x00, 0x01, 0x05, 0x10, 0x11, 0x12, 0x20, 0x30, 0x40, 0x50, 0x79])
        env.call(0xC055EC, A=mid, X=0x600, m=1, x=0)
        att_hero = random.random() < 0.5
        ai, di = (random.choice([0, 1, 2]), 3) if att_hero else (3, random.choice([0, 1, 2]))
        for sl in (ai, di):
            o = env.obj(sl)
            o.sb(0x1B0, random.choice([0, 0, 0x10, 0x20, 0x04, 0x08, 0x01, 0x02]))
            o.sb(0x1B1, random.choice([0, 0, 0x10]))
            o.sb(0x191, random.choice([0, 0, 0, 0x02]))
            o.sb(0x190, random.choice([0, 0, 0, 0x04, 0x10]))
            o.sb(0x1AE, random.choice([0, 0, 0, 1, 5, 9]))
            o.sb(0x19B, random.randrange(0, 9))
            o.sb(0x1BF, random.randrange(0, 40))
            o.sb(0x1E6, random.choice([0, 0, 0, 2]))
            o.sw(0x194, random.choice([0, 0x0100, 0x0200, 0x0400]))
        env.obj(di).sw(0x1A2, random.choice([0, 0x0100, 0x0200])); env.obj(di).sw(0x1A0, random.choice([0, 0x0400, 0x0800]))
        env.obj(ai).sb(0x1ED, random.choice([0, 0, 0, 5, 30, 60, 99]))
        for i in range(0x3F1, 0x400): c.wram[i] = random.randrange(256)
        c.wram[0x3F0] = random.randrange(15)
        ua, ud = units(env, ai, di)
        rg = R.Rng.from_wram(c.wram)
        ev, df = P.def_terms(ud)
        hit, acc = P.hit_test(ua, ev, rg)
        exp = 0
        if hit:
            m8f = P.elem_mult(ua, ud)
            exp, crit = P.damage(ua, ud, m8f, acc, ev, df, rg, ai if ai < 3 else 9, att_hero)
        got_hit, got = rom_hit(env, ai, di)
        if (hit, exp) == (got_hit, got): ok += 1
        else:
            bad += 1
            if bad <= 8: print('MISMATCH mid=%02X att=%d def=%d model hit=%s dmg=%d rom hit=%s dmg=%d' % (mid, ai, di, hit, exp, got_hit, got), ua['E197'], ua['E198'], ud['A4'], ud['A5'])
    print('ok', ok, 'bad', bad)

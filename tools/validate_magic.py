"""Validate magic_model.py against the REAL ROM routine $C8:E7A7 (spell hit on a target).  usage: validate_magic.py ROM STATE [N]"""
import sys, random, romio, combat_env, rng as R, magic_model as M
SPELL_ROW = 0x102AD0          # D0:2AD0 + id*64
def row(rom, sid):
    o = SPELL_ROW + sid * 64
    return dict(id=sid, power=rom[o + 10], acc=rom[o + 11], elem=rom[o + 12], mp=rom[o + 15])
def run_rom(env, ci, ti, sid, level, divisor):
    c = env.c; C, T = env.obj(ci), env.obj(ti)
    X, Y = 0x200 * ti, 0x200 * ci
    for off, v in ((0x385, X & 255), (0x386, X >> 8), (0x383, Y & 255), (0x384, Y >> 8), (0x382, ci)): c.wram[off] = v
    sdc = sid * 64; c.wram[0x3DC] = sdc & 255; c.wram[0x3DD] = sdc >> 8; c.wram[0x3DE] = 0xD0
    c.wram[0x39D] = level
    C.sb(0x170, sid); C.sb(0x171, level); C.sb(0x176, divisor)
    T.sw(0x1F1, 0); T.sw(0x1F3, 0)
    env.call(0xC8E7A7, X=X, Y=Y, m=1, x=0, D=0x300, long=True)
    return T.w(0x1F1), T.w(0x1F3)
if __name__ == '__main__':
    rom = romio.rom_from_argv(); state = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    random.seed(7); ok = bad = 0
    for t in range(N):
        env = combat_env.Env(rom, state); c = env.c
        mid = random.choice([0x00, 0x01, 0x11, 0x12, 0x20, 0x30, 0x40, 0x50, 0x79])
        env.call(0xC055EC, A=mid, X=0x600, m=1, x=0)
        hero_cast = random.random() < 0.6
        ci, ti = (random.choice([0, 1, 2]), 3) if hero_cast else (3, random.choice([0, 1, 2]))
        sid = random.choice([0, 1, 6, 7, 0xC, 0xD, 0xE, 0x10, 0x11, 0x12, 0x13, 0x1F, 0x25, 0x28, 0x0B])   # handlers that end in $C8:E9DF
        level = random.randrange(0, 9); divisor = random.choice([1, 1, 1, 2, 3])
        Cc, Tt = env.obj(ci), env.obj(ti)
        Cc.sb(0x1E6, random.choice([0, 0, 2]))
        Tt.sw(0x1A0, random.choice([0, 0x0100, 0x0400])); Tt.sw(0x1A2, random.choice([0, 0x0100, 0x0200]))
        # E1A1 / E1A3 are the byte masks used by spells
        Tt.sb(0x1A1, random.choice([0, 0, 0x01, 0x04, 0x10, 0x3F])); Tt.sb(0x1A3, random.choice([0, 0, 0x02, 0x08, 0x20]))
        Tt.sb(0x1A7, random.randrange(0, 100)); Tt.sw(0x1A8, random.randrange(0, 700))
        for i in range(0x3F1, 0x400): c.wram[i] = random.randrange(256)
        c.wram[0x3F0] = random.randrange(15)
        rg = R.Rng.from_wram(c.wram)
        crow = row(rom, sid)
        cu = dict(INT=Cc.b(0x18B), WIS=Cc.b(0x18C), E1FD=Cc.b(0x1FD), E1FE=Cc.b(0x1FE), E6=Cc.b(0x1E6))
        tu = dict(MDEF=Tt.w(0x1A8), MEV=Tt.b(0x1A7), RES=Tt.b(0x1A3), WEAK=Tt.b(0x1A1))
        if sid == 0x0B:
            exp = M.heal_amount(cu, tu, crow, level, divisor, hero_cast, rg)
            dmg_got, got = run_rom(env, ci, ti, sid, level, divisor)
        else:
            exp, m8 = M.spell_damage(cu, tu, crow, level, divisor, hero_cast, rg)
            got, heal = run_rom(env, ci, ti, sid, level, divisor)
        if exp == got: ok += 1
        else:
            bad += 1
            if bad <= 8: print('MISMATCH spell=%02X lvl=%d div=%d hero=%s model=%d rom=%d' % (sid, level, divisor, hero_cast, exp, got), cu, tu)
    print('ok', ok, 'bad', bad)

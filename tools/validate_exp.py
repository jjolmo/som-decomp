"""Validate the experience / level-up model against the REAL ROM routine $C0:4459 (kill reward: every living hero gets the monster's full EXP).
usage: validate_exp.py ROM STATE"""
import sys, random, romio, combat_env, hero_stats
def model(rom, hero, level, exp, gain):
    exp = min(exp + gain, 9999999)
    ex = lambda L: rom[0x104B58 + 3 * L] | rom[0x104B58 + 3 * L + 1] << 8 | rom[0x104B58 + 3 * L + 2] << 16
    while level < 98 and exp >= ex(level): level += 1
    return level, exp
if __name__ == '__main__':
    rom = romio.rom_from_argv(); state = sys.argv[1]
    random.seed(3); ok = bad = 0
    for t in range(60):
        env = combat_env.Env(rom, state); c = env.c
        env.call(0xC055EC, A=random.choice([0x00, 0x11, 0x79, 0x50]), X=0x600, m=1, x=0)
        mon = env.obj(3); gain = random.choice([mon.w(0x18D), random.randrange(1, 4000), 12345])
        mon.sw(0x18D, gain); mon.sb(0x18F, 0)
        h = env.obj(0)
        level = random.choice([0, 1, 5, 40, 64, 97, 98]); exp0 = random.randrange(0, 30000)
        h.sb(0x181, level); env.call(0xC04530, X=0, m=1, x=0)       # rebuild stats/expected-exp for that level
        h.sw(0x18D, exp0 & 0xFFFF); h.sb(0x18F, exp0 >> 16)
        for k in (1, 2): env.obj(k).sw(0x182, 0)                          # only hero 0 alive
        c.wram[0x383] = 0; c.wram[0x384] = 0; c.wram[0x385] = 0x00; c.wram[0x386] = 0x06
        env.call(0xC04459, m=1, x=0, D=0x300, long=False)
        got = (h.b(0x181), h.w(0x18D) | h.b(0x18F) << 16)
        exp_ = model(rom, 0, level, exp0, gain)
        if got == exp_: ok += 1
        else:
            bad += 1; print('MISMATCH', level, exp0, gain, 'model', exp_, 'rom', got)
    print('ok', ok, 'bad', bad)

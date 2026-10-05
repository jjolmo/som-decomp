"""Weapon level-up model (ROM routine $C0:4358 -> $C0:43B7) and a validator that runs the real routine.
usage: weapon_level.py ROM STATE [N]
Model (all values from the ROM, see docs/rom-combat.md section 11.2):
  A6 = 9 - killer.weapon_level;  halved if monster level < killer level
  killer gets A6, the other two living heroes get A6>>1 (applied with the killer's weapon level, each on its OWN weapon type)
  per hero: wl = weapon level of its equipped type; cap = orbs[type] + 1
     wl == cap          -> progress = 0
     else progress += A6; if progress >= 99: wl == 8 -> progress = 99 else progress = 0, level += 1
  ROM quirk: the level-up message code leaves the new weapon level (one digit) in the scratch byte A6, so the heroes
  processed AFTER a level-up in the same kill get that value (halved once if the level-up was the killer's) instead of 9 - wl.
"""
import sys, random
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import combat_env as ce

THRESH = 99          # table at $C0:43AC, 99 for all nine levels


def nibble(h, t):
    b = h['nib'][t >> 1]
    return b >> 4 if (t & 1) == 0 else b & 15


def set_nibble(h, t, v):
    b = h['nib'][t >> 1]
    h['nib'][t >> 1] = (b & 0x0F) | v << 4 if (t & 1) == 0 else (b & 0xF0) | v


def model_kill(heroes, caps, mon_level, killer):
    k = heroes[killer]
    a6 = 9 - nibble(k, k['type'])
    if mon_level < k['level']:
        a6 >>= 1
    order = [killer] + [i for i in range(3) if i != killer]
    for n, i in enumerate(order):
        h = heroes[i]
        if n == 1:
            a6 >>= 1
        if not h['alive']:
            continue
        t = h['type']; wl = nibble(h, t)
        if wl == caps[t] + 1:
            h['prog'][t] = 0
            continue
        p = (h['prog'][t] + a6) & 255
        if p < THRESH:
            h['prog'][t] = p
        elif wl == 8:
            h['prog'][t] = THRESH
        else:
            h['prog'][t] = 0
            set_nibble(h, t, wl + 1)
            a6 = wl + 1
    return heroes


def run_case(rom, state, rnd):
    env = ce.Env(rom, state)
    caps = [rnd.randint(0, 8) for _ in range(8)]
    for t in range(8):
        env.c.wram[0xCFB0 + t] = caps[t]
    heroes = []
    for i in range(3):
        o = env.obj(i)
        h = dict(type=rnd.randint(0, 7), level=rnd.randint(1, 98), alive=rnd.random() < 0.85,
                 nib=[rnd.randint(0, 8) << 4 | rnd.randint(0, 8) for _ in range(4)], prog=[rnd.randint(0, 98) for _ in range(8)])
        o.sb(0x1E4, h['type']); o.sb(0x1E8, h['type'] * 9); o.sb(0x1E9, h['type'] * 9); o.sb(0x181, h['level'])
        for j in range(4): o.sb(0x1C0 + j, h['nib'][j])
        for j in range(8): o.sb(0x1D0 + j, h['prog'][j])
        o.sb(0x19C, nibble(h, h['type']))
        o.sb(0x191, 0 if h['alive'] else 0x80)
        o.sb(0x182, 100); o.sb(0x183, 0)
        heroes.append(h)
    killer = rnd.randint(0, 2)
    mon_level = rnd.randint(0, 120)
    m = env.obj(3); m.sb(0x181, mon_level); m.sb(0x1F0, killer)
    # the routine requires the killer to be a valid living hero object
    heroes[killer]['alive'] = True; env.obj(killer).sb(0x191, 0)
    model_kill(heroes, caps, mon_level, killer)
    env.call(0xC04358, X=0x600, Y=killer * 0x200, m=1, x=0, D=0x300, long=False)
    bad = []
    for i in range(3):
        o = env.obj(i); h = heroes[i]
        got = (o.b(0x1C0), o.b(0x1C1), o.b(0x1C2), o.b(0x1C3), tuple(o.b(0x1D0 + j) for j in range(8)))
        exp = (*h['nib'], tuple(h['prog']))
        if got != exp: bad.append((i, got, exp))
    return bad


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    rnd = random.Random(1)
    nbad = 0
    for _ in range(n):
        b = run_case(rom, state, rnd)
        if b:
            nbad += 1
            if nbad < 4: print('MISMATCH', b)
    print('cases', n, 'mismatches', nbad)

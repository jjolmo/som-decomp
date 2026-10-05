"""Run an ordinary monster (ids 0-0x56) in the real per-frame game routine and log its AI bytecode.
usage: ai_sim.py ROM STATE MONSTER_ID SECONDS [--hero DX,DY (hero position relative to the monster)] [--tile TX,TY] [--seed N] [--hero-ai] [--ops]
STATE: ZSNES v143 state with the party on a map, monster slots 3-5 free and the pause flag $F1 clear (the map-246 arena state is used in the docs;
states with live monsters in slots 3-5 or with $F1 bit 7 set do not work). The monster is created in slot 3 by the
game's own spawner $C0:DE3B from a map-object record placed at WRAM $C830; each frame runs $C0:B08C with $56 = frame % 5
(PPU, DMA and sound are not emulated; the waits for NMI at $C1:E0F9 and $C1:E6AC are stubbed). Heroes 1 and 2 are made inactive, hero 0 is pinned
at its saved position (or at --hero offset from the monster) and its AI step is disabled unless --hero-ai.
library: Sim(rom, state, mid).frame(); .ops (tick, script pc, opcode); .obj(slot)"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, combat_env

REC = 0xC830            # map-object record used for the spawn (offset relative to $C800 is 0x30)
SCRIPT_BASE = 0x104F15


class Sim:
    def __init__(self, rom, state, mid=0, tile=(20, 25), seed=None, hero_ai=False, hero=None, only_hero0=True, slot=3):
        self.rom = rom
        self.env = env = combat_env.Env(rom, state)
        self.c = c = env.c
        self.mid = mid
        self.f = 0
        self.tick_ops = []
        self.steps = []          # one entry per AI step: (frame, [(pc, op)], command bytes issued)
        self.hero_ai = hero_ai
        self.pin = None
        def rts(cp):
            cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
        for a in (0xE0F9, 0xE6AC):                 # waits for NMI (flag $EC bit 1), stubbed
            c.hooks[0xC10000 | a] = rts; c.hooks[0x010000 | a] = rts
        if seed is not None:
            c.wram[0x33D] = seed
        if only_hero0:
            for s in (1, 2): env.obj(s).sb(0, 0)
        rec = bytes.fromhex('01 00 00 00 00 00 00 40 4e 66 92 15 40 00 2d 44')
        for i, b in enumerate(rec): c.wram[REC + i] = b
        c.wram[REC + 0xA], c.wram[REC + 0xB], c.wram[REC + 0xD] = tile[0], tile[1], mid
        env.call(0xC0DE3B, X=0x200 * slot, Y=REC - 0xC800, m=1, x=0, long=False)
        self.o = env.obj(slot)
        h = env.obj(0)
        self.pin = (h.w(2), h.w(4))
        if hero is not None:              # hero offset from the monster: the monster is moved, the hero keeps its saved on-screen position
            self.o.sw(2, self.pin[0] - hero[0]); self.o.sw(4, self.pin[1] - hero[1])
        if not hero_ai:
            def ai(cp):
                if cp.X < 0x600:
                    cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
                return False
            c.hooks[0xC12552] = ai
        orig = c.step
        o = self.o
        def st():
            a = c.PB << 16 | c.PC
            if a == 0xC1251A and c.Y == o.base:
                pc = c.wram[o.base + 0x144] | c.wram[o.base + 0x145] << 8
                self.tick_ops.append((self.f, pc, rom[SCRIPT_BASE + pc]))
            orig()
        c.step = st

    def obj(self, slot): return self.env.obj(slot)

    def frame(self):
        c = self.c
        if self.pin:
            h = self.env.obj(0); h.sw(2, self.pin[0]); h.sw(4, self.pin[1])
        c.wram[0x56] = self.f % 5
        n0 = len(self.tick_ops)
        self.env.call(0xC0B08C, m=1, x=0, long=False, DB=0x7E, max_steps=3000000)
        if len(self.tick_ops) > n0:
            o = self.o
            self.steps.append((self.f, [(pc, op) for _, pc, op in self.tick_ops[n0:]], tuple(o.b(0x140 + i) for i in range(4))))
        self.f += 1


def main():
    args = sys.argv[1:]
    opts = {}
    for k in ('--hero', '--tile', '--seed'):
        if k in args:
            i = args.index(k); opts[k] = args[i + 1]; del args[i:i + 2]
    hero_ai = '--hero-ai' in args
    show_ops = '--ops' in args
    args = [a for a in args if not a.startswith('--')]
    rom = romio.load(args[0]); state = args[1]; mid = int(args[2], 0); secs = float(args[3])
    hero = tuple(int(v) for v in opts['--hero'].split(',')) if '--hero' in opts else None
    tile = tuple(int(v) for v in opts['--tile'].split(',')) if '--tile' in opts else (20, 25)
    s = Sim(rom, state, mid, tile, int(opts['--seed']) if '--seed' in opts else None, hero_ai, hero)
    o = s.o; h = s.obj(0)
    prev = None
    for _ in range(int(secs * 60.0988)):
        s.frame()
        row = (o.w(2), o.w(4), o.b(0x140), o.b(0x141), o.b(0x142), o.b(0x143), o.w(0x182), h.w(0x182))
        if row != prev:
            print('f=%5d t=%7.3fs pos=(%d,%d) cmd=%02X %02X %02X %02X hp=%d hero_hp=%d' % ((s.f, s.f / 60.0988) + row))
            prev = row
    if show_ops:
        for f, pc, op in s.tick_ops: print('f=%5d pc=%04X op=%02X' % (f, pc, op))


if __name__ == '__main__':
    main()

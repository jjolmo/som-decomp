"""Run the map-object boss 0x7F (monster record 127) in the real C2 engine with the game's own frame schedule, logging phases and events.
usage: mb_sim.py ROM STATE FRAMES [SEED] [key=value ...]
STATE is the map-246 arena save state (heroes in object slots 0-2). Options: hp=N (boss HP), hero=X,Y (put all heroes there), force=PHASE@FRAME
(sets $94 at that frame; the run is then labelled 'phase forced'), dead=FRAME (sets the dead bit of $190 at that frame), quiet=1 (phase table only).
One frame = one call of the main-loop body $C0:B08C with $56 = frame mod 5 (the game dispatches the actors from there; the C2 boss engine runs for $56 in {0,1,2}).
library: MB(rom, state, seed) -> .frame(), .ev (event list), .r8/.r16(offset, slot)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, lich_sim

HOOKS = {0xC0006C: 'ROW', 0xC2396D: 'SPELL', 0xC0001B: 'CAST', 0xC20D53: 'NEWOBJ', 0xC2272D: 'PALFX', 0xC22700: 'PAL', 0xC224C3: 'GFX',
         0xC230E3: 'SND', 0xC2310A: 'SND2', 0x018000: 'EVT8000', 0x018003: 'EVT8003', 0x01800F: 'EVT800F', 0x018015: 'EVT8015', 0xC0006F: 'C0_006F', 0xC20C11: 'ENDEVT', 0xC23963: 'EV3'}


class MB(lich_sim.Sim):
    def __init__(self, rom, state, seed=1):
        super().__init__(rom, state, rng_index=seed, hero_hits=True, immortal=False)
        self.ev = []
        self.hero = [(self.w(0xE182 + 0x200 * h), self.w(0xE190 + 0x200 * h)) for h in range(3)]
        self.bhp = 0
        self.bfl = (0, 0, 0)
        self.ticks = 0
        for a, nm in HOOKS.items():
            self.c.hooks[a] = self._hook(nm)
        self.c.hooks[0xC20F83] = self._tickhook

    def _hook(self, nm):
        def h(c):
            self.ev.append((self.f, nm, c.A & 0xFFFF, c.X & 0xFFFF, c.Y & 0xFFFF, self.r16(0x94, 0)))
            return False
        return h

    def _tickhook(self, c):
        if c.X == 0xE600: self.ticks += 1
        return False

    def spawn_beast(self):
        self.c.wram[0xC82D] = 0x7F
        self.spawn(0x7F)

    def frame(self):
        lich_sim.Sim.frame(self)
        for h in range(3):
            b = 0xE000 + 0x200 * h
            cur = (self.w(b + 0x182), self.w(b + 0x190))
            if cur != self.hero[h]:
                self.ev.append((self.f, 'HERO%d' % h, cur[0], cur[1], self.hero[h][0], self.phase()))
                self.hero[h] = cur
        fl = (self.r8(0x1B1, 0), self.r8(0x1B0, 0), self.r16(0x190, 0))
        if fl != self.bfl:
            self.ev.append((self.f, 'BOSSFLG', fl[0], fl[1], fl[2], self.phase())); self.bfl = fl
        hp = self.r16(0x182, 0)
        if hp != self.bhp:
            self.ev.append((self.f, 'BOSSHP', hp, self.bhp, 0, self.phase())); self.bhp = hp

    def w(self, a): return self.c.wram[a] | self.c.wram[a + 1] << 8      # WRAM word at $7E:a

    def phase(self): return self.r16(0x94, 0)

    def hostile_targets(self):
        """Run the hero hostile-spell target builder $D0:DA60 ($1842 = 0x81) on a copy of the WRAM; returns the list of valid monster-slot offsets."""
        import cpu65816 as cpu
        c2 = cpu.CPU(); c2.wram[:] = self.c.wram; c2.wram[0x1842] = 0x81
        c2.M = 1; c2.XF = 0; c2.S = 0x1F00; c2.push8(0xFE); c2.push16(0xFFFD); c2.PB = 0xD0; c2.PC = 0xDA60
        while not (c2.PB == 0xFE and c2.PC == 0xFFFE): c2.step()
        return [c2.rd16(0x1812 + 2 * i) for i in range(3) if c2.rd16(0x1812 + 2 * i)]


def parse(args):
    o = {}
    for a in args:
        k, v = a.split('=', 1); o[k] = v
    return o


def run(rom, state, frames, seed=1, opts=None):
    o = opts or {}
    s = MB(rom, state, seed)
    s.spawn_beast()
    if 'hero' in o:
        x, y = [int(v) for v in o['hero'].split(',')]
        for h in range(3):
            s.c.wr16(0xE000 + 0x200 * h + 2, x); s.c.wr16(0xE000 + 0x200 * h + 4, y)
    if 'hp' in o:
        s.w16(0x182, int(o['hp']), 0)
    force = {}
    if 'force' in o:
        for item in o['force'].split(';'):
            p, f = item.split('@'); force[int(f)] = int(p, 0)
    dead = int(o['dead']) if 'dead' in o else None
    seg = []; cur = None
    for _ in range(frames):
        if s.f in force:
            s.w16(0x94, force[s.f], 0); s.w16(0x96, 0, 0)
        if dead is not None and s.f == dead:
            s.w16(0x190, s.r16(0x190, 0) | 0x8000, 0)
        n0 = len(s.ev)
        s.frame()
        ph = s.phase()
        if cur is None or ph != cur['ph']:
            if cur: cur['end'] = s.f; cur['ticks_end'] = s.ticks
            cur = dict(ph=ph, start=s.f, ticks_start=s.ticks, x=s.r16(0x2B, 0), y=s.r16(0x32, 0), ev=[])
            seg.append(cur)
        cur['ev'].extend(s.ev[n0:])
    if cur: cur['end'] = s.f; cur['ticks_end'] = s.ticks
    return s, seg


if __name__ == '__main__':
    rom = romio.rom_from_argv()
    state = sys.argv[1]; frames = int(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 and '=' not in sys.argv[3] else 1
    opts = parse([a for a in sys.argv[3:] if '=' in a])
    skip = set(opts.get('skip', 'PAL,PALFX,GFX').split(','))
    s, seg = run(rom, state, frames, seed, opts)
    for g in seg:
        print('phase %02X: frames %d-%d (%d frames, %d ticks = %.2f s) entry pos (%04X,%04X)' % (g['ph'], g['start'], g['end'], g['end'] - g['start'],
              g['ticks_end'] - g['ticks_start'], (g['end'] - g['start']) / 60.0988, g['x'], g['y']))
        if 'quiet' not in opts:
            for e in g['ev']:
                if e[1] in skip: continue
                print('    f=%-6d %-8s A=%04X X=%04X Y=%04X (phase %02X when logged)' % e)

"""Run the REAL boss engine from a ZSNES save state taken in the Dark Lich arena (map 246), one full game frame at a time.
The Lich is spawned through the game's own boss spawn ($C2:0000, map object record id 0x79) and the original 65816
code is stepped frame by frame in cpu65816.py (sound driver and PPU/DMA are not emulated).
library: Sim(rom, state_path, rng_index, hero_hits=False, immortal=True).spawn(); .frame(); .lich(offset)
cli:     lich_sim.py ROM STATE [frames] [seed]   -> prints one line per state change
One frame = one call of the main-loop body $C0:B08C with $56 = frame mod 5, as $C0:B06C-B08A does; the C2 engine is then called by $C0:FD12 only for $56 = 0,1,2
(12.02 ticks/s for flags with high byte &3 == 0). NMI wait loops (BIT $EC / BNE) are released."""
import sys, random, romio, cpu65816 as cpu, zsnes_state
SLOT = 0x7EE600
NMI_WAITS = (0x808d, 0xa4b4, 0xb068, 0xb079, 0xbf15, 0xbf47, 0xc053, 0xc09d, 0xcb6d, 0x1caf4, 0x1cb0d, 0x1cb48, 0x1cb7d, 0x1e0ff, 0x1e6b2, 0x2cae6, 0x2cdbc, 0x2cfdb)
class Sim:
    def __init__(self, rom, state_path, rng_index=None, hero_hits=False, immortal=True):
        cpu.set_rom(rom)
        self.c = c = cpu.CPU()
        c.wram[:] = zsnes_state.load_wram(state_path)
        def rtl(s):
            s.PC = (s.pull16()+1) & 0xFFFF; s.PB = s.pull8(); return True
        c.hooks[0xC30004] = rtl; c.hooks[0xC30000] = rtl      # sound driver not emulated
        self.f = 0
        self.immortal = immortal       # heroes' HP is refilled every frame (the boss would otherwise kill them and the game resets)
        c.wram[0x5C] = 0x80          # set by the map-object spawner ($C0:DE0D) for boss ids
        if not hero_hits:            # the party AI of the full frame would hit the boss; $C2:052E (hero weapon vs boss) then reports 'no contact'
            def nohit(cp): cp.C = 0; cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
            c.hooks[0xC2052E] = nohit
        def nmi(cp): cp.wram[0xEC] = 0; return False
        for o in NMI_WAITS:
            for pc in {(0xC0 + (o >> 16)) << 16 | o & 0xFFFF} | ({(o >> 16) << 16 | o & 0xFFFF} if o & 0x8000 else set()):
                c.hooks[pc] = nmi
        if rng_index is not None: c.wram[0x33D] = rng_index
    def call(self, addr, A=None, max_steps=3_000_000):
        c = self.c; c.M = 0; c.XF = 0
        if A is not None: c.A = A
        c.S = 0x1F00; c.push8(0xFE); c.push16(0xFFFD)
        c.PB = addr >> 16; c.PC = addr & 0xFFFF
        n = 0
        while not (c.PB == 0xFE and c.PC == 0xFFFE):
            c.step(); n += 1
            if n > max_steps: raise RuntimeError('timeout at %02X:%04X' % (c.PB, c.PC))
        return n
    def spawn(self, boss=0x79):
        c = self.c
        c.wram[0xCF4E] = (c.wram[0xCF4E] & 0xF0) | 6     # progress flag the boss record requires
        for i in range(9): c.wram[0xE60+i] = 0            # stale active flags in the state
        self.call(0xC20000, A=boss)
    def callrts(self, addr, max_steps=3_000_000):
        c = self.c; c.M = 1; c.XF = 0; c.S = 0x1F00; c.push16(0xFFFD); c.PB = addr >> 16; c.PC = addr & 0xFFFF
        n = 0
        while not (c.PB == addr >> 16 and c.PC == 0xFFFE):
            c.step(); n += 1
            if n > max_steps: raise RuntimeError('timeout at %02X:%04X' % (c.PB, c.PC))
        return n
    def frame(self):
        w = self.c.wram
        if self.immortal:
            for h in range(3): b = 0xE000 + 0x200 * h; w[b + 0x182] = w[b + 0x184]; w[b + 0x183] = w[b + 0x185]
        w[0x56] = self.f % 5
        n = self.callrts(0xC0B08C)
        self.f += 1
        return n
    def r8(self, off, slot=0): return self.c.rd8(SLOT + 0x200*slot + off)
    def r16(self, off, slot=0): return self.c.rd16(SLOT + 0x200*slot + off)
    def w16(self, off, v, slot=0): self.c.wr16(SLOT + 0x200*slot + off, v)
    def w8(self, off, v, slot=0): self.c.wr8(SLOT + 0x200*slot + off, v)
    def snapshot(self, slot=0):
        return dict(state=self.r8(0x7A, slot), seq=self.r16(0xB0, slot), idx=self.r16(0xB2, slot), phase94=self.r16(0x94, slot),
                    mode82=self.r16(0x82, slot), flags7e=self.r16(0x7E, slot), dur=self.r16(0x14, slot), thr=self.r16(0x2D, slot),
                    ad=self.r16(0xAD, slot), age=self.r16(0x96, slot), x=self.r16(0x2B, slot), y=self.r16(0x32, slot))
if __name__ == '__main__':
    rom = romio.rom_from_argv()
    s = Sim(rom, sys.argv[1], rng_index=int(sys.argv[3]) if len(sys.argv) > 3 else None)
    s.spawn()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    last = None
    for _ in range(n):
        s.frame()
        sn = s.snapshot()
        key = (sn['state'], sn['seq'], sn['flags7e'])
        if key != last:
            print('f=%5d t=%7.2fs state=%02X seq=%04X mode=%d $7E=%04X ad=%d thr=%d pos=(%d,%d)' % (s.f, s.f/60.0988, sn['state'], sn['seq'], sn['mode82'], sn['flags7e'], sn['ad'], sn['thr'], sn['x'], sn['y']))
            last = key

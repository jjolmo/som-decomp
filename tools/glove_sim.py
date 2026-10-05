"""Frame-exact simulation of a hero's weapon attack on top of a ZSNES save state.
library: GloveSim(rom, state, slot, row, level, mon=(dx, dy) or None)
  - equips weapon row `row` (type = row // 9) on hero `slot` with the real routines $C0:4530 (stats) and $C0:EA41 (animation tables),
    makes that hero the one controlled by pad 1 ($D9) and switches the other heroes off;
  - optionally spawns a dummy monster with the game's own spawner $C0:DE3B (AI step disabled, HP 9999) at an offset from the hero;
  - .frame(pad) runs ONE video frame of the real main routine $C0:B08C (SNES pad word: 0x8000 = B button = attack);
  - .events collects the animation control ops executed for the hero ($C0:F90B) and the sound requests (JSL $C3:0004).
The sound driver, PPU and DMA are not emulated; the NMI waits ($C1:E0F9, $C1:E6AC) are stubbed. $56 (frame phase) follows the real main loop
(heroes run their object step when $56 == 3, i.e. one step per 5 frames). $F4 (frame counter, incremented by the NMI in the game) is advanced by the harness.
No ROM data is stored in the repository: every table is read from the ROM given on the command line."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce

REC = 0xC830
HERO_TICK_PHASE = 3          # $56 value at which the three heroes run their object step ($C0:B0D3)


class GloveSim:
    def __init__(self, rom, state, slot=0, row=0, level=1, mon=None, mid=0, phase0=0, f4=0, monhp=9999):
        self.rom = rom
        self.env = e = ce.Env(rom, state)
        self.c = c = e.c
        self.slot = slot
        self.f = 0
        self.phase0 = phase0
        self.f4 = f4
        self.pad = 0
        self.events = []
        def rts(cp):
            cp.PC = (cp.pull16() + 1) & 0xFFFF
            return True
        for a in (0xE0F9, 0xE6AC):
            c.hooks[0xC10000 | a] = rts
            c.hooks[0x010000 | a] = rts
        for sl in range(3):
            if sl != slot:
                e.obj(sl).sb(0, 0)
            e.obj(sl).sb(0x2C, 1 if sl == slot else 0)
        c.wram[0xD9] = 1 << slot
        c.wram[0xDA] = 0
        c.wram[0xDB] = 0
        self.h = h = e.obj(slot)
        self.base = h.base - 0xE000
        for off in (0x1A, 0x1B, 0x1C, 0x1D, 0x06, 0x07, 0x08, 0x1ED, 0x19B, 0x60, 0x61, 0x63, 0xA, 0x41):
            h.sb(off, 0)
        h.sb(0x1E3, row); h.sb(0x1E8, row); h.sb(0x1E4, row // 9)
        e.call(0xC04530, X=0x200 * slot, m=1, x=0)
        e.call(0xC0EA41, X=0x200 * slot, m=1, x=0, long=False)
        h.sb(0x19C, level)
        h.sb(0x11, 3)
        self.row = row
        self.level = level
        self.m = None
        orig_hw = c.hwread
        def hw(o, orig_hw=orig_hw):
            if o == 0x4218: return self.pad & 0xFF
            if o == 0x4219: return (self.pad >> 8) & 0xFF
            return orig_hw(o)
        c.hwread = hw
        orig_step = c.step
        def st():
            a = c.PB << 16 | c.PC
            if a == 0xC0F90B and c.X == self.base:
                p = c.wram[0] | c.wram[1] << 8
                self.events.append((self.f, 'op', p, c.A & 0xFF))
            elif a == 0xC0BB11:
                self.events.append((self.f, 'request95', c.A & 0xFF))
            elif a == 0xC30004:
                self.events.append((self.f, 'sound', c.wram[0x1E01], c.wram[0x1E02], c.wram[0x1E03]))
            orig_step()
        c.step = st
        if mon is not None:
            self.spawn(mon, mid, monhp)

    def spawn(self, mon, mid=0, monhp=9999, slot=3):
        e, c, h = self.env, self.c, self.h
        rec = bytes.fromhex('01 00 00 00 00 00 00 40 4e 66 92 15 40 00 2d 44')
        for i, b in enumerate(rec):
            c.wram[REC + i] = b
        c.wram[REC + 0xA], c.wram[REC + 0xB], c.wram[REC + 0xD] = 20, 25, mid
        e.call(0xC0DE3B, X=0x200 * slot, Y=REC - 0xC800, m=1, x=0, long=False)
        def ai(cp):
            if cp.X < 0x600:
                cp.PC = (cp.pull16() + 1) & 0xFFFF
                return True
            return False
        c.hooks[0xC12552] = ai
        self.m = m = e.obj(slot)
        m.sw(0x182, monhp); m.sw(0x184, monhp)
        m.sw(2, h.w(2) + mon[0]); m.sw(4, h.w(4) + mon[1])
        for off in (0x198,):
            m.sb(off, 1)             # dummy deals (almost) no damage to the hero

    def frame(self, pad=None):
        c = self.c
        if pad is not None:
            self.pad = pad
        c.wram[0x56] = (self.f + self.phase0) % 5
        c.wram[0xF4] = (self.f4 + self.f) & 0xFF
        self.env.call(0xC0B08C, m=1, x=0, long=False, DB=0x7E, max_steps=3000000)
        self.f += 1

    def sample(self):
        h, m = self.h, self.m
        d = dict(f=self.f - 1, phase=(self.f - 1 + self.phase0) % 5, x=h.w(2), y=h.w(4), vx=h.b(6), vy=h.b(7), vz=h.b(8),
                 st=h.b(0x1C), var=h.b(0x11), dur=h.b(0x12), ptr=h.w(0x16), spr=h.b(0x26), face=h.b(0x10),
                 rect=[h.b(0xC0 + i) for i in range(4)], body=[h.b(0xC8 + i) for i in range(4)],
                 gauge=h.b(0x1ED), stage=h.b(0x19B), c1a=h.b(0x1A), c1b=h.b(0x1B), e060=h.b(0x60), z=h.b(0x45))
        if m is not None:
            d.update(mhp=m.w(0x182), mx=m.w(2), my=m.w(4), m59=m.b(0x59), m5a=m.b(0x5A), mst=m.b(0x190))
        return d


def rom_script(rom, ptr, limit=64):
    """Raw bytes of an animation script (bank $D1 offset `ptr`) up to and including the first $FF end op."""
    out = []
    p = 0x110000 + ptr
    while len(out) < limit:
        out.append(rom[p + len(out)])
        if out[-1] == 0xFF and len(out) >= 1:
            break
    return bytes(out)


def decode_script(rom, ptr):
    """Split an animation script into (offset, kind, bytes) entries using the operand lengths of the interpreter $C0:F5A3 / $C0:F90B:
    byte < 0x80: frame word (2 bytes); 0x80-0xAF: 1 byte; 0xB0-0xEF: 2 bytes; 0xF0-0xF7: 3; 0xF8: 4; 0xF9: 3; 0xFA: 4; 0xFB-0xFE: 1; 0xFF: end."""
    p = 0x110000 + ptr
    ents = []
    pos = 0
    while pos < 400:
        op = rom[p + pos]
        if op < 0x80: ln, kind = 2, 'frame'
        elif op < 0xB0: ln, kind = 1, 'op'
        elif op < 0xF0: ln, kind = 2, 'op'
        elif op < 0xF8: ln, kind = 3, 'op'
        elif op == 0xF8: ln, kind = 4, 'op'
        elif op == 0xF9: ln, kind = 3, 'op'
        elif op == 0xFA: ln, kind = 4, 'op'
        elif op == 0xFF: ln, kind = 1, 'end'
        else: ln, kind = 1, 'op'
        ents.append((ptr + pos, kind, bytes(rom[p + pos:p + pos + ln])))
        pos += ln
        if kind == 'end':
            break
    return ents

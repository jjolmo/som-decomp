"""Shared harness: run real SoM routines in the Python 65816 CPU on top of a ZSNES save state WRAM.
Objects are 0x200-byte records at $7E:E000 + slot*0x200 (slots 0-2 heroes, 3-5+ monsters, see docs/rom-combat.md).
library:  env = Env(rom, state_path)   env.call(addr24, X=, Y=, A=, m=, x=)   env.obj(slot) -> Obj view
The ROM path and state path are always arguments; nothing from the ROM is stored in this repo."""
import cpu65816 as cpu, zsnes_state
OBJ = 0xE000
class Obj:
    def __init__(s, env, slot): s.e, s.slot, s.base = env, slot, OBJ + 0x200 * slot
    def b(s, o): return s.e.c.wram[s.base + o]
    def w(s, o): return s.e.c.wram[s.base + o] | s.e.c.wram[s.base + o + 1] << 8
    def sb(s, o, v): s.e.c.wram[s.base + o] = v & 0xFF
    def sw(s, o, v): s.sb(o, v); s.sb(o + 1, v >> 8)
class Env:
    def __init__(s, rom, state_path=None, rng_index=None):
        cpu.set_rom(rom)
        s.rom = rom
        s.c = c = cpu.CPU()
        if state_path: c.wram[:] = zsnes_state.load_wram(state_path)
        def rtl(cp):
            cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True
        c.hooks[0xC30004] = rtl; c.hooks[0xC30000] = rtl     # sound driver not emulated
        if rng_index is not None: c.wram[0x33D] = rng_index
    def obj(s, slot): return Obj(s, slot)
    def call(s, addr, A=None, X=None, Y=None, m=1, x=0, D=None, DB=0x7E, max_steps=3_000_000, long=True):
        """Run the routine at 24-bit addr until it returns (RTL if long else RTS)."""
        c = s.c
        c.M = m; c.XF = x
        if A is not None: c.A = A
        if X is not None: c.X = X
        if Y is not None: c.Y = Y
        if D is not None: c.D = D
        c.DB = DB
        c.S = 0x1F00
        if long: c.push8(0xFE); c.push16(0xFFFD)
        else: c.push16(0xFFFD)      # RTS returns to 0xFFFE
        c.PB = addr >> 16; c.PC = addr & 0xFFFF
        n = 0
        while not ((c.PB == 0xFE and c.PC == 0xFFFE) if long else (c.PC == 0xFFFE and c.PB == addr >> 16)):
            c.step(); n += 1
            if n > max_steps: raise RuntimeError('timeout at %02X:%04X' % (c.PB, c.PC))
        return n

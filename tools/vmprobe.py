"""Run real AI-VM handlers ($C1:251A) in the Python 65816 CPU with a synthetic object and script bytes.
library: init(rom); run_op(bytes, setup=None) -> dict(A, pc (new PC), w (WRAM writes))"""
import cpu65816 as cpu, struct
W = 0x7E0000
def init(rom):
    cpu.set_rom(rom)
def mk(script):
    c = cpu.CPU(); orig = c.rd8; ov = {}
    for pc, bs in script.items():
        for i, b in enumerate(bs): ov[0x104F15 + pc + i] = b
    def rd8(a, orig=orig):
        a &= 0xFFFFFF
        if a >> 16 == 0xD0 and (a & 0x3FFFFF) in ov: return ov[a & 0x3FFFFF]
        return orig(a)
    c.rd8 = rd8
    return c
def run_op(bytes_, Yb=0xE600, setup=None, maxsteps=50000, pc=0x100):
    c = mk({pc: bytes(bytes_)})
    c.wr16(W + Yb + 0x144, pc)
    if setup: setup(c)
    c.wlog = []
    c.PB = 0xC1; c.PC = 0x251A; c.Y = Yb; c.M = 0; c.XF = 0; c.DB = 0x7E; c.D = 0
    c.S = 0x1FF0; c.push16(0xFFFE)
    n = 0
    while not (c.PC == 0xFFFF and c.S == 0x1FF0):
        try: c.step()
        except Exception as e: return dict(err=str(e))
        n += 1
        if n > maxsteps: return dict(err='timeout')
    return dict(A=c.A, pc=c.rd16(W + Yb + 0x144), steps=c.steps,
                w=[(a, v) for a, v in c.wlog if (a >> 16) == 0x7E and 0xE000 <= (a & 0xFFFF) < 0xF800])

"""Floating damage/heal counter: run the REAL per-frame update $C1:833A (JSL $C0:EB7D / $C0:FBEA) after the REAL creation routine $C1:810E.
usage: damage_counter.py ROM STATE [value=25] [type=D0] [slot=0] [--csv]
type = value of E175/E04F: D0 HP damage, D8 HP heal, E0 MP damage, E8 MP heal.
Prints, per 60 Hz frame after creation: phase E11E, amplitude E11D, hold timer E11F, palette row, and the screen offset of every digit slot
(x relative to the creature x, y relative to the creature origin y, negative = up). Findings: docs/damage-counter.md."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, combat_env as ce

def s8(v): return v - 256 if v > 127 else v
def s16(v): return v - 65536 if v > 32767 else v

def run(rom, state, value, code, slot=0, max_frames=400):
    env = ce.Env(rom, state); c = env.c; w = c.wram
    def rts(cp):
        cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
    for a in (0xC1E0F9, 0x01E0F9): c.hooks[a] = rts       # wait-for-NMI DMA flush
    pal = []
    def cap(cp):
        pal.append(cp.A & 0xFF); return False
    c.hooks[0xC1859B] = cap                               # palette-row upload; A = row index
    X = slot * 0x200; B = 0xE000 + X
    w[0xF1] = 0; w[B + 0x4F] = code; w[0x1E] = value & 255; w[0x1F] = value >> 8
    env.call(0xC1810E, X=X, m=1, x=0, long=False)         # creation (event 1 of the combat tick)
    h = env.obj(slot); H = w[B + 0x74] & 0x7F
    rows = []
    for n in range(max_frames):
        pal.clear()
        env.call(0xC1833A, X=X, m=1, x=0, long=True)      # one 60 Hz update
        st = w[B + 0x60]
        e118 = s16(h.w(0x118)); e11a = s16(h.w(0x11A))
        ent = [(s8(w[B + 0xD0 + 4 * i]) + e118, s8(w[B + 0xD1 + 4 * i]) + e11a - H) for i in range(3)]
        rows.append(dict(n=n, state=st, pal=pal[-1] if pal else None, phase=w[B + 0x11E], step=w[B + 0x11C], amp=w[B + 0x11D],
                         hold=w[B + 0x11F], ent=ent, tiles=[w[B + 0xD2 + 4 * i] | w[B + 0xD3 + 4 * i] << 8 for i in range(3)]))
        if st == 0: break
    return rows

if __name__ == '__main__':
    rom = romio.rom_from_argv(); a = [x for x in sys.argv[1:] if not x.startswith('--')]
    state = a[0]; value = int(a[1]) if len(a) > 1 else 25
    code = int(a[2], 16) if len(a) > 2 else 0xD0; slot = int(a[3]) if len(a) > 3 else 0
    for r in run(rom, state, value, code, slot):
        print(r['n'], 'state=%02X' % r['state'], 'pal=' + ('%02X' % r['pal'] if r['pal'] is not None else '--'),
              'phase=%3d step=%3d amp=%2d hold=%3d' % (r['phase'], r['step'], r['amp'], r['hold']), r['ent'])

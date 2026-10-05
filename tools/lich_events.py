"""Timeline of one simulated Dark Lich run with spell-cast and projectile-spawn events.
usage: lich_events.py ROM STATE FRAMES [rng_index] [player_x player_y]"""
import sys, romio, lich_sim
rom = romio.rom_from_argv(); st = sys.argv[1]; frames = int(sys.argv[2])
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
s = lich_sim.Sim(rom, st, rng_index=seed)
if len(sys.argv) > 5:
    px, py = int(sys.argv[4]), int(sys.argv[5])
    for p in range(3):
        s.c.wr16(0x7EE000 + 0x200*p + 0x2B - 0x29 + 0x29 - 0x29 + 0, 0) if False else None
    for p in range(3):
        s.c.wr16(0x7EE000 + 0x200*p + 0x02, px); s.c.wr16(0x7EE000 + 0x200*p + 0x04, py)
s.spawn()
ev = []
def hook_cast(c):
    X = c.X
    ev.append((s.f, 'CAST spell=%02X (obj %04X)' % (c.rd8(0x7E0000 + X + 0x170), X)))
    return False
s.c.hooks[0xC2021B] = hook_cast
def hook_spawn(c):
    ev.append((s.f, 'PROJECTILE/child object spawn type=$A7:%02X dx=%d dy=%d' % (c.A & 0xFF, c.rd8(0x7E0000 + 0x200 + 0x95), 0))); return False
s.c.hooks[0xC233A4] = hook_spawn
last = None
for _ in range(frames):
    n0 = len(ev)
    s.frame(); sn = s.snapshot()
    key = (sn['state'], sn['seq'], sn['flags7e'])
    if key != last:
        ev.append((s.f, 'STATE %02X seq=%04X mode=%d $7E=%04X ad=%d pos=(%d,%d)' % (sn['state'], sn['seq'], sn['mode82'], sn['flags7e'], sn['ad'], sn['x'], sn['y']))); last = key
    for e in ev[n0:]:
        pass
for f, t in ev: print('f=%5d %6.2fs %s' % (f, f/60.0988, t))

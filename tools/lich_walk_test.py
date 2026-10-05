"""Place all players at a fixed position and watch the Lich (movement speed / hands phase choices).
usage: lich_walk_test.py ROM STATE PX PY FRAMES [rng_index]"""
import sys, romio, lich_sim
rom = romio.rom_from_argv(); st = sys.argv[1]
px, py, frames = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
s = lich_sim.Sim(rom, st, rng_index=seed)
for p in range(3):
    s.c.wr16(0x7EE000 + 0x200*p + 2, px); s.c.wr16(0x7EE000 + 0x200*p + 4, py)
s.spawn()
last = None; lastpos = None; lastf = 0
for _ in range(frames):
    s.frame(); sn = s.snapshot()
    key = (sn['state'], sn['seq'], sn['flags7e'])
    if key != last:
        print('f=%5d %6.2fs state=%02X seq=%04X mode=%d $7E=%04X ad=%d pos=(%d,%d)' % (s.f, s.f/60.0988, sn['state'], sn['seq'], sn['mode82'], sn['flags7e'], sn['ad'], sn['x'], sn['y'])); last = key

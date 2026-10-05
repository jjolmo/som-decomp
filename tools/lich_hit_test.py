"""Inject a 'hit' (obj+$34 bit0, consumed by $C2:0501) at chosen frames and log the Lich reaction.
usage: lich_hit_test.py ROM STATE"""
import sys, romio, lich_sim
rom = romio.rom_from_argv(); st = sys.argv[1]
def trial(hit_frames, total, label, seed=1):
    s = lich_sim.Sim(rom, st, rng_index=seed); s.spawn()
    print('---', label)
    last = None
    for _ in range(total):
        if s.f in hit_frames:
            s.w8(0x34, s.r8(0x34) | 1)
            print('   >>> hit injected at f=%d (state %02X mode %d)' % (s.f, s.r8(0x7A), s.r16(0x82)))
        s.frame(); sn = s.snapshot()
        key = (sn['state'], sn['seq'], sn['mode82'])
        if key != last:
            print('f=%5d t=%6.2fs state=%02X seq=%04X mode=%d $7E=%04X ad=%d thr=%d' % (s.f, s.f/60.0988, sn['state'], sn['seq'], sn['mode82'], sn['flags7e'], sn['ad'], sn['thr'])); last = key
trial({40}, 300, 'hit during body move state (mode 1)')
trial({128, 135}, 330, 'hit during body action (mode 0, f=126 starts action)')

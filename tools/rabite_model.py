"""Exact model of the first command the Rabite script issues from its main loop (script pc 0x0003), compared with the real handlers.
usage: rabite_model.py ROM STATE [N]
The model is written from the decoded script (docs/rabite.md); the check runs N AI steps ($C1:2552) per case with random RNG state and counts the
first command issued: (cmd, animation) with cmd C1 = hop (animation 0 = turn only, 1/2/4/5 = hops), 02 = attack swing. Output: expected vs measured fraction."""
import sys, os, random, collections
from fractions import Fraction as F
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_ops


def wander():
    d = collections.Counter()
    for anim in (4, 1, 2):
        d[('hop', anim)] += F(1, 3) * (F(1, 8) + F(7, 8) * F(4, 5))
    d[('hop', 0)] += F(7, 8) * F(1, 5)          # three turn-only commands in a row, first one counted
    return d


def model(band, gauge_ready):
    d = collections.Counter()
    for k, p in wander().items(): d[k] += F(1, 8) * p
    q = F(7, 8)
    if band == 'none':
        d.clear()
        for k, p in wander().items(): d[k] += p
        return d
    if band == 'le32':
        if gauge_ready:
            d[('hop', 0)] += q * F(3, 4); d[('hop', 5)] += q * F(1, 4)
        else:
            d[('hop', 5)] += q
    elif band == 'le48':
        d[('hop', 0)] += q
    elif band == 'le64':
        d[('hop', 0)] += q * F(1, 3); d[('hop', 2)] += q * F(2, 3)
    elif band == 'far':
        d[('hop', 0)] += q * F(1, 6); d[('hop', 2)] += q * F(5, 6)
    return d


BANDS = {'le32': 24, 'le48': 40, 'le64': 56, 'far': 90}


def main():
    rom = romio.rom_from_argv(); state = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    b = ai_ops.Bench(rom, state)
    o = b.o
    for band, dist in list(BANDS.items()) + [('none', None)]:
        for ready in ((True, False) if band == 'le32' else (True,)):
            if dist is None:
                b.h.sw(0x190, 0x0020)     # hero invalid: no valid target on screen
            else:
                b.h.sw(0x190, 0); b.place(dist)
            cnt = collections.Counter()
            for _ in range(n):
                b.reseed()
                o.sw(0x144, 3); o.sb(0x14F, 0); o.sb(0x1AC, 0xFF); o.sw(0x182, 20); o.sb(0x1ED, 0 if ready else 50)
                o.sw(0x148, 0xFFFF); o.sw(0x14A, 0xFFFF); o.sb(0x140, 0)
                b.env.call(0xC12552, X=0x600, m=1, x=0, long=False, DB=0x7E)
                cmd, anim = o.b(0x140), o.b(0x142)
                cnt[('swing', 0) if cmd == 2 else ('hop', anim) if cmd == 0xC1 else ('cmd%02X' % cmd, anim)] += 1
            exp = model(band, ready)
            print('band %-5s gauge_ready=%s' % (band, ready))
            for k in sorted(set(exp) | set(cnt), key=str):
                print('   %-12s expected %.4f  measured %.4f' % (k, float(exp.get(k, 0)), cnt.get(k, 0) / n))
    b.h.sw(0x190, 0)


if __name__ == '__main__':
    main()

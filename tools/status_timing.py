"""Status timers and damage over time: run the REAL per-actor combat tick $C0:3A79 (JSL $C0:002D) repeatedly on a hero with one status set.
usage: status_timing.py ROM STATE [timer_value=20]
Prints, per status word, the timer byte used, the number of tick calls until the status clears and the HP lost.
Findings (docs/rom-combat.md section 12): timers drop by 1 once every 4 tick calls (first drop on call 1), so a status with timer d lasts 4*d-3 calls;
poison (0x2000) and engulf (0x4000) cost 1 HP per timer drop and end when the next drop would bring HP to 0 (HP never goes below 1)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce
rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
d = int(sys.argv[3]) if len(sys.argv) > 3 else 20
GROUPS = [(0x0004, 0x1B2), (0x0010, 0x1B2), (0x0020, 0x1B2), (0x0040, 0x1B2), (0x0080, 0x1B3), (0x0100, 0x1B3), (0x0200, 0x1B5), (0x0400, 0x1B5),
          (0x0800, 0x1B5), (0x1000, 0x1B5), (0x2000, 0x1B6), (0x4000, 0x1B6)]
for st, off in GROUPS:
    env = ce.Env(rom, state); h = env.obj(0)
    for k in (1, 2): env.obj(k).sw(0x182, 0)
    h.sw(0x1AA, 0); h.sw(0x190, st); h.sw(0x1EE, st); h.sw(0x19E, st); h.sb(off, d); h.sb(0x1B9, 5)
    h.sw(0x182, 500); h.sw(0x184, 500)
    for f in (0x1F8, 0x1F1, 0x1F3, 0x1EC): h.sb(f, 0)
    cleared = None
    for n in range(1, 1000):
        env.call(0xC03A79, A=0, X=0, m=0, x=0, long=True)
        if cleared is None and not (h.w(0x190) & st):
            cleared = n; break
    print('status %04X timer E%03X=%d -> cleared after %s calls, HP %d -> %d' % (st, off, d, cleared if cleared else '>999 (no timer)', 500, h.w(0x182)))

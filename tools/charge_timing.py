"""Weapon charge timing: run the REAL charge routine $C0:B330 (one call = one pass of the per-frame input handler) and print
the call number at which each charge stage is reached.
usage: charge_timing.py ROM STATE [weapon_level=8]
Result (docs/rom-combat.md section 11.3): the gauge acts every 2nd call, 45 acts per stage, so stage s is reached at call 90*s-1."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce
rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
level = int(sys.argv[3]) if len(sys.argv) > 3 else 8
env = ce.Env(rom, state); h = env.obj(0)
for off in (0x2C, 0x1C, 0x61, 0x1F, 0x1A, 0x1B, 0x85, 0x1ED, 0x191, 0x19B): h.sb(off, 0)
h.sb(0x2C, 1)                    # human-controlled hero (E02C != 0): the cap is the weapon level E19C
h.sb(0x19C, level)
reached = {}
for call in range(1, 90 * (level + 1)):
    env.call(0xC0B330, A=1, m=1, x=1, long=False)
    st = h.b(0x19B)
    if st not in reached and st:
        reached[st] = call
print('weapon level', level, 'stage -> call number', reached)
print('seconds at 60 fps / 60.0988 Hz:', {k: (round(v / 60.0, 2), round(v / 60.0988, 2)) for k, v in reached.items()})

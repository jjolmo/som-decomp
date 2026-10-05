"""Run the REAL attack-row loader $C0:45D6 (JSL $C0:006C) for every boss-attack row id and compare the object fields it fills with data/boss_attacks.json.
usage: validate_boss_attacks.py ROM STATE [boss_attacks.json]"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce
rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
rows = json.load(open(sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), '..', 'data', 'boss_attacks.json')))['rows']
bad = 0
for r in rows:
    env = ce.Env(rom, state)
    env.call(0xC055EC, A=0x79, X=0x600, m=1, x=0)        # Dark Lich record as the owner (Str 74)
    o = env.obj(3)
    env.call(0xC045D6, A=r['id'], X=0x600, m=1, x=0, D=0x300)
    got = (o.w(0x194), o.b(0x197), o.b(0x198), o.w(0x199), o.b(0x1F7))
    exp = (r['flags'], r['accuracy'], (74 + r['power']) & 255, r['status'], r['status_chance'])
    if got != exp:
        bad += 1
        print('MISMATCH id', r['id'], 'got', got, 'expected', exp)
print('rows', len(rows), 'mismatches', bad)

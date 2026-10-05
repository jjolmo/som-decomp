"""Boss object records of the C2 boss engine and the attack rows / spells their state scripts use -> data/boss_records.json.
usage: boss_records.py ROM OUT.json [sim.jsonl ...]
Static part: the 15 native object records (pointer table $D0:BC34, records in bank C2), their handler pointers and, for every state script,
the attack row set through op 0x13 ($C0:006C), the spells (op 0x0E: low byte = spell id, bit8 = area, bit9 = own side) and projectile spawns (op 0x0F).
Optional dynamic part: JSON lines from boss_sim.py (attack rows / spells actually seen when the real engine runs), merged per boss id."""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statescript


def main():
    d = open(sys.argv[1], 'rb').read()
    u16 = lambda o: struct.unpack_from('<H', d, o)[0]
    ptrs = [u16(0x10BC34 + 2 * i) for i in range(15)]
    OPS = statescript.OPS

    def ops_of(addr):
        p = 0x20000 + addr; out = []
        while True:
            op = d[p]
            if op == 0xFF: break
            info = OPS.get(op)
            if not info: break
            name, n = info[0], info[1]
            if len(info) > 2: args = list(d[p + 1:p + 1 + n]); ln = 1 + n
            else: args = [u16(p + 1 + 2 * i) for i in range(n)]; ln = 1 + 2 * n
            out.append((name, args)); p += ln
            if name == 'JUMP': break
        return out

    records = []
    for i, rp in enumerate(ptrs):
        r = 0x20000 + rp
        w = lambda o: u16(r + o)
        table = w(0x10); ent = []; limit = 0xFFFF; k = 0
        while 0x20000 + table + 2 * k < 0x20000 + limit and k < 200:
            a = u16(0x20000 + table + 2 * k); ent.append(a); limit = min(limit, a); k += 1
        states = []
        rows = set(); spells = set(); spawns = set()
        for si, a in enumerate(ent):
            st = dict(state=si, attack_rows=[], spells=[], spawns=[])
            for name, args in ops_of(a):
                if name == 'C0_006C': st['attack_rows'].append(args[0]); rows.add(args[0])
                elif name == 'SPELL': st['spells'].append(dict(spell_id=args[0] & 0xFF, area=bool(args[0] & 0x100), own_side=bool(args[0] & 0x200))); spells.add(args[0])
                elif name == 'SPAWN': st['spawns'].append(list(args)); spawns.add(tuple(args))
            if st['attack_rows'] or st['spells'] or st['spawns']: states.append(st)
        records.append(dict(index=i, address='C2:%04X' % rp, flags=w(0), init=w(4), chooser=w(6), action=w(8), hurt=w(0xA), state_table='C2:%04X' % table,
                            attack_rows=sorted(rows), spells=[dict(spell_id=s & 0xFF, area=bool(s & 0x100), own_side=bool(s & 0x200)) for s in sorted(spells)],
                            states=states))
    obs = collections.defaultdict(lambda: dict(attack_rows=collections.Counter(), spells=collections.Counter(), objects=None, runs=0))
    for path in sys.argv[3:]:
        for line in open(path):
            if not line.startswith('{'): continue
            j = json.loads(line); o = obs[j['boss']]
            o['runs'] += 1; o['objects'] = j['objects']
            for k, v in j['attack_rows'].items(): o['attack_rows'][int(k)] += v
            for k, v in j['spells'].items(): o['spells'][int(k)] += v
    bosses = []
    init_to_rec = {rec['init']: rec['index'] for rec in records}
    for b in sorted(obs):
        o = obs[b]; init = int(o['objects'][0][3], 16) if o['objects'] else None
        bosses.append(dict(boss_id=b, flags_98=int(o['objects'][0][1], 16) if o['objects'] else None, init_handler=init, record_index=init_to_rec.get(init),
                           observed_attack_rows=dict(sorted(o['attack_rows'].items())), observed_spells=dict(sorted(o['spells'].items())), runs=o['runs']))
    json.dump(dict(source='records: pointer table 0x10BC34 (D0:BC34), bank C2; bosses: boss_sim.py runs (real engine, no heroes hit). attack row ids index data/boss_attacks.json; spell ids index data/spells.json',
                   records=records, bosses=bosses), open(sys.argv[2], 'w'), indent=1)
    open(sys.argv[2], 'a').write('\n')


if __name__ == '__main__':
    main()

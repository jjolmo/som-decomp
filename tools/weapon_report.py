"""Print markdown tables from data/weapons_melee.json (written by `weapon_report.py merge`).  No ROM needed.
usage: weapon_report.py merge OUT.json IN.json [IN.json ...]       combine per-weapon files written by weapon_attacks.py into one file keyed by weapon name
       weapon_report.py JSON WEAPON SECTION [args]                  sections: normal phase power tl structure pieces gauge hits shared
       weapon_report.py JSON WEAPON tl normal|power A B FACING      one attack as rows (A = variant, or stage; B = class)
Frames are video frames (60.0988 Hz); the hero advances its animation once per 5 frames (12.02 Hz).  The row/box helpers are those of tools/glove_report.py."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glove_report as GR

NAMES = {0: 'glove', 1: 'sword', 2: 'axe', 3: 'spear'}


def merge(out, ins):
    res = {'source': 'tools/weapon_attacks.py via tools/weapon_report.py merge: numbers measured by running the real game code (docs/weapons-melee.md)', 'weapons': {}}
    for p in ins:
        d = json.load(open(p))
        res['weapons'][NAMES[d['weapon_type']]] = d
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import glove_attacks as ga
    with open(out, 'w') as fh:
        ga.dump_json(res, fh)
        fh.write('\n')


def phase(d):
    ph = d['normal_runs']['by_press_phase']
    print('| `$56` at the press | frames until the first step | variant 0 | variant 1 | variant 2 | variant 3 |')
    print('|---|---|---|---|---|---|')
    for p in '01234':
        print('| %s | %d | %s |' % (p, ph[p]['0']['first_step_frame'], ' | '.join(str(ph[p][v]['swing_frames']) for v in '0123')))


def labels(d, facing='facing2'):
    s = d['structure'][facing]
    pieces = s['pieces']
    name = {}
    for v in range(4):
        name.setdefault(str(s['variants'][str(v)]['script']), 'N%d' % v)
    n = [0]
    def visit(ptr):
        k = str(ptr)
        if k in name:
            return
        name[k] = 'P%d' % n[0]; n[0] += 1
        for it in pieces[k]['seq']:
            if it[0] == 'c':
                visit(it[1])
    for v in range(4, 40):
        ptr = s['variants'][str(v)]['script']
        visit(ptr)
    return name


def steps_of(pieces, ptr):
    p = pieces[str(ptr)]
    return p['ticks'] + sum(steps_of(pieces, q) for q in p['calls'])


def structure(d, facing='facing2'):
    s = d['structure'][facing]
    pieces, name = s['pieces'], labels(d, facing)
    print('| animation | stage, class | total steps | items in order (steps) |')
    print('|---|---|---|---|')
    for v in list(range(4, 36)):
        ptr = s['variants'][str(v)]['script']
        top = pieces[str(ptr)]
        items = []
        for it in top['seq']:
            if it[0] == 't':
                items.append('own(%d)' % it[1])
            else:
                items.append('%s(%d)' % (name[str(it[1])], steps_of(pieces, it[1])))
        print('| %d | %s | %d | %s |' % (v, '%d, %s' % (v // 4, 'status target' if v % 4 == 3 else v % 4), s['variants'][str(v)]['total_steps'], ' '.join(items)))


def pieces_table(d, facing='facing2'):
    s = d['structure'][facing]
    pieces, name = s['pieces'], labels(d, facing)
    print('| piece | script address (bank $D1) | steps | sound ids | velocity presets k (vx, vy, vz of the table row; 128 = unchanged) | calls |')
    print('|---|---|---|---|---|---|')
    for k, nm in sorted(name.items(), key=lambda kv: (kv[1][0], int(kv[1][1:]))):
        p = pieces.get(k)
        if not p:
            continue
        snd = ' '.join('0x%X' % x for x in p['sounds']) or '-'
        pre = '; '.join('%d: %d,%d,%d' % tuple(x) for x in p['presets']) or '-'
        calls = ' '.join(name[str(q)] for q in p['calls']) or '-'
        print('| %s | `$D1:%04X` | %d | %s | %s | %s |' % (nm, p['addr'], steps_of(pieces, p['addr']), snd, pre, calls))


def shared(d):
    s = d['structure']['shared_scripts_facing2']
    seen = set()
    for v in range(40):
        g = tuple(s[str(v)])
        if g not in seen:
            seen.add(g)
            if len(g) > 1:
                print(g)


def gauge(d):
    print(json.dumps(d['gauge'], indent=1))


def hits(d):
    print(json.dumps(d['hits'], indent=1))


def main():
    if sys.argv[1] == 'merge':
        merge(sys.argv[2], sys.argv[3:])
        return
    path, weapon, sec = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.load(open(path))['weapons'][weapon]
    if sec == 'normal':
        GR.norm(d)
    elif sec == 'power':
        GR.power(d)
    elif sec == 'tl':
        kind, a, b, face = sys.argv[4:8]
        e = d['normal_runs']['slot0'][a][face] if kind == 'normal' else d['power']['slot0'][a][b][face]
        GR.timeline(e, '%s %s %s %s %s' % (weapon, kind, a, b, face))
    else:
        {'phase': phase, 'structure': structure, 'pieces': pieces_table, 'shared': shared, 'gauge': gauge, 'hits': hits}[sec](d)


if __name__ == '__main__':
    main()

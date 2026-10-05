"""Print markdown tables from data/weapons_ranged.json (written by `ranged_report.py merge`).  No ROM needed.
usage: ranged_report.py merge OUT.json IN.json [IN.json ...]     combine per-weapon files written by ranged_attacks.py into one file keyed by weapon name
       ranged_report.py JSON WEAPON SECTION [args]              sections: normal phase structure proj power gauge charge model hits probes
       ranged_report.py JSON WEAPON tl normal|power A B FACING   one attack as rows (A = animation id, or stage; B = class)
Frames are video frames (60.0988 Hz); the hero advances its animation once per 5 frames (12.02 Hz).  The row helpers are those of tools/glove_report.py."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glove_report as GR

HZ = 60.0988
NAMES = {4: 'whip', 5: 'bow', 6: 'boomerang', 7: 'javelin'}


def merge(out, ins):
    import glove_attacks as ga
    res = {'source': 'tools/ranged_attacks.py via tools/ranged_report.py merge: numbers measured by running the real game code (docs/weapons-ranged.md)', 'weapons': {}}
    for p in ins:
        d = json.load(open(p))
        w = res['weapons'].setdefault(NAMES[d['weapon_type']], {})
        for k, v in d.items():
            w[k] = v
    with open(out, 'w') as fh:
        ga.dump_json(res, fh)
        fh.write('\n')


def normal(d):
    print('| animation id | facing | swing end (frames after the press frame) | hero free again (E061 = 0) | first step | weapon box frames (first..last) | projectile first live frame | sound ids (id@frame) |')
    print('|---|---|---|---|---|---|---|---|')
    for v in '0123':
        for face in ('left', 'up'):
            e = d['normal_runs']['slot0'][v][face]
            sn = ', '.join('0x%X@%d' % (x['arg'][0], x['f']) for x in e['sounds'])
            pr = ', '.join(str(p['first_live_frame']) for p in e['projectiles']) or '-'
            print('| %s | %s | %d | %d | %d | %d (%s..%s) | %s | %s |' % (v, face, e['swing_end_frame'], e['ready_frame'], e['first_step_frame'], e['weapon_box_frames'], e['weapon_box_first'], e['weapon_box_last'], pr, sn))


def phase(d):
    ph = d['normal_runs']['by_press_phase']
    print('| `$56` at the press | frames until the first step | swing end | hero free again | projectile live from |')
    print('|---|---|---|---|---|')
    for p in '01234':
        e = ph[p]['0']
        print('| %s | %s | %s | %s | %s |' % (p, e['first_step_frame'], e['swing_frames'], e['ready_frame'], e['spawn_frame']))


def structure(d):
    s = d['structure']
    print('animation id -> script (side facing): ' + ', '.join('%s: %s' % (k, v) for k, v in s['shared_scripts_facing2'].items()))
    print()
    print('| script (facing_addr) | steps | shot steps | sounds (step, id) | other ops (step, bytes) |')
    print('|---|---|---|---|---|')
    for k, v in s['scripts'].items():
        print('| %s | %d | %s | %s | %s |' % (k, v['total_steps'], v['shot_steps'], v['sounds'], v['other_ops']))


def proj(d, face='left'):
    print('| stage | facing | swing end | hero free again | entry | delay (frames) | live from..to | dying from | spawn offset from hero (x, y, z) | speed byte | end offset (x, y, z) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for st in range(9):
        e = d['proj']['stage%d' % st][face]
        for p in e['projectiles']:
            print('| %d | %s | %d | %d | %d | %d | %d..%d | %s | %s | %d | %s |' % (st, face, e['swing_end_frame'], e['ready_frame'], p['entry'], p['delay_frames'], p['first_live_frame'], p['last_frame'],
                                                                               p['dying_from_frame'], tuple(p['spawn_offset_from_hero']), p['speed_param'], tuple(p['path_dx_dy_z'][-1])))


def power(d):
    GR.power(d)


def gauge(d):
    print(json.dumps(d['gauge'], indent=1))


def charge(d):
    print(json.dumps(d['charge'], indent=1))


def model(d):
    for k, v in d['model'].items():
        print(k, 'mismatches', v['mismatches'], 'of', len(v['rows_dx_dy_predicted_pred_sample_observed_obs_frame']), 'hits', v['hits_observed'], 'frame offsets', v['frame_offset_observed_minus_predicted'])


def hits(d):
    print(json.dumps(d['hits'], indent=1)[:20000])


def probes(d):
    print(json.dumps(d['probes'], indent=1))


def tl(d):
    args = sys.argv[3:]
    if args and args[0] == 'tl':
        args = args[1:]
    kind, a, b, face = args[0], args[1], args[2], args[3]
    e = d['normal_runs']['slot0'][a][face] if kind == 'normal' else d['power']['slot0'][a][b][face]
    GR.timeline(e, '%s %s %s %s' % (kind, a, b, face))


SECTIONS = {'normal': normal, 'phase': phase, 'structure': structure, 'proj': proj, 'power': power, 'gauge': gauge, 'charge': charge, 'model': model, 'hits': hits, 'probes': probes}


def main():
    if sys.argv[1] == 'merge':
        merge(sys.argv[2], sys.argv[3:])
        return
    d = json.load(open(sys.argv[1]))['weapons'][sys.argv[2]]
    name = sys.argv[3]
    if name == 'tl':
        tl(d)
    else:
        SECTIONS[name](d)


if __name__ == '__main__':
    main()

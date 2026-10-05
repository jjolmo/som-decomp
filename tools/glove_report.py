"""Print markdown tables from data/glove_attacks.json (written by glove_attacks.py).  No ROM needed.
usage: glove_report.py [data/glove_attacks.json] [section ...]      sections: normal gauge charge power
       glove_report.py data/glove_attacks.json tl normal|power A B FACING     one attack as rows (A = variant, or stage; B = class)
Frames are video frames (60.0988 Hz); the hero advances its animation once per 5 frames (12.02 Hz)."""
import sys, json

HZ = 60.0988


def sec(frames):
    return '%.3f' % (frames / HZ)


def boxes(segs):
    out = []
    for s in segs:
        if s[7] and s[8]:
            out.append((s[0], s[1], s[5], s[6], s[7], s[8]))
    return out


def norm(d):
    print('| variant | facing | steps | frames (s) | forward move px (frames) | weapon box first..last frame | weapon boxes (frame, n, centre x, y, w, h) | sound |')
    print('|---|---|---|---|---|---|---|---|')
    for v in '0123':
        for face in ('left', 'up'):
            e = d['normal_runs']['slot0'][v][face]
            moves = [(s[2] or s[3], s[1]) for s in e['segments'] if s[2] or s[3]]
            mv = ', '.join('%d px/f x %d' % (a, b) for a, b in moves) or '-'
            sn = ', '.join('0x%X@%d' % (x['arg'][0], x['f']) for x in e['sounds'])
            bx = '; '.join('%d,%d: %d,%d %dx%d' % b for b in boxes(e['segments']))
            print('| %s | %s | %d | %d (%s) | %s | %s..%s | %s | %s |' % (v, face, (e['swing_frames'] - e['first_tick_frame']) // 5, e['swing_frames'],
                  sec(e['swing_frames']), mv, e['weapon_box_first'], e['weapon_box_last'], bx, sn))


def gauge(d):
    g = d['gauge']
    print(json.dumps(g, indent=1))


def charge(d):
    print(json.dumps(d['charge'], indent=1))


def reach(e):
    """Union of the weapon boxes in world offsets from the hero's start position (hero moving included): [x_lo, x_hi, y_lo, y_hi]."""
    xs, ys = [], []
    for s in e['segments']:
        f, n, vx, vy, vz, wx, wy, ww, wh = s[:9]
        if not (ww and wh):
            continue
        px, py = s[13], s[14]
        for k in (0, n - 1):
            x = px + vx * k
            y = py + vy * k
            xs += [x + wx - ww / 2, x + wx + ww / 2]
            ys += [y + wy - wh / 2, y + wy + wh / 2]
    return [min(xs), max(xs), min(ys), max(ys)] if xs else None


def power(d):
    print('| stage | class | frames (s) | steps | move px (x, y) | max height | weapon box frames | first..last | box union x lo..hi, y lo..hi | sounds (id@frame) |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for st in '12345678':
        for cl in '012':
            e = d['power']['slot0'][st][cl]['left']
            sn = ' '.join('%X@%d' % (x['arg'][0], x['f']) for x in e['sounds'])
            r = reach(e)
            print('| %s | %s | %d (%s) | %d | %s | %d | %d | %s..%s | %s | %s |' % (st, cl, e['swing_frames'], sec(e['swing_frames']), (e['swing_frames'] - e['first_tick_frame']) // 5,
                  tuple(e['end_pos_nominal']), e['max_height'], e['weapon_box_frames'], e['weapon_box_first'], e['weapon_box_last'], r, sn))


def timeline(e, title=''):
    """Rows of (frames, velocity, weapon box, body) with consecutive rows of equal velocity and weapon box merged."""
    rows = []
    for s in e['segments']:
        f, n, vx, vy, vz, wx, wy, ww, wh, bx, by, bw, bh, px, py, hgt = s
        key = (vx, vy, vz, (wx, wy, ww, wh) if ww and wh else None, 'tangible' if bw and bh else 'intangible')
        if rows and rows[-1][0] == key:
            rows[-1][2] += n
        else:
            rows.append([key, f, n, px, py, hgt])
    print('%s end of state at frame %d (%s s), gauge set to %d' % (title, e['swing_frames'], sec(e['swing_frames']), e['gauge_after']))
    print()
    print('| frames | v px/frame (x, y, z) | weapon box (cx, cy, w, h) | hero body | hero offset at start (x, y), height |')
    print('|---|---|---|---|---|')
    for key, f, n, px, py, hgt in rows:
        v = key[:3]
        box = '%d, %d, %d, %d' % key[3] if key[3] else '-'
        print('| %d-%d | %s | %s | %s | %d, %d, %d |' % (f, f + n - 1, '%d, %d, %d' % v if any(v) else '0', box, key[4], px, py, hgt))


def tl(d):
    args = [a for a in sys.argv[2:] if a != 'tl']
    kind, a, b, face = args[0], args[1], args[2], args[3]
    if kind == 'normal':
        e = d['normal_runs']['slot0'][a][face]
    else:
        e = d['power']['slot0'][a][b][face]
    timeline(e, '%s %s %s %s' % (kind, a, b, face))


SECTIONS = {'tl': tl, 'normal': norm, 'gauge': gauge, 'charge': charge, 'power': power}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/glove_attacks.json'
    d = json.load(open(path))
    names = sys.argv[2:] or [k for k in SECTIONS if k != 'tl']
    for name in names[:1] if names and names[0] == 'tl' else names:
        print('##', name)
        SECTIONS[name](d)


if __name__ == '__main__':
    main()

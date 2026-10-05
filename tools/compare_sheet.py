"""Compare the frames written by rip_hero_anims.py with a public sprite sheet (a PNG you provide), pixel by pixel on the 5-bit colours (frames with fewer than 40 body pixels are skipped).
usage: compare_sheet.py SHEET.png OUTDIR hero [--vflip] [--recolour]     e.g.  compare_sheet.py boy_sheet.png out boy
  --groups prints the found / total pictures per animation id.
  --vflip also tries vertical flips (upside-down frames), --recolour retries failed frames under a consistent recolouring (counted separately; for flash palettes)
A frame matches when every opaque pixel of the PNG, apart from the colours of the effect palette (sprite palette 0, which cycles during the attacks), equals the sheet
pixel at some position, in the sheet's orientation or mirrored. The sheet's background colour is its most common colour. Standard library only (slow on big sheets)."""
import sys, os, json, glob, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx_decode as G


def q(r, g, b): return (r >> 3) << 10 | (g >> 3) << 5 | (b >> 3)


def load_sheet(path):
    im = G.read_png(path); px = im.px; w, h = im.w, im.h
    flat = [q(px[4 * i], px[4 * i + 1], px[4 * i + 2]) for i in range(w * h)]
    bg = collections.Counter(flat[::7]).most_common(1)[0][0]
    where = collections.defaultdict(list)
    for i, c in enumerate(flat):
        if c != bg: where[c].append(i)
    return flat, w, h, bg, where


def frame_pixels(path, drop):
    im = G.read_png(path); out = []
    for y in range(im.h):
        for x in range(im.w):
            o = 4 * (y * im.w + x)
            if im.px[o + 3]:
                c = q(im.px[o], im.px[o + 1], im.px[o + 2])
                if c not in drop: out.append((x, y, c))
    return out, im.w, im.h


def find(sheet, pixels, width, height=None):
    """True when every pixel is found in the sheet (same 5-bit colour) in one of the orientations: as is, mirrored, and (when `height` is given) flipped vertically / both."""
    flat, w, h, bg, where = sheet
    for fv in ((False, True) if height else (False,)):
        for mirrored in (False, True):
            pts = [((width - 1 - x) if mirrored else x, (height - 1 - y) if fv else y, c) for x, y, c in pixels]
            ax, ay, ac = min(pts, key=lambda p: len(where.get(p[2], ())))
            for pos in where.get(ac, ()):
                sx, sy = pos % w - ax, pos // w - ay
                if sx < 0 or sy < 0: continue
                if all(sx + x < w and sy + y < h and flat[(sy + y) * w + sx + x] == c for x, y, c in pts): return True, mirrored or fv
    return False, False


_NONBG = {}


def find_recoloured(sheet, pixels, width, height):
    """Shape match under a consistent recolouring (a function from the frame's colours to the sheet's colours): used for frames whose palette the game
    changes while they are drawn (flashes); reported separately from exact matches."""
    flat, w, h, bg, where = sheet
    nb = _NONBG.get(id(sheet))
    if nb is None: nb = _NONBG[id(sheet)] = [i for i, c in enumerate(flat) if c != bg]
    for fv in (False, True):
        for mirrored in (False, True):
            pts = sorted(((width - 1 - x) if mirrored else x, (height - 1 - y) if fv else y, c) for x, y, c in pixels)
            pts = sorted(pts, key=lambda p: (p[1], p[0]))
            ax, ay, _ = pts[0]
            sample = pts[::max(1, len(pts) // 10)]
            for pos in nb:
                sx, sy = pos % w - ax, pos // w - ay
                if sx < 0 or sy < 0: continue
                ok = True
                for x, y, c in sample:
                    X, Y = sx + x, sy + y
                    if X >= w or Y >= h or flat[Y * w + X] == bg: ok = False; break
                if not ok: continue
                m = {}
                for x, y, c in pts:
                    X, Y = sx + x, sy + y
                    if X >= w or Y >= h: ok = False; break
                    v = flat[Y * w + X]
                    if v == bg or m.setdefault(c, v) != v: ok = False; break
                if ok: return True
    return False


if __name__ == '__main__':
    vflip = '--vflip' in sys.argv; recol = '--recolour' in sys.argv; groups = '--groups' in sys.argv
    sys.argv = [a for a in sys.argv if not a.startswith('--')]
    tally = {}
    sheet = load_sheet(sys.argv[1]); d = os.path.join(sys.argv[2], sys.argv[3]); n = ok = empty = rec = 0; miss = []
    for jp in sorted(glob.glob(os.path.join(d, '*.json'))):
        j = json.load(open(jp)); drop = set()
        if 'frames' not in j: continue                  # index.json
        for fr in j['frames']:
            for v in fr['palettes'].get('obj_row_0', []):
                w16 = int(v, 16); drop.add((w16 & 31) << 10 | ((w16 >> 5) & 31) << 5 | (w16 >> 10) & 31)
        for fr in j['frames']:
            pix, width, height = frame_pixels(os.path.join(d, fr['file']), drop); n += 1
            if len(pix) < 40: empty += 1; continue
            good, _ = find(sheet, pix, width, height if vflip else None)
            if not good and recol: good = find_recoloured(sheet, pix, width, height); rec += good
            ok += good
            if not good: miss.append(fr['file'])
            if groups:
                g = re.match(r'[a-z]+', fr['file']).group(0) + ('' if not re.match(r'[a-z]+(\d+)', fr['file']) else re.match(r'[a-z]+(\d+)', fr['file']).group(1))
                gs = tally.setdefault(g, [0, 0, 0]); gs[0] += 1; gs[1] += bool(good); gs[2] += 0
    print('%d frames: %d match%s, %d with fewer than 40 body pixels (skipped), %d not found' % (n, ok, ' (%d of them only under a consistent recolouring)' % rec if recol else '', empty, len(miss)))
    print(miss[:40])
    if groups:
        print('per animation (frames, found):', ' '.join('%s=%d/%d' % (g, v[1], v[0]) for g, v in sorted(tally.items())))

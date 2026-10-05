"""Compare the frames written by rip_hero_anims.py with a public sprite sheet (a PNG you provide), pixel by pixel on the 5-bit colours (frames with fewer than 40 body pixels are skipped).
usage: compare_sheet.py SHEET.png OUTDIR hero      e.g.  compare_sheet.py boy_sheet.png out boy
A frame matches when every opaque pixel of the PNG, apart from the colours of the effect palette (sprite palette 0, which cycles during the attacks), equals the sheet
pixel at some position, in the sheet's orientation or mirrored. The sheet's background colour is its most common colour. Standard library only (slow on big sheets)."""
import sys, os, json, glob, collections
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
    return out, im.w


def find(sheet, pixels, width):
    flat, w, h, bg, where = sheet
    for mirrored in (False, True):
        pts = [((width - 1 - x) if mirrored else x, y, c) for x, y, c in pixels]
        ax, ay, ac = min(pts, key=lambda p: len(where.get(p[2], ())))
        for pos in where.get(ac, ()):
            sx, sy = pos % w - ax, pos // w - ay
            if sx < 0 or sy < 0: continue
            if all(sx + x < w and sy + y < h and flat[(sy + y) * w + sx + x] == c for x, y, c in pts): return True, mirrored
    return False, False


if __name__ == '__main__':
    sheet = load_sheet(sys.argv[1]); d = os.path.join(sys.argv[2], sys.argv[3]); n = ok = empty = 0; miss = []
    for jp in sorted(glob.glob(os.path.join(d, '*.json'))):
        j = json.load(open(jp)); drop = set()
        for fr in j['frames']:
            for v in fr['palettes'].get('obj_row_0', []):
                w16 = int(v, 16); drop.add((w16 & 31) << 10 | ((w16 >> 5) & 31) << 5 | (w16 >> 10) & 31)
        for fr in j['frames']:
            pix, width = frame_pixels(os.path.join(d, fr['file']), drop); n += 1
            if len(pix) < 40: empty += 1; continue
            good, _ = find(sheet, pix, width)
            ok += good
            if not good: miss.append(fr['file'])
    print('%d frames: %d match, %d with fewer than 40 body pixels (skipped), %d not found' % (n, ok, empty, len(miss)))
    print(miss[:40])

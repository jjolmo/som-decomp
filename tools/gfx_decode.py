"""SNES graphics helpers: 4bpp tile decoding, BGR555 palettes, OAM decoding, sprite rendering and a PNG writer (standard library only).
Nothing here reads the ROM; callers pass the byte buffers (VRAM, CGRAM, OAM) they captured. Output images are written by the callers, never into this repo.
library: decode_tile(vram, byte_addr) -> 8 rows of 8 colour indices   palette_rgba(cgram) -> 256 (r,g,b)
         oam_entries(oam544) -> list of dicts   render(entries, vram, cgram, ...) -> Image   write_png(path, img)"""
import zlib, struct


def decode_tile(buf, a):
    """One 8x8 tile in SNES 4bpp planar format: 32 bytes, bitplanes 0/1 interleaved in the first 16 bytes by row, planes 2/3 in the last 16."""
    rows = []
    for y in range(8):
        p0, p1, p2, p3 = buf[a + 2 * y], buf[a + 2 * y + 1], buf[a + 16 + 2 * y], buf[a + 17 + 2 * y]
        rows.append([((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1) | (((p2 >> (7 - x)) & 1) << 2) | (((p3 >> (7 - x)) & 1) << 3) for x in range(8)])
    return rows


def bgr555(v):
    return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)


def palette_rgba(cgram):
    """256 colours from a 512-byte CGRAM image (little-endian BGR555 words)."""
    return [bgr555(cgram[2 * i] | cgram[2 * i + 1] << 8) for i in range(256)]


def oam_entries(oam):
    """Decode the 544-byte OAM image: 128 x (x, y, tile, attr) + 32 bytes of (x bit 8, size) pairs. Returns dicts with signed x."""
    out = []
    for i in range(128):
        x, y, t, a = oam[4 * i:4 * i + 4]
        hb = oam[512 + (i >> 2)] >> ((i & 3) * 2)
        out.append(dict(i=i, x=x - 256 if hb & 1 else x, y=y, tile=t | (a & 1) << 8, pal=(a >> 1) & 7, prio=(a >> 4) & 3,
                        hflip=(a >> 6) & 1, vflip=(a >> 7) & 1, large=(hb >> 1) & 1))
    return out


class Image:
    def __init__(s, w, h):
        s.w, s.h, s.px = w, h, bytearray(4 * w * h)

    def put(s, x, y, rgb):
        if 0 <= x < s.w and 0 <= y < s.h:
            o = 4 * (y * s.w + x); s.px[o:o + 4] = bytes((rgb[0], rgb[1], rgb[2], 255))

    def get(s, x, y):
        o = 4 * (y * s.w + x); return bytes(s.px[o:o + 4])

    def bbox(s):
        xs = [x for y in range(s.h) for x in range(s.w) if s.px[4 * (y * s.w + x) + 3]]
        ys = [y for y in range(s.h) for x in range(s.w) if s.px[4 * (y * s.w + x) + 3]]
        return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None

    def crop(s, x0, y0, x1, y1):
        im = Image(x1 - x0, y1 - y0)
        for y in range(y0, y1):
            if 0 <= y < s.h:
                a, b = max(x0, 0), min(x1, s.w)
                if a < b: im.px[4 * ((y - y0) * im.w + a - x0):4 * ((y - y0) * im.w + b - x0)] = s.px[4 * (y * s.w + a):4 * (y * s.w + b)]
        return im


def render(entries, vram, cgram, obj_base=0x6000, name_gap=0x1000, small=16, large=32, size=(256, 224), pal_base=128):
    """Draw OAM entries (lower index on top) into a transparent image.
    obj_base / name_gap are VRAM WORD addresses from OBJSEL ($2101): first name table and distance to the second one; small/large are the two sprite sizes."""
    img = Image(*size); pal = palette_rgba(cgram)
    for e in sorted(entries, key=lambda e: -e['i']):
        S = large if e['large'] else small
        y = e['y']
        if y >= 224 and y + S <= 256: continue
        if y >= 224: y -= 256
        n = S // 8
        for ty in range(n):
            for tx in range(n):
                sx = n - 1 - tx if e['hflip'] else tx; sy = n - 1 - ty if e['vflip'] else ty
                tn = (e['tile'] & 0x100) | (((e['tile'] & 0xFF) + sy * 16 + sx) & 0xFF)
                a = ((obj_base + (tn & 0xFF) * 16 + (tn >> 8) * name_gap) * 2) & 0xFFFF
                rows = decode_tile(vram, a)
                for yy in range(8):
                    for xx in range(8):
                        c = rows[yy][xx]
                        if c:
                            img.put(e['x'] + tx * 8 + (7 - xx if e['hflip'] else xx), y + ty * 8 + (7 - yy if e['vflip'] else yy), pal[pal_base + e['pal'] * 16 + c])
    return img


def write_png(path, img):
    raw = b''.join(b'\x00' + bytes(img.px[4 * y * img.w:4 * (y + 1) * img.w]) for y in range(img.h))
    def chunk(t, d): c = struct.pack('>I', len(d)) + t + d; return c + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', img.w, img.h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def read_png(path):
    """Minimal reader for the 8-bit RGBA PNGs written above and for ordinary non-interlaced 8-bit RGB/RGBA/palette files (used by the validation step)."""
    d = open(path, 'rb').read(); p = 8; idat = b''; plte = trns = None
    while p < len(d):
        n, t = struct.unpack('>I4s', d[p:p + 8]); body = d[p + 8:p + 8 + n]; p += 12 + n
        if t == b'IHDR': w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', body)
        elif t == b'PLTE': plte = body
        elif t == b'tRNS': trns = body
        elif t == b'IDAT': idat += body
    assert bd == 8 and il == 0 and ct in (3, 2, 6), 'unsupported PNG'
    bpp = {3: 1, 2: 3, 6: 4}[ct]; raw = zlib.decompress(idat); st = w * bpp; img = Image(w, h); prev = bytearray(st); o = 0
    for y in range(h):
        f = raw[o]; line = bytearray(raw[o + 1:o + 1 + st]); o += 1 + st
        for i in range(st):
            a = line[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        for x in range(w):
            if ct == 3:
                k = line[x]; rgb = plte[3 * k:3 * k + 3]; al = trns[k] if trns and k < len(trns) else 255
                px = (rgb[0], rgb[1], rgb[2], al)
            elif ct == 2: px = (line[3 * x], line[3 * x + 1], line[3 * x + 2], 255)
            else: px = tuple(line[4 * x:4 * x + 4])
            img.px[4 * (y * w + x):4 * (y * w + x) + 4] = bytes(px)
    return img

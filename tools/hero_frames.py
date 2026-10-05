"""Static decoder of the hero animation tables (no emulation): weapon row -> animation script -> frame -> sprite pieces and 8x8 tile sources.
usage: hero_frames.py ROM hero weapon_row anim dir        prints the script start and the frames of the script entries that follow
       hero_frames.py ROM check DIR                       compares every frame in the JSON files written by rip_hero_anims.py (DIR/<hero>/*.json) with this decoder
hero: boy girl sprite   dir: up down side (0 1 2)   formats are documented in docs/graphics.md section 5. The first form stops at the first script operation (their arguments are not decoded).
Tables read (file offset = (bank - 0xC0) << 16 | address): weapon rows D0:1000, frame-table bases D0:FFD0, scripts and frame descriptors in bank D1, piece lists in bank D2."""
import sys, os, json, struct, romio

HERO = dict(boy=dict(slot=0, lists=0x000, pool=(0xD5, 0x0000)), girl=dict(slot=1, lists=0x200, pool=(0xD5, 0x8000)), sprite=dict(slot=2, lists=0x400, pool=(0xD6, 0x0000)))
SCRIPT_BASE, SCRIPT_STRIDE = 0x3040, 240        # attack script pointer table of weapon type g: D1:3040 + 240*g, then (anim*3 + dir)*2   [runtime values of obj+0x65/+0x77]


def off(bank, a): return ((bank - 0xC0) << 16) | (a & 0xFFFF)
def w16(rom, bank, a): return struct.unpack_from('<H', rom, off(bank, a))[0]
def sext7(v): return v - 128 if v & 0x40 else v


def weapon_type(rom, row): return rom[0x101000 + 12 * row]


def script_ptr(rom, wtype, anim, d): return w16(rom, 0xD1, SCRIPT_BASE + SCRIPT_STRIDE * wtype + (anim * 3 + d) * 2)


def frame(rom, hero, wtype, idx, entry_flags=0, left=False):
    """Pieces of frame `idx` (script entry byte 1). entry_flags = script entry byte 0, left = actor mirrored (+0x10 bit 7).
    Returns dict(count, flips, pieces=[(x, y, hflip, vflip, tile_source_offsets)]) with x, y relative to the actor position minus the body height."""
    base = struct.unpack_from('<H', rom, 0x10FFD0 + 2 * wtype)[0]
    desc = w16(rom, 0xD1, base + 2 * idx); lo, hi = desc & 0xFF, desc >> 8
    a = entry_flags ^ (0x20 if left else 0)
    flips = (lo ^ (a << 1)) & 0xC0
    p = w16(rom, 0xD2, HERO[hero]['lists'] + 2 * hi)
    hdr = rom[off(0xD2, p)]; n = (hdr & 15) or 1; q = p + 1; src = []
    while len(src) < 4 * n:
        w = w16(rom, 0xD2, q); q += 2; s = (w << 1) & 0x7FE0
        if w & 0x8000: src += [s + 0x20 * k for k in range((w & 15) + 1)] if w & 0x4000 else [s] * ((w & 15) + 1)
        else: src.append((w & 0x3FF0) << 1)
    src = src[:4 * n]; pcs = []
    for k in range(n):
        g = w16(rom, 0xD2, q); q += 2; glo, ghi = g & 0xFF, g >> 8
        y, x = sext7(glo & 0x7F), sext7(ghi & 0x7F)
        if flips & 0x40: x = -x - 16
        if flips & 0x80: y = -y - 16
        pcs.append((x, y, (ghi >> 7) ^ (flips >> 6 & 1), flips >> 7 & 1, src[4 * k:4 * k + 4]))
    return dict(header=hdr, count=n, flips=flips, pieces=pcs)


def check(rom, d):
    """Compare with the recorded frames: piece count, positions (JSON dy = y - body height - jump height) and flip bits of the list-0x90 pieces."""
    ok = bad = 0
    for hero in HERO:
        hp = os.path.join(d, hero)
        if not os.path.isdir(hp): continue
        for fn in sorted(os.listdir(hp)):
            if not fn.endswith('.json'): continue
            j = json.load(open(os.path.join(hp, fn)))
            for st in j['script_steps']:
                vf = st['start_frame']; i = j['per_frame']['file_index'][vf]; fr = j['frames'][i]
                b0 = rom[off(0xD1, int(st['script_pos'], 16) - 2)]
                dec = frame(rom, hero, j['weapon_type'], st['frame_idx'], b0, fr['facing'] & 0x80 != 0)
                rec = [p for p in fr['pieces'] if p['list'] == '90']
                body = j['body_offset'] + j['per_frame']['jump_height'][vf]
                got = [(p[0], p[1] - body, p[2], p[3]) for p in dec['pieces']]
                want = [(p['dx'], p['dy'], p['hflip'], p['vflip']) for p in rec]
                if got == want: ok += 1
                else:
                    bad += 1
                    if bad <= 5: print('MISMATCH', hero, fn, st, got, want)
    print('frames checked: %d match, %d differ' % (ok, bad))


if __name__ == '__main__':
    rom = romio.rom_from_argv()
    if sys.argv[1] == 'check': check(rom, sys.argv[2])
    else:
        hero, row, anim, d = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), {'up': 0, 'down': 1, 'side': 2}.get(sys.argv[4], None)
        d = int(sys.argv[4]) if d is None else d; t = weapon_type(rom, row); p = script_ptr(rom, t, anim, d)
        print('weapon row %d -> type %d, script of anim %d dir %d at D1:%04X' % (row, t, anim, d, p))
        print(' '.join('%02X' % b for b in rom[off(0xD1, p):off(0xD1, p) + 24]), '...')
        for k in range(0, 16, 2):
            b0, idx = rom[off(0xD1, p + k)], rom[off(0xD1, p + k + 1)]
            if b0 & 0x80: break
            f = frame(rom, hero, t, idx, b0)
            print('entry %02X %02X: ticks=%d frame %d flips %02X header %02X' % (b0, idx, (b0 & 7 if b0 & 7 < 4 else 0) + 1, idx, f['flips'], f['header']))
            for pc in f['pieces']: print('   piece x=%d y=%d hflip=%d vflip=%d tiles=%s' % (pc[0], pc[1], pc[2], pc[3], ' '.join('%04X' % s for s in pc[4])))

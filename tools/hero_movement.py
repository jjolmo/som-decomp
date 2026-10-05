"""Hero movement: feed the pad bytes to the real per-frame routines and record the position of a hero.
usage: hero_movement.py ROM STATE [OUT.json]

Per frame the harness runs, in the order of the main loop ($C0:B070-B0D0): the input handler $C0:B69C (pad bytes $42-$47 -> velocity
word E006 of the controlled hero), the movement routine $C0:D5C0 (velocity -> position E002/E004, with the tile collision) and the
object step dispatcher $C0:B0D3 (combat tick of the hero, animation state; $56 cycles 0..4).  The frame wait of the scene routine
$01:E0F9 is replaced by a return.  The controlled hero, the tile map around it and the tile attribute entries are rewritten by the
harness, so the STATE only has to be a ZSNES save state taken on a map (same requirements as the other tools).
Documented in docs/hero-movement.md."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, combat_env as ce

FRAME_HZ = 60.0988
ATTR = 0x10000 + 0xB800            # $7F:B800 tile attribute entries, 4 bytes per tile id
MAP = 0x10000                      # $7F:0000 tile id map, 128 entries per row, 16 px tiles
FLOOR, WALL_ID, SOLID = 0, 250, (19, 6, 0, 0)


def rts(cp):
    cp.PC = (cp.pull16() + 1) & 0xFFFF
    return True


class Rig:
    def __init__(self, rom, state, hero=0, x=None, y=None, region=10):
        self.env = ce.Env(rom, state)
        c = self.env.c
        c.hooks[0x01E0F9] = rts
        self.hero = hero
        h = self.env.obj(hero)
        x = h.w(2) if x is None else x
        y = h.w(4) if y is None else y
        for k in range(3):
            self.env.obj(k).sb(0x2C, 0)
        h.sb(0x2C, 1)
        c.wram[0xD9] = 1 << hero; c.wram[0xDA] = 0; c.wram[0xDB] = 0
        for a in (0xF1, 0xFF, 0xD0, 0x52, 0xE2, 0xE8):
            c.wram[a] = 0
        c.wram[0xED] = 0x80
        c.wram[ATTR:ATTR + 4] = bytes((16, 0, 0, 0)); c.wram[ATTR + WALL_ID * 4:ATTR + WALL_ID * 4 + 4] = bytes(SOLID)
        self.tx, self.ty = x >> 4, y >> 4
        self.fill(lambda a, b: False, region)
        for off in (0x190, 0x191, 0x1B0, 0x1B1, 0x1B4, 0x1B2, 0x1B3, 0x1B5, 0x1B6, 0x1F1, 0x1F2, 0x1F3, 0x1F4, 0x1F5, 0x1F6, 0x1A, 0x1B, 0x1C, 0x60, 0x61, 0x0A, 0x1ED):
            h.sb(off, 0)
        h.sw(0x1EE, 0); h.sw(0x19E, 0); h.sw(0x1AA, 0); h.sb(0x19C, 8)      # weapon level 8: the charge gauge only runs for a weapon level above 0
        h.sw(2, x); h.sw(4, y); h.sb(0x10, 1)
        c.wram[0x56] = 0
        self.h = h

    def fill(self, wallfn, region=10):
        w = self.env.c.wram
        for ty in range(self.ty - region, self.ty + region + 1):
            for tx in range(self.tx - region, self.tx + region + 1):
                w[MAP + ty * 128 + tx] = WALL_ID if wallfn(tx, ty) else FLOOR

    def place(self, x, y):
        self.h.sw(2, x); self.h.sw(4, y)

    def frame(self, hi=0, lo=0, objstep=True):
        c = self.env.c
        f4 = (c.wram[0xF4] | c.wram[0xF5] << 8) + 1                      # the NMI handler increments the frame counter $F4 once per frame
        c.wram[0xF4] = f4 & 255; c.wram[0xF5] = (f4 >> 8) & 255
        c.wram[0x42] = lo; c.wram[0x43] = hi
        self.env.call(0xC0B69C, m=1, x=0, D=0, long=False)
        self.env.call(0xC0D5C0, m=1, x=0, D=0, long=False)
        if objstep: self.env.call(0xC0B0D3, m=1, x=0, D=0, long=False, max_steps=5_000_000)
        c.wram[0x56] = (c.wram[0x56] + 1) % 5

    def pos(self): return (self.h.w(2), self.h.w(4))

    def run(self, hi, n, lo=0, objstep=True):
        p = [self.pos()]
        for _ in range(n):
            self.frame(hi, lo, objstep); p.append(self.pos())
        return p


def deltas(p): return [[p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]] for i in range(len(p) - 1)]


PAD = dict(right=0x01, left=0x02, down=0x04, up=0x08)
DIRS = {'right': 0x01, 'left': 0x02, 'down': 0x04, 'up': 0x08, 'up+right': 0x09, 'up+left': 0x0A, 'down+right': 0x05, 'down+left': 0x06}


def walk_table(rom, state, hero):
    out = {}
    for name, hi in DIRS.items():
        r = Rig(rom, state, hero)
        p = r.run(hi, 12)
        out[name] = dict(per_frame=deltas(p)[:6], E006_after_frame1='0x%04X' % r.h.w(6), facing_E010='0x%02X' % r.h.b(0x10), anim_E011=r.h.b(0x11))
    r = Rig(rom, state, hero)
    p = r.run(0x01, 10) + r.run(0x00, 4)[1:]
    out['release_after_10_frames'] = deltas(p)[8:14]
    return out


def status_table(rom, state, hero):
    out = {}
    for b in range(16):
        word = 1 << b
        r = Rig(rom, state, hero)
        h = r.h
        h.sw(0x190, word); h.sw(0x19E, word); h.sw(0x1EE, word & 0xFFFC)
        for t in (0x1B2, 0x1B3, 0x1B5, 0x1B6, 0x1B4): h.sb(t, 255)
        p = r.run(0x01, 14)
        d = [x for x, _ in deltas(p)]
        out['0x%04X' % word] = d
    return out


def charge(rom, state, hero):
    out = {}
    r = Rig(rom, state, hero)
    log = []
    for i in range(200):
        r.frame(0x81 if i >= 1 else 0x01)
        log.append((i, r.h.b(0x1A), r.h.b(0x1B), r.h.b(0x19B)))
    p = Rig(rom, state, hero)
    pp = p.run(0x01, 1)
    pos = [p.pos()]
    seq = []
    for i in range(1, 100):
        p.frame(0x81); seq.append(p.pos()[0] - pos[-1][0]); pos.append(p.pos())
    out['hold_B_and_right_first_frames'] = seq[:10]
    out['hold_B_counter_E01A_by_frame'] = [x[1] for x in log[:8]]
    out['stage_E01B_reached_at_frame'] = next((i for i, a, b, s in log if b >= 1), None)
    for e1a, e1b in ((0, 0), (1, 0), (0, 1), (1, 1), (44, 8)):
        q = Rig(rom, state, hero); q.h.sb(0x1A, e1a); q.h.sb(0x1B, e1b)
        out['direct E01A=%d E01B=%d (no button)' % (e1a, e1b)] = [x for x, _ in deltas(q.run(0x01, 6, objstep=False))]
    return out


def buttons(rom, state, hero):
    out = {}
    for name, hi, lo in [('B', 0x81, 0), ('Y', 0x41, 0), ('Select', 0x21, 0), ('Start', 0x11, 0), ('A held without a press edge', 0x01, 0x80), ('X', 0x01, 0x40), ('L', 0x01, 0x20), ('R', 0x01, 0x10)]:
        r = Rig(rom, state, hero)
        out[name] = [x for x, _ in deltas(r.run(hi, 8, lo))]
    return out


def dash(rom, state, hero):
    """the A button (bit 7 of the low pad byte): the press-edge latch $CC bit 7 starts a run at 3 px per frame ($02:B6CD)"""
    def seq(script, setup=None, region=14):
        r = Rig(rom, state, hero, region=region)
        if setup: setup(r)
        h, c = r.h, r.env.c
        out = []; prev = r.pos()
        for n, hi, lo, latch in script:
            for k in range(n):
                if latch and k == 0: c.wram[0xCC] = 0x80          # what the NMI edge detector ($C0:93F7-9411) stores for a new A press
                r.frame(hi, lo)
                p = r.pos(); out.append((p[0] - prev[0], p[1] - prev[1], h.b(0x11), h.b(0x1ED))); prev = p
        return out
    res = {}
    for name, hi in DIRS.items():
        o = seq([(3, hi, 0, False), (8, hi, 0x80, True)])
        res[name] = dict(before=[[a, b] for a, b, _, _ in o[:3]], dash=[[a, b] for a, b, _, _ in o[3:8]], anim_E011=o[4][2])
    o = seq([(3, 0x04, 0, False), (3, 0, 0, False), (8, 0, 0x80, True)])
    res['from standstill facing down'] = [[a, b] for a, b, _, _ in o[6:12]]
    o = seq([(2, 0x01, 0, False), (8, 0x01, 0x80, True), (8, 0x08, 0x80, False)])
    res['right then up pressed while A held'] = [[a, b] for a, b, _, _ in o[2:18]]
    o = seq([(2, 0x01, 0, False), (6, 0x01, 0x80, True), (10, 0x01, 0, False)])
    res['release A'] = dict(per_frame=[[a, b] for a, b, _, _ in o[2:16]], E1ED=[e for *_, e in o[2:16]])
    for agi in (1, 50, 99):
        def sa(r, agi=agi): r.h.sb(0x189, agi)
        o = seq([(2, 0x01, 0, False), (3, 0x01, 0x80, True), (3, 0x01, 0, False)], setup=sa)
        res['recharge E1ED after releasing A, Agi %d' % agi] = o[-1][3]
    o = seq([(2, 0x01, 0, False), (4, 0x01, 0x80, True), (3, 0x01, 0, False), (4, 0x01, 0x80, True)])
    res['second A press during the recharge'] = [[a, b] for a, b, _, _ in o[:13]]
    def slowed(r): r.h.sw(0x190, 4); r.h.sw(0x19E, 4); r.h.sw(0x1EE, 4); [r.h.sb(t, 255) for t in (0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6)]
    res['with status 0x0004'] = [[a, b] for a, b, _, _ in seq([(2, 0x01, 0, False), (8, 0x01, 0x80, True)], setup=slowed)[:8]]
    def charging(r): r.h.sb(0x1B, 1)
    res['with charge stage 1'] = [[a, b] for a, b, _, _ in seq([(2, 0x01, 0, False), (8, 0x01, 0x80, True)], setup=charging)[:8]]
    def wallfn(r):
        tx = r.tx
        r.fill(lambda a, b: a >= tx + 4)
    o = seq([(2, 0x01, 0, False), (30, 0x01, 0x80, True)], setup=wallfn)
    res['into a wall 4 tiles away'] = [[a, b] for a, b, _, _ in o[:26]]
    return res


def blockers(rom, state, hero):
    """actor fields that stop the pad from steering the hero, with the combat/animation step off (pad -> E006 -> position only)"""
    out = {}
    for name, off, val in (('E01C=0x20', 0x1C, 0x20), ('E01C=0x80', 0x1C, 0x80), ('E060=0x40', 0x60, 0x40), ('E00A=5', 0x0A, 5), ('E1ED=40 (weapon gauge)', 0x1ED, 40), ('E061=1', 0x61, 1)):
        r = Rig(rom, state, hero)
        r.h.sb(off, val)
        out[name] = [x for x, _ in deltas(r.run(0x01, 8, objstep=False))]
    r = Rig(rom, state, hero)
    r.h.sb(0x1C, 0x20)
    for _ in range(4): r.frame(0x01, objstep=False)
    r.h.sb(0x1C, 0)
    out['E01C cleared after 4 frames: next frames'] = [x for x, _ in deltas(r.run(0x01, 4, objstep=False))]
    return out


def wall_box(rom, state, hero):
    """stop positions in front of a solid tile column/row, both pixel parities, and the single-tile scans that give the probe points"""
    res = {}
    for name, hi, dx, dy in (('right', 0x01, 1, 0), ('left', 0x02, -1, 0), ('down', 0x04, 0, 1), ('up', 0x08, 0, -1)):
        stops = []
        for par in (0, 1):
            r = Rig(rom, state, hero, region=10)
            x0, y0 = r.pos()
            tx, ty = r.tx, r.ty
            if dx > 0: r.fill(lambda a, b: a >= tx + 4)
            if dx < 0: r.fill(lambda a, b: a <= tx - 4)
            if dy > 0: r.fill(lambda a, b: b >= ty + 4)
            if dy < 0: r.fill(lambda a, b: b <= ty - 4)
            r.place(x0 + (par if dx else 0), y0 + (par if dy else 0))
            p = r.run(hi, 60, objstep=False)
            stops.append(p[-1])
        edge = {'right': (r.tx + 4) * 16, 'left': (r.tx - 4 + 1) * 16, 'down': (r.ty + 4) * 16, 'up': (r.ty - 4 + 1) * 16}[name]
        res[name] = dict(wall_edge_pixel=edge, stop_even=stops[0], stop_odd=stops[1])
    # single tile scans
    r0 = Rig(rom, state, hero)
    x0, y0 = r0.pos(); tx0, ty0 = r0.tx, r0.ty
    horiz = []
    for d in range(-8, 24):
        r = Rig(rom, state, hero)
        r.fill(lambda a, b: (a, b) == (tx0 + 3, ty0))
        r.place(tx0 * 16 + 12, ty0 * 16 + d)
        p = r.run(0x01, 40, objstep=False)
        horiz.append((d, p[-1][0] - (tx0 * 16 + 12)))
    vert = []
    for d in range(-8, 24):
        r = Rig(rom, state, hero)
        r.fill(lambda a, b: (a, b) == (tx0, ty0 + 3))
        r.place(tx0 * 16 + d, ty0 * 16 + 4)
        p = r.run(0x04, 40, objstep=False)
        vert.append((d, p[-1][1] - (ty0 * 16 + 4)))
    res['single_tile_walk_right_y_offset_in_tile_vs_x_progress'] = horiz
    res['single_tile_walk_down_x_offset_in_tile_vs_y_progress'] = vert
    return res


def slide(rom, state, hero):
    out = {}
    cases = (('wall to the right, up+right', 0x09, lambda tx, ty: (lambda a, b: a >= tx + 2)),
             ('wall above, up+right', 0x09, lambda tx, ty: (lambda a, b: b <= ty - 2)),
             ('wall to the right and above, up+right', 0x09, lambda tx, ty: (lambda a, b: a >= tx + 2 or b <= ty - 2)))
    for name, hi, mk in cases:
        r = Rig(rom, state, hero)
        r.fill(mk(r.tx, r.ty))
        out[name] = deltas(r.run(hi, 14, objstep=False))
    r0 = Rig(rom, state, hero)
    tx0, ty0 = r0.tx, r0.ty
    for d in (3, 13):
        r = Rig(rom, state, hero)
        r.fill(lambda a, b: (a, b) == (tx0 + 4, ty0))
        r.place(tx0 * 16 + 12, ty0 * 16 + d)
        out['single tile corner, walk right, y offset %d in tile' % d] = deltas(r.run(0x01, 34, objstep=False))[16:30]
    return out


def tile_codes(rom, state, hero):
    out = {}
    def blocked(entry):
        r = Rig(rom, state, hero)
        w = r.env.c.wram
        w[ATTR + 251 * 4:ATTR + 251 * 4 + 4] = bytes(entry)
        tx = r.tx
        for ty in range(r.ty - 10, r.ty + 11):
            for t in range(tx + 3, tx + 11): w[MAP + ty * 128 + t] = 251
        x0 = r.pos()[0]
        return r.run(0x01, 24, objstep=False)[-1][0] - x0
    for name, mk in (('byte0', lambda b: (b, 0, 0, 0)), ('byte1', lambda b: (16, b, 0, 0)), ('byte2', lambda b: (16, 0, b, 0))):
        m = {b: blocked(mk(b)) for b in range(256)}
        out[name + '_sweep_px_moved_of_48_free'] = {str(b): v for b, v in m.items() if v != 48}
        out[name + '_values_that_stop_the_hero'] = [b for b, v in m.items() if v < 40]
    return out


def ground(rom, state, hero):
    out = {}
    for b2 in list(range(0x20, 0x50)):
        row = {}
        for name, hi in (('idle', 0), ('right', 0x01), ('down', 0x04)):
            r = Rig(rom, state, hero)
            w = r.env.c.wram
            w[ATTR + 251 * 4:ATTR + 251 * 4 + 4] = bytes((16, 0, b2, 0))
            for ty in range(r.ty - 10, r.ty + 11):
                for t in range(r.tx - 10, r.tx + 11): w[MAP + ty * 128 + t] = 251
            p = r.run(hi, 16)
            row[name] = [p[-1][0] - p[0][0], p[-1][1] - p[0][1]]
        out['0x%02X' % b2] = row
    return out


def knockback(rom, state, hero):
    out = {}
    def hit(face, ax, ay):
        r = Rig(rom, state, hero)
        env, c, h = r.env, r.env.c, r.h
        env.call(0xC055EC, A=0x12, X=0x600, m=1, x=0)
        m = env.obj(3); m.sb(0, 1); m.sw(2, ax); m.sw(4, ay); m.sb(0x198, 60); m.sb(0x197, 99); h.sb(0x1A4, 0)
        x0, y0 = r.pos()
        m.sw(2, x0 + ax); m.sw(4, y0 + ay)
        h.sb(0x10, face)
        p = [r.pos()]
        for i in range(120):
            if i == 0: h.sb(0x59, 1)
            r.frame(0)
            p.append(r.pos())
        return p, h
    for face, nm in ((0, 'facing up'), (1, 'facing down'), (2, 'facing right'), (0x82, 'facing left')):
        for (ax, ay, an) in ((80, 0, 'attacker right'), (-80, 0, 'attacker left'), (0, -80, 'attacker above'), (0, 80, 'attacker below')):
            p, h = hit(face, ax, ay)
            d = deltas(p)
            mv = [i for i, (a, b) in enumerate(d) if a or b]
            out['%s, %s' % (nm, an)] = dict(displacement=[p[-1][0] - p[0][0], p[-1][1] - p[0][1]], moving_frames=[mv[0], mv[-1]] if mv else None, count=len(mv))
    p, h = hit(1, 80, 0)
    d = deltas(p)
    out['profile_facing_down_attacker_right_dy_per_frame'] = [b for a, b in d[:60]]
    return out


def main():
    rom = romio.load(sys.argv[1]); state = sys.argv[2]
    outp = sys.argv[3] if len(sys.argv) > 3 else None
    r0 = ce.Env(rom, state)
    hero = 0
    res = dict(source='numbers measured by running the real routines $C0:B69C, $C0:D5C0, $C0:B0D3; layout: docs/hero-movement.md',
               frame_hz=FRAME_HZ, hero_slot=hero)
    res['walk'] = walk_table(rom, state, hero); print('walk', json.dumps(res['walk'])[:600])
    res['buttons'] = buttons(rom, state, hero); print('buttons', res['buttons'])
    res['dash'] = dash(rom, state, hero); print('dash', json.dumps(res['dash'])[:700])
    res['status_words'] = status_table(rom, state, hero); print('status', res['status_words'])
    res['charge'] = charge(rom, state, hero); print('charge', res['charge'])
    res['blockers'] = blockers(rom, state, hero); print('blockers', res['blockers'])
    res['wall_box'] = wall_box(rom, state, hero); print('wall', {k: v for k, v in res['wall_box'].items() if k in ('right', 'left', 'down', 'up')})
    res['slide'] = slide(rom, state, hero); print('slide', res['slide'])
    res['tile_codes'] = tile_codes(rom, state, hero); print('tile codes', res['tile_codes'])
    res['ground_types'] = ground(rom, state, hero)
    res['knockback'] = knockback(rom, state, hero); print('knockback', res['knockback'])
    res['px_per_second'] = {k: round(v * FRAME_HZ, 2) for k, v in dict(one_px_per_frame=1, two_px_per_frame=2, three_px_per_frame=3, diagonal_2_2=(8 ** 0.5), run_3_px_per_frame=3, run_diagonal_3_3=(18 ** 0.5)).items()}
    if outp:
        json.dump(res, open(outp, 'w'), indent=1, sort_keys=True)
        print('wrote', outp)


if __name__ == '__main__':
    main()

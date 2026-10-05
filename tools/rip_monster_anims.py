"""Rip every animation of an ordinary monster (object ids 0-0x56) by letting the game draw it: the monster is created by the game's spawner in slot 3 of a
save state, its AI is switched off, and for every animation id and facing the state / animation bytes of the object are set and the real per-frame routine
plus the NMI handler (tile and palette uploads, OAM DMA) run; the OAM entries owned by the monster are rendered. Output goes to a directory chosen by the caller
(never into the repository).
usage: rip_monster_anims.py ROM STATE OUTDIR ID[,ID...] [--only ord,atk,hurt,death] [--dirs up,down,right,left] [--tile X,Y]
Animation sets (docs/monster-3.md section 13):
  ord<NN>    ordinary table (object-table entry bytes 5-6, bank $D1): animation NN, object state 0 (loops are recorded for one period)
  atk<NN>    attack table (entry bytes 7-8): object state 0x40 (pose) with animation NN, a one-shot script that ends by itself
  hurt<NN>   ordinary table animation NN played in object state 0x40 with animation id 0x80 | NN (the hit reactions use 0x88, 0x89: NN = 8, 9)
  swing<NN>  attack table animation NN played in object state 0x80 (the state a swing command sets)
  death      the monster is given lethal pending damage (obj+0x1F1) and recorded until the object is gone (or turned into a chest); the three damage-digit pieces are left out
Files: OUTDIR/<id>/<set>_<facing>.json and <set>_<facing>_<nn>.png (RGBA, colour 0 transparent, equal size for every picture of an animation, foot point =
actor position given as `origin` in the JSON), plus OUTDIR/<id>/index.json. Per animation JSON: pictures with start frame, duration in video frames and
seconds (60.0988 Hz), actor position and displacement, animation id and script position, palettes, pieces, `script_steps`, `per_frame` (picture index, actor
displacement, jump height, weapon / body / third box, sound requests). Left is the mirror image of right and is ripped too."""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_sim, rip_hero_anims as R, gfx_decode as G

HZ = R.HZ
DIGIT_TILES = (200, 202, 204)      # sprite tiles of the three damage-number slots (list 2 of the monster object, palette 4)
FACINGS = {'up': 0x00, 'down': 0x01, 'right': 0x02, 'left': 0x82}


class MonsterCpu(R.PpuCpu):
    """PpuCpu whose OAM ownership test is stricter: an entry belongs to an actor only when it is written through that actor's own piece lists
    (X register inside object+0x90..0x10F); entries written through the projectile table ($7E:D000..D1FF) are tagged with the table owner (X-0xD000) >> 6."""
    def wr8(s, a, v):
        R.PpuCpu.wr8(s, a, v)
        a &= 0xFFFFFF; b = a >> 16; o = a & 0xFFFF
        if b == 0x7E and 0x801 <= o < 0xA01 and o & 3 == 1:
            ob = s.wram[0x14] | s.wram[0x15] << 8; rel = s.X - 0xE000 - ob
            if 0x90 <= rel < 0xD0: s.owner[(o - 0x800) >> 2] = (ob, '90')
            elif 0xD0 <= rel < 0x110: s.owner[(o - 0x800) >> 2] = (ob, 'D0')
            elif 0xD000 <= s.X < 0xD200: s.owner[(o - 0x800) >> 2] = ((s.X - 0xD000) >> 6, 'proj')
            else: s.owner[(o - 0x800) >> 2] = (-1, 'other')


def off(bank, a): return ((bank - 0xC0) << 16) | (a & 0xFFFF)


def table_sizes(rom):
    """Number of animations of each script-pointer table: tables are packed back to back (3 pointers of 2 bytes per animation)."""
    starts = set()
    for i in range(0x57):
        e = rom[0x100000 + 16 * i: 0x100000 + 16 * i + 16]
        starts.add(e[5] | e[6] << 8); starts.add(e[7] | e[8] << 8)
    ss = sorted(starts)
    return {a: (b - a) // 6 for a, b in zip(ss, ss[1:])}


def sext(v): return v - 256 if v > 127 else v


class Rip:
    def __init__(self, rom, state, mid, tile=(17, 25)):
        self.rom, self.mid = rom, mid
        self.s = ai_sim.Sim(rom, state, mid, tile, cpu_class=MonsterCpu)
        self.c, self.o = self.s.c, self.s.o
        self.base = self.o.base - 0xE000
        self.c.hooks[0xC12552] = lambda cp: (setattr(cp, 'PC', (cp.pull16() + 1) & 0xFFFF), True)[1]      # AI step off
        for _ in range(60): self.frame()
        self.x0, self.y0 = self.o.w(2), self.o.w(4)
        self.snap = self.save()

    def nmi(self):
        c = self.c; sv = (c.PB, c.PC, c.M, c.XF, c.S, c.A, c.X, c.Y, c.D, c.DB)
        c.wram[0xEC] |= 1; c.M = 0; c.XF = 0; c.S = 0x1E00; c.PB = 0xC0; c.PC = 0xC0A8
        while not (c.PB == 0xC0 and c.PC == 0xC16F): c.step()
        c.PB, c.PC, c.M, c.XF, c.S, c.A, c.X, c.Y, c.D, c.DB = sv

    def frame(self):
        self.s.frame(); self.nmi()

    def save(self):
        c = self.c
        return (self.s.f, dict(c.__dict__, wram=bytes(c.wram), vram=bytes(c.vram), cgram=bytes(c.cgram), oam=bytes(c.oam), hw=dict(c.hw), ch=dict(c.ch), owner=dict(c.owner), dma_src=[],
                               sounds=list(self.s.sounds)))

    def load(self, snap):
        f, d = snap; c = self.c; self.s.f = f
        for k, v in d.items():
            if k in ('wram', 'vram', 'cgram', 'oam'): getattr(c, k)[:] = v
            elif k == 'sounds': self.s.sounds[:] = v
            elif isinstance(v, (dict, list)): setattr(c, k, type(v)(v))
            elif k not in ('hooks', 'wlog'): setattr(c, k, v)

    def grab(self):
        c, o = self.c, self.o; ox, oy = o.w(0x20), o.w(0x22); out = []; proj = []
        for e in G.oam_entries(c.oam):
            if e['y'] >= 224 and e['y'] + 16 <= 256: continue
            ow = c.owner.get(e['i'])
            if ow and ow[0] == self.base and ow[1] in ('90', 'D0'):
                if ow[1] == 'D0' and e['tile'] in DIGIT_TILES and e['pal'] == 4 and o.b(0x60) == 0x40: continue      # damage digits (overlay of the same object, docs/damage-counter.md)
                y = e['y'] - 256 if e['y'] >= 224 else e['y']
                out.append(dict(list=ow[1], dx=e['x'] - ox, dy=y - oy, tile=e['tile'], pal=e['pal'], prio=e['prio'], hflip=e['hflip'], vflip=e['vflip']))
            elif ow and ow[1] == 'proj' and ow[0] == (self.base >> 9):
                y = e['y'] - 256 if e['y'] >= 224 else e['y']
                proj.append(dict(dx=e['x'] - ox, dy=y - oy, tile=e['tile'], pal=e['pal'], prio=e['prio'], hflip=e['hflip'], vflip=e['vflip']))
        fr = dict(entries=out, pos=(ox, oy), wpos=(o.w(2), o.w(4)), anim=o.b(0x11), facing=o.b(0x10), state=o.b(0x1C), script=o.w(0x16), stage=0, frame_idx=o.w(0x26) // 2,
                  height=o.b(0x45), body=o.b(0x74) & 0x7F, oid=o.b(0x180), active=o.b(0),
                  boxes=dict(weapon=self.box(0xC0), body=self.box(0xC8), third=self.box(0xCC)), vel=(sext(o.b(6)), sext(o.b(7))), proj=proj)
        fr['proj_imgs'] = {}
        for pp in proj:
            key = (pp['tile'], pp['pal'], pp['hflip'], pp['vflip'])
            fr['proj_imgs'][key] = G.render([dict(i=0, x=0, y=0, tile=pp['tile'], pal=pp['pal'], prio=0, hflip=pp['hflip'], vflip=pp['vflip'], large=0)], c.vram, c.cgram, R.OBJ_BASE, R.NAME_GAP, 16, 32, size=(16, 16))
        fr['img'] = R.draw(fr, c.vram, c.cgram)
        fr['palettes'] = {r: [c.cgram[256 + 32 * r + 2 * k] | c.cgram[256 + 32 * r + 2 * k + 1] << 8 for k in range(16)] for r in sorted({e['pal'] for e in out})}
        return fr

    def box(self, a):
        o = self.o
        return [sext(o.b(a)), sext(o.b(a + 1)), o.b(a + 2), o.b(a + 3)]

    def start(self, state, anim, face):
        self.load(self.snap)
        o = self.o
        o.sw(2, self.x0); o.sw(4, self.y0)
        for k in (6, 7, 0x45, 0x12, 0x13, 0x60, 0x61, 0x62, 0x64): o.sb(k, 0)
        o.sw(0x30, 0xFFFF)
        o.sb(0x1C, state); o.sb(0x11, anim); o.sb(0x10, face)
        self.s.sounds.clear()

    def play(self, state, anim, face, maxf=600, loop=True):
        """Record frames after setting the state; stops when the state / animation ends, when one loop of a looping script is complete or after maxf frames."""
        self.start(state, anim, face)
        frs = []; seen = []; p0 = (self.o.w(2), self.o.w(4)); started = False
        for i in range(maxf):
            self.frame(); fr = self.grab(); fr['p0'] = p0; fr['sounds'] = [(f - self.s.f + 1 + i, a, b_, c_, d_) for f, a, b_, c_, d_ in self.s.sounds if f == self.s.f - 1]
            if state and started and fr['state'] == 0: break
            if state == 0 and fr['anim'] != anim and i > 0: break
            if abs(fr['wpos'][0] - p0[0]) > 70 or abs(fr['wpos'][1] - p0[1]) > 60: break
            k = (fr['script'], fr['frame_idx'])
            if state == 0 and loop:
                if not seen or k != seen[-1]:
                    if len(seen) >= 2 and k == seen[0]: break
                    seen.append(k)
                if len(seen) == 1 and i >= 10: break
            started = True
            frs.append(fr)
        return frs

    def kill(self, face, maxf=400):
        self.start(0, 0, face)
        def ai(cp):                          # the death script of the corpse object runs in the AI step: heroes stay off, the monster's step is real
            if cp.X < 0x600:
                cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
            return False
        self.c.hooks[0xC12552] = ai
        for _ in range(3): self.frame()
        self.o.sw(0x1F1, 9999)
        frs = []; p0 = (self.o.w(2), self.o.w(4))
        for i in range(maxf):
            self.frame(); fr = self.grab(); fr['p0'] = p0
            fr['sounds'] = [(i, a, b_, c_, d_) for f, a, b_, c_, d_ in self.s.sounds if f == self.s.f - 1]
            if fr['active'] == 0 and i > 5: break
            if self.o.b(0x1B1) == 0x80 and self.o.b(0x184) == 0 and i > 5: break          # the corpse turned into a chest
            frs.append(fr)
        return frs


def export(rom, frs, outdir, name, meta):
    n = R.export(rom, frs, outdir, name, meta)
    p = os.path.join(outdir, name + '.json'); d = json.load(open(p))
    pf = d['per_frame']
    pf['weapon_box'] = [f['boxes']['weapon'] for f in frs]; pf['body_box'] = [f['boxes']['body'] for f in frs]; pf['third_box'] = [f['boxes']['third'] for f in frs]
    pf['projectile_pieces'] = [f['proj'] for f in frs]
    pf['velocity'] = [list(f['vel']) for f in frs]; pf['object_id'] = [f['oid'] for f in frs]
    pf['sounds'] = [[s[0], s[2], s[3], s[4]] for f in frs for s in f.get('sounds', [])]
    d['script_pointers'] = sorted({'%04X' % f['script'] for f in frs})
    json.dump(d, open(p, 'w'), indent=1)
    return n


def rip(rom, state, outdir, mid, only=None, dirs=None, tile=(17, 25)):
    only = only or ['ord', 'atk', 'hurt', 'swing', 'death']; dirs = dirs or list(FACINGS)
    r = Rip(rom, state, mid, tile)
    t5, t7 = r.o.w(0x75), r.o.w(0x65); sizes = table_sizes(rom)
    n5, n7 = sizes.get(t5, 21), sizes.get(t7, 5)
    od = os.path.join(outdir, '%d' % mid); os.makedirs(od, exist_ok=True)
    idx = dict(object_id=mid, ordinary_table='D1:%04X' % t5, attack_table='D1:%04X' % t7, ordinary_animations=n5, attack_animations=n7, body_height=r.o.b(0x74) & 0x7F, animations={})
    jobs = []
    for d in dirs:
        f = FACINGS[d]
        if 'ord' in only: jobs += [('ord%02d' % a, d, (0, a, f)) for a in range(n5)]
        if 'atk' in only: jobs += [('atk%02d' % a, d, (0x40, a, f)) for a in range(n7)]
        if 'hurt' in only: jobs += [('hurt%02d' % a, d, (0x40, 0x80 | a, f)) for a in range(n5)]
        if 'swing' in only: jobs += [('swing%02d' % a, d, (0x80, a, f)) for a in range(n7)]
    projs = {}
    for name, d, (st, a, f) in jobs:
        frs = r.play(st, a, f)
        for fr in frs: projs.update(fr['proj_imgs'])
        if len(frs) < 2 or not any(fr['entries'] for fr in frs): continue
        meta = dict(object_id=mid, set=name, direction=d, state_byte=st, anim_id=a, facing_byte=f, animation_table='D1:%04X' % (t5 if (st == 0 or a >= 0x80) else t7))
        export(rom, frs, od, '%s_%s' % (name, d), meta)
        idx['animations']['%s_%s' % (name, d)] = dict(total_frames=len(frs), seconds=round(len(frs) / HZ, 5))
    if projs:
        pd = os.path.join(od, 'projectile'); os.makedirs(pd, exist_ok=True); lst = []
        for (tile, pal, hf, vf), im in sorted(projs.items()):
            fn = 'piece_t%03X_p%d_h%d_v%d.png' % (tile, pal, hf, vf); G.write_png(os.path.join(pd, fn), im); lst.append(dict(file=fn, tile=tile, palette=pal, hflip=hf, vflip=vf))
        json.dump(dict(note='16x16 sprite pieces drawn through the projectile table ($7E:D000 + 0x40 * slot) while the monster shot', pieces=lst), open(os.path.join(pd, 'index.json'), 'w'), indent=1)
        idx['projectile_pieces'] = len(lst)
    if 'death' in only:
        for d in dirs:
            frs = r.kill(FACINGS[d])
            if len(frs) > 2:
                export(rom, frs, od, 'death_%s' % d, dict(object_id=mid, set='death', direction=d))
                idx['animations']['death_%s' % d] = dict(total_frames=len(frs), seconds=round(len(frs) / HZ, 5), object_ids=sorted({f['oid'] for f in frs}))
    json.dump(idx, open(os.path.join(od, 'index.json'), 'w'), indent=1)
    print('monster %d: %d animations written to %s' % (mid, len(idx['animations']), od))


def main():
    rom = romio.rom_from_argv(); state, outdir = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    only = dirs = None; tile = (17, 25)
    for k in ('--only', '--dirs', '--tile'):
        if k in args:
            i = args.index(k); v = args[i + 1]; del args[i:i + 2]
            if k == '--only': only = v.split(',')
            elif k == '--dirs': dirs = v.split(',')
            else: tile = tuple(int(x) for x in v.split(','))
    for mid in args[0].split(','):
        rip(rom, state, outdir, int(mid, 0), only, dirs, tile)


if __name__ == '__main__':
    main()

"""Run the hero attack code from a save state and record what the game draws, frame by frame (graphics go to a directory chosen by the caller).
usage: rip_hero_anims.py ROM STATE OUTDIR [hero[,hero]] [weapon_row] [attack[,attack]] [dir[,dir]] [x,y]
  hero: boy girl sprite (default all)   weapon_row: equipped weapon row id 0-71 (default 0 = first weapon of type 0, the glove group)
  attack: hook jab kick lunge (normal attacks, animation ids 0-3) and charge1..8, chargemid1..8, chargenear1..8 (charged attack of stage 1-8; the variant is the
  distance class of the nearest enemy: charge = none or far, chargemid, chargenear)   dir: up down left right   x,y: screen position of the
  centre of the lunges (default: where the state has the hero; use something near the screen centre, sprites outside the screen are not drawn)
STATE: a ZSNES v143 save state taken during play on a map with the three heroes (docs/graphics.md section 8).
Output: OUTDIR/<hero>/<attack>_<level>_<dir>_<frame>.png (RGBA, colour 0 transparent, same size for every frame of one animation) and <attack>_<level>_<dir>.json (plus OUTDIR/index.json).
The sound driver, PPU and DMA are not emulated by cpu65816.py; PpuCpu below captures the PPU register writes and the DMA transfers
(VRAM, CGRAM, OAM) that the NMI handler performs, so that the OAM shadow, the VRAM tiles and the palettes of every video frame are known."""
import sys, os, json, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, zsnes_state, cpu65816 as cpu, gfx_decode as G

HZ = 60.0988
OBJ_BASE, NAME_GAP = 0x6000, 0x1000        # OBJSEL = $63 ($7E:0091): name base word 0x6000, second table +0x1000 words, sizes 16x16 / 32x32
HEROES = ('boy', 'girl', 'sprite')
DIRS = {'up': 0x00, 'down': 0x01, 'right': 0x02, 'left': 0x82}      # actor +0x10: bits 0-3 = 0 up, 1 down, 2 side; bit 7 = mirrored (left)
ORIGIN = (128, 140)                                                    # hero origin placed here on the render canvas
PAD_B = 0x8000                                                         # $4219 bit 7 (B button), read into $43


class PpuCpu(cpu.CPU):
    """cpu65816.CPU plus the parts of the PPU / DMA / joypad registers that matter for sprites."""
    def __init__(s):
        super().__init__()
        s.vram = bytearray(0x10000); s.cgram = bytearray(512); s.oam = bytearray(544)
        s.vmadd = s.vmain = s.cgadd = s.oamadd = 0; s.ch = {}; s.pad = 0; s.owner = {}; s.dma_src = []

    def hwread(s, o):
        if o == 0x4218: return s.pad & 0xFF
        if o == 0x4219: return s.pad >> 8 & 0xFF
        if o in (0x4212, 0x4016, 0x4017) or 0x421A <= o <= 0x421F: return 0
        return super().hwread(o)

    def wr8(s, a, v):
        a &= 0xFFFFFF; b = a >> 16; o = a & 0xFFFF; v &= 0xFF
        if b == 0x7E and 0x801 <= o < 0xA01 and o & 3 == 1:           # OAM shadow y byte: remember which actor / draw list wrote the entry
            ob = s.wram[0x14] | s.wram[0x15] << 8
            s.owner[(o - 0x800) >> 2] = (ob, '90' if 0x90 <= s.X - 0xE000 - ob < 0xD0 else 'D0')
        if b < 0x40 or 0x80 <= b < 0xC0:
            if 0x2100 <= o < 0x2140: s.ppu(o, v); return
            if 0x4300 <= o < 0x4380: s.ch[o] = v; return
            if o == 0x420B: s.dma(v); return
        super().wr8(a, v)

    def ppu(s, o, v):
        if o == 0x2115: s.vmain = v
        elif o == 0x2116: s.vmadd = s.vmadd & 0xFF00 | v
        elif o == 0x2117: s.vmadd = s.vmadd & 0xFF | v << 8
        elif o in (0x2118, 0x2119):
            s.vram[(s.vmadd * 2 + o - 0x2118) & 0xFFFF] = v
            if (o == 0x2119) == bool(s.vmain & 0x80): s.vmadd = (s.vmadd + (1, 32, 128, 128)[s.vmain & 3]) & 0xFFFF
        elif o == 0x2121: s.cgadd = v * 2
        elif o == 0x2122: s.cgram[s.cgadd & 511] = v; s.cgadd += 1
        elif o == 0x2102: s.oamadd = s.oamadd & 0x100 | v
        elif o == 0x2103: s.oamadd = s.oamadd & 0xFF | (v & 1) << 8
        elif o == 0x2104: s.oam[s.oamadd % 544] = v; s.oamadd += 1

    def dma(s, mask):
        for c in range(8):
            if not mask >> c & 1: continue
            g = lambda r: s.ch.get(0x4300 + c * 16 + r, 0)
            ctl, dest, src, n = g(0), g(1), g(2) | g(3) << 8 | g(4) << 16, g(5) | g(6) << 8 or 0x10000
            if ctl & 0x80: continue
            if dest == 0x18: s.dma_src.append((src, n, s.vmadd))
            offs = {0: (0,), 1: (0, 1), 2: (0, 0), 3: (0, 0, 1, 1), 4: (0, 1, 2, 3)}[ctl & 7]; a = src; i = 0
            while i < n:
                for k in offs:
                    if i >= n: break
                    s.ppu(0x2100 + dest + k, s.rd8(a)); i += 1
                    if not ctl & 8: a = a & 0xFF0000 | (a + 1) & 0xFFFF


class Game:
    """Save state + one video frame = joypad poll, one pass of the main loop body $C0:B08C, then the NMI handler $C0:C0A8 (uploads, OAM and CGRAM DMA)."""
    def __init__(s, rom, state):
        cpu.set_rom(rom)
        s.c = c = PpuCpu(); c.wram[:] = zsnes_state.load_wram(state); s.f = 0
        def rtl(cp): cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True
        c.hooks[0xC30004] = rtl; c.hooks[0xC30000] = rtl                 # sound driver not emulated
        s.starts = []                                                    # (frame, $F4, anim) at every call of the attack animation chooser $C1:E40E
        def e40e(cp): s.starts.append((s.f, cp.wram[0xF4], cp.X)); return False
        c.hooks[0x01E40E] = c.hooks[0xC1E40E] = e40e
        s.force_m = None
        def e418(cp):                                   # A = nearest-target distance class (0-3) returned by $C1:E4CC; optionally overridden
            if s.force_m is not None: cp.A = (cp.A & 0xFF00) | s.force_m
            return False
        c.hooks[0x01E418] = c.hooks[0xC1E418] = e418

    def call(s, addr, m=1):
        c = s.c; c.M = m; c.XF = 0; c.S = 0x1F00; c.push16(0xFFFD); c.PB = addr >> 16; c.PC = addr & 0xFFFF
        while not (c.PB == addr >> 16 and c.PC == 0xFFFE): c.step()

    def nmi(s):
        c = s.c; sv = (c.PB, c.PC, c.M, c.XF, c.S, c.A, c.X, c.Y, c.D, c.DB)
        c.wram[0xEC] |= 1; c.M = 0; c.XF = 0; c.S = 0x1E00; c.PB = 0xC0; c.PC = 0xC0A8
        while not (c.PB == 0xC0 and c.PC == 0xC16F): c.step()          # stop at the RTI
        c.PB, c.PC, c.M, c.XF, c.S, c.A, c.X, c.Y, c.D, c.DB = sv

    def frame(s, pad=0):
        s.c.pad = pad; s.c.wram[0x56] = s.f % 5
        s.call(0xC0B08C); s.nmi(); s.f += 1

    def save(s):
        c = s.c
        return (s.f, copy.copy(c.__dict__ | dict(wram=bytes(c.wram), vram=bytes(c.vram), cgram=bytes(c.cgram), oam=bytes(c.oam), hw=dict(c.hw), ch=dict(c.ch), owner=dict(c.owner), dma_src=[])), list(s.starts))

    def load(s, snap):
        s.f, d, st = snap; c = s.c
        for k, v in d.items():
            if k in ('wram', 'vram', 'cgram', 'oam'): getattr(c, k)[:] = v
            elif isinstance(v, (dict, list)): setattr(c, k, copy.copy(v))
            elif k not in ('hooks', 'wlog'): setattr(c, k, v)
        s.starts = list(st)

    def w8(s, a): return s.c.wram[a]
    def w16(s, a): return s.c.wram[a] | s.c.wram[a + 1] << 8


def setup(rom, state, hero, row, direction, pos=None):
    """Only `hero` stays active, controlled by pad 1, equipped with weapon row `row` (the engine's own re-initialisation $C0:E9F8 loads the matching tables).
    Nothing may shorten a lunge: the party window ($C0:D6C8) is replaced by an RTS and the solid-tile codes of the attribute table ($7F:B800, bytes b0 and b2 of the
    256 entries) are cleared.
    pos = (x, y) screen position of the centre of the lunges; the hero starts 45 px (up, down) or 40 px (left, right) behind it, opposite to its facing, so that even the
    longest lunge (105 px) stays on the screen, where sprites are drawn; the world position (+0x02 / +0x04) is set to screen + scroll ($A8 / $AA). None keeps the state's position."""
    g = Game(rom, state); w = g.c.wram; slot = HEROES.index(hero); B = 0xE000 + 0x200 * slot
    if not w[B]: sys.exit('the save state has no active %s (object slot %d); use a state with the whole party' % (hero, slot))
    for k in range(11):
        if k != slot: w[0xE000 + 0x200 * k] = 0
    w[0xD9] = 1 << slot; w[0xD4] = (0x200 * slot) & 0xFF; w[0xD5] = (0x200 * slot) >> 8; w[0xDA] = w[0xDB] = 0
    w[B + 0x1E3] = row; w[B + 0x1E4] = row // 9; w[B + 0x1E8] = row
    w[B + 0x19C] = 8; w[0xCC7D + slot] = 8; w[B + 0x10] = DIRS[direction]; w[B + 0x6] = w[B + 0x7] = 0
    for o in (0x1A, 0x1B, 0x1C, 0x1D, 0x60, 0x61, 0x62, 0x64, 0x0A, 0x08, 0x11, 0x12, 0x190, 0x191, 0x19B, 0x1B0, 0x1B1, 0x1ED, 0x45): w[B + o] = 0    # clear attack / status / gauge state
    if pos:
        back = dict(up=(0, 45), down=(0, -45), left=(40, 0), right=(-40, 0))[direction]
        wx, wy = pos[0] + back[0] + (w[0xA8] | w[0xA9] << 8), pos[1] + back[1] + (w[0xAA] | w[0xAB] << 8)
        w[B + 1] = w[B + 6] = 0; w[B + 2:B + 6] = bytes((wx & 255, wx >> 8, wy & 255, wy >> 8))
    g.c.hooks[0xC0D6C8] = lambda cp: (setattr(cp, 'PC', (cp.pull16() + 1) & 0xFFFF), True)[1]
    for i in range(256): w[0x1B800 + 4 * i] = w[0x1B802 + 4 * i] = 0
    g.call(0xC0E9F8)
    for _ in range(30): g.frame()
    return g, slot, B


def grab(g, slot, B):
    """What the game draws for this hero in the current frame, relative to the actor origin: the pieces of the actor's two lists (+0x90 and +0xD0)."""
    c = g.c; ox, oy = g.w16(B + 0x20), g.w16(B + 0x22); out = []
    for e in G.oam_entries(c.oam):
        if e['y'] >= 224 and e['y'] + 16 <= 256: continue
        ow = c.owner.get(e['i'])
        if ow and ow[0] == B - 0xE000:
            y = e['y'] - 256 if e['y'] >= 224 else e['y']
            out.append(dict(list=ow[1], dx=e['x'] - ox, dy=y - oy, tile=e['tile'], pal=e['pal'], prio=e['prio'], hflip=e['hflip'], vflip=e['vflip']))
    fr = dict(entries=out, pos=(ox, oy), wpos=(g.w16(B + 2), g.w16(B + 4)), anim=g.w8(B + 0x11), facing=g.w8(B + 0x10), state=g.w8(B + 0x1C), script=g.w16(B + 0x16), stage=g.w8(B + 0x19B),
              frame_idx=g.w16(B + 0x26) // 2, height=g.w8(B + 0x45), body=g.w8(B + 0x74) & 0x7F)
    fr['img'] = draw(fr, c.vram, c.cgram)
    fr['palettes'] = {r: [c.cgram[256 + 32 * r + 2 * k] | c.cgram[256 + 32 * r + 2 * k + 1] << 8 for k in range(16)] for r in sorted({e['pal'] for e in out})}
    return fr


def is_ground_shadow(e):
    return e['list'] == 'D0' and e['tile'] == 0


def draw(fr, vram, cgram, with_shadow=False):
    ents = [dict(i=k, x=ORIGIN[0] + e['dx'], y=ORIGIN[1] + e['dy'], tile=e['tile'], pal=e['pal'], prio=e['prio'], hflip=e['hflip'], vflip=e['vflip'], large=0)
            for k, e in enumerate(fr['entries']) if with_shadow or not is_ground_shadow(e)]
    return G.render(ents, vram, cgram, OBJ_BASE, NAME_GAP, 16, 32)


def record(g, slot, B, pad_of, max_frames=400):
    """Step frames until the attack state byte (+0x1C) returns to 0. Frames before the animation script moves off its previous position are the engine's
    start-up latency (the previous pose stays on screen); they are returned separately. Returns (latency frames, animation frames)."""
    s0 = g.w16(B + 0x16); lat = []; frs = []; started = False; p0 = (g.w16(B + 2), g.w16(B + 4))
    for i in range(max_frames):
        g.frame(pad_of(i)); fr = grab(g, slot, B)
        started = started or fr['state'] != 0
        if started and fr['state'] == 0: break
        fr['p0'] = p0; (frs if frs or (started and fr['script'] != s0) else lat).append(fr)
    return lat, frs


def key(fr):
    return (tuple((e['list'], e['dx'], e['dy'], e['tile'], e['pal'], e['hflip'], e['vflip']) for e in fr['entries']), bytes(fr['img'].px))


def export(rom, frs, outdir, name, meta):
    """Write the distinct frames and the JSON. Frames are cropped to the union box of the whole animation; the origin is the actor position."""
    runs = []
    for i, fr in enumerate(frs):
        k = key(fr)
        if runs and runs[-1]['k'] == k: runs[-1]['n'] += 1
        else: runs.append(dict(k=k, n=1, start=i, fr=fr, img=fr['img']))
    boxes = [r['img'].bbox() for r in runs if r['img'].bbox()]
    ux0, uy0, ux1, uy1 = min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)
    os.makedirs(outdir, exist_ok=True); fl = []
    x0, y0 = frs[0]['p0']
    for j, r in enumerate(runs):
        fn = '%s_%02d.png' % (name, j); G.write_png(os.path.join(outdir, fn), r['img'].crop(ux0, uy0, ux1, uy1))
        fr = r['fr']
        fl.append(dict(file=fn, start_frame=r['start'], frames=r['n'], seconds=round(r['n'] / HZ, 5), actor_pos=list(fr['wpos']), move=[fr['wpos'][0] - x0, fr['wpos'][1] - y0],
                       anim=fr['anim'], facing=fr['facing'], script_pos='%04X' % fr['script'], charge_stage=fr['stage'], palettes={'obj_row_%d' % r: ['%04X' % v for v in w] for r, w in fr['palettes'].items()},
                       pieces=[dict({k: e[k] for k in ('list', 'dx', 'dy', 'tile', 'pal', 'prio', 'hflip', 'vflip')}, ground_shadow=is_ground_shadow(e)) for e in fr['entries']]))
    steps = []
    for i, fr in enumerate(frs):
        k2 = (fr['script'], fr['frame_idx'])
        if steps and steps[-1]['k'] == k2: steps[-1]['frames'] += 1
        else: steps.append(dict(k=k2, start_frame=i, frames=1, script_pos='%04X' % fr['script'], frame_idx=fr['frame_idx']))
    run_of = [j for j, r in enumerate(runs) for _ in range(r['n'])]
    for s in steps: s['file'] = fl[run_of[s['start_frame']]]['file']; s['seconds'] = round(s['frames'] / HZ, 5); del s['k']
    d = dict(meta, png_size=[ux1 - ux0, uy1 - uy0], origin=[ORIGIN[0] - ux0, ORIGIN[1] - uy0], total_frames=len(frs), total_seconds=round(len(frs) / HZ, 5),
             frame_rate_hz=HZ, start_world_position=[x0, y0], movement_during_latency=[frs[0]['wpos'][0] - x0, frs[0]['wpos'][1] - y0], frames=fl, script_steps=steps, per_frame=dict(file_index=run_of, actor_dx=[f['wpos'][0] - x0 for f in frs],
             actor_dy=[f['wpos'][1] - y0 for f in frs], jump_height=[f['height'] for f in frs]))
    json.dump(d, open(os.path.join(outdir, name + '.json'), 'w'), indent=1)
    return len(runs)


def parity_press(g, want):
    """Number of idle frames to wait before pressing B so that the attack chooser $C1:E40E runs with $F4 parity `want` (together with the distance class it picks one of the four normal attacks)."""
    snap = g.save()
    for wait in range(6):
        g.load(snap); n0 = len(g.starts)
        for _ in range(wait): g.frame()
        for i in range(8): g.frame(PAD_B if i == 0 else 0)
        if len(g.starts) > n0 and g.starts[n0][1] & 1 == want:
            g.load(snap); return wait
    raise RuntimeError('parity not reachable')


NORMAL = dict(hook=(0, 1, 0), jab=(0, 0, 1), kick=(2, 1, 2), lunge=(2, 0, 3))        # attack -> (distance class, $F4 parity, expected animation id)
CHARGE = dict(chargenear=0, chargemid=1, charge=3)                                    # charged-attack variant -> distance class forced at the release (animation id = 4 * stage + 0/1/2)
DIST_NAME = {0: 'nearest target distance byte 0-15', 1: 'distance byte 16-31', 2: 'distance byte 32-47', 3: 'distance byte 48 and more, or no target'}


def rip(rom, state, outdir, heroes, row, attacks, dirs, pos=None):
    n_anim = n_frames = 0; log = []; attacks = [a for a in attacks if a and a != 'index']      # 'index' alone only rebuilds OUTDIR/index.json
    def put(hero, frs, lat, name, atk, lv, d, m):
        meta = dict(body_offset=frs[0]['body'], latency_frames=len(lat), hero=hero, attack=atk, level=lv, direction=d, weapon_row=row, weapon_type=row // 9, anim_id=frs[0]['anim'],
                    distance_class=m, distance_class_meaning=DIST_NAME[m])
        return export(rom, frs, os.path.join(outdir, hero), '%s_%d_%s' % (name, lv, d), meta)
    for hero in heroes:
        for d in dirs:
            g, slot, B = setup(rom, state, hero, row, d, pos)
            base = g.save()
            for atk in [a for a in attacks if a in NORMAL]:
                m, par, want = NORMAL[atk]; g.load(base); g.force_m = m; wait = parity_press(g, par)
                for _ in range(wait): g.frame()
                lat, frs = record(g, slot, B, lambda i: PAD_B if i == 0 else 0)
                if frs[0]['anim'] != want: log.append('%s %s %s: animation id %d, expected %d' % (hero, d, atk, frs[0]['anim'], want))
                n_frames += put(hero, frs, lat, atk, atk, 0, d, m); n_anim += 1
            ch = [a for a in attacks if a not in NORMAL]
            if ch:
                g.load(base); g.force_m = 3; g.frame(PAD_B); snaps = {}; i = 0
                while i < 1400 and len(snaps) < 8:                   # keep B held: the charge stage rises by itself; snapshot when each stage is reached
                    g.frame(PAD_B); i += 1
                    st = g.w8(B + 0x19B)
                    if st and st not in snaps: snaps[st] = g.save()
                for atk in ch:
                    var, lv = atk[:-1], int(atk[-1])
                    if lv not in snaps: log.append('%s %s %s: stage %d not reached' % (hero, d, atk, lv)); continue
                    m = CHARGE[var]; g.load(snaps[lv]); g.force_m = m; lat, frs = record(g, slot, B, lambda i: 0)
                    n_frames += put(hero, frs, lat, var, var, lv, d, m); n_anim += 1
    idx = {}
    for hero in HEROES:
        for fn in sorted(os.listdir(os.path.join(outdir, hero))) if os.path.isdir(os.path.join(outdir, hero)) else []:
            if fn.endswith('.json'):
                d = json.load(open(os.path.join(outdir, hero, fn)))
                idx.setdefault(hero, {})[fn[:-5]] = dict(anim_id=d['anim_id'], distinct_frames=len(d['frames']), total_frames=d['total_frames'], seconds=d['total_seconds'], png_size=d['png_size'], origin=d['origin'])
    json.dump(idx, open(os.path.join(outdir, 'index.json'), 'w'), indent=1)
    print('animations %d, distinct frames %d' % (n_anim, n_frames)); [print(l) for l in log]


if __name__ == '__main__':
    rom = romio.rom_from_argv(); state, outdir = sys.argv[1], sys.argv[2]
    heroes = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[3] else list(HEROES)
    row = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else 0
    arg = lambda i: sys.argv[i].split(',') if len(sys.argv) > i and sys.argv[i] else None      # an empty argument means the default
    attacks = arg(5) or list(NORMAL) + ['%s%d' % (v, i) for v in CHARGE for i in range(1, 9)]
    dirs = arg(6) or list(DIRS)
    pos = tuple(int(v) for v in sys.argv[7].split(',')) if len(sys.argv) > 7 and sys.argv[7] else None
    rip(rom, state, outdir, heroes, row, attacks, dirs, pos)

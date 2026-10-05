"""Event-run harness for the cutscenes around the Mana Beast: generic timeline extraction on top of tools/event_vm.py (the real frame body `$C0:B08C`,
the map loader, the event VM `$C1:E8D3`, the text engine and the boss engine are executed; the PPU, DMA to video memory and the sound CPU are not).

usage:
  event_runs.py ROM STATE intro  OUT.json [leader=N] [after=N] [weapons=A,B,C] [md=1] [raw=FILE]
        STATE: a ZSNES v143 state with the three heroes on map 246 (flag 0x4E = 8, no event running). Starts event 0x429 (the entry into map 255 and
        the Mana Beast arena, map 253) as a trigger tile would, runs until the VM is idle, then `after` more frames (default 600) of the fight start.
        weapons=A,B,C overrides the weapon types of the three heroes.
  event_runs.py ROM STATE ending OUT.json [leader=N] [dead=F] [frames=N] [snap=FILE] [resume=FILE] [raw=FILE] [md=1]
        runs the intro, lets the Mana Beast fight start (heroes' HP refilled every frame), sets the boss dead bit (`$190`) `dead` frames after control
        returned (default 10), waits for the boss death sequence (phases 0x12, 0x13, 0x10), the event 0x42F and everything it starts until the VM idles,
        the restart routine `$C1:4CFA` is reached or `frames` frames have run. Frame 0 of the report = the frame in which the boss phase becomes 0x12.
        snap=FILE saves the state at that frame, resume=FILE restarts from such a file (skips the intro and the fight).
  event_runs.py ROM report RAW.pkl OUT.json       rebuild the report from the raw log of a run
  event_runs.py ROM md REPORT.json                print the timeline table of a report
  event_runs.py ROM decode2 EVENT [EVENT ...]
        static listing like `event_vm.py decode` (staff-roll segments 0x7D..0x7E are skipped as a whole); no text is printed.
library: Runner(rom, state) -> .run_until_idle(), .frame(), .save_snapshot(), .load_snapshot(); build_report(...), report_from_raw(...)
The boss engine and the map records decide what is on the map; nothing is read from fixed paths. No script text is printed or stored: text blocks are recorded as
bank:offset and length."""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, event_vm as E

HZ = E.HZ
FACE = E.FACE
HERO_NAMES = {0: 'boy', 1: 'girl', 2: 'sprite'}


def sec(t): return round(t / HZ, 3)


class Restart(Exception):
    pass


class Runner(E.World):
    """event_vm.World with a wider observer (12 object slots, event flags, screen-effect bytes) and an optional HP refill of the heroes."""
    MISC = E.World.MISC + [('X49', 0x49, 1), ('X5E', 0x5E, 1), ('X5F', 0x5F, 1), ('E3', 0xE3, 1), ('E4', 0xE4, 1), ('W10A', 0x010A, 2), ('W10C', 0x010C, 2),
                           ('B1057', 0x1057, 1), ('P1D00', 0x1D00, 1), ('P48', 0x48, 1), ('P4F', 0x4F, 1), ('P3A', 0x3A, 2), ('P1D4', 0x1D04, 1),
                           ('DA', 0xDA, 1), ('DB', 0xDB, 1), ('P95', 0x95, 1), ('P23', 0x23, 1), ('P22', 0x22, 1), ('P21', 0x21, 1)]
    SLOTS = 12

    def __init__(self, rom, state, seed=None):
        super().__init__(rom, state, seed)
        self.refill = False
        self._flags = None
        self.text_blocks = []
        self.restarted = None
        self.world_mode = False
        self.world_frames = 0
        self._vb = 0
        self.c.hooks[0xC14CFA] = self._restart_hook
        self.c.hooks[0xC08064] = self._world_hook
        orig = self.c.hwread
        def hwread(o):
            if o == 0x4210:
                self._vb ^= 1
                return 0x80 if self._vb else 0x00
            return orig(o)
        self.c.hwread = hwread

    WORLD_LOOP = (0xC08B5E, 0xC083A8, 0xC0983A, 0xC0908B, 0xC095A0, 0xC09AB8, 0xFFFDE4, 0xC087E0, 0xC08272, 0xC08093)

    def _world_hook(self, cp):
        # `JMP $8038` (map change with $FF bit 7, event command 0x1D) re-initialises the game in BG mode 7 and falls into the loop at $C0:8064: one frame ends here
        self.world_mode = True
        self.events.append(dict(t=self.t, kind='world_enter', f8=self.c.wram[0xF8]))
        cp.PB = 0xC0; cp.PC = 0xFFFE
        return True

    def callx(self, addr, long=False, max_steps=3_000_000):
        c = self.c
        c.M = 1; c.XF = 1; c.S = 0x1F00
        if long:
            c.push8(0xFE); c.push16(0xFFFD); end = (0xFE, 0xFFFE)
        else:
            c.push16(0xFFFD); end = (addr >> 16, 0xFFFE)
        c.PB = addr >> 16; c.PC = addr & 0xFFFF
        n = 0
        while not (c.PB == end[0] and c.PC == end[1]):
            c.step(); n += 1
            if n > max_steps: raise RuntimeError('timeout at %02X:%04X' % (c.PB, c.PC))
        return n

    def _world_frame(self):
        w = self.c.wram
        self.t += 1
        self.world_frames += 1
        w[0x56] = (self.t - self.phase0) % 5
        self.pad = 0
        try:
            for a in self.WORLD_LOOP:
                if a >> 16 == 0xFF: self.callx(0xC1FDE4, long=True)
                else: self.callx(a)
        except E.MapReload:
            self.world_mode = False
            self.events.append(dict(t=self.t, kind='world_exit', frames=self.world_frames))
            self.map_loader()
            self.events.append(dict(t=self.t, kind='map_load', map=self.w16(0xDC), dx=w[0xDE], dy=w[0xDF], b8=w[0xB8], from_world=True))
        w[0xF4] = (w[0xF4] + 1) & 0xFF
        w[0xEC] = 0
        self._observe()

    def _restart_hook(self, cp):
        raise Restart()

    REGS = 'A X Y S D DB PB PC N V Z C M XF I Dm E steps'.split()

    def save_snapshot(self, path, meta=None):
        import pickle
        c = self.c
        st = dict(wram=bytes(c.wram), sram=bytes(c.sram), hw=dict(c.hw), regs={k: getattr(c, k) for k in self.REGS}, t=self.t, phase0=self.phase0, events=self.events,
                  vm_ops=self.vm_ops, last=self._last, last_misc=self._last_misc, flags=self._flags, t_scene=self.t_scene, dma=bytes(self.dma), refill=self.refill,
                  release=self._release, pad=self.pad, meta=meta)
        pickle.dump(st, open(path, 'wb'))

    def load_snapshot(self, path):
        import pickle
        st = pickle.load(open(path, 'rb'))
        c = self.c
        c.wram[:] = st['wram']; c.sram[:] = st['sram']; c.hw.clear(); c.hw.update(st['hw'])
        for k, v in st['regs'].items(): setattr(c, k, v)
        self.t = st['t']; self.phase0 = st['phase0']; self.events = st['events']; self.vm_ops = st['vm_ops']; self._last = st['last']; self._last_misc = st['last_misc']
        self._flags = st['flags']; self.t_scene = st['t_scene']; self.dma[:] = st['dma']; self.refill = st['refill']; self._release = st['release']; self.pad = st['pad']
        return st.get('meta')

    def snap(self, slot):
        d = super().snap(slot)
        if d is not None:
            d['vis'] = self.c.wram[0xE000 + 0x200 * slot + 0x0E]
        return d

    def frame(self):
        w = self.c.wram
        if self.refill:
            for h in range(3):
                b = 0xE000 + 0x200 * h
                w[b + 0x182] = w[b + 0x184]; w[b + 0x183] = w[b + 0x185]
        try:
            if self.world_mode: self._world_frame()
            else: super().frame()
        except Restart:
            self.restarted = self.t
            self.events.append(dict(t=self.t, kind='restart'))
            self._observe()

    def _observe(self):
        w = self.c.wram
        for sl in range(self.SLOTS):
            s = self.snap(sl)
            if s != self._last.get(sl):
                self.events.append(dict(t=self.t, kind='obj', slot=sl, s=s)); self._last[sl] = s
        cam = (self.w16(0xA8), self.w16(0xAA), self.w16(0xC0), self.w16(0xC2))
        if cam != self._last.get('cam'):
            self.events.append(dict(t=self.t, kind='cam', x=cam[0], y=cam[1], mapw=cam[2], maph=cam[3])); self._last['cam'] = cam
        m = tuple(self.w16(a) if sz == 2 else w[a] for _, a, sz in self.MISC)
        if m != self._last_misc:
            self.events.append(dict(t=self.t, kind='misc', **{n: v for (n, _, _), v in zip(self.MISC, m)})); self._last_misc = m
        fl = bytes(w[0xCF00:0xD000])
        if self._flags is not None and fl != self._flags:
            for i in range(256):
                if fl[i] != self._flags[i]:
                    self.events.append(dict(t=self.t, kind='flag', idx=i, old=self._flags[i], new=fl[i]))
        self._flags = fl

    def run_until_idle(self, max_frames=20000, min_frames=10):
        w = self.c.wram
        t0 = self.t
        while self.t - t0 < max_frames:
            self.frame()
            if w[0xD0] == 0 and self.t - t0 > min_frames and not any(e['kind'] == 'map_load' and e['t'] >= self.t - 3 for e in self.events[-8:]):
                return True
        return False


# ----------------------------------------------------------------------------------------------------- static decoder with credits blocks
def text_extent(rom, bank, addr):
    """Length of the text block at (bank, addr): bytes >= 0x50 (0x57 and 0x59 take one argument byte); the code 0x7D opens a credits segment that runs through the
    first 0x7E (its bytes may be < 0x50); a block can chain several segments and ends at the first byte < 0x50 outside a segment [V: equals the engine's own end in every block]."""
    o = E.b24(bank << 16) + addr
    n = 0
    while True:
        c = rom[o + n]
        if c == 0x7D:
            n += 1
            while rom[o + n] != 0x7E: n += 1
            n += 1
        elif c >= 0x50:
            n += 2 if c in (0x57, 0x59) else 1
        else:
            return n


def op_len2(rom, bank, addr):
    o = E.b24(bank << 16) + addr
    if rom[o] >= 0x50: return text_extent(rom, bank, addr)
    return E.op_len(rom, bank, addr)


def decode2(rom, ev, limit=None):
    bank = 0xC9 if ev < 0x400 else 0xCA
    base = E.b24(bank << 16)
    p = struct.unpack_from('<H', rom, base + 2 * (ev & 0x3FF))[0]
    out = []
    a = p
    while True:
        o = base + a
        op = rom[o]
        ln = op_len2(rom, bank, a)
        if op >= 0x50: out.append(dict(off=a, op='TEXT', name='TEXT', bytes=ln, credits=0x7D in rom[o:o + ln]))
        else:
            ent = E.OPS.get(op)
            out.append(dict(off=a, op='%02X' % op, name=ent[0] if ent else '?', params=op_params2(op, bytes(rom[o + 1:o + 5])), bytes=ln))
        a += ln
        if op == 0 or (limit and a >= limit) or a - p > 6000: break
    return bank, out


def op_params2(op, a):
    if op == 0x2D:
        r = dict(arg=a[0])
        if a[0] in (5, 6) or 0x80 <= a[0] < 0x90: r['word'] = a[1] | a[2] << 8
        return r
    if op == 0x41 or op == 0x0A: return dict(raw=list(a))
    if op in (0x36, 0x37, 0x33): return dict(word=a[0] | a[1] << 8)
    if op in (0x39, 0x3A): return dict(actor=a[0], b=a[1], c=a[2])
    if op in (0x1D, 0x1E, 0x1F, 0x2B, 0x2C, 0x2E, 0x2F, 0x3B, 0x3C, 0x38): return dict(arg=a[0])
    if op in (0x43, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E): return dict(raw=list(a))
    return E.op_params(op, a)


# ----------------------------------------------------------------------------------------------------- report
def vm_text2(nm, pr):
    if nm == 'SCREEN':
        return 'SCREEN arg %d%s' % (pr['arg'], (' word 0x%04X' % pr['word']) if 'word' in pr else '')
    if nm in ('MAP_CHANGE_D', 'WARP', 'HERO_CMD', 'PARTY_CMD', 'ACTOR_CLONE', 'ACTOR_DELETE', 'ACTOR_FX', 'HERO_REFILL', 'IF_ACTOR', 'IF_PARTY', 'IF_PARTY_SIZE'):
        return '%s arg 0x%02X' % (nm, pr.get('arg', 0))
    if nm in ('CAFF_SET', 'CAFF_CLEAR', 'FLAG_OP_WAIT', 'FLAG_OP_WAIT2', 'IF_FIELD', 'OBJ_CMD', 'SET_0600', 'SET_FIELD_BYTE', 'SET_WORD_40'):
        return '%s %s' % (nm, ' '.join('%s=%s' % (k, ('0x%02X' % v if isinstance(v, int) else v)) for k, v in pr.items()))
    if nm == 'FLAG_SET': return 'FLAG_SET flag 0x%02X = %d' % (pr['flag'], pr['value'])
    return E.vm_text(nm, pr)


def vm_rows(rom, w, sc, t_end):
    rows = []
    for o in w.vm_ops:
        if o['t'] < sc or o['t'] > sc + t_end: continue
        evid, off = E.event_of(rom, o['bank'], o['addr'])
        opn = o['op'] if o['op'] < 0x50 else 0x50
        ent = E.OPS.get(opn)
        r = dict(t=o['t'] - sc, s=sec(o['t'] - sc), event='0x%03X' % evid, offset=off, addr='%02X:%04X' % (o['bank'], o['addr']),
                 op='%02X' % o['op'] if o['op'] < 0x50 else 'TEXT', name=ent[0] if ent else '?', d0=o['d0'])
        if o['op'] < 0x50:
            r['params'] = op_params2(o['op'], o['args'].ljust(4, b'\0'))
            r['length'] = op_len2(rom, o['bank'], o['addr'])
        else:
            r['bytes'] = text_extent(rom, o['bank'], o['addr'])
            r['bank'] = o['bank']; r['addr_int'] = o['addr']
        rows.append(r)
    return rows


def build_report(rom, w, sc, t_end, name, conds, leader, extra=None, first_map=None):
    lim = sc + t_end
    ev = [e for e in w.events if sc - 1 <= e['t'] <= lim]
    vm = vm_rows(rom, w, sc, t_end)
    # dialogs: dynamic length = distance to the next executed command of the same event/bank
    dialogs = []
    for i, r in enumerate(vm):
        if r['op'] != 'TEXT': continue
        nxt = vm[i + 1] if i + 1 < len(vm) else None
        t_next = nxt['t'] if nxt else t_end
        dyn = None
        if nxt and nxt['addr'][:2] == r['addr'][:2]:
            dyn = int(nxt['addr'][3:], 16) - r['addr_int']
            if dyn <= 0: dyn = None
        d = dict(n=len(dialogs) + 1, event=r['event'], offset=r['offset'], addr=r['addr'], bytes=r['bytes'], bytes_engine=dyn,
                 t_start=r['t'], s_start=r['s'], t_end=t_next, frames=t_next - r['t'], credits_block=0x7D in w.rom[E.b24(r['bank'] << 16) + r['addr_int']:E.b24(r['bank'] << 16) + r['addr_int'] + r['bytes']])
        dialogs.append(d)
        r.pop('bank'); r.pop('addr_int')
    sounds = []
    vm_sound_t = {r['t'] for r in vm if r['name'] == 'SOUND'}
    for e in ev:
        if e['kind'] == 'sound' and e['t'] >= sc:
            kind = {1: 'music', 2: 'sfx'}.get(e['cmd'], 'raw')
            sounds.append(dict(t=e['t'] - sc, s=sec(e['t'] - sc), kind=kind, cmd=e['cmd'], id=e['arg1'], p2=e['arg2'], p3=e['arg3'], source='vm_op' if (e['t'] - sc) in vm_sound_t else 'engine'))
    world = []
    for e in w.events:
        if e['kind'] == 'world_enter' and sc <= e['t'] <= lim: world.append([e['t'] - sc, None])
        if e['kind'] == 'world_exit' and sc <= e['t'] <= lim and world and world[-1][1] is None: world[-1][1] = e['t'] - sc
    for iv in world:
        if iv[1] is None: iv[1] = t_end
    in_world = lambda T: any(a <= T <= b for a, b in world)
    loads = [dict(t=e['t'] - sc, map=e['map'], start_tile_x=e['dx'], start_tile_y=e['dy'] >> 1, header_b8=e['b8']) for e in ev if e['kind'] == 'map_load']
    cam_all = [e for e in w.events if e['kind'] == 'cam']
    for l in loads:
        c0 = next((e for e in cam_all if e['t'] >= l['t'] + sc), None)
        if c0: l['map_size_px'] = [c0['mapw'], c0['maph']]
        ch = [r for r in vm if r['name'] in ('MAP_CHANGE', 'MAP_CHANGE_D') and r['t'] < l['t']]
        if ch:
            r = ch[-1]
            l['via'] = ('MAP_CHANGE transition %d' % r['params']['transition']) if r['name'] == 'MAP_CHANGE' else 'MAP_CHANGE_D arg 0x%02X (world-map mode, then the map the world-map code selects)' % r['params']['arg']
            l['via_op_t'] = r['t']
        if any(e['kind'] == 'map_load' and e['t'] == l['t'] + sc and e.get('from_world') for e in w.events): l['from_world_mode'] = True
    initial_map = first_map
    load_ts = {e['t'] + d for e in ev if e['kind'] == 'map_load' for d in (0, 1, 2)}
    camsz = [(e['t'], e['mapw'], e['maph']) for e in w.events if e['kind'] == 'cam' and e['t'] <= lim]
    objs = {}
    slot_series = {}
    for sl in range(Runner.SLOTS):
        ser = [(e['t'], e['s']) for e in w.events if e['kind'] == 'obj' and e['slot'] == sl and sc - 1 <= e['t'] <= lim]
        # the observer logs only changes: add the value in force at sc
        before = [(e['t'], e['s']) for e in w.events if e['kind'] == 'obj' and e['slot'] == sl and e['t'] < sc - 1]
        if before and (not ser or ser[0][0] > sc - 1): ser.insert(0, (sc - 1, before[-1][1]))
        if not ser or all(s is None for _, s in ser): continue
        slot_series[sl] = ser
        info = dict(slot=sl)
        info['moves'] = []
        mser = [(t, sn if sn and sn['id'] and not 0x57 <= sn['id'] <= 0x7F else None) for t, sn in ser]
        mser = unwrap(mser, camsz, load_ts)
        for g in E.movement_segments(mser, breaks=load_ts):
            if in_world(g['t0'] - sc): continue
            if sl >= 3 and g['frm'] == (0, 0) and g['t1'] == g['t0']: continue
            frames = g['t1'] - g['t0'] + 1
            cause = None
            for r in vm:
                if r['name'] in ('ACTOR_WALK', 'ACTOR_ANIM', 'ACTOR_ANIM_LOOP', 'GATHER') and 0 <= (g['t0'] - sc) - r['t'] <= 5:
                    if r['name'] == 'GATHER':
                        if sl < 3 and sl != leader: cause = '%s+%04X GATHER' % (r['event'], r['offset'])
                    else:
                        a = r['params']['actor']
                        tgt = leader if a == 0 else (a - 1 if a < 0x80 else None)
                        if tgt == sl: cause = '%s+%04X %s' % (r['event'], r['offset'], vm_text2(r['name'], r['params']))
                    if cause: break
            if cause is None and sl < 3:
                for r in vm:
                    if r['name'] in ('MAP_CHANGE', 'MAP_CHANGE_D') and r['t'] <= (g['t0'] - sc) <= next((l['t'] for l in loads if l['t'] >= r['t']), r['t'] + 400):
                        cause = 'engine: exit walk of the party during the map change started at frame %d' % r['t']
                if cause is None and any(0 <= g['t0'] - e['t'] <= 4 for e in w.events if e['kind'] == 'map_load'):
                    cause = 'engine: entry walk after the map load'
            idnow = next((s['id'] for t, s in mser if t >= g['t0'] and s), None)
            info['moves'].append(dict(t0=g['t0'] - sc, t1=g['t1'] - sc, s0=sec(g['t0'] - sc), id=idnow, frm=list(g['frm']), to=list(g['to']), frames=frames, px=g['path'],
                                      px_per_frame=round(g['path'] / frames, 3), px_per_s=round(g['path'] / frames * HZ, 2), anim=sorted(g['anims']),
                                      facing=sorted(FACE.get(f, f) for f in g['faces']), vel=sorted((E.sm(a), E.sm(b)) for a, b in g['vels']),
                                      profile=g['profile'], cause=cause, autonomous=cause is None))
        info['facing'] = []; info['pose'] = []; info['presence'] = []; info['ids'] = []; info['visibility'] = []
        pf = None; pp = None; pres = None; pv = None
        for t, s in ser:
            on = s is not None
            if on != pres:
                info['presence'].append(dict(t=t - sc, s=sec(t - sc), on=on, id=s['id'] if s else None, x=s['x'] if s else None, y=s['y'] if s else None)); pres = on
            if not s: pf = None; pp = None; pv = None; continue
            if not info['ids'] or info['ids'][-1]['id'] != s['id']: info['ids'].append(dict(t=t - sc, id=s['id']))
            if s['vis'] != pv:
                info['visibility'].append(dict(t=t - sc, s=sec(t - sc), obj0E=s['vis'])); pv = s['vis']
            if s['face'] != pf and t not in load_ts:
                info['facing'].append(dict(t=t - sc, s=sec(t - sc), facing=FACE.get(s['face'], s['face']), code=s['face'])); pf = s['face']
            key = (s['state'], s['anim']) if (s['state'] or s['anim'] not in (0, 1, 2, 3)) else None
            if key != pp and t not in load_ts:
                if key: info['pose'].append(dict(t=t - sc, s=sec(t - sc), state=s['state'], anim=s['anim']))
                else: info['pose'].append(dict(t=t - sc, s=sec(t - sc), state=0, anim='idle'))
                pp = key
        objs[E.SLOT_NAME.get(sl, 'slot%d' % sl)] = info
    # entries: objects present 3 frames after each map load (the loader places them over two frames) and at the start
    entries = []
    pts = [(0, initial_map)] + [(l['t'], l['map']) for l in loads]
    for T, m in pts:
        ent = dict(map=m, t=T, objects={})
        for sl in range(Runner.SLOTS):
            cur = None
            for t, sn in slot_series.get(sl, []):
                if t - sc <= T: cur = sn
            if cur is None:
                for t, sn in slot_series.get(sl, []):
                    if T < t - sc <= T + 3 and sn: cur = sn; break
            if cur:
                o = dict(id=cur['id'], x=cur['x'], y=cur['y'], face=FACE.get(cur['face'], cur['face']), face_code=cur['face'])
                if 0x57 <= cur['id'] <= 0x7F: o.update(engine_x=cur['f2b'], engine_y=cur['f32'], phase94=cur['f94'], flags98='0x%04X' % cur['f98'])
                ent['objects'][E.SLOT_NAME.get(sl, 'slot%d' % sl)] = o
        entries.append(ent)
    cams = [(e['t'], e['x'], e['y']) for e in w.events if e['kind'] == 'cam' and sc - 1 <= e['t'] <= lim]
    prevcam = [(e['x'], e['y']) for e in w.events if e['kind'] == 'cam' and e['t'] < sc - 1]
    if prevcam and (not cams or cams[0][0] > sc): cams.insert(0, (sc - 1, prevcam[-1][0], prevcam[-1][1]))
    camseg = []
    for i, (t, x, y) in enumerate(cams):
        if i == 0:
            camseg.append(dict(t0=t - sc, t1=t - sc, frm=[x, y], to=[x, y], initial=True)); continue
        px_, py_ = cams[i - 1][1], cams[i - 1][2]
        if t in load_ts:
            camseg.append(dict(t0=t - sc, t1=t - sc, frm=[px_, py_], to=[x, y], map_load=True)); continue
        if t - sc - camseg[-1]['t1'] <= 2 and not camseg[-1].get('initial') and not camseg[-1].get('map_load'):
            camseg[-1]['t1'] = t - sc; camseg[-1]['to'] = [x, y]
        else:
            camseg.append(dict(t0=t - sc, t1=t - sc, frm=[px_, py_], to=[x, y]))
    camseg = [c for c in camseg if not in_world(c['t0'])]
    for c in camseg:
        c['s0'] = sec(c['t0']); c['frames'] = c['t1'] - c['t0'] + 1
    misc = [e for e in w.events if e['kind'] == 'misc' and e['t'] <= lim]
    screen = []
    vm_states = []
    fade_runs = []
    prev = None
    for e in misc:
        if e['t'] < sc - 1:
            prev = e; continue
        if prev is None: prev = e; continue
        T = e['t'] - sc
        if (e['E2'] & 4) != (prev['E2'] & 4): screen.append(dict(t=T, s=sec(T), what='flash_on' if e['E2'] & 4 else 'flash_off'))
        if (e['E2'] & 8) != (prev['E2'] & 8): screen.append(dict(t=T, s=sec(T), what='camera_recentre_start' if e['E2'] & 8 else 'camera_recentre_done'))
        if e['E6'] != prev['E6']: fade_runs.append((T, prev['E6'], e['E6']))
        if (e['F1'] & 0x80) != (prev['F1'] & 0x80): screen.append(dict(t=T, s=sec(T), what='world_freeze_on' if e['F1'] & 0x80 else 'world_freeze_off'))
        if (e['D9'] & 0x80) != (prev['D9'] & 0x80): screen.append(dict(t=T, s=sec(T), what='pad_locked' if e['D9'] & 0x80 else 'pad_released'))
        if (e['CFFF'] & 1) != (prev['CFFF'] & 1): screen.append(dict(t=T, s=sec(T), what='boss_freeze_flag_set' if e['CFFF'] & 1 else 'boss_freeze_flag_cleared'))
        if e['X49'] != prev['X49']: screen.append(dict(t=T, s=sec(T), what='jitter_byte_49', value=e['X49']))
        if e['X2A'] != prev['X2A']: screen.append(dict(t=T, s=sec(T), what='palette_fade_mode_2A', value=e['X2A'], target_010C='0x%04X' % e['W10C']))
        if (e['E2'] & 0x10) != (prev['E2'] & 0x10): screen.append(dict(t=T, s=sec(T), what='colour_effect_on' if e['E2'] & 0x10 else 'colour_effect_off'))
        if (e['E2'] & 2) != (prev['E2'] & 2): screen.append(dict(t=T, s=sec(T), what='mosaic_on' if e['E2'] & 2 else 'mosaic_off'))
        if e['D0'] != prev['D0']: vm_states.append(dict(t=T, s=sec(T), d0=e['D0'], prev=prev['D0']))
        prev = e
    fades = []
    for t, a, b in fade_runs:
        if fades and t - fades[-1]['t1'] <= 4 and (b - a) == fades[-1]['dir']:
            fades[-1]['t1'] = t; fades[-1]['to'] = b
        else:
            fades.append(dict(t0=t, t1=t, frm=a, to=b, dir=b - a))
    for f in fades:
        f['s0'] = sec(f['t0']); f['frames'] = f['t1'] - f['t0'] + 1; f['kind'] = 'fade_in' if f['dir'] > 0 else 'fade_out'
    # palette fade ($2A != 0): per-step values of $010A while it runs
    pal = []
    run = None
    for e in misc:
        if e['t'] < sc - 1: continue
        T = e['t'] - sc
        tgt = '0x%04X' % e['W10C']
        if run is not None and (not e['X2A'] or tgt != run['target'] or e['X2A'] != run['mode'] or (run['steps'] and e['W10A'] < run['steps'][-1][1])):
            run['t1'] = T; run = None
        if e['X2A'] and run is None:
            run = dict(t0=T, mode=e['X2A'], target=tgt, steps=[]); pal.append(run)
        if run is not None and e['W10A'] is not None and (not run['steps'] or run['steps'][-1][1] != e['W10A']): run['steps'].append((T, e['W10A']))
    for p_ in pal:
        p_['frames'] = (p_.get('t1', p_['steps'][-1][0] if p_['steps'] else p_['t0']) - p_['t0'])
        p_['final_010A'] = '0x%04X' % p_['steps'][-1][1] if p_['steps'] else None
        p_['n_steps'] = len(p_['steps']); p_['t_last_step'] = p_['steps'][-1][0] if p_['steps'] else None; del p_['steps']
    flags = [dict(t=e['t'] - sc, s=sec(e['t'] - sc), flag=e['idx'], old=e['old'], new=e['new']) for e in w.events if e['kind'] == 'flag' and sc <= e['t'] <= lim]
    end_ops = [r for r in vm if r['name'] == 'END']
    initial = {k: v for k, v in (next((m for m in misc if m['t'] >= sc - 1), misc[0]).items()) if k not in ('t', 'kind')} if misc else {}
    summary = dict(total_frames=t_end, total_s=sec(t_end), vm_ops=len(vm), dialogs=len(dialogs), map_loads=([dict(t=0, map=initial_map)] if initial_map else []) + loads, leader=leader,
                   end_op_t=end_ops[-1]['t'] if end_ops else None)
    if world: extra = dict(extra or {}, world_mode_intervals=[dict(t0=a, t1=b, frames=b - a) for a, b in world])
    rep = dict(source='tools/event_runs.py %s (real 65816 code stepped frame by frame; PPU/APU not emulated)' % name, clock=dict(frame_hz=HZ, vm_tick_frames=5, vm_hz=round(HZ / 5, 3)),
               conditions=conds, summary=summary, initial_state=initial, entries=entries, vm=vm, dialogs=dialogs, sounds=sounds, objects=objs, camera=camseg,
               fades=fades, palette_fades=pal, screen=screen, flags=flags, vm_states=vm_states)
    if extra: rep.update(extra)
    return rep


def unwrap(ser, camsz, resets=()):
    """Positions of an object that crosses the map edge (the map wraps) made continuous: x and y are shifted by multiples of the map size."""
    out = []
    prev = None
    ox = oy = 0
    for t, s in ser:
        if s is None or t in resets:
            prev = None; ox = oy = 0
            if s is None:
                out.append((t, s)); continue
        mw, mh = 576, 640
        for ct, w_, h_ in camsz:
            if ct <= t: mw, mh = w_, h_
        s2 = dict(s)
        if prev is not None:
            if s['x'] + ox - prev[0] > mw // 2: ox -= mw
            elif s['x'] + ox - prev[0] < -(mw // 2): ox += mw
            if s['y'] + oy - prev[1] > mh // 2: oy -= mh
            elif s['y'] + oy - prev[1] < -(mh // 2): oy += mh
        s2['x'] = s['x'] + ox; s2['y'] = s['y'] + oy
        prev = (s2['x'], s2['y'])
        out.append((t, s2))
    return out


def boss_series(w, sc, boss_id, t_from=None, t_to=None):
    """Phase changes of the boss-engine object with id `boss_id` (first slot found), from the observer log; the first position change inside a phase is logged too."""
    out = []
    last = None
    pos_seen = set()
    for e in w.events:
        if e['kind'] == 'obj' and e['s'] and e['s']['id'] == boss_id:
            if (t_from is not None and e['t'] < t_from) or (t_to is not None and e['t'] > t_to): continue
            s = e['s']
            ph = (s['f94'], s['f98'])
            if ph != last:
                out.append(dict(t=e['t'] - sc, slot=e['slot'], phase94=s['f94'], flags98='0x%04X' % s['f98'], engine_x=s['f2b'], engine_y=s['f32'], age96=s['f96'], state7A=s['f7a']))
                pos_seen = {(s['f2b'], s['f32'])}
            elif (s['f2b'], s['f32']) not in pos_seen and len(pos_seen) < 2:
                out.append(dict(t=e['t'] - sc, slot=e['slot'], phase94=s['f94'], flags98='0x%04X' % s['f98'], engine_x=s['f2b'], engine_y=s['f32'], age96=s['f96'], state7A=s['f7a'], note='first position change in the phase'))
                pos_seen.add((s['f2b'], s['f32']))
            last = ph
    return out


# ----------------------------------------------------------------------------------------------------- scenarios
def timeline_md(rep, sc_label='frame'):
    rows = []
    vm = rep['vm']
    dn = 0
    i = 0
    while i < len(vm):
        r = vm[i]
        if r['op'] == 'TEXT':
            n0 = dn + 1
            j = i
            cnt = 0
            while j < len(vm) and (vm[j]['op'] == 'TEXT' or (vm[j]['name'] == 'WAIT' and vm[j]['params']['wait_press'])):
                if vm[j]['op'] == 'TEXT': cnt += 1
                j += 1
            t_next = vm[j]['t'] if j < len(vm) else rep['summary']['total_frames']
            dn += cnt
            rows.append((r['t'], 'dialog', '%d text block%s (#%d-#%d, %s ...), each followed by a wait for a button where the script has one; next command at frame %d' % (
                cnt, 's' if cnt != 1 else '', n0, dn, r['addr'], t_next)))
            i = j
            continue
        i += 1
        if r['name'] in ('WAIT_IDLE', 'RETURN'): continue
        rows.append((r['t'], 'VM %s+%04X' % (r['event'], r['offset']), vm_text2(r['name'], r.get('params', {}))))
    for k, o in rep['objects'].items():
        auto = collections.defaultdict(list)
        for m in o['moves']:
            if not m['cause'] and o['slot'] >= 3:
                auto[m['id']].append(m); continue
            prof = ' '.join('%dx(%+d,%+d)' % tuple(x) for x in m['profile'])
            rows.append((m['t0'], '%s (id 0x%02X)' % (k, m['id'] or 0), 'walk %s -> %s, %d frames, %.1f px/s, facing %s, anim %s, per-frame %s%s' % (
                tuple(m['frm']), tuple(m['to']), m['frames'], m['px_per_s'], '/'.join(m['facing']), m['anim'], prof, ' [%s]' % m['cause'] if m['cause'] else '')))
        for oid, ms in auto.items():
            xs = [v for m in ms for v in (m['frm'][0], m['to'][0])]; ys = [v for m in ms for v in (m['frm'][1], m['to'][1])]
            rows.append((ms[0]['t0'], '%s (id 0x%02X)' % (k, oid or 0), 'autonomous movement of the object (its own AI, no VM command): %d segments, frames %d-%d, x %d..%d, y %d..%d' % (
                len(ms), ms[0]['t0'], ms[-1]['t1'], min(xs), max(xs), min(ys), max(ys))))
        for f in o['facing'][1:]:
            if any(m['t0'] <= f['t'] <= m['t1'] + 1 for m in o['moves']): continue
            rows.append((f['t'], k, 'facing %s (0x%02X)' % (f['facing'], f['code'])))
        for p_ in o['pose']:
            rows.append((p_['t'], k, 'pose idle' if p_['anim'] == 'idle' else 'pose state 0x%02X anim 0x%02X' % (p_['state'], p_['anim'])))
        for pr_ in o['presence']:
            if pr_['t'] <= 0: continue
            rows.append((pr_['t'], k, ('appears id 0x%02X at (%s,%s)' % (pr_['id'], pr_['x'], pr_['y'])) if pr_['on'] else 'removed'))
        for v in o['visibility'][1:]:
            rows.append((v['t'], k, 'obj+0x0E = 0x%02X' % v['obj0E']))
    for c in rep['camera']:
        if c.get('initial'): continue
        if c.get('map_load'): rows.append((c['t0'], 'camera', 'set by the map loader to %s' % (tuple(c['to']),)))
        else: rows.append((c['t0'], 'camera', 'scroll %s -> %s, %d frames' % (tuple(c['frm']), tuple(c['to']), c['frames'])))
    for f in rep['fades']:
        rows.append((f['t0'], 'screen', '%s brightness %d -> %d, %d frames' % (f['kind'], f['frm'], f['to'], f['frames'])))
    for x in rep['screen']:
        if x['what'] in ('pad_locked', 'pad_released', 'world_freeze_on', 'world_freeze_off') and False: continue
        extra = ''
        if 'value' in x: extra = ' %s' % x['value']
        if 'target_010C' in x: extra += ' (target word $010C = %s)' % x['target_010C']
        rows.append((x['t'], 'engine', x['what'] + extra))
    for x in rep['sounds']:
        rows.append((x['t'], 'sound', '%s id 0x%02X (cmd %d, params 0x%02X 0x%02X) from %s' % (x['kind'], x['id'], x['cmd'], x['p2'], x['p3'], x['source'])))
    for f in rep['flags']:
        rows.append((f['t'], 'flag', 'flag 0x%02X %d -> %d' % (f['flag'], f['old'], f['new'])))
    for l in rep['summary']['map_loads']:
        rows.append((l['t'], 'engine', 'map %d loaded' % l['map']))
    return sorted(rows, key=lambda r: r[0])


def print_md(rep):
    print('| frame | s | object | what |'); print('|---|---|---|---|')
    for t, who, what in timeline_md(rep):
        print('| %d | %.3f | %s | %s |' % (t, t / HZ, who, what))


def run_intro(rom, state, leader=0, after=600, weapons=None):
    w = Runner(rom, state)
    w.set_leader(leader)
    if weapons:
        for h, t in enumerate(weapons):
            row = t * 9 + 7
            for off, v in ((0x1E3, row), (0x1E4, t), (0x1E8, row)): w.c.wram[0xE000 + 0x200 * h + off] = v
    first_map = w.w16(0xDC)
    w.t_scene = w.t
    w._observe()
    sc = w.t
    w.start_event(0x429)
    ok = w.run_until_idle()
    t_end = w.t - sc
    for _ in range(after): w.frame()
    return w, sc, t_end, first_map, ok


class Raw:
    """What build_report needs from a run: the ROM, the observer log and the VM command log."""
    def __init__(self, rom, events, vm_ops): self.rom = rom; self.events = events; self.vm_ops = vm_ops


def save_raw(path, w, meta):
    import pickle
    pickle.dump(dict(events=w.events, vm_ops=w.vm_ops, meta=meta), open(path, 'wb'))


def report_from_raw(rom, path):
    import pickle
    d = pickle.load(open(path, 'rb'))
    m = d['meta']
    raw = Raw(rom, d['events'], d['vm_ops'])
    extra = {}
    if m['kind'] == 'intro':
        extra = dict(boss=boss_series(raw, m['sc'], 0x7F), after_control_sounds=[dict(t=e['t'] - m['sc'], cmd=e['cmd'], id=e['arg1'], p2=e['arg2'], p3=e['arg3'])
                                                                                   for e in raw.events if e['kind'] == 'sound' and e['t'] - m['sc'] > m['t_end']])
        return build_report(rom, raw, m['sc'], m['t_end'], 'intro', m['conds'], m['leader'], first_map=m['first_map'], extra=extra)
    m['conds']['t0'] = 'frame in which the Mana Beast phase variable becomes 0x12 (the tick of phase 0xB that sees the dead bit; the dead bit was set by hand %d frames after control returned in the arena)' % (m['t_dead'] - m.get('t_ctrl', m['t_dead'] - 10))
    extra = dict(boss=boss_series(raw, m['sc'], 0x7F, m['t_dead'], m['t_stop']), event_start_t=m['ev_start'] - m['sc'] if m['ev_start'] else None,
                 restart_t=(m['restarted'] - m['sc']) if m['restarted'] else None)
    return build_report(rom, raw, m['sc'], m['t_end'], 'ending', m['conds'], m['leader'], first_map=m['first_map'], extra=extra)


def ending_report(rom, state, leader=0, dead=10, frames=60000, verbose=False, snap_path=None, resume=None):
    first12 = None
    if resume:
        w = Runner(rom, state)
        meta = w.load_snapshot(resume)
        first12 = w.t; t_dead = meta['t_dead']; t_ctrl = meta['t_ctrl']; first_map = meta['first_map']; slot = meta['slot']; leader = meta['leader']
        n_ops = meta['n_ops']
    else:
        w, sc0, t_end0, first_map, ok = run_intro(rom, state, leader, 0)
        w.refill = True
        t_ctrl = w.t
        for _ in range(dead): w.frame()
        slot = next(sl for sl in range(Runner.SLOTS) if w.snap(sl) and w.snap(sl)['id'] == 0x7F)
        b = 0xE000 + 0x200 * slot
        w.c.wram[b + 0x191] |= 0x80
        t_dead = w.t
        n_ops = len(w.vm_ops)
    ev_start = None
    stuck_key = None; stuck_t = 0
    reason = 'frames'
    if resume and first12 is not None and len(w.vm_ops) > n_ops: ev_start = w.vm_ops[n_ops]['t']
    while w.t - t_dead < frames:
        w.frame()
        if w.restarted: reason = 'restart'; break
        s_ = w.snap(slot)
        if first12 is None and s_ and s_['f94'] == 0x12:
            first12 = w.t
            if snap_path: w.save_snapshot(snap_path, dict(t_dead=t_dead, t_ctrl=t_ctrl, first_map=first_map, slot=slot, leader=leader, n_ops=n_ops)); print('snapshot saved', w.t, file=sys.stderr, flush=True)
        if ev_start is None and len(w.vm_ops) > n_ops: ev_start = w.vm_ops[n_ops]['t']
        if verbose and w.t % 1000 == 0:
            print('t', w.t, 'D0', w.c.wram[0xD0], 'map', w.w16(0xDC), 'ops', len(w.vm_ops), file=sys.stderr, flush=True)
        if ev_start is not None:
            c = w.c.wram
            key = (c[0xD0], c[0xD1], c[0xD2], c[0xD3], w.w16(0xDC))
            if key == stuck_key and c[0xD0] not in (0x82, 0x83, 0x81):
                if w.t - stuck_t > 3000: reason = 'stuck'; break
            else:
                stuck_key = key; stuck_t = w.t
            if c[0xD0] == 0 and not any(e['kind'] == 'map_load' and e['t'] >= w.t - 3 for e in w.events[-8:]):
                reason = 'idle'; break
    return w, first12, t_dead, t_ctrl, first_map, slot, ev_start, reason


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 1
    rom = romio.load(argv[1])
    if argv[2] == 'decode2':
        for e in argv[3:]:
            ev = int(e, 16)
            bank, out = decode2(rom, ev)
            print('event %03X bank %02X' % (ev, bank))
            for r in out:
                if r['op'] == 'TEXT': print('  %04X TEXT %d bytes%s' % (r['off'], r['bytes'], ' (credits block 0x7D..0x7E)' if r['credits'] else ''))
                else: print('  %04X %s %-16s %s' % (r['off'], r['op'], r['name'], r['params'] or ''))
        return 0
    if argv[2] == 'md':
        print_md(json.load(open(argv[3])))
        return 0
    if argv[2] == 'report':
        rep = report_from_raw(rom, argv[3])
        json.dump(rep, open(argv[4], 'w'), indent=1)
        print('wrote', argv[4], 'frames', rep['summary']['total_frames'])
        return 0
    state = argv[2]; cmd = argv[3]
    kv = dict(a.split('=', 1) for a in argv[4:] if '=' in a)
    pos = [a for a in argv[4:] if '=' not in a]
    leader = int(kv.get('leader', 0))
    if cmd == 'intro':
        w, sc, t_end, first_map, ok = run_intro(rom, state, leader, int(kv.get('after', 600)), [int(x) for x in kv['weapons'].split(',')] if 'weapons' in kv else None)
        meta = dict(kind='intro', sc=sc, t_end=t_end, first_map=first_map, leader=leader,
                    conds=dict(start_event='0x429', start_state_map=first_map, flags={'4E': w.c.wram[0xCF4E]}, leader=leader,
                               hero_weapon_types=[w.c.wram[0xE000 + 0x200 * h + 0x1E4] for h in range(3)], completed=ok,
                               t0='frame in which event 0x429 was started in the map-246 state (the VM first steps in frame 3)'))
        raw = kv.get('raw') or pos[0] + '.raw.pkl'
        save_raw(raw, w, meta)
        rep = report_from_raw(rom, raw)
        json.dump(rep, open(pos[0], 'w'), indent=1)
        print('wrote', pos[0], 'frames', rep['summary']['total_frames'])
        if kv.get('md'): print_md(rep)
        return 0
    if cmd == 'ending':
        w, first12, t_dead, t_ctrl, first_map, slot, ev_start, reason = ending_report(rom, state, leader, int(kv.get('dead', 10)), int(kv.get('frames', 60000)), verbose=True,
                                                                                         snap_path=kv.get('snap'), resume=kv.get('resume'))
        print('stop reason', reason, 'frame', w.t, 'first12', first12, 'event start', ev_start, file=sys.stderr)
        meta = dict(kind='ending', sc=first12, t_end=w.t - first12, first_map=253, leader=leader, t_dead=t_dead, t_ctrl=t_ctrl, t_stop=w.t, ev_start=ev_start, restarted=w.restarted,
                    conds=dict(start_event='0x42F (started by the end of the Mana Beast object)', start_state_map=first_map, flags={'4E': 8}, leader=leader,
                               hero_weapon_types=[w.c.wram[0xE000 + 0x200 * h + 0x1E4] for h in range(3)], stop_reason=reason,
                               t0='first tick of Mana Beast phase 0x12 (the dead bit was set by hand %d frames after control returned in the arena)' % int(kv.get('dead', 10))))
        raw = kv.get('raw') or pos[0] + '.raw.pkl'
        save_raw(raw, w, meta)
        rep = report_from_raw(rom, raw)
        json.dump(rep, open(pos[0], 'w'), indent=1)
        print('wrote', pos[0], 'frames', rep['summary']['total_frames'])
        if kv.get('md'): print_md(rep)
        return 0
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))

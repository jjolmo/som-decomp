"""Dark Lich hands phase and phase statistics, measured on the whole game frame (lich_sim.Sim).
usage:
  lich_hands.py ROM STATE anims                      frame lists and lengths of the animations the Lich states use (static decode of the ROM)
  lich_hands.py ROM STATE trace SEED FRAMES [natural|none|spread]
                                                     one line per state entry (kind of entry, ticks, movement, boxes, attack rows, hits)
  lich_hands.py ROM STATE restat EVENTS.json[,EVENTS2.json] OUT.json SETTING FRAMES [FIRST_SEED_INDEX]   aggregate again from saved events
  lich_hands.py ROM STATE hurt [OUT.json]            inject the party-hit flag in chosen states (what the Lich does next)
  lich_hands.py ROM STATE force [OUT.json]           states 22 / 27: heroes moved below / above the Lich while the hands are raised
  lich_hands.py ROM STATE build OUT.json name=file...   assemble data/dark_lich_hands.json from stats / hurt / force outputs
  lich_hands.py ROM STATE stats SEEDS FRAMES OUT.json [natural|none|spread] [EVENTS.json] [FIRST_SEED_INDEX]  (seed of run i = 7*i+1)
                                                     SEEDS runs of FRAMES frames in parallel; writes the aggregate as JSON
'natural': the three heroes start next to the Lich and the party's own weapon hits are enabled (the game's party AI fights).
'none': heroes far away and their weapon hits switched off (the setting of the earlier measurements).
'spread': like 'none' but the heroes stand at seed-dependent places around the Lich (every direction code occurs).
Lich HP is refilled when it drops below 2000 so that the fight never ends; heroes are immortal (Sim default).
Tick = 5 frames (the engine runs when $56 = 0); frame f runs the tick when f % 5 == 0."""
import sys, os, random, copy, json, struct, collections, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, lich_sim

FPS = 60.0988
ANIM_TABLE = 0x1B0000 + 0xF9A8          # $DB:F9A8, 2-byte pointers into bank C1
OBJ = 0xE600                            # Lich object (slot 0 of the boss objects)


def anim_frames(rom, aid):
    """Walk one animation script: entries are 3 bytes (frame record pointer lo, hi, delay in ticks) or odd command bytes.
    Returns (list of (frame_pointer, delay), terminator) where terminator is 'loop' (command 0x1A) or 'end' (delay 0)."""
    p = 0x10000 + struct.unpack_from('<H', rom, ANIM_TABLE + 2 * aid)[0]
    out = []
    while True:
        b = rom[p]
        if b & 1:                                    # command byte
            op = b & 0xFE
            if op == 0x1A: return out, 'loop'
            if op == 0x0C: p += 3; continue         # offset command: two argument bytes
            return out, 'cmd%02X' % op
        ptr = rom[p] | rom[p + 1] << 8; dl = rom[p + 2]
        out.append((ptr, dl)); p += 3
        if dl == 0: return out, 'end'


def cmd_anims(rom):
    names = {0xE8: 'body stand/walk', 0xE9: 'body stand/walk (flipped set)', 0xEA: 'body hurt', 0xF4: 'hands idle', 0xF5: 'hands raise (state 20)',
             0xF6: 'hands raised idle (21, 22, 27)', 0xF7: 'hands hurt (25)', 0xF8: 'hands lower (23)', 0xF9: 'hands slam (24)'}
    res = {}
    for aid, nm in names.items():
        fr, term = anim_frames(rom, aid)
        res[aid] = dict(name=nm, frames=len(fr), delays=[d for _, d in fr], first_frame='CA:%04X' % fr[0][0] if fr else None,
                        last_frame='CA:%04X' % fr[-1][0] if fr else None, ticks_to_end=sum(d for _, d in fr), terminator=term)
        print('anim %02X %-32s frames=%d delays=%s sum=%d ticks end=%s  frame pointers CA:%04X..CA:%04X' % (
            aid, nm, len(fr), [d for _, d in fr], sum(d for _, d in fr), term, min(p for p, _ in fr), max(p for p, _ in fr)))
    return res


def spread_heroes(c, seed):
    """Static heroes at seed-dependent places around the Lich: covers every direction code."""
    rnd = random.Random(seed)
    for h in range(3):
        c.wr16(0x7EE000 + 0x200 * h + 2, 288 + rnd.randint(-200, 200)); c.wr16(0x7EE000 + 0x200 * h + 4, 336 + rnd.randint(-120, 160))


class Run:
    def __init__(self, rom, state, seed, natural, spread=False):
        self.s = s = lich_sim.Sim(rom, state, rng_index=seed, hero_hits=natural)
        c = s.c; self.c = c
        if natural:
            for h, dx in enumerate((-20, 0, 20)):
                c.wr16(0x7EE000 + 0x200 * h + 2, 288 + dx); c.wr16(0x7EE000 + 0x200 * h + 4, 335 + 40)
        elif spread: spread_heroes(c, seed)
        s.spawn()
        self.cur = None; self.events = []; self.rows = []; self.casts = []; self.spawns = []; self.handler = None
        def rec_state(cp):
            if cp.X != OBJ: return False
            self.begin(cp.A & 0xFF); return False
        c.hooks[0xC2377A] = rec_state
        def mk(name):
            def h(cp):
                if cp.X == OBJ: self.handler = name
                return False
            return h
        c.hooks[0xC26DFB] = mk('chooser'); c.hooks[0xC26E82] = mk('action'); c.hooks[0xC26EBA] = mk('hurt')
        def row(cp): self.rows.append(cp.A & 0xFFFF); return False
        c.hooks[0xC0006C] = lambda cp: (self.rows.append(cp.A & 0xFFFF), rtl(cp))[1]
        def rtl(cp): cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True
        self.hp = s.r16(0x182)
        self.pending_hit = []; self.flashes = []; self.flash_on = None; self.t175 = None

    def snap(self):
        s = self.s
        return dict(f=s.f, x=s.r16(0x2B), y=s.r16(0x32), mode=s.r16(0x82), f7e=s.r16(0x7E), ad=s.r16(0xAD), thr=s.r16(0x2D),
                    age=s.r16(0x96), dur=s.r16(0x14), anim=s.r16(0x9A))

    def begin(self, st):
        s = self.s; sn = self.snap()
        self.finish(sn)
        self.cur = dict(state=st, f0=s.f, mode=sn['mode'], kind=(self.handler or 'script'), f7e0=sn['f7e'], ad0=sn['ad'], thr=sn['thr'], x0=sn['x'], y0=sn['y'],
                        rows=[], dirc=s.r8(0xAB) if self.handler == 'chooser' else None, hb_ticks=0, atk_ticks=0, ticks=0, dxs=collections.Counter(), dys=collections.Counter(), hits=[], hurtbox=None, lastxy=(sn['x'], sn['y']))
        self.rows = []; self.handler = None
        self.cur['rows'] = self.rows

    def finish(self, sn):
        if not self.cur: return
        c = self.cur; s = self.s
        c['f1'] = s.f; c['ticks'] = (s.f - c['f0']) / 5.0; c['x1'] = sn['x']; c['y1'] = sn['y']; c['f7e1'] = sn['f7e']
        c['dxs'] = dict(c['dxs']); c['dys'] = dict(c['dys']); del c['hurtbox']
        self.events.append(c)

    def step(self):
        s = self.s; c = self.c
        s.frame()
        sn = self.snap()
        cur = self.cur
        if cur is not None:
            dx = sn['x'] - cur['lastxy'][0]; dy = sn['y'] - cur['lastxy'][1]
            if dx: cur['dxs'][dx] += 1
            if dy: cur['dys'][dy] += 1
            cur['lastxy'] = (sn['x'], sn['y'])
            hb = (s.r16(0xCA) | s.r16(0xCE)) != 0
            if hb: cur['hb_ticks'] += 1
            if s.r16(0xC2) != 0: cur['atk_ticks'] += 1
        f60 = s.r8(0x60) == 0x40
        if f60 and self.flash_on is None: self.flash_on = s.f
        if not f60 and self.flash_on is not None: self.flashes.append((self.flash_on, s.f - self.flash_on)); self.flash_on = None
        hp = s.r16(0x182)
        if hp < self.hp:
            h = dict(f=s.f, damage=self.hp - hp, state=s.r8(0x7A), mode=sn['mode'], f7e=sn['f7e'], ad=sn['ad'])
            self.pending_hit.append(h)
            if cur is not None: cur['hits'].append(h)
        self.hp = hp
        if hp < 2000:
            s.w16(0x182, 6666); self.hp = 6666
        return sn


def run_trace(rom, state, seed, frames, natural, spread=False):
    r = Run(rom, state, seed, natural, spread)
    try:
        for _ in range(frames): r.step()
    except Exception as ex:                       # the interpreter does not implement every opcode: keep what was recorded
        print('seed %d stopped at frame %d: %s' % (seed, r.s.f, ex), file=sys.stderr, flush=True)
    r.finish(r.snap())
    r.events.append(dict(kind='meta', state=-1, flashes=r.flashes))
    return r.events


def cmd_trace(rom, state, seed, frames, mode):
    ev = run_trace(rom, state, seed, frames, mode == 'natural', mode == 'spread')
    for e in ev:
        if e['kind'] == 'meta': print('flash marker (start frame, frames until cleared):', e['flashes']); continue
        print('f=%6d %-7s st=%02X mode=%d ad=%3d 7E %04X->%04X ticks=%5.1f pos (%d,%d)->(%d,%d) dy%s dx%s rows=%s hb=%d/%d atk=%d hits=%s' % (
            e['f0'], e['kind'], e['state'], e['mode'], e['ad0'], e['f7e0'], e['f7e1'], e['ticks'], e['x0'], e['y0'], e['x1'], e['y1'],
            e['dys'], e['dxs'], e['rows'], e['hb_ticks'], e['ticks'] * 5, e['atk_ticks'], [(h['damage']) for h in e['hits']]))


def reach(rom, state, seed, target, limit=14000):
    """Run the whole game frame until the Lich is in state TARGET (past its first tick, in action or movement mode); returns the Sim."""
    s = lich_sim.Sim(rom, state, rng_index=seed); spread_heroes(s.c, seed); s.spawn()
    for _ in range(limit):
        s.frame()
        if s.r8(0x7A) == target and s.r16(0x96) >= 1 and s.r16(0x82) in (0, 1) and s.f % 5 == 1: return s
    return None


def capture(rom, state, seed, targets, limit=16000):
    """One pass of the whole game frame; returns {state: Sim copy} taken the first time each target state is active (past its first tick)."""
    s = lich_sim.Sim(rom, state, rng_index=seed); spread_heroes(s.c, seed); s.spawn()
    got = {}
    for _ in range(limit):
        s.frame()
        st = s.r8(0x7A)
        if st in targets and st not in got and s.r16(0x96) >= 1 and s.r16(0x82) in (0, 1) and s.f % 5 == 1:
            got[st] = copy.deepcopy(s)
            if len(got) == len(targets): break
    return got


def inject(s0):
    """Copy the simulation and inject a hit flag (obj+$34 bit 0, what the party hit sets at $C2:0F6D; no damage, no hit marker).
    Returns the Lich's state, mode and bit 15 at the time, and the following (frames after the hit, state, mode) changes."""
    s = copy.deepcopy(s0); t0 = s.f; start = (s.r8(0x7A), s.r16(0x82), s.r16(0x7E))
    s.w8(0x34, s.r8(0x34) | 1)
    out = []; last = None
    for _ in range(900):
        s.frame(); k = (s.r8(0x7A), s.r16(0x82))
        if k != last: out.append((s.f - t0, '%02X' % k[0], k[1])); last = k
        if len(out) >= 5: break
    return dict(state='%02X' % start[0], mode=start[1], flags7e='%04X' % start[2], following=out)


def cmd_hurt(rom, state, out=None):
    """Hit flag injected into every state of the hands phase (and a few body states), in the mode the state runs in."""
    targets = {0x1E, 0x20, 0x21, 0x23, 0x24, 0x26, 0x18, 0x19, 0x1B, 0x02, 0x00}      # 22 and 27 are injected by `force`
    res = []; done = set()
    for seed in (1, 8):
        for st, s0 in sorted(capture(rom, state, seed, targets - done).items()):
            r = inject(s0); r['seed'] = seed; res.append(r); done.add(st); print(r, flush=True)
        if done >= targets: break
    print('not captured:', sorted('%02X' % x for x in targets - done))
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


def parse_script(rom, addr):
    import statescript
    p = 0x20000 + addr; out = []
    while True:
        op = rom[p]
        if op == 0xFF: return out
        info = statescript.OPS[op]; name, n = info[0], info[1]
        if len(info) > 2: args = list(rom[p + 1:p + 1 + n]); ln = 1 + n
        else: args = [struct.unpack_from('<H', rom, p + 1 + 2 * i)[0] for i in range(n)]; ln = 1 + 2 * n
        out.append([name] + args); p += ln
        if name == 'JUMP': return out


def cmd_build(rom, out, parts):
    """Assemble data/dark_lich_hands.json: static decode of the hands scripts, animations, selection tables and the measured JSON files.
    PARTS = name=file pairs, e.g. none=statsA.json spread=statsS.json natural=statsN.json hurt=hurt.json"""
    d = dict(source='tools/lich_hands.py (build) from the ROM and the runs named in measured_runs; tick = 5 frames = 83.2 ms (12.02 Hz); seconds = frames / 60.0988; docs/dark-lich-hands.md',
             tick_rate_hz=12.02, frames_per_tick=5)
    scripts = {}
    for i in list(range(0x1E, 0x28)) + [0x07, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D]:
        a = struct.unpack_from('<H', rom, 0x2E896 + 2 * i)[0]
        scripts['%02X' % i] = [' '.join(['%s' % x if isinstance(x, str) else '%04X' % x for x in op]) for op in parse_script(rom, a)]
    d['state_scripts'] = scripts
    d['state_meaning_and_entry'] = {
        '1E': 'hands idle (low); chooser, bit 15 clear, direction 0/2, rand(0..1)=0', '1F': 'hands move +y; chooser, bit 15 clear, direction 1',
        '20': 'hands rise, sets bit 15; chooser, bit 15 clear, direction 0/2, rand(0..1)=1', '21': 'raised idle; chooser, bit 15 set, direction 0/2, rand(0..1)=0',
        '22': 'raised, move +y; chooser, bit 15 set, direction 1', '23': 'hands lower, clears bit 15; chooser, bit 15 set, direction 0/2, rand(0..1)=1',
        '24': 'slam (the hands action); action routine, bit 15 clear, AD >= threshold', '25': 'hurt (hands); hit flag consumed in mode 1 with bit 0 of 7E set',
        '26': 'hands move -y; chooser, bit 15 clear, direction 3', '27': 'raised, move -y; chooser, bit 15 set, direction 3', '07': 'hurt (body); hit flag consumed in mode 1 with bit 0 of 7E clear'}
    d['animations'] = {'%02X' % k: v for k, v in cmd_anims(rom).items()}
    tb = lambda b, n: ['%04X' % struct.unpack_from('<H', rom, 0x1C0000 + b + 2 * i)[0] for i in range(n)]
    d['selection_tables'] = dict(hands_bit15_clear_by_direction_E479=tb(0xE479, 4), hands_bit15_clear_random_E471=tb(0xE471, 2),
                                 hands_bit15_set_by_direction_E481=tb(0xE481, 4), hands_bit15_set_random_E475=tb(0xE475, 2),
                                 note='values are state sequence addresses in bank C2: E864=1E E866=1F E868=20 E86A=21 E86C=22 E86E=23 E870=26 E872=27 E894=24 E860=1B-1C-1D E84C=25 E84A=07; direction code 0 right, 1 down, 2 left, 3 up')
    runs = {}
    pooled_states = {}
    for part in parts:
        k, f = part.split('=', 1); runs[k] = json.load(open(f))
    d['measured_runs'] = {k: {x: v[x] for x in ('setting', 'seeds', 'frames_per_seed', 'total_seconds') if x in v} for k, v in runs.items() if isinstance(v, dict)}
    for k, v in runs.items():
        if isinstance(v, dict) and 'states' in v: d['scenario_' + k] = {x: v[x] for x in v if x not in ('setting',)}
        else: d['experiment_' + k] = v
    import lich_hands_model as M
    model = {}
    for name, pb, ph in (('rule_20_percent', 0.2, 0.2), ('measured_rates_0.21_0.223', 0.21, 0.223)):
        b, h = M.simulate(200000, 0.15, random.Random(1), pb, ph)
        model[name] = dict(phases=200000, direction_1_or_3_share=0.15,
                           body=dict(seconds_mean=round(sum(t for t, _ in b) / len(b) * 5 / FPS, 2), actions_mean=round(sum(a for _, a in b) / len(b), 3)),
                           hands=dict(seconds_mean=round(sum(t for t, _ in h) / len(h) * 5 / FPS, 2), actions_mean=round(sum(a for _, a in h) / len(h), 3)))
    d['rule_model_tools_lich_hands_model_py'] = model
    summ = {}
    for st in d['state_meaning_and_entry']:
        hist = collections.Counter(); n = 0; hb = atk = 0.0; dy = collections.Counter(); prev = collections.Counter(); nxt = collections.Counter()
        for k in ('none', 'spread', 'natural'):
            v = d.get('scenario_' + k, {}).get('states', {}).get(st)
            if not v: continue
            n += v['n']; hb += v['hurtbox_fraction_of_frames'] * v['n']; atk += v['attack_box_fraction_of_frames'] * v['n']
            for a, c in v['ticks_hist'].items(): hist[float(a)] += c
            for a, c in v['per_frame_dy'].items(): dy[a] += c
            for a, c in v['previous_state'].items(): prev[a] += c
            for a, c in v['next_state'].items(): nxt[a] += c
        if n:
            tk = sum(a * c for a, c in hist.items()) / n
            summ[st] = dict(n=n, ticks_min=min(hist), ticks_mean=round(tk, 2), ticks_max=max(hist), seconds_min=round(min(hist) * 5 / FPS, 3), seconds_mean=round(tk * 5 / FPS, 3),
                            seconds_max=round(max(hist) * 5 / FPS, 3), ticks_hist=dict(sorted(hist.items())), hurtbox_fraction_of_frames=round(hb / n, 3),
                            attack_box_fraction_of_frames=round(atk / n, 3), dy_pixels_per_frame_counts=dict(dy), previous_state=dict(prev), next_state=dict(nxt))
    d['hands_and_hurt_states_all_scenarios'] = summ
    json.dump(d, open(out, 'w'), indent=1)
    print('written', out)


def cmd_force(rom, state, out=None):
    """Direction-dependent poses 22 and 27: run to state 20 (the hands rise, bit 15 set), then move all heroes below (direction code 1) or
    above (code 3) the Lich and log the following states: ticks, AD at entry, vertical displacement in pixels."""
    res = []
    for label, dy in (('heroes below the Lich', 150), ('heroes above the Lich', -150)):
        for seed in (1, 8, 15, 22, 29, 36, 43, 50, 57, 64):
            s = reach(rom, state, seed, 0x20)
            if s and (dy < 0) == (s.r16(0x32) > 300): break         # room to move in the direction asked for (the arena wall is at y = 128)
        else:
            continue
        for p in range(3):
            s.c.wr16(0x7EE000 + 0x200 * p + 2, s.r16(0x2B)); s.c.wr16(0x7EE000 + 0x200 * p + 4, s.r16(0x32) + dy)
        seq = []; cur = None; caught = {}
        for _ in range(700):
            s.frame(); st = s.r8(0x7A)
            if st in (0x22, 0x27) and st not in caught and s.r16(0x96) >= 1 and s.r16(0x82) == 1 and s.f % 5 == 1: caught[st] = copy.deepcopy(s)
            if cur is None or st != cur['state']:
                if cur: cur['ticks'] = (s.f - cur['f0']) / 5; cur['dy'] = s.r16(0x32) - cur['y0']; seq.append(cur)
                cur = dict(state='%02X' % st if False else st, f0=s.f, y0=s.r16(0x32), ad=s.r16(0xAD), mode=s.r16(0x82))
        r = dict(scenario=label, seed=seed, injections=[inject(c) for c in caught.values()], states=[dict(state='%02X' % e['state'], ticks=e['ticks'], ad_at_entry=e['ad'], mode=e['mode'], dy_pixels=e['dy']) for e in seq[:8]])
        print(r, flush=True); res.append(r)
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


def worker(a):
    rom, state, seed, frames, natural, spread = a
    return run_trace(rom, state, seed, frames, natural, spread)


def agg(lst):
    c = collections.Counter()
    for ds in lst:
        for k, n in ds: c[k] += n
    return {str(k): v for k, v in sorted(c.items())}


def summarize(runs):
    """runs: list of event lists (one per seed). Per-state statistics and phase/action counting."""
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for ev in runs:
        ev = [e for e in ev if e['kind'] != 'meta']
        for i, e in enumerate(ev[:-1]):                 # the last event is cut by the end of the run
            p = per[e['state']]
            p['ticks'].append(e['ticks']); p['kind'].append(e['kind']); p['mode'].append(e['mode'])
            p['prev'].append(ev[i - 1]['state'] if i else -1); p['next'].append(ev[i + 1]['state'])
            p['dy'].append(tuple(sorted(e['dys'].items()))); p['dx'].append(tuple(sorted(e['dxs'].items())))
            p['rows'].append(tuple(e['rows'])); p['hb'].append(e['hb_ticks'] / max(1, e['ticks'] * 5)); p['atk'].append(e['atk_ticks'] / max(1, e['ticks'] * 5))
            p['f7e0'].append(e['f7e0']); p['f7e1'].append(e['f7e1']); p['ad0'].append(e['ad0'])
            p['dirc'].append(e['dirc'])
    out = {}
    for st, p in sorted(per.items()):
        t = p['ticks']
        out['%02X' % st] = dict(
            n=len(t), ticks_min=min(t), ticks_mean=round(sum(t) / len(t), 2), ticks_max=max(t),
            ticks_hist=dict(sorted(collections.Counter(t).items())),
            seconds_min=round(min(t) * 5 / FPS, 3), seconds_mean=round(sum(t) / len(t) * 5 / FPS, 3), seconds_max=round(max(t) * 5 / FPS, 3),
            entered_by=dict(collections.Counter(p['kind'])), mode_at_entry=dict(collections.Counter(p['mode'])),
            previous_state={'%02X' % k if k >= 0 else 'start': v for k, v in sorted(collections.Counter(p['prev']).items())},
            next_state={'%02X' % k: v for k, v in sorted(collections.Counter(p['next']).items())},
            per_frame_dy=agg(p['dy']), per_frame_dx=agg(p['dx']),
            attack_rows=dict(collections.Counter(r for rs in p['rows'] for r in rs)),
            hurtbox_fraction_of_frames=round(sum(p['hb']) / len(p['hb']), 3), attack_box_fraction_of_frames=round(sum(p['atk']) / len(p['atk']), 3),
            flags7e_entry=dict(collections.Counter('%04X' % v for v in p['f7e0'])),
            chooser_direction_code={str(k): v for k, v in sorted(collections.Counter(d for d in p['dirc'] if d is not None).items())},
            ad_at_entry_min=min(p['ad0']), ad_at_entry_max=max(p['ad0']))
    return out


def phases(runs):
    """Free phases of every run. Body phase = from the end of the hands->body transition (state 1D; spawn for the first one) to the start
    of the body->hands transition (state 18). Hands phase = from the end of 18-19-1A to the start of 1B. The 'with transition' lengths
    add the transition states. Actions = entries made by the action routine: spells 08-0E, projectile attacks 0F-17 (body), slam 24 (hands)."""
    body = []; hands = []
    for ev in runs:
        ev = [e for e in ev if e['kind'] != 'meta']
        mode = 'body'; start = 0; first = True; acts = []
        for i, e in enumerate(ev):
            st = e['state']
            if mode == 'body' and st == 0x18:
                body.append(dict(frames=e['f0'] - start, actions=len(acts), spells=sum(1 for a in acts if a < 0x0F), projectiles=sum(1 for a in acts if a >= 0x0F),
                                 first=first, tail=0)); mode = 'hands_trans'; acts = []; first = False
            elif mode == 'hands_trans' and st == 0x1A:
                mode = 'hands'; start = e['f0'] + int(e['ticks'] * 5); acts = []
            elif mode == 'hands' and st == 0x1B:
                hands.append(dict(frames=e['f0'] - start, actions=len(acts), slams=len(acts))); mode = 'body_trans'; acts = []
            elif mode == 'body_trans' and st == 0x1D:
                mode = 'body'; start = e['f0'] + int(e['ticks'] * 5); acts = []
            elif e['kind'] == 'action' and mode in ('body', 'hands'):
                acts.append(st)
    return body, hands


def hits_and_hurts(runs):
    """Party hits (Lich HP drops) by the state and mode the Lich was in, hurt-state entries by the state they interrupted, hit-marker lengths."""
    hits = collections.Counter(); dmg = collections.defaultdict(list); hurts = collections.Counter(); hurt_ticks = collections.defaultdict(list); flash = []
    for ev in runs:
        for e in ev:
            if e['kind'] == 'meta': flash += [fr for _, fr in e['flashes']]
        ev = [e for e in ev if e['kind'] != 'meta']
        for i, e in enumerate(ev):
            for h in e['hits']:
                k = '%02X mode %d' % (h['state'], h['mode']); hits[k] += 1; dmg[k].append(h['damage'])
            if e['kind'] == 'hurt' and i:
                hurts['%02X -> %02X' % (ev[i - 1]['state'], e['state'])] += 1; hurt_ticks['%02X' % e['state']].append(e['ticks'])
    return dict(hits_by_state_and_mode={k: dict(n=v, damage_min=min(dmg[k]), damage_max=max(dmg[k])) for k, v in sorted(hits.items())},
                hurt_entered_from=dict(sorted(hurts.items())),
                hurt_state_ticks={k: dict(stat(v), hist=dict(sorted(collections.Counter(v).items()))) for k, v in hurt_ticks.items()},
                hit_marker_frames=dict(stat(flash), hist=dict(sorted(collections.Counter(flash).items()))))


def stat(v):
    return dict(n=len(v), min=min(v), mean=round(sum(v) / len(v), 3), max=max(v)) if v else dict(n=0)


def leave_rates(runs):
    """How often a chooser call picks the transition (the ROM rule is rand(0..4) == 0, 20%). Body: first and second call after an action;
    hands: every call with bit 15 clear (states 1B, 1E, 1F, 20, 26 are the possible results) and the first call after a slam."""
    first = [0, 0]; second = [0, 0]; hands_all = [0, 0]; hands_first = [0, 0]
    for ev in runs:
        ev = [e for e in ev if e['kind'] != 'meta']
        for i, e in enumerate(ev):
            if e['kind'] == 'chooser' and e['state'] in (0x1B, 0x1E, 0x1F, 0x20, 0x26):
                hands_all[1] += 1; hands_all[0] += e['state'] == 0x1B
            if e['kind'] == 'action' and i + 1 < len(ev):
                nxt = ev[i + 1]
                if 0x08 <= e['state'] <= 0x17 and nxt['kind'] == 'chooser':
                    first[1] += 1; first[0] += nxt['state'] == 0x18
                    if nxt['state'] != 0x18 and i + 2 < len(ev) and ev[i + 2]['kind'] == 'chooser':
                        second[1] += 1; second[0] += ev[i + 2]['state'] == 0x18
                if e['state'] == 0x24 and nxt['kind'] == 'chooser':
                    hands_first[1] += 1; hands_first[0] += nxt['state'] == 0x1B
    r = lambda x: dict(transitions=x[0], calls=x[1], rate=round(x[0] / x[1], 4) if x[1] else None)
    return dict(body_first_call_after_action=r(first), body_second_call=r(second), hands_all_calls_bit15_clear=r(hands_all), hands_first_call_after_slam=r(hands_first))


def aggregate(runs, mode, seeds, frames, first_seed=0):
    body, hands = phases(runs)
    body_first = [b for b in body if b['first']]; body = [b for b in body if not b['first']]
    sd = lambda v: round((sum((x - sum(v) / len(v)) ** 2 for x in v) / len(v)) ** 0.5, 3) if v else None
    return dict(setting=mode, seeds=seeds, frames_per_seed=frames, total_seconds=round(seeds * frames / FPS, 1), first_seed_index=first_seed,
                states=summarize(runs),
                body_phase=dict(seconds=stat([round(b['frames'] / FPS, 2) for b in body]), actions=dict(stat([b['actions'] for b in body]), sd=sd([b['actions'] for b in body])),
                                spells=stat([b['spells'] for b in body]), projectiles=stat([b['projectiles'] for b in body])),
                hands_phase=dict(seconds=stat([round(h['frames'] / FPS, 2) for h in hands]), actions=dict(stat([h['actions'] for h in hands]), sd=sd([h['actions'] for h in hands]))),
                first_body_phase_from_spawn=dict(seconds=stat([round(b['frames'] / FPS, 2) for b in body_first]), actions=stat([b['actions'] for b in body_first])),
                chooser_transition_rates=leave_rates(runs), hits=hits_and_hurts(runs),
                body_actions_hist=dict(sorted(collections.Counter(b['actions'] for b in body).items())),
                hands_actions_hist=dict(sorted(collections.Counter(h['actions'] for h in hands).items())))


def cmd_stats(rom, state, seeds, frames, out, mode, events=None, first_seed=0):
    nat = mode == 'natural'
    with mp.Pool() as pool:
        runs = pool.map(worker, [(rom, state, 7 * i + 1, frames, nat, mode == 'spread') for i in range(first_seed, first_seed + seeds)])
    if events: json.dump(runs, open(events, 'w'), default=str)
    json.dump(aggregate(runs, mode, seeds, frames, first_seed), open(out, 'w'), indent=1, default=str)
    print('written', out)


def cmd_restat(events, out, mode, frames, first_seed=0):
    """Recompute the aggregate from the saved EVENTS file(s) of earlier stats runs (comma separated list: pooled; no simulation)."""
    runs = [r for f in events.split(',') for r in json.load(open(f))]
    json.dump(aggregate(runs, mode, len(runs), frames, first_seed), open(out, 'w'), indent=1, default=str)
    print('written', out)


if __name__ == '__main__':
    rom = romio.rom_from_argv(); state = sys.argv[1]; cmd = sys.argv[2]
    if cmd == 'anims': cmd_anims(rom)
    elif cmd == 'restat': cmd_restat(sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]), int(sys.argv[7]) if len(sys.argv) > 7 else 0)
    elif cmd == 'hurt': cmd_hurt(rom, state, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == 'force': cmd_force(rom, state, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == 'build': cmd_build(rom, sys.argv[3], sys.argv[4:])
    elif cmd == 'trace': cmd_trace(rom, state, int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else 'none')
    elif cmd == 'stats': cmd_stats(rom, state, int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else 'none', sys.argv[7] if len(sys.argv) > 7 else None, int(sys.argv[8]) if len(sys.argv) > 8 else 0)

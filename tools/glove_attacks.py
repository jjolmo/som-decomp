"""Glove (weapon type 0, rows 0..8) attacks of the three heroes, measured by running the real game routines frame by frame.
usage: glove_attacks.py ROM STATE OUT.json [section ...]
STATE: a ZSNES v143 save state taken during play on an open map with the three heroes idle (not in a menu or event).
sections (default: all): structure variants chooser gauge charge power hits invuln
Everything runs through tools/glove_sim.py, i.e. the real main routine $C0:B08C once per video frame with pad 1 injected (B button = attack).
Writes numbers only (data/glove_attacks.json).  Needs about 25 minutes of CPU for all sections (the invuln section alone takes about 8)."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio
import glove_sim as G

B = 0x8000
FACINGS = {'up': 0x00, 'down': 0x01, 'right': 0x02, 'left': 0x82}


def dump_json(obj, f, level=0):
    """JSON with one line per dict key and lists of numbers on a single line."""
    pad = ' ' * (level + 1)
    if isinstance(obj, dict):
        f.write('{\n')
        items = list(obj.items())
        for i, (k, v) in enumerate(items):
            f.write(pad + json.dumps(str(k)) + ': ')
            dump_json(v, f, level + 1)
            f.write(',\n' if i < len(items) - 1 else '\n')
        f.write(' ' * level + '}')
    elif isinstance(obj, list) and obj and isinstance(obj[0], list) and not isinstance(obj[0][0] if obj[0] else 0, (list, dict)):
        f.write('[\n')
        for i, v in enumerate(obj):
            f.write(pad + json.dumps(v, separators=(',', ':')) + (',\n' if i < len(obj) - 1 else '\n'))
        f.write(' ' * level + ']')
    else:
        f.write(json.dumps(obj, separators=(',', ':')))


def sbyte(v):
    return v - 256 if v >= 128 else v


def vxy(v):
    """E006/E007 velocity byte -> signed px per frame (bit 7 = negative direction, magnitude in the low 7 bits)."""
    return -(v & 0x7F) if v & 0x80 else v


def make(rom, state, slot, level=1, row=0, mon=None, press_phase=2, f4_par=0, idle=12):
    """Sim whose NEXT frame is the press frame, with $56 == press_phase on that frame and the parity of $F4 equal to f4_par."""
    sim = G.GloveSim(rom, state, slot, row, level, mon=mon)
    sim.phase0 = (press_phase - idle) % 5
    for _ in range(idle):
        sim.frame(0)
    sim.f4 = (f4_par - sim.f) & 0xFF
    return sim


SEG_FIELDS = ['frame', 'frames', 'vx', 'vy', 'vz', 'weapon_x', 'weapon_y', 'weapon_w', 'weapon_h', 'body_x', 'body_y', 'body_w', 'body_h',
              'dx', 'dy', 'height']


def segments(samples, end):
    """Runs of identical (velocity, weapon box, body box) between the press frame (0) and the frame where the state byte returns to 0.
    Row layout = SEG_FIELDS: first frame, length, velocity px/frame (x, y; z = E008 two's complement), weapon box (centre x, centre y, width, height,
    signed offsets from the hero position, world orientation), body box (same), measured displacement and height at the first frame."""
    x0, y0 = samples[0]['x'], samples[0]['y']
    segs, last = [], None
    for i, s in enumerate(samples[:end + 1]):
        key = (s['vx'], s['vy'], s['vz'], tuple(s['rect']), tuple(s['body']))
        if key != last:
            segs.append([i, 1, vxy(s['vx']), vxy(s['vy']), sbyte(s['vz']),
                         sbyte(s['rect'][0]), sbyte(s['rect'][1]), s['rect'][2], s['rect'][3],
                         sbyte(s['body'][0]), sbyte(s['body'][1]), s['body'][2], s['body'][3],
                         s['x'] - x0, s['y'] - y0, s['z']])
            last = key
        else:
            segs[-1][1] += 1
    return segs


def summarize(sim, samples, end):
    t0 = samples[0]['f']
    ticks = [s['f'] - t0 for s in samples[1:end + 1] if s['phase'] == G.HERO_TICK_PHASE]   # frame 0 (the press frame) runs the hero step before the input handler
    act = [i for i, s in enumerate(samples[:end + 1]) if s['rect'][2] and s['rect'][3]]
    sounds = [{'f': e[0] - t0, 'arg': [e[2], e[3], e[4]]} for e in sim.events if e[1] == 'sound' and e[0] - t0 <= end]
    words, lastp = [], None
    for i, s in enumerate(samples[:end]):
        if i and s['phase'] == G.HERO_TICK_PHASE:
            if s['ptr'] != lastp:
                words.append([i, 1])
                lastp = s['ptr']
            else:
                words[-1][1] += 1
    return {
        'swing_frames': end,
        'ticks': len(ticks),
        'words_start_frame_and_ticks': words,
        'first_tick_frame': ticks[0] if ticks else None,
        'gauge_after': samples[end]['gauge'],
        'end_pos_measured': [samples[end]['x'] - samples[0]['x'], samples[end]['y'] - samples[0]['y']],
        'end_pos_nominal': [sum(vxy(s['vx']) for s in samples[:end]), sum(vxy(s['vy']) for s in samples[:end])],
        'max_height': max(s['z'] for s in samples[:end + 1]),
        'weapon_box_frames': len(act),
        'weapon_box_first': act[0] if act else None,
        'weapon_box_last': act[-1] if act else None,
        'segments': segments(samples, end),
        'sounds': sounds,
    }


COMPACT = ('swing_frames', 'ticks', 'first_tick_frame', 'weapon_box_frames', 'weapon_box_first', 'weapon_box_last', 'end_pos_nominal', 'end_pos_measured', 'max_height', 'gauge_after')


def compact(d):
    return {k: d[k] for k in COMPACT}


def run_variant(rom, state, slot, var, face, level=1, kind='normal', stage=0, press_phase=2):
    """Start the attack the way the game does (B press for a normal swing, release of a charged button for a power attack), then force
    E011 = var after the start frame so that the script runs without any target around."""
    sim = make(rom, state, slot, level=level, press_phase=press_phase)
    sim.h.sb(0x10, face)
    sim.events.clear()
    if kind == 'normal':
        sim.frame(B)
    else:
        sim.h.sb(0x19B, stage)
        sim.frame(0)
    sim.pad = 0
    samples = [sim.sample()]
    sim.h.sb(0x11, var)
    end = None
    for i in range(1, 900):
        sim.frame(0)
        samples.append(sim.sample())
        if samples[-1]['st'] == 0:
            end = i
            break
    return sim, samples, end


def sec_variants(rom, state, res):
    out = {}
    for slot in range(3):
        hero = {}
        for var in range(4):
            sums = {}
            for fname, face in FACINGS.items():
                sim, samples, end = run_variant(rom, state, slot, var, face)
                sums[fname] = summarize(sim, samples, end)
            hero[str(var)] = dict(sums) if slot == 0 else {k: compact(v) for k, v in sums.items()}
        h = sim.h
        hero['agi'] = h.b(0x189); hero['atk'] = h.b(0x198); hero['hit'] = h.b(0x197); hero['crit'] = h.b(0x196)
        out['slot%d' % slot] = hero
    # swing length against the phase of the press inside the 5-frame hero step
    ph = {}
    for p in range(5):
        row = {}
        for var in range(4):
            sim, samples, end = run_variant(rom, state, 0, var, FACINGS['left'], press_phase=p)
            row[str(var)] = {'first_tick': summarize(sim, samples, end)['first_tick_frame'], 'swing_frames': end}
        ph[str(p)] = row
    out['by_press_phase'] = ph
    res['normal_runs'] = out


def cls_of(rom, state, face, dx, dy, par=0, slot=0):
    sim = make(rom, state, slot, mon=(dx, dy), f4_par=par, idle=7)
    sim.h.sb(0x10, face)
    sim.frame(B)
    return sim.h.b(0x11)


def sec_chooser(rom, state, res):
    out = {}
    # thresholds along each axis (monster at (+d, 0) / (0, +d) from the hero, hero facing left)
    for name, mk in (('x', lambda d: (d, 0)), ('y', lambda d: (0, d))):
        row = [cls_of(rom, state, FACINGS['left'], *mk(d)) for d in range(0, 64)]
        out['threshold_' + name] = [[d, row[d]] for d in range(len(row)) if d == 0 or row[d] != row[d - 1]]
    grid = {}
    for dx in (0, 20, 30, 45):
        grid[str(dx)] = [cls_of(rom, state, FACINGS['left'], dx, dy) for dy in (0, 20, 30, 45)]
    out['grid_dx_rows_dy_cols_0_20_30_45'] = grid
    # facing independence
    out['facing_check_dx_36'] = {k: cls_of(rom, state, f, 36, 0) for k, f in FACINGS.items()}
    # no target and a dead/absent target
    out['no_target'] = [cls_of(rom, state, FACINGS['left'], 400, 400, par=p) for p in (0, 1)]
    # parity of $F4: normal variant = class_value - parity
    out['normal_var_by_class_parity'] = {str(d): [cls_of(rom, state, FACINGS['left'], d, 0, par=p) for p in (0, 1)] for d in (10, 36, 100)}
    # power variant after releasing at stage s: E011 for (stage, class, parity), weapon level L
    pw = {}
    for L in (1, 4, 8):
        for s in range(1, L + 1):
            row = []
            for d in (10, 36, 100):
                for p in (0, 1):
                    sim = make(rom, state, 0, level=L, mon=(d, 0), f4_par=p, idle=7)
                    sim.h.sb(0x19B, s)
                    sim.frame(0)
                    row.append(sim.h.b(0x11))
            pw['L%d_stage%d' % (L, s)] = row
    out['power_var_levels_stage_rows_[near p0,p1, mid p0,p1, far p0,p1]'] = pw
    res['chooser'] = out


def sec_gauge(rom, state, res):
    out = {}
    for slot in range(3):
        sim = make(rom, state, slot, level=1)
        h = sim.h
        agi = h.b(0x189)
        seq = []
        sim.frame(B); sim.pad = 0
        for i in range(140):
            sim.frame(0)
            seq.append(h.b(0x1ED))
        end = next(i for i, s in enumerate(seq) if s)          # first frame with the gauge set
        first_zero = next(i for i in range(end, len(seq)) if seq[i] == 0)
        ones = sum(1 for s in seq[end:first_zero] if s == 1)
        out['slot%d' % slot] = {'agi': agi, 'start_value': seq[end], 'frames_counting_down': first_zero - end - ones,
                                'frames_held_at_1': ones, 'frames_to_zero': first_zero - end,
                                'formula_value': (100 - agi) // 2 + 50}
    # presses during a swing / spam
    sim = make(rom, state, 0, level=1)
    h = sim.h
    starts, prev = [], 0
    sim.frame(B); starts.append(0); prev = 0x20
    for f in range(1, 200):
        pad = B if f in (6, 12, 18) else 0                   # three extra presses inside the first swing
        sim.frame(pad)
        st = h.b(0x1C)
        if st == 0x20 and prev != 0x20:
            starts.append(f)
        prev = st
    out['extra_presses_at_6_12_18_swing_starts'] = starts
    sim = make(rom, state, 0, level=1)
    h = sim.h
    starts, prev, gauge_at_start = [], 0, []
    for f in range(400):
        sim.frame(B if f % 2 == 0 else 0)
        st = h.b(0x1C)
        if st == 0x20 and prev != 0x20:
            starts.append(f); gauge_at_start.append(h.b(0x1ED))
        prev = st
    out['spam_every_2nd_frame_swing_starts'] = starts[:8]
    out['spam_gauge_at_swing_start'] = gauge_at_start[:8]
    # gauge frozen while a swing runs
    sim = make(rom, state, 0, level=1)
    h = sim.h
    sim.frame(B); sim.pad = 0
    for i in range(200):
        sim.frame(0)
        if h.b(0x1C) == 0 and h.b(0x1ED):
            break
    first = h.b(0x1ED)
    for i in range(30):
        sim.frame(0)
    g_before = h.b(0x1ED)
    sim.frame(B); sim.pad = 0
    g_during = [h.b(0x1ED)]
    for i in range(30):
        sim.frame(0)
        g_during.append(h.b(0x1ED))
    out['gauge_after_30_frames'] = [first, g_before]
    out['gauge_during_second_swing_first_31_frames'] = g_during
    # direction held together with the attack button: no effect on the swing
    base = None
    for name, pad in (('B', B), ('B+right', B | 0x0100), ('B+up', B | 0x0800), ('B+left', B | 0x0200)):
        sim = make(rom, state, 0, level=1)
        h = sim.h
        h.sb(0x10, 0x82)
        x0, y0 = h.w(2), h.w(4)
        sim.frame(pad)
        sim.h.sb(0x11, 3)
        trace = []
        for i in range(1, 24):
            sim.frame(pad)
            trace.append([h.b(0x1C), h.b(0x10), h.w(2) - x0, h.w(4) - y0])
        out.setdefault('direction_held_with_B_first_24_frames_state_facing_dx_dy', {})[name] = trace[-1]
    res['gauge'] = out


def sec_charge(rom, state, res):
    out = {}
    for slot in range(3):
        for par in (0, 1):
            sim = make(rom, state, slot, level=8, f4_par=par)
            h = sim.h
            ev, prev = {}, 0
            end = None
            for f in range(900):
                sim.frame(B)
                s = h.b(0x19B)
                if s != prev:
                    ev[str(s)] = f; prev = s
                if end is None and f > 0 and h.b(0x1C) == 0:
                    end = f
            out['slot%d_parity%d' % (slot, par)] = {'agi': h.b(0x189), 'swing_end_frame': end, 'stage_reached_frame': ev}
    # sound requests while holding from the press (hero 0, level 8, 900 frames)
    sim = make(rom, state, 0, level=8)
    sim.events.clear()
    f0 = sim.f
    for f in range(900):
        sim.frame(B)
    snd = {}
    for e in sim.events:
        if e[1] == 'sound':
            snd.setdefault(str(e[2]), []).append(e[0] - f0)
    out['sound_ids_while_holding_900_frames_frames_since_press'] = {k: v[:12] for k, v in snd.items()}
    out['sound_counts_while_holding_900_frames'] = {k: len(v) for k, v in snd.items()}
    # release timing: hold until stage 1, then release on the next frame
    sim = make(rom, state, 0, level=8)
    h = sim.h
    rel = None
    for f in range(900):
        sim.frame(B if rel is None else 0)
        if rel is None and h.b(0x19B) == 1:
            rel = f
            sim.frame(0)
            out['release_after_stage1'] = {'stage1_frame': rel, 'state_byte_in_release_frame': h.b(0x1C), 'stage': h.b(0x19B), 'variant': h.b(0x11)}
            break
    # release before stage 1 (stage 0): no power attack
    sim = make(rom, state, 0, level=8)
    h = sim.h
    sim.frame(B)
    for f in range(1, 200):
        sim.frame(B if f < 120 else 0)
    out['release_at_stage0_state_byte'] = h.b(0x1C)
    # weapon level only caps the stage
    caps = {}
    for L in (1, 2, 5, 8):
        sim = make(rom, state, 0, level=L)
        h = sim.h
        for f in range(1000):
            sim.frame(B)
        caps[str(L)] = h.b(0x19B)
    out['stage_after_1000_frames_holding_by_level'] = caps
    res['charge'] = out


def sec_power(rom, state, res):
    out = {}
    for slot in range(3):
        for stage in range(1, 9):
            for cls in range(3):
                sums = {}
                for fname, face in FACINGS.items():
                    sim, samples, end = run_variant(rom, state, slot, 4 * stage + cls, face, level=stage, kind='power', stage=stage)
                    sums[fname] = summarize(sim, samples, end)
                rec = dict(sums) if slot == 0 else {k: compact(v) for k, v in sums.items()}
                out.setdefault('slot%d' % slot, {}).setdefault(str(stage), {})[str(cls)] = rec
        print('power slot', slot, 'stage', stage, flush=True)
    res['power'] = out


def hit_run(rom, state, stage, mon, face=0x82, var=None, slot=0, nframes=400, mon2=None, level=8):
    sim = make(rom, state, slot, level=level, mon=mon)
    if mon2 is not None:
        sim.spawn(mon2, 0, 9999, slot=4)
    h, m = sim.h, sim.m
    sim.h.sb(0x10, face)
    m2 = sim.env.obj(4) if mon2 is not None else None
    if stage:
        sim.h.sb(0x19B, stage)
        sim.frame(0)
    else:
        sim.frame(B); sim.pad = 0
    if var is not None:
        sim.h.sb(0x11, var)
    rec = {'hits': [], 'hits2': [], 'hero_flag_set': None, 'rect_first': None, 'mon_pos': [], 'dmg_stage': []}
    hp, hp2 = m.w(0x182), (m2.w(0x182) if m2 else None)
    x0, y0 = m.w(2), m.w(4)
    flag0 = h.b(0x5A)
    for f in range(1, nframes):
        sim.frame(0)
        if rec['rect_first'] is None and h.b(0xC2) and h.b(0xC3):
            rec['rect_first'] = f
        if rec['hero_flag_set'] is None and h.b(0x5A) != flag0:
            rec['hero_flag_set'] = f
        n = m.w(0x182)
        if n != hp:
            rec['hits'].append([f, hp - n]); rec['dmg_stage'].append(h.b(0x19B)); hp = n
        if m2 is not None:
            n2 = m2.w(0x182)
            if n2 != hp2:
                rec['hits2'].append([f, hp2 - n2]); hp2 = n2
        if f in (10, 30, 60, 120, 200, 399):
            rec['mon_pos'].append([f, m.w(2) - x0, m.w(4) - y0])
    rec['sounds'] = [[e[0] - sim.events[0][0] if False else e[0], e[2], e[3], e[4]] for e in sim.events if e[1] == 'sound']
    return rec, sim


def sec_hits(rom, state, res):
    out = {}
    for stage in range(0, 9):
        row = {}
        for dx in (-14, -30):
            rec, sim = hit_run(rom, state, stage, (dx, 0))
            row[str(dx)] = rec
        out[str(stage)] = row
    # two targets
    rec, sim = hit_run(rom, state, 8, (-20, 0), mon2=(-26, -4))
    out['two_targets_stage8'] = rec
    # damage per hit by stage: the real hit routine ($C0:4FED..$C0:514B, as in validate_phys.py) on 300 random RNG states, hero vs dummy (Saber nibble cleared)
    import random
    import validate_phys as VP
    sim = make(rom, state, 0, level=8, mon=(-14, 0))
    env, c = sim.env, sim.c
    env.obj(0).sb(0x1AE, 0)
    env.obj(0).sb(0x1ED, 0)
    random.seed(7)
    dmg = {}
    for stage in range(0, 9):
        env.obj(0).sb(0x19B, stage)
        vals = []
        for k in range(300):
            for i in range(0x3F1, 0x400):
                c.wram[i] = random.randrange(256)
            c.wram[0x3F0] = random.randrange(15)
            hit, d = VP.rom_hit(env, 0, 3)
            vals.append(d if hit else -1)
        ok = [v for v in vals if v >= 0]
        a_ = env.obj(0).b(0x198)
        dmg[str(stage)] = {'base_atk_x_(2s+4)>>2': (a_ * (2 * stage + 4)) >> 2, 'hit_rate': len(ok) / len(vals), 'min': min(ok), 'mean': round(sum(ok) / len(ok), 1), 'max': max(ok)}
    out['damage_by_stage_300_random_rng_states_hero0_row0_dummy_def0_ev0'] = dmg
    out['hero0_stats_during_damage_runs_atk_hit_crit_E1E6'] = [env.obj(0).b(0x198), env.obj(0).b(0x197), env.obj(0).b(0x196), env.obj(0).b(0x1E6)]
    # damage against the gauge value E1ED at the hit (frozen at its value from the start of the swing), same method, stage 0 and 8
    pen = {}
    env.obj(0).sb(0x1ED, 0)
    for stage in (0, 8):
        env.obj(0).sb(0x19B, stage)
        for g in (0, 1, 15, 30, 45, 60, 75, 90):
            env.obj(0).sb(0x1ED, g)
            vals = []
            for k in range(300):
                for i in range(0x3F1, 0x400):
                    c.wram[i] = random.randrange(256)
                c.wram[0x3F0] = random.randrange(15)
                hit, d = VP.rom_hit(env, 0, 3)
                vals.append(d if hit else -1)
            ok = [v for v in vals if v >= 0]
            pen['stage%d_gauge%d' % (stage, g)] = {'hit_rate': len(ok) / len(vals), 'mean': round(sum(ok) / len(ok), 1) if ok else 0, 'max': max(ok) if ok else 0}
    out['damage_by_gauge_value_300_random_rng_states'] = pen
    # target knockback: depends on damage against the target's max HP (hurt code $C0:4F2E-4F44), measured on the dummy with max HP 600 / 1000 / 2000
    kb = {}
    for maxhp in (600, 1000, 2000):
        for stage in (0, 4, 8):
            sim = make(rom, state, 0, level=8, mon=(-24, 0))
            h, m = sim.h, sim.m
            m.sw(0x184, maxhp); m.sw(0x182, maxhp)
            h.sb(0x10, 0x82)
            if stage:
                h.sb(0x19B, stage); sim.frame(0)
            else:
                sim.frame(B); sim.pad = 0
            x0, y0 = m.w(2), m.w(4)
            hit = dmg = e11 = None
            for f in range(1, 80):
                sim.frame(0)
                if hit is None and m.w(0x182) != maxhp:
                    hit = f; dmg = maxhp - m.w(0x182)
                if hit and e11 is None and m.b(0x11) >= 0x80:
                    e11 = m.b(0x11)
            kb['maxhp%d_stage%d' % (maxhp, stage)] = {'damage': dmg, 'max_hp_quarter': maxhp // 4, 'hurt_code_E011': e11, 'displacement_after_80_frames': [m.w(2) - x0, m.w(4) - y0], 'target_facing_E010': m.b(0x10)}
    out['target_knockback_by_damage_vs_max_hp'] = kb
    # E19B (stage) value during the whole power attack and status fields
    sim, samples, end = run_variant(rom, state, 0, 4 * 8 + 2, 0x82, level=8, kind='power', stage=8)
    out['stage_byte_during_attack_stage8'] = sorted(set(s['stage'] for s in samples[:end]))
    res['hits'] = out


PRESET_TABLE = 0x2AF05      # ROM offset ($C2:AF05): 4-byte velocity presets (vx, vy, vz, 0), 0x80 = leave unchanged, selected by op 0x8F + k
ANIM_TABLE = 0x3040         # bank $D1 offset of the animation-pointer table of weapon type 0 (E065): word [(E011*3 + facing) * 2]


def anim_ptr(rom, var, facing):
    o = 0x110000 + ANIM_TABLE + 2 * (var * 3 + facing)
    return rom[o] | rom[o + 1] << 8


def piece_info(rom, ptr, pieces, normal_ptrs):
    """Static walk of one animation script: ticks (sum of frame durations; a frame word with duration code d lasts d+1 steps for d < 4, one
    step for d >= 4), sounds (op 0xF9), velocity presets (ops 0x8F..0xAA) and calls (op 0xF1)."""
    if ptr in pieces:
        return pieces[ptr]['id']
    info = {'addr': ptr, 'ticks': 0, 'sounds': [], 'presets': [], 'calls': []}
    pid = len(pieces)
    info['id'] = pid
    pieces[ptr] = info
    for off, kind, b in G.decode_script(rom, ptr):
        if kind == 'frame':
            d = b[0] & 7
            info['ticks'] += (d if d < 4 else 0) + 1
        elif kind == 'op':
            if b[0] == 0xF9:
                info['sounds'].append(b[1] | b[2] << 8)
            elif 0x8F <= b[0] <= 0xAA:
                k = b[0] - 0x8F
                info['presets'].append([k] + list(rom[PRESET_TABLE + 4 * k:PRESET_TABLE + 4 * k + 3]))
            elif b[0] == 0xF1:
                q = b[1] | b[2] << 8
                piece_info(rom, q, pieces, normal_ptrs)
                info['calls'].append(q)
    return pid


def total_ticks(pieces, ptr):
    p = pieces[ptr]
    return p['ticks'] + sum(total_ticks(pieces, q) for q in p['calls'])


def sec_structure(rom, state, res):
    out = {}
    for facing in range(3):
        pieces = {}
        normals = {anim_ptr(rom, v, facing): v for v in range(4)}
        table = {}
        for var in range(0, 36):
            ptr = anim_ptr(rom, var, facing)
            piece_info(rom, ptr, pieces, normals)
            table[str(var)] = {'script': ptr, 'total_steps': total_ticks(pieces, ptr)}
        out['facing%d' % facing] = {'variants': table, 'pieces': {str(k): v for k, v in sorted(pieces.items())},
                                    'normal_variant_scripts': {str(k): v for k, v in normals.items()}}
    res['structure'] = out


def vulnerable_frames(rom, state, var, kind, stage, face=0x82, slot=0):
    """For every frame f of the attack: put a dummy monster on the hero, give it a large weapon box for that single frame and see whether the
    hero's hit flag routine ($C1:D23F, ORA $E059,X) fires.  Returns (frames with a non-empty body box, frames where the hero can be hit)."""
    sim, samples, end = run_variant(rom, state, slot, var, face, level=max(stage, 1), kind=kind, stage=stage)
    ref = [bool(s['body'][2] and s['body'][3]) for s in samples[:end + 1]]
    res = []
    for f in range(end + 1):
        sim = make(rom, state, slot, level=max(stage, 1), mon=(0, 0))
        h, m, c = sim.h, sim.m, sim.c
        hits = [0]
        orig = c.step
        def st(orig=orig, hits=hits, sim=sim, c=c):
            if (c.PB << 16 | c.PC) in (0xC1D23F, 0x01D23F) and c.X == sim.base:
                hits[0] += 1
            orig()
        c.step = st
        h.sb(0x10, face)
        if kind == 'normal':
            sim.frame(B); sim.pad = 0
        else:
            h.sb(0x19B, stage); sim.frame(0)
        h.sb(0x11, var)
        got = False
        for g in range(end + 1):
            if g == f:
                for i, v in enumerate((0, 0xF0, 60, 60)):
                    m.sb(0xC0 + i, v)
            else:
                for i in range(4):
                    m.sb(0xC0 + i, 0)
            hits[0] = 0
            if g > 0:
                sim.frame(0)
            if g == f and hits[0]:
                got = True
        res.append(got)
    return ref, res


def sec_invuln(rom, state, res):
    out = {}
    for name, var, kind, stage in (('normal_var0', 0, 'normal', 0), ('normal_var2', 2, 'normal', 0), ('power_stage8_cls2', 34, 'power', 8)):
        ref, hit = vulnerable_frames(rom, state, var, kind, stage)
        out[name] = {'frames_with_body_box': [i for i, x in enumerate(ref) if x], 'frames_hero_hittable': [i for i, x in enumerate(hit) if x]}
    res['invulnerability'] = out


def build_summary(res):
    """Short table of the normal attack (hero 0 geometry, all heroes share the timing): numbers copied from the runs above."""
    if 'normal_runs' not in res:
        return
    n = res['normal_runs']
    summ = {'units': 'video frames at 60.0988 Hz unless the name says steps (1 step = 5 frames = 83.2 ms)',
            'press_to_first_step_frames': [1, 5]}
    for var in '0123':
        rec = {}
        for face in ('left', 'up'):
            e = n['slot0'][var][face]
            first = e['first_tick_frame']
            steps = (e['swing_frames'] - first) // 5
            move = [[s[0] - first, s[1], s[2] if s[2] else s[3]] for s in e['segments'] if s[2] or s[3]]
            boxes = [[s[0] - first, s[1], s[5], s[6], s[7], s[8]] for s in e['segments'] if s[7] and s[8]]
            rec[face] = {
                'steps': steps,
                'frames_after_first_step': steps * 5,
                'frames_from_press_best': e['swing_frames'],
                'frames_from_press_worst': e['swing_frames'] + 4,
                'seconds_from_press_best': round(e['swing_frames'] / 60.0988, 4),
                'seconds_from_press_worst': round((e['swing_frames'] + 4) / 60.0988, 4),
                'movement_px_per_frame_start_frame_length': move,
                'movement_total_px': e['end_pos_nominal'],
                'weapon_box_hero0_start_end_after_first_step': [e['weapon_box_first'] - first, e['weapon_box_last'] - first],
                'weapon_box_frames': e['weapon_box_frames'],
                'weapon_boxes_start_len_x_y_w_h': boxes,
                'sound_ids': [[x['f'] - first, x['arg'][0]] for x in e['sounds']],
                'gauge_value_hero0_after_swing': e['gauge_after'],
            }
        summ['variant%s' % var] = rec
    gauge = {}
    for slot in range(3):
        h = n['slot%d' % slot]
        gauge['hero%d' % slot] = {'agi': h['agi'], 'atk': h['atk'], 'hit': h['hit'], 'crit': h['crit'],
                                  'gauge_start': (100 - h['agi']) // 2 + 50, 'frames_to_empty': (100 - h['agi']) // 2 + 50 + 15}
    summ['heroes'] = gauge
    res['normal'] = summ


SECTIONS = {'structure': sec_structure, 'variants': sec_variants, 'chooser': sec_chooser, 'gauge': sec_gauge, 'charge': sec_charge, 'power': sec_power, 'hits': sec_hits, 'invuln': sec_invuln}


def main():
    rom = romio.rom_from_argv()
    state = sys.argv[1]
    out_path = sys.argv[2]
    wanted = sys.argv[3:] or list(SECTIONS)
    res = {}
    if os.path.exists(out_path):
        res = json.load(open(out_path))
    res['source'] = 'tools/glove_attacks.py: frame-exact runs of the real main routine $C0:B08C on a save state (docs/glove-attacks.md)'
    res['clock'] = {'frame_hz': 60.0988, 'hero_step_frames': 5, 'hero_step_hz': 12.0198, 'hero_step_phase': G.HERO_TICK_PHASE}
    t = time.time()
    for name in wanted:
        SECTIONS[name](rom, state, res)
        build_summary(res)
        with open(out_path, 'w') as fh:
            dump_json(res, fh)
            fh.write('\n')
        print(name, 'done after', round(time.time() - t), 's', flush=True)


if __name__ == '__main__':
    main()

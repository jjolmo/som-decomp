"""Whip (weapon type 4), bow (5), boomerang (6) and javelin (7) attacks of the three heroes, measured by running the real game routines frame by frame.
usage: ranged_attacks.py ROM STATE OUT.json WEAPON [section ...]
WEAPON: whip | bow | boomerang | javelin (or the weapon type number 4-7).  STATE: a ZSNES v143 save state taken during play on an open map with the three heroes idle.
sections (default: all): structure normal chooser gauge charge power proj hits invuln
Generalises tools/glove_attacks.py (same experiments, weapon row as a parameter) and adds the projectile engine of bank $C2 (arrows, spears, boomerangs).
Everything runs through tools/glove_sim.py via tools/ranged_sim.py: the real main routine $C0:B08C once per video frame with pad 1 injected (B = attack).
Writes numbers only (data/weapons_ranged.json merges the four weapons).  One weapon takes about 20-40 minutes of CPU for all sections."""
import sys, os, json, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio
import glove_sim as G
import glove_attacks as ga
import ranged_sim as R
from ranged_sim import B, FACINGS, HZ, PROJ_BASE
from glove_attacks import dump_json, sbyte, vxy, compact, PRESET_TABLE

FACING_NAMES = {0x00: 'up', 0x01: 'down', 0x02: 'right', 0x82: 'left'}


# ---------------------------------------------------------------- static structure of the scripts
def walk_script(rom, ptr, t0=0, depth=0, out=None):
    """Linear event list of an animation script with the calls (op 0xF1) expanded in place; t = hero steps (5 frames) from the start of the attack.
    Returns (events, total_steps).  Event kinds: frame (dur, sprite), shot (op 0xFB), sound (id), preset (k), nibbles (op 0xF0), op (other one/two-byte ops)."""
    ev = [] if out is None else out
    t = t0
    for off, kind, b in G.decode_script(rom, ptr):
        if kind == 'frame':
            d = b[0] & 7
            dur = d + 1 if d < 4 else 1
            ev.append(dict(t=t, kind='frame', dur=dur, sprite=b[1], flags=b[0] >> 3))
            t += dur
        elif kind == 'end':
            break
        else:
            op = b[0]
            if op == 0xF1:
                q = b[1] | b[2] << 8
                _, t = walk_script(rom, q, t, depth + 1, ev)
                if depth == 0:
                    pass
                continue
            if op == 0xF9:
                ev.append(dict(t=t, kind='sound', id=b[1] | b[2] << 8))
            elif op == 0xFB:
                ev.append(dict(t=t, kind='shot'))
            elif 0x8F <= op <= 0xAA:
                k = op - 0x8F
                ev.append(dict(t=t, kind='preset', k=k, v=list(rom[PRESET_TABLE + 4 * k:PRESET_TABLE + 4 * k + 3])))
            elif op == 0xF0:
                ev.append(dict(t=t, kind='nibbles', b=list(b[1:])))
            else:
                ev.append(dict(t=t, kind='op', b=list(b)))
    return ev, t


def sec_structure(ctx, rom, state, res):
    out = {}
    o = 0x110000 + R.ANIM_MAP + 40 * ctx.type
    out['kind_to_animation_map'] = list(rom[o:o + 40])
    scripts = {}
    table = {}
    for facing in range(3):
        row = {}
        for var in range(40):
            ptr = ctx.anim_ptr(rom, var, facing)
            row[str(var)] = ptr
            if (ptr, facing) not in scripts:
                ev, total = walk_script(rom, ptr)
                scripts[(ptr, facing)] = dict(addr=ptr, facing=facing, total_steps=total,
                                              frames=[[e['t'], e['dur'], e['sprite']] for e in ev if e['kind'] == 'frame'],
                                              shot_steps=[e['t'] for e in ev if e['kind'] == 'shot'],
                                              sounds=[[e['t'], e['id']] for e in ev if e['kind'] == 'sound'],
                                              presets=[[e['t'], e['k']] + e['v'] for e in ev if e['kind'] == 'preset'],
                                              nibble_ops=[[e['t']] + e['b'] for e in ev if e['kind'] == 'nibbles'],
                                              other_ops=[[e['t']] + e['b'] for e in ev if e['kind'] == 'op'])
        table['facing%d' % facing] = row
    out['script_of_animation'] = table
    out['shared_scripts_facing2'] = {}
    seen = {}
    for var in range(40):
        p = ctx.anim_ptr(rom, var, 2)
        seen.setdefault(p, []).append(var)
    out['shared_scripts_facing2'] = {str(p): v for p, v in seen.items()}
    out['scripts'] = {'%d_%04X' % (f, p): v for (p, f), v in sorted(scripts.items(), key=lambda kv: (kv[0][1], kv[0][0]))}
    res['structure'] = out


# ---------------------------------------------------------------- projectile summaries
def proj_summary(smp, upto=None):
    """Per projectile entry k: when it exists, its flight path (px relative to the hero position at the same frame) and its end."""
    out = []
    n = len(smp) if upto is None else upto
    for k in range(3):
        fr = [(i, smp[i]['proj'][k]) for i in range(n) if smp[i]['proj'][k]['kind']]
        if not fr:
            continue
        i0, e0 = fr[0]
        live = [(i, e) for i, e in fr if e['kind'] & 0xF8 == 0]
        if not live:
            continue
        l0, le0 = live[0]
        dying = [i for i, e in live if e['dying']]
        hx, hy = smp[l0]['x'], smp[l0]['y']
        path = [[e['x'] - hx, e['y'] - hy, e['z']] for i, e in live]
        out.append(dict(
            entry=k, kind_byte_first=e0['kind'], delay_frames=(e0['kind'] >> 3), first_frame=i0, first_live_frame=l0, last_frame=live[-1][0],
            dying_from_frame=dying[0] if dying else None, live_frames=len(live),
            spawn_offset_from_hero=[le0['x'] - hx, le0['y'] - hy, le0['z']],
            facing_byte=le0['face'], speed_param=le0['fA'], init_f8_f9=[le0['f8'], le0['f9']],
            path_dx_dy_z=path, attr_first=le0['attr'], attr_values=sorted(set(e['attr'] for i, e in live))))
    return out


def run_attack(ctx, rom, state, slot, var, face, level=8, kind='normal', stage=0, press_phase=2, **kw):
    sim = ctx.start(rom, state, slot, var, face, level=level, kind=kind, stage=stage, press_phase=press_phase, **kw)
    smp, es, ea = R.follow(sim)
    return sim, smp, es, ea


def summarize(sim, smp, es, ea):
    d = ga.summarize(sim, smp, es)
    first = next((i for i, s in enumerate(smp) if s['ptr'] != sim.pre_ptr), None)
    d['first_step_frame'] = first
    d['swing_end_frame'] = es
    d['ready_frame'] = ea
    d['gauge_after_ready_frame'] = smp[ea]['gauge'] if ea is not None else None
    d['stage_byte_values'] = sorted(set(s['stage'] for s in smp[:(ea or es) + 1]))
    d['projectiles'] = proj_summary(smp)
    return d


def compact_r(d):
    c = compact(d)
    c['ready_frame'] = d['ready_frame']
    c['first_step_frame'] = d['first_step_frame']
    c['projectiles'] = [dict((k, p[k]) for k in ('entry', 'delay_frames', 'first_live_frame', 'last_frame', 'live_frames', 'spawn_offset_from_hero')) for p in d['projectiles']]
    return c


# ---------------------------------------------------------------- sections
def sec_normal(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        hero = {}
        for var in range(4):
            sums = {}
            for fname, face in FACINGS.items():
                sim, smp, es, ea = run_attack(ctx, rom, state, slot, var, face)
                sums[fname] = summarize(sim, smp, es, ea)
            if slot == 0:
                hero[str(var)] = dict(sums)
            else:
                ref = out['slot0'][str(var)]
                hero[str(var)] = {k: dict(compact_r(v), same_projectile_paths_as_hero0=[p['path_dx_dy_z'] for p in v['projectiles']] == [p['path_dx_dy_z'] for p in ref[k]['projectiles']],
                                          same_segments_as_hero0=v['segments'] == ref[k]['segments']) for k, v in sums.items()}
        h = sim.h
        hero['agi'] = h.b(0x189); hero['atk'] = h.b(0x198); hero['hit'] = h.b(0x197); hero['crit'] = h.b(0x196)
        out['slot%d' % slot] = hero
    ph = {}
    for p in range(5):
        row = {}
        for var in range(4):
            sim, smp, es, ea = run_attack(ctx, rom, state, 0, var, FACINGS['left'], press_phase=p)
            row[str(var)] = {'first_step_frame': next((i for i, s in enumerate(smp) if s['ptr'] != sim.pre_ptr), None), 'swing_frames': es, 'ready_frame': ea,
                             'spawn_frame': next((i for i, s in enumerate(smp) if s['proj'][0]['kind'] & 0xF8 == 0 and s['proj'][0]['kind']), None)}
        ph[str(p)] = row
    out['by_press_phase'] = ph
    res['normal_runs'] = out


def cls_of(ctx, rom, state, face, dx, dy, par=0, slot=0, stage=0):
    sim = ctx.make(rom, state, slot, mon=(dx, dy), f4_par=par, idle=7)
    sim.h.sb(0x10, face)
    if stage:
        sim.h.sb(0x19B, stage)
        sim.frame(0)
    else:
        sim.frame(B)
    return sim.h.b(0x11)


def sec_chooser(ctx, rom, state, res):
    out = {}
    for name, mk in (('x', lambda d: (d, 0)), ('y', lambda d: (0, d))):
        row = [cls_of(ctx, rom, state, FACINGS['left'], *mk(d)) for d in range(0, 64)]
        out['threshold_' + name] = [[d, row[d]] for d in range(len(row)) if d == 0 or row[d] != row[d - 1]]
    out['facing_check_dx_36'] = {k: cls_of(ctx, rom, state, f, 36, 0) for k, f in FACINGS.items()}
    out['no_target'] = [cls_of(ctx, rom, state, FACINGS['left'], 400, 400, par=p) for p in (0, 1)]
    out['normal_var_by_class_parity'] = {str(d): [cls_of(ctx, rom, state, FACINGS['left'], d, 0, par=p) for p in (0, 1)] for d in (10, 36, 100)}
    pw = {}
    for L in (1, 4, 8):
        for s in range(1, L + 1):
            row = []
            for d in (10, 36, 100):
                for p in (0, 1):
                    sim = ctx.make(rom, state, 0, level=L, mon=(d, 0), f4_par=p, idle=7)
                    sim.h.sb(0x19B, s)
                    sim.frame(0)
                    row.append(sim.h.b(0x11))
            pw['L%d_stage%d' % (L, s)] = row
    out['power_var_levels_stage_rows_[near p0,p1, mid p0,p1, far p0,p1]'] = pw
    sim = ctx.make(rom, state, 0)
    out['equip_E068_E065_E2A_D030'] = [sim.h.b(0x68), sim.h.w(0x65), sim.h.w(0x2A), sim.c.wram[PROJ_BASE + 0x30]]
    res['chooser'] = out


def sec_gauge(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        sim = ctx.make(rom, state, slot, level=1)
        h = sim.h
        agi = h.b(0x189)
        seq = []
        sim.frame(B); sim.pad = 0
        for i in range(260):
            sim.frame(0)
            seq.append((h.b(0x1ED), h.b(0x1C), h.b(0x61)))
        end = next(i for i, s in enumerate(seq) if s[0])
        first_zero = next(i for i in range(end, len(seq)) if seq[i][0] == 0)
        ones = sum(1 for s in seq[end:first_zero] if s[0] == 1)
        sw = next(i for i, s in enumerate(seq) if s[1] == 0 and i > 2)
        out['slot%d' % slot] = {'agi': agi, 'gauge_loaded_frame_after_press': end + 1, 'swing_end_frame_after_press': sw + 1, 'start_value': seq[end][0],
                                'frames_counting_down': first_zero - end - ones, 'frames_held_at_1': ones, 'frames_to_zero': first_zero - end,
                                'formula_value': (100 - agi) // 2 + 50, 'frames_from_press_to_empty': first_zero + 1}
    # presses during the swing, during the projectile flight and spam
    sim = ctx.make(rom, state, 0, level=1)
    h = sim.h
    starts, prev = [], 0
    sim.frame(B); starts.append(0); prev = 0x20
    for f in range(1, 200):
        sim.frame(B if f in (6, 12, 18, 30, 40) else 0)
        st = h.b(0x1C)
        if st == 0x20 and prev != 0x20:
            starts.append(f)
        prev = st
    out['extra_presses_at_6_12_18_30_40_swing_starts'] = starts
    sim = ctx.make(rom, state, 0, level=1)
    h = sim.h
    starts, prev, gauge_at_start, e061s = [], 0, [], []
    for f in range(500):
        sim.frame(B if f % 2 == 0 else 0)
        st = h.b(0x1C)
        if st == 0x20 and prev != 0x20:
            starts.append(f); gauge_at_start.append(h.b(0x1ED)); e061s.append(h.b(0x61))
        prev = st
    out['spam_every_2nd_frame_swing_starts'] = starts[:8]
    out['spam_gauge_at_swing_start'] = gauge_at_start[:8]
    out['spam_E061_at_swing_start'] = e061s[:8]
    # a press as soon as the hero is free again: first frame with E01C == 0 and E061 == 0 (gauge freshly loaded)
    sim = ctx.make(rom, state, 0, level=1)
    h = sim.h
    sim.frame(B); sim.pad = 0
    ready = None
    for f in range(1, 300):
        sim.frame(0)
        if f > 3 and h.b(0x1C) == 0 and h.b(0x61) == 0:
            ready = f
            break
    sim.frame(B); sim.pad = 0
    again = None
    for f in range(1, 80):
        sim.frame(0)
        if h.b(0x1C):
            again = f
            break
    out['ready_frame_and_second_swing_gauge'] = {'ready_frame': ready, 'second_press_starts_swing': again is not None, 'gauge_at_second_start': h.b(0x1ED)}
    # direction held with the attack button / pressed during the swing
    for name, pad in (('B', B), ('B+right', B | 0x0100), ('B+up', B | 0x0800), ('B+left', B | 0x0200), ('B+down', B | 0x0400)):
        sim = ctx.make(rom, state, 0, level=1)
        h = sim.h
        h.sb(0x10, 0x82)
        x0, y0 = h.w(2), h.w(4)
        sim.frame(pad)
        facings = set()
        trace = []
        for i in range(1, 24):
            sim.frame(pad)
            if h.b(0x1C):
                facings.add(h.b(0x10))
            trace.append([h.b(0x1C), h.b(0x10), h.w(2) - x0, h.w(4) - y0])
        out.setdefault('direction_held_with_B_first_24_frames_state_facing_dx_dy', {})[name] = trace[-1]
        out.setdefault('direction_held_with_B_facings_seen_during_swing', {})[name] = sorted(facings)
    # walking while the projectile is in flight (swing over, E061 != 0): hold right from the frame the swing ends
    sim = ctx.make(rom, state, 0, level=1)
    h = sim.h
    h.sb(0x10, 0x82)
    sim.frame(B); sim.pad = 0
    walk = None
    for f in range(1, 200):
        pad = 0x0100 if (h.b(0x1C) == 0 and f > 3) else 0
        sim.frame(pad)
        if f > 3 and h.b(0x1C) == 0 and walk is None:
            walk = dict(start_frame=f, e061=h.b(0x61), x=h.w(2), y=h.w(4))
        if walk and 'after10' not in walk and f == walk['start_frame'] + 10:
            walk['after10'] = dict(e061=h.b(0x61), dx=h.w(2) - walk['x'], dy=h.w(4) - walk['y'], face=h.b(0x10))
    out['walk_right_from_swing_end_frame_state_and_displacement_after_10_frames'] = walk
    res['gauge'] = out


def sec_charge(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        for par in (0, 1):
            sim = ctx.make(rom, state, slot, level=8, f4_par=par)
            h = sim.h
            ev, prev = {}, 0
            end = ready = empty = None
            e061_first = None
            for f in range(1200):
                sim.frame(B)
                s = h.b(0x19B)
                if s != prev:
                    ev[str(s)] = f; prev = s
                if end is None and f > 0 and h.b(0x1C) == 0:
                    end = f
                if e061_first is None and h.b(0x61):
                    e061_first = f
                if ready is None and end is not None and h.b(0x61) == 0 and e061_first is not None:
                    ready = f
                if empty is None and ready is not None and h.b(0x1ED) == 0:
                    empty = f
            out['slot%d_parity%d' % (slot, par)] = {'agi': h.b(0x189), 'swing_end_frame': end, 'projectile_first_frame': e061_first, 'ready_frame_gauge_loaded': ready,
                                                    'gauge_empty_frame': empty, 'stage_reached_frame': ev}
    sim = ctx.make(rom, state, 0, level=8)
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
    sim = ctx.make(rom, state, 0, level=8)
    h = sim.h
    rel = None
    for f in range(1200):
        sim.frame(B if rel is None else 0)
        if rel is None and h.b(0x19B) == 1:
            rel = f
            sim.frame(0)
            out['release_after_stage1'] = {'stage1_frame': rel, 'state_byte_in_release_frame': h.b(0x1C), 'stage': h.b(0x19B), 'variant': h.b(0x11)}
            break
    sim = ctx.make(rom, state, 0, level=8)
    h = sim.h
    sim.frame(B)
    for f in range(1, 260):
        sim.frame(B if f < 200 else 0)
    out['release_at_stage0_state_byte'] = h.b(0x1C)
    caps = {}
    for L in (1, 2, 5, 8):
        sim = ctx.make(rom, state, 0, level=L)
        h = sim.h
        for f in range(1200):
            sim.frame(B)
        caps[str(L)] = h.b(0x19B)
    out['stage_after_1200_frames_holding_by_level'] = caps
    res['charge'] = out


def sec_power(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        for stage in range(1, 9):
            for cls in range(3):
                sums = {}
                for fname, face in FACINGS.items():
                    sim, smp, es, ea = run_attack(ctx, rom, state, slot, 4 * stage + cls, face, level=stage, kind='power', stage=stage)
                    sums[fname] = summarize(sim, smp, es, ea)
                if slot == 0:
                    rec = dict(sums)
                else:
                    ref = out['slot0'][str(stage)][str(cls)]
                    rec = {k: dict(compact_r(v), same_projectile_paths_as_hero0=[p['path_dx_dy_z'] for p in v['projectiles']] == [p['path_dx_dy_z'] for p in ref[k]['projectiles']],
                                   same_segments_as_hero0=v['segments'] == ref[k]['segments']) for k, v in sums.items()}
                out.setdefault('slot%d' % slot, {}).setdefault(str(stage), {})[str(cls)] = rec
        print('power slot', slot, flush=True)
    res['power'] = out


def sec_proj(ctx, rom, state, res):
    """Projectile flights of hero 0 without a target: stage 0 (normal throw) and stages 1-8 (charged), four facings; the heroes 1 and 2 for stage 0, 4 and 8."""
    if ctx.type == 4:
        return
    out = {}
    for stage in range(0, 9):
        for fname, face in FACINGS.items():
            if stage == 0:
                sim, smp, es, ea = run_attack(ctx, rom, state, 0, 0, face)
            else:
                sim, smp, es, ea = run_attack(ctx, rom, state, 0, 4 * stage, face, level=stage, kind='power', stage=stage)
            out.setdefault('stage%d' % stage, {})[fname] = dict(swing_end_frame=es, ready_frame=ea, projectiles=proj_summary(smp),
                                                              gauge_after=smp[-1]['gauge'], e19b_values=sorted(set(s['stage'] for s in smp)))
    other = {}
    for slot in (1, 2):
        for stage in (0, 4, 8):
            for fname, face in FACINGS.items():
                if stage == 0:
                    sim, smp, es, ea = run_attack(ctx, rom, state, slot, 0, face)
                else:
                    sim, smp, es, ea = run_attack(ctx, rom, state, slot, 4 * stage, face, level=stage, kind='power', stage=stage)
                ps = proj_summary(smp)
                other['slot%d_stage%d_%s' % (slot, stage, fname)] = dict(ready_frame=ea, same_paths_as_hero0=[p['path_dx_dy_z'] for p in ps] == [p['path_dx_dy_z'] for p in out['stage%d' % stage][fname]['projectiles']],
                                                                       spawn_offsets=[p['spawn_offset_from_hero'] for p in ps])
    out['other_heroes'] = other
    res['proj'] = out


def hit_run(ctx, rom, state, var, kind, stage, mon, face=0x82, slot=0, nframes=400, mon2=None, level=8, mon_setup=None):
    sim = ctx.start(rom, state, slot, var, face, level=level, kind=kind, stage=stage, mon=mon, mon2=mon2)
    h, m = sim.h, sim.m
    m2 = sim.m2 if mon2 is not None else None
    rec = {'hits': [], 'hits2': [], 'hero_flag_set': None, 'dmg_stage': [], 'e1ed_at_hit': [], 'ready_frame': None, 'proj_dying_frames': []}
    hp, hp2 = m.w(0x182), (m2.w(0x182) if m2 else None)
    for f in range(1, nframes):
        sim.frame(0)
        n = m.w(0x182)
        if n != hp:
            rec['hits'].append([f, hp - n]); rec['dmg_stage'].append(h.b(0x19B)); rec['e1ed_at_hit'].append(h.b(0x1ED)); hp = n
        if m2 is not None:
            n2 = m2.w(0x182)
            if n2 != hp2:
                rec['hits2'].append([f, hp2 - n2]); hp2 = n2
        pr = R.proj_entries(sim)
        for k in range(3):
            if pr[k]['dying'] == 8:
                rec['proj_dying_frames'].append([k, f])
        if rec['ready_frame'] is None and f > 3 and h.b(0x1C) == 0 and h.b(0x61) == 0:
            rec['ready_frame'] = f
        if rec['ready_frame'] is not None and f > rec['ready_frame'] + 60:
            break
    return rec, sim


def sec_hits(ctx, rom, state, res):
    import validate_phys as VP
    out = {}
    stages = (0, 1, 3, 6, 8)
    def go(stage, mon, **kw):
        if stage == 0:
            return hit_run(ctx, rom, state, 0, 'normal', 0, mon, **kw)
        return hit_run(ctx, rom, state, 4 * stage, 'power', stage, mon, level=stage if kw.get('level') is None else kw['level'], **{k: v for k, v in kw.items() if k != 'level'})
    # one target in front: damage frame, damage, E19B and E1ED at the hit, how the projectile ends
    row = {}
    for stage in stages:
        for dx in (-30, -60):
            rec, sim = go(stage, (dx, 0))
            row['stage%d_dx%d' % (stage, dx)] = rec
    out['single_target'] = row
    # two targets: both in front of the hero, in a line (near one first) and side by side; hits are listed per target as [frame, damage]
    two = {}
    for stage in (0, 3, 6, 8):
        for name, a, b in (('line_-30_-60', (-30, 0), (-60, 0)), ('line_-45_-75', (-45, 0), (-75, 0)), ('side_by_side_-45_dy-12_+12', (-45, -12), (-45, 12))):
            rec, sim = go(stage, a, mon2=b)
            two['stage%d_%s' % (stage, name)] = {'first_target': a, 'first_hits': rec['hits'], 'second_target': b, 'second_hits': rec['hits2'], 'projectile_dying_frames_[entry,frame]': rec['proj_dying_frames']}
    out['two_targets'] = two
    # reach: the frame of the first hit of a target at distance d straight ahead (None = no hit), four facings
    reach = {}
    for fname, face in FACINGS.items():
        fx = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[fname]
        for stage in (0, 4, 8):
            row = {}
            for d in (14, 40, 70, 100, 130, 160, 200):
                rec, sim = go(stage, (fx[0] * d, fx[1] * d), face=face, nframes=260)
                row[str(d)] = [rec['hits'][0][0], rec['hits'][0][1]] if rec['hits'] else None
            reach['%s_stage%d' % (fname, stage)] = row
    out['hit_frame_and_damage_by_distance_ahead_none_means_no_hit'] = reach
    # damage per stage with the real hit routine (random RNG states) for this weapon type
    sim = ctx.make(rom, state, 0, level=8, mon=(-14, 0))
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
            hit, d = VP_hit(VP, env)
            vals.append(d if hit else -1)
        ok = [v for v in vals if v >= 0]
        a_ = env.obj(0).b(0x198)
        dmg[str(stage)] = {'base_atk_x_(2s+4)>>2': (a_ * (2 * stage + 4)) >> 2, 'hit_rate': len(ok) / len(vals), 'min': min(ok), 'mean': round(sum(ok) / len(ok), 1), 'max': max(ok)}
    out['damage_by_stage_300_random_rng_states_hero0_dummy_def0_ev0'] = dmg
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
                hit, d = VP_hit(VP, env)
                vals.append(d if hit else -1)
            ok = [v for v in vals if v >= 0]
            pen['stage%d_gauge%d' % (stage, g)] = {'hit_rate': len(ok) / len(vals), 'mean': round(sum(ok) / len(ok), 1) if ok else 0, 'max': max(ok) if ok else 0}
    out['damage_by_gauge_value_300_random_rng_states'] = pen
    env.obj(0).sb(0x1ED, 0)
    out['hero0_stats_during_damage_runs_atk_hit_crit_E1E6'] = [env.obj(0).b(0x198), env.obj(0).b(0x197), env.obj(0).b(0x196), env.obj(0).b(0x1E6)]
    # stats of the nine rows of the type after the equip routines, per weapon level (crit base halving for types > 4)
    rows = {}
    for grade in range(9):
        c2 = R.Ctx(ctx.type, grade)
        for lvl in (1, 8):
            s2 = c2.make(rom, state, 0, level=lvl)
            h = s2.h
            rows['row%d_level%d' % (c2.row, lvl)] = {'atk': h.b(0x198), 'hit': h.b(0x197), 'crit': h.b(0x196), 'status_word': h.w(0x199), 'status_chance': h.b(0x1F7), 'E194': h.w(0x194), 'E1E8': h.b(0x1E8), 'E19C': h.b(0x19C)}
    out['rows_of_type_hero0_after_equip'] = rows
    # knockback by damage against the target's maximum HP (hurt code) with a stage 0 / 4 / 8 hit
    kb = {}
    for maxhp in (600, 1000, 2000):
        for stage in (0, 4, 8):
            sim = ctx.start(rom, state, 0, 0 if stage == 0 else 4 * stage, 0x82, level=8, kind='normal' if stage == 0 else 'power', stage=stage, mon=(-24, 0), monhp=maxhp)
            m = sim.m
            m.sw(0x184, maxhp); m.sw(0x182, maxhp)
            x0, y0 = m.w(2), m.w(4)
            hit = dmg_ = e11 = None
            for f in range(1, 140):
                sim.frame(0)
                if hit is None and m.w(0x182) != maxhp:
                    hit = f; dmg_ = maxhp - m.w(0x182)
                if hit and e11 is None and m.b(0x11) >= 0x80:
                    e11 = m.b(0x11)
            kb['maxhp%d_stage%d' % (maxhp, stage)] = {'damage': dmg_, 'max_hp_quarter': maxhp // 4, 'hurt_code_E011': e11, 'displacement_after_140_frames': [m.w(2) - x0, m.w(4) - y0], 'target_facing_E010': m.b(0x10)}
    out['target_knockback_by_damage_vs_max_hp'] = kb
    res['hits'] = out


def predict_hit(smp, mon, scroll):
    """Hit test of the projectile engine (`$C2:C5B4-C62B`) applied to the recorded flights.  In frame i the entry is tested at the position it had at the end of
    frame i - 1 (the step tests, then moves) against the target as it is in frame i; the test succeeds when
    2 |tx - px| < wp + tw  and  2 |ty - hh - 1 - py| < hp + th,   (px, py) = entry position - scroll,  tx = E020 (signed word), ty = E022,
    hh = (E074 & 0x7F) + E045 of the target, (tw, th) = its body box E0CA / E0CB, wp = hp = 32 for kind 2 (javelin), 16 otherwise; both differences must also be < 0x60.
    Entries that are still delayed or already dying are skipped; boomerang entries (kind >= 3) are tested only before their return phase (E008 = 0xFF).
    `mon` = per-sample list of (tx, ty, hh, tw, th).  Returns the first frame i in which a test succeeds, or None."""
    for i in range(1, len(smp)):
        tx, ty, hh, tw, th = mon[min(i, len(mon) - 1)]
        if tx >= 0x8000:
            tx -= 0x10000
        if not (tw or th):
            continue
        for e in smp[i - 1]['proj']:
            kind = e['kind']
            if not kind or kind & 0xF8 or e['dying']:
                continue
            if kind >= 3 and e['f8'] == 0xFF:
                continue
            wp = 32 if kind == 2 else 16
            px, py = e['x'] - scroll[0], e['y'] - scroll[1]
            dx, dy = abs(tx - px), abs((ty - hh - 1) - py)
            if dx < 0x60 and dy < 0x60 and 2 * dx < ((wp + tw) & 0xFF) and 2 * dy < ((wp + th) & 0xFF):
                return i
    return None


def sec_model(ctx, rom, state, res):
    """Random target positions around the flight path: the hit box model of predict_hit against the real engine (damage dealt or not, frame of the damage)."""
    if ctx.type == 4:
        return
    out = {}
    rnd = random.Random(11 + ctx.type)
    for stage in (0, 8):
        rows = []
        all_fields = set()
        for n in range(80):
            dx, dy = rnd.randint(-175, -3), rnd.randint(-45, 35)
            if stage == 0:
                sim = ctx.start(rom, state, 0, 0, 0x82, kind='normal', mon=(dx, dy))
            else:
                sim = ctx.start(rom, state, 0, 4 * stage, 0x82, level=stage, kind='power', stage=stage, mon=(dx, dy))
            m, w = sim.m, sim.c.wram
            smp = [R.sample(sim)]
            mon = [(m.w(0x20), m.w(0x22), (m.b(0x74) & 0x7F) + m.b(0x45), m.b(0xCA), m.b(0xCB))]
            scroll = (w[0xA8] | w[0xA9] << 8, w[0xAA] | w[0xAB] << 8)
            hp0 = m.w(0x182)
            hit = None
            ready = None
            for f in range(1, 260):
                sim.frame(0)
                smp.append(R.sample(sim))
                mon.append((m.w(0x20), m.w(0x22), (m.b(0x74) & 0x7F) + m.b(0x45), m.b(0xCA), m.b(0xCB)))
                if hit is None and m.w(0x182) != hp0:
                    hit = f
                if ready is None and f > 3 and smp[-1]['st'] == 0 and smp[-1]['e061'] == 0:
                    ready = f
                if ready is not None and f > ready + 6:
                    break
            all_fields.update(mon)
            pred = predict_hit(smp, mon, scroll)
            rows.append([dx, dy, 1 if pred is not None else 0, pred, 1 if hit is not None else 0, hit])
        bad = [r for r in rows if r[2] != r[4]]
        diffs = sorted(set(r[5] - r[3] for r in rows if r[2] and r[4]))
        out['stage%d' % stage] = {'rows_dx_dy_predicted_pred_sample_observed_obs_frame': rows, 'mismatches': len(bad), 'hits_observed': sum(r[4] for r in rows), 'frame_offset_observed_minus_predicted': diffs,
                                  'target_E0CA_E0CB_and_height_seen_[w, h, height]': sorted(set((rr[3], rr[4], rr[2]) for rr in all_fields))}
    res['model'] = out


def sec_probes(ctx, rom, state, res):
    """Controlled experiments on the projectile hit rules: the hit mask E02E, the boomerang's return phase, the recharge gauge at the hit, status infliction."""
    out = {}
    if ctx.type != 4:
        # (1) the hit mask E02E: bit k of the shooter's E02E = monster slot 3 + k already hit by this volley
        sim = ctx.start(rom, state, 0, 12, 0x82, level=3, kind='power', stage=3, mon=(-30, 0), mon2=(-30, 14))
        h, m, m2 = sim.h, sim.m, sim.m2
        hp, hp2 = m.w(0x182), m2.w(0x182)
        log = []
        for f in range(1, 90):
            sim.frame(0)
            if m.w(0x182) != hp or m2.w(0x182) != hp2:
                log.append([f, hp - m.w(0x182), hp2 - m2.w(0x182), h.b(0x2E)])
                hp, hp2 = m.w(0x182), m2.w(0x182)
        out['e02e_two_monsters_slots_3_4_stage3_log_[frame, damage_slot3, damage_slot4, E02E]'] = log
        # the hit flag writes of the projectile engine ($C2:C649, ORA $E059,X) counted per frame, with the mask E02E as the game keeps it and with E02E forced to 0 every frame
        for stage in (3, 8):
            for hold_mask in (False, True):
                sim = ctx.start(rom, state, 0, 4 * stage, 0x82, level=stage, kind='power', stage=stage, mon=(-30, 0))
                h, m, c = sim.h, sim.m, sim.c
                writes = []
                orig = c.step
                def st(orig=orig, writes=writes, sim=sim, c=c, m=m):
                    if (c.PB << 16 | c.PC) in (0xC2C649, 0x02C649) and c.X == m.base - 0xE000:
                        writes.append(sim.f - f0)
                    orig()
                c.step = st
                f0 = sim.f - 1
                for f in range(1, 120):
                    if hold_mask:
                        h.sb(0x2E, 0)
                    sim.frame(0)
                out['hit_flag_writes_on_a_target_at_30_px_frames_stage%d_%s' % (stage, 'E02E_forced_to_0' if hold_mask else 'normal')] = writes
    if ctx.type == 6:
        # (2) boomerang: a target placed on the boomerang in the return phase is not hit; the same placement in the outbound phase is
        for phase in ('outbound', 'return'):
            sim = ctx.start(rom, state, 0, 0, 0x82, kind='normal', mon=(-300, 0))
            h, m = sim.h, sim.m
            done = None
            hp = m.w(0x182)
            for f in range(1, 140):
                sim.frame(0)
                e = R.proj_entries(sim)[0]
                if done is None and e['kind'] and ((phase == 'outbound' and e['f8'] > 100 and e['f8'] < 255) or (phase == 'return' and e['f8'] == 255 and e['fA'] > 60)):
                    hh = (m.b(0x74) & 0x7F) + m.b(0x45)
                    m.sw(2, e['x']); m.sw(4, e['y'] + hh)
                    h.sb(0x2E, 0)
                    done = f
                    start_hp = m.w(0x182)
                    placed = [e['x'] - h.w(2), e['y'] - h.w(4), e['f8'], e['fA']]
                if done is not None and f == done + 8:
                    out['boomerang_target_placed_on_boomerang_%s' % phase] = {'frame': done, 'entry_offset_from_hero_x_y_and_f8_fA': placed, 'damage_after_8_frames': start_hp - m.w(0x182)}
                    break
    # (3) the recharge gauge at the hit: a second throw as soon as the hero is free again
    sim = ctx.start(rom, state, 0, 0, 0x82, kind='normal', mon=(-30, 0) if ctx.type != 4 else (-40, 0))
    h, m = sim.h, sim.m
    hp = m.w(0x182)
    log = []
    ready = None
    second = None
    for f in range(1, 400):
        pad = 0
        if ready is None and f > 3 and h.b(0x1C) == 0 and h.b(0x61) == 0:
            ready = f
        if ready is not None and second is None and f == ready + 1:
            pad = B
            second = f
        sim.frame(pad)
        if m.w(0x182) != hp:
            log.append([f, hp - m.w(0x182), h.b(0x1ED), h.b(0x19B)])
            hp = m.w(0x182)
        if second is not None and f > second + 90:
            break
    out['first_and_second_shot_log_[frame, damage, E1ED_at_that_frame, E19B]_ready_frame_second_press_frame'] = [log, ready, second]
    # (4) status infliction: every row of the type that carries a status word, 60 RNG start indexes, a stage 0 hit on the dummy
    stat = {}
    for grade in range(9):
        c2 = R.Ctx(ctx.type, grade)
        o = 0x101000 + 12 * c2.row
        word = rom[o + 9] | rom[o + 10] << 8
        if not word:
            continue
        res_by = {}
        n_hit = n_status = 0
        seen = {}
        for k in range(60):
            sim = c2.start(rom, state, 0, 0, 0x82, kind='normal', mon=(-30, 0) if ctx.type != 4 else (-40, 0))
            rr = random.Random(1000 + k)
            for q in range(0x3F1, 0x400):
                sim.c.wram[q] = rr.randrange(256)
            sim.c.wram[0x3F0] = rr.randrange(15)
            m = sim.m
            hp0, s0 = m.w(0x182), (m.w(0x190), m.b(0x192))
            for f in range(1, 140):
                sim.frame(0)
            if m.w(0x182) != hp0:
                n_hit += 1
                st = m.w(0x190)
                seen[st] = seen.get(st, 0) + 1
                if st != s0[0]:
                    n_status += 1
        stat['row%d' % c2.row] = {'status_word': word, 'chance_byte': rom[o + 11], 'hits': n_hit, 'target_status_changed': n_status, 'target_E190_values_after_hit': {str(k): v for k, v in sorted(seen.items())}}
    out['status_infliction_stage0_hit_60_rng_starts'] = stat
    res['probes'] = out


def VP_hit(VP, env):
    return VP.rom_hit(env, 0, 3)


def vulnerable_frames(ctx, rom, state, var, kind, stage, face=0x82, slot=0):
    """For every frame f of the attack: put a dummy monster on the hero, give it a large weapon box for that single frame and see whether the
    hero's hit flag routine ($C1:D23F) fires.  Returns (frames with a non-empty body box, frames where the hero can be hit)."""
    sim, smp, es, ea = run_attack(ctx, rom, state, slot, var, face, level=max(stage, 1), kind=kind, stage=stage)
    ref = [bool(s['body'][2] and s['body'][3]) for s in smp[:es + 1]]
    res = []
    for f in range(es + 1):
        sim = ctx.start(rom, state, slot, var, face, level=max(stage, 1), kind=kind, stage=stage, mon=(0, 0))
        h, m, c = sim.h, sim.m, sim.c
        hits = [0]
        orig = c.step
        def st(orig=orig, hits=hits, sim=sim, c=c):
            if (c.PB << 16 | c.PC) in (0xC1D23F, 0x01D23F) and c.X == sim.base:
                hits[0] += 1
            orig()
        c.step = st
        got = False
        for g in range(es + 1):
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


def sec_invuln(ctx, rom, state, res):
    out = {}
    cases = [('normal_var0', 0, 'normal', 0), ('normal_var2', 2, 'normal', 0), ('power_stage8_cls2', 34, 'power', 8)]
    for name, var, kind, stage in cases:
        ref, hit = vulnerable_frames(ctx, rom, state, var, kind, stage)
        out[name] = {'frames_with_body_box': [i for i, x in enumerate(ref) if x], 'frames_hero_hittable': [i for i, x in enumerate(hit) if x]}
        print('invuln', name, flush=True)
    res['invulnerability'] = out


SECTIONS = {'structure': sec_structure, 'normal': sec_normal, 'chooser': sec_chooser, 'gauge': sec_gauge, 'charge': sec_charge, 'power': sec_power,
            'proj': sec_proj, 'model': sec_model, 'hits': sec_hits, 'probes': sec_probes, 'invuln': sec_invuln}


def main():
    rom = romio.rom_from_argv()
    state, out_path, weapon = sys.argv[1], sys.argv[2], sys.argv[3]
    wanted = sys.argv[4:] or list(SECTIONS)
    wtype = R.TYPE_BY_NAME[weapon] if weapon in R.TYPE_BY_NAME else int(weapon)
    ctx = R.Ctx(wtype)
    res = {}
    if os.path.exists(out_path):
        res = json.load(open(out_path))
    res['source'] = 'tools/ranged_attacks.py: frame-exact runs of the real main routine $C0:B08C on a save state (docs/weapons-ranged.md)'
    res['weapon_type'] = wtype
    res['weapon_name'] = R.TYPE_NAMES.get(wtype)
    res['weapon_row_used'] = ctx.row
    res['clock'] = {'frame_hz': HZ, 'hero_step_frames': 5, 'hero_step_hz': 12.0198, 'hero_step_phase': G.HERO_TICK_PHASE}
    t = time.time()
    for name in wanted:
        SECTIONS[name](ctx, rom, state, res)
        with open(out_path, 'w') as fh:
            dump_json(res, fh)
            fh.write('\n')
        print(name, 'done after', round(time.time() - t), 's', flush=True)


if __name__ == '__main__':
    main()

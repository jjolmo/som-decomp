"""Melee weapon attacks (weapon type 1 sword, 2 axe, 3 spear; type 0 = glove also works) of the three heroes, measured by running the real game routines frame by frame.
usage: weapon_attacks.py ROM STATE OUT.json WEAPON [section ...]
WEAPON: sword | axe | spear | glove | a weapon type number 0-7.  STATE: a ZSNES v143 save state taken during play on an open map with the three heroes idle.
sections (default: all): structure variants chooser gauge charge power hits invuln spawn grades status
Generalises tools/glove_attacks.py: the same experiments, with the weapon row (type * 9 + grade) as a parameter and the animation script table of the weapon type
(`$D1:3040 + 240 * type`).  Everything runs through tools/glove_sim.py, i.e. the real main routine $C0:B08C once per video frame with pad 1 injected (B = attack).
Writes numbers only.  One weapon takes roughly 25-40 minutes of CPU for all sections (invuln about 10)."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio
import glove_sim as G
import glove_attacks as ga
from glove_attacks import B, FACINGS, dump_json, sbyte, vxy, segments, compact, piece_info, total_ticks, PRESET_TABLE

TYPES = {'glove': 0, 'sword': 1, 'axe': 2, 'spear': 3}
SCRIPT_BASE, SCRIPT_STRIDE = 0x3040, 240      # bank $D1: attack/charge script pointer table of weapon type t at $3040 + 240 t; word [(anim * 3 + facing) * 2]
KIND_TABLE, ANIM_MAP = 0x0000, 0x0480          # bank $D1: chooser kinds (576 bytes) and the per-type map kind -> animation (40 bytes per type)
SPAWN_SLOTS = range(3, 32)


class Ctx:
    """Weapon under test: type, equipped row (grade 0 of the type unless given) and the helpers that depend on them."""
    def __init__(self, wtype, grade=0):
        self.type, self.row = wtype, wtype * 9 + grade

    def make(self, rom, state, slot, level=1, mon=None, press_phase=2, f4_par=0, idle=12):
        sim = G.GloveSim(rom, state, slot, self.row, level, mon=mon)
        sim.force_m = None
        def e418(cp):
            if sim.force_m is not None:
                cp.A = (cp.A & 0xFF00) | sim.force_m
            return False
        sim.c.hooks[0x01E418] = sim.c.hooks[0xC1E418] = e418      # result of the distance-class routine $C1:E4CC, optionally overridden
        sim.phase0 = (press_phase - idle) % 5
        for _ in range(idle):
            sim.frame(0)
        sim.f4 = (f4_par - sim.f) & 0xFF
        return sim

    def anim_ptr(self, rom, var, facing):
        o = 0x110000 + SCRIPT_BASE + SCRIPT_STRIDE * self.type + 2 * (var * 3 + facing)
        return rom[o] | rom[o + 1] << 8

    def kind_for(self, rom, var, stage=0):
        """(distance class, $F4 parity) for which the chooser $C1:E40E returns animation `var` at charge stage `stage` (no status variant, target bit clear)."""
        for d in range(4):
            for par in (0, 1):
                kind = rom[0x110000 + KIND_TABLE + d * 144 + stage * 16 + par]
                if rom[0x110000 + ANIM_MAP + 40 * self.type + kind] == var:
                    return d, par
        raise ValueError('animation %d is not reachable at stage %d' % (var, stage))

    def run_variant(self, rom, state, slot, var, face, level=1, kind='normal', stage=0, press_phase=2, watch_spawn=False):
        """Start animation `var` the way the game does: a B press for a normal swing, the release of a charged button for a power attack.  The distance class
        (result of $C1:E4CC) and the parity of $F4 are chosen so that the real chooser returns `var`; E011 is checked, not forced."""
        d, par = self.kind_for(rom, var, stage)
        sim = self.make(rom, state, slot, level=level, press_phase=press_phase, f4_par=par)
        sim.force_m = d
        sim.h.sb(0x10, face)
        sim.events.clear()
        pre = sim.sample()['ptr']
        if kind == 'normal':
            sim.frame(B)
        else:
            sim.h.sb(0x19B, stage)
            sim.frame(0)
        sim.pad = 0
        if sim.h.b(0x11) != var:
            raise RuntimeError('chooser returned %d, wanted %d' % (sim.h.b(0x11), var))
        samples = [sim.sample()]
        end = None
        ids0 = spawn_ids(sim) if watch_spawn else None
        spawned = {}
        for i in range(1, 900):
            sim.frame(0)
            samples.append(sim.sample())
            if watch_spawn:
                for s, v in spawn_ids(sim).items():
                    if ids0.get(s) != v:
                        spawned.setdefault((s, v), i)
            if samples[-1]['st'] == 0:
                end = i
                break
        sim.pre_ptr = pre
        if watch_spawn:
            sim.spawned = spawned
        return sim, samples, end


def first_step(sim, samples):
    """Frame (counted from the press/release frame 0) in which the attack script is first read; 0 when the hero step of the press frame already does it."""
    for i, smp in enumerate(samples):
        if smp['ptr'] != sim.pre_ptr:
            return i
    return None


def summarize(sim, samples, end):
    d = ga.summarize(sim, samples, end)
    d['first_step_frame'] = first_step(sim, samples)
    return d


def spawn_ids(sim):
    """{slot: object id byte} of all active objects in the slots 3..31 (monsters, effects, projectiles)."""
    out = {}
    for s in SPAWN_SLOTS:
        v = sim.env.obj(s).b(0)
        if v:
            out[s] = v
    return out


def piece_walk(rom, ptr, pieces):
    """Static walk of one animation script like glove_attacks.piece_info, additionally keeping the order of the items: 'seq' lists ['t', steps] for a run of
    frame words and ['c', script address] for a call (op 0xF1), in script order.  Also counts the operation bytes used."""
    if ptr in pieces:
        return
    info = {'addr': ptr, 'ticks': 0, 'sounds': [], 'presets': [], 'calls': [], 'seq': [], 'ops': {}}
    pieces[ptr] = info
    for off, kind, b in G.decode_script(rom, ptr):
        if kind == 'frame':
            d = b[0] & 7
            n = (d if d < 4 else 0) + 1
            info['ticks'] += n
            if info['seq'] and info['seq'][-1][0] == 't':
                info['seq'][-1][1] += n
            else:
                info['seq'].append(['t', n])
        elif kind == 'op':
            info['ops'][str(b[0])] = info['ops'].get(str(b[0]), 0) + 1
            if b[0] == 0xF9:
                info['sounds'].append(b[1] | b[2] << 8)
            elif 0x8F <= b[0] <= 0xAA:
                k = b[0] - 0x8F
                info['presets'].append([k] + list(rom[PRESET_TABLE + 4 * k:PRESET_TABLE + 4 * k + 3]))
            elif b[0] == 0xF1:
                q = b[1] | b[2] << 8
                piece_walk(rom, q, pieces)
                info['calls'].append(q)
                info['seq'].append(['c', q])


def sec_structure(ctx, rom, state, res):
    out = {}
    for facing in range(3):
        pieces = {}
        normals = {ctx.anim_ptr(rom, v, facing): v for v in range(4)}
        table = {}
        for var in range(0, 40):
            ptr = ctx.anim_ptr(rom, var, facing)
            piece_walk(rom, ptr, pieces)
            table[str(var)] = {'script': ptr, 'total_steps': total_ticks(pieces, ptr)}
        out['facing%d' % facing] = {'variants': table, 'pieces': {str(k): v for k, v in sorted(pieces.items())},
                                    'normal_variant_scripts': {str(k): v for k, v in normals.items()}}
    o = 0x110000 + ANIM_MAP + 40 * ctx.type
    out['kind_to_animation_map'] = list(rom[o:o + 40])
    # distinct script addresses among the 40 animations (animations that share a script are the same attack)
    out['shared_scripts_facing2'] = {str(v): [w for w in range(40) if ctx.anim_ptr(rom, w, 2) == ctx.anim_ptr(rom, v, 2)] for v in range(40)}
    res['structure'] = out


def sec_variants(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        hero = {}
        for var in range(4):
            sums = {}
            for fname, face in FACINGS.items():
                sim, samples, end = ctx.run_variant(rom, state, slot, var, face)
                sums[fname] = summarize(sim, samples, end)
            hero[str(var)] = dict(sums) if slot == 0 else {k: compact(v) for k, v in sums.items()}
        h = sim.h
        hero['agi'] = h.b(0x189); hero['atk'] = h.b(0x198); hero['hit'] = h.b(0x197); hero['crit'] = h.b(0x196)
        out['slot%d' % slot] = hero
    ph = {}
    for p in range(5):
        row = {}
        for var in range(4):
            sim, samples, end = ctx.run_variant(rom, state, 0, var, FACINGS['left'], press_phase=p)
            row[str(var)] = {'first_step_frame': first_step(sim, samples), 'swing_frames': end}
        ph[str(p)] = row
    out['by_press_phase'] = ph
    res['normal_runs'] = out


def cls_of(ctx, rom, state, face, dx, dy, par=0, slot=0):
    sim = ctx.make(rom, state, slot, mon=(dx, dy), f4_par=par, idle=7)
    sim.h.sb(0x10, face)
    sim.frame(B)
    return sim.h.b(0x11)


def sec_chooser(ctx, rom, state, res):
    out = {}
    for name, mk in (('x', lambda d: (d, 0)), ('y', lambda d: (0, d))):
        row = [cls_of(ctx, rom, state, FACINGS['left'], *mk(d)) for d in range(0, 64)]
        out['threshold_' + name] = [[d, row[d]] for d in range(len(row)) if d == 0 or row[d] != row[d - 1]]
    grid = {}
    for dx in (0, 20, 30, 45):
        grid[str(dx)] = [cls_of(ctx, rom, state, FACINGS['left'], dx, dy) for dy in (0, 20, 30, 45)]
    out['grid_dx_rows_dy_cols_0_20_30_45'] = grid
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
    # E068 (weapon type used by the chooser) and the script table pointer after the equip refresh
    sim = ctx.make(rom, state, 0)
    out['equip_E068_E065_E2A'] = [sim.h.b(0x68), sim.h.w(0x65), sim.h.w(0x2A)]
    res['chooser'] = out


def sec_gauge(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        sim = ctx.make(rom, state, slot, level=1)
        h = sim.h
        agi = h.b(0x189)
        seq = []
        sim.frame(B); sim.pad = 0
        for i in range(140):
            sim.frame(0)
            seq.append(h.b(0x1ED))
        end = next(i for i, s in enumerate(seq) if s)
        first_zero = next(i for i in range(end, len(seq)) if seq[i] == 0)
        ones = sum(1 for s in seq[end:first_zero] if s == 1)
        out['slot%d' % slot] = {'agi': agi, 'start_value': seq[end], 'frames_counting_down': first_zero - end - ones,
                                'frames_held_at_1': ones, 'frames_to_zero': first_zero - end,
                                'formula_value': (100 - agi) // 2 + 50}
    sim = ctx.make(rom, state, 0, level=1)
    h = sim.h
    starts, prev = [], 0
    sim.frame(B); starts.append(0); prev = 0x20
    for f in range(1, 200):
        pad = B if f in (6, 12, 18) else 0
        sim.frame(pad)
        st = h.b(0x1C)
        if st == 0x20 and prev != 0x20:
            starts.append(f)
        prev = st
    out['extra_presses_at_6_12_18_swing_starts'] = starts
    sim = ctx.make(rom, state, 0, level=1)
    h = sim.h
    starts, prev, gauge_at_start, variants = [], 0, [], []
    for f in range(400):
        sim.frame(B if f % 2 == 0 else 0)
        st = h.b(0x1C)
        if st == 0x20 and prev != 0x20:
            starts.append(f); gauge_at_start.append(h.b(0x1ED)); variants.append(h.b(0x11))
        prev = st
    out['spam_every_2nd_frame_swing_starts'] = starts[:8]
    out['spam_gauge_at_swing_start'] = gauge_at_start[:8]
    out['spam_variant_at_swing_start'] = variants[:8]
    sim = ctx.make(rom, state, 0, level=1)
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
    # direction held together with the attack button, and a direction pressed in the middle of the swing
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
            facings.add(h.b(0x10)) if h.b(0x1C) else None
            trace.append([h.b(0x1C), h.b(0x10), h.w(2) - x0, h.w(4) - y0])
        out.setdefault('direction_held_with_B_first_24_frames_state_facing_dx_dy', {})[name] = trace[-1]
        out.setdefault('direction_held_with_B_facings_seen_during_swing', {})[name] = sorted(facings)
    for name, pad in (('right', 0x0100), ('up', 0x0800)):
        sim = ctx.make(rom, state, 0, level=1)
        h = sim.h
        h.sb(0x10, 0x82)
        x0, y0 = h.w(2), h.w(4)
        sim.frame(B); sim.pad = 0
        facings = set()
        for i in range(1, 22):
            sim.frame(pad if i >= 8 else 0)
            if h.b(0x1C):
                facings.add(h.b(0x10))
        out.setdefault('direction_pressed_from_frame_8_state_facing_dx_dy_facings_seen', {})[name] = [h.b(0x1C), h.b(0x10), h.w(2) - x0, h.w(4) - y0, sorted(facings)]
    res['gauge'] = out


def sec_charge(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        for par in (0, 1):
            sim = ctx.make(rom, state, slot, level=8, f4_par=par)
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
            out['slot%d_parity%d' % (slot, par)] = {'agi': h.b(0x189), 'swing_end_frame': end, 'stage_reached_frame': ev, 'variant_of_swing': None}
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
    for f in range(900):
        sim.frame(B if rel is None else 0)
        if rel is None and h.b(0x19B) == 1:
            rel = f
            sim.frame(0)
            out['release_after_stage1'] = {'stage1_frame': rel, 'state_byte_in_release_frame': h.b(0x1C), 'stage': h.b(0x19B), 'variant': h.b(0x11)}
            break
    sim = ctx.make(rom, state, 0, level=8)
    h = sim.h
    sim.frame(B)
    for f in range(1, 200):
        sim.frame(B if f < 120 else 0)
    out['release_at_stage0_state_byte'] = h.b(0x1C)
    caps = {}
    for L in (1, 2, 5, 8):
        sim = ctx.make(rom, state, 0, level=L)
        h = sim.h
        for f in range(1000):
            sim.frame(B)
        caps[str(L)] = h.b(0x19B)
    out['stage_after_1000_frames_holding_by_level'] = caps
    res['charge'] = out


def sec_power(ctx, rom, state, res):
    out = {}
    for slot in range(3):
        for stage in range(1, 9):
            for cls in range(3):
                sums = {}
                for fname, face in FACINGS.items():
                    sim, samples, end = ctx.run_variant(rom, state, slot, 4 * stage + cls, face, level=stage, kind='power', stage=stage)
                    sums[fname] = summarize(sim, samples, end)
                rec = dict(sums) if slot == 0 else {k: compact(v) for k, v in sums.items()}
                out.setdefault('slot%d' % slot, {}).setdefault(str(stage), {})[str(cls)] = rec
        print('power slot', slot, flush=True)
    res['power'] = out


def sec_spawn(ctx, rom, state, res):
    """Objects that appear in the slots 3..31 during every normal variant and every charged attack of hero 0 (a projectile or effect object would show here)."""
    out = {}
    for var in list(range(4)) + [4 * s + c for s in range(1, 9) for c in range(3)]:
        kind, stage = ('normal', 0) if var < 4 else ('power', var // 4)
        found = {}
        for fname in ('left', 'up'):
            sim, samples, end = ctx.run_variant(rom, state, 0, var, FACINGS[fname], level=max(stage, 1), kind=kind, stage=stage, watch_spawn=True)
            found[fname] = [[s, v, f] for (s, v), f in sorted(sim.spawned.items())]
        out[str(var)] = found
    res['spawn'] = out


def sec_grades(ctx, rom, state, res):
    """Do the nine weapon rows (grades) of the type differ in any attack timeline?  Compares the full summaries of normal variants 0-3 and of the power attacks
    of stages 1, 3, 8 (class 0 and 2), facing left, hero 0, against grade 0."""
    def key(c):
        out = []
        for var in (0, 1, 2, 3, 4, 6, 12, 14, 32, 34):
            kind, stage = ('normal', 0) if var < 4 else ('power', var // 4)
            sim, samples, end = c.run_variant(rom, state, 0, var, FACINGS['left'], level=max(stage, 1), kind=kind, stage=stage)
            d = summarize(sim, samples, end)
            out.append(json.dumps(d, sort_keys=True))
        return out
    base = key(Ctx(ctx.type, 0))
    res['grades'] = {'rows_identical_to_grade0_in_variants_0_1_2_3_4_6_12_14_32_34': [g for g in range(1, 9) if key(Ctx(ctx.type, g)) == base]}


def sec_status(ctx, rom, state, res):
    """For every row of the type that carries a status word: 100 uncharged swings at a dummy 14 px in front, each with a random RNG state; how often the status
    bits of the row appear in the target's status word E190/E191 after the hit, and the hero fields E199/E1F7 seen during the swing."""
    import random
    out = {}
    for grade in range(9):
        c2 = Ctx(ctx.type, grade)
        n = got = 0
        fields = set()
        for i in range(100):
            sim = c2.make(rom, state, 0, level=8, mon=(-14, 0))
            h, m = sim.h, sim.m
            word = h.w(0x199)
            if not word:
                break
            random.seed(i)
            for k in range(0x3F1, 0x400):
                sim.c.wram[k] = random.randrange(256)
            sim.c.wram[0x3F0] = random.randrange(15)
            h.sb(0x10, 0x82); sim.frame(B); sim.pad = 0
            for f in range(60):
                sim.frame(0)
                fields.add((h.w(0x199), h.b(0x1F7)))
            n += 1
            got += (m.w(0x190) & word) == word
        if n:
            out[str(c2.row)] = {'status_word': word, 'trials': n, 'target_got_status': got, 'hero_fields_E199_E1F7_seen': sorted(fields)}
    res['status'] = out


def hit_run(ctx, rom, state, stage, mon, face=0x82, var=None, slot=0, nframes=400, mon2=None, level=8):
    sim = ctx.make(rom, state, slot, level=level, mon=mon)
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
    calls = [0]
    orig_step = sim.c.step
    def count_step():
        if (sim.c.PB << 16 | sim.c.PC) in (0xC04FED, 0x0004FED) and sim.c.X == 0x200 * 3:
            calls[0] += 1
        orig_step()
    sim.c.step = count_step
    rec = {'hits': [], 'hits2': [], 'hero_flag_set': None, 'rect_first': None, 'mon_pos': [], 'dmg_stage': [], 'anim_id': h.b(0x11), 'status_fields': set()}
    hp, hp2 = m.w(0x182), (m2.w(0x182) if m2 else None)
    x0, y0 = m.w(2), m.w(4)
    flag0 = h.b(0x5A)
    for f in range(1, nframes):
        sim.frame(0)
        rec['status_fields'].add((h.w(0x199), h.b(0x1F7)))
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
    rec['status_fields'] = sorted(rec['status_fields'])
    rec['hit_routine_calls_on_slot3'] = calls[0]
    rec['sounds'] = [[e[0], e[2], e[3], e[4]] for e in sim.events if e[1] == 'sound']
    return rec, sim


def sec_hits(ctx, rom, state, res):
    import random
    import validate_phys as VP
    out = {}
    for stage in range(0, 9):
        row = {}
        for dx in (-14, -30):
            rec, sim = hit_run(ctx, rom, state, stage, (dx, 0))
            row[str(dx)] = rec
        out[str(stage)] = row
    rec, sim = hit_run(ctx, rom, state, 8, (-20, 0), mon2=(-26, -4))
    out['two_targets_stage8'] = rec
    # a target on the far side and above/below the hero: reach of the attack in the four facings (hit or not, frame of the hit) for stages 0, 4, 8
    reach = {}
    for fname, face in FACINGS.items():
        fx = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[fname]
        for stage in (0, 4, 8):
            row = {}
            for d in (14, 30, 50, 80, 110):
                rec, sim = hit_run(ctx, rom, state, stage, (fx[0] * d, fx[1] * d), face=face, nframes=260)
                row[str(d)] = rec['hits'][0][0] if rec['hits'] else None
            reach['%s_stage%d' % (fname, stage)] = row
    out['hit_frame_by_distance_in_front_none_means_no_hit'] = reach
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
            hit, d = VP.rom_hit(env, 0, 3)
            vals.append(d if hit else -1)
        ok = [v for v in vals if v >= 0]
        a_ = env.obj(0).b(0x198)
        dmg[str(stage)] = {'base_atk_x_(2s+4)>>2': (a_ * (2 * stage + 4)) >> 2, 'hit_rate': len(ok) / len(vals), 'min': min(ok), 'mean': round(sum(ok) / len(ok), 1), 'max': max(ok)}
    out['damage_by_stage_300_random_rng_states_hero0_dummy_def0_ev0'] = dmg
    out['hero0_stats_during_damage_runs_atk_hit_crit_E1E6'] = [env.obj(0).b(0x198), env.obj(0).b(0x197), env.obj(0).b(0x196), env.obj(0).b(0x1E6)]
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
    kb = {}
    for maxhp in (600, 1000, 2000):
        for stage in (0, 4, 8):
            sim = ctx.make(rom, state, 0, level=8, mon=(-24, 0))
            h, m = sim.h, sim.m
            m.sw(0x184, maxhp); m.sw(0x182, maxhp)
            h.sb(0x10, 0x82)
            if stage:
                h.sb(0x19B, stage); sim.frame(0)
            else:
                sim.frame(B); sim.pad = 0
            x0, y0 = m.w(2), m.w(4)
            hit = dmg_ = e11 = None
            for f in range(1, 80):
                sim.frame(0)
                if hit is None and m.w(0x182) != maxhp:
                    hit = f; dmg_ = maxhp - m.w(0x182)
                if hit and e11 is None and m.b(0x11) >= 0x80:
                    e11 = m.b(0x11)
            kb['maxhp%d_stage%d' % (maxhp, stage)] = {'damage': dmg_, 'max_hp_quarter': maxhp // 4, 'hurt_code_E011': e11, 'displacement_after_80_frames': [m.w(2) - x0, m.w(4) - y0], 'target_facing_E010': m.b(0x10)}
    out['target_knockback_by_damage_vs_max_hp'] = kb
    sim, samples, end = ctx.run_variant(rom, state, 0, 4 * 8 + 2, 0x82, level=8, kind='power', stage=8)
    out['stage_byte_during_attack_stage8'] = sorted(set(s['stage'] for s in samples[:end]))
    # the nine rows of the type: stats after the equip routines (hero 0) and the status fields during a stage-8 hit
    rows = {}
    for grade in range(9):
        c2 = Ctx(ctx.type, grade)
        s2 = c2.make(rom, state, 0, level=8)
        h = s2.h
        rows[str(c2.row)] = {'atk': h.b(0x198), 'hit': h.b(0x197), 'crit': h.b(0x196), 'status_word': h.w(0x199), 'status_chance': h.b(0x1F7), 'E194': h.w(0x194), 'E1E8': h.b(0x1E8)}
    out['rows_of_type_hero0_after_equip_level8'] = rows
    res['hits'] = out


def vulnerable_frames(ctx, rom, state, var, kind, stage, face=0x82, slot=0):
    """For every frame f of the attack: put a dummy monster on the hero, give it a large weapon box for that single frame and see whether the
    hero's hit flag routine ($C1:D23F, ORA $E059,X) fires.  Returns (frames with a non-empty body box, frames where the hero can be hit)."""
    sim, samples, end = ctx.run_variant(rom, state, slot, var, face, level=max(stage, 1), kind=kind, stage=stage)
    ref = [bool(s['body'][2] and s['body'][3]) for s in samples[:end + 1]]
    res = []
    for f in range(end + 1):
        d, par = ctx.kind_for(rom, var, stage)
        sim = ctx.make(rom, state, slot, level=max(stage, 1), mon=(0, 0), f4_par=par)
        h, m, c = sim.h, sim.m, sim.c
        hits = [0]
        orig = c.step
        def st(orig=orig, hits=hits, sim=sim, c=c):
            if (c.PB << 16 | c.PC) in (0xC1D23F, 0x01D23F) and c.X == sim.base:
                hits[0] += 1
            orig()
        c.step = st
        sim.force_m = d
        h.sb(0x10, face)
        if kind == 'normal':
            sim.frame(B); sim.pad = 0
        else:
            h.sb(0x19B, stage); sim.frame(0)
        if h.b(0x11) != var:
            raise RuntimeError('chooser returned %d, wanted %d' % (h.b(0x11), var))
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


def sec_invuln(ctx, rom, state, res):
    out = {}
    for name, var, kind, stage in (('normal_var0', 0, 'normal', 0), ('normal_var1', 1, 'normal', 0), ('normal_var2', 2, 'normal', 0), ('power_stage8_cls2', 34, 'power', 8)):
        ref, hit = vulnerable_frames(ctx, rom, state, var, kind, stage)
        out[name] = {'frames_with_body_box': [i for i, x in enumerate(ref) if x], 'frames_hero_hittable': [i for i, x in enumerate(hit) if x]}
        print('invuln', name, flush=True)
    res['invulnerability'] = out


SECTIONS = {'structure': sec_structure, 'variants': sec_variants, 'chooser': sec_chooser, 'gauge': sec_gauge, 'charge': sec_charge, 'power': sec_power,
            'spawn': sec_spawn, 'grades': sec_grades, 'status': sec_status, 'hits': sec_hits, 'invuln': sec_invuln}


def main():
    rom = romio.rom_from_argv()
    state, out_path, weapon = sys.argv[1], sys.argv[2], sys.argv[3]
    wanted = sys.argv[4:] or list(SECTIONS)
    wtype = TYPES[weapon] if weapon in TYPES else int(weapon)
    ctx = Ctx(wtype)
    res = {}
    if os.path.exists(out_path):
        res = json.load(open(out_path))
    res['source'] = 'tools/weapon_attacks.py: frame-exact runs of the real main routine $C0:B08C on a save state (docs/weapons-melee.md)'
    res['weapon_type'] = wtype
    res['weapon_row_used'] = ctx.row
    res['clock'] = {'frame_hz': 60.0988, 'hero_step_frames': 5, 'hero_step_hz': 12.0198, 'hero_step_phase': G.HERO_TICK_PHASE}
    t = time.time()
    for name in wanted:
        SECTIONS[name](ctx, rom, state, res)
        ga.build_summary(res)
        with open(out_path, 'w') as fh:
            dump_json(res, fh)
            fh.write('\n')
        print(name, 'done after', round(time.time() - t), 's', flush=True)


if __name__ == '__main__':
    main()

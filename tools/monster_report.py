"""Measure an ordinary monster in the real game code and write its numbers to a JSON file (data/monster_<id>.json).
usage: monster_report.py ROM STATE ID OUT.json [--only sec,sec,...] [--update] [--rip-dir DIR] [--gfx-validation A.json,B.json]
  --update keeps the sections already in OUT.json and replaces only the ones that run now
Sections (each is one function below; all run the real per-frame routine $C0:B08C on the save state, see tools/ai_sim.py):
  record      stat record, object-table entry (decoded fields), drop row, script entry, opcodes used
  model       the AI model of tools/ai_vm.py against the real handlers (tools/monster_model.py)
  commands    every command the script can issue: frames until the actor is free again, displacement, per direction code (tools/ai_cmds.py)
  swing       command 02 (op E8): animation chosen by distance and facing, frames, displacement, box and sound timeline, projectiles
  reaction    hit reaction after a hit by the real hit routine for a range of damage values: animation, knockback, stun, AI resume
  death       what happens at HP 0: frames, sounds, EXP and gold paid
  spawn       first seconds after the spawner ran
  ripped      per-animation summary read from the output of tools/rip_monster_anims.py (--rip-dir)
The STATE is the map-246 arena state of docs/rom-combat.md section 19 (the heroes are late-game; hero 1 and 2 are made inactive, hero 0 is pinned)."""
import sys, os, json, collections, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_sim, ai_cmds, aidis, monster_model, names

FPS = 60.0988


def u16(rom, o): return rom[o] | rom[o + 1] << 8


def entry_fields(rom, mid):
    e = rom[0x100000 + 16 * mid: 0x100000 + 16 * mid + 16]
    w = lambda i: e[i] | e[i + 1] << 8
    return dict(tile_offset_units=w(0) & 0x3FF, tile_offset_bytes=(w(0) & 0x3FF) << 6, tile_bank='$%02X' % (0xD5 + ((e[1] >> 2) & 7)), piece_list_offset=w(2),
                body_height=e[4] & 0x7F, entry_byte4_bit7=e[4] >> 7, ordinary_script_table='$D1:%04X' % w(5), attack_script_table='$D1:%04X' % w(7),
                ai_script_entry=w(9), shadow_table_a='$D1:%04X' % w(11), shadow_table_b='$D1:%04X' % w(13), flags_byte=e[15], palette_source='$C8:%04X' % (0x1000 + 30 * mid))


def static_commands(rom, entry):
    out = collections.Counter()
    for p in monster_model.static_reach(rom, entry):
        op = rom[aidis.BASE + p]
        ln, t, tg, ft = aidis.decode(rom, p)
        if op in (0xE0, 0xE2, 0xE3, 0xE4, 0xFD, 0xE6, 0xFE, 0xBE, 0xBF, 0xE8):
            out[(op,) + tuple(rom[aidis.BASE + p + 1:aidis.BASE + p + ln])] += 1
    return out


def sec_record(rom, mid, state=None):
    mon = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'monsters.json')))['records'][mid]
    drop = [r for r in json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'drops.json')))['rows'] if r['monster_id'] == mid]
    entry = u16(rom, 0x100000 + 16 * mid + 9)
    reach = monster_model.static_reach(rom, entry)
    ops = sorted({rom[aidis.BASE + p] for p in reach})
    rabite = set(json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'ai_scripts.json')))['entries'][0]['ops'])
    live = None
    if state:
        sm = ai_sim.Sim(rom, state, mid, (20, 25)); o = sm.o
        live = {name: o.b(off) for name, off in (('level_0based', 0x181), ('str', 0x188), ('agi', 0x189), ('con', 0x18A), ('int', 0x18B), ('wis', 0x18C), ('type', 0x192), ('element', 0x193), ('crit_base', 0x196),
                                                  ('accuracy', 0x197), ('attack', 0x198), ('evade', 0x1A4), ('flags_1FB', 0x1FB), ('facing', 0x10), ('weapon_level_nibbles', 0x1C0))}
        live.update(hp=o.w(0x182), max_hp=o.w(0x184), mp=o.b(0x186), defense=o.w(0x1A5), status_word_inflicted=o.w(0x199), status_chance=o.b(0x1F7), magic_evade=o.b(0x1A7), magic_defense=o.w(0x1A8),
                    immunity=o.w(0x1AA), exp=o.w(0x18D) | o.b(0x18F) << 16, gold=o.w(0x1C8), spell_power=(o.b(0x1FD), o.b(0x1FE)), body_height=o.b(0x74) & 0x7F, byte_74_bit7=o.b(0x74) >> 7)
    wr = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'weapons.json')))['rows']
    return dict(monster_record=mon, live_object_after_spawn=live, attack_rows=[wr[mon['weapon_a']], wr[mon['weapon_b']]], drop=drop[0] if drop else None, object_table_entry=entry_fields(rom, mid), name_block_index=0xCF + mid,
                script=dict(entry_pc=entry, instructions=len(reach), opcodes=ops, opcodes_not_in_rabite_script=sorted(set(ops) - rabite)),
                scripted_commands=[dict(op='%02X' % k[0], args=list(k[1:]), count=v) for k, v in sorted(static_commands(rom, entry).items())])


def sec_cadence(rom, state, mid):
    """AI step frames modulo 5 for the monster in slots 3, 4 and 5 (the AI step runs when the main-loop counter $56 equals slot - 3)."""
    out = {}
    for slot in (3, 4, 5):
        s = ai_sim.Sim(rom, state, mid, (20, 25), slot=slot, hero=(-60, 0), seed=1)
        for _ in range(int(6 * FPS)): s.frame()
        out[str(slot)] = dict(steps=len(s.steps), frames_mod_5=sorted({f % 5 for f, ops, cmd in s.steps}), first_steps=[f for f, ops, cmd in s.steps[:8]])
    return out


def sec_model(rom, state, mid, n=9000):
    done, bad, first, visited = monster_model.compare(rom, state, mid, n)
    entry = u16(rom, 0x100000 + 16 * mid + 9)
    reach = monster_model.static_reach(rom, entry)
    return dict(ai_steps_compared=done, mismatches=bad, instructions_reached_by_model=len(visited & reach), instructions_reachable=len(reach),
                not_reached=sorted('%04X' % p for p in reach - visited))


# ---------------------------------------------------------------------------------------------------------------- helpers

def sbox(v): return v - 256 if v > 127 else v


def box(o, a): return [sbox(o.b(a)), sbox(o.b(a + 1)), o.b(a + 2), o.b(a + 3)]


def runs(seq):
    """run-length encoding of a list: [[first_index, last_index, value], ...]"""
    out = []
    for i, v in enumerate(seq):
        if out and out[-1][2] == v: out[-1][1] = i
        else: out.append([i, i, v])
    return out


class Cmd:
    """Issue commands to the monster (one per AI step, instead of its script) and record every frame from the issue of the last one until the actor is free."""
    def __init__(self, rom, state, mid, cmds, hero=None, hp=None, tile=(20, 25), seed=None, hero_ai=False, setup=None):
        self.s = s = ai_sim.Sim(rom, state, mid, tile, seed=seed, hero=hero, hero_ai=hero_ai)
        self.o, self.c, self.h = s.o, s.c, s.obj(0)
        if hp: self.o.sw(0x182, hp); self.o.sw(0x184, hp)
        self.q = list(cmds); self.n = len(cmds); self.ev = []; self.rows = []
        if setup: setup(self)
        o, c = self.o, self.c
        def ai(cp):
            if cp.X < 0x600:
                cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
            if self.q:
                cm = self.q.pop(0)
                for i, v in enumerate(cm): c.wram[o.base + 0x140 + i] = v
                if cm[0] == 2: o.sb(0x19B, o.b(0x1C0)); o.sb(0x1AC, 0)
                self.ev.append(('issue', s.f))
            else:
                c.wram[o.base + 0x140] = 0; self.ev.append(('free', s.f))
            cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
        c.hooks[0xC12552] = ai

    def proj_entries(self):
        c = self.c; base = 0xD000 + 0x40 * ((self.o.base - 0xE000) >> 9)
        return [dict(slot=k, bytes=bytes(c.wram[base + 16 * k: base + 16 * k + 16])) for k in range(3) if c.wram[base + 16 * k]]

    def run(self, maxf=500, after=0, stop_proj=True):
        s, o, h = self.s, self.o, self.h
        t0 = None; x0 = y0 = None; endf = None
        for f in range(maxf):
            s.frame()
            if len(self.ev) >= self.n and self.ev[self.n - 1][0] == 'issue':
                if t0 is None: t0 = self.ev[self.n - 1][1]; x0, y0 = o.w(2), o.w(4)
                row = dict(t=s.f - 1 - t0, pos=(o.w(2) - x0, o.w(4) - y0), face=o.b(0x10), anim=o.b(0x11), st=o.b(0x1C), scr=o.w(0x16), idx=o.w(0x26) // 2, ht=o.b(0x45),
                           wb=box(o, 0xC0), bb=box(o, 0xC8), b3=box(o, 0xCC), proj=self.proj_entries(), hero_hp=h.w(0x182), hero_flag=h.b(0x59), hero_st=h.b(0x1C), hero_anim=h.b(0x11),
                           gauge=o.b(0x1ED), abs=(o.w(2), o.w(4)), hero_scr=(h.w(0x20), h.w(0x22), h.b(0x74) & 0x7F, h.b(0x45), h.b(0xCA), h.b(0xCB)), hero_abs=(h.w(2), h.w(4)), hero_bb=box(h, 0xC8),
                           cam=(self.c.wram[0xA8] | self.c.wram[0xA9] << 8, self.c.wram[0xAA] | self.c.wram[0xAB] << 8))
                self.rows.append(row)
            if len(self.ev) > self.n and endf is None: endf = self.ev[self.n][1] - t0 + 1
            if endf is not None and (not stop_proj or not any(r['proj'] for r in self.rows[-1:])) and len(self.rows) >= endf + after: break
        self.t0 = t0
        self.free_at = (self.ev[self.n][1] - t0) if len(self.ev) > self.n else None       # frames until the actor is free (the frame of the AI step that found it free)
        return self.rows

    def sounds(self):
        return [dict(frame=f - self.t0, id=b, param=c_, pan=d) for f, a, b, c_, d in self.s.sounds if a == 2 and f >= self.t0]


def hits_of(rows):
    return [r['t'] for r in rows if r['hero_flag']]


def sec_commands(rom, state, mid):
    entry = u16(rom, 0x100000 + 16 * mid + 9)
    cases = {}
    for k in static_commands(rom, entry):
        op = k[0]
        if op == 0xE0: cases[(k[1], k[2], k[3])] = 1
        elif op == 0xE3:
            for d in (1, 2, 4, 8): cases[(d, k[1], k[2])] = 1
        elif op in (0xE4, 0xE6): 
            for d in (1, 2, 4, 8, 5, 6, 9, 10): cases[(d, k[1], k[2])] = 1
        elif op in (0xFD, 0xFE):
            for d in (5, 6, 9, 10): cases[(d, k[1], k[2])] = 1
        elif op in (0xBE, 0xBF):
            for d in (1, 2, 4, 8): cases[(d, k[1], k[2])] = 1
    out = []
    for (d, a, f) in sorted(cases, key=lambda x: (x[1], x[2], x[0])):
        r = ai_cmds.measure(rom, state, mid, [(0xC1, d, a, f)])
        out.append(r)
    poses = sorted({k[1] for k in static_commands(rom, entry) if k[0] == 0xE2})
    for a in poses: out.append(ai_cmds.measure(rom, state, mid, [(0x40, a, 0, 0)]))
    return dict(cases=out, source='ai_cmds.measure: one command issued at the first AI step after the spawn; flag byte = requested frames (0 = natural length of the animation)')


def timeline(c):
    """Compact description of a recorded command: duration, displacement, boxes, sounds, projectile entries."""
    rows = c.rows
    n = c.free_at or len(rows)
    r0 = rows[:n]
    out = dict(frames=n, seconds=round(n / FPS, 4), anim_ids=sorted({r['anim'] for r in r0}), states=sorted({r['st'] for r in r0}),
               displacement=[r0[-1]['pos'][0], r0[-1]['pos'][1]] if r0 else None,
               path=[[a, b, v] for a, b, v in runs([tuple(r['pos']) for r in r0])],
               height=[[a, b, v] for a, b, v in runs([r['ht'] for r in r0])],
               weapon_box=[[a, b, v] for a, b, v in runs([tuple(r['wb']) for r in r0]) if v[2] and v[3]],
               body_box=[[a, b, v] for a, b, v in runs([tuple(r['bb']) for r in r0])],
               third_box=[[a, b, v] for a, b, v in runs([tuple(r['b3']) for r in r0]) if v[2] and v[3]],
               script_steps=[[a, b, '%04X' % v[0], v[1]] for a, b, v in runs([(r['scr'], r['idx']) for r in r0])],
               sounds=c.sounds())
    return out


def projectile_flights(c):
    """Per entry of the projectile table of the monster: first frame alive, per-frame world position, kind byte, facing, dying counter."""
    rows = c.rows; flights = {}
    for r in rows:
        for e in r['proj']:
            b = e['bytes']; k = e['slot']
            fl = flights.setdefault(k, dict(first=r['t'], last=r['t'], kind=b[0], facing=b[1], frames=[]))
            fl['last'] = r['t']
            fl['frames'].append([r['t'], b[2] | b[3] << 8, b[4] | b[5] << 8, b[6], b[7], b[10]])
    return flights


def sec_swing(rom, state, mid):
    out = dict(by_distance=[], timelines=[])
    for face, vec in ((1, (1, 0)), (2, (-1, 0)), (4, (0, 1)), (8, (0, -1))):
        for d in range(10, 100, 2):
            c = Cmd(rom, state, mid, [(0xC1, face, 0, 0), (2, face, 0, 0)], hero=(vec[0] * d, vec[1] * d))
            c.run(maxf=300, stop_proj=False)
            r = c.rows
            out['by_distance'].append(dict(facing=face, distance=d, animation=r[0]['anim'] if r else None, frames=c.free_at, dx=r[c.free_at - 1]['pos'][0] if c.free_at else None, dy=r[c.free_at - 1]['pos'][1] if c.free_at else None))
    anims = sorted({r['animation'] for r in out['by_distance']})
    for face, vec in ((1, (1, 0)), (2, (-1, 0)), (4, (0, 1)), (8, (0, -1))):
        for d in sorted({min(r['distance'] for r in out['by_distance'] if r['animation'] == a and r['facing'] == face) + 4 for a in anims}):
            for aside in (False, True):
                hero = (vec[0] * d, vec[1] * d) if not aside else (vec[1] * 100 + vec[0] * d, vec[0] * 100 + vec[1] * d)      # hero beside the line of the swing: not touched
                if aside: hero = (vec[0] * d + (0 if vec[0] else 100), vec[1] * d + (0 if vec[1] else 100))
                c = Cmd(rom, state, mid, [(0xC1, face, 0, 0), (2, face, 0, 0)], hero=hero)
                c.run(maxf=400, after=40)
                tl = timeline(c); tl.update(facing=face, hero_distance=d, hero_in_line=not aside, projectiles=projectile_flights(c) and {str(k): dict(first=v['first'], last=v['last'], kind=v['kind'] & 7, path=[[f[0], f[1] - c.rows[0]['abs'][0], f[2] - c.rows[0]['abs'][1]] for f in v['frames']]) for k, v in projectile_flights(c).items()},
                                            hero_hp_before=c.rows[0]['hero_hp'], hero_hp_after=c.rows[-1]['hero_hp'], hero_hit_frames=[r['t'] for r in c.rows if r['hero_st'] == 0x40][:1])
                out['timelines'].append(tl)
    return out


def arrow_model(rows, wp=16):
    """Hit rule of the projectile engine ($C2:C5B4, docs/weapons-ranged.md section 7.1) applied to the recorded frames: in frame i the entry (live, position and hero fields of
    the end of frame i-1, i.e. the state at the start of frame i) hits the hero when 2|tx - px| < wp + tw and 2|ty - py| < wp + th (also both differences < 96)."""
    for i in range(1, len(rows)):
        r, q = rows[i], rows[i - 1]
        for e in q['proj']:
            b = e['bytes']
            if b[0] & 7 == 0 or b[0] >> 3 or b[7]: continue                  # free, still delayed, or dying
            px, py = (b[2] | b[3] << 8) - q['cam'][0], (b[4] | b[5] << 8) - q['cam'][1]
            tx = q['hero_scr'][0]; ty = q['hero_scr'][1] - q['hero_scr'][2] - q['hero_scr'][3] - 1
            tw, th = q['hero_scr'][4], q['hero_scr'][5]
            if tw == 0 or th == 0: continue
            if 2 * abs(tx - px) < wp + tw and 2 * abs(ty - py) < wp + th and abs(tx - px) < 96 and abs(ty - py) < 96: return r['t']
    return None


def sec_arrow(rom, state, mid, n=60, seed=7):
    """Flight of the arrow without a target, hit test model against random hero placements, damage dealt to a hero with evade 0 and defense 0."""
    import random
    rnd = random.Random(seed)
    def setup(c):
        c.h.sb(0x1A4, 0); c.h.sw(0x1A5, 0)
    out = dict(flights=[], validation=[], damage=[])
    for face, vec in ((1, (1, 0)), (2, (-1, 0)), (4, (0, 1)), (8, (0, -1))):
        c = Cmd(rom, state, mid, [(0xC1, face, 0, 0), (2, face, 0, 0)], hero=(vec[0] * 120, vec[1] * 100 if vec[1] else 70), setup=setup)
        c.run(maxf=300, after=40)
        fl = projectile_flights(c)
        for k, v in fl.items():
            ent = c.rows[v['first']]['proj']
            out['flights'].append(dict(facing=face, entry=k, kind=v['kind'] & 7, first_frame=v['first'], last_frame=v['last'], facing_byte=v['facing'], launch_offset=[v['frames'][0][1] - c.rows[0]['abs'][0], v['frames'][0][2] - c.rows[0]['abs'][1]],
                                       height_byte=[f[3] for f in v['frames']], dying=[f[4] for f in v['frames']], speed_byte=v['frames'][0][5],
                                       path=[[f[0], f[1] - c.rows[0]['abs'][0], f[2] - c.rows[0]['abs'][1]] for f in v['frames']]))
        ok = bad = hits = 0; mism = []
        for _ in range(n):
            dx = rnd.randint(-30, 120); dy = rnd.randint(-40, 40)
            off = {1: (dx, dy), 2: (-dx, dy), 4: (dy, dx), 8: (dy, -dx)}[face]
            c = Cmd(rom, state, mid, [(0xC1, face, 0, 0), (2, face, 0, 0)], hero=off, setup=setup)
            c.run(maxf=300, after=30)
            hp0 = c.rows[0]['hero_hp']
            flag = [r['t'] for r in c.rows if r['hero_flag']]
            dmg = hp0 - c.rows[-1]['hero_hp']
            pred = arrow_model(c.rows)
            observed = bool(flag or dmg)
            hits += observed
            if observed == (pred is not None): ok += 1
            else: bad += 1; mism.append(dict(offset=off, observed=observed, predicted_frame=pred))
            if dmg: out['damage'].append(dmg)
        out['validation'].append(dict(facing=face, placements=n, hit=hits, agree=ok, disagree=bad, disagreements=mism[:6]))
    return out


def hit_trial(rom, state, mid, atk, face=None, hero=(100, 0), seed=5, secs=7.0, hit_at=40):
    """One hit by hero 0 through the real hit resolver $C0:4F7B (hero Str-independent: attack byte `atk`, accuracy 99, no E1E6 bonus, monster evade 0), then
    the real frame loop with the monster's own AI running. Returns what the monster did."""
    s = ai_sim.Sim(rom, state, mid, (20, 25), hero=hero, seed=seed)
    env, c, o, h = s.env, s.c, s.o, s.obj(0)
    for _ in range(hit_at): s.frame()
    if face is not None: o.sb(0x10, face)
    h.sb(0x1E6, 0); h.sb(0x198, atk); h.sb(0x197, 99); h.sb(0x19B, 0); h.sb(0x1F7, 0); h.sw(0x199, 0)
    o.sb(0x1A4, 0)
    c.wram[0x385] = (o.base - 0xE000) & 0xFF; c.wram[0x386] = (o.base - 0xE000) >> 8
    o.sb(0x59, 1)
    hp0, maxhp = o.w(0x182), o.w(0x184)
    pos0 = (o.w(2), o.w(4)); face0 = o.b(0x10)
    n_ai0 = len(s.steps)
    d0 = c.D
    env.call(0xC04F7B, X=o.base - 0xE000, Y=0, m=1, x=0, D=0x300, long=True)
    c.D = d0
    f0 = s.f
    rows = []; prev = None
    for i in range(int(secs * FPS)):
        s.frame()
        row = (o.w(2) - pos0[0], o.w(4) - pos0[1], o.b(0x10), o.b(0x11), o.b(0x1C), o.b(0x60), o.w(0x182), o.w(0x190) & 3, o.b(0x1B4))
        rows.append(row)
    hp1 = rows[-1][6]
    reaction = [r for r in rows if r[3] in (0x88, 0x89)]
    anim = reaction[0][3] if reaction else None
    hurt_frames = [i for i, r in enumerate(rows) if r[4] == 0x40 and r[3] in (0x88, 0x89)]
    first_e1b4 = next((r[8] for r in rows if r[8]), 0)
    nxt = next(((f, ops, cmd) for f, ops, cmd in s.steps if f > f0), None)
    resume = (nxt[0] - f0) if nxt else None
    end = resume if resume is not None else len(rows)
    move = [(i, r[0], r[1]) for i, r in enumerate(rows[:end]) if (r[0], r[1]) != (0, 0)]
    kn = None
    if move:
        kn = dict(first_frame=move[0][0], last_frame=move[-1][0], dx=rows[end - 1][0], dy=rows[end - 1][1],
                  path=[[a_, b_, list(v)] for a_, b_, v in runs([(r[0], r[1]) for r in rows[:end]])])
    return dict(atk=atk, hp_before=hp0, max_hp=maxhp, damage=hp0 - rows[min(len(rows) - 1, 20)][6], face_before=face0, reaction_anim=anim, stun_counter=first_e1b4,
                status_bits=sorted({r[7] for r in rows} - {0}), hurt_first=hurt_frames[0] if hurt_frames else None, hurt_last=hurt_frames[-1] if hurt_frames else None,
                ai_resume_frame=resume, ai_resume_command=list(nxt[2]) if nxt else None, ai_resume_pc='%04X' % nxt[1][-1][0] if nxt else None, knockback=kn, sounds=[dict(frame=f - f0, id=b, param=c_, pan=d) for f, a, b, c_, d in s.sounds if f >= f0 and a == 2])


def sec_reaction(rom, state, mid):
    mon = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'monsters.json')))['records'][mid]
    hp = mon['hp']
    atks = sorted({2, 5, 8, 12, hp // 4 - 4, hp // 4 - 1, hp // 4 + 2, hp // 4 + 6, hp // 2, hp - 20, hp - 6} - {0})
    out = dict(by_damage=[], by_facing=[], rule='see docs: reaction code 8 (anim 0x88) when damage <= max HP / 4, else 9 (anim 0x89); stun counter obj+0x1B4 = max(6, damage >> 3) combat ticks')
    for a in atks: out['by_damage'].append(hit_trial(rom, state, mid, a))
    big = max(hp // 4 + 6, 20)
    for face in (0, 1, 2, 0x82):
        for hero in ((-100, 0), (-60, -40), (-40, 40), (-120, 20)):          # four places of the arena: a wall or an object in the way shortens the push, so the largest value is the open-ground one
            out['by_facing'].append(dict(facing_byte=face, hero_offset=list(hero), **hit_trial(rom, state, mid, big, face=face, hero=hero, secs=3)))
    return out


def sec_death(rom, state, mid):
    """A lethal hit through the real resolver; the monster object is followed frame by frame; EXP (hero 0) and gold are read before and after; sounds listed."""
    out = []
    for seed in (5, 9):
        s = ai_sim.Sim(rom, state, mid, (20, 25), hero=(100, 0), seed=seed)
        env, c, o, h = s.env, s.c, s.o, s.obj(0)
        for _ in range(40): s.frame()
        h.sb(0x1E6, 0); h.sb(0x198, 250); h.sb(0x197, 99); o.sb(0x1A4, 0)
        c.wram[0x385] = (o.base - 0xE000) & 0xFF; c.wram[0x386] = (o.base - 0xE000) >> 8; o.sb(0x59, 1)
        exp0 = h.w(0x18D) | h.b(0x18F) << 16; gold0 = c.wram[0xCC6A] | c.wram[0xCC6B] << 8 | c.wram[0xCC6C] << 16
        d0 = c.D; env.call(0xC04F7B, X=o.base - 0xE000, Y=0, m=1, x=0, D=0x300, long=True); c.D = d0
        f0 = s.f; rows = []
        for i in range(260):
            s.frame()
            rows.append((o.b(0), o.b(0x1C), o.b(0x60), o.b(0x11), o.b(0x180), o.w(0x182), o.w(0x190), o.b(0x1B1), o.w(0x184), o.b(0x1C8)))
        out.append(dict(seed=seed, exp_paid=(h.w(0x18D) | h.b(0x18F) << 16) - exp0, gold_paid=(c.wram[0xCC6A] | c.wram[0xCC6B] << 8 | c.wram[0xCC6C] << 16) - gold0,
                        object_id_byte_after=rows[0][4], status_after=rows[0][6],
                        phases=[[a, b, dict(active=v[0], state=v[1], overlay_state_60=v[2], anim=v[3], id_byte_180=v[4], hp=v[5], chest_flag_1B1=v[6], max_hp=v[7])] for a, b, v in runs([(r[0], r[1], r[2], r[3], r[4], r[5], r[7], r[8]) for r in rows])],
                        sounds=[dict(frame=f - f0, id=b, param=c_, pan=d) for f, a, b, c_, d in s.sounds if f >= f0 and a == 2]))
    return out


def sec_drops(rom, state, mid, n=300):
    """The real death routine $C0:4203 on n random RNG states: how often the monster turns into a chest (object record: HP 0, +0x1B1 = 0x80) and its class; the real chest
    content routine $C8:E12C on n random RNG states."""
    import random
    from collections import Counter
    rnd = random.Random(21)
    chest = Counter(); cls = Counter(); cont = Counter()
    def rtl(cp):
        cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True
    import combat_env
    for k in range(n):
        env = combat_env.Env(rom, state); c = env.c
        for j in range(15): c.wram[0x3F1 + j] = rnd.randrange(256)
        c.wram[0x3F0] = rnd.randrange(15)
        env.call(0xC055EC, A=mid, X=0x600, m=1, x=0)
        m = env.obj(3); c.wram[0x385] = 0; c.wram[0x386] = 6; m.sb(0x1F0, 0); m.sb(0x1CF, 0)
        env.call(0xC04203, X=0x600, m=1, x=0, D=0x300, long=False)
        got = m.b(0x1B1) == 0x80 and m.b(0x184) == 0 and m.b(0x181) == 0
        chest[got] += 1
        if got: cls[m.b(0x1C8)] += 1
    for k in range(n):
        env = combat_env.Env(rom, state); c = env.c
        for j in range(15): c.wram[0x3F1 + j] = rnd.randrange(256)
        c.wram[0x3F0] = rnd.randrange(15)
        log = []
        for name, addr in (('item', 0xC06420), ('msg', 0xC058DB), ('msg2', 0xC058F1), ('gold', 0xC039CF), ('goldmsg', 0xC058C8)):
            c.hooks[addr] = (lambda nm: (lambda cp: (log.append((nm, cp.A & 0xFF)), rtl(cp))[1]))(name)
        for t in range(8): c.wram[0xCFB8 + t] = 0; c.wram[0xCFC0 + t] = 9
        c.wram[0x385] = 0; c.wram[0x386] = 6; c.wram[0xCF0F] = 0
        env.call(0xC8E12C, X=mid * 5, m=1, x=0, D=0x300, long=False)
        for nm, a in log:
            if nm in ('item', 'gold'): cont[(nm, a)] += 1
    return dict(death_routine_cases=n, chest=dict((str(k), v) for k, v in chest.items()), chest_class={str(k): v for k, v in sorted(cls.items())},
                chest_contents_cases=n, contents={'%s %d' % k: v for k, v in sorted(cont.items())}, note='orb counters set so that no orb drop is replaced; contents of the rows are in docs/rom-combat.md section 13')


def sec_trace(rom, state, mid, secs=14, scenarios=None):
    """The monster's own script running in the real frame loop with hero 0 pinned at an offset: every AI step merged into runs of identical commands."""
    # hero offset = hero position - monster position is NOT what the harness takes: the monster is moved to (hero position - offset), so a negative x puts the monster to the right
    # of hero 0 on screen; positive offsets of 120 or more put it off the left edge of the screen (screen x wraps, distance class forced to 'within 64')
    scen = scenarios or [(-100, 0), (-60, 0), (-40, 0), (-24, 0), (-60, 30), (-12, 0), (0, 70), (0, -50), (0, 0, 'disabled')]
    out = []
    for hero in scen:
        off = hero[:2]; disabled = len(hero) > 2
        s = ai_sim.Sim(rom, state, mid, (20, 25), hero=off, seed=1)
        o = s.o
        if disabled: s.obj(0).sw(0x190, 0x0020)           # no valid hero anywhere: the script runs its wander routine
        for _ in range(int(secs * FPS)): s.frame()
        steps = [(f, cmd) for f, ops, cmd in s.steps]
        seq = []
        for i, (f, cmd) in enumerate(steps):
            nxt = steps[i + 1][0] if i + 1 < len(steps) else s.f
            if seq and seq[-1]['cmd'] == list(cmd) and seq[-1]['t_end'] == f: seq[-1]['t_end'] = nxt; seq[-1]['steps'] += 1
            else: seq.append(dict(t_start=f, t_end=nxt, steps=1, cmd=list(cmd)))
        for e in seq: e['frames'] = e['t_end'] - e['t_start']
        out.append(dict(hero_offset=list(off), hero_disabled=disabled, seconds=secs, commands=seq, sounds=[dict(frame=f, id=b) for f, a, b, c_, d in s.sounds if a == 2][:60]))
    return out


def sec_ripped(rip_dir, mid):
    """Summary of the pictures written by tools/rip_monster_anims.py: one row per animation set and facing (frames, seconds, number of distinct pictures, picture size)."""
    import glob
    d = os.path.join(rip_dir, str(mid))
    idx = json.load(open(os.path.join(d, 'index.json')))
    rows = {}
    for jp in sorted(glob.glob(os.path.join(d, '*.json'))):
        if os.path.basename(jp) == 'index.json': continue
        j = json.load(open(jp)); nm = os.path.basename(jp)[:-5]
        rows[nm] = dict(anim_id=j['anim_id'] if 'anim_id' in j else None, state_byte=j.get('state_byte'), table=j.get('animation_table'), frames=j['total_frames'], seconds=j['total_seconds'],
                        pictures=len(j['frames']), png=j['png_size'], origin=j['origin'], script_pointers=j.get('script_pointers'))
    out = dict(index={k: v for k, v in idx.items() if k != 'animations'}, animations=rows)
    return out


def box_model(rows):
    """First frame in which the monster's weapon box overlaps the hero's body box (docs/glove-attacks.md section 2.5: |cx1 - cx2| < (w1 + w2) / 2 and |cy1 - cy2| < (h1 + h2) / 2,
    centres = object position + offset; the boxes of frame i - 1 are tested in frame i)."""
    for i in range(1, len(rows)):
        q = rows[i - 1]
        wx, wy, ww, wh = q['wb']; bx, by, bw, bh = q['hero_bb']
        if not (ww and wh and bw and bh): continue
        mx, my = q['abs']; hx, hy = q['hero_abs']
        if 2 * abs((mx + wx) - (hx + bx)) < ww + bw and 2 * abs((my + wy) - (hy + by)) < wh + bh: return rows[i]['t']
    return None


def sec_contact(rom, state, mid, n=50, seed=3):
    """Weapon box of the swing against random hero placements (hero evade 0, defense 0): does the hero get hit and how much damage; model = box_model."""
    import random
    rnd = random.Random(seed)
    def setup(c):
        c.h.sb(0x1A4, 0); c.h.sw(0x1A5, 0)
    out = []; dmg = []
    for face in (1, 2, 4, 8):
        agree = disagree = hits = 0; mism = []
        for _ in range(n):
            dx = rnd.randint(-20, 75); dy = rnd.randint(-30, 30)
            off = {1: (dx, dy), 2: (-dx, dy), 4: (dy, dx), 8: (dy, -dx)}[face]
            c = Cmd(rom, state, mid, [(0xC1, face, 0, 0), (2, face, 0, 0)], hero=off, setup=setup)
            c.run(maxf=400, after=20)
            hp0 = c.rows[0]['hero_hp']; d = hp0 - c.rows[-1]['hero_hp']
            flag = [r['t'] for r in c.rows if r['hero_flag']]
            obs = bool(d or flag); hits += obs
            pred = box_model(c.rows)
            if obs == (pred is not None): agree += 1
            else: disagree += 1; mism.append(dict(offset=off, observed=obs, predicted_frame=pred))
            if d: dmg.append(d)
        out.append(dict(facing=face, placements=n, hit=hits, agree=agree, disagree=disagree, disagreements=mism[:6]))
    return dict(validation=out, damage_counts={str(k): v for k, v in sorted(collections.Counter(dmg).items())})


def sec_sleep(rom, state, mid):
    """Polter Chair only: the watch loop at the start of the script (pc 0x0B6D). Hero 0 at distance d (monster to the right of the hero, horizontal): does the script leave the
    loop (the pose command 0x40 at pc 0x0B81 is issued) within 4 s; and the reaction to 1 point of damage."""
    out = dict(by_distance=[], by_damage=[])
    for d in (10, 14, 16, 17, 18, 24, 40, 80):
        s = ai_sim.Sim(rom, state, mid, (20, 25), hero=(-d, 0), seed=1)
        for _ in range(int(4 * FPS)): s.frame()
        wake = next((f for f, ops, cmd in s.steps if ops[-1][0] == 0x0B81), None)
        out['by_distance'].append(dict(distance=d, woke_at_frame=wake, first_commands=[list(cmd) for f, ops, cmd in s.steps[:4]]))
    for atk in (1, 2):
        r = hit_trial(rom, state, mid, atk, hero=(-100, 0), secs=3)
        s = ai_sim.Sim(rom, state, mid, (20, 25), hero=(-100, 0), seed=5)
        out['by_damage'].append(dict(attack_byte=atk, damage=r['damage'], hp_before=r['hp_before'], reaction_anim=r['reaction_anim'], ai_resume_frame=r['ai_resume_frame'], ai_resume_command=r['ai_resume_command'], ai_resume_pc=r['ai_resume_pc']))
    return out


def main():
    rom = romio.rom_from_argv(); state, out, mid = sys.argv[1], sys.argv[3], int(sys.argv[2], 0)
    args = sys.argv[4:]
    only = None
    if '--only' in args: only = args[args.index('--only') + 1].split(',')
    rep = None
    if '--update' in args and os.path.exists(out): rep = json.load(open(out))
    if rep is None: rep = dict(source='tools/monster_report.py: real per-frame routine $C0:B08C on a ZSNES v143 state, monster %d in slot 3 (see docs/monster-%d.md); frames are 60.0988 Hz video frames' % (mid, mid), monster_id=mid, fps=FPS)
    if not only or 'record' in only: rep.update(sec_record(rom, mid, state))
    if only and 'ripped' in only and '--rip-dir' in args: rep['ripped'] = sec_ripped(args[args.index('--rip-dir') + 1], mid)
    if '--gfx-validation' in args:
        rep['graphics_validation'] = [json.load(open(pth)) for pth in args[args.index('--gfx-validation') + 1].split(',')]
    if not only or 'model' in only: rep['ai_model_check'] = sec_model(rom, state, mid)
    if not only or 'cadence' in only: rep['cadence'] = sec_cadence(rom, state, mid)
    if not only or 'commands' in only: rep['commands'] = sec_commands(rom, state, mid)
    if not only or 'swing' in only: rep['swing'] = sec_swing(rom, state, mid)
    if not only or 'reaction' in only: rep['reaction'] = sec_reaction(rom, state, mid)
    if not only or 'death' in only: rep['death'] = sec_death(rom, state, mid)
    if not only or 'drops' in only: rep['drops_check'] = sec_drops(rom, state, mid)
    if only and 'trace' in only: rep['trace'] = sec_trace(rom, state, mid)
    if only and 'sleep' in only: rep['sleep'] = sec_sleep(rom, state, mid)
    if only and 'contact' in only: rep['contact'] = sec_contact(rom, state, mid)
    if only and 'arrow' in only: rep['arrow'] = sec_arrow(rom, state, mid)
    json.dump(rep, open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()

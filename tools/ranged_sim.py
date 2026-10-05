"""Frame-exact simulation helpers for the whip (weapon type 4), bow (5), boomerang (6) and javelin (7), on top of tools/glove_sim.py.
library: Ctx(wtype, grade=0) -> .make(rom, state, slot, ...) builds a GloveSim with the weapon row equipped and the projectile table cleared;
         .run_attack(...) starts one attack the way the game does and follows it until the projectiles are gone.
The projectile engine (bank $C2, `$C2:BF1D` launcher, `$C2:C27F` per-frame step, `$C2:C3C1` draw, hit test `$C2:C54E-C62B`) keeps its entries in WRAM `$7E:D000 + 0x40 * hero + 0x10 * k`
(k = 0..2, 16 bytes each, see docs/weapons-ranged.md section 3.2). No ROM data is stored in the repository: every table is read from the ROM given on the command line."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glove_sim as G
import glove_attacks as ga

B = ga.B
FACINGS = ga.FACINGS
TYPE_NAMES = {4: 'whip', 5: 'bow', 6: 'boomerang', 7: 'javelin'}
TYPE_BY_NAME = {v: k for k, v in TYPE_NAMES.items()}
SCRIPT_BASE, SCRIPT_STRIDE = 0x3040, 240      # bank $D1: script pointer table of weapon type t at $3040 + 240 t, word [(anim * 3 + facing) * 2]
KIND_TABLE, ANIM_MAP = 0x0000, 0x0480          # bank $D1: chooser kinds (576 bytes) and the per-type map kind -> animation (40 bytes per type)
PROJ_BASE = 0xD000                             # WRAM bank $7E: projectile entries of hero h at PROJ_BASE + 0x40 h + 0x10 k; PROJ_BASE + 0x40 h + 0x30 = projectile kind of the equipped weapon
HZ = 60.0988


class Ctx:
    """Weapon under test: type, equipped row (grade 0 of the type unless given) and the helpers that depend on them."""
    def __init__(self, wtype, grade=0):
        self.type, self.row = wtype, wtype * 9 + grade

    def make(self, rom, state, slot, level=8, mon=None, press_phase=2, f4_par=0, idle=12, mon2=None, monhp=9999):
        """Sim whose NEXT frame is the press frame ($56 == press_phase there, parity of $F4 == f4_par); the projectile table is cleared."""
        sim = G.GloveSim(rom, state, slot, self.row, level, mon=mon, monhp=monhp)
        sim.force_m = None
        def e418(cp):
            if sim.force_m is not None:
                cp.A = (cp.A & 0xFF00) | sim.force_m
            return False
        sim.c.hooks[0x01E418] = sim.c.hooks[0xC1E418] = e418      # result of the distance-class routine $C1:E4CC, optionally overridden
        for hh in range(3):
            for i in range(0x30):
                sim.c.wram[PROJ_BASE + 0x40 * hh + i] = 0
        if mon2 is not None:
            first = sim.m
            sim.spawn(mon2, 0, monhp, slot=4)
            sim.m2, sim.m = sim.m, first        # sim.m stays the monster of slot 3, sim.m2 is the one of slot 4
        sim.phase0 = (press_phase - idle) % 5
        for _ in range(idle):
            sim.frame(0)
        sim.f4 = (f4_par - sim.f) & 0xFF
        sim.slot = slot
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

    def start(self, rom, state, slot, var, face, level=8, kind='normal', stage=0, press_phase=2, mon=None, mon2=None, monhp=9999, hold=None):
        """Sim after the start frame of animation `var` (a B press for a normal swing, the release of a charged button for a power attack).
        The distance class and the parity of $F4 are chosen so that the real chooser returns `var`."""
        d, par = self.kind_for(rom, var, stage)
        sim = self.make(rom, state, slot, level=level, press_phase=press_phase, f4_par=par, mon=mon, mon2=mon2, monhp=monhp)
        sim.force_m = d
        sim.h.sb(0x10, face)
        sim.events.clear()
        sim.pre_ptr = sim.sample()['ptr']
        if kind == 'normal':
            sim.frame(B)
        else:
            sim.h.sb(0x19B, stage)
            sim.frame(0)
        sim.pad = 0
        if sim.h.b(0x11) != var:
            raise RuntimeError('chooser returned %d, wanted %d' % (sim.h.b(0x11), var))
        return sim


def proj_entries(sim, slot=None):
    """The three 16-byte projectile entries of a hero as dicts (kind 0 = free)."""
    w = sim.c.wram
    slot = sim.slot if slot is None else slot
    out = []
    for k in range(3):
        b = bytes(w[PROJ_BASE + 0x40 * slot + 0x10 * k:PROJ_BASE + 0x40 * slot + 0x10 * k + 16])
        out.append(dict(kind=b[0], face=b[1], x=b[2] | b[3] << 8, y=b[4] | b[5] << 8, z=b[6], dying=b[7], f8=b[8], f9=b[9], fA=b[10], fB=b[11], fC=b[12], fD=b[13], attr=b[14] | b[15] << 8))
    return out


def sample(sim):
    """glove_sim sample plus the projectile state of the hero."""
    s = sim.sample()
    h = sim.h
    s['e061'] = h.b(0x61)
    s['e02e'] = h.b(0x2E)
    s['e05a'] = h.b(0x5A)
    s['proj'] = proj_entries(sim)
    return s


def follow(sim, samples=None, max_frames=900, until_free=True, extra=3):
    """Run frames after the start frame until the state byte is 0 and (until_free) the projectile flag E061 is 0 too; returns (samples, end_swing, end_all).
    samples[0] is the start (press / release) frame; end_swing = first frame with E01C == 0; end_all = first frame with E01C == 0 and E061 == 0
    (E061 is raised by the launcher `$C2:BF1D`, which also happens late in the swing; the check only counts after the swing ended)."""
    samples = [sample(sim)] if samples is None else samples
    end_swing = end_all = None
    for i in range(1, max_frames):
        sim.frame(0)
        samples.append(sample(sim))
        s = samples[-1]
        if end_swing is None and s['st'] == 0:
            end_swing = i
        if end_swing is not None and s['e061'] == 0:
            end_all = i
            break
    for _ in range(extra):
        sim.frame(0)
        samples.append(sample(sim))
    return samples, end_swing, end_all

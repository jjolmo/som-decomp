"""Python model of the enemy AI bytecode machine ($C1:2552 -> $C1:251A, handler table $C1:2257) for the ops used by the scripts of the Rabite (id 0),
the Chobin Hood (id 3) and the Polter Chair (id 0x0D). The model is written from the handler code and from the experiments of tools/ai_ops.py; it is
checked against the real handlers by tools/monster_model.py (command bytes, script pointer, call stack, variables, saved position, target and random
bytes consumed after every AI step, in randomised worlds).
library: VM(rom, entry).step(world, rng_bytes) -> command bytes written (list of up to 4 values, None where the op leaves the byte alone)
         Actor(x, y, h, active, status)    World(me, heroes, gauge, hp, level, facing)
Time and movement are not modelled: the world is whatever the caller sets before each step."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aidis

BASE = aidis.BASE


class Actor:
    def __init__(self, x=128, y=112, h=0, active=1, status=0):
        self.x, self.y, self.h, self.active, self.status = x, y, h, active, status

    @property
    def ey(self): return (self.y - self.h) & 0xFFFF            # $C1:032E / $0343: screen y minus jump height


class World:
    def __init__(self, me, heroes, gauge=0, hp=20, level=0, facing=2):
        self.me, self.heroes, self.gauge, self.hp, self.level, self.facing = me, heroes, gauge, hp, level, facing


def on_screen(a):
    """$C1:0526 (used through $C1:05A5 for the current target): active and on screen; the status word is not tested."""
    return a.active == 1 and a.x < 256 and a.ey < 224


def valid(a):
    """$C1:054A (target acquisition): active, on screen, status word has none of the bits 0x8460."""
    return on_screen(a) and (a.status & 0x8460) == 0


def dist_class(a, b):
    """$C1:0358: 1, 2, 4, 8, 0x10, 0x30 for distance <= 16, 32, 48, 64, 96, farther; 8 when a coordinate difference is 256 or more.
    The sum of squares is a 16-bit sum (carry dropped)."""
    dx = abs(a.x - b.x)
    if dx > 255: return 8
    dy = abs(a.ey - b.ey)
    if dy > 255: return 8
    s = (dx * dx + dy * dy) & 0xFFFF
    if s > 0x2400: return 0x30
    if s > 0x1000: return 0x10
    if s > 0x0900: return 8
    if s > 0x0400: return 4
    if s > 0x0100: return 2
    return 1


def primary_code(dx, dy):
    """$C1:0404 primary 8-way code from the offsets target - self (dy already minus height): 1 right, 2 left, 4 down, 8 up, 9 up-right, 10 up-left, 5 down-right, 6 down-left."""
    a, b = abs(dx), abs(dy)
    big, small = max(a, b), min(a, b)
    d = big - small
    t = (d >> 1) + ((d >> 1) >> 1)
    horiz = (1 if dx >= 0 else 2)
    vert = (4 if dy > 0 else 8)
    if t >= small:                       # axis only
        return horiz if a >= b else vert
    return horiz | vert


def alternate_code(dx, dy):
    return (1 if dx >= 0 else 2) | (8 if dy < 0 else 4)


def cardinal_code(dx, dy):
    return (1 if dx >= 0 else 2) if abs(dx) >= abs(dy) else (4 if dy > 0 else 8)


OPP = {1: 2, 2: 1, 4: 8, 8: 4}


class VMError(Exception):
    pass


class VM:
    def __init__(self, rom, entry):
        self.rom, self.entry = rom, entry
        self.pc, self.stack, self.var3, self.tgt = entry, [], 0, 0xFF
        self.saved = (0xFFFF, 0xFFFF)
        self.draws = 0
        self.visited = set()

    def b(self, pc): return self.rom[BASE + pc]

    def obj_byte(self, w, ref, off):
        o = off + 0x180
        if ref == 0x80: who = 'me'
        elif ref == 0x81: who = 'tgt'
        else: who = ('hero', ref)
        if o == 0x1AC and who == 'me': return self.tgt
        if o == 0x1ED and who == 'me': return w.gauge
        if o == 0x181 and who == 'tgt': return w.level
        if o == 0x182 and who == 'me': return w.hp & 0xFF
        raise VMError('object field %02X %02X not modelled' % (ref, off))

    def obj_word(self, w, ref, off):
        if ref == 0x80 and off + 0x180 == 0x182: return w.hp
        raise VMError('object word %02X %02X not modelled' % (ref, off))

    def rnd(self, rng, n):
        if n == 0: return 0
        while True:
            v = rng[self.draws] & 0x0F; self.draws += 1
            if v <= n: return v

    def band(self, w, thr):
        """first valid hero (slot order) whose distance class <= thr; None if none"""
        for i, h in enumerate(w.heroes):
            if valid(h) and dist_class(w.me, h) <= thr: return i
        return None

    def tgt_hero(self, w):
        if self.tgt == 0xFF or self.tgt >= len(w.heroes): return None
        h = w.heroes[self.tgt]
        return h if on_screen(h) else None

    def step(self, w, rng):
        """run ops until one yields; returns the command bytes written"""
        self.draws = 0
        cmd = [0, None, None, None]
        for _ in range(256):
            r = self.op(w, rng, cmd)
            if r is not None: return cmd, r
        raise VMError('256 ops without a yield')

    def jump_or_skip(self, ln, tgt, take):
        self.pc = tgt if take else self.pc + ln

    def op(self, w, rng, cmd):
        pc = self.pc; op = self.b(pc); self.visited.add(pc)
        ln, text, tgt, ft = aidis.decode(self.rom, pc)
        a = [self.b(pc + 1 + i) for i in range(6)]
        me = w.me
        def done(): self.pc = pc + ln
        # control flow
        if op == 0x00:
            if not self.stack: raise VMError('return at depth 0')
            self.pc = self.stack.pop(); return None
        if op == 0x01: self.pc = tgt; return None
        if op == 0xFF:
            if len(self.stack) >= 16: raise VMError('call depth')
            self.stack.append(pc + 3); self.pc = tgt; return None
        # variables
        if op == 0x05: self.jump_or_skip(ln, tgt, self.var3 != 0); return None
        if op == 0x09: self.jump_or_skip(ln, tgt, self.var3 == 0); return None
        if op == 0x0D: self.jump_or_skip(ln, tgt, self.var3 != a[0]); return None
        if op == 0x2C: self.var3 = self.rnd(rng, a[0]); done(); return None
        # compares on object fields
        if op == 0x2F: self.jump_or_skip(ln, tgt, self.obj_byte(w, a[0], a[1]) < a[2]); return None
        if op == 0x30: self.jump_or_skip(ln, tgt, self.obj_byte(w, a[0], a[1]) > a[2]); return None
        if op == 0xBD: self.jump_or_skip(ln, tgt, self.obj_word(w, a[0], a[1]) > (a[2] | a[3] << 8)); return None
        if op == 0xDC:
            if a[0] == 0x80 and a[1] == 0x6D: w.gauge = a[2]
            else: raise VMError('DC target not modelled')
            done(); return None
        # target classes
        thr = {0x31: 1, 0x49: 2, 0x4E: 4, 0x53: 8}
        if op in thr: self.jump_or_skip(ln, tgt, self.band(w, thr[op]) is None); return None
        if op == 0x58: self.jump_or_skip(ln, tgt, not any(valid(h) for h in w.heroes)); return None
        thr = {0x4C: 2, 0x51: 4, 0x56: 8}
        if op in thr:
            h = self.tgt_hero(w)
            self.jump_or_skip(ln, tgt, not (h is not None and dist_class(me, h) <= thr[op])); return None
        if op == 0x34:
            h = self.tgt_hero(w)
            self.jump_or_skip(ln, tgt, not (h is not None and dist_class(me, h) == 1)); return None
        if op in (0x6A, 0x73):
            h = self.tgt_hero(w)
            ok = False
            if h is not None:
                dx, dy = h.x - me.x, h.ey - me.ey
                ok = (abs(dx) <= 15 and abs(dx) < abs(dy)) if op == 0x6A else (abs(dy) <= 15 and abs(dy) <= abs(dx))
            self.jump_or_skip(ln, tgt, not ok); return None
        sel = {0xA5: 1, 0xB1: 2, 0xB4: 4, 0xB7: 8}
        if op in sel:
            i = self.band(w, sel[op]); self.tgt = 0xFF if i is None else i; done(); return None
        if op == 0x5D:
            self.tgt = 0xFF
            for i, h in enumerate(w.heroes):
                if valid(h) and dist_class(me, h) > 8: self.tgt = i; break
            done(); return None
        # position memory
        if op == 0x9F: self.saved = (me.x, me.ey); done(); return None
        if op == 0x9D: self.jump_or_skip(ln, tgt, self.saved == (me.x, me.ey)); return None
        # commands
        if op == 0xE0:
            cmd[:] = [0xC1, a[0], a[1], a[2]]; done(); return 0
        if op == 0xE2:
            cmd[0], cmd[1] = 0x40, a[0]; done(); return 0
        if op == 0xE3:
            face = {0: 8, 1: 4, 2: 1}.get(w.facing, 2)
            cmd[:] = [0xC1, face, a[0], a[1]]; done(); return 0
        if op in (0xE4, 0xFD, 0xE6, 0xFE, 0xBE, 0xBF):
            h = self.tgt_hero(w)
            done()
            if h is None: return None
            dx, dy = h.x - me.x, h.ey - me.ey
            if op == 0xE4: code = primary_code(dx, dy)
            elif op == 0xFD: code = alternate_code(dx, dy)
            elif op == 0xE6: code = primary_code(-dx, -dy)
            elif op == 0xFE: code = alternate_code(-dx, -dy)
            elif op == 0xBE: code = cardinal_code(dx, dy)
            else: code = OPP[cardinal_code(dx, dy)]
            if op in (0xE6, 0xFE, 0xBF):
                cmd[:] = [0xC1, code, a[0], a[1]]
            else:
                cmd[:] = [0xC1, code, a[0], a[1]]
            return 0
        if op == 0xE8:
            done()
            if w.gauge != 0: return None
            cmd[0] = 0x02; return 0
        raise VMError('op %02X not modelled' % op)

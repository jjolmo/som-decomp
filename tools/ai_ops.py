"""Run the real AI bytecode handlers ($C1:251A -> table $C1:2257) on synthetic scripts and print what each opcode does.
usage: ai_ops.py ROM STATE [--new]      (--new: only the opcodes added for docs/monster-3.md and docs/monster-13.md: 34, 6A, 73, BE, BF, DC)
Each case patches a few script bytes into an in-memory copy of the ROM (script base 0x104F15, never written to disk), builds a monster in slot 3
with the game's spawner, runs one handler and prints: return value (FF = continue with the next op, 00 = yield until the next tick),
script-pointer advance, and the object fields that changed. Lengths of conditional ops include the 1- or 2-byte jump offset.
Distances use the on-screen coordinates (obj+0x20, obj+0x22 - obj+0x45) of the monster and of hero 0."""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_sim

BASE = ai_sim.SCRIPT_BASE
P = 0x7000      # scratch script address (patched copy only)


class Bench:
    def __init__(self, rom, state):
        self.rom = bytearray(rom)
        self.sim = ai_sim.Sim(self.rom, state, 0, (20, 25))
        self.env = self.sim.env; self.c = self.sim.c; self.o = self.sim.o
        self.h = self.env.obj(0)
        self.rnd = random.Random(1)

    def place(self, dx=None, dy=0, mx=128, my=112):
        o, h = self.o, self.h
        o.sw(0x20, mx); o.sw(0x22, my)
        if dx is not None:
            h.sw(0x20, (mx + dx) & 0xFFFF); h.sw(0x22, (my + dy) & 0xFFFF)

    def reseed(self):
        c = self.c
        c.wram[0x3F0] = self.rnd.randrange(15)
        for i in range(0x3F1, 0x400): c.wram[i] = self.rnd.randrange(256)

    def snap(self):
        o = self.o
        return {k: o.b(k) for k in list(range(0x140, 0x160)) + [0x1AC, 0x1AD, 0x1ED, 0x19B]}

    def run(self, code, pc=P, reseed=True, **fields):
        for i, b in enumerate(code): self.rom[BASE + pc + i] = b
        o = self.o
        o.sw(0x144, pc); o.sb(0x14F, 0)
        for k, v in fields.items():
            if k == 'tgt': o.sb(0x1AC, v)
            elif k == 'var': o.sb(0x147, v << 4)
            elif k == 'hp': o.sw(0x182, v)
            elif k == 'gauge': o.sb(0x1ED, v)
            elif k == 'depth': o.sb(0x14F, 1); o.sw(0x150, v)
            elif k == 'saved': o.sw(0x148, v[0]); o.sw(0x14A, v[1])
        if reseed: self.reseed()
        before = self.snap()
        self.env.call(0xC1251A, Y=o.base, m=1, x=0, long=False, DB=0x7E)
        a = self.c.A & 0xFF
        after = self.snap()
        diff = {hex(k): '%02X' % after[k] for k in after if after[k] != before[k] and k not in (0x144, 0x145)}
        return dict(A=a, pc=o.w(0x144), adv=o.w(0x144) - pc, diff=diff, depth=o.b(0x14F))


def show(name, r):
    print('%-44s A=%02X adv=%+d depth=%d %s' % (name, r['A'], r['adv'], r['depth'], r['diff']))


def new_ops(b):
    """Exhaustive checks of the opcodes the Chobin Hood (id 3) and Polter Chair (id 0x0D) scripts use beyond the Rabite's 33:
    34 (target within 16 px), 6A / 73 (target in a vertical / horizontal lane), BE / BF (cardinal turn toward / away), DC (set byte).
    Each model is compared with the real handler over every case listed; the result is printed as 'cases / mismatches'."""
    h, o = b.h, b.o
    h.sw(0x190, 0)
    print('--- 34: jump unless the current target is valid and within 16 px (distance class 1)')
    bad = n = 0
    for d in range(0, 40):
        b.place(d); r = b.run(bytes([0x34, 0x85]), tgt=0); n += 1
        bad += (r['adv'] == 2) != (d <= 16)
    b.place(10); r = b.run(bytes([0x34, 0x85]), tgt=0xFF); n += 1; bad += r['adv'] == 2
    print('34: %d cases, %d mismatches (d <= 16 falls through; no target jumps)' % (n, bad))
    print('--- 6A / 73: dx, dy = hero - monster on screen (dy uses obj+0x22 - obj+0x45)')
    for op in (0x6A, 0x73):
        bad = n = 0
        for oth in range(-60, 61):
            for v in range(-30, 31):
                dx, dy = (v, oth) if op == 0x6A else (oth, v)
                if not (0 <= 128 + dx < 256 and 0 <= 112 + dy < 224): continue
                b.place(dx, dy); r = b.run(bytes([op, 0x85]), tgt=0); n += 1
                pred = (abs(dx) <= 15 and abs(dx) < abs(dy)) if op == 0x6A else (abs(dy) <= 15 and abs(dy) <= abs(dx))
                bad += (r['adv'] == 2) != pred
        print('%02X: %d cases, %d mismatches (falls through iff %s)' % (op, n, bad, '|dx| <= 15 and |dx| < |dy|' if op == 0x6A else '|dy| <= 15 and |dy| <= |dx|'))
        b.place(30, 0); r = b.run(bytes([op, 0x85]), tgt=0xFF); print('%02X with no target: %s' % (op, 'jump' if r['adv'] != 2 else 'fall'))
    print('--- BE / BF: command C1 with a cardinal code, animation arg1, flag arg2 (no-op when there is no valid target)')
    for op in (0xBE, 0xBF):
        bad = n = 0
        for dx in range(-60, 61, 3):
            for dy in range(-60, 61, 3):
                if dx == 0 and dy == 0: continue
                if not (0 <= 128 + dx < 256 and 0 <= 112 + dy < 224): continue
                b.place(dx, dy); b.o.sb(0x140, 0); b.o.sb(0x141, 0)
                r = b.run(bytes([op, 3, 5]), tgt=0); n += 1
                toward = (1 if dx >= 0 else 2) if abs(dx) >= abs(dy) else (4 if dy > 0 else 8)
                want = toward if op == 0xBE else {1: 2, 2: 1, 4: 8, 8: 4}[toward]
                ok = b.o.b(0x140) == 0xC1 and b.o.b(0x141) == want and b.o.b(0x142) == 3 and b.o.b(0x143) == 5 and r['A'] == 0 and r['adv'] == 3
                bad += not ok
        print('%02X: %d cases, %d mismatches (code = %s; |dx| >= |dy| is horizontal)' % (op, n, bad, 'toward' if op == 0xBE else 'away'))
        b.place(30, 0); b.o.sb(0x140, 0); r = b.run(bytes([op, 3, 5]), tgt=0xFF); print('%02X with no target: A=%02X adv=%d cmd=%02X' % (op, r['A'], r['adv'], b.o.b(0x140)))
    print('--- DC a b v: byte(object a, offset b + 0x180) = v, continue')
    b.place(40)
    r = b.run(bytes([0xDC, 0x80, 0x6D, 0x00]), gauge=50); show('DC 80 6D 00 (self+0x1ED = 0)', r); print('self+0x1ED =', b.o.b(0x1ED))
    r = b.run(bytes([0xDC, 0x80, 0x6D, 0x07]), gauge=50); show('DC 80 6D 07', r); print('self+0x1ED =', b.o.b(0x1ED))
    h.sb(0x1ED, 50); r = b.run(bytes([0xDC, 0x00, 0x6D, 0x09]), gauge=50); print('DC 00 6D 09 sets hero 0 +0x1ED =', h.b(0x1ED), ' (object ref 0 = slot 0)')


def main():
    rom = romio.rom_from_argv(); state = sys.argv[1]
    b = Bench(rom, state)
    b.env.obj(0).sw(0x190, 0)
    if '--new' in sys.argv:
        new_ops(b); return
    print('--- control flow')
    r = b.run(bytes([0x01, 0x85])); show('01 JMP +5 (1-byte offset 0x85)', r)
    r = b.run(bytes([0x01, 0x00, 0x20])); show('01 JMP 2-byte offset 0x0020', r)
    r = b.run(bytes([0x01, 0xC1])); show('01 JMP -63 (0xC1)', r)
    r = b.run(bytes([0xFF, 0x00, 0x90])); show('FF CALL 0090 (stack push)', r)
    print('stack word at 0x150:', hex(b.o.w(0x150)), 'new pc', hex(r['pc']))
    r = b.run(bytes([0x00]), depth=0x1234); show('00 RET at depth 1 (pops 0x1234)', r)
    print('new pc', hex(r['pc']))
    print('--- variable ops (nibble variable 3 = obj+0x147 high nibble)')
    for v in (0, 1, 3):
        r = b.run(bytes([0x05, 0x85]), var=v); show('05 IF var3!=0 jump (var3=%d)' % v, r)
    for v in (0, 1):
        r = b.run(bytes([0x09, 0x85]), var=v); show('09 IF var3==0 jump (var3=%d)' % v, r)
    for v in (1, 2):
        r = b.run(bytes([0x0D, 0x01, 0x85]), var=v); show('0D 01 IF var3!=1 jump (var3=%d)' % v, r)
    for n in (2, 3, 4, 5, 7):
        cnt = collections.Counter()
        for _ in range(4000):
            b.run(bytes([0x2C, n]));  cnt[b.o.b(0x147) >> 4] += 1
        print('2C %02d  var3 = rand 0..%d: %s' % (n, n, dict(sorted(cnt.items()))))
    print('--- compare ops on object fields (argument 1 = object ref: 0x80 self, 0x81 current target slot; argument 2 = byte offset)')
    b.o.sw(0x182, 20)
    for hp in (9, 10):
        b.o.sw(0x182, hp)
        r = b.run(bytes([0xBD, 0x80, 0x02, 0x09, 0x00, 0x85])); show('BD 80 02 0009 (word self+0x182 > 9 jumps) hp=%d' % hp, r)
    b.o.sw(0x182, 20)
    for g in (0, 5):
        r = b.run(bytes([0x30, 0x80, 0x6D, 0x00, 0x85]), gauge=g); show('30 80 6D 00 (byte self+0x1ED > 0 jumps) 1ED=%d' % g, r)
    for t in (3, 0xFF):
        r = b.run(bytes([0x2F, 0x80, 0x2C, 0xFF, 0x85]), tgt=t); show('2F 80 2C FF (byte self+0x1AC < 0xFF jumps) 1AC=%02X' % t, r)
    print('--- target classes (distance d between monster and hero 0 on screen)')
    for d in (10, 16, 17, 32, 33, 48, 49, 64, 65, 96, 97):
        row = []
        for op in (0x31, 0x49, 0x4E, 0x53, 0x58):
            b.place(d); r = b.run(bytes([op, 0x85])); row.append('%02X:%s' % (op, 'jump' if r['adv'] != 2 else 'fall'))
        sel = []
        for op in (0xA5, 0xB1, 0xB4, 0xB7, 0x5D):
            b.place(d); r = b.run(bytes([op])); sel.append('%02X->1AC=%02X' % (op, b.o.b(0x1AC)))
        print('d=%3d  IF(no hero within 16/32/48/64/any)=%s  select=%s' % (d, ' '.join(row), ' '.join(sel)))
    print('--- class vs current target (op 4C/51/56 jump unless target valid and within 32/48/64)')
    for d in (30, 33, 47, 50, 63, 66):
        row = []
        for op in (0x4C, 0x51, 0x56):
            b.place(d); b.o.sb(0x1AC, 0); r = b.run(bytes([op, 0x85]), tgt=0); row.append('%02X:%s' % (op, 'jump' if r['adv'] != 2 else 'fall'))
        print('d=%3d %s' % (d, ' '.join(row)))
    b.place(30); r = b.run(bytes([0x4C, 0x85]), tgt=0xFF); show('4C with no target', r)
    print('--- position memory (9F stores, 9D jumps when unchanged)')
    b.place(40)
    r = b.run(bytes([0x9F])); show('9F store screen position', r)
    print('saved:', b.o.w(0x148), b.o.w(0x14A))
    r = b.run(bytes([0x9D, 0x85]), reseed=False); show('9D after 9F (unchanged -> jump)', r)
    b.o.sw(0x20, 131)
    r = b.run(bytes([0x9D, 0x85]), reseed=False); show('9D after moving x by 3 (-> fall through)', r)
    print('--- command ops (cmd bytes obj+0x140..0x143)')
    b.place(40)
    r = b.run(bytes([0xE0, 0x09, 0x04, 0x00])); show('E0 09 04 00', r)
    r = b.run(bytes([0xE2, 0x05])); show('E2 05', r)
    r = b.run(bytes([0xE4, 0x02, 0x00]), tgt=0); show('E4 02 00 target at +40,0', r)
    r = b.run(bytes([0xFD, 0x02, 0x00]), tgt=0); show('FD 02 00 target at +40,0', r)
    r = b.run(bytes([0xE6, 0x02, 0x00]), tgt=0); show('E6 02 00 target at +40,0', r)
    r = b.run(bytes([0xFE, 0x02, 0x00]), tgt=0); show('FE 02 00 target at +40,0', r)
    r = b.run(bytes([0xE4, 0x02, 0x00]), tgt=0xFF); show('E4 02 00 with no target', r)
    r = b.run(bytes([0xE8]), gauge=0); show('E8 gauge 0', r)
    r = b.run(bytes([0xE8]), gauge=7); show('E8 gauge 7', r)
    b.o.sb(0x10, 1); b.o.sb(0x6, 0); b.o.sb(0x7, 0)
    r = b.run(bytes([0xE3, 0x00, 0x00])); show('E3 00 00 facing 1, no velocity', r)
    b.o.sb(0x10, 0)
    r = b.run(bytes([0xE3, 0x00, 0x00])); show('E3 00 00 facing 0, no velocity', r)
    new_ops(b)


if __name__ == '__main__':
    main()

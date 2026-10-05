"""Check the Python model of the AI bytecode machine (tools/ai_vm.py) against the real handlers, step by step, in randomised worlds.
usage: monster_model.py ROM STATE [ID[,ID...]] [N_STEPS]      (default ids 0,3,0x0D; default 6000 steps per id)
For every id the monster is created by the game's spawner in slot 3 and the real AI step ($C1:2552) is called N times. Before each step the world is
randomised and written into the object records of the monster and the three heroes: hero positions (on screen, off screen, in each distance band,
near the 255 / 223 limits), hero active flags and status words (valid or one of the bits 0x8460), monster position (sometimes equal to the position saved by
op 9F), jump height, facing, HP (around the thresholds of the scripts), weapon gauge (zero or not) and the level byte of the heroes. The RNG routine
$C1:26FB is replaced by a list of random bytes that the model consumes in the same order. After the step the command bytes, the script pointer, the call stack,
variable 3, the target slot, the saved position and the number of random bytes drawn are compared with the model. Output: steps compared, mismatches,
distribution of the first command written (so that the coverage of each routine is visible)."""
import sys, os, random, collections, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_sim, ai_vm

HP_POINTS = {0: (9, 10, 20), 3: (60,), 13: (127, 128)}


class Scenario:
    """A world that persists for about 20 steps (hero offsets, HP, gauge, flags) with small random jitter in between, so that the loops of the scripts run
    for several steps; every step also has a small chance of a completely random world."""
    def __init__(self, rnd, mid, hp_full):
        self.rnd, self.mid, self.hp_full = rnd, mid, hp_full
        self.left = 0

    def draw(self):
        rnd = self.rnd
        self.heroes = []
        for i in range(3):
            band = rnd.choice([8, 14, 20, 30, 33, 40, 47, 52, 62, 70, 90, 100, 140, 400])
            ang = rnd.uniform(0, 360)
            dx = int(round(band * math.cos(math.radians(ang)))); dy = int(round(band * math.sin(math.radians(ang))))
            r = rnd.random()
            if r < 0.3:                                    # axis-aligned lane cases for the Chobin ops
                if rnd.random() < 0.5: dx = rnd.randint(-17, 17)
                else: dy = rnd.randint(-17, 17)
            elif r < 0.34: dx = rnd.choice([200, -200, 255]); dy = rnd.choice([160, -90, 100])
            st = 0 if rnd.random() < 0.9 else rnd.choice([0x0020, 0x0400, 0x0040, 0x8000, 0x2000, 0x0010])
            self.heroes.append([dx, dy, st, 1 if (i == 0 or rnd.random() < 0.5) else 0])
        self.hp = rnd.choice(list(HP_POINTS.get(self.mid, (20,))) + [self.hp_full, self.hp_full, 1, rnd.randint(1, self.hp_full)])
        self.gauge = rnd.choice([0, 0, 3, 99])
        self.facing = rnd.choice([0, 1, 2, 0x82])
        self.level = rnd.randrange(80)
        self.left = rnd.randint(5, 30)

    def world(self, vm):
        rnd = self.rnd
        if self.left <= 0: self.draw()
        self.left -= 1
        me = ai_vm.Actor(128 + rnd.randint(-30, 30), 112 + rnd.randint(-30, 30), 0, 1, 0)
        if vm.saved[0] != 0xFFFF and rnd.random() < 0.5: me.x, me.y = vm.saved[0], vm.saved[1]
        if rnd.random() < 0.1: me.h = rnd.randint(1, 15)
        heroes = []
        for dx, dy, st, act in self.heroes:
            jx = rnd.randint(-3, 3) if rnd.random() < 0.5 else 0
            jy = rnd.randint(-3, 3) if rnd.random() < 0.5 else 0
            x, y = me.x + dx + jx, me.ey + dy + jy
            r = rnd.random()
            if r < 0.01: x = rnd.choice([255, 256, 300, 0xFFF0])
            elif r < 0.02: y = rnd.choice([223, 224, 230, 0xFFF0])
            heroes.append(ai_vm.Actor(x & 0xFFFF, y & 0xFFFF, 0, act, st))
        if rnd.random() < 0.15: self.gauge = rnd.choice([0, 0, 3, 99])
        if rnd.random() < 0.05: self.hp = rnd.choice(list(HP_POINTS.get(self.mid, (20,))) + [self.hp_full, 1])
        if rnd.random() < 0.3: self.facing = rnd.choice([0, 1, 2, 0x82])
        return ai_vm.World(me, heroes, gauge=self.gauge, hp=self.hp, level=self.level, facing=self.facing)


def compare(rom, state, mid, n, seed=1):
    rnd = random.Random(seed)
    s = ai_sim.Sim(rom, state, mid, (20, 25), only_hero0=False)
    env, c, o = s.env, s.c, s.o
    heroes = [env.obj(i) for i in range(3)]
    entry = rom[0x100000 + mid * 16 + 9] | rom[0x100000 + mid * 16 + 10] << 8
    hp_full = o.w(0x182)
    vm = ai_vm.VM(rom, entry)
    scen = Scenario(rnd, mid, hp_full)
    forced = []
    def rng_hook(cp):
        v = forced.pop(0) if forced else 0
        s.rng_used += 1
        cp.A = (cp.A & 0xFF00) | v
        cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
    s.rng_used = 0
    c.hooks[0xC126FB] = rng_hook
    c.hooks[0xC12552] = lambda cp: False
    o.sw(0x144, entry); o.sb(0x14F, 0); o.sb(0x1AC, 0xFF); o.sw(0x148, 0xFFFF); o.sw(0x14A, 0xFFFF); o.sb(0x147, 0)
    for h in heroes[1:]: h.sb(0, 1)
    bad = 0; first = collections.Counter(); errors = 0
    visited = set()
    for k in range(n):
        if k % 150 == 0 and k:                       # restart the script at its entry: the spawn-time routines are rarely reached otherwise
            visited |= vm.visited
            vm = ai_vm.VM(rom, entry)
            o.sw(0x144, entry); o.sb(0x14F, 0); o.sb(0x1AC, 0xFF); o.sw(0x148, 0xFFFF); o.sw(0x14A, 0xFFFF); o.sb(0x147, 0)
            scen.left = 0
        w = scen.world(vm)
        rng = [rnd.randrange(256) for _ in range(64)]
        o.sw(0x20, w.me.x); o.sw(0x22, w.me.y); o.sb(0x45, w.me.h); o.sb(0x10, w.facing); o.sw(0x182, w.hp); o.sb(0x1ED, w.gauge)
        o.sb(0x6, 0); o.sb(0x7, 0); o.sw(0x190, 0)
        for i, h in enumerate(heroes):
            a = w.heroes[i]
            h.sb(0, a.active); h.sw(0x20, a.x); h.sw(0x22, a.y); h.sb(0x45, 0); h.sw(0x190, a.status); h.sb(0x181, w.level)
        for i in range(0x140, 0x144): o.sb(i, 0)
        forced[:] = rng; s.rng_used = 0
        env.call(0xC12552, X=0x600, m=1, x=0, long=False, DB=0x7E, max_steps=3000000)
        real = dict(cmd=[o.b(0x140 + i) for i in range(4)], pc=o.w(0x144), depth=o.b(0x14F), var3=o.b(0x147) >> 4, tgt=o.b(0x1AC),
                    saved=(o.w(0x148), o.w(0x14A)), draws=s.rng_used, stack=[o.w(0x150 + 2 * i) for i in range(o.b(0x14F))])
        vm_tgt_before = vm.tgt
        try:
            cmd, _ = vm.step(w, rng)
            model = dict(cmd=cmd, pc=vm.pc, depth=len(vm.stack), var3=vm.var3, tgt=vm.tgt, saved=vm.saved, draws=vm.draws, stack=[p for p in vm.stack])
        except ai_vm.VMError as e:
            errors += 1
            print('model error', e); break
        ok = all(model['cmd'][i] is None or model['cmd'][i] == real['cmd'][i] for i in range(4)) and model['cmd'][0] == real['cmd'][0]
        ok = ok and all(real[key] == model[key] for key in ('pc', 'depth', 'var3', 'tgt', 'saved', 'draws', 'stack'))
        first[(real['cmd'][0], real['cmd'][2] if real['cmd'][0] == 0xC1 else None)] += 1
        if not ok:
            bad += 1
            if bad <= 5:
                print('MISMATCH step %d' % k, 'real', real, 'model', model)
                print('  world: me', vars(w.me), 'facing', w.facing, 'hp', w.hp, 'gauge', w.gauge, 'tgt before', vm_tgt_before)
                for i, a in enumerate(w.heroes): print('  hero', i, vars(a), 'valid', ai_vm.valid(a), 'class', ai_vm.dist_class(w.me, a))
            break
        # the real object keeps its saved position / stack / variable: the model does the same, so both continue from the same state
    return k + 1 - (1 if bad else 0), bad, first, visited | vm.visited


def static_reach(rom, pc0):
    import aidis
    seen = set(); st = [pc0]
    while st:
        p = st.pop()
        while p not in seen:
            ln, t, tg, ft = aidis.decode(rom, p)
            seen.add(p)
            if tg is not None: st.append(tg)
            if not ft: break
            p += ln
    return seen


def main():
    rom = romio.rom_from_argv(); state = sys.argv[1]
    ids = [int(x, 0) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else [0, 3, 0x0D]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
    for mid in ids:
        done, bad, first, visited = compare(rom, state, mid, n)
        import ai_scripts
        entry = rom[0x100000 + mid * 16 + 9] | rom[0x100000 + mid * 16 + 10] << 8
        reach = static_reach(rom, entry)
        print('id %d: %d AI steps compared, %d mismatches' % (mid, done, bad))
        print('   script instructions executed by the model: %d of %d reachable (missing: %s)' % (len(visited & reach), len(reach), ' '.join('%04X' % p for p in sorted(reach - visited))))
        print('   first command byte / animation of each step:', dict(sorted(first.items(), key=lambda kv: str(kv[0]))))


if __name__ == '__main__':
    main()

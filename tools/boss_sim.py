"""Spawn bosses with the game's own boss spawner and step the real engine, logging which attack rows ($C0:006C) and spells they use.
usage: boss_sim.py ROM STATE FRAMES SEEDS BOSS_IDS    e.g.  boss_sim.py rom.sfc arena.zs3 3000 1,2 79,7f
STATE must be the map-246 (Dark Lich arena) save state: the boss id is patched into its map object (WRAM $C82D) and the game's spawn routine
$C2:0000 builds the boss from it. One JSON line per boss/seed: attack rows seen, spell ids seen, objects created (slot, flags $98, id, init handler $B4).
The rows are those set by native handlers and state scripts through $C0:006C; no hero is hit (the loader call is intercepted)."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lich_sim


def run(rom, state, boss, frames, seed):
    s = lich_sim.Sim(rom, state, rng_index=seed); c = s.c
    def rtl(cp):
        cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True
    rows = collections.Counter()
    def h(cp):
        rows[cp.A & 0xFFFF] += 1; return rtl(cp)
    c.hooks[0xC0006C] = h
    c.wram[0xC82D] = boss
    s.spawn(boss)
    objs = [(k, '0x%04X' % s.r16(0x98, k), s.r8(0x1E7, k), '0x%04X' % s.r16(0xB4, k)) for k in range(9) if s.r8(0, k) == 1]
    spells = collections.Counter(); last = {}
    for f in range(frames):
        s.frame()
        for k in range(9):
            if s.r8(0, k) != 1: continue
            key = (k, s.r8(0x170, k), s.r8(0x171, k))
            if last.get(k) != key and s.r8(0x170, k): spells[s.r8(0x170, k)] += 1
            last[k] = key
    return dict(boss=boss, seed=seed, frames=frames, attack_rows=dict(rows), spells=dict(spells), objects=objs)


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read(); state = sys.argv[2]
    frames = int(sys.argv[3]); seeds = [int(x) for x in sys.argv[4].split(',')]
    for b in sys.argv[5].split(','):
        for sd in seeds:
            print(json.dumps(run(rom, state, int(b, 16), frames, sd)), flush=True)

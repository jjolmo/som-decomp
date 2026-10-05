"""Statistics over many simulated Dark Lich runs (different RNG start index).
usage: lich_stats.py ROM STATE FRAMES SEEDS [EVENTS_PICKLE_OUT]"""
import sys, collections, multiprocessing as mp, romio, lich_sim
def run(args):
    rom, st, frames, seed = args
    s = lich_sim.Sim(rom, st, rng_index=seed); s.spawn()
    ev = []; last = None
    for _ in range(frames):
        s.frame(); sn = s.snapshot()
        key = (sn['state'], sn['seq'], sn['flags7e'])
        if key != last:
            ev.append((s.f, sn['state'], sn['seq'], sn['mode82'], sn['flags7e'], sn['ad'])); last = key
    return ev
if __name__ == '__main__':
    rom = romio.rom_from_argv(); st = sys.argv[1]; frames = int(sys.argv[2]); seeds = int(sys.argv[3])
    pickle_path = sys.argv[4] if len(sys.argv) > 4 else None
    with mp.Pool() as p:
        res = p.map(run, [(rom, st, frames, 7*i+1) for i in range(seeds)])
    if pickle_path:
        import pickle; pickle.dump(res, open(pickle_path, 'wb'))
    cnt = collections.Counter()
    for ev in res:
        for e in ev: cnt[e[1]] += 1
    print(sorted(cnt.items()))

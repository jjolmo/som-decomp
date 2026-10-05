"""Monte-Carlo examples with the validated physical model (no ROM needed).  usage: example_damage.py"""
import random, rng as R, phys_model as P
def sim(atk, acc, stage, ev, df, trials=20000, crit=0, hero=True, gauge=0, seed=1, e6=0):
    rnd = random.Random(seed); tot = hits = 0; hist = []
    for _ in range(trials):
        rg = R.Rng([rnd.randrange(256) for _ in range(15)], rnd.randrange(15))
        a = dict(E197=acc, E190=0, B0=0, B0w=0, ED=gauge, E198=atk, E19B=stage, AE=0, E6=e6, E196=crit, E191=0, E189=50, CC76=0)
        d = dict(A4=ev, A5=df, B0=0, E191=0, E190=0, B1=0, BF=0, E194=0, A2=0, A0=0)
        e, dd = P.def_terms(d)
        ok, accv = P.hit_test(a, e, rg)
        if not ok: continue
        dmg, c = P.damage(a, d, 2, accv, e, dd, rg, 0, hero)
        hits += 1; tot += dmg; hist.append(dmg)
    hist.sort()
    return hits / trials, (tot / max(1, hits)), (hist[len(hist) // 2] if hist else 0), (hist[-1] if hist else 0)
if __name__ == '__main__':
    for name, args in (('boy lv66 atk135 vs Dark Lich (eva99 def200), stage 0', dict(atk=135, acc=92, stage=0, ev=99, df=200, crit=29)),
                       ('same, stage 8', dict(atk=135, acc=92, stage=8, ev=99, df=200, crit=29)),
                       ('same, stage 8, gauge half-empty (E1ED=30)', dict(atk=135, acc=92, stage=8, ev=99, df=200, crit=29, gauge=30)),
                       ('Rabite-like (eva0 def0), boy lv1 atk 17 acc 90 stage 0', dict(atk=17, acc=90, stage=0, ev=0, df=0, crit=5))):
        for e6 in (0, 8):     # E1E6 = $CFFC of the hero: 0 at new game, 8 in the late-game saves (docs/rom-combat.md 11.6)
            h, mean, med, mx = sim(e6=e6, **args)
            print('%-62s E1E6=%d hit %.3f  mean dmg(on hit) %.1f  median %d  max %d' % (name, e6, h, mean, med, mx))

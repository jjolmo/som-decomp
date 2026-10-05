"""Measure the commands an AI script can issue (obj+0x140..0x143) by executing them on a monster with the AI step replaced.
usage: ai_cmds.py ROM STATE [MONSTER_ID] [OUT.json]
For every case the command is written once at the next AI step; the object then runs the real per-frame routine until the AI step is due
again. Reported per case: frames until the actor is free again (AI steps run on every 5th frame, so this is a multiple of 5), displacement in
pixels, number of frames with movement and the largest per-frame step. Cases: hop command C1 (direction code, animation id, flag), pose
command 40, attack swing 02 issued after a turn command (as the script does; the weapon-level nibble is copied to obj+0x19B as op E8 does and hero 0 is the current target, which selects the swing animation). Facing codes: 1 right, 2 left, 4 down, 8 up."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_sim

FPS = 60.0988


def measure(rom, state, mid, cmds, tile=(20, 25), maxf=600):
    """cmds: list of commands issued one per AI step; the last one is measured."""
    s = ai_sim.Sim(rom, state, mid, tile)
    o = s.o; c = s.c
    q = list(cmds); ev = []
    def ai(cp):
        if cp.X < 0x600:
            cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
        if q:
            cm = q.pop(0)
            for i, v in enumerate(cm): c.wram[o.base + 0x140 + i] = v
            if cm[0] == 2: o.sb(0x19B, o.b(0x1C0)); o.sb(0x1AC, 0)     # as in the script: weapon-level nibble copied, hero 0 is the target
            ev.append(('issue', s.f, o.w(2), o.w(4)))
        else:
            c.wram[o.base + 0x140] = 0; ev.append(('free', s.f, o.w(2), o.w(4)))
        cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
    c.hooks[0xC12552] = ai
    n = len(cmds)
    steps = []; px, py = o.w(2), o.w(4)
    for f in range(maxf):
        s.frame()
        x, y = o.w(2), o.w(4)
        if len(ev) >= n and ev[n - 1][0] == 'issue' and (x, y) != (px, py): steps.append((s.f - 1 - ev[n - 1][1], x - px, y - py))
        px, py = x, y
        if len(ev) > n: break
    t0, t1 = ev[n - 1], ev[n]
    free = t1[1] - t0[1]
    return dict(cmd=list(cmds[-1]), preceded_by=[list(x) for x in cmds[:-1]], frames_until_free=free, seconds=round(free / FPS, 3),
                dx=t1[2] - t0[2], dy=t1[3] - t0[3], move_frames=len(steps), first_move=steps[0][0] if steps else None,
                last_move=steps[-1][0] if steps else None, max_step=max([max(abs(a), abs(b)) for _, a, b in steps] or [0]))


def swing_by_distance(rom, state, mid=0):
    """Swing (command 02 after a turn) against hero 0 standing d px away along the facing axis: animation chosen, frames, displacement."""
    out = []
    for face, vec in ((1, (1, 0)), (2, (-1, 0)), (4, (0, 1)), (8, (0, -1))):
        for d in range(10, 70, 2):
            s = ai_sim.Sim(rom, state, mid, (20, 25), hero=(vec[0] * d, vec[1] * d))
            o = s.o; c = s.c
            q = [(0xC1, face, 0, 0), (2, face, 0, 0)]; ev = []; anim = None
            def ai(cp):
                if cp.X < 0x600:
                    cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
                if q:
                    cm = q.pop(0)
                    for i, v in enumerate(cm): c.wram[o.base + 0x140 + i] = v
                    if cm[0] == 2: o.sb(0x19B, o.b(0x1C0)); o.sb(0x1AC, 0)
                    ev.append((s.f, o.w(2), o.w(4)))
                else:
                    c.wram[o.base + 0x140] = 0; ev.append((s.f, o.w(2), o.w(4)))
                cp.PC = (cp.pull16() + 1) & 0xFFFF; return True
            c.hooks[0xC12552] = ai
            for f in range(300):
                s.frame()
                if len(ev) >= 2 and anim is None: anim = o.b(0x11)
                if len(ev) >= 3: break
            out.append(dict(facing=face, distance=d, animation=anim, frames=ev[2][0] - ev[1][0], dx=ev[2][1] - ev[1][1], dy=ev[2][2] - ev[1][2]))
    return out


def main():
    rom = romio.rom_from_argv(); state = sys.argv[1]
    mid = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    out = sys.argv[3] if len(sys.argv) > 3 else None
    res = []
    for anim in (0, 1, 2, 4, 5):
        for d in (1, 2, 4, 8):
            res.append(measure(rom, state, mid, [(0xC1, d, anim, 0)]))
    for anim in (1, 2, 4, 5):
        for d in (5, 6, 9, 10):
            res.append(measure(rom, state, mid, [(0xC1, d, anim, 0)]))
    for pose in (0, 5):
        res.append(measure(rom, state, mid, [(0x40, pose, 0, 0)]))
    for d in (1, 2, 4, 8):
        res.append(measure(rom, state, mid, [(0xC1, d, 0, 0)]))
    for d in (1, 2, 4, 8):
        r = measure(rom, state, mid, [(0xC1, d, 0, 0), (2, d, 0, 0)]); res.append(r)
    sw = swing_by_distance(rom, state, mid)
    for r in res: print(r)
    for r in sw: print(r)
    if out:
        json.dump(dict(source='tools/ai_cmds.py: real per-frame routine $C0:B08C, monster %d in slot 3, AI step $C1:2552 replaced by one command; '
                              'frames = 60.0988 Hz video frames, AI steps only on every 5th frame' % mid, fps=FPS, cases=res, swing_by_distance=sw), open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()

"""Rip the hero attack animations of the whip, bow, boomerang and javelin, including the projectiles in flight, and the projectile sprites
(graphics go to a directory chosen by the caller, never into the repository).
usage: rip_ranged_anims.py ROM STATE OUTDIR WEAPON [hero[,hero]] [attack[,attack]] [dir[,dir]] [x,y]
  WEAPON: whip | bow | boomerang | javelin | 4-7 | row=N       hero: boy girl sprite (default all)       dir: up down left right (default all)
  attack (default: every distinct one): normal0..normal3 (animation ids 0-3), charge1..8 (charged attack of stage 1-8, nothing in range = class far)
    and chargemid1..8 / chargenear1..8 (classes mid / near; for these four weapons they have the same script as chargeN, see aliases.json).
  x,y: screen position of the centre of the lunges (default: 128,112 for left/right, 128,150 for up, 128,90 for down, so that the longest flight stays on screen)
Output: OUTDIR/<weapon>/<hero>/<attack>_<level>_<dir>_<nn>.png and <attack>_<level>_<dir>.json (as tools/rip_hero_anims.py; the animation lasts until the
attack state is over AND the last projectile is gone; JSON fields swing_frames, projectile_frames), OUTDIR/<weapon>/index.json, aliases.json (animations that
share a script with a ripped one) and OUTDIR/<weapon>/projectile/<tile>_<flips>.png (every distinct 16x16 projectile piece seen) with projectile_sprites.json.
Everything is done by tools/rip_hero_anims.py (PPU/DMA capture, tile decoding, export); only the end condition of the recording, the screen positions and the
projectile bookkeeping are added here."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio
import rip_hero_anims as RH
import gfx_decode as G
import ranged_sim as RS

NORMAL = dict(normal0=(0, 1, 0), normal1=(0, 0, 1), normal2=(1, 0, 2), normal3=(2, 0, 3))      # attack -> (distance class, $F4 parity, expected animation id)
POS = dict(left=(128, 112), right=(128, 112), up=(128, 150), down=(128, 90))
PROJ_BASE = RS.PROJ_BASE
SEEN = {}          # (tile, pal, hflip, vflip) -> dict of observations, for the projectile sprite export


def record(g, slot, B, pad_of, max_frames=700):
    """Like rip_hero_anims.record, but the recording ends only when the attack state is 0 and the projectile flag (+0x61) is 0 too."""
    c = g.c
    s0 = g.w16(B + 0x16); lat = []; frs = []; started = False; p0 = (g.w16(B + 2), g.w16(B + 4)); swing = None
    for i in range(max_frames):
        g.frame(pad_of(i)); fr = RH.grab(g, slot, B)
        state = fr['state']
        started = started or state != 0
        if started and state == 0 and swing is None:
            swing = len(frs)
        if started and state == 0 and c.wram[B + 0x61] == 0 and swing is not None and i > 3:
            break
        ents = [bytes(c.wram[PROJ_BASE + 0x40 * slot + 0x10 * k:PROJ_BASE + 0x40 * slot + 0x10 * k + 16]) for k in range(3)]
        fr['proj'] = [dict(kind=e[0], dying=e[7], attr=e[14] | e[15] << 8) for e in ents if e[0] and not e[0] & 0xF8]
        for e in fr['proj']:
            tile = e['attr'] & 0x1FF
            for p in fr['entries']:
                if p['tile'] == tile and p['list'] == 'D0':
                    SEEN.setdefault((p['tile'], p['pal'], p['hflip'], p['vflip']), dict(kinds=set(), dying=set(), attrs=set(), frame=None, entry=None))
                    o = SEEN[(p['tile'], p['pal'], p['hflip'], p['vflip'])]
                    o['kinds'].add(e['kind']); o['dying'].add(e['dying']); o['attrs'].add(e['attr'])
                    if o['entry'] is None or o['img'].bbox() is None:       # keep the first picture that is not empty (the tile upload can lag a frame behind the OAM)
                        o['entry'] = dict(p); o['img'] = RH.G.render([dict(i=0, x=RH.ORIGIN[0], y=RH.ORIGIN[1], tile=p['tile'], pal=p['pal'], prio=p['prio'], hflip=p['hflip'], vflip=p['vflip'], large=0)],
                                                                    c.vram, c.cgram, RH.OBJ_BASE, RH.NAME_GAP, 16, 32)
                    p['projectile'] = True
        fr['p0'] = p0; (frs if frs or (started and fr['script'] != s0) else lat).append(fr)
    for fr in frs:
        fr['swing_frames'] = swing
    return lat, frs


_export = RH.export


def export(rom, frs, outdir, name, meta):
    n = _export(rom, frs, outdir, name, meta)
    p = os.path.join(outdir, name + '.json')
    d = json.load(open(p))
    swing = frs[0].get('swing_frames')
    d['swing_frames'] = swing
    d['projectile_frames'] = d['total_frames'] - (swing or 0)
    d['max_projectiles_in_flight'] = max(len(f.get('proj', [])) for f in frs)
    for pc, f in zip(d['frames'], [frs[0]]):
        pass
    json.dump(d, open(p, 'w'), indent=1)
    return n


def aliases(rom, wtype):
    """Animations (id, facing) whose script is the same as an earlier one's: they are not ripped twice."""
    out = {}
    for var in range(40):
        for f in range(3):
            o = 0x110000 + RS.SCRIPT_BASE + RS.SCRIPT_STRIDE * wtype + 2 * (var * 3 + f)
            out.setdefault((f, rom[o] | rom[o + 1] << 8), []).append(var)
    return out


def main():
    rom = romio.rom_from_argv()
    state, outdir, weapon = sys.argv[1], sys.argv[2], sys.argv[3]
    if weapon.startswith('row='):
        row = int(weapon[4:]); wtype = row // 9
    else:
        wtype = RS.TYPE_BY_NAME[weapon] if weapon in RS.TYPE_BY_NAME else int(weapon); row = 9 * wtype
    name = RS.TYPE_NAMES.get(wtype, 'type%d' % wtype) + ('_row%d' % row if weapon.startswith('row=') else '')
    arg = lambda i: sys.argv[i].split(',') if len(sys.argv) > i and sys.argv[i] else None
    heroes = arg(4) or list(RH.HEROES)
    attacks = arg(5)
    dirs = arg(6) or list(RH.DIRS)
    pos_arg = tuple(int(v) for v in sys.argv[7].split(',')) if len(sys.argv) > 7 and sys.argv[7] else None
    # distinct animations: ids 0-3 and the three classes of a stage often share one script
    al = aliases(rom, wtype)
    if attacks is None:
        attacks = list(NORMAL)
        for v in ('charge', 'chargemid', 'chargenear'):
            attacks += ['%s%d' % (v, i) for i in range(1, 9)]
        keep, seen = [], set()
        for a in attacks:
            var = NORMAL[a][2] if a in NORMAL else 4 * int(a[-1]) + {'chargenear': 0, 'chargemid': 1, 'charge': 2}[a[:-1]]
            sig = tuple(rom[0x110000 + RS.SCRIPT_BASE + RS.SCRIPT_STRIDE * wtype + 2 * (var * 3 + f)] | rom[0x110000 + RS.SCRIPT_BASE + RS.SCRIPT_STRIDE * wtype + 2 * (var * 3 + f) + 1] << 8 for f in range(3))
            sig = (0 if a in NORMAL else int(a[-1]),) + sig
            if sig not in seen:
                seen.add(sig); keep.append(a)
        attacks = keep
    RH.NORMAL.clear(); RH.NORMAL.update(NORMAL)
    RH.record = record; RH.export = export
    root = os.path.join(outdir, name)
    for d in dirs:
        RH.rip(rom, state, root, heroes, row, attacks, [d], pos_arg or POS[d])
    os.makedirs(os.path.join(root, 'projectile'), exist_ok=True)
    meta = []
    for (tile, pal, hf, vf), o in sorted(SEEN.items()):
        fn = '%03X_p%d_h%d_v%d.png' % (tile, pal, hf, vf)
        img = o['img']; b = img.bbox()
        if b:
            G.write_png(os.path.join(root, 'projectile', fn), img.crop(*b))
        meta.append(dict(file=fn, tile=tile, palette=pal, hflip=hf, vflip=vf, projectile_kinds=sorted(o['kinds']), dying_counter_values=sorted(o['dying']),
                         attr_words=['%04X' % a for a in sorted(o['attrs'])], bbox_on_16x16_cell=list(b) if b else None))
    json.dump(meta, open(os.path.join(root, 'projectile', 'projectile_sprites.json'), 'w'), indent=1)
    json.dump({'%d_%04X' % k: v for k, v in al.items()}, open(os.path.join(root, 'aliases.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()

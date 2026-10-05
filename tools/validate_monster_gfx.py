"""Compare the pictures ripped by tools/rip_monster_anims.py with public sprite sheets (PNG files you provide), grouped by animation set.
usage: validate_monster_gfx.py RIPDIR ID SHEET.png[,SHEET.png...] [EFFECTS.png[,...]] [OUT.json]
A picture is "found" when every opaque pixel of the PNG equals the sheet pixel at some position (5-bit colours; as is, mirrored, flipped vertically or both).
A picture that is not found exactly is retried under a consistent recolouring (a function from its colours to the sheet's colours); such pictures are the ones the game
draws with a flashing palette (hit flash, casting flash) and are counted separately. The pictures of the `death` sets are looked up in the EFFECTS sheets when given
(the corpse effect is not part of the monster's own sheet; the first picture of a death animation is the live monster and is looked up in the monster sheets).
Per set (ord, atk, hurt, swing, death; animation numbers are merged over the four facings) the output lists pictures, exact matches, recoloured matches and the rest.
Standard library only."""
import sys, os, re, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_sheet as CS


def main():
    rip, mid = sys.argv[1], int(sys.argv[2], 0)
    sheets = [CS.load_sheet(p) for p in sys.argv[3].split(',')]
    eff = [CS.load_sheet(p) for p in sys.argv[4].split(',')] if len(sys.argv) > 4 and sys.argv[4] and not sys.argv[4].endswith('.json') else []
    out_path = sys.argv[-1] if sys.argv[-1].endswith('.json') else None
    d = os.path.join(rip, str(mid))
    res = collections.OrderedDict(); per_anim = collections.defaultdict(lambda: [0, 0, 0, 0])
    for jp in sorted(glob.glob(os.path.join(d, '*.json'))):
        if os.path.basename(jp) == 'index.json': continue
        j = json.load(open(jp)); nm = os.path.basename(jp)[:-5]; grp = re.sub(r'_(up|down|left|right)$', '', nm)
        kind = re.match(r'[a-z]+', grp).group(0)
        for k, fr in enumerate(j['frames']):
            pix, w, h = CS.frame_pixels(os.path.join(d, fr['file']), set())
            if len(pix) < 40: continue
            targets = (eff if (kind == 'death' and k > 0 and eff) else sheets)
            ex = any(CS.find(t, pix, w, h)[0] for t in targets)
            rc = (not ex) and any(CS.find_recoloured(t, pix, w, h) for t in targets)
            g = per_anim[grp]; g[0] += 1; g[1] += ex; g[2] += rc; g[3] += (not ex and not rc)
    out = dict(monster=mid, sheets=[os.path.basename(p) for p in sys.argv[3].split(',')], effects_sheets=[os.path.basename(p) for p in sys.argv[4].split(',')] if eff else [], per_animation={k: dict(pictures=v[0], exact=v[1], recoloured_only=v[2], not_found=v[3]) for k, v in sorted(per_anim.items())})
    tot = [sum(v[i] for v in per_anim.values()) for i in range(4)]
    out['total'] = dict(pictures=tot[0], exact=tot[1], recoloured_only=tot[2], not_found=tot[3])
    for k, v in out['per_animation'].items():
        if v['not_found'] or v['recoloured_only']: print(k, v)
    print('monster %d: %d pictures: %d exact, %d only under a recolouring, %d not found' % (mid, tot[0], tot[1], tot[2], tot[3]))
    if out_path: json.dump(out, open(out_path, 'w'), indent=1)


if __name__ == '__main__':
    main()

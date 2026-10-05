"""Rip the hero attack animations of any weapon type (graphics go to a directory chosen by the caller).
usage: rip_weapon_anims.py ROM STATE OUTDIR WEAPON [hero[,hero]] [attack[,attack]] [dir[,dir]] [x,y]
  WEAPON: glove | sword | axe | spear | a weapon type number 0-7 | row=N (an equipped weapon row id 0-71; the default is grade 0 of the type, row = 9 * type)
  hero: boy girl sprite (default all)   dir: up down left right (default all)   x,y: screen position of the centre of the lunges (default 128,112)
  attack (default all): normal0..normal3 (normal attacks, animation ids 0-3, chosen the way docs/weapons-melee.md section 2.2 describes) and
    charge1..8 / chargemid1..8 / chargenear1..8 (charged attack of stage 1-8, distance class far-or-none / mid / near, animation ids 4k+2, 4k+1, 4k)
  'index' alone only rebuilds OUTDIR/index.json.
Same output layout as tools/rip_hero_anims.py: OUTDIR/<hero>/<attack>_<level>_<dir>_<nn>.png and <attack>_<level>_<dir>.json, plus OUTDIR/index.json.
This is a thin wrapper: all work is done by tools/rip_hero_anims.py (the weapon row selects the animation script table, frame descriptors and effect tiles
through the game's own equip refresh $C0:E9F8)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio
import rip_hero_anims as R

TYPES = {'glove': 0, 'sword': 1, 'axe': 2, 'spear': 3}
NORMAL = dict(normal0=(0, 1, 0), normal1=(0, 0, 1), normal2=(1, 0, 2), normal3=(2, 0, 3))      # attack -> (distance class, $F4 parity, expected animation id)


def main():
    rom = romio.rom_from_argv()
    state, outdir, weapon = sys.argv[1], sys.argv[2], sys.argv[3]
    row = int(weapon[4:]) if weapon.startswith('row=') else 9 * (TYPES[weapon] if weapon in TYPES else int(weapon))
    arg = lambda i: sys.argv[i].split(',') if len(sys.argv) > i and sys.argv[i] else None
    heroes = arg(4) or list(R.HEROES)
    attacks = arg(5) or list(NORMAL) + ['%s%d' % (v, i) for v in R.CHARGE for i in range(1, 9)]
    dirs = arg(6) or list(R.DIRS)
    pos = tuple(int(v) for v in sys.argv[7].split(',')) if len(sys.argv) > 7 and sys.argv[7] else (128, 112)
    R.NORMAL.clear(); R.NORMAL.update(NORMAL)
    R.rip(rom, state, outdir, heroes, row, attacks, dirs, pos)


if __name__ == '__main__':
    main()

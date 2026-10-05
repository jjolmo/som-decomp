"""Survey of the ordinary monsters of the early game (object ids 0x00-0x1F): stat record, AI script size, opcodes beyond the 33 that the Rabite script uses, and what the
monster does in the real frame loop when hero 0 stands still 60 px away (monster to its right, on screen) for 8 seconds.
usage: monster_survey.py ROM STATE OUT.json [FIRST_ID LAST_ID]
Per id: level, HP, Str, Agi, element, EXP, gold, attack rows (data/monsters.json); script entry, number of reachable instructions, opcodes not used by the Rabite script, opcode
count (static walk, tools/aidis.py); from the run: commands issued by kind (turn / hop / pose / swing 02), net change of the distance to the hero, whether projectile table
entries ($7E:D000 + 0x40 * 3 + 0x10 k) were used, and whether the monster ever moved. The effort rating is a rule on the static numbers only (see the document):
low = at most 4 new opcodes, medium = 5-10, high = more than 10 or a script of more than 300 instructions."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, ai_sim, aidis, monster_model, names

FPS = 60.0988


def main():
    rom = romio.rom_from_argv(); state, out = sys.argv[1], sys.argv[2]
    lo, hi = (int(sys.argv[3], 0), int(sys.argv[4], 0)) if len(sys.argv) > 4 else (0, 0x1F)
    here = os.path.dirname(os.path.abspath(__file__))
    mon = json.load(open(os.path.join(here, '..', 'data', 'monsters.json')))['records']
    nm = names.load(rom)
    rabite = set()
    rows = []
    for mid in range(lo, hi + 1):
        entry = rom[0x100000 + 16 * mid + 9] | rom[0x100000 + 16 * mid + 10] << 8
        reach = monster_model.static_reach(rom, entry)
        ops = sorted({rom[aidis.BASE + p] for p in reach})
        if mid == 0: rabite = set(ops)
        rows.append(dict(id=mid, entry=entry, instructions=len(reach), ops=ops))
    if not rabite:
        entry = rom[0x100000 + 9] | rom[0x100000 + 10] << 8
        rabite = {rom[aidis.BASE + p] for p in monster_model.static_reach(rom, entry)}
    res = []
    for r in rows:
        mid = r['id']; m = mon[mid]
        new = sorted(set(r['ops']) - rabite)
        s = ai_sim.Sim(rom, state, mid, (20, 25), hero=(-60, 0), seed=1)
        o = s.o; h = s.obj(0)
        proj = False; d0 = None; moved = 0; px = (o.w(2), o.w(4))
        for _ in range(int(8 * FPS)):
            s.frame()
            if not proj and any(s.env.c.wram[0xD0C0 + 16 * k] for k in range(3)): proj = True
            if (o.w(2), o.w(4)) != px: moved += 1; px = (o.w(2), o.w(4))
        cmds = collections.Counter()
        for f, ops, cmd in s.steps:
            kind = {0xC1: 'move' if cmd[2] else 'turn', 0x40: 'pose', 0x02: 'swing'}.get(cmd[0], 'other%02X' % cmd[0])
            cmds[kind] += 1
        effort = 'low' if len(new) <= 4 and r['instructions'] <= 300 else 'medium' if len(new) <= 10 and r['instructions'] <= 300 else 'high'
        res.append(dict(id=mid, name_block_index=0xCF + mid, level=m['level'], hp=m['hp'], str=m['str'], agi=m['agi'], element=m['element'], exp=m['exp'], gold=m['gold'], weapons=[m['weapon_a'], m['weapon_b']],
                        script_entry=r['entry'], instructions=r['instructions'], opcodes=len(r['ops']), new_opcodes=['%02X' % x for x in new], effort=effort,
                        observed_8s_hero_60px=dict(commands=dict(cmds), projectile_used=proj, frames_with_movement=moved, final_offset_from_start=[o.w(2) - (h.w(2) + 60), o.w(4) - h.w(4)])))
        print('%02X %-13s L%-2d HP%-4d new ops %-2d effort %-6s cmds %s proj %s' % (mid, nm[0xCF + mid], m['level'], m['hp'], len(new), effort, dict(cmds), proj))
    json.dump(dict(source='tools/monster_survey.py: 8 s of the real frame loop per id, hero 0 pinned, monster 60 px to its right, seed 1; static numbers from tools/aidis.py', monsters=res), open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()

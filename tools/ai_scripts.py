"""Write data/ai_scripts.json: for every object id 0-0x7F the script entry pointer (object-table entry bytes 9-10, script base ROM 0x104F15)
and, from a recursive walk of the bytecode with the lengths of tools/aidis.py, the opcodes used and the CALL targets reached.
usage: ai_scripts.py ROM OUT.json
Only numbers are written. The walk is static (read, not executed) and follows both branches of every conditional op."""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, aidis

def walk(d, pc0):
    seen = {}; ops = set(); calls = set(); st = [pc0]
    while st:
        p = st.pop()
        while p not in seen:
            ln, t, tg, ft = aidis.decode(d, p)
            seen[p] = ln; ops.add(d[aidis.BASE + p])
            if t.startswith('CALL'): calls.add(tg)
            if tg is not None: st.append(tg)
            if not ft: break
            p += ln
    return sorted(ops), sorted(calls), len(seen)

def main():
    d = romio.rom_from_argv(); out = sys.argv[1]
    ents = []
    for i in range(0x80):
        pc = struct.unpack_from('<H', d, 0x100000 + i * 16 + 9)[0]
        if i >= 0x57:
            ents.append(dict(id=i, entry=pc, note='boss id: entry is filler or unused (see docs)')); continue
        ops, calls, n = walk(d, pc)
        ents.append(dict(id=i, entry=pc, instructions=n, ops=ops, calls=calls))
    json.dump(dict(source='object table ROM 0x100000 + id*16 (bytes 9-10 = entry), script base ROM 0x104F15; static walk by tools/aidis.py', entries=ents),
              open(out, 'w'))

if __name__ == '__main__':
    main()

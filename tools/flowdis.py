"""Recursive-descent 65816 disassembler with M/X flag tracking (no ROM bytes are stored; output goes to stdout / a scratch file).
usage: flowdis.py ROM OUTFILE [extra seed addresses, hex 24-bit]...
Seeds: reset vector, every JSL/JSR/JMP/JML target found while tracing, plus the extra seeds given.
Output lines: 'AAAAAA: bytes   mnemonic operand   ; m=.. x=..'. Use grep on the output to navigate."""
import sys, struct, romio, disasm65 as D
def run(rom, seeds):
    D.set_rom(rom)
    ops = D.ops
    seen = {}      # addr -> (m,x)
    out = {}
    stack = [s if isinstance(s, tuple) else (s, 1, 1) for s in seeds]
    def sz_of(mode, m, x):
        if mode == '#': return 1 if m else 2
        if mode == '#X': return 1 if x else 2
        if mode in ('imp', 'A'): return 0
        if mode in ('dp','dp,X','dp,Y','(dp)','(dp),Y','[dp]','[dp],Y','(dp,X)','sr,S','(sr,S),Y','rel','b'): return 1
        if mode in ('abs','abs,X','abs,Y','(abs)','(abs,X)','[abs]','rel16','mv'): return 2
        return 3
    while stack:
        a, m, x = stack.pop()
        while True:
            a &= 0xFFFFFF
            if (a & 0x3FFFFF) >= len(rom) or (a >> 16) < 0xC0: break
            if a in seen: break
            seen[a] = (m, x)
            o = a & 0x3FFFFF; op = rom[o]
            if op not in ops: break
            nm, mode = ops[op]; sz = sz_of(mode, m, x)
            v = int.from_bytes(rom[o+1:o+1+sz], 'little')
            out[a] = (nm, mode, sz, v, m, x)
            nxt = a + 1 + sz
            if nm == 'REP':
                if v & 0x20: m = 0
                if v & 0x10: x = 0
            elif nm == 'SEP':
                if v & 0x20: m = 1
                if v & 0x10: x = 1
            if mode == 'rel':
                t = (a & 0xFF0000) | ((nxt + (v-256 if v > 127 else v)) & 0xFFFF)
                stack.append((t, m, x))
                if nm == 'BRA': break
            elif mode == 'rel16':
                t = (a & 0xFF0000) | ((nxt + (v-65536 if v > 32767 else v)) & 0xFFFF)
                if nm == 'BRL': a = t; continue
            elif nm == 'JSR' and mode == 'abs': stack.append(((a & 0xFF0000) | v, m, x))
            elif nm == 'JSL': stack.append((v, m, x))
            elif nm == 'JMP' and mode == 'abs': a = (a & 0xFF0000) | v; continue
            elif nm == 'JML': a = v; continue
            elif nm in ('RTS', 'RTL', 'RTI', 'JMP', 'BRK', 'STP'): break
            a = nxt
    return out
def fmt(a, e):
    nm, mode, sz, v, m, x = e
    if mode == 'imp': s = ''
    elif mode == 'A': s = 'A'
    elif mode == 'mv': s = '$%02X,$%02X' % (v & 0xFF, v >> 8)
    else:
        f = ('$%02X', '$%04X', '$%06X')[sz-1] % v if sz else ''
        if mode == 'rel': s = '$%04X' % (((a & 0xFFFF) + 2 + (v-256 if v > 127 else v)) & 0xFFFF)
        elif mode == 'rel16': s = '$%04X' % (((a & 0xFFFF) + 3 + (v-65536 if v > 32767 else v)) & 0xFFFF)
        elif mode in ('#', '#X', 'b'): s = '#' + f
        else: s = mode.replace('dp', f).replace('abs', f).replace('long', f).replace('sr', f)
    return '%06X: %-4s %-14s ; m%d x%d' % (a, nm, s, m, x)
if __name__ == '__main__':
    rom = romio.rom_from_argv(); outp = sys.argv[1]
    seeds = [int.from_bytes(rom[0xFFFC:0xFFFE], 'little') | 0xC00000]
    seeds += [(int(s.split(':')[0], 16), int(s.split(':')[1][0]), int(s.split(':')[1][1])) if ':' in s else int(s, 16) for s in sys.argv[2:] if s != '--auto']   # ADDR (m=1,x=1) -- use ADDR:MX for other flags, e.g. C0514B:10 = m1 x0
    auto = []
    if '--auto' in sys.argv:   # also seed every JSL target (banks C0-C3) found by a byte scan; noisy but widens coverage
        for i in range(0, 0x200000 - 3):
            if rom[i] == 0x22 and 0xC0 <= rom[i+3] <= 0xD3 and (rom[i+3] in (0xC0,0xC1,0xC2,0xC3,0xC7,0xC8,0xD0,0xD3)):
                auto.append((int.from_bytes(rom[i+1:i+4], 'little'), 1, 0))
        seeds = auto + seeds     # explicit seeds are popped first, so they win overlaps
    out = run(rom, seeds)
    with open(outp, 'w') as f:
        for a in sorted(out): f.write(fmt(a, out[a]) + '\n')
    print(len(out), 'instructions')

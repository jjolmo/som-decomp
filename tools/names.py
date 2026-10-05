"""Decode the in-ROM name blocks (event ids 0x800-0x94E, text table at file 0xA0000) for LOCAL display only (nothing is stored in the repo).
Block layout as documented by the SecretOfManaRandomizer project (NamesOfThings.cs): spells 0x00, elements 0x2A, weapons 0x32, armors 0x7A, consumables 0xBA, menu 0xC6, enemies 0xCF.
usage: names.py ROM            (prints the blocks)       library: names.load(rom) -> list of 335 strings"""
import struct, sys, romio
def ch(s):
    if s == 0x7F: return '\n'
    if s == 0x80: return ' '
    if 0x81 <= s <= 0x9A: return chr(s - 0x20)
    if 0x9B <= s <= 0xB4: return chr(s - 0x5A)
    if 0xB5 <= s <= 0xBE: return chr(s - 0x85)
    return {0xBF: '.', 0xC0: ',', 0xC1: '/', 0xC2: "'", 0xC3: '[', 0xC4: ']', 0xC5: ':'}.get(s, '~')
def load(d):
    out = []
    for ev in range(0x800, 0x94F):
        o = struct.unpack_from('<H', d, 0xA0000 + (ev - 0x400) * 2)[0] + 0xA0000
        s = ''
        while d[o] != 0: s += ch(d[o]); o += 1
        out.append(s)
    return out
START = dict(spells=0, elements=0x2A, weapons=0x32, armors=0x7A, consumables=0xBA, menu=0xC6, enemies=0xCF)
if __name__ == '__main__':
    d = romio.rom_from_argv(); n = load(d)
    for k, v in START.items():
        print(k, [(i - v, n[i]) for i in range(v, min(len(n), v + 0x80)) if i < len(n)][:100] if k != 'menu' else '')

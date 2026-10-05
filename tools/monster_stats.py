"""Print the 29-byte monster stat record (ROM 0x101C00 + id*29) and the 16-byte object-table entry (ROM 0x100000 + id*16).
usage: monster_stats.py ROM_PATH ID_HEX"""
import struct, romio
d = romio.rom_from_argv()
i = int(__import__('sys').argv[1], 16)
r = d[0x101C00 + i*29: 0x101C00 + i*29 + 29]
print('stat record:', r.hex(' '))
print(f'level={r[0]} hp={struct.unpack_from("<H", r, 1)[0]} mp={r[3]} str={r[4]} agi={r[5]} int={r[6]} wis={r[7]} '
      f'eva={r[8]} def={struct.unpack_from("<H", r, 9)[0]} mev={r[11]} mdef={struct.unpack_from("<H", r, 12)[0]} '
      f'type=0x{r[14]:02X} element=0x{r[15]:02X}')
e = d[0x100000 + i*16: 0x100000 + i*16 + 16]
print('object entry:', e.hex(' '), f'AI script PC=0x{struct.unpack_from("<H", e, 9)[0]:04X} (script base ROM 0x104F15)')

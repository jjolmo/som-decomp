"""Print the Dark Lich definition decoded from the ROM: boss loader entry, object record, state sequences, chooser tables.
usage: lich_dump.py ROM"""
import struct, romio, statescript
d = romio.rom_from_argv()
BOSS = 0x79
a1 = struct.unpack_from('<H', d, 0x200EE + 2*(BOSS-0x54))[0]; a2 = struct.unpack_from('<H', d, 0x20146 + 2*(BOSS-0x54))[0]
print('boss loader scripts (bank C1): A=%04X B=%04X' % (a1, a2))
rec = 0x2E82E
w = lambda o: struct.unpack_from('<H', d, rec+o)[0]
print('object record idx 8 @ C2:E82E: flags=%04X B4(init)=%04X B6(chooser)=%04X B8(action)=%04X BA(hurt)=%04X BC(first seq)=%04X BE(default seq)=%04X state-table=%04X' % (w(0), w(4), w(6), w(8), w(10), w(12), w(14), w(16)))
def seq(p):
    out = []
    while d[0x20000+p] != 0xFF: out.append(d[0x20000+p]); p += 1
    return out
print('state sequences (C2:E848..E895):')
p = 0xE848
while p < 0xE896:
    s = seq(p); print('  %04X: %s' % (p, ' '.join('%02X' % x for x in s))); p += len(s)+1
def tbl(base, n, name):
    print('  %-8s' % name, ' '.join('%04X' % struct.unpack_from('<H', d, base+2*i)[0] for i in range(n)))
print('selection tables (bank DC):')
tbl(0x1CE461, 4, 'E461 near/face (4 dirs)'); tbl(0x1CE469, 4, 'E469 far/walk (4 dirs)')
tbl(0x1CE479, 4, 'E479 hands, bit15 clear, by dir'); tbl(0x1CE471, 2, 'E471 hands random (bit15 clear)')
tbl(0x1CE481, 4, 'E481 hands, bit15 set, by dir'); tbl(0x1CE475, 2, 'E475 hands random (bit15 set)')
tbl(0x1CE489, 7, 'E489 spells (rand 0..6)'); tbl(0x1CE497, 9, 'E497 projectile attacks (rand 0..8)')
print('state scripts (table C2:E896):')
for i in range(0x28):
    a = struct.unpack_from('<H', d, 0x2E896+2*i)[0]
    print('--- state %02X @ %04X' % (i, a)); print(statescript.decode(d, a))

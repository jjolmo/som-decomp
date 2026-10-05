"""Decoder for the C2 per-object state scripts (interpreter $C2:3799, opcode table $C2:37CC). Operand sizes come from the handler table; op names are plain labels.
usage: statescript.py ROM HEXADDR   (address inside bank C2, e.g. E8F6)  /  statescript.py ROM table HEXADDR COUNT"""
import sys, struct, romio
OPS = {0:('ANIM',1),1:('FRAMES',6),2:('SPEED90',1),3:('F48',1),4:('F4A',1),5:('DURATION14',1),6:('SET98_40',0),7:('SET98_80',0),
       8:('TOG98_40',0),9:('TOG98_80',0),0xA:('CLR98_40',0),0xB:('CLR98_80',0),0xC:('SET_E1E3',1),0xD:('PAL',1),0xE:('SPELL',1),
       0xF:('SPAWN',3,'bytes'),0x10:('CALLNATIVE',1),0x11:('STORE',2),0x12:('C18003',1),0x13:('C0_006C',1),0x14:('CALL30E3',1),0x15:('JUMP',1)}
def decode(d, addr):
    p = 0x20000 + addr; out = []
    while True:
        op = d[p]
        if op == 0xFF: out.append('%04X: END' % (p-0x20000)); break
        info = OPS.get(op)
        if not info: out.append('%04X: ?? %02X' % (p-0x20000, op)); break
        name, n = info[0], info[1]
        if len(info) > 2:
            args = list(d[p+1:p+1+n]); ln = 1+n
            out.append('%04X: %-10s %s' % (p-0x20000, name, ' '.join('%02X'%a for a in args)))
        else:
            args = [struct.unpack_from('<H', d, p+1+2*i)[0] for i in range(n)]; ln = 1+2*n
            out.append('%04X: %-10s %s' % (p-0x20000, name, ' '.join('%04X'%a for a in args)))
        p += ln
        if name == 'JUMP': break
    return '\n'.join(out)
if __name__ == '__main__':
    d = romio.rom_from_argv()
    if sys.argv[1] == 'table':
        t = int(sys.argv[2], 16); n = int(sys.argv[3])
        for i in range(n):
            a = struct.unpack_from('<H', d, 0x20000+t+2*i)[0]
            print('--- state %02X @ %04X' % (i, a)); print(decode(d, a))
    else:
        print(decode(d, int(sys.argv[1], 16)))

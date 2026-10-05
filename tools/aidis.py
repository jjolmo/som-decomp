"""AI bytecode lister. usage: aidis.py ROM HEXPC [HEXLEN] [--text]   (PC relative to ROM 0x104F15)
Lengths verified by reading handler code ($C1:2257 table) and by running handlers in cpu65816. With --text the opcodes whose handlers were
executed by tools/ai_ops.py (the ones the Rabite script uses) get a one-line description; the others are printed as opNN.
Conditional ops are written IFxx args -> target: the jump is taken when the condition described for the op holds."""
import sys, romio
BASE = 0x104F15
N0 = set([0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x31,0x32,0x33,0x34,0x35,0x37,0x38,0x39,0x3A,0x3B,0x3D,0x3E,0x3F,0x40,0x41,0x43,0x44,0x45,0x46,0x47,
          0x49,0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x57,0x58,0x59,0x5A,0x5B,0x5C,0x62,0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6A,0x6B,
          0x6C,0x6D,0x6E,0x6F,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x78,0x79,0x7A,0x7B,0x7C,0x9D,0x9E,0xD6,0xF6,0x01])
N1 = set(list(range(0x0A,0x1A)) + [0x36,0x3C,0x42,0x48,0x5F,0x60,0xF5,0xF2])
N3 = set([0x2D,0x2E,0x2F,0x30])
N4 = set([0xBA,0xBB,0xBC,0xBD])
FIX = {}
for o in list(range(0x1A,0x25))+[0x5D,0x5E,0x61,0x9F,0xFB,0xFC,0xF3,0xF4,0xDF,0xE1,0xE8,0xEC,0xEE,0x00]+list(range(0xA0,0xBA))+list(range(0xC0,0xD9)): FIX[o]=1
for o in range(0x25,0x2D): FIX[o]=2
for o in (0xE2,0xED,0xF0,0xF1,0xF9,0xFA): FIX[o]=2
for o in (0xE3,0xE4,0xE5,0xE6,0xE7,0xE9,0xEA,0xEB,0xEF,0xF7,0xFD,0xFE,0xBE,0xBF,0xFF): FIX[o]=3
for o in (0xDA,0xDB,0xDC,0xE0): FIX[o]=4
def decode(d, pc):
    """returns (length, text, target_or_None, falls_through)"""
    op = d[BASE+pc]; b = d[BASE+pc+1:BASE+pc+8]
    if op in FIX:
        n = FIX[op]
        args = ' '.join('%02X'%x for x in d[BASE+pc+1:BASE+pc+n])
        if op == 0xFF: return n, 'CALL %04X' % (b[0]<<8|b[1]), b[0]<<8|b[1], True
        if op == 0x00: return n, 'RET', None, False
        return n, 'op%02X %s' % (op, args), None, True
    n = 0 if op in N0 else 1 if op in N1 else 3 if op in N3 else 4 if op in N4 else None
    if n is None: return 1, 'op%02X ???' % op, None, True
    off = BASE+pc+1+n
    fb = d[off]
    if fb & 0x80:
        ol = 1; v = fb & 0x7F
        if v & 0x40: v -= 0x80
    else:
        ol = 2; v = ((fb<<8)|d[off+1])
        if v & 0x4000: v |= 0x8000
        if v & 0x8000: v -= 0x10000
    ln = 1+n+ol
    tgt = (pc+ln+v) & 0xFFFF
    args = ' '.join('%02X'%x for x in d[BASE+pc+1:BASE+pc+1+n])
    kind = 'JMP' if op==1 else 'IF%02X' % op
    return ln, '%s %s-> %04X' % (kind, args+' ' if args else '', tgt), tgt, op != 1
DESC = {
    0x00: 'return (pops the address pushed by CALL; at depth 0 the error handler restarts the script at entry+3)',
    0x01: 'jump',
    0x05: 'jump if var3 != 0', 0x09: 'jump if var3 == 0', 0x0D: 'jump if var3 != arg',
    0x2C: 'var3 = random 0..arg (inclusive, uniform)',
    0x2F: 'jump if byte(objref arg1, offset arg2 + 0x180) < arg3', 0x30: 'jump if byte(objref arg1, offset arg2 + 0x180) > arg3',
    0xBD: 'jump if word(objref arg1, offset arg2 + 0x180) > arg3 (word)',
    0x31: 'jump if no valid hero within 16 px', 0x49: 'jump if no valid hero within 32 px', 0x4E: 'jump if no valid hero within 48 px',
    0x53: 'jump if no valid hero within 64 px', 0x58: 'jump if no valid hero on screen',
    0x4C: 'jump unless the current target is valid and within 32 px', 0x51: 'jump unless the current target is valid and within 48 px',
    0x56: 'jump unless the current target is valid and within 64 px',
    0xA5: 'target = first valid hero within 16 px (FF if none)', 0xB1: 'target = first valid hero within 32 px', 0xB4: 'target = first valid hero within 48 px',
    0xB7: 'target = first valid hero within 64 px', 0x5D: 'target = first valid hero farther than 64 px',
    0x9F: 'save own screen position', 0x9D: 'jump if own screen position equals the saved one',
    0xE0: 'hop: command C1, direction code arg1, animation arg2, flag arg3; yield',
    0xE2: 'pose: command 40, animation arg1; yield',
    0xE3: 'command C1 in the current facing direction when the actor is not moving (else from the velocity bytes), animation arg1, flag arg2; yield',
    0xE4: 'if target valid: command C1 toward the target (primary direction), animation arg1, flag arg2; yield',
    0xFD: 'if target valid: command C1 toward the target (alternate direction), animation arg1, flag arg2; yield',
    0xE6: 'if target valid: command C1 away from the target (primary direction); yield',
    0xFE: 'if target valid: command C1 away from the target (alternate direction); yield',
    0xE8: 'attack swing (command 02) if the cooldown gauge obj+0x1ED is 0, otherwise no-op',
    0xFF: 'call (pushes the return address, depth limit 16)',
}
def listing(d, pc, n, text=False):
    p = pc; out = []
    while p < pc+n:
        ln, t, tg, _ = decode(d, p)
        raw = ' '.join('%02X'%x for x in d[BASE+p:BASE+p+ln])
        extra = ('   ; ' + DESC[d[BASE+p]]) if text and d[BASE+p] in DESC else ''
        out.append('%04X: %-18s %s%s' % (p, raw, t, extra)); p += ln
    return '\n'.join(out)
if __name__ == '__main__':
    d = romio.rom_from_argv()
    text = '--text' in sys.argv
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    print(listing(d, int(a[0],16), int(a[1],16) if len(a)>1 else 0x40, text))

"""Decode the per-object animation scripts of the C2 engine (player $C2:13EB, op table $C2:142E, script pointers $DB:F9A8 -> bank C1).
usage: mb_anim.py ROM ID[,ID...]      (ids in hex, e.g. 111,112)
A script is a list of 3-byte frames (word, duration in object ticks) and ops (odd first byte, argument counts measured by running the handlers).
Frame words are printed raw; ops are printed as 'op XX' with their raw arguments."""
import sys, struct, romio

ARGS = {0x01: 0, 0x03: 0, 0x05: 0, 0x07: 0, 0x09: 0, 0x0B: 0, 0x0D: 2, 0x0F: 0, 0x11: 2, 0x13: 4, 0x15: 2, 0x17: 2, 0x19: 1, 0x1B: 0, 0x1D: 1,
        0x1F: 2, 0x21: 2, 0x23: 3, 0x25: 4, 0x27: 0, 0x29: 0, 0x2B: 0, 0x2D: 2, 0x2F: 2, 0x31: 2, 0x33: 6}
ENDS = (0x11, 0x15, 0x1B)       # jump / switch script / restart end linear reading


def script(d, sid):
    return 0x10000 + struct.unpack_from('<H', d, 0x1BF9A8 + 2 * sid)[0]      # table $DB:F9A8, scripts in bank C1


def decode(d, sid, limit=400):
    base = script(d, sid); i = 0; out = []; seen = set()
    while len(out) < limit:
        if i in seen: break
        seen.add(i)
        b = d[base + i]
        if b & 1:
            n = ARGS.get(b)
            if n is None:
                out.append('%03X: op %02X ?' % (i, b)); break
            a = d[base + i + 1: base + i + 1 + n]
            out.append('%03X: op %02X %s' % (i, b, a.hex(' ')))
            i += 1 + n
            if b in ENDS:
                if b == 0x11: out[-1] += '   (jump to %03X)' % struct.unpack_from('<H', d, base + i - 2)[0]
                break
        else:
            w = struct.unpack_from('<H', d, base + i)[0]
            out.append('%03X: frame %04X dur %d' % (i, w, d[base + i + 2]))
            i += 3
    return out


if __name__ == '__main__':
    d = romio.rom_from_argv()
    for t in sys.argv[1].split(','):
        sid = int(t, 16)
        print('--- script %03X @ C1:%04X' % (sid, struct.unpack_from('<H', d, 0x1BF9A8 + 2 * sid)[0]))
        print('\n'.join(decode(d, sid)))

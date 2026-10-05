"""Render the sound effects of the game from the ROM (no emulator of the whole console needed).

usage: sfx_extract.py ROM OUTDIR [--ids all|0x99,0x32,...] [--pan 0x77] [--secs 30] [--state STATE]
                      [--keep-gain] [--dump-spc ID] [--selftest]

How it works (details in docs/audio.md):
  1. The sound driver, the effect sequence table and the BRR samples are read from the ROM blocks that the 65816 uploads
     to the APU RAM at boot ($C3:0008 pointers, $C3:0014 destinations). They are placed at their destinations in a 64 KiB
     image: this is the APU RAM exactly as it is after the boot upload.
  2. A .spc file is built from that image with the SPC700 entry point 0x0200 (where the boot upload jumps). The driver
     initialises the DSP itself. A 40-byte stub in unused RAM injects one "effect request" (APU port 0 = 2, ports 1-3 =
     id, param, pan) at the first pass of the driver main loop, by jumping into the driver's own handler (0x0E10).
  3. The .spc is run by libgme (ctypes; libgme.so.0 must be installed) at 32000 Hz and the stereo output is written
     as 16-bit WAV, trimmed of trailing silence. libgme multiplies the DSP output by 1.4 (measured with --selftest), which
     is divided out unless --keep-gain is given.
OUTDIR must be outside the repository (the files are game audio and must never be committed).
"""
import sys, os, json, struct, wave, ctypes
from array import array

import romio
import spc700

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SR = 32000
GME_GAIN = 1.4
STUB = 0x2800
SILENCE = 2            # |sample| <= 2 counts as silence (libgme scale)
LOOP_WINDOW_S = 5      # sound inside the last 5 s of the render = looping or continuous effect
LOOP_KEEP_S = 10       # looping effects are written truncated to this length


# ---------------------------------------------------------------- APU RAM from the ROM
def boot_ram(rom):
    """APU RAM after the boot upload: the six blocks listed at $C3:0008 (pointers) and $C3:0014 (destinations)."""
    base = 0x030000
    ram = bytearray(65536)
    blocks = []
    for i in range(6):
        p = int.from_bytes(rom[base + 8 + 2 * i:base + 10 + 2 * i], 'little')
        d = int.from_bytes(rom[base + 0x14 + 2 * i:base + 0x16 + 2 * i], 'little')
        n = int.from_bytes(rom[base + p:base + p + 2], 'little')
        assert d + n <= 0x10000
        ram[d:d + n] = rom[base + p + 2:base + p + 2 + n]
        blocks.append((d, n))
    return ram, blocks


def state_ram(path):
    """APU RAM of a ZSNES v143 save state (64 KiB at file offset 0x30C13, right after WRAM and VRAM)."""
    d = open(path, 'rb').read()
    assert d.startswith(b'ZSNES Save State File V143')
    return bytearray(d[0x30C13:0x40C13])


def check_driver(ram):
    """The stub depends on these driver addresses: refuse to run on anything that does not look like the driver."""
    want = {0x200: 'CLRP', 0x201: 'DI', 0x279: 'CALL !$0CAF', 0xE10: 'MOV $2C,$B5', 0xEF6: 'MOV A,X'}
    for a, text in want.items():
        got = spc700.disasm_one(ram, a)[1]
        assert got == text, 'unexpected driver code at 0x%04X: %s (expected %s)' % (a, got, text)
    assert not any(ram[STUB:STUB + 0x40]), 'stub area is not free'


def with_request(ram, cmd, p1, p2, p3):
    """Return a copy of ram that, at the first main-loop pass, runs the driver's handler for the request."""
    r = bytearray(ram)
    c = bytearray()
    for i in range(3):                                         # put the original CALL at 0x0279 back (it is run once)
        c += bytes([0xE8, ram[0x279 + i], 0xC5, (0x279 + i) & 255, (0x279 + i) >> 8])   # MOV A,#b ; MOV !addr,A
    if cmd == 2:                                               # effect: $B4..$B7 = ports 0..3, then JMP !$0E10
        c += bytes([0x8F, 2, 0xB4, 0x8F, p1, 0xB5, 0x8F, p2, 0xB6, 0x8F, p3, 0xB7, 0x5F, 0x10, 0x0E])
    else:                                                      # built-in sequence 0x10-0x1F: X = cmd, JMP !$0EF6
        c += bytes([0x8F, cmd, 0xB4, 0xCD, cmd, 0x5F, 0xF6, 0x0E])
    r[STUB:STUB + len(c)] = c
    r[0x279:0x27C] = bytes([0x3F, STUB & 255, STUB >> 8])      # CALL !stub
    return r


def make_spc(ram, pc=0x200):
    h = bytearray(0x10200)
    h[:0x21] = b'SNES-SPC700 Sound File Data v0.30'
    h[0x21:0x24] = bytes([26, 26, 27])
    h[0x24] = 30
    h[0x25:0x27] = struct.pack('<H', pc)
    h[0x2B] = 0xEF
    h[0x100:0x10100] = ram
    h[0x100 + 0xF1] = 0                                        # IPL ROM off
    return bytes(h)


# ---------------------------------------------------------------- libgme
_g = None


def gme():
    global _g
    if _g is None:
        g = ctypes.CDLL('libgme.so.0')
        g.gme_open_data.argtypes = [ctypes.c_char_p, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int]
        g.gme_open_data.restype = ctypes.c_char_p
        g.gme_start_track.argtypes = [ctypes.c_void_p, ctypes.c_int]
        g.gme_start_track.restype = ctypes.c_char_p
        g.gme_play.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        g.gme_play.restype = ctypes.c_char_p
        g.gme_delete.argtypes = [ctypes.c_void_p]
        g.gme_mute_voices.argtypes = [ctypes.c_void_p, ctypes.c_int]
        _g = g
    return _g


def render(spc, secs, mute=0):
    """Interleaved stereo 16-bit samples at 32000 Hz, exactly as libgme produces them (gain 1.4 included)."""
    g = gme()
    emu = ctypes.c_void_p()
    e = g.gme_open_data(spc, len(spc), ctypes.byref(emu), SR)
    assert not e, e
    if mute:
        g.gme_mute_voices(emu, mute)           # libgme only honours the mask when it is set before start_track
    e = g.gme_start_track(emu, 0)
    assert not e, e
    n = int(secs * SR) * 2
    buf = array('h', bytes(2 * n))
    addr, _ = buf.buffer_info()
    e = g.gme_play(emu, n, ctypes.c_void_p(addr))
    assert not e, e
    g.gme_delete(emu)
    return buf


def peak(buf):
    return max(max(buf), -min(buf)) if len(buf) else 0


def last_sound(buf, thr=SILENCE, chunk=4096):
    """Index (in frames) just after the last frame with |sample| > thr, or 0."""
    n = len(buf)
    i = n
    while i > 0:
        j = max(0, i - chunk)
        seg = buf[j:i]
        if max(seg) > thr or -min(seg) > thr:
            k = i - 1
            while not (buf[k] > thr or -buf[k] > thr):
                k -= 1
            return k // 2 + 1
        i = j
    return 0


def first_sound(buf, thr=SILENCE, chunk=4096):
    n = len(buf)
    for j in range(0, n, chunk):
        seg = buf[j:j + chunk]
        if max(seg) > thr or -min(seg) > thr:
            k = j
            while not (buf[k] > thr or -buf[k] > thr):
                k += 1
            return k // 2
    return None


def ungain(buf):
    out = array('h', bytes(2 * len(buf)))
    for i, v in enumerate(buf):
        x = int(round(v / GME_GAIN))
        out[i] = 32767 if x > 32767 else -32768 if x < -32768 else x
    return out


def write_wav(path, buf):
    w = wave.open(path, 'wb')
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(buf.tobytes())
    w.close()


# ---------------------------------------------------------------- self test of the gain
def selftest():
    """Voice 0 plays a looping BRR block of constant value; the DSP output is computed by hand and compared."""
    for rng in (6, 8, 10):
        ram = bytearray(65536)
        regs = [(0x6C, 0x20), (0x5D, 0x10), (0x0C, 0x7F), (0x1C, 0x7F), (0x2C, 0), (0x3C, 0), (0x4D, 0), (0x3D, 0),
                (0x2D, 0), (0x00, 0x7F), (0x01, 0x7F), (0x02, 0), (0x03, 0x10), (0x04, 0), (0x05, 0), (0x06, 0),
                (0x07, 0x7F), (0x4C, 1)]
        code = bytearray()
        for r, v in regs:
            code += bytes([0x8F, r, 0xF2, 0x8F, v, 0xF3])
        code += bytes([0x2F, 0xFE])
        ram[0x200:0x200 + len(code)] = code
        ram[0x1000:0x1004] = bytes([0x00, 0x20, 0x00, 0x20])
        ram[0x2000] = (rng << 4) | 3
        ram[0x2001:0x2009] = bytes([0x77] * 8)
        s = render(make_spc(bytes(ram)), 2)
        sample = 7 << rng                       # BRR filter 0: nibble << range
        exp = sample * 0x7F0 >> 11              # GAIN direct 0x7F -> envelope 0x7F0
        exp = exp * 0x7F >> 7                   # voice volume
        exp = exp * 0x7F >> 7                   # master volume
        print('range %2d: libgme %6d, hand-computed DSP output %6d, ratio %.4f' % (rng, s[40000], exp, s[40000] / exp))


# ---------------------------------------------------------------- main
def entry_of(ram, i):
    e = ram[0x2C00 + 4 * i:0x2C00 + 4 * i + 4]
    p0 = e[0] | e[1] << 8
    p1 = e[2] | e[3] << 8
    return p0, p1


def tracks_of(ram, i):
    """The driver (0x0E28-0x0E4B) uses a pointer when its high byte is non-zero."""
    p0, p1 = entry_of(ram, i)
    return int(p0 >> 8 != 0) + int(p1 >> 8 != 0)


def render_id(ram, cmd, p1, p2, p3, secs):
    return render(make_spc(bytes(with_request(ram, cmd, p1, p2, p3))), secs)


def analyse(ram, cmd, p1, p2, p3, secs, keep_gain):
    buf = render_id(ram, cmd, p1, p2, p3, secs)
    end = last_sound(buf)
    info = {'audible': end > 0}
    if not end:
        return info, None
    total = len(buf) // 2
    looping = end > total - LOOP_WINDOW_S * SR
    if looping:
        end = min(end, LOOP_KEEP_S * SR)
    out = buf[:2 * end]
    on = first_sound(out)
    left, right = out[0::2], out[1::2]
    voices = []
    for v in range(8):
        solo = render(make_spc(bytes(with_request(ram, cmd, p1, p2, p3))), min(end / SR + 0.1, secs), 0xFF ^ (1 << v))
        if peak(solo) > SILENCE:
            voices.append(v)
    info.update(duration_s=round(end / SR, 4), onset_ms=round(on * 1000 / SR, 1), looping=looping,
                peak=peak(out) if keep_gain else int(round(peak(out) / GME_GAIN)),
                peak_left=max(max(left), -min(left)), peak_right=max(max(right), -min(right)), voices=voices)
    if looping:
        info['truncated_at_s'] = LOOP_KEEP_S
    if not keep_gain:
        info['peak_left'] = int(round(info['peak_left'] / GME_GAIN))
        info['peak_right'] = int(round(info['peak_right'] / GME_GAIN))
        out = ungain(out)
    return info, out


def main():
    argv = sys.argv[1:]
    if '--selftest' in argv:
        selftest()
        return
    rom = romio.rom_from_argv()
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    outdir = os.path.realpath(args.pop(0))
    if outdir == REPO or outdir.startswith(REPO + os.sep):
        sys.exit('refusing to write game audio inside the repository: ' + outdir)

    def opt(name, default=None):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return v
        return default
    ids_arg = opt('--ids', 'all')
    pan = int(opt('--pan', '0x77'), 0)
    secs = float(opt('--secs', '30'))
    state = opt('--state')
    dump = opt('--dump-spc')
    keep_gain = '--keep-gain' in args
    ram, blocks = boot_ram(rom)
    check_driver(ram)
    os.makedirs(outdir, exist_ok=True)
    if dump is not None:
        i = int(dump, 0)
        p = os.path.join(outdir, 'sfx_%02x.spc' % i)
        open(p, 'wb').write(make_spc(bytes(with_request(ram, 2, i, 0, pan))))
        print('wrote', p, '(contains game data: keep it outside the repository)')
        return
    ids = list(range(256)) if ids_arg == 'all' else [int(x, 0) for x in ids_arg.split(',')]
    sram = state_ram(state) if state else None
    index = []
    jobs = [(2, i, 0, pan) for i in ids]
    if ids_arg == 'all':
        jobs += [(c, 0, 0, 0) for c in (0x10, 0x11, 0x12)]        # built-in sequences present in the driver table
    for cmd, i, p2, p3 in jobs:
        if cmd == 2 and i == 0x35:
            p2 = 0x0F                                          # the game requests the hit sound with param 0x0F
            if pan == 0x77:
                p3 = 0x60
        name = 'sfx_%02x' % i if cmd == 2 else 'cmd_%02x' % cmd
        info, out = analyse(ram, cmd, i, p2, p3, secs, keep_gain)
        rec = {'name': name, 'request': {'port0': cmd, 'port1': i, 'port2': p2, 'port3': p3}}
        if cmd == 2:
            rec['tracks'] = tracks_of(ram, i)
        rec.update(info)
        if out is not None:
            write_wav(os.path.join(outdir, name + '.wav'), out)
            rec['file'] = name + '.wav'
        if sram is not None and cmd == 2:
            other = render_id(sram, cmd, i, p2, p3, 4)
            mine = render_id(ram, cmd, i, p2, p3, 4)
            rec['same_as_state_render'] = bytes(other) == bytes(mine)
        index.append(rec)
        print('%-8s %s' % (name, ('%.3f s  peak %5d  voices %s%s' % (rec['duration_s'], rec['peak'], rec['voices'],
                                  '  LOOPING' if rec['looping'] else '')) if rec['audible'] else 'silent'))
    meta = {'sample_rate': SR, 'channels': 2, 'bits': 16, 'gain_divided_out': not keep_gain, 'libgme_gain': GME_GAIN,
            'silence_threshold': SILENCE, 'pan_param': pan, 'render_seconds': secs, 'boot_blocks_dest_len': blocks}
    json.dump({'meta': meta, 'sounds': index}, open(os.path.join(outdir, 'index.json'), 'w'), indent=1)
    lines = ['Sound effect contact sheet (request: port0=2, port1=id, port2=%s, port3=pan 0x%02X)' % ('0', pan), '']
    silent = [r['name'] for r in index if not r['audible']]
    empty = [r['name'] for r in index if not r['audible'] and r.get('tracks') == 0]
    lines.append('%d requests rendered, %d audible, %d silent (%d of them have no sequence in the table).' % (
        len(index), len(index) - len(silent), len(silent), len(empty)))
    lines.append('')
    lines.append('%-8s %-8s %-8s %-6s %-10s %s' % ('name', 'dur (s)', 'peak', 'trk', 'voices', 'notes'))
    for r in index:
        if r['audible']:
            lines.append('%-8s %-8.3f %-8d %-6s %-10s %s' % (r['name'], r['duration_s'], r['peak'], r.get('tracks', '-'),
                         ','.join(map(str, r['voices'])), 'looping (truncated to %d s)' % LOOP_KEEP_S if r['looping'] else ''))
    lines.append('')
    lines.append('SILENT: ' + ' '.join(silent))
    lines.append('  no sequence in the table: ' + ' '.join(empty))
    lines.append('  sequence present but no output: ' + ' '.join(n for n in silent if n not in empty))
    open(os.path.join(outdir, 'contact_sheet.txt'), 'w').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()

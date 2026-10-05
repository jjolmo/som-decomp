"""Event (cutscene) virtual machine of Secret of Mana (USA): static decoder and a harness that runs the game's own code and logs what a script does.

The VM is `$C1:E8D3` (opcode dispatch table `$C1:E922`). An event is started by `JSL $01:E76D` (or `$01:8000`) with the event id in A, and the VM is
stepped by the frame body `$C0:B08C` once every 5 frames (when `$56` == 3 and `$D0` != 0), i.e. at 60.0988 / 5 = 12.02 Hz. See docs/cutscene-engine.md.

usage:
  event_vm.py ROM decode EVENT_ID [EVENT_ID ...]          static listing of events (no execution; text is never printed, only its length)
  event_vm.py ROM table                                     opcode table
  event_vm.py ROM STATE run TRANSITION [FLAG=VAL ...] [leader=N] [frames=N] [out=FILE.json] [quiet=1]
        STATE: a ZSNES v143 state taken during play with the three heroes on a map (any map). The party is sent to the map reached by transition
        TRANSITION (index into the table at `$C8:3000`, what the VM commands 0x18-0x1B use) through the game's own loader; the entry event of that
        map then runs until the VM is idle again. FLAG=VAL sets an event flag nibble (`$7E:CF00 + index`, hex index), e.g. 4E=4.
        leader=N: hero slot (0-2) that the player controls (`$D4`, pad binding `$D9`, `E02C`).
  event_vm.py ROM STATE dark-lich OUT.json [leader=N] [variants=1] [md=1]
        the Dark Lich arena cutscene: transition 340 with flag 4E=4, writes the timeline as JSON; variants=1 re-runs it for every controlled hero and every
        weapon type of the girl (about 5 minutes); md=1 prints the timeline as a markdown table
library: World(rom, state) -> .load_map(n, flags), .set_leader(slot), .frame(), .run_scene(), .events

Everything the game does through the PPU, DMA to VRAM/CGRAM/OAM and the sound CPU is not emulated; DMA to the WRAM port is. The NMI is replaced by the
two NMI duties that change game state (frame counter `$F4`, and the text engine `$C0:0006` called from `$C0:C1E7`). The joypad is injected through
`$4218/$4219`: the A button is tapped for one frame whenever the VM waits for a button press (state `$D0` = 0x83). The map loader is run as the
subroutines `$C0:87C4, BC9B, BC0B, E9F8, BEAA` of `$C0:B03F` (which cannot be entered as such because it resets the stack).
No ROM bytes are stored by this tool: script text is never printed or saved, only ids, addresses and lengths."""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romio, lich_sim, zsnes_state

HZ = 60.0988
AFTER_FRAMES = 360          # frames simulated after the END of the scene to see what the Lich does
VM_TICK = 5                 # frames per VM step

# opcode: (name, length, summary, tag). length None = variable (see summary). [V] executed in this harness, [C] read from the disassembly.
OPS = {
    0x00: ('END', 1, 'end of event: clear $F1 (world unfrozen), $D0, $4E, $3A/$3B, key latches $CC-$CE, bit 7 of the pad bindings $D9-$DB', 'V'),
    0x01: ('NOP', 1, 'advance one byte', 'C'),
    0x02: ('RETURN', 1, 'return from a called event: $D1/$D2/$D3 = $D6/$D7/$D8 (one level only)', 'V'),
    0x03: ('GATHER', 1, 'party gather: $4E = 0x80, state 0x80 (wait until the party AI clears $4E); heroes other than the actor $D4 are stopped first ($C1:CA6C)', 'V'),
    0x04: ('TOGGLE_HERO_VIS', 1, 'toggle bit 7 of obj+0x0E for the three heroes (04 and 05 are identical)', 'C'),
    0x05: ('TOGGLE_HERO_VIS', 1, 'same as 04', 'C'),
    0x06: ('FREEZE', 1, 'set bit 7 of $F1 (the hero input handler returns at once), wait until no hero has a state flag obj+0x60 ($C2:B053), zero the heroes velocities and obj+0x1D', 'V'),
    0x07: ('UNFREEZE', 1, 'clear bit 7 of $F1', 'C'),
    0x08: ('WAIT_IDLE', 1, 'state 0x85: wait until every actor of slots 3.. (and heroes) has its busy flag obj+0x42 clear', 'V'),
    0x09: ('REFRESH_OBJECTS', 1, 'for every object slot 3..: if its map record fails the flag-range test ($C2:C757) remove it, then scan the map records again ($C0:E00C) so that newly valid ones appear', 'V'),
    0x0A: ('CAFF_SET', 1, 'JSL $C0:CAFF with carry set', 'C'),
    0x0B: ('SAVE_TRANS', 1, '$0108 = $010E', 'C'),
    0x0C: ('CLEAR_TRANS', 1, '$0108 = 0', 'C'),
    0x0D: ('MAP_FROM_0108', 1, 'start map change 0x800 + $0108', 'C'),
    0x0E: ('OBJ_FX', 1, 'JSL $C0:004B on the current NPC', 'C'),
    0x0F: ('OBJ_FX', 1, 'JSL $C0:004E on the current NPC', 'C'),
    **{o: ('GOTO_EVENT', 2, 'continue with event (op & 7) * 256 + arg; no return', 'V') for o in range(0x10, 0x18)},
    **{o: ('MAP_CHANGE', 2, 'start map transition (op & 3) * 256 + arg (index into $C8:3000); the script continues in the new map', 'V') for o in range(0x18, 0x1C)},
    0x1C: ('WARP', 2, 'event 0xC00 + arg (table $C6:7A80), then END', 'C'),
    0x1D: ('MAP_CHANGE_D', 2, 'event 0xD00 + (arg & 0x3F) (table $C6:7C80 loader), sets $E3', 'C'),
    0x1E: ('HERO_CMD', 2, 'JSL $C0:0051 with A = arg', 'C'),
    0x1F: ('PARTY_CMD', 2, 'arg 0-2 hero init, 3-4 set mode, 6 JSL $C0:000C, 7 JML $00:8004, 8-0xB JSL $C0:005A, 0xC, 0x10, other', 'C'),
    **{o: ('CALL_EVENT', 2, 'call event (op & 7) * 256 + arg, return address kept in $D6-$D8 (one level)', 'V') for o in range(0x20, 0x28)},
    0x28: ('WAIT', 2, 'arg 0: wait for a button (state 0x83, any of A X L R B Y); arg n: wait n VM ticks (state 0x82, $4F = n, decremented each tick)', 'V'),
    0x29: ('FLAG_INC', 2, 'event flag nibble $CF00+arg: +1 (capped at 15); arg 0 is special', 'V'),
    0x2A: ('FLAG_DEC', 2, 'event flag nibble $CF00+arg: -1 (floored at 0)', 'V'),
    0x2B: ('ACTOR_CLONE', 2, 'object slot (arg & 15) is made active at the position of object $3A with obj+0x0B/0x4C/0x8E copied from $D4 and the facing reversed', 'C'),
    0x2C: ('ACTOR_DELETE', 2, 'remove actor in slot (arg & 15) (obj+0 = 0x80), release its pad binding', 'C'),
    0x2D: ('SCREEN', None, 'arg 0: start flash (colour math alternates every frame, bit 2 of $E2); arg 1: end flash; 2/3/4 set $49 = 0xE0/0x60/0; '
           '5, 6, 0x80-0x8F: palette fade (length 4: + word $010C); 7: fade stop; 8: camera re-centre on $D4 and wait ($E2 bit 3, state 0x86)', 'V'),
    0x2E: ('ACTOR_FX', 2, 'JSL $C0:0048 with Y = arg on the current NPC', 'C'),
    0x2F: ('HERO_REFILL', 2, 'copy obj+0x184 to obj+0x182 (arg bit 7 clear) or obj+0x187 to obj+0x186 (bit 7 set) for the hero selected by arg & 0x3F (0 = $D4, 1-3 = hero, more = all three)', 'C'),
    0x30: ('FLAG_SET', 3, 'event flag nibble $CF00+arg = byte 2', 'C'),
    0x31: ('ACTOR_ANIM', 3, 'actor arg: stop it, obj+0x1C = 0x40, obj+0x11 = byte 2 (animation code), obj+0x30 = 0xFF, obj+0x42 = 1 (busy until the animation ends)', 'V'),
    0x32: ('ACTOR_WALK', 3, 'actor arg: obj+0x0A = byte2 & 0x3F frames, direction byte2 >> 6 (0 up, 1 down, 2 right, 3 left), speed 2 px/frame (obj+0x06/07), obj+0x42 = 1; byte2 & 0x3F = 0 stops it', 'V'),
    0x33: ('SET_0600', 3, '$0600 = byte2 * 256 + arg', 'C'),
    0x34: ('ACTOR_ANIM_LOOP', 3, 'like 31 but obj+0x1C = 0x30 and not busy', 'V'),
    0x35: ('CALL_E326', 1, 'JSR $C1:E326', 'C'),
    0x36: ('OBJ_CMD', 3, 'JSL $C0:0057 with X = arg word', 'C'),
    0x37: ('OBJ_CMD', 3, 'same as 36', 'C'),
    0x38: ('IF_ACTOR', 2, 'if the slot of $D4 (= $D5 >> 1) equals arg continue after 2 bytes, else skip the next 2-byte command (total 4)', 'C'),
    0x39: ('SET_FIELD_BYTE', 4, 'actor arg: obj[0x100 + byte2] = byte3', 'C'),
    0x3A: ('SET_WORD_40', 4, 'actor arg: obj+0x40 (word) = bytes 2-3', 'C'),
    0x3B: ('IF_PARTY', 2, 'test on the pad bindings $D9-$DB selected by arg; continue after 2 bytes or skip the next 2-byte command (exact test not decoded)', 'C'),
    0x3C: ('IF_PARTY_SIZE', 2, 'number of leading non-zero pad bindings $D9-$DB == arg: continue after 2 bytes, else skip the next 2-byte command', 'C'),
    0x40: ('SOUND', 5, '$1E00 = arg, $1E01 = byte 2, $1E02/03 = word bytes 3-4, JSL $C3:0004 (cmd 1 = start music $1E01, cmd 2 = sound effect $1E01, other = raw command)', 'V'),
    0x41: ('CAFF_CLEAR', 5, 'JSL $C0:CAFF with carry clear, parameters from bytes 0-4', 'C'),
    0x42: ('IF_FLAG_RANGE', 3, 'flag byte $CF00+arg: lo = byte 2 >> 4, hi = byte 2 & 15; if lo <= value <= hi (whole byte) execute the next 2-byte command, else skip it', 'V'),
    0x43: ('FLAG_OP_WAIT', 3, 'flag nibble operation selected by arg bits 5-7 (replace, or, xor), the command repeats (waits) while the resulting nibble is 0; not executed', 'C'),
    0x49: ('IF_FIELD', 4, 'compare an object field with a value; ops 0x4A-0x4E are the same family (equality, ordering, and, or, xor)', 'C'),
    0x50: ('TEXT', None, 'bytes >= 0x50 up to the first byte < 0x50 are handed to the text engine ($C0:0006, per NMI); 0x57 and 0x59 carry one argument byte; '
           'the VM waits in state 0x81 until the engine has consumed the block, then resumes at the pointer the engine left in $1D01-$1D03', 'V'),
}
OPS[0x48] = ('FLAG_OP_WAIT2', 4, 'like 43 with the flag index taken from byte 3', 'C')
for _o in (0x3D, 0x3E, 0x3F, 0x44, 0x45, 0x46, 0x47, 0x4F): OPS[_o] = ('STALL', 1, 'the handler is a bare RTS: the VM neither advances nor changes state, so the event hangs here', 'C')
for _o in range(0x4A, 0x4F): OPS[_o] = OPS[0x49]
for _o in range(0x51, 0x60): OPS[_o] = OPS[0x50]
EVENT_ID_BANKS = {0xC9: (0x000, 0x3FF), 0xCA: (0x400, 0x7FF)}


def b24(a): return a & 0x3FFFFF


def event_range(rom, ev):
    """(bank, start, end) of an event script: ids 0-0x3FF live in bank C9, 0x400-0x7FF in bank CA (`$C1:E794`)."""
    bank = 0xC9 if ev < 0x400 else 0xCA
    base = b24(bank << 16)
    p = struct.unpack_from('<H', rom, base + 2 * (ev & 0x3FF))[0]
    n = struct.unpack_from('<H', rom, base + 2 * ((ev & 0x3FF) + 1))[0]
    return bank, p, n


def event_of(rom, bank, addr):
    """Event id whose script contains `addr` of `bank`, and the offset inside it (the smallest enclosing range)."""
    base = b24(bank << 16)
    first = 0 if bank == 0xC9 else 0x400
    starts = [struct.unpack_from('<H', rom, base + 2 * i)[0] for i in range(0x400)]
    best = None
    for i, p in enumerate(starts):
        if p <= addr and (best is None or p > starts[best] or (p == starts[best] and i < best)):
            best = i
    return first + best, addr - starts[best]


def op_len(rom, bank, addr):
    """Length in bytes of the VM command at (bank, addr); text blocks run to the first byte < 0x50."""
    o = b24(bank << 16) + addr
    op = rom[o]
    if op >= 0x50:
        n = 0
        while rom[o + n] >= 0x50:
            n += 2 if rom[o + n] in (0x57, 0x59) else 1
        return n
    if op == 0x2D:
        a = rom[o + 1]
        return 4 if a in (5, 6) or 0x80 <= a < 0x90 else 2
    ent = OPS.get(op)
    return ent[1] if ent and ent[1] else 1


def decode_event(rom, ev):
    """Static listing: list of dicts (offset, op, name, decoded params, length). Text blocks give only their length."""
    bank, p, n = event_range(rom, ev)
    out = []
    a = p
    while a < n:
        o = b24(bank << 16) + a
        op = rom[o]
        ln = op_len(rom, bank, a)
        if op >= 0x50:
            out.append(dict(off=a, op='TEXT', name='TEXT', bytes=ln))
        else:
            ent = OPS.get(op)
            out.append(dict(off=a, op='%02X' % op, name=ent[0] if ent else '?', params=op_params(op, bytes(rom[o + 1:o + 5])), bytes=ln))
        a += ln
    return bank, out


def op_params(op, a):
    """Decoded operands of a command as a dict of numbers (`a` = bytes after the opcode byte)."""
    if 0x10 <= op < 0x18 or 0x20 <= op < 0x28: return dict(target_event=(op & 7) << 8 | a[0])
    if 0x18 <= op < 0x1C: return dict(transition=(op & 3) << 8 | a[0])
    if op == 0x28: return dict(ticks=a[0], wait_press=a[0] == 0)
    if op in (0x29, 0x2A): return dict(flag=a[0])
    if op == 0x30: return dict(flag=a[0], value=a[1])
    if op == 0x32: return dict(actor=a[0], direction=('up', 'down', 'right', 'left')[a[1] >> 6], frames=a[1] & 0x3F)
    if op in (0x31, 0x34): return dict(actor=a[0], anim=a[1])
    if op == 0x2D: return dict(arg=a[0])
    if op == 0x40: return dict(cmd=a[0], id=a[1], word=a[2] | a[3] << 8)
    if op == 0x42: return dict(flag=a[0], lo=a[1] >> 4, hi=a[1] & 15)
    return {}


class MapReload(Exception):
    pass


FIELDS = [('x', 0x02, 2), ('y', 0x04, 2), ('face', 0x10, 1), ('anim', 0x11, 1), ('vx', 0x06, 1), ('vy', 0x07, 1), ('state', 0x1C, 1),
          ('busy', 0x42, 1), ('count', 0x0A, 1), ('flags60', 0x60, 1)]


class World(lich_sim.Sim):
    """Whole game frame + map loader + event VM on top of a save state."""
    PAD_A = 0x0080       # $4218 bit of the A button

    def __init__(self, rom, state, seed=None):
        super().__init__(rom, state, rng_index=seed, hero_hits=False, immortal=False)
        c = self.c
        self.rom = rom
        w = c.wram
        w[0x5C] = zsnes_state.load_wram(state)[0x5C]          # lich_sim forces it to 0x80; the boss spawner sets it itself
        self.t = 0                                            # absolute frame counter
        self.phase0 = 0                                       # frame at which $56 was last 0 (a map load restarts the 5-frame cycle)
        self.pad = 0
        self.events = []
        self.vm_ops = []
        self._release = 0
        self.t_scene = 0
        orig = c.hwread
        def hwread(o):
            if o in (0x4210, 0x4212): return 0x80
            if o == 0x4218: return self.pad & 0xFF
            if o == 0x4219: return (self.pad >> 8) & 0xFF
            return orig(o)
        c.hwread = hwread
        self.dma = bytearray(0x80)
        ohw = c.hwwrite
        def hwwrite(o, v):
            if 0x4300 <= o < 0x4380: self.dma[o - 0x4300] = v & 0xFF
            elif o == 0x420B: self._dma(v & 0xFF)
            ohw(o, v)
        c.hwwrite = hwwrite
        for a in (0xC1E8F1, 0x01E8F1): c.hooks[a] = self._vm_op
        c.hooks[0xC0B03F] = self._reload_hook
        for a in (0xC30004, 0xC30000): c.hooks[a] = self._snd
        self._last = {}
        self._last_misc = None
        self._vmi = 0

    # ---- DMA: only transfers whose B-bus target is the WRAM port $2180 change game memory (clears of work areas); the rest is dropped
    def _dma(self, mask):
        c = self.c
        for ch in range(8):
            if not (mask >> ch) & 1: continue
            r = self.dma[ch * 16:ch * 16 + 16]
            if r[1] != 0x80 or r[0] & 0x80: continue
            src = r[2] | r[3] << 8 | r[4] << 16
            n = r[5] | r[6] << 8 or 0x10000
            fixed = bool(r[0] & 0x08)
            for i in range(n):
                c.hwwrite(0x2180, c.rd8(src if fixed else src + i))
            self.dma[ch * 16 + 5] = 0; self.dma[ch * 16 + 6] = 0

    # ---- hooks
    def _vm_op(self, cp):
        w = cp.wram
        d1 = w[0xD1] | w[0xD2] << 8; bank = w[0xD3]
        o = (bank << 16 | d1) & 0x3FFFFF
        op = self.rom[o]
        self.vm_ops.append(dict(t=self.t, bank=bank, addr=d1, op=op, args=bytes(self.rom[o + 1:o + 5]) if op < 0x50 else b'', d0=w[0xD0]))
        return False

    def _snd(self, cp):
        w = cp.wram
        self.events.append(dict(t=self.t, kind='sound', cmd=w[0x1E00], arg1=w[0x1E01], arg2=w[0x1E02], arg3=w[0x1E03]))
        cp.PC = (cp.pull16() + 1) & 0xFFFF; cp.PB = cp.pull8(); return True

    def _reload_hook(self, cp):
        raise MapReload()

    def w8(self, a): return self.c.wram[a]
    def w16(self, a): return self.c.wram[a] | self.c.wram[a + 1] << 8

    # ---- map loading (the part of $C0:B03F that matters)
    def map_loader(self):
        w = self.c.wram
        w[0xFF] = 0; w[0xE2] = 0
        for a in (0xC087C4, 0xC0BC9B, 0xC0BC0B, 0xC0E9F8):
            self.callrts(a)
        self.callrts(0xC0BEAA)              # entry event of the new map
        self.phase0 = self.t + 1

    def load_map(self, transition, flags=None):
        """Same as VM command 0x18-0x1B (event 0x800 | transition), then the loader the main loop jumps to when the fade is done."""
        w = self.c.wram
        for k, v in (flags or {}).items():
            w[0xCF00 + k] = v
        for a in (0xD0, 0xF1, 0x4E, 0x4F, 0xCFFF, 0x1D04, 0x1D00): w[a] = 0        # no event, no freeze, no text window left over in the state
        for i in range(9): w[0xE60 + i] = 0
        self.call(0xC1E76D, A=0x800 | transition)
        self.map_loader()
        self.t_scene = self.t

    def set_leader(self, slot):
        w = self.c.wram
        for h in range(3):
            w[0xE000 + 0x200 * h + 0x2C] = 1 if h == slot else 0
        w[0xD9] = 1 << slot; w[0xDA] = 0; w[0xDB] = 0
        w[0xD4] = (slot * 0x200) & 0xFF; w[0xD5] = (slot * 0x200) >> 8

    def start_event(self, ev):
        self.call(0xC1E76D, A=ev)

    # ---- one frame = body $C0:B08C + the NMI duties
    def frame(self):
        w = self.c.wram
        self.t += 1
        w[0x56] = (self.t - self.phase0) % 5
        self.pad = 0
        if w[0xD0] == 0x83:
            if self._release <= 0: self.pad = self.PAD_A; self._release = 2
        self._release -= 1
        try:
            self.callrts(0xC0B08C)
        except MapReload:
            self.map_loader()
            self.events.append(dict(t=self.t, kind='map_load', map=self.w16(0xDC), dx=w[0xDE], dy=w[0xDF], b8=w[0xB8]))
        w[0xF4] = (w[0xF4] + 1) & 0xFF
        if w[0x1D04] & 4:
            self.callrts(0xC0C1E7)
        self._observe()

    # ---- observers
    def snap(self, slot):
        w = self.c.wram
        b = 0xE000 + 0x200 * slot
        if not w[b]: return None
        d = {n: (w[b + o] if sz == 1 else self.w16(b + o)) for n, o, sz in FIELDS}
        d['id'] = w[b + 0x180]
        d['f2b'] = self.w16(b + 0x2B); d['f32'] = self.w16(b + 0x32); d['f98'] = self.w16(b + 0x98); d['f7a'] = w[b + 0x7A]; d['f94'] = self.w16(b + 0x94); d['f96'] = self.w16(b + 0x96); d['fb0'] = self.w16(b + 0xB0); d['fad'] = self.w16(b + 0xAD)
        return d

    MISC = [('D0', 0xD0, 1), ('F1', 0xF1, 1), ('D9', 0xD9, 1), ('E2', 0xE2, 1), ('E6', 0xE6, 1), ('E7', 0xE7, 1), ('E8', 0xE8, 1), ('FF', 0xFF, 1),
            ('P52', 0x52, 1), ('P4E', 0x4E, 1), ('P5C', 0x5C, 1), ('D4', 0xD4, 2), ('E0', 0xE0, 1), ('X2A', 0x2A, 1), ('cf4e', 0xCF4E, 1), ('T1D04', 0x1D04, 1), ('CFFF', 0xCFFF, 1)]

    def _observe(self):
        w = self.c.wram
        for sl in range(9):
            s = self.snap(sl)
            if s != self._last.get(sl):
                self.events.append(dict(t=self.t, kind='obj', slot=sl, s=s)); self._last[sl] = s
        cam = (self.w16(0xA8), self.w16(0xAA), self.w16(0xC0), self.w16(0xC2))
        if cam != self._last.get('cam'):
            self.events.append(dict(t=self.t, kind='cam', x=cam[0], y=cam[1], mapw=cam[2], maph=cam[3])); self._last['cam'] = cam
        m = tuple(self.w16(a) if sz == 2 else w[a] for _, a, sz in self.MISC)
        if m != self._last_misc:
            self.events.append(dict(t=self.t, kind='misc', **{n: v for (n, _, _), v in zip(self.MISC, m)})); self._last_misc = m

    # ---- whole scene
    def run_scene(self, transition, flags, leader=0, max_frames=12000):
        self.set_leader(leader)
        self.load_map(transition, flags)
        self._observe()
        w = self.c.wram
        while self.t - self.t_scene < max_frames:
            self.frame()
            if w[0xD0] == 0 and self.t - self.t_scene > 10 and not any(e['kind'] == 'map_load' and e['t'] >= self.t - 3 for e in self.events[-5:]):
                break
        return self.events




# ---------------------------------------------------------------------------------------------- timeline extraction
FACE = {0x00: 'up', 0x01: 'down', 0x02: 'right', 0x82: 'left'}
SLOT_NAME = {0: 'hero0_boy', 1: 'hero1_girl', 2: 'hero2_sprite'}


def _sec(t): return round(t / HZ, 3)


def series(events, slot):
    """[(t, snapshot or None)] of one object slot (a new entry whenever any logged field changed)."""
    return [(e['t'], e['s']) for e in events if e['kind'] == 'obj' and e['slot'] == slot]


def movement_segments(ser, gap=2, breaks=()):
    """Groups of frames in which the position changed (gaps up to `gap` frames are bridged: half-speed objects move every second frame).
    Frames listed in `breaks` (map loads) are repositionings, not movement. Each group carries `profile`: run-length list of [frames, dx, dy]."""
    frames = []
    prev = None
    for t, s in ser:
        if s is None:
            prev = None; continue
        if prev is not None and (s['x'], s['y']) != (prev['x'], prev['y']) and t not in breaks:
            frames.append((t, s, prev))
        prev = s
    groups = []
    for t, s, p in frames:
        d = (s['x'] - p['x'], s['y'] - p['y'])
        dk = ((d[0] > 0) - (d[0] < 0), (d[1] > 0) - (d[1] < 0))
        if groups and t - groups[-1]['t1'] <= gap and groups[-1]['dk'] == dk:
            g = groups[-1]
            g['t1'] = t; g['to'] = (s['x'], s['y']); g['anims'].add(s['anim']); g['faces'].add(s['face'])
            g['vels'].add((s['vx'], s['vy'])); g['path'] += abs(d[0]) + abs(d[1]); g['n'] += 1
            g['per'].append((t, d))
        else:
            groups.append(dict(t0=t, t1=t, frm=(p['x'], p['y']), to=(s['x'], s['y']), anims={s['anim']}, faces={s['face']},
                               vels={(s['vx'], s['vy'])}, path=abs(d[0]) + abs(d[1]), n=1, per=[(t, d)], dk=dk))
    for g in groups:
        runs = []
        last_t = None
        for t, d in g['per']:
            if last_t is not None and t - last_t > 1:
                runs.append([t - last_t - 1, 0, 0])
            if runs and runs[-1][1:] == [d[0], d[1]]: runs[-1][0] += 1
            else: runs.append([1, d[0], d[1]])
            last_t = t
        g['profile'] = runs
    return groups


def vm_text(nm, pr):
    """One-line description of a decoded command."""
    if nm == 'WAIT_IDLE': return 'WAIT_IDLE (state 0x85)'
    if nm == 'WAIT':
        return 'WAIT for a button (state 0x83)' if pr['wait_press'] else 'WAIT %d ticks (= %d frames, %.3f s)' % (pr['ticks'], pr['ticks'] * VM_TICK, pr['ticks'] * VM_TICK / HZ)
    if nm in ('CALL_EVENT', 'GOTO_EVENT'): return '%s event 0x%03X' % (nm, pr['target_event'])
    if nm == 'MAP_CHANGE': return 'MAP_CHANGE transition %d' % pr['transition']
    if nm == 'ACTOR_WALK': return 'ACTOR_WALK actor %d %s %d frames' % (pr['actor'], pr['direction'], pr['frames'])
    if nm in ('ACTOR_ANIM', 'ACTOR_ANIM_LOOP'): return '%s actor %d anim 0x%02X' % (nm, pr['actor'], pr['anim'])
    if nm in ('FLAG_INC', 'FLAG_DEC'): return '%s flag 0x%02X' % (nm, pr['flag'])
    if nm == 'SOUND': return 'SOUND cmd %d id 0x%02X word 0x%04X' % (pr['cmd'], pr['id'], pr['word'])
    if nm == 'SCREEN': return 'SCREEN arg %d' % pr['arg']
    if nm == 'IF_FLAG_RANGE': return 'IF_FLAG_RANGE flag 0x%02X in %d..%d' % (pr['flag'], pr['lo'], pr['hi'])
    return nm


def sm(v):
    """sign-magnitude velocity byte -> signed int"""
    return -(v & 0x7F) if v & 0x80 else v & 0x7F


def dark_lich_report(rom, w, leader=0):
    ev = list(w.run_scene(340, {0x4E: 4}, leader=leader))
    t_end = w.t - w.t_scene
    tail_from = len(w.events)
    for _ in range(AFTER_FRAMES):             # keep running: what the released Lich does next (no hero input, the party stands still)
        w.frame()
    tail = w.events[tail_from:]
    sc = w.t_scene
    loads = [dict(t=0, map=245)] + [dict(t=e['t'] - sc, map=e['map'], start_tile_x=e['dx'], start_tile_y=e['dy'] >> 1, header_b8=e['b8']) for e in ev if e['kind'] == 'map_load']
    vm = []
    for o in w.vm_ops:
        evid, off = event_of(rom, o['bank'], o['addr'])
        opn = o['op'] if o['op'] < 0x50 else 0x50
        ent = OPS.get(opn)
        r = dict(t=o['t'] - sc, s=_sec(o['t'] - sc), event='0x%03X' % evid, offset=off, addr='%02X:%04X' % (o['bank'], o['addr']),
                 op='%02X' % o['op'] if o['op'] < 0x50 else 'TEXT', name=ent[0] if ent else '?', d0=o['d0'])
        if o['op'] < 0x50:
            r['params'] = op_params(o['op'], o['args'].ljust(4, b'\0'))
            r['length'] = op_len(rom, o['bank'], o['addr'])
        else:
            r['bytes'] = op_len(rom, o['bank'], o['addr'])
        vm.append(r)
    dialogs = []
    for i, r in enumerate(vm):
        if r['op'] == 'TEXT':
            nxt = vm[i + 1]['t'] if i + 1 < len(vm) else t_end
            dialogs.append(dict(n=len(dialogs) + 1, event=r['event'], offset=r['offset'], addr=r['addr'], bytes=r['bytes'], t_start=r['t'], s_start=r['s'],
                                t_end=nxt, frames=nxt - r['t']))
    sounds = []
    vm_sound_t = {r['t'] for r in vm if r['name'] == 'SOUND'}
    for e in ev:
        if e['kind'] == 'sound':
            kind = {1: 'music', 2: 'sfx'}.get(e['cmd'], 'raw')
            sounds.append(dict(t=e['t'] - sc, s=_sec(e['t'] - sc), kind=kind, cmd=e['cmd'], id=e['arg1'], p2=e['arg2'], p3=e['arg3'], source='vm_op' if (e['t'] - sc) in vm_sound_t else 'engine'))
    load_ts = {e['t'] + d for e in ev if e['kind'] == 'map_load' for d in (0, 1)}      # the loader places the objects over two frames
    objs = {}
    for sl in range(9):
        ser = series(ev, sl)
        if not ser: continue
        first = ser[0][1]
        info = dict(slot=sl, id=first['id'] if first else None)
        info['first_t'] = ser[0][0] - sc
        info['moves'] = []
        mser = [(t, sn if sn and sn['id'] and not 0x57 <= sn['id'] <= 0x7F else None) for t, sn in ser]       # boss-engine objects (ids 0x57-0x7F) keep other fields in obj+2/+4; id 0 = helper object
        for g in movement_segments(mser, breaks=load_ts):
            frames = g['t1'] - g['t0'] + 1
            cause = None
            for r in vm:
                if r['name'] in ('ACTOR_WALK', 'ACTOR_ANIM', 'ACTOR_ANIM_LOOP', 'GATHER') and 0 <= (g['t0'] - sc) - r['t'] <= 2:
                    if r['name'] == 'GATHER':
                        if sl < 3 and sl != leader: cause = '%s+%04X GATHER' % (r['event'], r['offset'])
                    else:
                        a = r['params']['actor']
                        tgt = leader if a == 0 else (a - 1 if a < 0x80 else None)
                        if tgt == sl: cause = '%s+%04X %s' % (r['event'], r['offset'], vm_text(r['name'], r['params']))
                    if cause: break
            info['moves'].append(dict(t0=g['t0'] - sc, t1=g['t1'] - sc, s0=_sec(g['t0'] - sc), frm=list(g['frm']), to=list(g['to']), frames=frames,
                                      px=g['path'], px_per_frame=round(g['path'] / frames, 3), px_per_s=round(g['path'] / frames * HZ, 2),
                                      anim=sorted(g['anims']), facing=sorted(FACE.get(f, f) for f in g['faces']),
                                      vel=sorted((sm(a), sm(b)) for a, b in g['vels']), profile=g['profile'], cause=cause))
        info['facing'] = []; info['pose'] = []; info['presence'] = []; info['ids'] = []
        pf = None; pp = None; pres = None
        for t, s in ser:
            on = s is not None
            if on != pres:
                info['presence'].append(dict(t=t - sc, s=_sec(t - sc), on=on)); pres = on
            if not s: pf = None; pp = None; continue
            if not info['ids'] or info['ids'][-1]['id'] != s['id']: info['ids'].append(dict(t=t - sc, id=s['id']))
            if s['face'] != pf and t not in load_ts:
                info['facing'].append(dict(t=t - sc, s=_sec(t - sc), facing=FACE.get(s['face'], s['face']), code=s['face'])); pf = s['face']
            key = (s['state'], s['anim']) if (s['state'] or s['anim'] not in (0, 1, 2, 3)) else None
            if key != pp and t not in load_ts:
                if key: info['pose'].append(dict(t=t - sc, s=_sec(t - sc), state=s['state'], anim=s['anim']))
                else: info['pose'].append(dict(t=t - sc, s=_sec(t - sc), state=0, anim='idle'))
                pp = key
        info['snap0'] = {k: ser[0][1][k] for k in ('x', 'y', 'face', 'anim', 'id')} if ser[0][1] else None
        objs[SLOT_NAME.get(sl, 'slot%d' % sl)] = info
    entries = []
    for ld in loads:
        tt = ld['t'] + sc
        ent = dict(map=ld['map'], t=ld['t'], objects={})
        for sl in range(9):
            cur = None
            for t, sn in series(ev, sl):
                if t <= tt: cur = sn
            if cur:
                o = dict(id=cur['id'], x=cur['x'], y=cur['y'], face=FACE.get(cur['face'], cur['face']), face_code=cur['face'])
                if cur['id'] == 0x79: o.update(engine_x=cur['f2b'], engine_y=cur['f32'], note='boss engine object: position is obj+0x2B/+0x32, obj+2/+4 are unused')
                ent['objects'][SLOT_NAME.get(sl, 'slot%d' % sl)] = o
        entries.append(ent)
    cams = [(e['t'], e['x'], e['y']) for e in ev if e['kind'] == 'cam']
    camseg = []
    for i, (t, x, y) in enumerate(cams):
        if i == 0:
            camseg.append(dict(t0=t - sc, t1=t - sc, frm=[x, y], to=[x, y], initial=True)); continue
        px_, py_ = cams[i - 1][1], cams[i - 1][2]
        if t in load_ts:
            camseg.append(dict(t0=t - sc, t1=t - sc, frm=[px_, py_], to=[x, y], map_load=True)); continue
        if t - sc - camseg[-1]['t1'] <= 2 and not camseg[-1].get('initial') and not camseg[-1].get('map_load'):
            camseg[-1]['t1'] = t - sc; camseg[-1]['to'] = [x, y]
        else:
            camseg.append(dict(t0=t - sc, t1=t - sc, frm=[px_, py_], to=[x, y]))
    for c in camseg:
        c['s0'] = _sec(c['t0']); c['frames'] = c['t1'] - c['t0'] + 1
    mapsz = next(((e['mapw'], e['maph']) for e in ev if e['kind'] == 'cam'), None)
    misc = [e for e in ev if e['kind'] == 'misc']
    screen = []
    vm_states = []
    prev = None
    fade_runs = []
    for e in misc:
        if prev is None: prev = e; continue
        T = e['t'] - sc
        if (e['E2'] & 4) != (prev['E2'] & 4): screen.append(dict(t=T, s=_sec(T), what='flash_on' if e['E2'] & 4 else 'flash_off'))
        if (e['E2'] & 8) != (prev['E2'] & 8): screen.append(dict(t=T, s=_sec(T), what='camera_recentre_start' if e['E2'] & 8 else 'camera_recentre_done'))
        if e['E6'] != prev['E6']: fade_runs.append((T, prev['E6'], e['E6']))
        if (e['F1'] & 0x80) != (prev['F1'] & 0x80): screen.append(dict(t=T, s=_sec(T), what='world_freeze_on' if e['F1'] & 0x80 else 'world_freeze_off'))
        if (e['D9'] & 0x80) != (prev['D9'] & 0x80): screen.append(dict(t=T, s=_sec(T), what='pad_locked' if e['D9'] & 0x80 else 'pad_released'))
        if (e['CFFF'] & 1) != (prev['CFFF'] & 1): screen.append(dict(t=T, s=_sec(T), what='boss_freeze_flag_set' if e['CFFF'] & 1 else 'boss_freeze_flag_cleared'))
        if e['cf4e'] != prev['cf4e']: screen.append(dict(t=T, s=_sec(T), what='flag_4E_changed', value=e['cf4e']))
        if e['D0'] != prev['D0']:
            vm_states.append(dict(t=T, s=_sec(T), d0=e['D0'], prev=prev['D0']))
        prev = e
    fades = []
    for t, a, b in fade_runs:
        if fades and t - fades[-1]['t1'] <= 4 and (b - a) == fades[-1]['dir']:
            fades[-1]['t1'] = t; fades[-1]['to'] = b
        else:
            fades.append(dict(t0=t, t1=t, frm=a, to=b, dir=b - a))
    for f in fades:
        f['s0'] = _sec(f['t0']); f['frames'] = f['t1'] - f['t0'] + 1; f['kind'] = 'fade_in' if f['dir'] > 0 else 'fade_out'
    lich = {}
    for t, s in series(ev, 3):
        if s and s['id'] == 0x79:
            lich.setdefault('spawn', dict(t=t - sc, s=_sec(t - sc), engine_x=s['f2b'], engine_y=s['f32'], flags98='0x%04X' % s['f98'], phase94=s['f94'], state7A=s['f7a']))
    ticks = []
    lastage = None
    for t, s in series(ev, 3):
        if s and s['id'] == 0x79 and s['f96'] != lastage:
            ticks.append(t - sc); lastage = s['f96']
    lich['age_change_t'] = ticks[:12]
    rel = [x for x in screen if x['what'] == 'boss_freeze_flag_cleared']
    lich['freeze_flag_set_t'] = [x['t'] for x in screen if x['what'] == 'boss_freeze_flag_set']
    lich['freeze_flag_cleared_t'] = [x['t'] for x in rel]
    lich['first_tick_after_release'] = next((t for t in ticks if rel and t > rel[0]['t']), None)
    after = []
    last = None
    for e in tail:
        if e['kind'] == 'obj' and e['slot'] == 3 and e['s'] and e['s']['id'] == 0x79:
            sn = e['s']; key = (sn['f7a'], sn['fb0'], sn['f94'])
            if key != last:
                after.append(dict(t=e['t'] - sc, state_7A=sn['f7a'], seq_B0=sn['fb0'], phase_94=sn['f94'], action_timer_AD=sn['fad'], engine_x=sn['f2b'], engine_y=sn['f32'])); last = key
    lich['after_release_state_changes'] = after
    end_ops = [r for r in vm if r['name'] == 'END']
    initial = {k: v for k, v in (misc[0].items() if misc else []) if k not in ('t', 'kind')}
    summary = dict(total_frames=t_end, total_s=_sec(t_end), vm_ops=len(vm), dialogs=len(dialogs), map_loads=loads, leader=leader,
                   end_op_t=end_ops[-1]['t'] if end_ops else None, map_size_px=mapsz)
    return dict(source='tools/event_vm.py dark-lich (real 65816 code stepped frame by frame; PPU/APU not emulated)', clock=dict(frame_hz=HZ, vm_tick_frames=VM_TICK, vm_hz=round(HZ / VM_TICK, 3)),
                conditions=dict(transition=340, flags={'4E': 4}, leader=leader, hero_weapon_types=[w.c.wram[0xE000 + 0x200 * h + 0x1E4] for h in range(3)],
                                t0='first frame after the loader of map 245 returned', time_unit='frames of 1/60.0988 s; VM steps happen every 5 frames'),
                summary=summary, initial_state=initial, entries=entries, vm=vm, dialogs=dialogs, sounds=sounds, objects=objs, camera=camseg, fades=fades, screen=screen, vm_states=vm_states, lich=lich)


def scene_variants(rom, state):
    """Re-run the scene for each controlled hero and for each weapon type of hero 1 (the girl); records what changes (about 25 s per run)."""
    out = dict(leader=[], hero1_weapon_type=[])
    for L in range(3):
        w = World(rom, state)
        rep = dark_lich_report(rom, w, L)
        pan = [x for x in rep['screen'] if x['what'] in ('camera_recentre_start', 'camera_recentre_done')]
        out['leader'].append(dict(leader=L, total_frames=rep['summary']['total_frames'], end_op_t=rep['summary']['end_op_t'],
                                  second_recentre_frames=pan[3]['t'] - pan[2]['t'] if len(pan) >= 4 else None))
    for t in range(8):
        w = World(rom, state)
        row = t * 9 + 7                                  # weapon row id = type * 9 + grade (grade 7 here)
        for off, v in ((0x1E3, row), (0x1E4, t), (0x1E8, row)): w.c.wram[0xE200 + off] = v
        rep = dark_lich_report(rom, w, 0)
        pose = [p for p in rep['objects']['hero1_girl']['pose'] if p['anim'] == 0 and p['state'] == 0x40]
        nxt = [p for p in rep['objects']['hero1_girl']['pose'] if pose and p['t'] > pose[0]['t']]
        out['hero1_weapon_type'].append(dict(weapon_type=t, swing_anim_frames=nxt[0]['t'] - pose[0]['t'] if pose and nxt else None,
                                             total_frames=rep['summary']['total_frames'], end_op_t=rep['summary']['end_op_t']))
    return out


def timeline_rows(rep):
    """Merged chronological rows (t, who, what) for the markdown table; dialog blocks are collapsed into runs."""
    rows = []
    def objname(k, o, t=None):
        if o['slot'] < 3: return {0: 'boy (slot 0)', 1: 'girl (slot 1)', 2: 'sprite (slot 2)'}[o['slot']]
        ids = [i for i in o['ids'] if t is None or i['t'] <= t] or o['ids'][:1]
        return 'slot %d (id 0x%02X)' % (o['slot'], ids[-1]['id'])
    rows.append((0, 'party', 'map 245 loaded, party placed at its start tile; fade-in brightness 0 -> 15 (+1 per frame, frames 1-15)'))
    run = None
    vm = rep['vm']
    for i, r in enumerate(vm):
        nm = r['name']
        if nm in ('TEXT', 'WAIT') and (nm == 'TEXT' or r['params']['wait_press']):
            if run is None: run = dict(t0=r['t'], n=0, ev=r['event'], off=r['offset'])
            if nm == 'TEXT': run['n'] += 1
            run['t1'] = vm[i + 1]['t'] if i + 1 < len(vm) else r['t']
            continue
        if run:
            rows.append((run['t0'], 'dialog', '%d text block%s from %s+%04X, each followed by a wait for a button; the next command runs at frame %d' % (run['n'], 's' if run['n'] != 1 else '', run['ev'], run['off'], run['t1']))); run = None
        txt = vm_text(nm, r.get('params', {}))
        rows.append((r['t'], 'VM %s+%04X' % (r['event'], r['offset']), txt))
    if run:
        rows.append((run['t0'], 'dialog', '%d text block%s from %s+%04X; the next command runs at frame %d' % (run['n'], 's' if run['n'] != 1 else '', run['ev'], run['off'], run['t1'])))
    for k, o in rep['objects'].items():
        sl = o['slot']
        for m in o['moves']:
            prof = ' '.join('%dx(%+d,%+d)' % tuple(x) for x in m['profile'])
            rows.append((m['t0'], objname(k, o, m['t0']), 'walk %s -> %s, %d frames, %.1f px/s, facing %s, anim %s, per-frame %s%s' % (
                tuple(m['frm']), tuple(m['to']), m['frames'], m['px_per_s'], '/'.join(m['facing']), m['anim'], prof, ' [%s]' % m['cause'] if m['cause'] else '')))
        for f in o['facing'][1:]:
            if any(m['t0'] <= f['t'] <= m['t1'] + 1 for m in o['moves']): continue
            rows.append((f['t'], objname(k, o, f['t']), 'facing %s (0x%02X)' % (f['facing'], f['code'])))
        for p_ in o['pose']:
            rows.append((p_['t'], objname(k, o, p_['t']), 'pose idle' if p_['anim'] == 'idle' else 'pose state 0x%02X anim 0x%02X' % (p_['state'], p_['anim'])))
        for pr_ in o['presence'][1:]:
            rows.append((pr_['t'], objname(k, o, pr_['t']), 'appears' if pr_['on'] else 'removed'))
    for c in rep['camera'][1:]:
        if c.get('map_load'): rows.append((c['t0'], 'camera', 'set by the map loader to %s' % (tuple(c['to']),)))
        else: rows.append((c['t0'], 'camera', 'scroll %s -> %s, %d frames' % (tuple(c['frm']), tuple(c['to']), c['frames'])))
    for f in rep['fades']:
        rows.append((f['t0'], 'screen', '%s brightness %d -> %d, %d frames' % (f['kind'], f['frm'], f['to'] if f['dir'] > 0 else f['to'], f['frames'])))
    for x in rep['screen']:
        rows.append((x['t'], 'engine', x['what'] + (' %s' % x['value'] if 'value' in x else '')))
    for x in rep['sounds']:
        rows.append((x['t'], 'sound', '%s id 0x%02X (cmd %d, params 0x%02X 0x%02X) from %s' % (x['kind'], x['id'], x['cmd'], x['p2'], x['p3'], x['source'])))
    lich = rep['lich']
    if 'spawn' in lich:
        sp = lich['spawn']
        rows.append((sp['t'], 'Dark Lich', 'spawned by the boss spawner: engine position (%d,%d), flags 0x%04X' % (sp['engine_x'], sp['engine_y'], int(sp['flags98'], 16))))
    if lich.get('first_tick_after_release'):
        rows.append((lich['first_tick_after_release'], 'Dark Lich', 'first AI tick after the freeze flag was cleared'))
    return sorted(rows, key=lambda r: r[0])        # stable: commands first, then what they caused


def print_md(rep):
    print('| frame | s | object | what |'); print('|---|---|---|---|')
    for t, who, what in timeline_rows(rep):
        print('| %d | %.3f | %s | %s |' % (t, t / HZ, who, what))


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 1
    rom = romio.load(argv[1])
    cmd = argv[2]
    if cmd == 'table':
        for o in sorted(OPS):
            nm, ln, s, tag = OPS[o]
            print('%02X %-16s %-4s [%s] %s' % (o, nm, ln if ln else 'var', tag, s))
        return 0
    if cmd == 'decode':
        for e in argv[3:]:
            ev = int(e, 16)
            bank, out = decode_event(rom, ev)
            print('event %03X bank %02X' % (ev, bank))
            for r in out:
                if r['op'] == 'TEXT': print('  %04X TEXT %d bytes' % (r['off'], r['bytes']))
                else: print('  %04X %s %-16s %s' % (r['off'], r['op'], r['name'], r['params'] or ''))
        return 0
    state = argv[2]
    cmd = argv[3]
    kv = dict(a.split('=', 1) for a in argv[4:] if '=' in a)
    pos = [a for a in argv[4:] if '=' not in a]
    w = World(rom, state)
    if cmd == 'dark-lich':
        leader = int(kv.get('leader', 0))
        rep = dark_lich_report(rom, w, leader)
        if kv.get('variants'):
            rep['variants'] = scene_variants(rom, state)
        json.dump(rep, open(pos[0], 'w'), indent=1)
        print('wrote', pos[0], 'frames', rep['summary']['total_frames'])
        if kv.get('md'):
            print_md(rep)
        return 0
    if cmd == 'run':
        flags = {int(k, 16): int(v, 0) for k, v in kv.items() if len(k) <= 2 and k not in ('leader',)}
        ev = w.run_scene(int(pos[0]), flags, leader=int(kv.get('leader', 0)), max_frames=int(kv.get('frames', 12000)))
        if 'out' in kv:
            json.dump(dict(frames=w.t - w.t_scene, events=ev, vm_ops=[dict(t=o['t'], bank=o['bank'], addr=o['addr'], op=o['op'], d0=o['d0'], params=op_params(o['op'], o['args'].ljust(4, b'\0')) if o['op'] < 0x50 else {}) for o in w.vm_ops]), open(kv['out'], 'w'))
        if not kv.get('quiet'):
            for o in w.vm_ops:
                ev_id, off = event_of(rom, o['bank'], o['addr'])
                nm = OPS[o['op'] if o['op'] < 0x50 else 0x50][0] if (o['op'] if o['op'] < 0x50 else 0x50) in OPS else '?'
                print('t=%5d %6.2fs ev %03X+%04X %-16s %s' % (o['t'] - w.t_scene, (o['t'] - w.t_scene) / HZ, ev_id, off, nm, op_params(o['op'], o['args'].ljust(4, b'\0')) if o['op'] < 0x50 else ''))
        return 0
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))

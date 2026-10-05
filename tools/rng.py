"""Exact model of the SoM random number generator ($C0:38A0): 15-byte lagged additive generator in WRAM $03F1-$03FF with index $03F0.
Usage: r = Rng(state_bytes15, index);  r.byte() -> 0..255;  r.below(n) -> floor(byte*n/256)  (= JSL $C0:3884 with A=n)"""
class Rng:
    def __init__(s, state, idx):
        s.t = list(state); s.i = idx
    @classmethod
    def from_wram(cls, wram):
        return cls(wram[0x3F1:0x400], wram[0x3F0])
    def byte(s):
        cc = s.t[s.i]
        x = s.i - 1
        if x < 0: x = 0x0E
        v = (s.t[x] + cc) & 0xFF
        s.t[x] = v
        s.i += 1
        if s.i == 0x0F: s.i = 0
        return v
    def below(s, n):
        return (s.byte() * (n & 0xFF)) >> 8

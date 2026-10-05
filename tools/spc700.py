"""SPC700 opcode table and disassembler (library and command line).

usage: spc700.py RAMFILE START_HEX LENGTH_HEX      (RAMFILE = 65536-byte APU RAM image, for example bytes 0x100-0x100FF of a .spc written by sfx_extract.py --dump-spc)

OPS[op] = (mnemonic template, operand kinds). Operand kinds: d = direct page byte, a = 16-bit address,
i = immediate byte, r = relative branch byte, m = 13-bit address + 3-bit bit index (16-bit word), u = upage byte.
The template refers to the operand bytes by position in the instruction ({0} is the first byte after the opcode).
"""
import sys

# (template, kinds) for every opcode; kinds is a string of operand kinds in byte order
_T = """
NOP|;TCALL 0|;SET1 {0}.0|d;BBS {0}.0,{1}|dr;OR A,{0}|d;OR A,!{0}|a;OR A,(X)|;OR A,[{0}+X]|d;OR A,#{0}|i;OR {1},{0}|dd;OR1 C,{0}|m;ASL {0}|d;ASL !{0}|a;PUSH PSW|;TSET1 !{0}|a;BRK|
BPL {0}|r;TCALL 1|;CLR1 {0}.0|d;BBC {0}.0,{1}|dr;OR A,{0}+X|d;OR A,!{0}+X|a;OR A,!{0}+Y|a;OR A,[{0}]+Y|d;OR {1},#{0}|id;OR (X),(Y)|;DECW {0}|d;ASL {0}+X|d;ASL A|;DEC X|;CMP X,!{0}|a;JMP [!{0}+X]|a
CLRP|;TCALL 2|;SET1 {0}.1|d;BBS {0}.1,{1}|dr;AND A,{0}|d;AND A,!{0}|a;AND A,(X)|;AND A,[{0}+X]|d;AND A,#{0}|i;AND {1},{0}|dd;OR1 C,/{0}|m;ROL {0}|d;ROL !{0}|a;PUSH A|;CBNE {0},{1}|dr;BRA {0}|r
BMI {0}|r;TCALL 3|;CLR1 {0}.1|d;BBC {0}.1,{1}|dr;AND A,{0}+X|d;AND A,!{0}+X|a;AND A,!{0}+Y|a;AND A,[{0}]+Y|d;AND {1},#{0}|id;AND (X),(Y)|;INCW {0}|d;ROL {0}+X|d;ROL A|;INC X|;CMP X,{0}|d;CALL !{0}|a
SETP|;TCALL 4|;SET1 {0}.2|d;BBS {0}.2,{1}|dr;EOR A,{0}|d;EOR A,!{0}|a;EOR A,(X)|;EOR A,[{0}+X]|d;EOR A,#{0}|i;EOR {1},{0}|dd;AND1 C,{0}|m;LSR {0}|d;LSR !{0}|a;PUSH X|;TCLR1 !{0}|a;PCALL {0}|u
BVC {0}|r;TCALL 5|;CLR1 {0}.2|d;BBC {0}.2,{1}|dr;EOR A,{0}+X|d;EOR A,!{0}+X|a;EOR A,!{0}+Y|a;EOR A,[{0}]+Y|d;EOR {1},#{0}|id;EOR (X),(Y)|;CMPW YA,{0}|d;LSR {0}+X|d;LSR A|;MOV X,A|;CMP Y,!{0}|a;JMP !{0}|a
CLRC|;TCALL 6|;SET1 {0}.3|d;BBS {0}.3,{1}|dr;CMP A,{0}|d;CMP A,!{0}|a;CMP A,(X)|;CMP A,[{0}+X]|d;CMP A,#{0}|i;CMP {1},{0}|dd;AND1 C,/{0}|m;ROR {0}|d;ROR !{0}|a;PUSH Y|;DBNZ {0},{1}|dr;RET|
BVS {0}|r;TCALL 7|;CLR1 {0}.3|d;BBC {0}.3,{1}|dr;CMP A,{0}+X|d;CMP A,!{0}+X|a;CMP A,!{0}+Y|a;CMP A,[{0}]+Y|d;CMP {1},#{0}|id;CMP (X),(Y)|;ADDW YA,{0}|d;ROR {0}+X|d;ROR A|;MOV A,X|;CMP Y,{0}|d;RETI|
SETC|;TCALL 8|;SET1 {0}.4|d;BBS {0}.4,{1}|dr;ADC A,{0}|d;ADC A,!{0}|a;ADC A,(X)|;ADC A,[{0}+X]|d;ADC A,#{0}|i;ADC {1},{0}|dd;EOR1 C,{0}|m;DEC {0}|d;DEC !{0}|a;MOV Y,#{0}|i;POP PSW|;MOV {1},#{0}|id
BCC {0}|r;TCALL 9|;CLR1 {0}.4|d;BBC {0}.4,{1}|dr;ADC A,{0}+X|d;ADC A,!{0}+X|a;ADC A,!{0}+Y|a;ADC A,[{0}]+Y|d;ADC {1},#{0}|id;ADC (X),(Y)|;SUBW YA,{0}|d;DEC {0}+X|d;DEC A|;MOV X,SP|;DIV YA,X|;XCN A|
EI|;TCALL 10|;SET1 {0}.5|d;BBS {0}.5,{1}|dr;SBC A,{0}|d;SBC A,!{0}|a;SBC A,(X)|;SBC A,[{0}+X]|d;SBC A,#{0}|i;SBC {1},{0}|dd;MOV1 C,{0}|m;INC {0}|d;INC !{0}|a;CMP Y,#{0}|i;POP A|;MOV (X)+,A|
BCS {0}|r;TCALL 11|;CLR1 {0}.5|d;BBC {0}.5,{1}|dr;SBC A,{0}+X|d;SBC A,!{0}+X|a;SBC A,!{0}+Y|a;SBC A,[{0}]+Y|d;SBC {1},#{0}|id;SBC (X),(Y)|;MOVW YA,{0}|d;INC {0}+X|d;INC A|;MOV SP,X|;DAS A|;MOV A,(X)+|
DI|;TCALL 12|;SET1 {0}.6|d;BBS {0}.6,{1}|dr;MOV {0},A|d;MOV !{0},A|a;MOV (X),A|;MOV [{0}+X],A|d;CMP X,#{0}|i;MOV !{0},X|a;MOV1 {0},C|m;MOV {0},Y|d;MOV !{0},Y|a;MOV X,#{0}|i;POP X|;MUL YA|
BNE {0}|r;TCALL 13|;CLR1 {0}.6|d;BBC {0}.6,{1}|dr;MOV {0}+X,A|d;MOV !{0}+X,A|a;MOV !{0}+Y,A|a;MOV [{0}]+Y,A|d;MOV {0},X|d;MOV {0}+Y,X|d;MOVW {0},YA|d;MOV {0}+X,Y|d;DEC Y|;MOV A,Y|;CBNE {0}+X,{1}|dr;DAA A|
CLRV|;TCALL 14|;SET1 {0}.7|d;BBS {0}.7,{1}|dr;MOV A,{0}|d;MOV A,!{0}|a;MOV A,(X)|;MOV A,[{0}+X]|d;MOV A,#{0}|i;MOV X,!{0}|a;NOT1 {0}|m;MOV Y,{0}|d;MOV Y,!{0}|a;NOTC|;POP Y|;SLEEP|
BEQ {0}|r;TCALL 15|;CLR1 {0}.7|d;BBC {0}.7,{1}|dr;MOV A,{0}+X|d;MOV A,!{0}+X|a;MOV A,!{0}+Y|a;MOV A,[{0}]+Y|d;MOV X,{0}|d;MOV X,{0}+Y|d;MOV {1},{0}|dd;MOV Y,{0}+X|d;INC Y|;MOV Y,A|;DBNZ Y,{0}|r;STOP|
"""
OPS = []
for row in _T.strip().split('\n'):
    for ent in row.split(';'):
        t, k = ent.split('|')
        OPS.append((t, k))
assert len(OPS) == 256, len(OPS)
KSZ = {'d': 1, 'a': 2, 'i': 1, 'r': 1, 'm': 2, 'u': 1}


def length(op):
    return 1 + sum(KSZ[k] for k in OPS[op][1])


def disasm_one(ram, pc):
    op = ram[pc]
    t, kinds = OPS[op]
    vals = []
    p = pc + 1
    for k in kinds:
        if k in 'dir u'.replace(' ', ''):
            v = ram[p & 0xFFFF]
            p += 1
        else:
            v = ram[p & 0xFFFF] | ram[(p + 1) & 0xFFFF] << 8
            p += 2
        vals.append((k, v))
    out = []
    for k, v in vals:
        if k == 'r':
            tgt = (p + (v - 256 if v > 127 else v)) & 0xFFFF
            out.append('$%04X' % tgt)
        elif k == 'a':
            out.append('$%04X' % v)
        elif k == 'm':
            out.append('$%04X.%d' % (v & 0x1FFF, v >> 13))
        elif k == 'i':
            out.append('#$%02X' % v)
        else:
            out.append('$%02X' % v)
    s = t
    for i, o in enumerate(out):
        s = s.replace('{%d}' % i, o.replace('#', ''))
    s = s.replace('#{', '#')
    return p - pc, s


def main():
    ram = open(sys.argv[1], 'rb').read()
    a = int(sys.argv[2], 16)
    n = int(sys.argv[3], 16)
    end = a + n
    while a < end:
        ln, s = disasm_one(ram, a)
        print('%04X: %-9s %s' % (a, ram[a:a + ln].hex(), s))
        a += ln


if __name__ == '__main__':
    main()

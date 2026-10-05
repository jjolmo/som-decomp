import sys
import os
rom=None
def set_rom(r):
    global rom
    rom=r
def off(a): return a & 0x3FFFFF
# addressing modes: sizes
ops={}
def d(op,name,mode): ops[op]=(name,mode)
# build table
grp={
 'ORA':0x01,'AND':0x21,'EOR':0x41,'ADC':0x61,'STA':0x81,'LDA':0xA1,'CMP':0xC1,'SBC':0xE1}
m1=['(dp,X)','sr','dp','[dp]','#','abs','long','','(dp),Y','(dp)','(sr,S),Y','[dp],Y','abs,X'.replace('abs,X','dp,X'),'abs,Y','abs,X','long,X']
# standard 65816 layout of group1: low nibble patterns
g1={0x1:'(dp,X)',0x3:'sr,S',0x5:'dp',0x7:'[dp]',0x9:'#',0xD:'abs',0xF:'long',
    0x11:'(dp),Y',0x12:'(dp)',0x13:'(sr,S),Y',0x15:'dp,X',0x17:'[dp],Y',0x19:'abs,Y',0x1D:'abs,X',0x1F:'long,X'}
for n,b in grp.items():
    for lo,m in g1.items():
        op=(b&0xE0)|lo if False else None
for n,b in grp.items():
    base=b&0xE0
    for lo,m in g1.items():
        op=base|lo
        if n=='STA' and m=='#': continue
        ops[op]=(n,m)
# fix: mapping of lo with 0x10 bit: (dp),Y at 0x11, (dp) at 0x12, etc. base|lo works
rmw={'ASL':0x00,'ROL':0x20,'LSR':0x40,'ROR':0x60,'STX':0x80,'LDX':0xA0,'DEC':0xC0,'INC':0xE0}
for n,b in rmw.items():
    for lo,m in {0x6:'dp',0xE:'abs',0x16:'dp,X',0x1E:'abs,X'}.items():
        ops[b|lo]=(n,m)
    if n in('ASL','ROL','LSR','ROR','DEC','INC'): ops[b|0xA]=(n,'A')
ops[0x96]=('STX','dp,Y');ops[0xB6]=('LDX','dp,Y');ops[0xBE]=('LDX','abs,Y');ops[0x9E]=('STZ','abs,X')
ops[0xA2]=('LDX','#X');ops[0xA0]=('LDY','#X');ops[0xC0]=('CPY','#X');ops[0xE0]=('CPX','#X')
for n,b in {'STY':0x80,'LDY':0xA0,'CPY':0xC0,'CPX':0xE0}.items():
    for lo,m in {0x4:'dp',0xC:'abs'}.items(): ops[b|lo]=(n,m)
ops[0x94]=('STY','dp,X');ops[0xB4]=('LDY','dp,X');ops[0xBC]=('LDY','abs,X')
ops[0x64]=('STZ','dp');ops[0x74]=('STZ','dp,X');ops[0x9C]=('STZ','abs');ops[0x9E]=('STZ','abs,X')
ops[0x14]=('TRB','dp');ops[0x1C]=('TRB','abs');ops[0x04]=('TSB','dp');ops[0x0C]=('TSB','abs')
ops[0x24]=('BIT','dp');ops[0x2C]=('BIT','abs');ops[0x34]=('BIT','dp,X');ops[0x3C]=('BIT','abs,X');ops[0x89]=('BIT','#')
for n,o in {'BPL':0x10,'BMI':0x30,'BVC':0x50,'BVS':0x70,'BCC':0x90,'BCS':0xB0,'BNE':0xD0,'BEQ':0xF0,'BRA':0x80}.items(): ops[o]=(n,'rel')
ops[0x82]=('BRL','rel16')
imp={0x18:'CLC',0x38:'SEC',0x58:'CLI',0x78:'SEI',0xB8:'CLV',0xD8:'CLD',0xF8:'SED',0xAA:'TAX',0xA8:'TAY',0x8A:'TXA',0x98:'TYA',0xBA:'TSX',0x9A:'TXS',0x9B:'TXY',0xBB:'TYX',
0xCA:'DEX',0x88:'DEY',0xE8:'INX',0xC8:'INY',0xEA:'NOP',0x48:'PHA',0x68:'PLA',0x08:'PHP',0x28:'PLP',0xDA:'PHX',0xFA:'PLX',0x5A:'PHY',0x7A:'PLY',0x0B:'PHD',0x2B:'PLD',0x4B:'PHK',0x8B:'PHB',0xAB:'PLB',
0x60:'RTS',0x6B:'RTL',0x40:'RTI',0x1A:'INC A',0x3A:'DEC A',0x5B:'TCD',0x7B:'TDC',0x1B:'TCS',0x3B:'TSC',0xEB:'XBA',0xFB:'XCE',0xCB:'WAI',0xDB:'STP',0x0A:'ASL A',0x2A:'ROL A',0x4A:'LSR A',0x6A:'ROR A'}
for o,n in imp.items(): ops[o]=(n,'imp')
ops[0x20]=('JSR','abs');ops[0x22]=('JSL','long');ops[0x4C]=('JMP','abs');ops[0x5C]=('JML','long');ops[0x6C]=('JMP','(abs)');ops[0x7C]=('JMP','(abs,X)');ops[0xDC]=('JML','[abs]')
ops[0xFC]=('JSR','(abs,X)');ops[0xC2]=('REP','b');ops[0xE2]=('SEP','b');ops[0x54]=('MVN','mv');ops[0x44]=('MVP','mv');ops[0xF4]=('PEA','abs');ops[0xD4]=('PEI','dp');ops[0x62]=('PER','rel16')
ops[0x00]=('BRK','b');ops[0x02]=('COP','b');ops[0x42]=('WDM','b')
ops[0xA9]=('LDA','#');ops[0x29]=('AND','#');ops[0x09]=('ORA','#');ops[0x49]=('EOR','#');ops[0x69]=('ADC','#');ops[0xC9]=('CMP','#');ops[0xE9]=('SBC','#')
def dis(addr,n,m=1,x=1,stopRet=False):
    a=addr;end=addr+n
    while a<end:
        o=off(a);op=rom[o]
        if op not in ops: print(f'{a:06X}: {op:02X}  ??');a+=1;continue
        nm,mode=ops[op]
        if mode=='#': sz=1 if m else 2
        elif mode=='#X': sz=1 if x else 2
        elif mode in('imp','A'): sz=0
        elif mode in('dp','dp,X','dp,Y','(dp)','(dp),Y','[dp]','[dp],Y','(dp,X)','sr,S','(sr,S),Y','rel','b'): sz=1
        elif mode in('abs','abs,X','abs,Y','(abs)','(abs,X)','[abs]','rel16','mv'): sz=2
        elif mode in('long','long,X'): sz=3
        v=int.from_bytes(rom[o+1:o+1+sz],'little')
        bs=' '.join(f'{b:02X}' for b in rom[o:o+1+sz])
        if mode=='rel': t=(a+2+(v-256 if v>127 else v))&0xFFFFFF; s=f'${t:06X}'
        elif mode=='rel16': t=(a+3+(v-65536 if v>32767 else v))&0xFFFFFF; s=f'${t:06X}'
        elif sz==0: s='A' if mode=='A' else ''
        else:
            fmt={1:'${:02X}',2:'${:04X}',3:'${:06X}'}[sz].format(v)
            s=mode.replace('#X','#').replace('dp','').replace('abs','').replace('long','').replace('sr','')
            s={'#':'#'+fmt,'#X':'#'+fmt}.get(mode) or (mode.replace('dp',fmt).replace('abs',fmt).replace('long',fmt).replace('sr',fmt) if any(k in mode for k in('dp','abs','long','sr')) else fmt)
            if mode=='b': s='#'+fmt
        print(f'{a:06X}: {bs:<14}{nm} {s}')
        if nm=='REP': m = 0 if v&0x20 else m; x = 0 if v&0x10 else x
        if nm=='SEP': m = 1 if v&0x20 else m; x = 1 if v&0x10 else x
        a+=1+sz
        if stopRet and nm in('RTS','RTL'): break
if __name__=='__main__':
    import romio
    set_rom(romio.rom_from_argv())
    # usage: dis.py ROM HEXADDR HEXLEN [m x]   (HiROM address, e.g. C18015)
    a=int(sys.argv[1],16);n=int(sys.argv[2],16)
    m=int(sys.argv[3]) if len(sys.argv)>3 else 1
    x=int(sys.argv[4]) if len(sys.argv)>4 else 1
    dis(a,n,m,x)

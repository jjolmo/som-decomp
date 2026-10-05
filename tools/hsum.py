"""Summarize each AI-VM opcode handler: JSR targets + compare/branch instructions. usage: hsum.py ROM"""
import sys,struct,io,contextlib,romio,disasm65 as dis
d=romio.rom_from_argv(); dis.set_rom(d)
tbl=[struct.unpack_from('<H',d,0x12257+2*i)[0] for i in range(256)]
def text(addr):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf): dis.dis(0xC10000+addr,0x120,0,0,stopRet=True)
    return buf.getvalue().strip().split('\n')
seen={}
for op in range(256):
    h=tbl[op]
    if h==0x100: continue
    lines=text(h)
    s=[]
    for l in lines:
        m=l[22:].strip() if len(l)>22 else ''
        if m.startswith(('JSR','JMP','CMP','BNE','BEQ','BCS','BCC','AND','LDA #','LDA $D0','CPX')): s.append(m.replace('$','').replace(' ',''))
    print(f'{op:02X} {h:04X}: '+' ; '.join(s))

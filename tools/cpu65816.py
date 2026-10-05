import struct
ROM=b''
def set_rom(r):
    global ROM
    ROM=r
class Halt(Exception): pass
class CPU:
    def __init__(s):
        s.wram=bytearray(0x20000); s.sram=bytearray(0x2000)
        s.A=0;s.X=0;s.Y=0;s.S=0x1FFF;s.D=0;s.DB=0;s.PB=0;s.PC=0
        s.N=s.V=s.Z=s.C=0;s.M=1;s.XF=1;s.I=1;s.Dm=0;s.E=0
        s.hw={}  # hardware regs
        s.steps=0
        s.rng=None
        s.trace=None
        s.hooks={}
        s.wlog=None
    # memory
    def rd8(s,a):
        a&=0xFFFFFF;b=a>>16;o=a&0xFFFF
        if b==0x7E: return s.wram[o]
        if b==0x7F: return s.wram[0x10000+o]
        if (b<0x40 or 0x80<=b<0xC0):
            if o<0x2000: return s.wram[o]
            if 0x4200<=o<0x4400: return s.hwread(o)
            if 0x2000<=o<0x8000: return 0
            if b<0x40 and o>=0x8000 or True:
                if 0x6000<=o<0x8000 and 0x30<=(b&0x3f)<0x40: return s.sram[o-0x6000]
        # HiROM
        if b>=0xC0: return ROM[(a&0x3FFFFF)] if (a&0x3FFFFF)<len(ROM) else 0
        if o>=0x8000 and b<0x40: return ROM[(b<<16|o)] if (b<<16|o)<len(ROM) else 0
        if b>=0x40 and b<0x7E: return ROM[(a&0x3FFFFF)] if (a&0x3FFFFF)<len(ROM) else 0
        if b>=0x80: 
            bb=b-0x80
            if o>=0x8000: return ROM[(bb<<16|o)] if (bb<<16|o)<len(ROM) else 0
        return 0
    def hwread(s,o):
        if o==0x4214: return s.hw.get('q',0)&0xFF
        if o==0x4215: return (s.hw.get('q',0)>>8)&0xFF
        if o==0x4216: return s.hw.get('r',0)&0xFF
        if o==0x4217: return (s.hw.get('r',0)>>8)&0xFF
        return 0
    def wr8(s,a,v):
        a&=0xFFFFFF;b=a>>16;o=a&0xFFFF;v&=0xFF
        if s.wlog is not None and (b==0x7E or (b<0x40 and o<0x2000)): s.wlog.append((a,v))
        if b==0x7E: s.wram[o]=v;return
        if b==0x7F: s.wram[0x10000+o]=v;return
        if (b<0x40 or 0x80<=b<0xC0):
            if o<0x2000: s.wram[o]=v;return
            if 0x4200<=o<0x4400 or 0x2180<=o<=0x2183: s.hwwrite(o,v);return
            if 0x6000<=o<0x8000 and 0x30<=(b&0x3f): s.sram[o-0x6000]=v
    def hwwrite(s,o,v):
        h=s.hw
        if o==0x2180:
            a=h.get('wa',0); s.wram[a&0x1FFFF]=v; h['wa']=(a+1)&0x1FFFF; return
        if o==0x2181: h['wa']=(h.get('wa',0)&0x1FF00)|v; return
        if o==0x2182: h['wa']=(h.get('wa',0)&0x100FF)|(v<<8); return
        if o==0x2183: h['wa']=(h.get('wa',0)&0xFFFF)|((v&1)<<16); return
        if o==0x4202: h['m1']=v
        elif o==0x4203:
            h['r']=h.get('m1',0)*v; 
        elif o==0x4204: h['dl']=v
        elif o==0x4205: h['dh']=v
        elif o==0x4206:
            dd=h.get('dl',0)|h.get('dh',0)<<8
            if v==0: h['q']=0xFFFF;h['r']=dd
            else: h['q']=dd//v;h['r']=dd%v
    def rd16(s,a): return s.rd8(a)|s.rd8(a+1)<<8
    def wr16(s,a,v): s.wr8(a,v);s.wr8(a+1,v>>8)
    def rd24(s,a): return s.rd16(a)|s.rd8(a+2)<<16
    # helpers
    def fetch8(s):
        v=s.rd8(s.PB<<16|s.PC);s.PC=(s.PC+1)&0xFFFF;return v
    def fetch16(s): l=s.fetch8();return l|s.fetch8()<<8
    def fetch24(s): l=s.fetch16();return l|s.fetch8()<<16
    def push8(s,v): s.wr8(s.S,v);s.S=(s.S-1)&0xFFFF
    def pull8(s): s.S=(s.S+1)&0xFFFF;return s.rd8(s.S)
    def push16(s,v): s.push8(v>>8);s.push8(v)
    def pull16(s): l=s.pull8();return l|s.pull8()<<8
    def P(s): return (s.N<<7|s.V<<6|s.M<<5|s.XF<<4|s.Dm<<3|s.I<<2|s.Z<<1|s.C)
    def setP(s,p):
        s.N=p>>7&1;s.V=p>>6&1;s.M=p>>5&1;s.XF=p>>4&1;s.Dm=p>>3&1;s.I=p>>2&1;s.Z=p>>1&1;s.C=p&1
        if s.XF: s.X&=0xFF;s.Y&=0xFF
    # effective addresses
    def dp(s,off,idx=0):
        a=(s.D+off+idx)&0xFFFF if not s.E else (s.D+off+idx)&0xFFFF
        return a
    def ea(s,mode):
        xm=0xFF if s.XF else 0xFFFF
        if mode=='dp': return s.dp(s.fetch8())
        if mode=='dpx': return s.dp(s.fetch8(),s.X)
        if mode=='dpy': return s.dp(s.fetch8(),s.Y)
        if mode=='abs': return s.DB<<16|s.fetch16()
        if mode=='absx': return ((s.DB<<16|s.fetch16())+s.X)&0xFFFFFF
        if mode=='absy': return ((s.DB<<16|s.fetch16())+s.Y)&0xFFFFFF
        if mode=='long': return s.fetch24()
        if mode=='longx': return (s.fetch24()+s.X)&0xFFFFFF
        if mode=='(dp)': p=s.dp(s.fetch8()); return s.DB<<16|s.rd16(p)
        if mode=='(dp),y': p=s.dp(s.fetch8()); return ((s.DB<<16|s.rd16(p))+s.Y)&0xFFFFFF
        if mode=='(dpx)': p=s.dp(s.fetch8(),s.X); return s.DB<<16|s.rd16(p)
        if mode=='[dp]': p=s.dp(s.fetch8()); return s.rd24(p)
        if mode=='[dp],y': p=s.dp(s.fetch8()); return (s.rd24(p)+s.Y)&0xFFFFFF
        if mode=='sr': return (s.S+s.fetch8())&0xFFFF
        if mode=='(sr),y': p=(s.S+s.fetch8())&0xFFFF; return ((s.DB<<16|s.rd16(p))+s.Y)&0xFFFFFF
        raise Exception(mode)
    def ld(s,a,m8):
        return s.rd8(a) if m8 else s.rd16(a)
    def st(s,a,v,m8):
        if m8: s.wr8(a,v)
        else: s.wr16(a,v)
    def setnz(s,v,m8):
        if m8: v&=0xFF;s.N=v>>7;s.Z=int(v==0)
        else: v&=0xFFFF;s.N=v>>15;s.Z=int(v==0)
        return v
    def adc(s,v):
        if s.M:
            a=s.A&0xFF
            if s.Dm:
                lo=(a&0xF)+(v&0xF)+s.C
                if lo>9: lo+=6
                hi=(a>>4)+(v>>4)+(lo>0xF)
                if hi>9: hi+=6
                r=((hi<<4)|(lo&0xF));s.C=int(hi>0xF);s.V=0
                s.A=(s.A&0xFF00)|(r&0xFF);s.setnz(r,1);return
            r=a+v+s.C;s.V=int(((a^r)&(v^r)&0x80)!=0);s.C=int(r>0xFF)
            s.A=(s.A&0xFF00)|(r&0xFF);s.setnz(r,1)
        else:
            a=s.A
            r=a+v+s.C;s.V=int(((a^r)&(v^r)&0x8000)!=0);s.C=int(r>0xFFFF)
            s.A=r&0xFFFF;s.setnz(r,0)
    def sbc(s,v):
        if s.Dm: raise Exception('BCD sbc')
        if s.M: s.adc(v^0xFF)
        else: s.adc(v^0xFFFF)
    def cmp(s,r,v,m8):
        if m8: r&=0xFF;res=r-v
        else: r&=0xFFFF;res=r-v
        s.C=int(res>=0);s.setnz(res,m8)
    def branch(s,cond):
        o=s.fetch8()
        if cond:
            if o>127:o-=256
            s.PC=(s.PC+o)&0xFFFF
    def step(s):
        s.steps+=1
        pc=s.PB<<16|s.PC
        if s.hooks and pc in s.hooks:
            if s.hooks[pc](s): return
        if s.trace is not None: s.trace.append(pc)
        op=s.fetch8()
        M=s.M;XF=s.XF
        grp={0x01:'(dpx)',0x03:'sr',0x05:'dp',0x07:'[dp]',0x0D:'abs',0x0F:'long',0x11:'(dp),y',0x12:'(dp)',0x13:'(sr),y',0x15:'dpx',0x17:'[dp],y',0x19:'absy',0x1D:'absx',0x1F:'longx'}
        lo=op&0x1F; base=op&0xE0
        if op&0x03==1 or op&0x1F in (0x03,0x12,0x13,0x17,0x1F,0x07,0x0F,0x1D,0x19,0x15,0x11,0x0D,0x05) and False: pass
        # group1 ALU ops: opcodes where (op & 0x1F) in grp and base in 0x00,0x20,...,0xE0 excluding some
        g1=op&0x03
        if lo in grp and base in (0x00,0x20,0x40,0x60,0x80,0xA0,0xC0,0xE0) and not (op in (0x89,)) and (op&0x0F in (1,3,5,7,0xD,0xF) or op&0x1F in (0x11,0x12,0x13,0x15,0x17,0x19,0x1D,0x1F)):
            # exclude non-group1 ones sharing patterns (e.g. 0x0D? ora abs yes). Exclusions: 0x14? not in grp. 0x1D etc ok.
            nm=['ORA','AND','EOR','ADC','STA','LDA','CMP','SBC'][base>>5]
            mode=grp[lo]
            if nm=='STA' and False: pass
            a=s.ea(mode)
            m8=M
            if nm=='STA': s.st(a,s.A,m8);return
            v=s.ld(a,m8)
            s.alu(nm,v,m8);return
        if op in (0x09,0x29,0x49,0x69,0xA9,0xC9,0xE9):
            nm={0x09:'ORA',0x29:'AND',0x49:'EOR',0x69:'ADC',0xA9:'LDA',0xC9:'CMP',0xE9:'SBC'}[op]
            v=s.fetch8() if M else s.fetch16()
            s.alu(nm,v,M);return
        if op==0x89:
            v=s.fetch8() if M else s.fetch16()
            s.Z=int((s.A&v&(0xFF if M else 0xFFFF))==0);return
        # RMW/other
        sh={0x06:'dp',0x0E:'abs',0x16:'dpx',0x1E:'absx'}
        if (op&0x1F) in sh and op&0xE0 in (0x00,0x20,0x40,0x60,0xC0,0xE0):
            nm={0x00:'ASL',0x20:'ROL',0x40:'LSR',0x60:'ROR',0xC0:'DEC',0xE0:'INC'}[op&0xE0]
            a=s.ea(sh[op&0x1F]);v=s.ld(a,M);v=s.rmw(nm,v,M);s.st(a,v,M);return
        if op in (0x0A,0x2A,0x4A,0x6A,0x1A,0x3A):
            nm={0x0A:'ASL',0x2A:'ROL',0x4A:'LSR',0x6A:'ROR',0x1A:'INC',0x3A:'DEC'}[op]
            if M: v=s.rmw(nm,s.A&0xFF,1);s.A=(s.A&0xFF00)|v
            else: s.A=s.rmw(nm,s.A,0)
            return
        # branches
        br={0x10:lambda:not s.N,0x30:lambda:s.N,0x50:lambda:not s.V,0x70:lambda:s.V,0x90:lambda:not s.C,0xB0:lambda:s.C,0xD0:lambda:not s.Z,0xF0:lambda:s.Z,0x80:lambda:True}
        if op in br: s.branch(br[op]());return
        if op==0x82: o=s.fetch16(); s.PC=(s.PC+(o-65536 if o>32767 else o))&0xFFFF;return
        # jumps
        if op==0x4C: s.PC=s.fetch16();return
        if op==0x5C: a=s.fetch24();s.PC=a&0xFFFF;s.PB=a>>16;return
        if op==0x20: a=s.fetch16();s.push16((s.PC-1)&0xFFFF);s.PC=a;return
        if op==0x22: a=s.fetch24();s.push8(s.PB);s.push16((s.PC-1)&0xFFFF);s.PC=a&0xFFFF;s.PB=a>>16;return
        if op==0x60: s.PC=(s.pull16()+1)&0xFFFF;return
        if op==0x6B: s.PC=(s.pull16()+1)&0xFFFF;s.PB=s.pull8();return
        if op==0x6C: p=s.fetch16();s.PC=s.rd16(p);return
        if op==0x7C: p=(s.fetch16()+s.X)&0xFFFF;s.PC=s.rd16(s.PB<<16|p);return
        if op==0xFC: p=(s.fetch16()+s.X)&0xFFFF;s.push16((s.PC-1)&0xFFFF);s.PC=s.rd16(s.PB<<16|p);return
        if op==0xDC: p=s.fetch16();a=s.rd24(p);s.PC=a&0xFFFF;s.PB=a>>16;return
        # flags
        fl={0x18:('C',0),0x38:('C',1),0xB8:('V',0),0xD8:('Dm',0),0xF8:('Dm',1),0x58:('I',0),0x78:('I',1)}
        if op in fl: setattr(s,*fl[op]);return
        if op==0xC2: v=s.fetch8();s.setP(s.P()&~v);return
        if op==0xE2: v=s.fetch8();s.setP(s.P()|v);return
        if op==0xFB: 
            c=s.C;s.C=s.E;s.E=c;
            if s.E: s.M=1;s.XF=1
            return
        # transfers
        if op==0xAA: s.X=s.A&(0xFF if XF else 0xFFFF);s.setnz(s.X,XF);return
        if op==0xA8: s.Y=s.A&(0xFF if XF else 0xFFFF);s.setnz(s.Y,XF);return
        if op==0x8A:
            if M: s.A=(s.A&0xFF00)|(s.X&0xFF)
            else: s.A=s.X
            s.setnz(s.A,M);return
        if op==0x98:
            if M: s.A=(s.A&0xFF00)|(s.Y&0xFF)
            else: s.A=s.Y
            s.setnz(s.A,M);return
        if op==0x9B: s.Y=s.X;s.setnz(s.Y,XF);return
        if op==0xBB: s.X=s.Y;s.setnz(s.X,XF);return
        if op==0xBA: s.X=s.S&(0xFF if XF else 0xFFFF);s.setnz(s.X,XF);return
        if op==0x9A: s.S=s.X if not XF else (0x100|s.X);return
        if op==0x5B: s.D=s.A;s.setnz(s.D,0);return
        if op==0x7B: s.A=s.D;s.setnz(s.A,0);return
        if op==0x1B: s.S=s.A;return
        if op==0x3B: s.A=s.S;s.setnz(s.A,0);return
        if op==0xEB: s.A=((s.A&0xFF)<<8)|(s.A>>8);s.setnz(s.A&0xFF,1);return
        # inc/dec regs
        if op==0xE8: s.X=(s.X+1)&(0xFF if XF else 0xFFFF);s.setnz(s.X,XF);return
        if op==0xC8: s.Y=(s.Y+1)&(0xFF if XF else 0xFFFF);s.setnz(s.Y,XF);return
        if op==0xCA: s.X=(s.X-1)&(0xFF if XF else 0xFFFF);s.setnz(s.X,XF);return
        if op==0x88: s.Y=(s.Y-1)&(0xFF if XF else 0xFFFF);s.setnz(s.Y,XF);return
        # stack
        if op==0x48: 
            if M: s.push8(s.A)
            else: s.push16(s.A)
            return
        if op==0x68:
            if M: v=s.pull8();s.A=(s.A&0xFF00)|v;s.setnz(v,1)
            else: s.A=s.pull16();s.setnz(s.A,0)
            return
        if op==0xDA:
            if XF: s.push8(s.X)
            else: s.push16(s.X)
            return
        if op==0xFA:
            if XF: s.X=s.pull8();s.setnz(s.X,1)
            else: s.X=s.pull16();s.setnz(s.X,0)
            return
        if op==0x5A:
            if XF: s.push8(s.Y)
            else: s.push16(s.Y)
            return
        if op==0x7A:
            if XF: s.Y=s.pull8();s.setnz(s.Y,1)
            else: s.Y=s.pull16();s.setnz(s.Y,0)
            return
        if op==0x08: s.push8(s.P());return
        if op==0x28: s.setP(s.pull8());return
        if op==0x0B: s.push16(s.D);return
        if op==0x2B: s.D=s.pull16();s.setnz(s.D,0);return
        if op==0x8B: s.push8(s.DB);return
        if op==0xAB: s.DB=s.pull8();s.setnz(s.DB,1);return
        if op==0x4B: s.push8(s.PB);return
        if op==0xF4: v=s.fetch16();s.push16(v);return
        if op==0xD4: p=s.dp(s.fetch8());s.push16(s.rd16(p));return
        # LDX/LDY/STX/STY/CPX/CPY/STZ/BIT/TSB/TRB
        if op in (0xA2,0xA0):
            v=s.fetch8() if XF else s.fetch16()
            if op==0xA2:s.X=v;s.setnz(v,XF)
            else:s.Y=v;s.setnz(v,XF)
            return
        if op in (0xE0,0xC0):
            v=s.fetch8() if XF else s.fetch16();s.cmp(s.X if op==0xE0 else s.Y,v,XF);return
        ldx={0xA6:'dp',0xAE:'abs',0xB6:'dpy',0xBE:'absy'}
        ldy={0xA4:'dp',0xAC:'abs',0xB4:'dpx',0xBC:'absx'}
        if op in ldx: a=s.ea(ldx[op]);s.X=s.ld(a,XF);s.setnz(s.X,XF);return
        if op in ldy: a=s.ea(ldy[op]);s.Y=s.ld(a,XF);s.setnz(s.Y,XF);return
        stx={0x86:'dp',0x8E:'abs',0x96:'dpy'}
        sty={0x84:'dp',0x8C:'abs',0x94:'dpx'}
        if op in stx: a=s.ea(stx[op]);s.st(a,s.X,XF);return
        if op in sty: a=s.ea(sty[op]);s.st(a,s.Y,XF);return
        cpx={0xE4:'dp',0xEC:'abs'};cpy={0xC4:'dp',0xCC:'abs'}
        if op in cpx: a=s.ea(cpx[op]);s.cmp(s.X,s.ld(a,XF),XF);return
        if op in cpy: a=s.ea(cpy[op]);s.cmp(s.Y,s.ld(a,XF),XF);return
        stz={0x64:'dp',0x74:'dpx',0x9C:'abs',0x9E:'absx'}
        if op in stz: a=s.ea(stz[op]);s.st(a,0,M);return
        bit={0x24:'dp',0x2C:'abs',0x34:'dpx',0x3C:'absx'}
        if op in bit:
            a=s.ea(bit[op]);v=s.ld(a,M);s.Z=int((s.A&v&(0xFF if M else 0xFFFF))==0)
            s.N=v>>(7 if M else 15)&1;s.V=v>>(6 if M else 14)&1;return
        tsb={0x04:'dp',0x0C:'abs',0x14:'dp',0x1C:'abs'}
        if op in tsb:
            a=s.ea(tsb[op]);v=s.ld(a,M);m=0xFF if M else 0xFFFF
            s.Z=int((s.A&v&m)==0)
            if op in (0x04,0x0C): v|=s.A&m
            else: v&=~s.A&m
            s.st(a,v,M);return
        if op==0x54 or op==0x44:
            dst=s.fetch8();src=s.fetch8()
            s.DB=dst
            while True:
                s.wr8(dst<<16|s.Y,s.rd8(src<<16|s.X))
                if op==0x54: s.X=(s.X+1)&0xFFFF;s.Y=(s.Y+1)&0xFFFF
                else: s.X=(s.X-1)&0xFFFF;s.Y=(s.Y-1)&0xFFFF
                s.A=(s.A-1)&0xFFFF
                if s.A==0xFFFF:break
            return
        if op==0xEA: return
        if op==0x42: s.fetch8();return
        raise Exception(f'unimpl op {op:02X} at {pc:06X}')
    def alu(s,nm,v,m8):
        if nm=='LDA':
            if m8: s.A=(s.A&0xFF00)|v
            else: s.A=v
            s.setnz(v,m8)
        elif nm in('ORA','AND','EOR'):
            a=s.A&(0xFF if m8 else 0xFFFF)
            r={'ORA':a|v,'AND':a&v,'EOR':a^v}[nm]
            if m8: s.A=(s.A&0xFF00)|r
            else: s.A=r
            s.setnz(r,m8)
        elif nm=='ADC': s.adc(v)
        elif nm=='SBC': s.sbc(v)
        elif nm=='CMP': s.cmp(s.A,v,m8)
    def rmw(s,nm,v,m8):
        top=0x80 if m8 else 0x8000;mask=0xFF if m8 else 0xFFFF
        if nm=='ASL': s.C=int(v&top!=0);v=(v<<1)&mask
        elif nm=='LSR': s.C=v&1;v>>=1
        elif nm=='ROL': c=s.C;s.C=int(v&top!=0);v=((v<<1)|c)&mask
        elif nm=='ROR': c=s.C;s.C=v&1;v=(v>>1)|(top if c else 0)
        elif nm=='INC': v=(v+1)&mask
        elif nm=='DEC': v=(v-1)&mask
        s.setnz(v,m8);return v

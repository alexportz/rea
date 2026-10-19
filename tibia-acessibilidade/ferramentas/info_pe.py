"""Cabeçalho PE, seções (com entropia) e DLLs importadas. Uso: python -I info_pe.py client.exe"""
import struct,sys,math,collections
b=open(sys.argv[1],'rb').read()
pe=struct.unpack_from('<I',b,0x3c)[0]; mach,nsec,ts=struct.unpack_from('<HHI',b,pe+4); opt=pe+24
magic=struct.unpack_from('<H',b,opt)[0]; szopt=struct.unpack_from('<H',b,pe+20)[0]
ep=struct.unpack_from('<I',b,opt+16)[0]; ib=struct.unpack_from('<Q',b,opt+24)[0]
import datetime
print('machine',hex(mach),'PE32+' if magic==0x20b else 'PE32','timestamp',datetime.datetime.fromtimestamp(ts, datetime.timezone.utc),'entry',hex(ep),'imagebase',hex(ib))
dd=opt+112; dirs=[struct.unpack_from('<II',b,dd+8*i) for i in range(16)]
secs=[]
for i in range(nsec):
    o=pe+24+szopt+40*i; n=b[o:o+8].rstrip(b'\0').decode(); vs,va,rs,ra=struct.unpack_from('<IIII',b,o+8)
    d=b[ra:ra+rs]; c=collections.Counter(d); H=-sum(v/len(d)*math.log2(v/len(d)) for v in c.values()) if d else 0
    secs.append((n,va,vs,ra,rs)); print(f'  {n:8} va={va:#x} vsize={vs:#x} raw={rs:#x} entropia={H:.2f}')
def r2o(rva):
    for n,va,vs,ra,rs in secs:
        if va<=rva<va+max(vs,rs): return rva-va+ra
def cstr(o): return b[o:b.index(b'\0',o)].decode()
imp=dirs[1][0]; o=r2o(imp); dlls=[]
while True:
    ilt,_,_,name,iat=struct.unpack_from('<IIIII',b,o)
    if name==0: break
    dll=cstr(r2o(name)); cnt=0; p=r2o(ilt or iat)
    while struct.unpack_from('<Q',b,p)[0]: cnt+=1; p+=8
    dlls.append((dll,cnt)); o+=20
print('imports:',', '.join(f'{d}({c})' for d,c in dlls))
print('TLS dir',dirs[9], 'debug dir', dirs[6], 'cert', dirs[4])

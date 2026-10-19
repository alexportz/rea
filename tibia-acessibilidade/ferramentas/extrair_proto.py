"""Extrai os FileDescriptorProto embutidos no client.exe e gera .proto legíveis. Uso: python -I extrair_proto.py client.exe PASTA_SAIDA"""
import re,sys,os
data=open(sys.argv[1],'rb').read(); out=sys.argv[2]; os.makedirs(out,exist_ok=True)
def varint(b,i):
    r=s=0
    while True:
        if i>=len(b): raise ValueError
        c=b[i]; i+=1; r|=(c&0x7f)<<s; s+=7
        if not c&0x80: return r,i
        if s>70: raise ValueError
def fields(b):
    i=0; res=[]
    while i<len(b):
        k,i=varint(b,i); f,w=k>>3,k&7
        if w==0: v,i=varint(b,i)
        elif w==2:
            L,i=varint(b,i)
            if i+L>len(b): raise ValueError
            v=b[i:i+L]; i+=L
        elif w==5: v=b[i:i+4]; i+=4
        elif w==1: v=b[i:i+8]; i+=8
        else: raise ValueError
        res.append((f,w,v))
    return res
def scan_len(b,start):
    """percorre campos de topo de um FileDescriptorProto até achar campo inválido"""
    i=start; last=start
    valid={1,2,3,4,5,6,7,8,9,10,11,12,14,15}
    while i<len(b):
        try:
            k,j=varint(b,i); f,w=k>>3,k&7
            if f not in valid or w not in (0,2): break
            if w==0: _,j=varint(b,j)
            else:
                L,j=varint(b,j); j+=L
                if j>len(b): break
            i=j; last=i
        except ValueError: break
    return last
TYPES={1:'double',2:'float',3:'int64',4:'uint64',5:'int32',6:'fixed64',7:'fixed32',8:'bool',9:'string',12:'bytes',13:'uint32',15:'sfixed32',16:'sfixed64',17:'sint32',18:'sint64'}
LAB={1:'optional',2:'required',3:'repeated'}
def s(v): return v.decode('utf-8','replace')
def render_enum(b,ind):
    fs=fields(b); name=[s(v) for f,w,v in fs if f==1][0]
    o=[f"{ind}enum {name} {{"]
    for f,w,v in fs:
        if f==2:
            ef=fields(v); n=[s(x) for g,_,x in ef if g==1][0]; num=[x for g,_,x in ef if g==2]
            num=num[0] if num else 0
            if num>2**31: num-=2**64
            o.append(f"{ind}  {n} = {num};")
    o.append(ind+"}"); return o
def render_msg(b,ind):
    fs=fields(b); name=[s(v) for f,w,v in fs if f==1][0]
    o=[f"{ind}message {name} {{"]
    for f,w,v in fs:
        if f==2:
            ff=dict(); 
            for g,_,x in fields(v): ff.setdefault(g,x)
            t=TYPES.get(ff.get(5),None) or s(ff.get(6,b'?')).lstrip('.')
            lab=LAB.get(ff.get(4),'')
            o.append(f"{ind}  {lab} {t} {s(ff[1])} = {ff[3]};".replace('  ',' ',1) if False else f"{ind}  {lab} {t} {s(ff[1])} = {ff[3]};")
        elif f==3: o+=render_msg(v,ind+'  ')
        elif f==4: o+=render_enum(v,ind+'  ')
    o.append(ind+"}"); return o
n=0
for m in re.finditer(rb'\x0a([\x05-\x7f])([a-z_/]{1,100}\.proto)',data):
    if m.group(1)[0]!=len(m.group(2)): continue
    st=m.start(); en=scan_len(data,st); blob=data[st:en]
    try: fs=fields(blob)
    except ValueError: continue
    fname=s(fs[0][2]); pkg=[s(v) for f,w,v in fs if f==2]
    lines=[f'// extraído de client.exe offset 0x{st:x}, {len(blob)} bytes', 'syntax = "proto2";']
    if pkg: lines.append(f"package {pkg[0]};")
    for f,w,v in fs:
        if f==3: lines.append(f'import "{s(v)}";')
    try:
        for f,w,v in fs:
            if f==4: lines+=render_msg(v,'')
            elif f==5: lines+=render_enum(v,'')
    except Exception as e: lines.append(f'// erro ao renderizar: {e}')
    nm=fname.replace('/','_')
    open(os.path.join(out,f'{st:08x}_{nm}'),'w',encoding='utf-8').write('\n'.join(lines)+'\n'); n+=1
    print(hex(st),fname,pkg,len(blob))

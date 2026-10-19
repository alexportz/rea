"""Extrai os arquivos QML (interface) embutidos no client.exe. Uso: python -I extrair_qml.py client.exe PASTA_SAIDA"""
import sys,re,struct,os,zlib
data=open(sys.argv[1],"rb").read(); out=sys.argv[2]; os.makedirs(out,exist_ok=True)
# 1) blobs de texto com prefixo de tamanho big-endian (formato do rcc embutido)
found={}
for m in re.finditer(rb'import Qt',data):
    s=m.start()
    for back in range(0,4096):
        p=s-back
        if p<4: break
        L=struct.unpack('>I',data[p-4:p])[0]
        if back<=L<=3_000_000 and p+L<=len(data):
            blob=data[p:p+L]
            try: t=blob.decode('utf-8')
            except: continue
            if '\x00' in t: continue
            found[p]=t; break
# 2) blobs comprimidos com zlib (rcc usa qCompress: 4 bytes BE tamanho descompactado + zlib)
for m in re.finditer(rb'\x78[\x9c\xda\x01\x5e]',data):
    p=m.start()
    if p<8: continue
    try:
        d=zlib.decompressobj(); t=d.decompress(data[p:p+4_000_000])
    except Exception: continue
    if b'import Qt' in t[:4000]:
        try: found[p]=t.decode('utf-8')
        except: pass
print('blobs',len(found))
# 3) nomes de arquivos (tabela de nomes do rcc: UTF-16BE)
names=set(n.decode('utf-16-be') for n in re.findall(rb'(?:[\x00][A-Za-z0-9_.\-]){2,80}?\x00\.\x00q\x00m\x00l',data))
open(os.path.join(out,'_nomes_qml.txt'),'w').write('\n'.join(sorted(names)))
print('nomes',len(names))
for p,t in sorted(found.items()):
    m=re.search(r'^\s*(\w+)\s*\{',t,re.M)
    root=m.group(1) if m else 'x'
    ids=re.search(r'\bid:\s*(\w+)',t)
    fn=f"{p:08x}_{root}_{ids.group(1) if ids else ''}.qml"
    open(os.path.join(out,fn),'w',encoding='utf-8').write(t)

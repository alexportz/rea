"""Mostra as strings de metadados do Qt (moc: sinais, slots, Q_PROPERTY) de uma classe. Uso: python -I metadados_qt.py client.exe tibia::gamewindow::TStatusBarController"""
import sys,re
b=open(sys.argv[1],'rb').read()
for pat in sys.argv[2:]:
    for m in re.finditer(re.escape(pat.encode())+rb'\x00',b):
        s=m.start()
        # volta até o início do bloco de strings do moc
        p=s
        while p>0 and (32<=b[p-1]<127 or b[p-1]==0) and s-p<64: p-=1
        blk=b[p:s+3000]; parts=blk.split(b'\x00')
        out=[]
        for x in parts:
            if x and not all(32<=c<127 for c in x): break
            out.append(x.decode())
        print(f'== {pat} @0x{s:x}:',' | '.join(o for o in out[:120] if o)); print()

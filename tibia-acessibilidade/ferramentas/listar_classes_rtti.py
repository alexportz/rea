"""Lista os nomes de classe C++ do RTTI do MSVC (.?AV...@@) agrupados por namespace.
Uso: python -I listar_classes_rtti.py client.exe [filtro]"""
import collections
import re
import sys

data = open(sys.argv[1], "rb").read()
filtro = sys.argv[2].lower() if len(sys.argv) > 2 else ""
names = sorted(set(m.decode() for m in re.findall(rb"\.\?AV([A-Za-z0-9_@?]{3,160})@@", data)))
by_ns = collections.defaultdict(list)
for n in names:
    parts = n.split("@")
    cls, ns = parts[0], "::".join(reversed([p for p in parts[1:] if p]))
    if filtro in n.lower():
        by_ns[ns].append(cls)
for ns in sorted(by_ns):
    print(f"{ns or '(global)'} ({len(by_ns[ns])}): {', '.join(by_ns[ns][:40])}{' ...' if len(by_ns[ns]) > 40 else ''}")

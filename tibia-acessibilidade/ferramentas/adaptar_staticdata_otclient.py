"""Gera um staticdata.dat que o OTClient 4.1 consegue ler a partir do staticdata do client 15.33.

O 15.33 mudou o esquema do staticdata (o campo 2 de topo deixou de ser "Achievement"),
e o OTClient recusa o arquivo inteiro. Este script mantém só as entradas de topo
cujos campos batem com o esquema do OTClient (src/protobuf/staticdata.proto) e
descarta o resto. O arquivo original não é alterado.

Uso: python -I adaptar_staticdata_otclient.py <staticdata-original.dat> <saida.dat>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protowire import iter_fields  # noqa: E402

V, L = 0, 2  # wire types: varint e length-delimited
COLORS = {1: V, 2: V, 3: V, 4: V}
OUTFIT = {1: V, 2: (L, COLORS), 3: V, 4: V}
CREATURE = {1: V, 2: L, 3: (L, OUTFIT), 4: V}
ACHIEVEMENT = {1: V, 2: L, 3: L, 4: V}
POSITION = {1: V, 2: V, 3: V}
HOUSE = {1: V, 2: L, 3: L, 4: V, 5: V, 6: (L, POSITION), 7: V, 8: V, 9: L, 10: V}
QUEST = {1: V, 2: L}
TOP = {1: CREATURE, 2: ACHIEVEMENT, 3: HOUSE, 4: CREATURE, 5: QUEST}


def matches(buf, schema):
    try:
        for number, wire, value, _ in iter_fields(buf):
            expected = schema.get(number)
            if expected is None:
                continue  # campos desconhecidos são ignorados pelo protobuf
            if isinstance(expected, tuple):
                if wire != expected[0] or not matches(value, expected[1]):
                    return False
            elif wire != expected:
                return False
            elif wire == L:
                value.decode("utf-8")  # nestes esquemas todo campo L simples é string
        return True
    except (ValueError, UnicodeDecodeError):
        return False


def main():
    src, dst = sys.argv[1], sys.argv[2]
    data = open(src, "rb").read()
    out = bytearray()
    kept, dropped = {}, {}
    pos_list = list(iter_fields(data))
    for i, (number, wire, value, start) in enumerate(pos_list):
        end = pos_list[i + 1][3] if i + 1 < len(pos_list) else len(data)
        ok = number in TOP and wire == L and matches(value, TOP[number])
        (kept if ok else dropped)[number] = (kept if ok else dropped).get(number, 0) + 1
        if ok:
            out += data[start:end]
    open(dst, "wb").write(out)
    print(f"mantidos por campo: {kept}")
    print(f"descartados por campo: {dropped}")


if __name__ == "__main__":
    main()

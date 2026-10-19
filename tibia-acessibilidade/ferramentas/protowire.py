"""Leitor mínimo do formato de fio (wire format) do Protocol Buffers.

Usado para ler os assets do client (appearances.dat, staticdata.dat, map.dat...)
sem depender da biblioteca `protobuf`. Só lê; nunca escreve nada.
"""


def read_varint(buf, pos):
    result = shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("varint truncado")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("varint longo demais")


def iter_fields(buf):
    """Gera (numero_do_campo, wire_type, valor, offset_inicio) para cada campo."""
    pos = 0
    while pos < len(buf):
        start = pos
        key, pos = read_varint(buf, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = read_varint(buf, pos)
        elif wire == 1:
            value, pos = buf[pos:pos + 8], pos + 8
        elif wire == 2:
            length, pos = read_varint(buf, pos)
            value, pos = buf[pos:pos + length], pos + length
        elif wire == 5:
            value, pos = buf[pos:pos + 4], pos + 4
        else:
            raise ValueError(f"wire type {wire} não suportado no offset {start}")
        yield number, wire, value, start


def first(buf, number, default=None):
    for n, _, v, _ in iter_fields(buf):
        if n == number:
            return v
    return default


def all_of(buf, number):
    return [v for n, _, v, _ in iter_fields(buf) if n == number]


def packed_varints(value):
    out, pos = [], 0
    while pos < len(value):
        v, pos = read_varint(value, pos)
        out.append(v)
    return out

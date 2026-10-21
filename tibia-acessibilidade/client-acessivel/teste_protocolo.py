"""Teste rápido sem rede: codifica, cifra, decifra e confere a origem dos campos.

Uso: python -I teste_protocolo.py
"""
import ctypes
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocolo import (  # noqa: E402
    Frame, PlayerDataCurrent, build_frame, decode_player_data_current, encode_player_data_current, xtea,
)


def main():
    key = [0x01234567, 0x89ABCDEF, 0xFEDCBA98, 0x76543210]
    block = os.urandom(16)
    assert xtea(xtea(block, key), key, decrypt=True) == block

    values = {"health": 1234, "max_health": 1450, "free_capacity": 185_037, "mana": 999, "max_mana": 4220}
    for compress in (False, True):
        raw = build_frame(encode_player_data_current(values), key, sequence=42, compress=compress)
        frame = Frame(1, raw, key)
        target = PlayerDataCurrent()
        origins, end = decode_player_data_current(frame, 0, target)
        assert end == len(frame.payload), (end, len(frame.payload))
        for name, expected in values.items():
            o = origins[name]
            assert getattr(target, name) == expected
            # o endereço do campo aponta mesmo para o valor guardado na estrutura
            assert ctypes.c_uint32.from_address(o.struct_address).value == expected
            # e o endereço do buffer aponta para os bytes crus do pacote
            assert struct.unpack("<I", ctypes.string_at(o.buffer_address, 4))[0] == expected
        assert origins["health"].offset_in_message == 1
        assert origins["max_health"].offset_in_message == 5
        assert origins["free_capacity"].offset_in_message == 9
        assert origins["mana"].offset_in_message == 1 + 4 + 4 + 4 + 8 + 2 + 1 + 2 * 4
    print("ok: XTEA, enquadramento, zlib e origem dos campos conferidos")


if __name__ == "__main__":
    main()

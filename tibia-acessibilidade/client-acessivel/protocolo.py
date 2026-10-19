"""Protocolo de jogo usado pelo client acessível de demonstração.

Reproduz o *modelo* do protocolo de jogo do Tibia (enquadramento TCP, XTEA,
opcode + campos little-endian) para que cada valor exibido possa ser rastreado
até o byte de origem. O layout de PlayerDataCurrent (opcode 0xA0) segue o
servidor open source Canary e NÃO foi confirmado byte a byte no client 15.33;
veja docs/ANALISE_CLIENT_TIBIA.md, seção "O que é observado e o que é inferido".

Cada valor decodificado é guardado em uma estrutura ctypes, então os endereços
mostrados nos tooltips são endereços reais da memória DESTE processo.
"""
import ctypes
import struct
import zlib

DELTA = 0x9E3779B9
MASK = 0xFFFFFFFF
COMPRESSED_FLAG = 0x80000000

OPCODE_PLAYER_DATA_CURRENT = 0xA0


# --- XTEA (mesma cifra que o client importa do Crypto++: CryptoPP::XTEA) -----------

def _xtea_block(v0, v1, key, decrypt):
    if not decrypt:
        s = 0
        for _ in range(32):
            v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & MASK
            s = (s + DELTA) & MASK
            v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & MASK
    else:
        s = (DELTA * 32) & MASK
        for _ in range(32):
            v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & MASK
            s = (s - DELTA) & MASK
            v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & MASK
    return v0, v1


def xtea(data, key, decrypt=False):
    """Tibia usa palavras de 32 bits little-endian, blocos de 8 bytes, 32 rodadas."""
    if len(data) % 8:
        raise ValueError("XTEA exige múltiplos de 8 bytes")
    out = bytearray()
    for i in range(0, len(data), 8):
        v0, v1 = struct.unpack_from("<II", data, i)
        out += struct.pack("<II", *_xtea_block(v0, v1, key, decrypt))
    return bytes(out)


# --- Enquadramento ----------------------------------------------------------------
# [u16 tamanho][u32 sequência | flag de compressão][XTEA( u8 padding | payload | padding )]

def build_frame(payload, key, sequence, compress=False):
    if compress:
        c = zlib.compressobj(6, zlib.DEFLATED, -15)
        payload = c.compress(payload) + c.flush()
        sequence |= COMPRESSED_FLAG
    pad = (8 - (1 + len(payload)) % 8) % 8
    body = bytes([pad]) + payload + b"\x00" * pad
    encrypted = xtea(body, key)
    rest = struct.pack("<I", sequence) + encrypted
    return struct.pack("<H", len(rest)) + rest


class Frame:
    """Um quadro recebido, com o buffer decifrado mantido vivo em memória ctypes."""

    def __init__(self, number, raw, key):
        self.number = number
        self.raw = raw
        (self.sequence,) = struct.unpack_from("<I", raw, 2)
        self.compressed = bool(self.sequence & COMPRESSED_FLAG)
        decrypted = xtea(raw[6:], key, decrypt=True)
        pad = decrypted[0]
        payload = decrypted[1:len(decrypted) - pad]
        if self.compressed:
            payload = zlib.decompress(payload, -15)
        self.payload = payload
        # buffer em memória nativa: é daqui que os campos são lidos
        self.buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        self.buffer_address = ctypes.addressof(self.buffer)


def read_frames(sock_file_read):
    """Lê quadros de um socket: devolve bytes crus de um quadro por vez."""
    while True:
        head = sock_file_read(2)
        if len(head) < 2:
            return
        (size,) = struct.unpack("<H", head)
        rest = sock_file_read(size)
        if len(rest) < size:
            return
        yield head + rest


# --- PlayerDataCurrent (0xA0) -------------------------------------------------------

# (nome, formato struct, descrição, campo equivalente no client oficial)
PLAYER_DATA_CURRENT_FIELDS = [
    ("health", "I", "Vida atual", "TStatusBarController.currentHitpoints"),
    ("max_health", "I", "Vida máxima", "TStatusBarController.maxHitpoints"),
    ("free_capacity", "I", "Capacidade livre (centésimos de oz)", "TPlayerInventoryAndStatusController.capacity"),
    ("experience", "Q", "Experiência", "TStatusBarController.xpSkill"),
    ("level", "H", "Nível", "TStatusBarController.skillList"),
    ("level_percent", "B", "Percentual para o próximo nível", "TStatusBarController.skillList"),
    ("base_xp_gain", "H", "Taxa base de XP", "(Skills widget)"),
    ("xp_voucher", "H", "Bônus de voucher", "(Skills widget)"),
    ("low_level_bonus", "H", "Bônus de nível baixo", "(Skills widget)"),
    ("xp_boost", "H", "XP boost da loja", "(Skills widget)"),
    ("stamina_multiplier", "H", "Multiplicador de stamina", "(Skills widget)"),
    ("mana", "I", "Mana atual", "TStatusBarController.currentMana"),
    ("max_mana", "I", "Mana máxima", "TStatusBarController.maxMana"),
    ("soul", "B", "Soul points", "TPlayerInventoryAndStatusController.soulpoints"),
    ("stamina_minutes", "H", "Stamina em minutos", "(Skills widget)"),
    ("base_speed", "H", "Velocidade base", "(Skills widget)"),
    ("regeneration_seconds", "H", "Regeneração por comida (s)", "(Skills widget)"),
    ("offline_training_minutes", "H", "Treino offline (min)", "(Skills widget)"),
    ("xp_boost_seconds", "H", "Tempo restante de XP boost (s)", "(Skills widget)"),
    ("can_buy_xp_boost", "B", "Pode comprar XP boost", "(Skills widget)"),
    ("mana_shield", "I", "Escudo de mana atual", "TStatusBarController.manaShield"),
    ("max_mana_shield", "I", "Escudo de mana máximo", "TStatusBarController.maxManaShield"),
]

_CTYPE = {"I": ctypes.c_uint32, "Q": ctypes.c_uint64, "H": ctypes.c_uint16, "B": ctypes.c_uint8}


class PlayerDataCurrent(ctypes.Structure):
    """Estrutura do nosso client que guarda o último PlayerDataCurrent recebido."""
    _pack_ = 1
    _fields_ = [(name, _CTYPE[fmt]) for name, fmt, _, _ in PLAYER_DATA_CURRENT_FIELDS]


def encode_player_data_current(values):
    out = bytearray([OPCODE_PLAYER_DATA_CURRENT])
    for name, fmt, _, _ in PLAYER_DATA_CURRENT_FIELDS:
        out += struct.pack("<" + fmt, values.get(name, 0))
    return bytes(out)


class FieldOrigin:
    """De onde veio um valor: quadro, offsets, bytes crus e endereços de memória."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def decode_player_data_current(frame, message_offset, target):
    """Decodifica a mensagem 0xA0 que começa em `message_offset` do payload.

    Preenche `target` (PlayerDataCurrent) e devolve {campo: FieldOrigin}.
    """
    origins = {}
    pos = message_offset + 1
    struct_address = ctypes.addressof(target)
    for name, fmt, label, official in PLAYER_DATA_CURRENT_FIELDS:
        size = struct.calcsize(fmt)
        raw = bytes(frame.buffer[pos:pos + size])
        (value,) = struct.unpack("<" + fmt, raw)
        setattr(target, name, value)
        field_offset = getattr(PlayerDataCurrent, name).offset
        origins[name] = FieldOrigin(
            field=name,
            label=label,
            official=official,
            value=value,
            ctype=f"u{size * 8} little-endian",
            frame_number=frame.number,
            sequence=frame.sequence & ~COMPRESSED_FLAG,
            compressed=frame.compressed,
            frame_size=len(frame.raw),
            opcode=OPCODE_PLAYER_DATA_CURRENT,
            message_offset=message_offset,
            payload_offset=pos,
            offset_in_message=pos - message_offset,
            raw_hex=" ".join(f"{b:02X}" for b in raw),
            buffer_address=frame.buffer_address + pos,
            struct_address=struct_address + field_offset,
            struct_offset=field_offset,
        )
        pos += size
    return origins, pos

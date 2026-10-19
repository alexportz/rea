"""Análise estática dos assets do client oficial do Tibia (somente leitura).

Uso:
    python -I analisar_assets.py <pasta tibia/packages/Tibia> [--extrair-sprite N] [--saida PASTA]

O que faz:
  * lê assets/catalog-content.json (índice de todos os assets);
  * decodifica appearances.dat com o esquema appearances.proto extraído do client.exe;
  * descompacta uma folha de sprites (*.bmp.lzma) para mostrar o formato;
  * resume staticdata.dat / staticmapdata.dat / map.dat pelo formato de fio protobuf.

Nada é gravado dentro da pasta do client. Imagens extraídas vão para --saida
(por padrão tibia/_extraido, que fica fora do git por estar dentro de tibia/).
"""
import argparse
import collections
import json
import lzma
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protowire import all_of, first, iter_fields, packed_varints, read_varint  # noqa: E402

SPRITE_MAGIC = b"\x70\x0a\xfa\x80\x24"

# campos de appearances.proto (extraído de client.exe)
APPEARANCE_GROUPS = {1: "object", 2: "outfit", 3: "effect", 4: "missile"}
FLAG_NAMES = {
    2: "clip", 3: "bottom", 4: "top", 5: "container", 6: "cumulative", 7: "usable",
    13: "unpass", 14: "unmove", 15: "unsight", 18: "take", 20: "hang", 23: "light",
    36: "market", 40: "npcsaledata", 42: "corpse", 45: "ammo", 59: "dual_wielding",
}


def load_catalog(root):
    with open(os.path.join(root, "assets", "catalog-content.json"), encoding="utf-8") as f:
        return json.load(f)


def summarize_catalog(catalog):
    by_type = collections.Counter(e["type"] for e in catalog)
    sprites = [e for e in catalog if e["type"] == "sprite"]
    last_id = max(e["lastspriteid"] for e in sprites)
    sprite_types = collections.Counter(e["spritetype"] for e in sprites)
    return {"por_tipo": dict(by_type), "maior_sprite_id": last_id, "spritetype": dict(sprite_types)}


def summarize_appearances(path):
    data = open(path, "rb").read()
    counts = collections.Counter()
    flags = collections.Counter()
    named = []
    frame_groups = collections.Counter()
    for number, _, value, _ in iter_fields(data):
        group = APPEARANCE_GROUPS.get(number)
        if not group:
            continue
        counts[group] += 1
        app_id = first(value, 1)
        name = first(value, 4)
        fg = all_of(value, 2)
        frame_groups[len(fg)] += 1
        flag_buf = first(value, 3, b"")
        for fnum, _, _, _ in iter_fields(flag_buf):
            if fnum in FLAG_NAMES:
                flags[FLAG_NAMES[fnum]] += 1
        if group == "object" and name and len(named) < 8:
            sprite_ids = []
            if fg:
                info = first(fg[0], 3, b"")
                for sv in all_of(info, 5):
                    sprite_ids += packed_varints(sv) if isinstance(sv, bytes) else [sv]
            named.append({"id": app_id, "nome": name.decode("utf-8", "replace"), "sprites": sprite_ids[:4]})
    return {
        "bytes": len(data),
        "quantidade": dict(counts),
        "flags_mais_comuns": dict(flags.most_common(12)),
        "frame_groups_por_aparencia": dict(frame_groups),
        "exemplos": named,
    }


def decode_sprite_sheet(path):
    """Formato: zeros de preenchimento + assinatura 70 0A FA 80 24 + varint (tamanho)
    + stream LZMA 'alone' (5 bytes de propriedades + 8 bytes de tamanho + dados).
    O resultado é um BMP 384x384 com sprites 32x32, 32x64, 64x32 ou 64x64."""
    raw = open(path, "rb").read()
    pos = raw.index(SPRITE_MAGIC) + len(SPRITE_MAGIC)
    packed_size, pos = read_varint(raw, pos)
    props = raw[pos:pos + 5]
    lzma_stream = props + struct.pack("<q", -1) + raw[pos + 13:]
    bmp = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(lzma_stream)
    width, height = struct.unpack_from("<ii", bmp, 18)
    bpp = struct.unpack_from("<H", bmp, 28)[0]
    return {
        "padding_zeros": raw.index(SPRITE_MAGIC),
        "tamanho_compactado_declarado": packed_size,
        "lzma_props": props.hex(),
        "bmp_bytes": len(bmp),
        "bmp_assinatura": bmp[:2].decode(),
        "dimensoes": f"{width}x{abs(height)}",
        "bits_por_pixel": bpp,
    }, bmp


def summarize_protobuf_file(path, sample=3):
    data = open(path, "rb").read()
    top = collections.Counter()
    samples = collections.defaultdict(list)
    for number, wire, value, _ in iter_fields(data):
        top[number] += 1
        if wire == 2 and len(samples[number]) < sample:
            strings = []
            try:
                for n2, w2, v2, _ in iter_fields(value):
                    if w2 == 2:
                        try:
                            s = v2.decode("utf-8")
                            if s.isprintable() and len(s) > 2:
                                strings.append(s)
                        except UnicodeDecodeError:
                            pass
            except ValueError:
                pass
            samples[number].append(strings[:3])
    return {"bytes": len(data), "campos_de_topo": dict(top), "strings_exemplo": dict(samples)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--extrair-sprite", type=int, default=None, help="índice da folha de sprites a salvar como .bmp")
    ap.add_argument("--saida", default=None)
    args = ap.parse_args()

    catalog = load_catalog(args.root)
    files = {e["type"]: os.path.join(args.root, "assets", e["file"]) for e in catalog if e["type"] != "sprite"}
    report = {"catalogo": summarize_catalog(catalog)}
    report["appearances"] = summarize_appearances(files["appearances"])
    for kind in ("staticdata", "staticmapdata", "map"):
        report[kind] = summarize_protobuf_file(files[kind])

    sprites = [e for e in catalog if e["type"] == "sprite"]
    index = args.extrair_sprite if args.extrair_sprite is not None else 0
    entry = sprites[index]
    info, bmp = decode_sprite_sheet(os.path.join(args.root, "assets", entry["file"]))
    info.update({k: entry[k] for k in ("firstspriteid", "lastspriteid", "spritetype", "area")})
    report["folha_de_sprites_exemplo"] = info
    if args.extrair_sprite is not None:
        out_dir = args.saida or os.path.join(args.root, "..", "..", "_extraido")
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"sprites_{entry['firstspriteid']}-{entry['lastspriteid']}.bmp")
        with open(out, "wb") as f:
            f.write(bmp)
        report["folha_de_sprites_exemplo"]["salvo_em"] = os.path.abspath(out)

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()

"""Servidor de demonstração LOCAL (127.0.0.1) que envia PlayerDataCurrent.

Simula o lado servidor do protocolo para alimentar o client acessível sem tocar
nos servidores oficiais. Simplificação consciente: o client manda a chave XTEA
em texto puro no início da conexão (no jogo real ela vai cifrada com RSA dentro
do pacote de login).

Uso: python -I servidor_demo.py [--porta 7999]
"""
import argparse
import math
import os
import random
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocolo import build_frame, encode_player_data_current  # noqa: E402


def simulate(tick):
    max_health, max_mana = 1450, 4220
    health = int(max_health * (0.55 + 0.45 * abs(math.sin(tick / 9))))
    mana = int(max_mana * (0.3 + 0.7 * abs(math.cos(tick / 13))))
    cap = 185_000 - (tick * 137) % 40_000  # centésimos de oz
    return {
        "health": health, "max_health": max_health,
        "free_capacity": cap,
        "experience": 4_200_000 + tick * 350, "level": 87, "level_percent": (tick * 3) % 100,
        "base_xp_gain": 100, "low_level_bonus": 0, "xp_boost": 0,
        "stamina_multiplier": 150,
        "mana": mana, "max_mana": max_mana,
        "soul": 100, "stamina_minutes": 2520, "base_speed": 220,
        "regeneration_seconds": max(0, 600 - tick), "offline_training_minutes": 720,
        "xp_boost_seconds": 0, "can_buy_xp_boost": 1,
        "mana_shield": 0, "max_mana_shield": 0,
    }


def serve_client(conn, addr):
    with conn:
        key_bytes = conn.recv(16)
        if len(key_bytes) != 16:
            return
        key = [int.from_bytes(key_bytes[i:i + 4], "little") for i in range(0, 16, 4)]
        print(f"[servidor] {addr} conectado, chave XTEA recebida")
        sequence = 1
        try:
            while True:
                payload = encode_player_data_current(simulate(sequence))
                conn.sendall(build_frame(payload, key, sequence, compress=random.random() < 0.3))
                sequence += 1
                time.sleep(1.0)
        except OSError:
            print(f"[servidor] {addr} desconectado")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=7999)
    args = ap.parse_args()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.porta))
    srv.listen()
    print(f"[servidor] ouvindo em 127.0.0.1:{args.porta}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=serve_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()

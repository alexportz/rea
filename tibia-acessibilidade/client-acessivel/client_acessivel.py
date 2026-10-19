"""Client acessível de demonstração: Vida, Mana e CAP com a origem de cada valor.

Passe e segure o mouse sobre Vida, Mana ou CAP (ou foque com Tab e pressione
Enter/F1) para ver de onde o valor veio: quadro TCP, offset do byte, bytes crus,
endereço no buffer decifrado e endereço do campo na estrutura em memória deste
processo, além da cadeia equivalente no client oficial 15.33.

Por segurança este client só conecta em 127.0.0.1 (servidor_demo.py ou um
servidor de testes seu). Ele não lê memória de outros processos.

Uso: python -I client_acessivel.py [--porta 7999]
"""
import argparse
import ipaddress
import os
import queue
import socket
import sys
import threading
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocolo import (  # noqa: E402
    OPCODE_PLAYER_DATA_CURRENT, Frame, PlayerDataCurrent, decode_player_data_current, read_frames,
)

HOVER_DELAY_MS = 700

OFFICIAL_CHAIN = {
    "health": "QML healthAndMana.currentValueHitPoints  ←  TStatusBarController.currentHitpoints",
    "max_health": "QML healthAndMana.maxValueHitPoints  ←  TStatusBarController.maxHitpoints",
    "mana": "QML healthAndMana.currentValueMana  ←  TStatusBarController.currentMana",
    "max_mana": "QML healthAndMana.maxValueMana  ←  TStatusBarController.maxMana",
    "free_capacity": "QML inventorySidebarWidget.capacityValue  ←  panelController.capacity "
                     "(TPlayerInventoryAndStatusController.capacity, NOTIFY capacityChanged)",
}
OFFICIAL_PIPELINE = (
    "TGameserverTCPConnection → TGameserverNetworkPacketRawDataProcessor (XTEA/zlib) → "
    "TGameserverNetworkPacketSequenceFlowProcessor → TGameserverNetworkPacketReader → "
    "TProtocolReader/TProtobufServerMessageTranslator → GameserverMessagePlayerDataCurrent → "
    "TProtocolMessageQueue::receivedPlayerDataCurrentMessage → TPlayerProtocolMessageHandler → "
    "TPlayerData → controllers Qt (Q_PROPERTY) → QML"
)

STATS = [
    # (chave, rótulo, campo atual, campo máximo, cor)
    ("vida", "Vida", "health", "max_health", "#c62828"),
    ("mana", "Mana", "mana", "max_mana", "#1565c0"),
    ("cap", "CAP", "free_capacity", None, "#6d4c41"),
]


def require_loopback(host):
    addr = ipaddress.ip_address(socket.gethostbyname(host))
    if not addr.is_loopback:
        raise SystemExit("Este client de demonstração só conecta em 127.0.0.1.")


def network_thread(host, port, out_queue):
    key_words = [int.from_bytes(os.urandom(4), "little") for _ in range(4)]
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except OSError as exc:
        out_queue.put(("erro", f"Não foi possível conectar em {host}:{port}: {exc}"))
        return
    sock.settimeout(None)
    sock.sendall(b"".join(w.to_bytes(4, "little") for w in key_words))
    reader = sock.makefile("rb")
    number = 0
    target = PlayerDataCurrent()
    for raw in read_frames(reader.read):
        number += 1
        frame = Frame(number, raw, key_words)
        if frame.payload and frame.payload[0] == OPCODE_PLAYER_DATA_CURRENT:
            origins, _ = decode_player_data_current(frame, 0, target)
            # mantém o quadro vivo para que os endereços continuem válidos
            out_queue.put(("dados", frame, origins, target))
    out_queue.put(("erro", "Conexão encerrada pelo servidor."))


def describe(origin):
    o = origin
    end = o.buffer_address + len(o.raw_hex.split()) - 1
    return (
        f"Campo '{o.field}' ({o.label}) = {o.value}\n"
        f"  Rede: quadro TCP nº {o.frame_number}, sequência {o.sequence}, {o.frame_size} bytes, "
        f"compactado: {'sim' if o.compressed else 'não'}\n"
        f"  Mensagem 0x{o.opcode:02X} PlayerDataCurrent no offset {o.message_offset} do payload decifrado\n"
        f"  Campo no offset +{o.offset_in_message} da mensagem (payload[{o.payload_offset}]), {o.ctype}\n"
        f"  Bytes crus: {o.raw_hex}\n"
        f"  Memória (este processo): buffer decifrado 0x{o.buffer_address:016X}..0x{end:016X}\n"
        f"  Memória (este processo): PlayerDataCurrent.{o.field} em 0x{o.struct_address:016X} "
        f"(offset {o.struct_offset} na estrutura)\n"
        f"  Client oficial: {OFFICIAL_CHAIN.get(o.field, o.official)}"
    )


class HoverHoldTooltip:
    """Mostra o tooltip quando o mouse fica parado sobre o widget por HOVER_DELAY_MS."""

    def __init__(self, widget, text_fn, children=()):
        self.widget, self.text_fn = widget, text_fn
        self.after_id = None
        self.tip = None
        self.label = None
        for w in (widget, *children):
            w.bind("<Enter>", self._schedule, add="+")
            w.bind("<Motion>", self._schedule, add="+")
            w.bind("<Leave>", self._maybe_hide, add="+")
            w.bind("<ButtonPress>", self.hide, add="+")

    def _maybe_hide(self, event):
        # passar do quadro para um filho não conta como sair
        inside = self.widget.winfo_containing(event.x_root, event.y_root)
        while inside is not None and inside is not self.widget:
            inside = inside.master
        if inside is None:
            self.hide()

    def _schedule(self, _event=None):
        if self.tip:
            return
        if self.after_id:
            self.widget.after_cancel(self.after_id)
        self.after_id = self.widget.after(HOVER_DELAY_MS, self.show)

    def show(self):
        self.after_id = None
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        self.label = tk.Label(self.tip, text=self.text_fn(), justify="left", font=("Consolas", 10),
                              background="#fffde7", foreground="#000000", relief="solid", borderwidth=1,
                              padx=8, pady=6, wraplength=self.widget.winfo_toplevel().winfo_width() - 60)
        self.label.pack()

    def refresh(self):
        if self.label:
            self.label.config(text=self.text_fn())

    def hide(self, _event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tip:
            self.tip.destroy()
            self.tip = self.label = None


class App:
    def __init__(self, root, host, port):
        self.root = root
        self.queue = queue.Queue()
        self.origins = {}
        self.frame = None  # mantém o último quadro (e seu buffer) vivo
        self.target = None
        root.title("Tibia - client acessível (demonstração)")
        root.configure(background="#121212")
        style = ttk.Style(root)
        style.theme_use("clam")

        tk.Label(root, text="Passe e segure o mouse sobre um valor, ou use Tab + Enter, para ver a origem.",
                 background="#121212", foreground="#ffffff", font=("Segoe UI", 11)).pack(anchor="w", padx=12, pady=(10, 4))

        self.rows = {}
        self.tooltips = []
        for key, label, cur, mx, color in STATS:
            row = tk.Frame(root, background="#1e1e1e", highlightthickness=3, highlightcolor="#ffd600",
                           highlightbackground="#1e1e1e", takefocus=1)
            row.pack(fill="x", padx=12, pady=4)
            name = tk.Label(row, text=label, width=6, anchor="w", background="#1e1e1e", foreground="#ffffff",
                            font=("Segoe UI", 18, "bold"))
            name.pack(side="left", padx=8, pady=6)
            bar = tk.Canvas(row, width=320, height=26, background="#333333", highlightthickness=0)
            bar.pack(side="left", padx=8)
            value = tk.Label(row, text="—", width=14, anchor="w", background="#1e1e1e", foreground="#ffffff",
                             font=("Segoe UI", 18))
            value.pack(side="left", padx=8)
            self.rows[key] = (row, bar, value, cur, mx, color)
            text_fn = (lambda c=cur, m=mx: self.provenance(c, m))
            self.tooltips.append(HoverHoldTooltip(row, text_fn, children=(name, bar, value)))
            for seq in ("<Return>", "<F1>", "<space>"):
                row.bind(seq, lambda _e, c=cur, m=mx: self.show_details(c, m))
            row.bind("<FocusIn>", lambda _e, c=cur, m=mx: self.show_details(c, m))

        tk.Label(root, text="Detalhes (somente leitura, pode selecionar e copiar):", background="#121212",
                 foreground="#ffffff", font=("Segoe UI", 11)).pack(anchor="w", padx=12, pady=(10, 0))
        self.details = tk.Text(root, height=16, width=120, font=("Consolas", 10), background="#000000",
                               foreground="#e0e0e0", insertbackground="#ffffff", wrap="word")
        self.details.pack(fill="both", expand=True, padx=12, pady=(2, 6))
        self.details.insert("1.0", "Cadeia no client oficial 15.33:\n" + OFFICIAL_PIPELINE)
        self.details.config(state="disabled")
        self.status = tk.Label(root, text=f"Conectando em {host}:{port}...", background="#121212",
                               foreground="#bdbdbd", font=("Segoe UI", 10))
        self.status.pack(anchor="w", padx=12, pady=(0, 10))
        self.detail_fields = None

        threading.Thread(target=network_thread, args=(host, port, self.queue), daemon=True).start()
        root.after(100, self.poll)

    def provenance(self, cur, mx):
        if cur not in self.origins:
            return "Ainda não chegou nenhum PlayerDataCurrent (0xA0)."
        parts = [describe(self.origins[cur])]
        if mx:
            parts.append(describe(self.origins[mx]))
        if cur == "free_capacity":
            parts.append("  Exibição: valor / 100 = oz (o servidor envia centésimos de onça)")
        return "\n\n".join(parts)

    def show_details(self, cur, mx):
        self.detail_fields = (cur, mx)
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", self.provenance(cur, mx) + "\n\nCadeia no client oficial 15.33:\n" + OFFICIAL_PIPELINE)
        self.details.config(state="disabled")

    def poll(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item[0] == "erro":
                    self.status.config(text=item[1])
                else:
                    _, self.frame, self.origins, self.target = item
                    self.render()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def render(self):
        t = self.target
        for key, (row, bar, value, cur, mx, color) in self.rows.items():
            current = getattr(t, cur)
            if mx:
                maximum = max(1, getattr(t, mx))
                fraction = current / maximum
                text = f"{current} / {maximum}"
            else:
                fraction = min(1.0, current / 200_000)
                text = f"{current / 100:.2f} oz"
            bar.delete("all")
            bar.create_rectangle(0, 0, int(320 * fraction), 26, fill=color, width=0)
            value.config(text=text)
        o = self.origins["health"]
        self.status.config(text=f"Último quadro: nº {o.frame_number}, sequência {o.sequence}, "
                                f"{o.frame_size} bytes, compactado: {'sim' if o.compressed else 'não'}")
        for tip in self.tooltips:
            tip.refresh()
        if self.detail_fields:
            self.show_details(*self.detail_fields)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=7999)
    args = ap.parse_args()
    require_loopback(args.host)
    root = tk.Tk()
    App(root, args.host, args.porta)
    root.mainloop()


if __name__ == "__main__":
    main()

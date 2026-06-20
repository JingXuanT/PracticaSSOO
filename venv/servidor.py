import http.server
import json
import os
import random
import string
import threading
import time
import uuid
from urllib.parse import urlparse, parse_qs

HOST_HTTP = "0.0.0.0"
PUERTO_HTTP = 5000

TIEMPO_BLOQUEO_CATEGORIA = 20
TIEMPO_LIMITE_PARTIDA = 60

CATEGORIAS = ["Nombre", "Apellido", "Ciudad", "País", "Animal", "Comida", "Marca", "Color"]

RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_INDEX = os.path.join(RAIZ, "templates", "juego.html")

partidas = {}
bloqueo_partidas = threading.Lock()


class Partida:
    def __init__(self, id_partida):
        self.id_partida = id_partida
        self.jugadores = {}
        self.tablero = {cat: {"value": "", "locked_by": None, "lock_until": 0} for cat in CATEGORIAS}
        self.letra = ""
        self.iniciada = False
        self.terminada = False
        self.hora_inicio = 0
        self.razon_fin = None
        self.bloqueo = threading.Lock()

    def unir(self, nombre):
        player_id = uuid.uuid4().hex[:8]
        with self.bloqueo:
            self.jugadores[player_id] = nombre
        return player_id

    def empezar(self):
        with self.bloqueo:
            if self.iniciada:
                return False
            self.letra = random.choice(string.ascii_uppercase)
            self.iniciada = True
            self.hora_inicio = time.time()
        t = threading.Timer(TIEMPO_LIMITE_PARTIDA, self.terminar, args=("TIEMPO_AGOTADO",))
        t.daemon = True
        t.start()
        return True

    def bloquear(self, player_id, categoria):
        if not self.iniciada or self.terminada:
            return False, "La partida no está activa"
        if categoria not in self.tablero:
            return False, "Categoría inválida"
        with self.bloqueo:
            entrada = self.tablero[categoria]
            ahora = time.time()
            if entrada["value"]:
                return False, "Ya tiene valor"
            if entrada["locked_by"] and entrada["locked_by"] != player_id and ahora < entrada["lock_until"]:
                nombre = self.jugadores.get(entrada["locked_by"], "otro jugador")
                return False, f"Bloqueada por {nombre}"
            entrada["locked_by"] = player_id
            entrada["lock_until"] = ahora + TIEMPO_BLOQUEO_CATEGORIA
        return True, ""

    def rellenar(self, player_id, categoria, valor):
        if not self.iniciada or self.terminada:
            return False, "La partida no está activa"
        if categoria not in self.tablero:
            return False, "Categoría inválida"
        valor = valor.strip()
        if not valor:
            return False, "Valor vacío"
        if not valor.upper().startswith(self.letra):
            return False, f"Debe empezar por '{self.letra}'"
        with self.bloqueo:
            entrada = self.tablero[categoria]
            if entrada["value"]:
                return False, "Ya tiene valor"
            if entrada["locked_by"] != player_id:
                return False, "No tienes el bloqueo"
            entrada["value"] = valor
            entrada["locked_by"] = None
            entrada["lock_until"] = 0
            completado = all(e["value"] for e in self.tablero.values())
        if completado:
            self.terminar("TABLERO_COMPLETO")
        return True, ""

    def terminar(self, razon):
        with self.bloqueo:
            if self.terminada:
                return
            self.terminada = True
            self.razon_fin = razon

    def estado(self, player_id=None):
        ahora = time.time()
        tablero = {}
        for cat, e in self.tablero.items():
            bloqueada_activa = e["locked_by"] and ahora < e["lock_until"]
            tablero[cat] = {
                "value": e["value"],
                "locked_by": self.jugadores.get(e["locked_by"]) if bloqueada_activa else None,
                "locked_by_me": bool(bloqueada_activa and e["locked_by"] == player_id),
            }
        tiempo_restante = None
        if self.iniciada and not self.terminada:
            tiempo_restante = max(0, int(TIEMPO_LIMITE_PARTIDA - (ahora - self.hora_inicio)))
        return {
            "game_id": self.id_partida,
            "started": self.iniciada,
            "finished": self.terminada,
            "letter": self.letra,
            "board": tablero,
            "players": list(self.jugadores.values()),
            "time_left": tiempo_restante,
            "reason": self.razon_fin,
        }


def crear_partida():
    id_partida = uuid.uuid4().hex[:6].upper()
    p = Partida(id_partida)
    with bloqueo_partidas:
        partidas[id_partida] = p
    return p


def obtener_partida(id_partida):
    with bloqueo_partidas:
        return partidas.get(id_partida.upper())


class ManejadorStop(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[HTTP] {fmt % args}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _html(self):
        try:
            with open(RUTA_INDEX, "rb") as f:
                cuerpo = f.read()
        except FileNotFoundError:
            self._json(500, {"status": "error", "msg": "index.html no encontrado"})
            return
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        analizada = urlparse(self.path)
        ruta = analizada.path.rstrip("/")
        qs = parse_qs(analizada.query)

        if ruta == "" or ruta == "/index.html":
            self._html()
            return

        if ruta == "/stop/new":
            p = crear_partida()
            self._json(200, {"status": "ok", "game_id": p.id_partida})
            return

        if ruta == "/stop":
            with bloqueo_partidas:
                info = {gid: {"started": p.iniciada, "finished": p.terminada,
                               "players": list(p.jugadores.values())}
                        for gid, p in partidas.items()}
            self._json(200, {"status": "ok", "games": info})
            return

        partes = ruta.split("/")

        if len(partes) == 4 and partes[1] == "stop" and partes[3] == "estado":
            p = obtener_partida(partes[2])
            if not p:
                self._json(404, {"status": "error", "msg": "Partida no encontrada"})
                return
            player_id = qs.get("player_id", [None])[0]
            self._json(200, p.estado(player_id))
            return

        if len(partes) == 3 and partes[1] == "stop":
            p = obtener_partida(partes[2])
            if not p:
                self._json(404, {"status": "error", "msg": "Partida no encontrada"})
                return
            self._json(200, p.estado())
            return

        self._json(404, {"status": "error", "msg": "Ruta no encontrada"})

    def do_POST(self):
        analizada = urlparse(self.path)
        ruta = analizada.path.rstrip("/")
        partes = ruta.split("/")

        longitud = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(longitud) if longitud else b"{}"
        try:
            cuerpo = json.loads(crudo.decode() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"status": "error", "msg": "JSON inválido"})
            return

        if len(partes) != 4 or partes[1] != "stop":
            self._json(404, {"status": "error", "msg": "Ruta no encontrada"})
            return

        p = obtener_partida(partes[2])
        if not p:
            self._json(404, {"status": "error", "msg": "Partida no encontrada"})
            return

        accion = partes[3]

        if accion == "unirse":
            nombre = cuerpo.get("name", "").strip()
            if not nombre:
                self._json(400, {"status": "error", "msg": "Nombre vacío"})
                return
            if p.iniciada:
                self._json(400, {"status": "error", "msg": "La partida ya ha comenzado"})
                return
            player_id = p.unir(nombre)
            self._json(200, {"status": "ok", "player_id": player_id})
            return

        if accion == "empezar":
            ok = p.empezar()
            self._json(200, {"status": "ok" if ok else "error",
                              "msg": "" if ok else "La partida ya ha empezado"})
            return

        if accion == "bloquear":
            player_id = cuerpo.get("player_id", "")
            categoria = cuerpo.get("category", "")
            ok, razon = p.bloquear(player_id, categoria)
            self._json(200, {"status": "ok" if ok else "error", "msg": razon})
            return

        if accion == "rellenar":
            player_id = cuerpo.get("player_id", "")
            categoria = cuerpo.get("category", "")
            valor = cuerpo.get("value", "")
            ok, razon = p.rellenar(player_id, categoria, valor)
            self._json(200, {"status": "ok" if ok else "error", "msg": razon})
            return

        self._json(404, {"status": "error", "msg": "Acción no reconocida"})


class ServidorStop(http.server.ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    print("   SERVIDOR WEB STOP!")
    print(f"  http://{HOST_HTTP}:{PUERTO_HTTP}")
    servidor = ServidorStop((HOST_HTTP, PUERTO_HTTP), ManejadorStop)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Servidor detenido")
        servidor.shutdown()

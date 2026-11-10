import argparse
import os
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

CARPETA = os.path.dirname(os.path.abspath(__file__))
HEADERS_A_REENVIAR = ("Content-Type", "Authorization", "Accept")


class Handler(SimpleHTTPRequestHandler):
    api = "http://127.0.0.1:8000"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CARPETA, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api"):
            return self.reenviar()
        return super().do_GET()

    def do_POST(self):
        return self.reenviar() if self.path.startswith("/api") else self.send_error(404)

    def do_PUT(self):
        return self.reenviar() if self.path.startswith("/api") else self.send_error(404)

    def do_PATCH(self):
        return self.reenviar() if self.path.startswith("/api") else self.send_error(404)

    def do_DELETE(self):
        return self.reenviar() if self.path.startswith("/api") else self.send_error(404)

    def reenviar(self):
        destino = self.api + (self.path[len("/api"):] or "/")
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo) if largo else None
        headers = {h: self.headers[h] for h in HEADERS_A_REENVIAR if self.headers.get(h)}
        pedido = urllib.request.Request(destino, data=cuerpo, headers=headers, method=self.command)

        try:
            with urllib.request.urlopen(pedido, timeout=30) as r:
                self.responder(r.status, r.headers.get("Content-Type"), r.read())
        except urllib.error.HTTPError as e:  # 4xx / 5xx de la API: se pasan tal cual
            self.responder(e.code, e.headers.get("Content-Type"), e.read())
        except (urllib.error.URLError, OSError):
            self.responder(
                502, "application/json",
                f'{{"detail": "El backend no responde en {self.api}. ¿Está corriendo uvicorn?"}}'.encode(),
            )

    def responder(self, status, tipo, cuerpo):
        self.send_response(status)
        self.send_header("Content-Type", tipo or "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--puerto", type=int, default=5500)
    a = p.parse_args()
    Handler.api = a.api.rstrip("/")
    print(f"Frontend en http://127.0.0.1:{a.puerto}  →  API en {Handler.api}")
    ThreadingHTTPServer(("127.0.0.1", a.puerto), Handler).serve_forever()

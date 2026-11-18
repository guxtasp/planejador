import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ["APP_ENV"] = "production"

from planner import create_app  # noqa: E402


def _restaurar_caminho_vercel(wsgi_app):
    def middleware(environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        if path_info in ("/api/index", "/api/index.py"):
            qs = environ.get("QUERY_STRING", "")
            pares = parse_qsl(qs, keep_blank_values=True)
            caminho = None
            restantes = []
            for chave, valor in pares:
                if chave == "__path" and caminho is None:
                    caminho = valor
                else:
                    restantes.append((chave, valor))

            if caminho is not None:
                environ["QUERY_STRING"] = urlencode(restantes, doseq=True)
            else:
                matches = dict(
                    parse_qsl(
                        environ.get("HTTP_X_NOW_ROUTE_MATCHES", ""),
                        keep_blank_values=True,
                    )
                )
                if "1" in matches:
                    caminho = "/" + unquote(matches["1"]).lstrip("/")

            environ["PATH_INFO"] = "/" + (caminho or "/").lstrip("/")
        return wsgi_app(environ, start_response)

    return middleware


app = create_app()
app.wsgi_app = _restaurar_caminho_vercel(app.wsgi_app)
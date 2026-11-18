"""
Defesa contra CSRF (requisição forjada por outro site) — Etapa 5A.

Com login por cookie, um site malicioso poderia fazer o navegador da vítima
enviar um POST ao nosso servidor. Duas camadas barram isso:
  1. cookie de sessão `SameSite=Lax` (config): o navegador não o envia em POST
     vindo de outro site;
  2. este filtro: todo método que altera dados precisa vir DESTE site, conforme
     os cabeçalhos `Sec-Fetch-Site` e `Origin`, que o navegador preenche e que o
     código da página de terceiros não consegue forjar.

Clientes que não são navegadores (testes, `curl`) não mandam esses cabeçalhos e
passam; eles não carregam o cookie de ninguém, então não são o alvo do ataque.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from flask import Flask, request

from .errors import ProibidoError

METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
# `Sec-Fetch-Site`: "same-origin" (nossa página) e "none" (digitado/favorito) são legítimos.
_SEC_FETCH_OK = frozenset({"same-origin", "none"})


def origem_permitida(metodo: str, host: str, origin: str | None, sec_fetch_site: str | None) -> bool:
    """Regra pura: a requisição pode alterar dados? (`host` é o do próprio servidor.)"""
    if metodo.upper() in METODOS_SEGUROS:
        return True
    if sec_fetch_site is not None:
        return sec_fetch_site in _SEC_FETCH_OK
    if origin is not None:
        # Compara só o host:porta; atrás de proxy TLS o esquema visto pelo Flask pode diferir.
        return origin != "null" and urlsplit(origin).netloc == host
    return True


def registrar_verificacao_de_origem(app: Flask) -> None:
    @app.before_request
    def _verificar_origem():
        if not origem_permitida(request.method, request.host,
                                request.headers.get("Origin"), request.headers.get("Sec-Fetch-Site")):
            raise ProibidoError("Requisição de origem não permitida.")

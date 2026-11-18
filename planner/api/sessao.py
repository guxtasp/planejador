"""
Sessão do usuário (Etapa 5A): quem está logado nesta requisição.

A sessão é o cookie assinado do Flask com o id da conta (`session["usuario_id"]`).
Um filtro `before_request` lê o cookie, confere a conta no banco e deixa o
resultado em `g.usuario`; as rotas usam `usuario_atual_id()` e os decoradores
`login_obrigatorio` (API: 401 JSON) e `login_obrigatorio_pagina` (página: redireciona).
"""
from __future__ import annotations

from functools import wraps
from urllib.parse import quote

from flask import Flask, current_app, g, redirect, request, session

from ..services.auth import AutenticacaoService, criar_autenticacao
from .errors import NaoAutenticadoError

CHAVE = "usuario_id"
EXTENSAO = "autenticacao"   # chave em `app.extensions`


def servico_de_autenticacao() -> AutenticacaoService:
    """O serviço da aplicação atual (criado uma vez em `create_app`; sem estado por requisição)."""
    return current_app.extensions[EXTENSAO]


def iniciar_sessao(usuario_id: int) -> None:
    """Abre a sessão. Limpa antes, para nunca herdar dados de uma sessão anterior."""
    session.clear()
    session[CHAVE] = usuario_id
    session.permanent = True      # respeita PERMANENT_SESSION_LIFETIME


def encerrar_sessao() -> None:
    session.clear()


def usuario_atual() -> dict | None:
    """`{id, email, nome}` da conta logada, ou `None` (visitante)."""
    return g.get("usuario")


def usuario_atual_id() -> int | None:
    usuario = usuario_atual()
    return usuario["id"] if usuario else None


def registrar_carregamento_do_usuario(app: Flask) -> None:
    app.extensions[EXTENSAO] = criar_autenticacao(app.config)

    @app.before_request
    def _carregar_usuario():
        g.usuario = None
        usuario_id = session.get(CHAVE)
        if usuario_id is None or request.endpoint == "static":   # arquivos estáticos não precisam da conta
            return
        usuario = servico_de_autenticacao().obter_usuario(usuario_id) if isinstance(usuario_id, int) else None
        if usuario is None:            # conta apagada ou cookie estranho: sessão inválida
            session.clear()
        g.usuario = usuario


def login_obrigatorio(funcao):
    """Rota de API: sem conta logada responde 401 em JSON."""
    @wraps(funcao)
    def interna(*args, **kwargs):
        if usuario_atual() is None:
            raise NaoAutenticadoError("Entre com seu e-mail para continuar.")
        return funcao(*args, **kwargs)
    return interna


def login_obrigatorio_pagina(funcao):
    """Rota de página: sem conta logada leva a `/entrar`, que depois devolve a esta página."""
    @wraps(funcao)
    def interna(*args, **kwargs):
        if usuario_atual() is None:
            return redirect(f"/entrar?proximo={quote(request.path, safe='/')}")
        return funcao(*args, **kwargs)
    return interna

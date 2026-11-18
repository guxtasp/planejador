"""
Rotas de autenticação (Etapa 5A, revista para o Supabase). Só traduzem HTTP ⇄ `AutenticacaoService`.

O e-mail/código é tratado pelo Supabase, no navegador; aqui só se troca o token
dele por uma sessão nossa.

  POST /api/auth/entrar   {access_token, proximo?}   confere o token e abre a sessão
  POST /api/auth/sair                                encerra a sessão
  GET  /api/auth/eu                                  conta logada (ou `null`)
  GET  /entrar                                       tela de entrada
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, redirect, render_template, request

from ..domain.identidade import caminho_interno_seguro
from .errors import AppError
from .sessao import encerrar_sessao, iniciar_sessao, servico_de_autenticacao, usuario_atual

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
bp_pagina = Blueprint("auth_pagina", __name__)


def _json() -> dict:
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        raise AppError("Envie os dados em JSON.")
    return corpo


def _config_publica_do_login() -> dict:
    """
    O que a tela de entrada precisa para falar com o Supabase. A chave "anon" é
    PÚBLICA por desenho (vai em qualquer site que usa o Supabase); o que a protege
    são as regras do próprio Supabase, não o sigilo. Nada secreto sai daqui.
    """
    cfg = current_app.config
    if cfg.get("AUTH_PROVEDOR") == "supabase":
        return {"provedor": "supabase", "url": cfg["SUPABASE_URL"].rstrip("/"), "chave": cfg["SUPABASE_ANON_KEY"]}
    return {"provedor": "dev"}


@bp.post("/entrar")
def entrar():
    corpo = _json()
    usuario, proximo = servico_de_autenticacao().entrar(corpo.get("access_token"), corpo.get("proximo"))
    iniciar_sessao(usuario["id"])
    return jsonify({"ok": True, "usuario": usuario, "proximo": proximo})


@bp.post("/sair")
def sair():
    encerrar_sessao()
    return jsonify({"ok": True})


@bp.get("/eu")
def eu():
    return jsonify({"ok": True, "usuario": usuario_atual()})


@bp_pagina.get("/entrar")
def pagina_entrar():
    proximo = caminho_interno_seguro(request.args.get("proximo"))
    # Já logado: segue para onde ia. A volta do link do e-mail (`#access_token=...`)
    # chega sem sessão, então não cai neste redirecionamento.
    if usuario_atual() is not None:
        return redirect(proximo)
    return render_template("entrar.html", proximo=proximo, login=_config_publica_do_login())

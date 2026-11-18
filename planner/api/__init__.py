"""
Camada HTTP. Cada módulo expõe um Blueprint por área do domínio.
Regra: rotas só traduzem HTTP ⇄ services; nada de SQL ou regra de negócio aqui.
"""
from flask import Flask

from . import auth, cursos, health, historico, importacao, oferta, planos
from .origem import registrar_verificacao_de_origem
from .sessao import registrar_carregamento_do_usuario


def register_blueprints(app: Flask) -> None:
    """Ponto único de registro. Novos blueprints entram nesta lista."""
    # Filtros globais, na ordem: origem (barra CSRF) e depois quem é o usuário.
    registrar_verificacao_de_origem(app)
    registrar_carregamento_do_usuario(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(auth.bp_pagina)
    app.register_blueprint(importacao.bp)
    app.register_blueprint(importacao.bp_pagina)
    app.register_blueprint(cursos.bp)
    app.register_blueprint(cursos.bp_pagina)
    app.register_blueprint(oferta.bp)
    app.register_blueprint(historico.bp)
    app.register_blueprint(planos.bp)

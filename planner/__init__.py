"""
Planejador Acadêmico — pacote principal.

Usa o padrão Application Factory: `create_app()` monta uma instância nova da
aplicação, o que permite testes isolados e múltiplas configurações.

Execução local:  flask --app planner run --debug
"""
from flask import Flask

from .api import register_blueprints
from .api.errors import register_error_handlers
from .cli import registrar_comandos
from .config import ProductionConfig, get_config
from .extensions import db, migrate


def create_app(config_name: str | None = None) -> Flask:
    config = get_config(config_name)
    if config is ProductionConfig:
        ProductionConfig.validate()

    app = Flask(__name__, template_folder="templates")
    app.config.from_object(config)

    db.init_app(app)
    # render_as_batch: o SQLite não tem ALTER TABLE completo; o modo batch
    # recria a tabela quando necessário, mantendo as migrações portáveis.
    migrate.init_app(app, db, render_as_batch=True)

    # Importa os modelos para que o Alembic os enxergue ao gerar migrações.
    from . import models  # noqa: F401

    register_blueprints(app)
    register_error_handlers(app)
    registrar_comandos(app)
    return app

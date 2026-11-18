"""
Testes da migração inicial (Etapa 1A).

Garantem que o histórico de migrações e os modelos NÃO divergem: quem alterar
um modelo sem gerar a migração correspondente quebra este teste.
"""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect

from planner import create_app
from planner.config import BASE_DIR
from planner.extensions import db

MIGRATIONS_DIR = str(BASE_DIR / "migrations")
TABELAS = {
    "curso", "disciplina", "requisito", "turma", "encontro", "usuario",
    "historico", "plano", "plano_semestre", "plano_item",
}


@pytest.fixture
def app_sem_schema():
    """App com banco VAZIO (sem `create_all`): só a migração cria as tabelas."""
    app = create_app("testing")
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


def _tabelas():
    return set(inspect(db.engine).get_table_names()) - {"alembic_version"}


def test_upgrade_cria_todas_as_tabelas(app_sem_schema):
    upgrade(directory=MIGRATIONS_DIR)
    assert _tabelas() == TABELAS


def test_migracao_nao_diverge_dos_modelos(app_sem_schema):
    upgrade(directory=MIGRATIONS_DIR)
    with db.engine.connect() as conn:
        contexto = MigrationContext.configure(conn)
        assert compare_metadata(contexto, db.metadata) == []


def test_downgrade_remove_tudo(app_sem_schema):
    upgrade(directory=MIGRATIONS_DIR)
    downgrade(directory=MIGRATIONS_DIR, revision="base")
    assert _tabelas() == set()

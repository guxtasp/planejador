"""
Instâncias das extensões Flask, criadas SEM app (padrão Application Factory).

Ficam aqui, e não em `__init__.py`, para que modelos e repositórios possam
importar `db` sem causar importação circular.
"""
import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine

# Convenção de nomes: dá nome previsível a toda constraint/índice. Sem isso o
# Alembic não consegue alterar ou remover constraints no SQLite (batch mode) e
# as migrações ficam diferentes entre SQLite e Postgres.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
migrate = Migrate()


@event.listens_for(Engine, "connect")
def _ativar_chaves_estrangeiras_no_sqlite(dbapi_connection, _record):
    """
    O SQLite IGNORA chaves estrangeiras por padrão. Sem este PRAGMA, os
    `ON DELETE CASCADE/RESTRICT` dos modelos só valeriam em produção (Postgres)
    e os testes em SQLite dariam falsa segurança.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

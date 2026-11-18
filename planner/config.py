"""
Configuração da aplicação (padrão: objetos de configuração por ambiente).

Regra de ouro: NADA de curso, universidade ou departamento aqui.
Este módulo só conhece infraestrutura (banco, segredo, modo de execução).
"""
import os
from datetime import timedelta
from pathlib import Path

from sqlalchemy.pool import NullPool

# Raiz do projeto (pasta que contém o pacote `planner/`).
BASE_DIR = Path(__file__).resolve().parent.parent


def normalize_database_url(url: str) -> str:
    """
    Provedores gerenciados (Heroku, Supabase, Neon) às vezes entregam a URL
    com o prefixo antigo `postgres://`, que o SQLAlchemy 2.x não aceita.
    Também força o driver `psycopg2` explicitamente, para evitar ambiguidade.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class BaseConfig:
    """Valores comuns a todos os ambientes."""

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # uploads de CSV: 5 MB bastam para qualquer matriz
    JSON_SORT_KEYS = False  # mantém a ordem dos campos nas respostas da API
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-inseguro-troque-em-producao")

    # ── autenticação (Etapa 5A, revista): Supabase Auth ───────────────────
    # O login (e-mail, link, código) é do Supabase, chamado pelo navegador; o servidor só
    # confere o token dele. Não há servidor de e-mail nem SMTP. Em dev/testes, o provedor
    # "dev" dispensa o Supabase. A chave "anon" é pública (ver `api/auth.py`).
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")            # https://<projeto>.supabase.co
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")  # chave pública (anon / publishable)
    AUTH_PROVEDOR = os.environ.get("AUTH_PROVEDOR") or ("supabase" if SUPABASE_URL and SUPABASE_ANON_KEY else "dev")

    # ── cookie de sessão ─────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True      # o JavaScript da página não lê o cookie
    SESSION_COOKIE_SAMESITE = "Lax"     # o navegador não o manda em POST vindo de outro site
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Subclasses definem a URI; ver `resolve_database_uri`.
    SQLALCHEMY_DATABASE_URI = None


class DevelopmentConfig(BaseConfig):
    """Desenvolvimento local: SQLite em arquivo, zero configuração."""

    DEBUG = True
    _local_db = BASE_DIR / "instance" / "planner.db"
    try:
        _local_db.parent.mkdir(exist_ok=True)
    except OSError:
        pass   # disco somente leitura (ex.: Vercel): esta classe nem é usada em produção
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{_local_db}")
    )


class TestingConfig(BaseConfig):
    """Testes: banco em memória, isolado e descartável."""

    TESTING = True
    AUTH_PROVEDOR = "dev"   # os testes não dependem de rede nem do Supabase
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    """Produção (Vercel): exige banco, segredo e o Supabase configurados."""

    DEBUG = False
    # Serverless: cada invocação pode abrir conexões novas; sem pool local (use o pooler
    # do provedor, ex.: Supabase porta 6543) e testando a conexão antes de usar.
    SQLALCHEMY_ENGINE_OPTIONS = {"poolclass": NullPool, "pool_pre_ping": True}
    AUTH_PROVEDOR = "supabase"     # o provedor "dev" aceita qualquer e-mail: proibido aqui
    SESSION_COOKIE_SECURE = True   # o cookie só trafega por HTTPS
    SQLALCHEMY_DATABASE_URI = (
        normalize_database_url(os.environ["DATABASE_URL"])
        if "DATABASE_URL" in os.environ
        else None
    )

    @classmethod
    def validate(cls) -> None:
        """Falha cedo (fail-fast) se a configuração de produção estiver incompleta."""
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("DATABASE_URL é obrigatória em produção.")
        if cls.SECRET_KEY == BaseConfig.SECRET_KEY:
            raise RuntimeError("SECRET_KEY é obrigatória em produção.")
        if cls.AUTH_PROVEDOR != "supabase":
            raise RuntimeError("Produção exige AUTH_PROVEDOR=supabase.")
        if not cls.SUPABASE_URL.startswith("https://") or not cls.SUPABASE_ANON_KEY:
            raise RuntimeError("Produção exige SUPABASE_URL (https://...) e SUPABASE_ANON_KEY.")


# Mapa nome → classe. Novo ambiente = nova linha aqui (aberto a extensão).
CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    """Resolve a configuração pelo nome ou pela variável APP_ENV."""
    name = name or os.environ.get("APP_ENV", "development")
    try:
        return CONFIG_BY_NAME[name]
    except KeyError:
        raise RuntimeError(f"APP_ENV inválido: {name!r}. Use: {list(CONFIG_BY_NAME)}")
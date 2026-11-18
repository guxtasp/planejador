import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_CHAVE_PADRAO_DEV = "dev-inseguro-troque-em-producao"


def _normalizar_url_banco(url: str | None) -> str | None:
    if not url:
        return None
    limpa = url.strip()
    if limpa.startswith("postgres://"):
        return "postgresql+psycopg2://" + limpa[len("postgres://") :]
    if limpa.startswith("postgresql://"):
        return "postgresql+psycopg2://" + limpa[len("postgresql://") :]
    return limpa


def _caminho_sqlite_local() -> str:
    local_db = BASE_DIR / "instance" / "planner.db"
    try:
        local_db.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return f"sqlite:///{local_db}"


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", _CHAVE_PADRAO_DEV)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    AUTH_PROVEDOR = os.environ.get("AUTH_PROVEDOR", "dev")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "").strip()


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        _normalizar_url_banco(os.environ.get("DATABASE_URL"))
        or _caminho_sqlite_local()
    )


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTH_PROVEDOR = "dev"


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    AUTH_PROVEDOR = os.environ.get("AUTH_PROVEDOR", "supabase")
    SQLALCHEMY_DATABASE_URI = _normalizar_url_banco(os.environ.get("DATABASE_URL"))

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY or cls.SECRET_KEY == _CHAVE_PADRAO_DEV:
            raise RuntimeError("SECRET_KEY é obrigatória em produção.")
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("DATABASE_URL é obrigatória em produção.")
        if cls.AUTH_PROVEDOR != "supabase":
            raise RuntimeError("AUTH_PROVEDOR deve ser 'supabase' em produção.")
        if not cls.SUPABASE_URL or not cls.SUPABASE_URL.startswith("https://"):
            raise RuntimeError("SUPABASE_URL com HTTPS é obrigatória em produção.")
        if not cls.SUPABASE_ANON_KEY:
            raise RuntimeError("SUPABASE_ANON_KEY é obrigatória em produção.")


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(nome: str | None = None) -> type[BaseConfig]:
    ambiente = (
        nome
        or os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or ("production" if os.environ.get("VERCEL") else "development")
    ).lower()
    return _CONFIGS.get(ambiente, DevelopmentConfig)
"""Etapa 5A (revista) — produção só sobe com o Supabase configurado e sem o provedor de desenvolvimento."""
import pytest

from planner.config import ProductionConfig

OK = {
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg2://x", "SECRET_KEY": "segredo-real",
    "AUTH_PROVEDOR": "supabase", "SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "chave",
}


def aplicar(monkeypatch, **mudancas):
    for chave, valor in {**OK, **mudancas}.items():
        monkeypatch.setattr(ProductionConfig, chave, valor)


def test_configuracao_completa_passa(monkeypatch):
    aplicar(monkeypatch)
    ProductionConfig.validate()


@pytest.mark.parametrize("mudanca", [
    {"AUTH_PROVEDOR": "dev"}, {"SUPABASE_URL": ""}, {"SUPABASE_URL": "http://sem-tls"},
    {"SUPABASE_ANON_KEY": ""}, {"SECRET_KEY": "dev-inseguro-troque-em-producao"},
    {"SQLALCHEMY_DATABASE_URI": None},
])
def test_configuracao_incompleta_falha_cedo(monkeypatch, mudanca):
    aplicar(monkeypatch, **mudanca)
    with pytest.raises(RuntimeError):
        ProductionConfig.validate()


def test_producao_nao_usa_provedor_dev_e_exige_cookie_seguro():
    assert ProductionConfig.AUTH_PROVEDOR == "supabase"
    assert ProductionConfig.SESSION_COOKIE_SECURE is True

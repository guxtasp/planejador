"""Etapa 5A — defesa contra requisição forjada por outro site (CSRF)."""
import pytest

from planner.api.origem import origem_permitida

HOST = "app.exemplo.com"


@pytest.mark.parametrize("metodo", ["GET", "HEAD", "OPTIONS"])
def test_metodos_de_leitura_sempre_passam(metodo):
    assert origem_permitida(metodo, HOST, "https://mal.com", "cross-site")


@pytest.mark.parametrize("site,esperado", [
    ("same-origin", True), ("none", True), ("same-site", False), ("cross-site", False)])
def test_sec_fetch_site_decide_quando_presente(site, esperado):
    assert origem_permitida("POST", HOST, None, site) is esperado


def test_origin_do_mesmo_host_passa_mesmo_com_esquema_diferente():
    assert origem_permitida("POST", HOST, "https://app.exemplo.com", None)
    assert origem_permitida("POST", HOST, "http://app.exemplo.com", None)


@pytest.mark.parametrize("origin", ["https://mal.com", "null", "https://app.exemplo.com.mal.com"])
def test_origin_de_outro_host_e_barrado(origin):
    assert not origem_permitida("POST", HOST, origin, None)


def test_sem_cabecalhos_passa_cliente_que_nao_e_navegador():
    assert origem_permitida("POST", HOST, None, None)


# ── pela aplicação ───────────────────────────────────────────────────────────
def test_post_vindo_de_outro_site_da_403(client):
    r = client.post("/api/auth/sair", headers={"Origin": "https://mal.com"})
    assert r.status_code == 403 and not r.get_json()["ok"]


def test_post_do_proprio_site_passa(client):
    r = client.post("/api/auth/sair", headers={"Origin": "http://localhost"})
    assert r.status_code == 200

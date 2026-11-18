"""Fumaça da nova aplicação: sobe, conecta ao banco e responde JSON."""


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "database": "ok"}


def test_unknown_route_returns_json_error(client):
    resp = client.get("/api/nao-existe")
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False

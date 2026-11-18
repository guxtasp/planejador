"""Etapa 5A (revista) — login pelo Supabase, sessão e rotas protegidas (via HTTP, com banco)."""
import io
from pathlib import Path

from planner.extensions import db
from planner.models import Curso, Usuario, Visibilidade

EXEMPLO = Path(__file__).resolve().parent.parent / "examples" / "ciencia-da-computacao"
NOMES = ("curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv")


def entrar(client, email="aluno@teste.com", **extra):
    """Login no provedor "dev" dos testes (token `dev:<e-mail>`); o Supabase real é coberto em test_auth_verificador."""
    return client.post("/api/auth/entrar", json={"access_token": f"dev:{email}", **extra})


def multipart():
    return {n: (io.BytesIO((EXEMPLO / n).read_bytes()), n) for n in NOMES}


# ── entrar ───────────────────────────────────────────────────────────────────
def test_primeiro_acesso_cria_a_conta_e_abre_a_sessao(client):
    r = entrar(client, "  Novo@Teste.com ")
    assert r.status_code == 200 and r.get_json()["usuario"]["email"] == "novo@teste.com"
    assert db.session.query(Usuario).filter_by(email="novo@teste.com").count() == 1
    assert client.get("/api/auth/eu").get_json()["usuario"]["email"] == "novo@teste.com"


def test_conta_existente_e_reaproveitada(client, usuario):
    assert entrar(client, usuario.email).get_json()["usuario"]["id"] == usuario.id
    assert db.session.query(Usuario).count() == 1


def test_entrar_de_novo_nao_duplica_a_conta(client):
    entrar(client, "a@teste.com")
    entrar(client, "a@teste.com")
    assert db.session.query(Usuario).count() == 1


def test_token_invalido_ou_ausente_da_401_e_nao_abre_sessao(client):
    for corpo in ({"access_token": "lixo"}, {}, {"access_token": None}, {"access_token": "dev:nao-e-email"}):
        r = client.post("/api/auth/entrar", json=corpo)
        assert r.status_code == 401 and not r.get_json()["ok"]
    assert client.get("/api/auth/eu").get_json()["usuario"] is None
    assert db.session.query(Usuario).count() == 0


def test_corpo_que_nao_e_json_da_400(client):
    assert client.post("/api/auth/entrar", data="texto").status_code == 400


def test_proximo_so_aceita_caminho_interno(client):
    assert entrar(client, proximo="/importar").get_json()["proximo"] == "/importar"
    assert entrar(client, "b@teste.com", proximo="https://mal.com").get_json()["proximo"] == "/"


def test_cookie_de_sessao_e_httponly_e_samesite(client):
    cookie = entrar(client).headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_rotas_do_link_magico_proprio_nao_existem_mais(client):
    assert client.post("/api/auth/link", json={"email": "a@x.com"}).status_code == 404
    assert client.get("/entrar/confirmar").status_code == 404


def test_usuario_novo_logado_pelo_supabase_usa_o_verificador_configurado(app, client):
    """O serviço usa o verificador da aplicação: trocá-lo troca o provedor sem mexer nas rotas."""
    from planner.services.auth import AutenticacaoService, IdentidadeVerificada

    class Fixo:
        def verificar(self, token):
            return IdentidadeVerificada("fixo@teste.com", "uuid")
    app.extensions["autenticacao"] = AutenticacaoService(Fixo())
    r = client.post("/api/auth/entrar", json={"access_token": "qualquer-jwt"})
    assert r.status_code == 200 and r.get_json()["usuario"]["email"] == "fixo@teste.com"


# ── sessão ───────────────────────────────────────────────────────────────────
def test_visitante_nao_tem_conta(client):
    assert client.get("/api/auth/eu").get_json() == {"ok": True, "usuario": None}


def test_sair_encerra_a_sessao(client_logado):
    assert client_logado.get("/api/auth/eu").get_json()["usuario"] is not None
    assert client_logado.post("/api/auth/sair").status_code == 200
    assert client_logado.get("/api/auth/eu").get_json()["usuario"] is None


def test_conta_apagada_derruba_a_sessao(client_logado, usuario):
    db.session.delete(usuario)
    db.session.commit()
    assert client_logado.get("/api/auth/eu").get_json()["usuario"] is None


def test_sessao_com_id_estranho_e_ignorada(client):
    with client.session_transaction() as s:
        s["usuario_id"] = "1; DROP TABLE usuario"
    assert client.get("/api/auth/eu").get_json()["usuario"] is None


# ── páginas ──────────────────────────────────────────────────────────────────
def test_pagina_de_entrada_abre_e_nao_expoe_segredos(app, client):
    html = client.get("/entrar").get_data(as_text=True)
    assert "no-referrer" in html and '"provedor": "dev"' in html
    app.config.update(AUTH_PROVEDOR="supabase", SUPABASE_URL="https://x.supabase.co/", SUPABASE_ANON_KEY="chave-publica")
    html = client.get("/entrar").get_data(as_text=True)
    assert "https://x.supabase.co" in html and "chave-publica" in html
    assert app.config["SECRET_KEY"] not in html


def test_pagina_entrar_ja_logado_redireciona(client_logado):
    r = client_logado.get("/entrar?proximo=/importar")
    assert r.status_code == 302 and r.headers["Location"].endswith("/importar")


def test_entrar_nao_redireciona_para_fora_do_site(client_logado):
    r = client_logado.get("/entrar?proximo=https://mal.com")
    assert r.headers["Location"] in ("/", "http://localhost/")


# ── rotas protegidas ─────────────────────────────────────────────────────────
def test_importar_pagina_exige_login(client):
    r = client.get("/importar")
    assert r.status_code == 302 and "/entrar?proximo=/importar" in r.headers["Location"]


def test_importar_pagina_abre_logado(client_logado):
    assert client_logado.get("/importar").status_code == 200


def test_validar_e_confirmar_exigem_login(client):
    for rota in ("validar", "confirmar"):
        r = client.post(f"/api/importacao/{rota}", data=multipart(), content_type="multipart/form-data")
        assert r.status_code == 401 and not r.get_json()["ok"]


def test_modelos_e_prompt_continuam_publicos(client):
    assert client.get("/api/importacao/modelos").status_code == 200
    assert client.get("/api/importacao/prompt-ia").status_code == 200


def test_curso_importado_pertence_a_quem_importou(client_logado, usuario):
    r = client_logado.post("/api/importacao/confirmar", data=multipart(), content_type="multipart/form-data")
    assert r.status_code == 201
    curso = db.session.get(Curso, r.get_json()["relatorio"]["curso_id"])
    assert curso.dono_id == usuario.id and curso.visibilidade == Visibilidade.PRIVADO.value


# ── fluxo completo, ponta a ponta ────────────────────────────────────────────
def test_fluxo_completo_entrar_importar_listar_sair(client):
    assert entrar(client, "novo@teste.com", proximo="/importar").status_code == 200
    assert client.post("/api/importacao/confirmar", data=multipart(), content_type="multipart/form-data").status_code == 201
    assert len(client.get("/api/cursos").get_json()["cursos"]) == 1
    client.post("/api/auth/sair")
    assert client.get("/api/cursos").get_json()["cursos"] == []

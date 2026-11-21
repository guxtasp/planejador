"""Etapa 4A — onboarding, listagem/catálogo de cursos e o shell do planejador."""
import io
import re
from pathlib import Path

import pytest

from planner.extensions import db
from planner.models import Curso, Usuario, Visibilidade

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "examples" / "ciencia-da-computacao"
NOMES = ("curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv")
JS = RAIZ / "planner" / "static" / "js"


@pytest.fixture
def client(client_logado):
    """Desde a 5A importar exige login: estes testes usam um cliente já logado."""
    return client_logado


def importar_exemplo(client):
    dados = {n: (io.BytesIO((EXEMPLO / n).read_bytes()), n) for n in NOMES}
    r = client.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    assert r.status_code == 201
    return r.get_json()["relatorio"]["curso_id"]


# ── app sem nenhum curso (verificação central da 4A) ─────────────────────────
def test_sem_cursos_a_lista_vem_vazia_e_a_pagina_inicial_abre(client):
    assert client.get("/api/cursos").get_json() == {"ok": True, "cursos": []}
    pagina = client.get("/")
    assert pagina.status_code == 200 and "/importar" in pagina.get_data(as_text=True)


# ── listagem ─────────────────────────────────────────────────────────────────
def test_curso_importado_aparece_na_lista_com_contadores(client):
    curso_id = importar_exemplo(client)
    (c,) = client.get("/api/cursos").get_json()["cursos"]
    assert c["id"] == curso_id and c["total_disciplinas"] == 49 and c["total_turmas"] == 61


def test_curso_privado_de_outro_usuario_nao_aparece_nem_abre(client, app):
    dono = Usuario(email="a@x.com", nome="A")
    db.session.add(dono)
    db.session.flush()
    db.session.add(Curso(nome="Alheio", dono_id=dono.id, visibilidade=Visibilidade.PRIVADO.value))
    db.session.commit()
    assert client.get("/api/cursos").get_json()["cursos"] == []
    alheio = db.session.query(Curso).one().id
    assert client.get(f"/api/cursos/{alheio}").status_code == 404
    assert client.get(f"/api/cursos/{alheio}/disciplinas").status_code == 404


def test_curso_publico_aparece_mesmo_com_dono(client, app):
    dono = Usuario(email="a@x.com", nome="A")
    db.session.add(dono)
    db.session.flush()
    db.session.add(Curso(nome="Aberto", dono_id=dono.id, visibilidade=Visibilidade.PUBLICO.value))
    db.session.commit()
    assert [c["nome"] for c in client.get("/api/cursos").get_json()["cursos"]] == ["Aberto"]


# ── catálogo ─────────────────────────────────────────────────────────────────
def test_catalogo_traz_disciplinas_e_requisitos_resolvidos(client):
    curso_id = importar_exemplo(client)
    j = client.get(f"/api/cursos/{curso_id}/disciplinas").get_json()
    assert j["ok"] and j["curso"]["id"] == curso_id and len(j["disciplinas"]) == 49
    reqs = [r for d in j["disciplinas"] for r in d["requisitos"]]
    assert len(reqs) == 46
    assert all(r["codigo"] and r["tipo"] in ("pre", "co") for r in reqs)


def test_campos_desconhecidos_saem_null_e_nunca_zero(client):
    dados = {
        "curso.csv": (io.BytesIO("nome\nCurso Mínimo\n".encode()), "curso.csv"),
        "disciplinas.csv": (io.BytesIO("codigo,nome,tipo\nABC101,Intro,obrigatoria\n".encode()), "disciplinas.csv"),
    }
    r = client.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    curso_id = r.get_json()["relatorio"]["curso_id"]
    j = client.get(f"/api/cursos/{curso_id}/disciplinas").get_json()
    (d,) = j["disciplinas"]
    assert d["creditos"] is None and d["carga_h"] is None and d["periodo_sugerido"] is None
    assert j["curso"]["ch_total"] is None and j["curso"]["dias_letivos"] is None


def test_curso_inexistente_da_404_em_json(client):
    r = client.get("/api/cursos/999")
    assert r.status_code == 404 and r.get_json()["ok"] is False


# ── páginas ──────────────────────────────────────────────────────────────────
def test_planejador_do_curso_recebe_o_id_e_curso_inexistente_volta_ao_inicio(client):
    curso_id = importar_exemplo(client)
    html = client.get(f"/curso/{curso_id}").get_data(as_text=True)
    assert f'data-curso-id="{curso_id}"' in html
    r = client.get("/curso/999")
    assert r.status_code == 302 and r.headers["Location"].endswith("/")


def test_assets_do_planejador_sao_servidos(client):
    curso_id = importar_exemplo(client)
    html = client.get(f"/curso/{curso_id}").get_data(as_text=True)
    for url in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
        assert client.get(url).status_code == 200, url


# ── frontend modular (sem banco) ─────────────────────────────────────────────
def test_todo_modulo_js_esta_no_shell_e_na_ordem_certa():
    html = (RAIZ / "planner" / "templates" / "index.html").read_text(encoding="utf-8")
    carregados = re.findall(r"js/(\w+)\.js", html)
    assert carregados[0] == "core" and carregados[-1] == "main"
    assert sorted(carregados) == sorted(p.stem for p in JS.glob("*.js"))


def test_nao_ha_curso_fixo_no_frontend():
    textos = [p.read_text(encoding="utf-8") for p in JS.glob("*.js")]
    textos.append((RAIZ / "planner" / "templates" / "index.html").read_text(encoding="utf-8"))
    assert not any("Ciência da Computação" in t or "UFV" in t for t in textos)


def test_frontend_nao_chama_mais_a_api_do_legado():
    legado = re.compile(r"/api/(disciplinas|historico|planos|assistente|semestres|validar_semestre)")
    for nome in tuple(p.stem for p in JS.glob("*.js")):
        texto = (JS / f"{nome}.js").read_text(encoding="utf-8")
        assert not legado.search(texto), f"{nome}.js ainda chama a API do legado"


def test_nenhuma_tela_esta_marcada_como_pendente_ou_esmaecida():
    """5B-2 ligou histórico e dashboard: não sobra aviso de 'próxima etapa' nem item esmaecido no menu."""
    html = (RAIZ / "planner" / "templates" / "index.html").read_text(encoding="utf-8")
    core = (JS / "core.js").read_text(encoding="utf-8")
    assert "PAGINAS_PENDENTES" not in core and "RECURSOS" not in core
    itens = re.findall(r'<div class="nav-item[^>]*data-page="(\w+)"[^>]*>', html)
    assert sorted(itens) == ["calendario", "dashboard", "disciplinas", "fluxograma", "historico", "planner", "rotina",
                             "simulador"]
    for tag in re.findall(r'<div class="nav-item[^>]*>', html):
        assert "opacity" not in tag and "próxima etapa" not in tag


def test_planos_nao_ficam_mais_so_no_navegador():
    """Os planos vêm do servidor; o `localStorage` só serve à migração e à preferência de qual plano abrir."""
    store = (JS / "plano_store.js").read_text(encoding="utf-8")
    assert "/planos" in store and "migrarDoNavegador" in store
    for nome in ("page_planner", "page_calendario", "core"):
        assert "PlanoLocal" not in (JS / f"{nome}.js").read_text(encoding="utf-8")


# ── exclusão de curso ────────────────────────────────────────────────────────
def test_dono_exclui_o_curso_e_tudo_que_depende_dele(client, usuario):
    from planner.models import Disciplina, Historico, Turma
    curso_id = importar_exemplo(client)
    disc = db.session.query(Disciplina).filter_by(curso_id=curso_id).first()
    db.session.add(Historico(usuario_id=usuario.id, disciplina_id=disc.id, status="aprovado"))
    db.session.commit()
    r = client.delete(f"/api/cursos/{curso_id}")
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    assert client.get("/api/cursos").get_json()["cursos"] == []
    assert db.session.query(Curso).count() == db.session.query(Disciplina).count() == 0
    assert db.session.query(Turma).count() == db.session.query(Historico).count() == 0


def test_lista_marca_quais_cursos_sao_meus(client):
    importar_exemplo(client)
    (c,) = client.get("/api/cursos").get_json()["cursos"]
    assert c["meu"] is True


def test_nao_dono_nao_exclui_curso_publico(client, app):
    dono = Usuario(email="a@x.com", nome="A")
    db.session.add(dono)
    db.session.flush()
    db.session.add(Curso(nome="Aberto", dono_id=dono.id, visibilidade=Visibilidade.PUBLICO.value))
    db.session.commit()
    cid = db.session.query(Curso).one().id
    assert client.delete(f"/api/cursos/{cid}").status_code == 403
    assert db.session.query(Curso).count() == 1


def test_curso_privado_de_outro_e_inexistente_dao_404(client, app):
    dono = Usuario(email="a@x.com", nome="A")
    db.session.add(dono)
    db.session.flush()
    db.session.add(Curso(nome="Alheio", dono_id=dono.id, visibilidade=Visibilidade.PRIVADO.value))
    db.session.commit()
    cid = db.session.query(Curso).one().id
    assert client.delete(f"/api/cursos/{cid}").status_code == 404
    assert client.delete("/api/cursos/99999").status_code == 404


def test_excluir_exige_login(app):
    assert app.test_client().delete("/api/cursos/1").status_code == 401


def test_curso_com_historico_de_outra_conta_nao_e_excluido(client, app):
    from planner.models import Disciplina, Historico
    curso_id = importar_exemplo(client)
    outra = Usuario(email="b@x.com", nome="B")
    db.session.add(outra)
    db.session.flush()
    disc = db.session.query(Disciplina).filter_by(curso_id=curso_id).first()
    db.session.add(Historico(usuario_id=outra.id, disciplina_id=disc.id, status="aprovado"))
    db.session.commit()
    assert client.delete(f"/api/cursos/{curso_id}").status_code == 409
    assert db.session.query(Curso).count() == 1

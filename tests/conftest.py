"""Fixtures compartilhadas pelos testes."""
import pytest

from planner import create_app
from planner.extensions import db


@pytest.fixture
def app():
    """Aplicação nova por teste, com banco SQLite em memória."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    """
    App ORIGINAL (legacy/app_legacy.py) apontando para um banco temporário.

    Serve apenas para os testes de caracterização: eles registram o que o
    sistema antigo fazia ANTES da refatoração, para que cada mudança de
    comportamento seja intencional e visível.
    """
    from legacy import app_legacy as mod

    monkeypatch.setattr(mod, "DB_PATH", tmp_path / "legacy.db")
    mod.init_db()  # cria schema + seed de Ciência da Computação
    mod.app.config["TESTING"] = True
    return mod


@pytest.fixture
def legacy_client(legacy):
    return legacy.app.test_client()


# ── autenticação (Etapa 5A) ─────────────────────────────────────────────────
@pytest.fixture
def usuario(app):
    """Conta de teste já gravada no banco."""
    from planner.models import Usuario

    u = Usuario(email="aluno@teste.com", nome="Aluno")
    db.session.add(u)
    db.session.commit()
    return u


def entrar_como(client, usuario_id: int) -> None:
    """Abre a sessão do `client` direto no cookie (atalho; o fluxo do link tem testes próprios)."""
    with client.session_transaction() as sessao:
        sessao["usuario_id"] = usuario_id


@pytest.fixture
def client_logado(app, usuario):
    """Cliente HTTP já logado como `usuario`."""
    cliente = app.test_client()
    entrar_como(cliente, usuario.id)
    return cliente


# ── curso pequeno + segundo usuário (Etapa 5B-2) ────────────────────────────
CSVS_CURSO_PEQUENO = {
    "curso.csv": "nome,max_creditos_semestre,creditos_obrigatorios,duracao_semestres\nCurso Pequeno,6,10,2\n",
    "disciplinas.csv": (
        "codigo,nome,creditos,tipo\n"
        "AAA100,Alfa,4,obrigatoria\nBBB100,Beta,4,obrigatoria\nCCC100,Gama,2,obrigatoria\n"
    ),
    "requisitos.csv": "disciplina,requisito,tipo,grupo_alt\nBBB100,AAA100,pre,\n",
    "turmas.csv": (
        "disciplina,periodo_letivo,codigo_turma,horarios\n"
        "AAA100,2026/1,T1,SEG 08:00-10:00\n"
        "BBB100,2026/1,T1,SEG 09:00-11:00\n"
        "BBB100,2026/1,T2,TER 19:00-22:30\n"
        "CCC100,2026/1,T1,SAB 08:00-12:00\n"
        "BBB100,2026/2,T1,SEG 09:00-11:00\n"
    ),
}


@pytest.fixture
def curso_pequeno(client_logado):
    """
    Curso importado pelo `usuario` logado. Devolve
    `{"id", "disc": {codigo: id}, "turmas": {(codigo, periodo, turma): id}}`.
    """
    import io

    dados = {n: (io.BytesIO(t.encode()), n) for n, t in CSVS_CURSO_PEQUENO.items()}
    r = client_logado.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["relatorio"]["curso_id"]
    disc = {d["codigo"]: d["id"] for d in client_logado.get(f"/api/cursos/{cid}/disciplinas").get_json()["disciplinas"]}
    por_id = {i: c for c, i in disc.items()}
    turmas = {
        (por_id[t["disciplina_id"]], t["periodo_letivo"], t["codigo_turma"]): t["id"]
        for t in client_logado.get(f"/api/cursos/{cid}/turmas").get_json()["turmas"]
    }
    return {"id": cid, "disc": disc, "turmas": turmas}


@pytest.fixture
def outro_usuario(app):
    from planner.models import Usuario

    u = Usuario(email="outra@teste.com", nome="Outra")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def client_outro(app, outro_usuario):
    """Cliente logado como OUTRA conta (para testar isolamento)."""
    cliente = app.test_client()
    entrar_como(cliente, outro_usuario.id)
    return cliente


def tornar_publico(curso_id: int) -> None:
    """Deixa o curso visível a todos, para duas contas usarem o MESMO curso."""
    from planner.models import Curso

    db.session.get(Curso, curso_id).visibilidade = "publico"
    db.session.commit()

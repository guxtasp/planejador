"""Etapa 5A — quem vê e quem altera cada curso; cursos sem dono; comando de administração."""
import io

import pytest

from planner.api.errors import NotFoundError
from planner.extensions import db
from planner.models import Curso, Usuario, Visibilidade
from planner.services.cursos import CursoService
from planner.services.importacao import ImportacaoService
from planner.services.posse import PosseService
from planner.services.previa_importacao import PreviaImportacaoService

from .conftest import entrar_como

CSV = {"curso.csv": "nome\nMeu Curso\n", "disciplinas.csv": "codigo,nome,tipo\nA1,Alfa,obrigatoria\n"}


def criar_usuario(email):
    u = Usuario(email=email)
    db.session.add(u)
    db.session.flush()
    return u


def criar_curso(nome, dono_id=None, visibilidade=Visibilidade.PRIVADO):
    c = Curso(nome=nome, dono_id=dono_id, visibilidade=visibilidade.value)
    db.session.add(c)
    db.session.commit()
    return c


# ── leitura ──────────────────────────────────────────────────────────────────
def test_curso_sem_dono_nao_aparece_para_ninguem(app, usuario):
    criar_curso("Órfão")
    assert CursoService().listar(usuario.id) == []
    assert CursoService().listar(None) == []


def test_curso_sem_dono_nao_abre_nem_logado(app, usuario):
    orfao = criar_curso("Órfão")
    with pytest.raises(NotFoundError):
        CursoService().obter(orfao.id, usuario.id)


def test_curso_publico_sem_dono_continua_visivel(app):
    criar_curso("Aberto", visibilidade=Visibilidade.PUBLICO)
    assert [c["nome"] for c in CursoService().listar(None)] == ["Aberto"]


def test_cada_um_ve_so_os_seus_privados_mais_os_publicos(app, usuario):
    outro = criar_usuario("outro@teste.com")
    criar_curso("Meu", usuario.id)
    criar_curso("Dele", outro.id)
    criar_curso("De todos", outro.id, Visibilidade.PUBLICO)
    assert [c["nome"] for c in CursoService().listar(usuario.id)] == ["De todos", "Meu"]


def test_visitante_ve_publico_mas_nao_privado_pela_api(client, app):
    dono = criar_usuario("a@teste.com")
    publico = criar_curso("Aberto", dono.id, Visibilidade.PUBLICO)
    privado = criar_curso("Fechado", dono.id)
    assert client.get(f"/api/cursos/{publico.id}").status_code == 200
    assert client.get(f"/api/cursos/{privado.id}").status_code == 404
    assert client.get(f"/api/cursos/{privado.id}/turmas").status_code == 404
    r = client.post(f"/api/cursos/{privado.id}/plano/analisar", json={"semestres": []})
    assert r.status_code == 404


def test_pagina_do_planejador_visitante_vai_ao_login_e_logado_volta_ao_inicio(client, client_logado, app):
    dono = criar_usuario("a@teste.com")
    privado = criar_curso("Fechado", dono.id)
    anonimo = client.get(f"/curso/{privado.id}")
    assert anonimo.status_code == 302 and "/entrar?proximo=/curso/" in anonimo.headers["Location"]
    inexistente = client.get("/curso/9999")                   # mesma resposta: nada vaza
    assert inexistente.headers["Location"].split("?")[0] == anonimo.headers["Location"].split("?")[0]
    logado = client_logado.get(f"/curso/{privado.id}")
    assert logado.status_code == 302 and logado.headers["Location"] in ("/", "http://localhost/")


# ── escrita (importação) ─────────────────────────────────────────────────────
def test_nao_da_para_atualizar_curso_de_outra_pessoa(app, usuario):
    outro = criar_usuario("outro@teste.com")
    alheio = criar_curso("Alheio", outro.id)
    with pytest.raises(NotFoundError):
        PreviaImportacaoService().gerar(CSV, curso_id=alheio.id, dono_id=usuario.id)
    with pytest.raises(NotFoundError):
        ImportacaoService().confirmar(CSV, curso_id=alheio.id, dono_id=usuario.id)


def test_nem_curso_publico_de_outra_pessoa_pode_ser_alterado(app, usuario):
    outro = criar_usuario("outro@teste.com")
    publico = criar_curso("Aberto", outro.id, Visibilidade.PUBLICO)
    with pytest.raises(NotFoundError):
        ImportacaoService().confirmar(CSV, curso_id=publico.id, dono_id=usuario.id)


def test_dono_atualiza_o_proprio_curso(app, usuario):
    meu = criar_curso("Meu Curso", usuario.id)
    rel = ImportacaoService().confirmar(CSV, curso_id=meu.id, dono_id=usuario.id)
    assert rel.curso_id == meu.id and not rel.curso_criado


def test_curso_de_mesmo_nome_de_outra_pessoa_nao_e_tocado(app, usuario):
    outro = criar_usuario("outro@teste.com")
    alheio = criar_curso("Meu Curso", outro.id)
    rel = ImportacaoService().confirmar(CSV, dono_id=usuario.id)
    assert rel.curso_criado and rel.curso_id != alheio.id          # criou o SEU, ao lado do dele
    assert db.session.get(Curso, rel.curso_id).dono_id == usuario.id


def test_api_curso_id_alheio_da_404(client, app):
    outro = criar_usuario("outro@teste.com")
    alheio = criar_curso("Alheio", outro.id)
    meu = criar_usuario("eu@teste.com")
    db.session.commit()
    entrar_como(client, meu.id)
    for rota in ("validar", "confirmar"):
        # Arquivos novos a cada envio: o cliente de teste fecha os streams ao enviá-los.
        dados = {n: (io.BytesIO(t.encode()), n) for n, t in CSV.items()}
        dados["curso_id"] = str(alheio.id)
        r = client.post(f"/api/importacao/{rota}", data=dados, content_type="multipart/form-data")
        assert r.status_code == 404, rota


# ── cursos sem dono → comando de administração ───────────────────────────────
def test_reivindicar_entrega_os_orfaos_a_conta(app):
    criar_curso("Órfão 1")
    criar_curso("Órfão 2")
    dono = criar_usuario("outro@teste.com")
    criar_curso("Já tem dono", dono.id)
    assert PosseService().reivindicar_orfaos("  Admin@Teste.com ") == 2
    admin = db.session.query(Usuario).filter_by(email="admin@teste.com").one()
    assert sorted(c.nome for c in db.session.query(Curso).filter_by(dono_id=admin.id)) == ["Órfão 1", "Órfão 2"]
    assert db.session.query(Curso).filter_by(dono_id=dono.id).count() == 1     # o resto não mudou
    assert PosseService().reivindicar_orfaos("admin@teste.com") == 0           # repetir é inofensivo


def test_reivindicar_reaproveita_conta_existente(app, usuario):
    criar_curso("Órfão")
    PosseService().reivindicar_orfaos(usuario.email)
    assert db.session.query(Usuario).count() == 1
    assert [c["nome"] for c in CursoService().listar(usuario.id)] == ["Órfão"]


def test_comando_de_linha(app):
    criar_curso("Órfão")
    r = app.test_cli_runner().invoke(args=["reivindicar-cursos", "admin@teste.com"])
    assert r.exit_code == 0 and "1 curso(s) atribuído(s)" in r.output


def test_comando_de_linha_recusa_email_invalido(app):
    r = app.test_cli_runner().invoke(args=["reivindicar-cursos", "invalido"])
    assert r.exit_code != 0 and "E-mail inválido" in r.output

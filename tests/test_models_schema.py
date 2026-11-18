"""
Testes do schema (Etapa 1A): constraints, chaves estrangeiras e cascatas.

Rodam em SQLite com `PRAGMA foreign_keys=ON` (ver `extensions.py`), então os
`ON DELETE` valem aqui como valerão no Postgres.
"""
from datetime import time

import pytest
from sqlalchemy.exc import IntegrityError

from planner.extensions import db
from planner.models import (
    Curso, Disciplina, Encontro, Historico, Plano, PlanoItem, PlanoSemestre,
    Requisito, Turma, Usuario,
)


# ── helpers ────────────────────────────────────────────────────────────────
def _salvar(*objetos):
    db.session.add_all(objetos)
    db.session.commit()
    return objetos[0] if len(objetos) == 1 else objetos


def _curso(nome="Curso Teste"):
    return _salvar(Curso(nome=nome))


def _disc(curso, codigo="D1", **extra):
    return _salvar(Disciplina(curso_id=curso.id, codigo=codigo, nome=f"Disc {codigo}", **extra))


def _usuario(email="aluno@exemplo.com"):
    return _salvar(Usuario(email=email))


def _contar(modelo):
    return db.session.query(modelo).count()


def _deve_violar(objeto):
    """Afirma que gravar `objeto` viola uma constraint, e limpa a sessão."""
    db.session.add(objeto)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# ── defaults e opcionalidade (NULL = desconhecido) ─────────────────────────
def test_curso_so_exige_nome_e_nasce_privado(app):
    curso = _curso()
    assert curso.visibilidade == "privado"
    # Campos acadêmicos ficam NULL, nunca zero.
    assert curso.creditos_obrigatorios is None
    assert curso.max_creditos_semestre is None
    assert curso.dias_letivos is None


def test_dias_letivos_guarda_lista(app):
    curso = _salvar(Curso(nome="Noturno", dias_letivos=["SEG", "SAB"]))
    db.session.expire_all()
    assert db.session.get(Curso, curso.id).dias_letivos == ["SEG", "SAB"]


def test_disciplina_aceita_campos_academicos_vazios(app):
    disc = _disc(_curso())
    assert disc.creditos is None and disc.carga_h is None and disc.periodo_sugerido is None
    assert disc.tipo == "obrigatoria"


# ── unicidade e CHECKs ─────────────────────────────────────────────────────
def test_codigo_de_disciplina_unico_por_curso(app):
    curso_a, curso_b = _curso("A"), _curso("B")
    _disc(curso_a, "INF110")
    _deve_violar(Disciplina(curso_id=curso_a.id, codigo="INF110", nome="Duplicada"))
    # O mesmo código em OUTRO curso é permitido.
    _disc(curso_b, "INF110")


def test_tipo_de_disciplina_invalido_e_rejeitado(app):
    curso = _curso()
    _deve_violar(Disciplina(curso_id=curso.id, codigo="X", nome="X", tipo="inventado"))


def test_creditos_negativos_sao_rejeitados(app):
    curso = _curso()
    _deve_violar(Disciplina(curso_id=curso.id, codigo="X", nome="X", creditos=-1))


def test_visibilidade_invalida_e_rejeitada(app):
    _deve_violar(Curso(nome="X", visibilidade="secreto"))


def test_email_de_usuario_unico(app):
    _usuario("a@x.com")
    _deve_violar(Usuario(email="a@x.com"))


def test_disciplina_nao_pode_ser_requisito_de_si_mesma(app):
    disc = _disc(_curso())
    _deve_violar(Requisito(disciplina_id=disc.id, requisito_id=disc.id, tipo="pre"))


def test_requisito_duplicado_e_rejeitado_mas_pre_e_co_coexistem(app):
    curso = _curso()
    a, b = _disc(curso, "A"), _disc(curso, "B")
    _salvar(Requisito(disciplina_id=a.id, requisito_id=b.id, tipo="pre"))
    _deve_violar(Requisito(disciplina_id=a.id, requisito_id=b.id, tipo="pre"))
    _salvar(Requisito(disciplina_id=a.id, requisito_id=b.id, tipo="co"))


def test_requisitos_expoem_relacionamentos_dos_dois_lados(app):
    curso = _curso()
    a, b = _disc(curso, "A"), _disc(curso, "B")
    _salvar(Requisito(disciplina_id=a.id, requisito_id=b.id, tipo="pre", grupo_alt="g1"))
    assert [r.requerida.codigo for r in a.requisitos] == ["B"]
    assert b.requisitos == []  # B não exige nada


def test_encontro_exige_inicio_antes_do_fim(app):
    turma = _turma(_disc(_curso()))
    _deve_violar(Encontro(turma_id=turma.id, dia="SEG", inicio=time(18), fim=time(16)))
    _deve_violar(Encontro(turma_id=turma.id, dia="SEG", inicio=time(16), fim=time(16)))


def test_encontro_com_dia_invalido_e_rejeitado(app):
    turma = _turma(_disc(_curso()))
    _deve_violar(Encontro(turma_id=turma.id, dia="XXX", inicio=time(8), fim=time(10)))


def _turma(disciplina, periodo="2026/1", codigo="T1"):
    return _salvar(Turma(disciplina_id=disciplina.id, periodo_letivo=periodo, codigo_turma=codigo))


def test_turma_unica_por_disciplina_periodo_e_codigo(app):
    disc = _disc(_curso())
    _turma(disc, "2026/1", "T1")
    _deve_violar(Turma(disciplina_id=disc.id, periodo_letivo="2026/1", codigo_turma="T1"))
    _turma(disc, "2026/2", "T1")  # outro período: ok
    _turma(disc, "2026/1", "T2")  # outro código: ok


def test_horarios_preservam_hora_e_vem_ordenados(app):
    turma = _turma(_disc(_curso()))
    _salvar(
        Encontro(turma_id=turma.id, dia="QUI", inicio=time(14), fim=time(16)),
        Encontro(turma_id=turma.id, dia="SEG", inicio=time(16), fim=time(18)),
    )
    db.session.expire_all()
    encontros = db.session.get(Turma, turma.id).encontros
    assert [(e.dia, e.inicio) for e in encontros] == [("QUI", time(14)), ("SEG", time(16))]


# ── chaves estrangeiras ────────────────────────────────────────────────────
def test_fk_inexistente_e_rejeitada(app):
    _deve_violar(Disciplina(curso_id=999, codigo="X", nome="X"))
    _deve_violar(Historico(usuario_id=999, disciplina_id=999, status="aprovado"))


# ── cascatas ───────────────────────────────────────────────────────────────
def test_apagar_curso_apaga_catalogo_e_oferta(app):
    curso = _curso()
    disc = _disc(curso)
    turma = _turma(disc)
    _salvar(Encontro(turma_id=turma.id, dia="SEG", inicio=time(8), fim=time(10)))
    outra = _disc(curso, "D2")
    _salvar(Requisito(disciplina_id=outra.id, requisito_id=disc.id, tipo="pre"))

    db.session.delete(curso)
    db.session.commit()

    for modelo in (Disciplina, Turma, Encontro, Requisito):
        assert _contar(modelo) == 0, modelo.__name__


def test_apagar_disciplina_remove_requisitos_dos_dois_lados(app):
    curso = _curso()
    a, b = _disc(curso, "A"), _disc(curso, "B")
    _salvar(Requisito(disciplina_id=a.id, requisito_id=b.id, tipo="pre"))
    db.session.delete(b)  # B era requisito de A
    db.session.commit()
    assert _contar(Requisito) == 0
    assert _contar(Disciplina) == 1


def test_apagar_disciplina_com_historico_e_bloqueado(app):
    """Regra central da 1A: apagar disciplina NÃO apaga (nem orfana) histórico."""
    disc = _disc(_curso())
    aluno = _usuario()
    _salvar(Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="aprovado", nota=85))

    db.session.delete(disc)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert _contar(Disciplina) == 1
    assert _contar(Historico) == 1


def test_apagar_curso_com_historico_tambem_e_bloqueado(app):
    curso = _curso()
    disc = _disc(curso)
    aluno = _usuario()
    _salvar(Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="cursando"))
    db.session.delete(curso)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert _contar(Historico) == 1


def test_historico_aceita_varias_tentativas_da_mesma_disciplina(app):
    disc = _disc(_curso())
    aluno = _usuario()
    _salvar(
        Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="reprovado", periodo_letivo="2025/1", nota=40),
        Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="aprovado", periodo_letivo="2025/2", nota=72.5),
    )
    assert len(aluno.historico) == 2


def test_historico_rejeita_status_e_nota_invalidos(app):
    disc, aluno = _disc(_curso()), _usuario()
    _deve_violar(Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="talvez"))
    _deve_violar(Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="aprovado", nota=101))


def test_apagar_usuario_apaga_historico_e_planos_mas_preserva_curso(app):
    curso = _salvar(Curso(nome="Publicável"))
    disc = _disc(curso)
    aluno = _usuario()
    curso.dono_id = aluno.id
    _salvar(Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="aprovado"))
    _salvar(Plano(usuario_id=aluno.id, curso_id=curso.id, nome="Plano A"))

    db.session.delete(aluno)
    db.session.commit()

    assert _contar(Historico) == 0 and _contar(Plano) == 0
    db.session.expire_all()
    assert db.session.get(Curso, curso.id).dono_id is None  # curso sobrevive sem dono


# ── planos ─────────────────────────────────────────────────────────────────
def _plano_com_item():
    curso = _curso()
    disc = _disc(curso)
    turma = _turma(disc)
    aluno = _usuario()
    plano = _salvar(Plano(usuario_id=aluno.id, curso_id=curso.id, nome="P"))
    sem = _salvar(PlanoSemestre(plano_id=plano.id, ordem=1, label="1º semestre"))
    _salvar(PlanoItem(semestre_id=sem.id, disciplina_id=disc.id, turma_id=turma.id))
    return plano, sem, disc, turma


def test_semestre_com_ordem_repetida_no_mesmo_plano_e_rejeitado(app):
    plano, *_ = _plano_com_item()
    _deve_violar(PlanoSemestre(plano_id=plano.id, ordem=1, label="duplicado"))


def test_mesma_disciplina_nao_entra_duas_vezes_no_semestre(app):
    _plano, sem, disc, _turma_ = _plano_com_item()
    _deve_violar(PlanoItem(semestre_id=sem.id, disciplina_id=disc.id))


def test_apagar_turma_mantem_item_do_plano_sem_turma(app):
    _plano, sem, _disc_, turma = _plano_com_item()
    db.session.delete(turma)
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(PlanoSemestre, sem.id).itens[0].turma_id is None


def test_apagar_plano_apaga_semestres_e_itens(app):
    plano, *_ = _plano_com_item()
    db.session.delete(plano)
    db.session.commit()
    assert _contar(PlanoSemestre) == 0 and _contar(PlanoItem) == 0


def test_apagar_disciplina_remove_do_plano_sem_tocar_o_plano(app):
    plano, _sem, disc, _turma_ = _plano_com_item()
    db.session.delete(disc)
    db.session.commit()
    assert _contar(PlanoItem) == 0
    assert _contar(Plano) == 1

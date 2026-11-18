"""
Testes dos repositories (Etapa 1B).

Cobrem: consultas, filtros por curso/usuário, política de transação
(flush sem commit) e ausência de N+1 (contando as instruções SQL emitidas).
"""
from contextlib import contextmanager
from datetime import time

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from planner.extensions import db
from planner.models import (
    Curso, Disciplina, Encontro, Historico, Plano, PlanoItem, PlanoSemestre,
    Requisito, Turma, Usuario,
)
from planner.repositories import (
    CursoRepository, DisciplinaRepository, HistoricoRepository, PlanoRepository,
    RequisitoRepository, TurmaRepository, UsuarioRepository,
)


# ── helpers ────────────────────────────────────────────────────────────────
@contextmanager
def contar_consultas():
    """Coleta as instruções SQL executadas dentro do bloco."""
    instrucoes: list[str] = []

    def registrar(_conexao, _cursor, instrucao, *_resto):
        instrucoes.append(instrucao)

    event.listen(db.engine, "before_cursor_execute", registrar)
    try:
        yield instrucoes
    finally:
        event.remove(db.engine, "before_cursor_execute", registrar)


def _salvar(*objetos):
    db.session.add_all(objetos)
    db.session.commit()
    return objetos[0] if len(objetos) == 1 else objetos


def _curso(nome="Curso A", **extra):
    return _salvar(Curso(nome=nome, **extra))


def _disc(curso, codigo, periodo=None, **extra):
    return _salvar(Disciplina(
        curso_id=curso.id, codigo=codigo, nome=f"Disc {codigo}",
        periodo_sugerido=periodo, **extra,
    ))


def _turma(disc, periodo="2026/1", codigo="T1", encontros=1):
    turma = Turma(disciplina_id=disc.id, periodo_letivo=periodo, codigo_turma=codigo)
    turma.encontros = [
        Encontro(dia="SEG", inicio=time(8 + i * 2), fim=time(10 + i * 2)) for i in range(encontros)
    ]
    return _salvar(turma)


# ── transação: flush sem commit ────────────────────────────────────────────
def test_adicionar_atribui_id_mas_nao_faz_commit(app):
    repo = CursoRepository()
    curso = repo.adicionar(Curso(nome="Novo"))
    assert curso.id is not None            # flush: já tem id
    db.session.rollback()                  # sem commit: a transação desfaz
    assert repo.obter(curso.id) is None


def test_remover_curso_apaga_catalogo_em_cascata(app):
    curso = _curso()
    disc = _disc(curso, "D1")
    _turma(disc)
    CursoRepository().remover(curso)
    db.session.commit()
    assert db.session.query(Disciplina).count() == 0
    assert db.session.query(Turma).count() == 0
    assert db.session.query(Encontro).count() == 0


def test_remover_curso_com_historico_e_bloqueado(app):
    curso = _curso()
    disc = _disc(curso, "D1")
    aluno = _salvar(Usuario(email="a@x.com"))
    _salvar(Historico(usuario_id=aluno.id, disciplina_id=disc.id, status="aprovado"))
    with pytest.raises(IntegrityError):
        CursoRepository().remover(curso)
    db.session.rollback()


# ── CursoRepository ────────────────────────────────────────────────────────
def test_listar_acessiveis_mostra_publicos_e_os_do_usuario(app):
    dono = _salvar(Usuario(email="d@x.com"))
    outro = _salvar(Usuario(email="o@x.com"))
    _curso("Público", visibilidade="publico", dono_id=outro.id)
    _curso("Meu privado", dono_id=dono.id)
    _curso("Privado alheio", dono_id=outro.id)
    repo = CursoRepository()
    assert [c.nome for c in repo.listar_acessiveis(dono.id)] == ["Meu privado", "Público"]
    assert [c.nome for c in repo.listar_acessiveis()] == ["Público"]  # visitante


def test_obter_curso_por_nome_respeita_o_dono(app):
    dono = _salvar(Usuario(email="d@x.com"))
    _curso("CC", dono_id=dono.id)
    repo = CursoRepository()
    assert repo.obter_por_nome("CC", dono.id) is not None
    assert repo.obter_por_nome("CC", None) is None
    assert repo.obter_por_nome("Outro", dono.id) is None


# ── DisciplinaRepository ───────────────────────────────────────────────────
def test_listar_disciplinas_ordena_por_periodo_com_sem_periodo_no_fim(app):
    curso = _curso()
    _disc(curso, "B", periodo=2)
    _disc(curso, "OPT")                    # sem período sugerido
    _disc(curso, "A", periodo=2)
    _disc(curso, "C", periodo=1)
    codigos = [d.codigo for d in DisciplinaRepository().listar_do_curso(curso.id)]
    assert codigos == ["C", "A", "B", "OPT"]


def test_disciplinas_nao_vazam_entre_cursos(app):
    a, b = _curso("A"), _curso("B")
    _disc(a, "INF110")
    _disc(b, "INF110")
    repo = DisciplinaRepository()
    assert len(repo.listar_do_curso(a.id)) == 1
    assert repo.obter_por_codigo(a.id, "INF110").curso_id == a.id
    assert repo.obter_por_codigo(a.id, "NAO") is None


def test_mapa_por_codigo(app):
    curso = _curso()
    _disc(curso, "X1")
    _disc(curso, "X2")
    assert set(DisciplinaRepository().mapa_por_codigo(curso.id)) == {"X1", "X2"}


def test_pre_carregar_requisitos_e_turmas_evita_n_mais_1(app):
    curso = _curso()
    base = _disc(curso, "BASE", periodo=1)
    for i in range(6):
        disc = _disc(curso, f"D{i}", periodo=2)
        _salvar(Requisito(disciplina_id=disc.id, requisito_id=base.id, tipo="pre"))
        _turma(disc, "2026/1", "T1", encontros=2)
        _turma(disc, "2026/2", "T1", encontros=2)
    curso_id = curso.id
    db.session.expunge_all()               # força o carregamento real a partir do banco

    with contar_consultas() as sql:
        for d in DisciplinaRepository().listar_do_curso(
            curso_id, com_requisitos=True, com_turmas=True
        ):
            _ = [r.requisito_id for r in d.requisitos]
            _ = [e.dia for t in d.turmas for e in t.encontros]
    # disciplinas + requisitos + turmas + encontros, não importa quantas disciplinas
    assert len(sql) == 4


def test_sem_pre_carga_o_contador_enxerga_o_n_mais_1(app):
    """Controle: prova que o contador acima detecta o problema que ele deveria evitar."""
    curso = _curso()
    for i in range(6):
        _turma(_disc(curso, f"D{i}"))
    curso_id = curso.id
    db.session.expunge_all()
    with contar_consultas() as sql:
        for d in DisciplinaRepository().listar_do_curso(curso_id):
            _ = d.turmas
    assert len(sql) == 1 + 6


# ── RequisitoRepository ────────────────────────────────────────────────────
def test_requisitos_do_curso_vem_so_do_curso_pedido(app):
    a, b = _curso("A"), _curso("B")
    a1, a2 = _disc(a, "A1"), _disc(a, "A2")
    b1, b2 = _disc(b, "B1"), _disc(b, "B2")
    _salvar(Requisito(disciplina_id=a2.id, requisito_id=a1.id, tipo="pre"))
    _salvar(Requisito(disciplina_id=b2.id, requisito_id=b1.id, tipo="co"))
    repo = RequisitoRepository()
    assert [r.tipo for r in repo.listar_do_curso(a.id)] == ["pre"]
    assert repo.obter(a2.id, a1.id, "pre") is not None
    assert repo.obter(a2.id, a1.id, "co") is None


# ── TurmaRepository ────────────────────────────────────────────────────────
def test_turmas_filtram_por_periodo_e_trazem_encontros_sem_n_mais_1(app):
    curso = _curso()
    for i in range(5):
        disc = _disc(curso, f"D{i}")
        _turma(disc, "2026/1", encontros=2)
        _turma(disc, "2026/2", encontros=2)
    curso_id = curso.id
    db.session.expunge_all()

    repo = TurmaRepository()
    with contar_consultas() as sql:
        turmas = repo.listar_do_curso(curso_id, "2026/1")
        assert all(len(t.encontros) == 2 for t in turmas)
    assert len(turmas) == 5 and len(sql) == 2      # turmas + encontros
    assert len(repo.listar_do_curso(curso_id)) == 10


def test_turma_por_chave_natural_e_periodos_do_curso(app):
    curso = _curso()
    disc = _disc(curso, "D1")
    _turma(disc, "2026/2")
    _turma(disc, "2026/1")
    repo = TurmaRepository()
    assert repo.obter_por_chave(disc.id, "2026/1", "T1") is not None
    assert repo.obter_por_chave(disc.id, "2026/1", "T9") is None
    assert repo.listar_periodos_do_curso(curso.id) == ["2026/1", "2026/2"]


# ── Usuário, histórico e plano ─────────────────────────────────────────────
def test_usuario_por_email(app):
    aluno = _salvar(Usuario(email="a@x.com"))
    repo = UsuarioRepository()
    assert repo.obter_por_email("a@x.com").id == aluno.id
    assert repo.obter_por_email("b@x.com") is None


def test_historico_guarda_n_tentativas_e_filtra_por_curso(app):
    a, b = _curso("A"), _curso("B")
    da, db_ = _disc(a, "D1"), _disc(b, "D1")
    aluno = _salvar(Usuario(email="a@x.com"))
    _salvar(
        Historico(usuario_id=aluno.id, disciplina_id=da.id, status="reprovado"),
        Historico(usuario_id=aluno.id, disciplina_id=da.id, status="aprovado"),
        Historico(usuario_id=aluno.id, disciplina_id=db_.id, status="cursando"),
    )
    repo = HistoricoRepository()
    assert [h.status for h in repo.listar_do_usuario(aluno.id, a.id)] == ["reprovado", "aprovado"]
    assert len(repo.listar_do_usuario(aluno.id)) == 3


def test_plano_completo_carrega_a_arvore_sem_n_mais_1(app):
    curso = _curso()
    aluno = _salvar(Usuario(email="a@x.com"))
    plano = _salvar(Plano(usuario_id=aluno.id, curso_id=curso.id, nome="P"))
    for ordem in range(1, 4):
        semestre = _salvar(PlanoSemestre(plano_id=plano.id, ordem=ordem, label=f"S{ordem}"))
        for j in range(2):
            disc = _disc(curso, f"D{ordem}{j}")
            turma = _turma(disc)
            _salvar(PlanoItem(semestre_id=semestre.id, disciplina_id=disc.id, turma_id=turma.id))
    ids = {"plano": plano.id, "aluno": aluno.id, "curso": curso.id}
    db.session.expunge_all()

    repo = PlanoRepository()
    with contar_consultas() as sql:
        completo = repo.obter_completo(ids["plano"])
        codigos = [i.disciplina.codigo for s in completo.semestres for i in s.itens]
        assert all(i.turma is not None for s in completo.semestres for i in s.itens)
    assert len(codigos) == 6
    assert len(sql) == 5   # plano + semestres + itens + disciplinas + turmas
    assert [p.id for p in repo.listar_do_usuario(ids["aluno"], ids["curso"])] == [ids["plano"]]


# ── 5B-2: histórico e planos por usuário ─────────────────────────────────────
def test_listar_completos_de_planos_nao_faz_n_mais_1_e_isola_usuarios(app):
    curso = _curso()
    aluno = _salvar(Usuario(email="a@x.com"))
    outra = _salvar(Usuario(email="b@x.com"))
    _salvar(Plano(usuario_id=outra.id, curso_id=curso.id, nome="Da outra"))
    for n in range(3):
        plano = _salvar(Plano(usuario_id=aluno.id, curso_id=curso.id, nome=f"P{n}"))
        semestre = _salvar(PlanoSemestre(plano_id=plano.id, ordem=1, label="S1"))
        disc = _disc(curso, f"D{n}")
        _salvar(PlanoItem(semestre_id=semestre.id, disciplina_id=disc.id))
    ids = {"aluno": aluno.id, "curso": curso.id}
    db.session.expunge_all()

    repo = PlanoRepository()
    with contar_consultas() as sql:
        planos = repo.listar_completos(ids["aluno"], ids["curso"])
        assert [i.disciplina.codigo for p in planos for s in p.semestres for i in s.itens] == ["D0", "D1", "D2"]
    assert [p.nome for p in planos] == ["P0", "P1", "P2"]
    # planos + semestres + itens + disciplinas (+ turmas; o SQLAlchemy mais novo pula essa consulta
    # quando nenhum item tem turma). O que importa: constante, para QUALQUER número de planos.
    assert len(sql) <= 5


def test_obter_completo_do_usuario_nega_plano_alheio_e_de_outro_curso(app):
    curso, outro_curso = _curso("A"), _curso("B")
    aluno, outra = _salvar(Usuario(email="a@x.com")), _salvar(Usuario(email="b@x.com"))
    plano = _salvar(Plano(usuario_id=aluno.id, curso_id=curso.id, nome="P"))
    repo = PlanoRepository()
    assert repo.obter_completo_do_usuario(plano.id, aluno.id, curso.id) is not None
    assert repo.obter_completo_do_usuario(plano.id, outra.id, curso.id) is None
    assert repo.obter_completo_do_usuario(plano.id, aluno.id, outro_curso.id) is None


def test_substituir_semestres_troca_tudo_mesmo_reaproveitando_a_ordem(app):
    curso = _curso()
    aluno = _salvar(Usuario(email="a@x.com"))
    d1, d2 = _disc(curso, "D1"), _disc(curso, "D2")
    plano = _salvar(Plano(usuario_id=aluno.id, curso_id=curso.id, nome="P"))
    semestre = _salvar(PlanoSemestre(plano_id=plano.id, ordem=1, label="Velho"))
    _salvar(PlanoItem(semestre_id=semestre.id, disciplina_id=d1.id))
    ids = {"plano": plano.id, "d2": d2.id}
    db.session.expunge_all()

    repo = PlanoRepository()
    plano = repo.obter_completo(ids["plano"])
    repo.substituir_semestres(plano, [PlanoSemestre(ordem=1, label="Novo", itens=[PlanoItem(disciplina_id=ids["d2"])])])
    db.session.commit()
    db.session.expunge_all()

    recarregado = repo.obter_completo(ids["plano"])
    assert [(s.ordem, s.label, [i.disciplina_id for i in s.itens]) for s in recarregado.semestres] == [(1, "Novo", [ids["d2"]])]
    assert db.session.query(PlanoItem).count() == 1


def test_historico_com_disciplina_usa_duas_consultas_e_obter_do_usuario_isola(app):
    curso = _curso()
    aluno, outra = _salvar(Usuario(email="a@x.com")), _salvar(Usuario(email="b@x.com"))
    for n in range(3):
        _salvar(Historico(usuario_id=aluno.id, disciplina_id=_disc(curso, f"D{n}").id, status="aprovado"))
    _salvar(Historico(usuario_id=outra.id, disciplina_id=_disc(curso, "X").id, status="aprovado"))
    ids = {"aluno": aluno.id, "outra": outra.id, "curso": curso.id}
    db.session.expunge_all()

    repo = HistoricoRepository()
    with contar_consultas() as sql:
        lista = repo.listar_do_usuario(ids["aluno"], ids["curso"], com_disciplina=True)
        assert [h.disciplina.codigo for h in lista] == ["D0", "D1", "D2"]
    assert len(sql) == 2
    assert repo.obter_do_usuario(lista[0].id, ids["aluno"]) is not None
    assert repo.obter_do_usuario(lista[0].id, ids["outra"]) is None

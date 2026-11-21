"""Atualizar curso sem duplicar: candidatos por nome normalizado e por disciplinas em comum."""
import pytest

from planner.api.errors import ConflictError
from planner.domain.cursos_parecidos import (MOTIVO_AMBOS, MOTIVO_DISCIPLINAS, MOTIVO_NOME, CursoConhecido,
                                             candidatos_a_atualizar, normalizar_nome_curso)
from planner.extensions import db
from planner.models import Curso, Usuario
from planner.services.importacao import ImportacaoService
from planner.services.previa_importacao import PreviaImportacaoService

CC = CursoConhecido(1, "Ciência da Computação", "UFV", frozenset({"INF110", "INF112", "MAT140", "MAT147", "INF213"}))


@pytest.mark.parametrize("nome", ["Ciência da Computação", "ciencia da computacao", "  CIÊNCIA   DA COMPUTAÇÃO ",
                                  "Bacharelado em Ciência da Computação", "Ciência da Computação."])
def test_nome_variando_ainda_e_o_mesmo_curso(nome):
    assert normalizar_nome_curso(nome) == "ciencia da computacao"
    (c,) = candidatos_a_atualizar(nome, None, [], [CC])
    assert c.curso_id == 1 and c.motivo == MOTIVO_NOME


def test_instituicao_diferente_nao_casa_pelo_nome_mas_vazia_nao_atrapalha():
    assert candidatos_a_atualizar("Ciência da Computação", "USP", [], [CC]) == ()
    assert candidatos_a_atualizar("Ciência da Computação", "ufv", [], [CC])[0].curso_id == 1


def test_sessenta_por_cento_dos_codigos_bastam():
    (c,) = candidatos_a_atualizar("Outro nome", None, ["inf110", "INF112", "MAT140", "X1", "X2"], [CC])
    assert c.motivo == MOTIVO_DISCIPLINAS and c.em_comum == 3 and c.enviados == 5
    assert candidatos_a_atualizar("Outro nome", None, ["INF110", "X1", "X2", "X3"], [CC]) == ()


def test_dois_cursos_parecidos_vem_os_dois_o_mais_parecido_primeiro():
    outro = CursoConhecido(2, "Ciencia da Computacao (antigo)", None, frozenset({"INF110", "INF112", "MAT140"}))
    cands = candidatos_a_atualizar("Ciência da Computação", None, ["INF110", "INF112", "MAT140", "MAT147"], [outro, CC])
    assert [c.curso_id for c in cands] == [1, 2] and cands[0].motivo == MOTIVO_AMBOS


# ── serviço (com banco) ──────────────────────────────────────────────────────
CSV = {"curso.csv": "nome,instituicao\nCiência da Computação,UFV\n",
       "disciplinas.csv": "codigo,nome,tipo\nINF110,Prog I,obrigatoria\nINF112,Prog II,obrigatoria\nMAT140,Cálculo I,obrigatoria\n"}


def _usuario(email):
    u = Usuario(email=email, nome=email)
    db.session.add(u)
    db.session.commit()
    return u


def test_reimportar_com_nome_diferente_pede_escolha_e_nunca_duplica_em_silencio(app):
    dono = _usuario("a@t.com")
    rel = ImportacaoService().confirmar(CSV, dono_id=dono.id)
    variado = dict(CSV, **{"curso.csv": "nome,instituicao\n  bacharelado em CIENCIA da computação ,UFV\n"})
    previa, destino = PreviaImportacaoService().previa_e_destino(variado, dono_id=dono.id)
    assert destino.decisao_necessaria and destino.candidatos[0].curso_id == rel.curso_id
    assert "Atualizar" in destino.mensagem and previa.novos == 0       # comparado com o curso parecido
    with pytest.raises(ConflictError):
        ImportacaoService().confirmar(variado, dono_id=dono.id)
    assert db.session.query(Curso).count() == 1
    ImportacaoService().confirmar(variado, dono_id=dono.id, criar_novo=True)    # escolheu criar
    assert db.session.query(Curso).count() == 2


def test_curso_de_outro_dono_nunca_e_candidato(app):
    a, b = _usuario("a@t.com"), _usuario("b@t.com")
    ImportacaoService().confirmar(CSV, dono_id=a.id)
    _previa, destino = PreviaImportacaoService().previa_e_destino(CSV, dono_id=b.id)
    assert destino.candidatos == () and not destino.decisao_necessaria


def test_atualizar_sem_curso_csv_nao_mexe_no_curso_e_a_previa_diz(app):
    dono = _usuario("a@t.com")
    rel = ImportacaoService().confirmar(dict(CSV, **{"curso.csv": "nome,instituicao,duracao_semestres\nCiência da Computação,UFV,8\n"}),
                                        dono_id=dono.id)
    so_disc = {"disciplinas.csv": CSV["disciplinas.csv"] + "INF213,ED,obrigatoria\n"}
    _p, destino = PreviaImportacaoService().previa_e_destino(so_disc, curso_id=rel.curso_id, dono_id=dono.id)
    assert "não mudam" in destino.nota_curso
    ImportacaoService().confirmar(so_disc, curso_id=rel.curso_id, dono_id=dono.id)
    curso = db.session.get(Curso, rel.curso_id)
    assert (curso.nome, curso.duracao_semestres) == ("Ciência da Computação", 8)

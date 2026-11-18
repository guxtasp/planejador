"""Periodicidade de oferta (par/ímpar/sempre): domínio, importador, banco e API."""
import pytest

from planner.domain.entidades import Disciplina, PER_IMPAR, PER_PAR, PER_SEMPRE, Turma
from planner.domain.periodicidade import (
    HORARIO_PROJETADO, HORARIO_REAL, ORIGEM_CADASTRADA, ORIGEM_DESCONHECIDA, ORIGEM_ESTIMADA,
    numero_do_periodo, ofertada_em, paridade_do_periodo, periodicidade_efetiva,
    proximo_periodo_ofertado, turmas_para_periodo,
)


def test_paridade_segue_o_numero_do_periodo():
    assert numero_do_periodo("2026/2") == 2
    assert paridade_do_periodo("2026/1") == PER_IMPAR
    assert paridade_do_periodo("2027/2") == PER_PAR


def test_ofertada_em():
    assert ofertada_em(PER_IMPAR, "2027/1") and not ofertada_em(PER_IMPAR, "2027/2")
    assert ofertada_em(PER_PAR, "2027/2") and not ofertada_em(PER_PAR, "2027/1")
    assert ofertada_em(PER_SEMPRE, "2027/2") and ofertada_em(None, "2027/1")   # desconhecida não bloqueia


def test_proximo_periodo_ofertado():
    assert proximo_periodo_ofertado(PER_IMPAR, "2027/2") == "2028/1"
    assert proximo_periodo_ofertado(PER_PAR, "2027/2") == "2027/2"
    assert proximo_periodo_ofertado(PER_SEMPRE, "2027/2") == "2027/2"


def test_periodicidade_efetiva_marca_a_origem():
    d = Disciplina(1, "A", "A", 4, periodo_sugerido=3)
    e = periodicidade_efetiva(d)
    assert (e.valor, e.origem) == (PER_IMPAR, ORIGEM_ESTIMADA)
    e = periodicidade_efetiva(Disciplina(2, "B", "B", periodo_sugerido=4, periodicidade=PER_IMPAR))
    assert (e.valor, e.origem) == (PER_IMPAR, ORIGEM_CADASTRADA)           # cadastrada vence a estimativa
    e = periodicidade_efetiva(Disciplina(3, "C", "C"))
    assert (e.valor, e.origem) == (PER_SEMPRE, ORIGEM_DESCONHECIDA)
    e = periodicidade_efetiva(d, estimar=False)
    assert e.origem == ORIGEM_DESCONHECIDA


def test_turmas_projetadas_vem_do_periodo_de_mesma_paridade():
    t1, t2 = Turma(1, 9, periodo_letivo="2026/1"), Turma(2, 9, periodo_letivo="2026/2")
    real, origem = turmas_para_periodo([t1, t2], "2026/2")
    assert (real, origem) == ((t2,), HORARIO_REAL)
    proj, origem = turmas_para_periodo([t1, t2], "2028/1")
    assert (proj, origem) == ((t1,), HORARIO_PROJETADO)
    assert turmas_para_periodo([t1], "2028/2")[0] == ()


class TestImportador:
    CAB = "codigo,nome,tipo,periodicidade\n"

    def importar(self, corpo):
        from planner.importers.disciplinas import DisciplinaImporter
        return DisciplinaImporter().importar(self.CAB + corpo)

    @pytest.mark.parametrize("texto,esperado", [
        ("sempre", "sempre"), ("Ímpar", "impar"), ("PAR", "par"), ("semestre ímpar", "impar"),
        ("2º semestre", "par"), ("todo semestre", "sempre"), ("", None),
    ])
    def test_valores_aceitos(self, texto, esperado):
        r = self.importar(f"X1,Nome,obrigatoria,{texto}\n")
        assert not r.erros, r.issues
        assert r.registros[0].periodicidade == esperado

    def test_valor_invalido_e_erro(self):
        r = self.importar("X1,Nome,obrigatoria,quinzenal\n")
        assert [(i.linha, i.coluna) for i in r.erros] == [(2, "periodicidade")]

    def test_coluna_e_opcional_e_aceita_apelido(self):
        from planner.importers.disciplinas import DisciplinaImporter
        r = DisciplinaImporter().importar("codigo,nome,tipo,oferta\nX1,Nome,obrigatoria,par\n")
        assert r.registros[0].periodicidade == "par"
        r = DisciplinaImporter().importar("codigo,nome,tipo\nX1,Nome,obrigatoria\n")
        assert r.registros[0].periodicidade is None


def test_banco_recusa_periodicidade_invalida(app):
    from sqlalchemy.exc import IntegrityError
    from planner.extensions import db
    from planner.models import Curso, Disciplina as D
    with app.app_context():
        c = Curso(nome="C"); db.session.add(c); db.session.flush()
        db.session.add(D(curso_id=c.id, codigo="A", nome="A", periodicidade="quinzenal"))
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()

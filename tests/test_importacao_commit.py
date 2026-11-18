"""Etapa 3C — commit atômico: grava o que a prévia mostrou, e só isso."""
from pathlib import Path

import pytest
from sqlalchemy import func, select

from planner.api.errors import AppError, NotFoundError
from planner.extensions import db
from planner.models import Curso, Disciplina, Encontro, Requisito, Turma
from planner.repositories import TurmaRepository
from planner.services.importacao import ImportacaoService
from planner.services.previa_importacao import PreviaImportacaoService

EXEMPLO = Path(__file__).resolve().parent.parent / "examples" / "ciencia-da-computacao"
ARQUIVOS = {n: (EXEMPLO / n).read_bytes() for n in ("curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv")}
MODELOS = (Curso, Disciplina, Requisito, Turma, Encontro)


def contagens():
    return [db.session.scalar(select(func.count()).select_from(m)) for m in MODELOS]


def test_exemplo_de_cc_ponta_a_ponta(app):
    r = ImportacaoService().confirmar(ARQUIVOS)
    assert r.curso_criado
    assert r.por_arquivo["disciplinas.csv"] == {"criados": 49, "atualizados": 0, "inalterados": 0}
    assert r.por_arquivo["requisitos.csv"]["criados"] == 46
    assert r.por_arquivo["turmas.csv"]["criados"] == 61
    c, d, q, t, e = contagens()
    assert (c, d, q, t) == (1, 49, 46, 61) and e > 61
    curso = db.session.scalar(select(Curso))
    assert curso.visibilidade == "privado" and curso.nome == "Ciência da Computação"
    inf110 = db.session.scalar(select(Disciplina).where(Disciplina.codigo == "INF110"))
    assert (inf110.creditos, inf110.carga_h, inf110.periodo_sugerido) == (6, 90, 1)
    turma = TurmaRepository().obter_por_chave(inf110.id, "2026/1", "T1")
    assert [(x.dia, f"{x.inicio:%H:%M}") for x in turma.encontros] == [("QUI", "14:00"), ("SEG", "16:00"), ("SEX", "14:00")]


def test_segunda_importacao_nao_tem_o_que_gravar(app):
    ImportacaoService().confirmar(ARQUIVOS)
    antes = contagens()
    with pytest.raises(AppError) as erro:
        ImportacaoService().confirmar(ARQUIVOS)
    assert erro.value.status_code == 422 and "Nada a importar" in erro.value.message
    assert contagens() == antes


def test_atualiza_so_o_que_mudou_e_nao_apaga_com_celula_vazia(app):
    ImportacaoService().confirmar(ARQUIVOS)
    alterado = {"disciplinas.csv": (
        "codigo,nome,tipo,creditos\n"
        "INF110,Programação I (nova),obrigatoria,\n"      # créditos vazio: mantém 6
        "NOVA1,Disciplina nova,optativa,2\n")}
    r = ImportacaoService().confirmar(alterado, curso_id=db.session.scalar(select(Curso.id)))
    assert r.por_arquivo["disciplinas.csv"] == {"criados": 1, "atualizados": 1, "inalterados": 0}
    inf110 = db.session.scalar(select(Disciplina).where(Disciplina.codigo == "INF110"))
    assert (inf110.nome, inf110.creditos, inf110.carga_h) == ("Programação I (nova)", 6, 90)
    assert db.session.scalar(select(func.count()).select_from(Disciplina)) == 50   # nada foi removido


def test_atualiza_encontros_da_turma(app):
    ImportacaoService().confirmar(ARQUIVOS)
    r = ImportacaoService().confirmar(
        {"turmas.csv": "disciplina,periodo_letivo,codigo_turma,horarios\nINF110,2026/1,T1,TER 08:00-10:00\n"},
        curso_id=db.session.scalar(select(Curso.id)))
    assert r.por_arquivo["turmas.csv"]["atualizados"] == 1
    inf110 = db.session.scalar(select(Disciplina).where(Disciplina.codigo == "INF110"))
    turma = TurmaRepository().obter_por_chave(inf110.id, "2026/1", "T1")
    assert [(e.dia, f"{e.inicio:%H:%M}") for e in turma.encontros] == [("TER", "08:00")]
    assert db.session.scalar(select(func.count()).select_from(Turma)) == 61


def test_erro_na_validacao_nao_grava_nada(app):
    ruim = dict(ARQUIVOS, **{"requisitos.csv": "disciplina,requisito,tipo\nINF112,NAOEXISTE,pre\n"})
    with pytest.raises(AppError) as erro:
        ImportacaoService().confirmar(ruim)
    assert erro.value.status_code == 422 and erro.value.details["totais"]["erros"] == 1
    assert contagens() == [0] * 5


def test_falha_no_meio_da_gravacao_desfaz_tudo(app, monkeypatch):
    original = TurmaRepository.adicionar

    def quebra(self, turma):
        raise RuntimeError("falha simulada")
    monkeypatch.setattr(TurmaRepository, "adicionar", quebra)
    with pytest.raises(RuntimeError):
        ImportacaoService().confirmar(ARQUIVOS)   # curso, disciplinas e requisitos já tinham sido gravados
    assert contagens() == [0] * 5
    monkeypatch.setattr(TurmaRepository, "adicionar", original)
    ImportacaoService().confirmar(ARQUIVOS)       # e a sessão continua utilizável
    assert contagens()[0] == 1


def test_sem_curso_de_destino_e_erro(app):
    with pytest.raises(AppError, match="Informe o curso"):
        ImportacaoService().confirmar({"disciplinas.csv": "codigo,nome,tipo\nA1,Alfa,obrigatoria\n"})
    assert contagens() == [0] * 5


def test_curso_id_inexistente(app):
    with pytest.raises(NotFoundError):
        ImportacaoService().confirmar({"disciplinas.csv": "codigo,nome,tipo\nA1,Alfa,obrigatoria\n"}, curso_id=999)


def test_visibilidade_e_validada_e_aplicada(app):
    with pytest.raises(AppError, match="Visibilidade"):
        ImportacaoService().confirmar(ARQUIVOS, visibilidade="secreto")
    ImportacaoService().confirmar(ARQUIVOS, visibilidade="publico")
    assert db.session.scalar(select(Curso.visibilidade)) == "publico"


def test_historico_nao_faz_parte_da_importacao(app):
    arquivos = dict(ARQUIVOS, **{"historico.csv": "disciplina,status\nINF110,aprovado\n"})
    with pytest.raises(AppError, match="erros") as erro:
        ImportacaoService().confirmar(arquivos)
    assert "histórico do aluno" in str(erro.value.details)


def test_previa_e_commit_concordam(app):
    previa = PreviaImportacaoService().gerar(ARQUIVOS)
    r = ImportacaoService().confirmar(ARQUIVOS)
    assert sum(c["criados"] for c in r.por_arquivo.values()) == previa.novos


def test_turma_sem_horarios_no_arquivo_mantem_os_encontros_do_banco(app):
    ImportacaoService().confirmar(ARQUIVOS)
    ImportacaoService().confirmar(
        {"turmas.csv": "disciplina,periodo_letivo,codigo_turma,docente\nINF110,2026/1,T1,Profa. Ana\n"},
        curso_id=db.session.scalar(select(Curso.id)))
    inf110 = db.session.scalar(select(Disciplina).where(Disciplina.codigo == "INF110"))
    turma = TurmaRepository().obter_por_chave(inf110.id, "2026/1", "T1")
    assert turma.docente == "Profa. Ana" and len(turma.encontros) == 3


def test_curso_csv_com_celula_vazia_nao_apaga_dado_do_curso(app):
    ImportacaoService().confirmar({"curso.csv": "nome,ch_total,versao_matriz\nCurso Z,3000,2020\n"})
    ImportacaoService().confirmar({"curso.csv": "nome,ch_total,versao_matriz\nCurso Z,,2024\n"})
    curso = db.session.scalar(select(Curso))
    assert (curso.ch_total, curso.versao_matriz) == (3000, "2024")


def test_mensagem_distingue_erro_de_nada_a_importar(app):
    with pytest.raises(AppError, match="tem erros"):
        ImportacaoService().confirmar({"disciplinas.csv": "codigo,nome,tipo\nA1,Alfa,\n"}, curso_id=None)

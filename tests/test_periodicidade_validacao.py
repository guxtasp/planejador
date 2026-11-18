"""Aviso de periodicidade não informada e conferência de paridade das turmas (validação, sem banco)."""
from planner.importers import IMPORTADORES
from planner.importers.base import Severidade
from planner.importers.validacao import DisciplinaExistente, EstadoExistente, gerar_previa

DISC = "codigo,nome,tipo,periodicidade\n"
TUR = "disciplina,periodo_letivo,codigo_turma,horarios\n"


def previa(disciplinas, turmas=None, estado=None):
    leituras = {"disciplinas.csv": IMPORTADORES["disciplinas.csv"].importar(DISC + disciplinas)}
    if turmas is not None:
        leituras["turmas.csv"] = IMPORTADORES["turmas.csv"].importar(TUR + turmas)
    return gerar_previa(leituras, estado)


def avisos_de(p, coluna):
    return [i for i in p.issues if i.severidade == Severidade.AVISO and i.coluna == coluna]


def test_disciplina_sem_periodicidade_gera_um_aviso_com_a_lista():
    p = previa("A1,Alfa,obrigatoria,par\nB1,Beta,obrigatoria,\nC1,Gama,optativa,\n")
    (aviso,) = avisos_de(p, "periodicidade")
    assert "2 de 3" in aviso.mensagem and "B1, C1" in aviso.mensagem
    assert p.pode_confirmar          # continua sendo aviso, não erro


def test_tudo_informado_nao_avisa():
    p = previa("A1,Alfa,obrigatoria,par\nB1,Beta,obrigatoria,sempre\nC1,Gama,optativa,impar\n")
    assert avisos_de(p, "periodicidade") == []


def test_valor_ja_gravado_conta_como_informado_e_vazio_no_arquivo_nao_apaga():
    estado = EstadoExistente(disciplinas=(DisciplinaExistente("A1", "Alfa", "obrigatoria", periodicidade="impar"),))
    p = previa("A1,Alfa,obrigatoria,\n", estado=estado)
    assert avisos_de(p, "periodicidade") == []


def test_lista_do_aviso_e_truncada():
    corpo = "".join(f"D{i},Disc {i},obrigatoria,\n" for i in range(20))
    (aviso,) = avisos_de(previa(corpo), "periodicidade")
    assert "20 de 20" in aviso.mensagem and "e mais 8" in aviso.mensagem


def test_turma_em_periodo_de_outra_paridade_avisa():
    p = previa("A1,Alfa,obrigatoria,par\nB1,Beta,obrigatoria,impar\nC1,Gama,obrigatoria,sempre\nD1,Delta,obrigatoria,\n",
               turmas="A1,2026/1,T1,SEG 08:00-10:00\nB1,2026/1,T1,TER 08:00-10:00\nC1,2026/1,T1,QUA 08:00-10:00\nD1,2026/1,T1,QUI 08:00-10:00\n")
    (aviso,) = avisos_de(p, "periodo_letivo")
    assert "A1" in aviso.mensagem and "2026/1" in aviso.mensagem

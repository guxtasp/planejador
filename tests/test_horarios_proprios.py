"""Horários próprios: o aluno monta o calendário sem quadro importado (sem banco)."""
from datetime import time

import pytest

from planner.api.errors import AppError
from planner.domain.analise import ItemPlano, SemestrePlano, analisar_plano
from planner.domain.conflitos import CONFLITO
from planner.domain.entidades import Disciplina, Encontro, Turma
from planner.services.analise_json import encontros_para_json, ler_encontros_livres, ler_payload
from planner.services.planos_json import ler_plano, validar_referencias

SEG_8_10 = {"dia": "SEG", "inicio": "08:00", "fim": "10:00"}
SEG_9_11 = {"dia": "SEG", "inicio": "09:00", "fim": "11:00"}


def _disc(i):
    return Disciplina(i, f"D{i}", f"Disciplina {i}", 4)


def test_leitura_converte_para_encontros():
    assert ler_encontros_livres([SEG_8_10], "S1") == (Encontro("SEG", time(8), time(10)),)
    assert ler_encontros_livres(None, "S1") == () and ler_encontros_livres([], "S1") == ()


@pytest.mark.parametrize("bruto", [
    "x", [1], [{"dia": "XXX", "inicio": "08:00", "fim": "10:00"}],
    [{"dia": "SEG", "inicio": "8h", "fim": "10:00"}], [{"dia": "SEG", "inicio": "08:00"}],
    [{"dia": "SEG", "inicio": "10:00", "fim": "08:00"}], [{"dia": "SEG", "inicio": "08:00", "fim": "08:00"}],
    [SEG_8_10, SEG_9_11],                      # mesma disciplina, sobrepostos
    [SEG_8_10] * 15,
])
def test_leitura_recusa_formato_invalido(bruto):
    with pytest.raises(AppError):
        ler_encontros_livres(bruto, "S1")


def test_ida_e_volta_json():
    enc = ler_encontros_livres([SEG_8_10], "S1")
    assert encontros_para_json(enc) == [SEG_8_10]


def test_payload_da_analise_aceita_encontros_livres():
    (s,) = ler_payload({"semestres": [{"itens": [{"disciplina_id": 1, "encontros_livres": [SEG_8_10]}]}]})
    assert s.itens[0].encontros_livres == (Encontro("SEG", time(8), time(10)),)


def test_conflito_entre_dois_horarios_proprios_sem_nenhuma_turma_no_curso():
    disc = {1: _disc(1), 2: _disc(2)}
    sem = SemestrePlano((
        ItemPlano(1, None, ler_encontros_livres([SEG_8_10], "S")),
        ItemPlano(2, None, ler_encontros_livres([SEG_9_11], "S")),
    ), None)   # sem período letivo e sem turmas: ainda assim julga
    (a,) = analisar_plano([sem], disc, {}, {}, None)
    assert [c.tipo for c in a.conflitos] == [CONFLITO]
    assert a.sem_turma_escolhida == () and a.invalidos == ()


def test_horario_proprio_nao_colide_se_apenas_encosta():
    disc = {1: _disc(1), 2: _disc(2)}
    outro = {"dia": "SEG", "inicio": "10:00", "fim": "12:00"}
    sem = SemestrePlano((
        ItemPlano(1, None, ler_encontros_livres([SEG_8_10], "S")),
        ItemPlano(2, None, ler_encontros_livres([outro], "S")),
    ))
    assert analisar_plano([sem], disc, {}, {}, None)[0].conflitos == ()


def test_horario_proprio_conflita_com_turma_escolhida_de_outra_disciplina():
    disc = {1: _disc(1), 2: _disc(2)}
    turma = Turma(7, 2, (Encontro("SEG", time(9), time(11)),), "2026/1", "T1")
    sem = SemestrePlano((
        ItemPlano(1, None, ler_encontros_livres([SEG_8_10], "S")),
        ItemPlano(2, 7),
    ), "2026/1")
    (a,) = analisar_plano([sem], disc, {}, {2: [turma]}, None)
    assert [c.tipo for c in a.conflitos] == [CONFLITO]


def test_horario_proprio_vale_no_lugar_da_turma_informada():
    disc = {1: _disc(1)}
    turma = Turma(7, 1, (Encontro("TER", time(9), time(11)),), "2026/1", "T1")
    sem = SemestrePlano((ItemPlano(1, 7, ler_encontros_livres([SEG_8_10], "S")),), "2026/1")
    (a,) = analisar_plano([sem], disc, {}, {1: [turma]}, None)
    assert a.invalidos == () and a.sem_turma_escolhida == ()


def _plano(item):
    return {"nome": "p", "semestres": [{"periodo_letivo": None, "itens": [item]}]}


def test_plano_recusa_turma_e_horario_proprio_juntos():
    entrada = ler_plano(_plano({"disciplina_id": 1, "turma_id": 5, "encontros_livres": [SEG_8_10]}))
    with pytest.raises(AppError, match="OU horários próprios"):
        validar_referencias(entrada, {1}, {5: (1, "2026/1")})


def test_plano_aceita_horario_proprio_em_semestre_sem_periodo():
    entrada = ler_plano(_plano({"disciplina_id": 1, "turma_id": None, "encontros_livres": [SEG_8_10]}))
    validar_referencias(entrada, {1}, {})   # não levanta
    assert entrada.semestres[0].itens[0].encontros_livres[0].dia == "SEG"

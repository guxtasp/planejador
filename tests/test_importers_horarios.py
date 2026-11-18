"""Etapa 3A — parser de horários: "SEG 16:00-18:00 | QUI 14:00-16:00"."""
from datetime import time

import pytest

from planner.domain.entidades import Encontro
from planner.importers.horarios import parse_dia, parse_horarios


def test_varios_encontros_da_mesma_turma():
    enc, erros = parse_horarios("SEG 16:00-18:00 | QUI 14:00-16:00 | SEX 14:00-16:00")
    assert not erros
    assert enc == (Encontro("SEG", time(16), time(18)),
                   Encontro("QUI", time(14), time(16)),
                   Encontro("SEX", time(14), time(16)))


def test_um_unico_encontro_e_espacos_extras():
    enc, erros = parse_horarios("  qua   8:00  –  9:50 ")
    assert not erros and enc == (Encontro("QUA", time(8, 0), time(9, 50)),)


@pytest.mark.parametrize("texto, sigla", [
    ("seg", "SEG"), ("Terça", "TER"), ("QUARTA-FEIRA", "QUA"), ("qui", "QUI"),
    ("Sexta", "SEX"), ("sáb", "SAB"), ("Sábado", "SAB"), ("dom", "DOM"),
])
def test_dias_aceitos(texto, sigla):
    assert parse_dia(texto) == sigla


def test_dia_por_extenso_no_horario():
    enc, erros = parse_horarios("Terça-feira 10:00-12:00")
    assert not erros and enc[0].dia == "TER"


def test_barra_sobrando_e_ignorada():
    enc, erros = parse_horarios("SEG 08:00-10:00 | ")
    assert not erros and len(enc) == 1


@pytest.mark.parametrize("texto, trecho", [
    ("XYZ 08:00-10:00", "Dia 'XYZ' inválido"),
    ("SEG 25:00-26:00", "Hora inexistente"),
    ("SEG 08:70-09:00", "Hora inexistente"),
    ("SEG 10:00-08:00", "fim deve ser depois"),
    ("SEG 10:00-10:00", "fim deve ser depois"),
    ("SEG 8h-10h", "fora do formato"),
    ("SEG 08:00", "fora do formato"),
    ("08:00-10:00", "fora do formato"),
])
def test_erros_de_formato(texto, trecho):
    enc, erros = parse_horarios(texto)
    assert enc == () and len(erros) == 1 and trecho in erros[0]


def test_um_encontro_ruim_nao_esconde_os_outros_erros():
    enc, erros = parse_horarios("SEG 08:00-10:00 | QUA 12:00-11:00 | XXX 08:00-09:00")
    assert len(enc) == 1 and len(erros) == 2

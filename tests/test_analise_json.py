"""Etapa 4B — leitura do corpo e formato JSON da análise (sem banco)."""
from datetime import time

import pytest

from planner.api.errors import AppError
from planner.domain.analise import ItemPlano, SemestrePlano, analisar_plano
from planner.domain.entidades import REQ_PRE, Disciplina, Encontro, Requisito, Turma
from planner.services.analise_json import ler_payload, serializar_semestre


def test_ler_payload_converte_para_entidades_do_dominio():
    (s,) = ler_payload({"semestres": [{"periodo_letivo": "2026/1", "itens": [
        {"disciplina_id": 1, "turma_id": 5}, {"disciplina_id": 2}]}]})
    assert s == SemestrePlano((ItemPlano(1, 5), ItemPlano(2, None)), "2026/1")


def test_periodo_vazio_vira_none():
    (s,) = ler_payload({"semestres": [{"periodo_letivo": "", "itens": []}]})
    assert s.periodo_letivo is None


@pytest.mark.parametrize("corpo", [
    None, [], {}, {"semestres": "x"}, {"semestres": [1]}, {"semestres": [{"itens": "x"}]},
    {"semestres": [{"itens": [1]}]}, {"semestres": [{"itens": [{"disciplina_id": "1"}]}]},
    {"semestres": [{"itens": [{"disciplina_id": True}]}]},
    {"semestres": [{"itens": [{"disciplina_id": 1, "turma_id": 1.5}]}]},
    {"semestres": [{"periodo_letivo": 5, "itens": []}]},
    {"semestres": [{"itens": []}] * 21},
    {"semestres": [{"itens": [{"disciplina_id": 1}] * 41}]},
])
def test_corpo_malformado_levanta_erro_400(corpo):
    with pytest.raises(AppError) as e:
        ler_payload(corpo)
    assert e.value.status_code == 400


def test_serializacao_traz_codigos_horarios_e_alternativas():
    h = lambda s: time(*map(int, s.split(":")))
    discs = {1: Disciplina(1, "A1", "Alfa", 4), 2: Disciplina(2, "B1", "Beta", 4)}
    turmas = {1: [Turma(10, 1, (Encontro("SEG", h("08:00"), h("10:00")),), "2026/1", "T1")],
              2: [Turma(20, 2, (Encontro("SEG", h("09:00"), h("11:00")),), "2026/1", "T1")]}
    reqs = {2: [Requisito(2, 1, REQ_PRE)]}
    (a,) = analisar_plano(
        [SemestrePlano((ItemPlano(1, 10), ItemPlano(2, 20)), "2026/1")], discs, reqs, turmas, 6)
    j = serializar_semestre(a, discs)
    assert j["posicao"] == 1 and j["creditos"] == 8 and j["limite_creditos"] == 6 and j["sobrecarga"]
    (c,) = j["conflitos"]
    assert (c["tipo"], c["dia"], c["horario_a"], c["horario_b"]) == ("conflito", "SEG", "08:00–10:00", "09:00–11:00")
    assert (c["a"]["codigo"], c["b"]["codigo"]) == ("A1", "B1")
    (p,) = j["pendencias"]
    assert p["disciplina"]["codigo"] == "B1" and p["tipo"] == "pre" and not p["e_alternativa"]
    assert [x["codigo"] for x in p["alternativas"]] == ["A1"]
    import json
    json.dumps(j)   # tudo serializável

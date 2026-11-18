"""Etapa 5B-2 — validação e serialização JSON (sem banco)."""
from types import SimpleNamespace as NS

import pytest

from planner.api.errors import AppError
from planner.domain.entidades import Disciplina
from planner.domain.painel import montar_painel
from planner.services.historico_json import ler_tentativa, serializar_tentativa
from planner.services.painel_json import serializar_painel
from planner.services.planos_json import ler_plano, serializar_plano, validar_referencias


# ── histórico ────────────────────────────────────────────────────────────────
def test_tentativa_valida_normaliza_periodo_e_arredonda_nota():
    t = ler_tentativa({"disciplina_id": 3, "status": "aprovado", "periodo_letivo": "2024.1", "nota": 7.256},
                      com_disciplina=True)
    assert (t.disciplina_id, t.periodo_letivo, t.nota) == (3, "2024/1", 7.26)


def test_periodo_e_nota_sao_opcionais():
    t = ler_tentativa({"disciplina_id": 3, "status": "cursando", "periodo_letivo": "  ", "nota": None},
                      com_disciplina=True)
    assert t.periodo_letivo is None and t.nota is None


@pytest.mark.parametrize("corpo", [
    None, [], {"status": "aprovado"}, {"disciplina_id": "3", "status": "aprovado"},
    {"disciplina_id": True, "status": "aprovado"},
    {"disciplina_id": 3, "status": "trancado"},
    {"disciplina_id": 3, "status": "aprovado", "periodo_letivo": "2024/3"},
    {"disciplina_id": 3, "status": "aprovado", "periodo_letivo": 20241},
    {"disciplina_id": 3, "status": "aprovado", "nota": -1},
    {"disciplina_id": 3, "status": "aprovado", "nota": 101},
    {"disciplina_id": 3, "status": "aprovado", "nota": "8"},
    {"disciplina_id": 3, "status": "aprovado", "nota": float("nan")},
    {"disciplina_id": 3, "status": "aprovado", "nota": True},
])
def test_tentativa_invalida_vira_erro(corpo):
    with pytest.raises(AppError):
        ler_tentativa(corpo, com_disciplina=True)


def test_na_edicao_a_disciplina_nao_e_exigida_nem_lida():
    t = ler_tentativa({"disciplina_id": 99, "status": "reprovado"}, com_disciplina=False)
    assert t.disciplina_id is None and t.status == "reprovado"


def test_serializar_tentativa_mantem_desconhecido_como_null():
    h = NS(id=1, disciplina_id=2, status="cursando", periodo_letivo=None, nota=None,
           disciplina=NS(codigo="A1", nome="Alfa", creditos=None, periodo_sugerido=None))
    j = serializar_tentativa(h)
    assert j["creditos"] is None and j["nota"] is None and j["periodo_letivo"] is None


# ── planos ───────────────────────────────────────────────────────────────────
def plano_ok(**extra):
    return {"nome": "  Meu plano ", "semestres": [
        {"rotulo": "S1", "periodo_letivo": "2026.1", "itens": [{"disciplina_id": 1, "turma_id": 10}]},
        {"periodo_letivo": None, "itens": [{"disciplina_id": 2, "turma_id": None}]},
    ], **extra}


def test_plano_valido_e_normalizado():
    p = ler_plano(plano_ok())
    assert p.nome == "Meu plano"
    assert p.semestres[0].periodo_letivo == "2026/1"
    assert p.semestres[1].rotulo == "Semestre 2"          # rótulo vazio ganha padrão


@pytest.mark.parametrize("corpo", [
    None, [], {}, {"nome": ""}, {"nome": 3}, {"nome": "x" * 201},
    {"nome": "x", "semestres": "a"}, {"nome": "x", "semestres": [1]},
    {"nome": "x", "semestres": [{"itens": "a"}]},
    {"nome": "x", "semestres": [{"periodo_letivo": "2026/9", "itens": []}]},
    {"nome": "x", "semestres": [{"rotulo": "r" * 51}]},
    {"nome": "x", "semestres": [{"itens": [{"disciplina_id": "1"}]}]},
    {"nome": "x", "semestres": [{"itens": [{"disciplina_id": 1, "turma_id": "2"}]}]},
    {"nome": "x", "semestres": [{}] * 21},
    {"nome": "x", "semestres": [{"itens": [{"disciplina_id": i} for i in range(41)]}]},
])
def test_plano_invalido_vira_erro(corpo):
    with pytest.raises(AppError):
        ler_plano(corpo)


def test_plano_sem_semestres_e_aceito():
    assert ler_plano({"nome": "Vazio"}).semestres == ()


TURMAS = {10: (1, "2026/1"), 11: (1, "2026/2"), 20: (2, "2026/1")}


def test_referencias_validas_passam():
    validar_referencias(ler_plano(plano_ok()), {1, 2}, TURMAS)


@pytest.mark.parametrize("mexer,trecho", [
    (lambda c: c["semestres"][1]["itens"].append({"disciplina_id": 99}), "não pertence a este curso"),
    (lambda c: c["semestres"][1]["itens"].append({"disciplina_id": 1}), "mais de uma vez"),
    (lambda c: c["semestres"][0]["itens"].__setitem__(0, {"disciplina_id": 1, "turma_id": 20}), "não pertence à disciplina"),
    (lambda c: c["semestres"][0]["itens"].__setitem__(0, {"disciplina_id": 1, "turma_id": 11}), "outro período"),
    (lambda c: c["semestres"][1]["itens"].__setitem__(0, {"disciplina_id": 2, "turma_id": 20}), "período letivo antes"),
    (lambda c: c["semestres"][0]["itens"].__setitem__(0, {"disciplina_id": 1, "turma_id": 777}), "não pertence à disciplina"),
])
def test_referencias_invalidas_dao_422(mexer, trecho):
    corpo = plano_ok()
    mexer(corpo)
    with pytest.raises(AppError) as e:
        validar_referencias(ler_plano(corpo), {1, 2}, TURMAS)
    assert e.value.status_code == 422 and trecho in e.value.message


def test_serializar_plano_ordena_semestres_e_itens():
    d = lambda i, cod: NS(codigo=cod)
    item = lambda did, cod, tid=None: NS(disciplina_id=did, turma_id=tid, disciplina=d(did, cod))
    plano = NS(id=5, nome="P", semestres=[
        NS(ordem=2, label="B", periodo_letivo=None, itens=[]),
        NS(ordem=1, label="A", periodo_letivo="2026/1", itens=[item(2, "ZZZ"), item(1, "AAA", 10)]),
    ])
    j = serializar_plano(plano)
    assert [s["rotulo"] for s in j["semestres"]] == ["A", "B"]
    assert [i["disciplina_id"] for i in j["semestres"][0]["itens"]] == [1, 2]
    assert j["semestres"][0]["itens"][0]["turma_id"] == 10
    assert "encontros_livres" not in j["semestres"][0]["itens"][0]   # contrato anterior intacto


def test_serializar_plano_inclui_horarios_proprios_quando_existem():
    proprios = [{"dia": "SEG", "inicio": "08:00", "fim": "10:00"}]
    item = NS(disciplina_id=1, turma_id=None, encontros_livres=proprios, disciplina=NS(codigo="A"))
    plano = NS(id=1, nome="P", semestres=[NS(ordem=1, label="A", periodo_letivo=None, itens=[item])])
    assert serializar_plano(plano)["semestres"][0]["itens"][0]["encontros_livres"] == proprios


# ── painel ───────────────────────────────────────────────────────────────────
def test_serializar_painel_traz_pendencias_com_codigo_e_previsao_nula_sem_base():
    ds = {1: Disciplina(1, "A1", "Alfa", 4), 2: Disciplina(2, "B1", "Beta", 4)}
    from planner.domain.entidades import Requisito
    p = montar_painel(list(ds.values()), {2: [Requisito(2, 1, "pre")]}, [], creditos_obrigatorios=8)
    j = serializar_painel(p, ds)
    beta = next(d for d in j["disciplinas"] if d["id"] == 2)
    assert beta["situacao"] == "bloqueada"
    assert beta["pendencias"][0]["alternativas"] == [{"id": 1, "codigo": "A1", "nome": "Alfa"}]
    assert j["previsao"]["formatura"] is None and j["progresso"]["percentual"] == 0.0

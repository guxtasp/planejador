"""Peças 3/4 (parte C) — leitura dos pedidos e textos do simulador. Sem banco."""
import pytest

from planner.api.errors import AppError
from planner.domain.simulacao import R_FORA_DE_OFERTA, R_PRE_REQUISITO, Risco
from planner.domain.entidades import Disciplina
from planner.services.simulacao_json import (ler_edicoes_periodicidade, ler_pedido_simulacao,
                                             ler_pedido_sugestao, mensagem_risco, proximo_periodo_livre)

CAT = {1: Disciplina(1, "INF110", "Programação I"), 2: Disciplina(2, "INF112", "Programação II")}


def test_todo_risco_tem_frase_e_acao_em_portugues_nunca_so_o_codigo():
    r = Risco(R_FORA_DE_OFERTA, "alta", 1, "2027/2", (1,), {"periodicidade": "impar", "proximo_periodo": "2028/1"})
    msg, acao = mensagem_risco(r, CAT)
    assert "INF110" in msg and "2027/2" in msg and "ímpares" in msg
    assert acao and "2028/1" in acao


def test_mensagem_de_prerequisito_diz_quem_exige_o_que():
    r = Risco(R_PRE_REQUISITO, "alta", 1, "2027/1", (2,), {"tipo": "pre", "alternativas": [1]})
    msg, acao = mensagem_risco(r, CAT)
    assert "INF112" in msg and "INF110" in msg and "anterior" in acao


def test_periodo_do_pedido_e_normalizado_e_invalido_da_erro_claro():
    semestres, inicial = ler_pedido_simulacao({"semestres": [{"periodo_letivo": "2027.1", "itens": []}], "periodo_inicial": "2027-2"})
    assert semestres[0].periodo_letivo == "2027/1" and inicial == "2027/2"
    with pytest.raises(AppError) as e:
        ler_pedido_simulacao({"semestres": [{"periodo_letivo": "abc", "itens": []}]})
    assert e.value.status_code == 422 and "Semestre 1" in e.value.message


def test_pedido_de_sugestao_valida_limites():
    assert ler_pedido_sugestao(None)["semestres_extras"] == 0
    for ruim in ({"max_creditos": 0}, {"max_creditos": 99}, {"semestres_extras": 9}, {"optativas": ["x"]}, {"max_creditos": "8"}):
        with pytest.raises(AppError):
            ler_pedido_sugestao(ruim)


def test_proximo_periodo_livre_vem_do_historico_nunca_da_data():
    assert proximo_periodo_livre(["2025/2", "2026.1", None]) == "2026/2"
    assert proximo_periodo_livre(["2026/2"]) == "2027/1"
    assert proximo_periodo_livre([None, "lixo"]) is None


def test_edicao_de_oferta_aceita_so_valores_conhecidos():
    assert ler_edicoes_periodicidade({"itens": [{"disciplina_id": 1, "periodicidade": "impar"},
                                                {"disciplina_id": 2, "periodicidade": None}]}) == {1: "impar", 2: None}
    for ruim in ({}, {"itens": []}, {"itens": [{"disciplina_id": 1, "periodicidade": "talvez"}]},
                 {"itens": [{"disciplina_id": "1", "periodicidade": "par"}]}):
        with pytest.raises(AppError):
            ler_edicoes_periodicidade(ruim)


def test_pedido_de_sugestao_le_optativas_faltando_e_feitas():
    vazio = ler_pedido_sugestao(None)
    assert vazio["optativas_faltando"] is None and vazio["optativas_feitas"] == []      # None = o app calcula
    ok = ler_pedido_sugestao({"optativas_faltando": 0, "optativas_feitas": [3, 3, 1]})
    assert ok["optativas_faltando"] == 0 and ok["optativas_feitas"] == [1, 3]           # 0 é um número válido
    for ruim in ({"optativas_faltando": -1}, {"optativas_faltando": "9"}, {"optativas_feitas": "x"}, {"optativas_feitas": [True]}):
        with pytest.raises(AppError):
            ler_pedido_sugestao(ruim)

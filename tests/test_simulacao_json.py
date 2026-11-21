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


def test_cadeia_critica_sai_com_periodos_e_frase_pronta():
    from planner.domain.entidades import Requisito
    from planner.domain.otimizador import otimizar_plano
    from planner.services.simulacao_json import serializar_sugestao
    cat = {1: Disciplina(1, "INF110", "Programação I", 4, periodicidade="sempre"),
           2: Disciplina(2, "INF112", "Programação II", 4, periodicidade="sempre"),
           3: Disciplina(3, "INF213", "Estruturas de Dados", 4, periodicidade="sempre")}
    reqs = {1: [], 2: [Requisito(2, 1)], 3: [Requisito(3, 2)]}
    j = serializar_sugestao(otimizar_plano(cat, reqs, {}, set(), "2027/1"), cat, "S")
    assert [c["disciplina"]["codigo"] for c in j["cadeia_critica"]] == ["INF110", "INF112", "INF213"]
    assert [c["periodo"] for c in j["cadeia_critica"]] == ["2027/1", "2027/2", "2028/1"]
    assert j["cadeia_mensagem"].startswith("Programação I → Programação II → Estruturas de Dados")


# ── Fase 2: preferências ─────────────────────────────────────────────────────
def test_preferencias_sao_lidas_e_normalizadas():
    from planner.services.simulacao_json import ler_preferencias
    p = ler_preferencias({"preferencias": {
        "indisponiveis": [{"dia": "seg", "inicio": "08:00", "fim": "12:00", "motivo": "trabalho"}],
        "turno": "noite", "dias_livres": ["sex", "SEG"], "teto_por_periodo": {"2028.1": 12},
        "periodos_pulados": ["2028-2"], "max_pesadas": 2, "pesadas": [3, 3], "fator_prazo_maximo": 2,
        "periodo_ingresso": "2024/1", "simulacoes": 100}})
    assert p["semana"].indisponiveis[0].dia == "SEG" and p["semana"].indisponiveis[0].motivo == "trabalho"
    assert p["semana"].dias_livres == ("SEG", "SEX") and p["semana"].turno == "noite"
    assert p["teto_por_periodo"] == {"2028/1": 12} and p["periodos_pulados"] == frozenset({"2028/2"})
    assert p["pesadas_marcadas"] == [3] and p["fator_prazo"] == 2.0 and p["simulacoes"] == 100


def test_sem_preferencias_tudo_vazio_e_padroes():
    from planner.services.simulacao_json import ler_preferencias
    p = ler_preferencias({})
    assert p["semana"] is None and p["max_pesadas"] is None and p["fator_prazo"] == 1.5 and p["simulacoes"] == 500


def test_erro_de_preferencia_diz_qual_campo():
    from planner.services.simulacao_json import ler_preferencias
    casos = [
        ({"indisponiveis": [{"dia": "XYZ", "inicio": "08:00", "fim": "10:00"}]}, "indisponiveis.0.dia"),
        ({"indisponiveis": [{"dia": "SEG", "inicio": "10:00", "fim": "08:00"}]}, "indisponiveis.0.fim"),
        ({"indisponiveis": [{"dia": "SEG", "inicio": "8h", "fim": "10:00"}]}, "indisponiveis.0.inicio"),
        ({"turno": "madrugada"}, "turno"),
        ({"max_pesadas": 0}, "max_pesadas"),
        ({"fator_prazo_maximo": 5}, "fator_prazo_maximo"),
        ({"periodo_ingresso": "abc"}, "periodo_ingresso"),
        ({"periodos_pulados": ["x"]}, "periodos_pulados"),
        ({"simulacoes": 10}, "simulacoes"),
        ({"teto_por_periodo": {"2028/1": 0}}, "teto_por_periodo"),
    ]
    for pref, campo in casos:
        with pytest.raises(AppError) as e:
            ler_preferencias({"preferencias": pref})
        assert e.value.status_code == 422 and e.value.details == {"campo": campo}, pref


def test_mensagens_de_prazo():
    from planner.domain.prazo import avaliar_prazo
    from planner.services.simulacao_json import prazo_json
    j = prazo_json(avaliar_prazo("2024/1", "2028/2", 8), "2024/1", "historico", "2028/2", False, 1.5)
    assert "2 semestres além da duração (8)" in j["mensagem"] and "Dentro do prazo máximo (12)" in j["mensagem"]
    assert "não informa a duração" in prazo_json(avaliar_prazo("2024/1", "2028/2", None), "2024/1", "historico",
                                                 "2028/2", False, 1.5)["mensagem"]
    assert "ingresso" in prazo_json(avaliar_prazo(None, "2028/2", 8), None, None, "2028/2", False, 1.5)["mensagem"]

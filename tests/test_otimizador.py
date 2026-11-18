"""Peça 4 (parte B) — sugestão de plano: grafos + guloso + recozimento simulado. Domínio puro, sem banco."""
from planner.domain.entidades import Disciplina, Requisito
from planner.domain.otimizador import (LIM_OFERTA, LIM_REQUISITOS, M_CICLO, ParametrosOtimizacao,
                                       distribuir_optativas, encaixar_optativas, otimizar_plano)


def disc(i, creditos=4, per=None, sug=None, tipo="obrigatoria"):
    return Disciplina(i, f"D{i}", f"Disciplina {i}", creditos, tipo, sug, per)


def pre(d, r):
    return Requisito(d, r, "pre")


def posicao_de(res):
    return {it.disciplina_id: s.posicao for s in res.semestres for it in s.itens}


def rodar(discs, reqs, concluidas=(), inicio="2027/1", **kw):
    catalogo = {d.id: d for d in discs}
    requisitos = {d.id: [] for d in discs}
    for r in reqs:
        requisitos[r.disciplina_id].append(r)
    return otimizar_plano(catalogo, requisitos, {}, set(concluidas), inicio,
                          ParametrosOtimizacao(**kw))


def test_cadeia_de_prerequisitos_leva_um_semestre_por_elo_e_e_otima():
    res = rodar([disc(1, per="sempre"), disc(2, per="sempre"), disc(3, per="sempre")], [pre(2, 1), pre(3, 2)])
    assert res.viavel and res.metricas.n_semestres == 3
    pos = posicao_de(res)
    assert pos[1] < pos[2] < pos[3]
    assert res.otimo_comprovado and res.limite_inferior == 3 and res.limitado_por == LIM_REQUISITOS


def test_oferta_impar_alonga_o_prazo_e_o_motivo_e_a_oferta():
    # 2 só abre em período ímpar; começando em 2027/1, 1 ocupa 2027/1 e 2 só pode ir para 2028/1
    res = rodar([disc(1, per="sempre"), disc(2, per="impar")], [pre(2, 1)])
    assert res.viavel and res.metricas.n_semestres == 3
    assert res.semestres[-1].periodo == "2028/1"
    assert res.limitado_por == LIM_OFERTA


def test_respeita_o_teto_de_creditos_por_semestre():
    res = rodar([disc(i, creditos=4, per="sempre") for i in range(1, 5)], [], max_creditos=8)
    assert res.viavel
    assert all(s.creditos <= 8 for s in res.semestres)
    assert res.metricas.n_semestres == 2 and res.otimo_comprovado


def test_ciclo_de_prerequisitos_e_inviavel_com_motivo():
    res = rodar([disc(1, per="sempre"), disc(2, per="sempre")], [pre(1, 2), pre(2, 1)])
    assert not res.viavel and res.motivo == M_CICLO and res.ciclos


def test_o_que_ja_foi_concluido_nao_entra_na_sugestao():
    res = rodar([disc(1, per="sempre"), disc(2, per="sempre")], [pre(2, 1)], concluidas={1})
    assert posicao_de(res) == {2: 1}


def test_requisito_optativo_de_obrigatoria_entra_marcado():
    res = rodar([disc(1, per="sempre"), disc(2, per="sempre", tipo="optativa")], [pre(1, 2)])
    assert 2 in res.incluidas_por_requisito
    assert any(i.incluida_por_requisito for s in res.semestres for i in s.itens if i.disciplina_id == 2)


def test_mesma_semente_mesmo_resultado():
    discs = [disc(i, per="sempre") for i in range(1, 9)]
    reqs = [pre(3, 1), pre(4, 2), pre(6, 3), pre(7, 4)]
    a, b = rodar(discs, reqs, max_creditos=12), rodar(discs, reqs, max_creditos=12)
    assert posicao_de(a) == posicao_de(b)


def test_folga_voluntaria_acrescenta_semestres_e_alivia_a_carga():
    discs = [disc(i, per="sempre") for i in range(1, 7)]
    rapido = rodar(discs, [], max_creditos=24)
    leve = rodar(discs, [], max_creditos=24, semestres_extras=2)
    assert leve.metricas.n_semestres >= rapido.metricas.n_semestres
    assert leve.metricas.carga_maxima <= rapido.metricas.carga_maxima


def test_distribuir_optativas_enche_o_semestre_mais_leve_primeiro():
    # enchimento por nível: o de carga 2 sobe até empatar com o de 6 e os dois dividem o resto
    extra, criados = distribuir_optativas([8, 2, 6], teto=8, faltando=6)
    assert extra == [0, 5, 1] and criados == 0


def test_distribuir_optativas_cria_semestres_quando_nao_ha_espaco():
    extra, criados = distribuir_optativas([8, 8], teto=8, faltando=10)
    assert criados >= 1 and sum(extra) == 10


def test_encaixar_optativas_nunca_cria_semestre_e_devolve_o_que_sobrou():
    extra, sobra = encaixar_optativas([8, 8], teto=8, faltando=10)
    assert extra == [0, 0] and sobra == 10
    extra, sobra = encaixar_optativas([8, 2, 6], teto=8, faltando=9)
    assert sum(extra) == 8 and sobra == 1 and len(extra) == 3


def test_optativas_nao_adiam_a_formatura_em_silencio():
    # 6 disciplinas de 4 créditos, teto 12: 2 semestres cheios. 9 créditos de optativas não cabem.
    discs = [disc(i, per="sempre") for i in range(1, 7)]
    res = rodar(discs, [], max_creditos=12, optativas_faltando=9)
    assert res.viavel and res.metricas.n_semestres == 2 and res.metricas.periodo_fim == "2027/2"
    assert res.optativas_encaixadas == 0 and res.optativas_sem_encaixe == 9
    assert res.periodo_fim_com_optativas == "2028/1"        # a data com optativas aparece ao lado
    assert all(s.creditos_optativos == 0 for s in res.semestres)


def test_optativas_que_cabem_nao_mudam_a_data_nem_criam_semestre():
    discs = [disc(i, per="sempre") for i in range(1, 7)]
    res = rodar(discs, [], max_creditos=20, optativas_faltando=8)
    assert res.optativas_sem_encaixe == 0 and res.optativas_encaixadas == 8
    assert res.metricas.n_semestres == 2
    assert res.periodo_fim_com_optativas == res.metricas.periodo_fim
    assert sum(s.creditos_optativos for s in res.semestres) == 8


def test_sem_optativas_faltando_as_duas_datas_coincidem():
    res = rodar([disc(1, per="sempre")], [], max_creditos=12)
    assert res.optativas_reservadas == 0 and res.periodo_fim_com_optativas == res.metricas.periodo_fim


def test_so_optativas_a_cumprir_formam_os_proprios_semestres():
    res = otimizar_plano({}, {}, {}, set(), "2027/1", ParametrosOtimizacao(max_creditos=12, optativas_faltando=20))
    assert res.viavel and len(res.semestres) == 2 and res.optativas_sem_encaixe == 0


def test_sugestao_com_disciplinas_roda_o_replanejamento_sem_quebrar():
    # regressão: `requisitos_originais` não era atribuído e a sugestão dava AttributeError
    res = rodar([disc(1, per="sempre"), disc(2, per="sempre")], [pre(2, 1)])
    assert res.viavel and res.metricas.atraso_maximo_reprovacao >= 0

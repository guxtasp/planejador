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


def test_optativas_entram_no_plano_com_espaco_no_meio():
    # 6 obrigatórias de 4 cr + 9 cr de optativas, teto 12: 33 cr pedem 3 semestres, e o plano já nasce com
    # espaço para as optativas (antes elas ficavam de fora e só "adiavam" a data no fim)
    discs = [disc(i, per="sempre") for i in range(1, 7)]
    res = rodar(discs, [], max_creditos=12, optativas_faltando=9)
    assert res.viavel and res.metricas.n_semestres == 3 and res.optativas_sem_encaixe == 0
    assert res.periodo_fim_com_optativas == "2028/1" and sum(s.creditos_optativos for s in res.semestres) == 9
    assert all(s.creditos + s.creditos_optativos <= 12 for s in res.semestres)


def test_optativas_preferem_o_meio_do_curso():
    # 5 semestres de cadeia; 4 cr de optativa sem lugar obrigatório: vai para o meio, não para o fim
    discs = [disc(i, per="sempre") for i in range(1, 6)]
    res = rodar(discs, [pre(i + 1, i) for i in range(1, 5)], max_creditos=8, optativas_faltando=4)
    meio = [s.creditos_optativos for s in res.semestres]
    assert meio.index(max(meio)) in (1, 2, 3) and meio[-1] == 0


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


# ── Fase 1: grafos, limites, metaheurística ──────────────────────────────────
import random
import time

from planner.domain import otimizador as ot
from planner.domain.grafo import (alturas, cadeia_critica, construir_grafo, horizonte_por_janelas,
                                  limite_energetico, pesos_posicionais, primeiros_semestres, ultimos_semestres)
from planner.domain.restante import CalendarioDeOferta, nos_a_cursar, periodicidades_efetivas


def co(d, r):
    return Requisito(d, r, "co")


def grafo_de(discs, reqs):
    requisitos = {d.id: [] for d in discs}
    for r in reqs:
        requisitos[r.disciplina_id].append(r)
    return construir_grafo([d.id for d in discs], requisitos, ())


def test_altura_e_o_caminho_mais_longo_ate_o_fim_com_co_valendo_zero():
    discs = [disc(i, per="sempre") for i in range(1, 6)]
    g = grafo_de(discs, [pre(2, 1), pre(3, 2), co(4, 3), pre(5, 1)])
    assert alturas(g) == {1: 2, 2: 1, 3: 0, 4: 0, 5: 0}


def test_peso_posicional_soma_os_creditos_presos_atras():
    discs = [disc(1, creditos=4), disc(2, creditos=6), disc(3, creditos=2), disc(4, creditos=None)]
    g = grafo_de(discs, [pre(2, 1), pre(3, 2), pre(4, 1)])
    assert pesos_posicionais(g, {d.id: d.creditos for d in discs}) == {1: 12, 2: 8, 3: 2, 4: 0}


def test_cadeia_critica_e_a_sequencia_que_define_o_prazo():
    discs = [disc(i, per="sempre") for i in range(1, 6)]
    g = grafo_de(discs, [pre(2, 1), pre(3, 2), pre(5, 4)])
    prim = primeiros_semestres(g, 10, lambda _n, _t: True)
    assert cadeia_critica(g, prim) == (1, 2, 3)


def test_cadeia_critica_sai_na_sugestao():
    res = rodar([disc(i, per="sempre") for i in range(1, 6)], [pre(2, 1), pre(3, 2), pre(5, 4)])
    assert res.cadeia_critica == (1, 2, 3)


def test_limite_energetico_soma_cabecas_e_caudas():
    # X(1) → {A(4), B(4)} → Z(1), teto 4: X sozinho, A e B em dois semestres, Z depois = 4.
    # Soma simples dá ceil(10/4) = 3 e o grafo dá 3; só o energético (a=1, b=1) prova 4.
    discs = [disc(1, creditos=1, per="sempre"), disc(2, creditos=4, per="sempre"),
             disc(3, creditos=4, per="sempre"), disc(4, creditos=1, per="sempre")]
    reqs = [pre(2, 1), pre(3, 1), pre(4, 2), pre(4, 3)]
    g = grafo_de(discs, reqs)
    prim = primeiros_semestres(g, 10, lambda _n, _t: True)
    assert limite_energetico(prim, alturas(g, so_obrigatorias=True), {d.id: d.creditos for d in discs}, 4) == 4
    res = rodar(discs, reqs, max_creditos=4)
    assert res.metricas.n_semestres == 4 and res.limite_inferior == 4 and res.otimo_comprovado


def test_janelas_enxergam_a_oferta_par_impar():
    # duas disciplinas de 8 créditos que só abrem em período ímpar, teto 8: precisam de 2027/1 e 2028/1
    discs = [disc(1, creditos=8, per="impar"), disc(2, creditos=8, per="impar")]
    g = grafo_de(discs, [])
    cal = CalendarioDeOferta("2027/1", periodicidades_efetivas(discs))
    prim = primeiros_semestres(g, 10, cal)
    assert horizonte_por_janelas(g, prim, {1: 8, 2: 8}, 8, cal, 1, 10) == 3
    res = rodar(discs, [], max_creditos=8)
    assert res.metricas.n_semestres == 3 and res.otimo_comprovado


def test_modelo_recebe_os_requisitos_pelo_construtor():
    # dívida técnica da Fase 1: nada de atributo pendurado depois de criar o modelo
    import inspect
    assert "requisitos" in inspect.signature(ot._Modelo.__init__).parameters
    assert not hasattr(ot, "_requisitos_de")


def _modelo_cc(teto=24, concluidas=()):
    from tests.exemplo_cc import carregar
    ex = carregar()
    nos, _ = nos_a_cursar(ex.disciplinas, ex.requisitos, set(concluidas))
    cal = CalendarioDeOferta("2027/1", periodicidades_efetivas(ex.disciplinas.values()))
    g = construir_grafo(nos, ex.requisitos, set(concluidas))
    m = ot._Modelo(nos, g, ex.disciplinas, ex.requisitos, ex.turmas, cal, ParametrosOtimizacao(max_creditos=teto), 14)
    return m, g, cal


def test_custo_incremental_bate_com_o_calculo_completo():
    m, g, cal = _modelo_cc()
    h = 9
    asg = m.guloso(h, ultimos_semestres(g, h, cal))
    alvo = sum(m.cred) / h
    est = ot._Estado(m, asg, h, alvo)
    rng = random.Random(5)
    for _ in range(1500):
        desfazer = est.vizinho(rng)
        c, d = m.custo(est.asg, h, alvo)
        assert abs(c - est.custo()) < 1e-6 and d == est.duras()
        if desfazer is not None and rng.random() < 0.4:
            est.desfazer(desfazer)


def test_movimentos_a_partir_de_solucao_viavel_preservam_requisitos_e_oferta():
    m, g, cal = _modelo_cc()
    h = 9
    asg = m.guloso(h, ultimos_semestres(g, h, cal))
    est = ot._Estado(m, asg, h, sum(m.cred) / h)
    assert est.duras() == 0
    rng = random.Random(11)
    for _ in range(2000):
        desfazer = est.vizinho(rng)
        assert est.d_req == 0 and est.d_oferta == 0
        if desfazer is not None and est.d_cap:
            est.desfazer(desfazer)          # a cadeia pode lotar um semestre; o recozimento rejeitaria


def test_temperatura_inicial_vem_da_amostra_de_pioras():
    m, g, cal = _modelo_cc()
    h = 9
    est = ot._Estado(m, m.guloso(h, ultimos_semestres(g, h, cal)), h, sum(m.cred) / h)
    t0 = ot._temperatura_inicial(est, random.Random(1))
    assert t0 > 0 and t0 != 25.0
    assert est.custo() == ot._Estado(m, est.asg, h, sum(m.cred) / h).custo()    # a amostra desfaz tudo


def test_reinicios_com_sementes_derivadas_sao_deterministicos():
    m, g, cal = _modelo_cc()
    h = 9
    asg = m.guloso(h, ultimos_semestres(g, h, cal))
    alvo = sum(m.cred) / h
    a = m.recozer_com_reinicios(asg, h, alvo, 3000, 2027, time.monotonic() + 30)
    b = m.recozer_com_reinicios(asg, h, alvo, 3000, 2027, time.monotonic() + 30)
    assert a[0] == b[0] and a[1] == b[1]
    assert a[1] <= m.custo(asg, h, alvo)[0]          # nunca piora a solução inicial


def test_tempo_maximo_e_respeitado():
    from tests.exemplo_cc import carregar
    ex = carregar()
    t0 = time.perf_counter()
    res = otimizar_plano(ex.disciplinas, ex.requisitos, ex.turmas, set(), "2027/1",
                         ParametrosOtimizacao(max_creditos=24, iteracoes=10_000_000, tempo_max_s=0.5))
    assert res.viavel and time.perf_counter() - t0 < 3.0


# ── desempenho no exemplo real (Ciência da Computação) ───────────────────────
LIMITE_S = 5.0


def test_desempenho_exemplo_cc_completo():
    from tests.exemplo_cc import carregar
    ex = carregar()
    t0 = time.perf_counter()
    res = otimizar_plano(ex.disciplinas, ex.requisitos, ex.turmas, set(), "2027/1",
                         ParametrosOtimizacao(max_creditos=24))
    assert time.perf_counter() - t0 < LIMITE_S
    assert res.viavel and res.metricas.n_semestres == 8 and res.otimo_comprovado
    assert res.metricas.colisoes == 0
    assert len(res.cadeia_critica) >= 3


def test_meio_do_curso_com_teto_apertado_agora_tem_otimo_comprovado():
    # antes da Fase 1: 8 semestres com limite 7 (sem prova). As janelas com par/ímpar provam 8.
    from tests.exemplo_cc import carregar
    ex = carregar()
    meio = {i for i, d in ex.disciplinas.items() if d.periodo_sugerido in (1, 2, 3)}
    t0 = time.perf_counter()
    res = otimizar_plano(ex.disciplinas, ex.requisitos, ex.turmas, meio, "2027/1",
                         ParametrosOtimizacao(max_creditos=12))
    assert time.perf_counter() - t0 < LIMITE_S
    assert res.viavel and res.metricas.n_semestres == res.limite_inferior == 8 and res.otimo_comprovado



# ── disciplina fixada num período e "nunca pior que o seu plano" ─────────────
from planner.domain.preferencias import PreferenciasAluno


def test_disciplina_fixada_vai_para_o_periodo_pedido():
    discs = [disc(i, per="sempre") for i in range(1, 5)]
    res = rodar(discs, [], max_creditos=8, preferencias=PreferenciasAluno(fixas={3: "2028/1"}))
    assert posicao_de(res)[3] == 3 and res.fixas_respeitadas == {3: "2028/1"}


def test_fixacao_impossivel_e_ignorada_com_motivo():
    # 2 só abre em ímpar (pedido em período par) e 4 exige 3 (pedido no 1º semestre)
    discs = [disc(1, per="sempre"), disc(2, per="impar"), disc(3, per="sempre"), disc(4, per="sempre")]
    res = rodar(discs, [pre(4, 3)], preferencias=PreferenciasAluno(fixas={2: "2027/2", 4: "2027/1"}))
    assert res.viavel and res.fixas_ignoradas == {2: "nao_abre", 4: "requisitos"}


def test_sugestao_parte_do_plano_do_aluno_e_nao_sai_pior():
    from tests.exemplo_cc import carregar
    ex = carregar()
    base = otimizar_plano(ex.disciplinas, ex.requisitos, ex.turmas, set(), "2027/1", ParametrosOtimizacao(max_creditos=24))
    plano = [(s.periodo, [i.disciplina_id for i in s.itens]) for s in base.semestres]
    outra = otimizar_plano(ex.disciplinas, ex.requisitos, ex.turmas, set(), "2027/1",
                           ParametrosOtimizacao(max_creditos=24, semente=99, iteracoes=200), plano_atual=plano)
    assert outra.partiu_do_plano and outra.metricas.n_semestres <= base.metricas.n_semestres

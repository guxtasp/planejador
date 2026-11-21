"""Fase 2 — preocupações reais do aluno: prazo, Monte Carlo, semana e preferências. Domínio puro."""
from datetime import time

from planner.domain.analise import ItemPlano, SemestrePlano
from planner.domain.entidades import Disciplina, Encontro, Requisito, Turma
from planner.domain.monte_carlo import TAXA_PADRAO, Taxa, simular_formatura, taxa_de_aprovacao
from planner.domain.otimizador import ParametrosOtimizacao, otimizar_plano
from planner.domain.prazo import avaliar_prazo, ingresso_do_aluno
from planner.domain.preferencias import PreferenciasAluno
from planner.domain.replanejamento import replanejar
from planner.domain.semana import BlocoIndisponivel, PreferenciasSemana, metricas_semana
from planner.domain.simulacao import (R_INDISPONIVEL, R_PESADAS, R_PRAZO_MAXIMO, R_PRAZO_REGULAR,
                                      R_SEMESTRE_TRANCADO, R_SOBRECARGA, simular_plano)

SEMPRE = lambda _d, _t: True


def disc(i, creditos=4, per="sempre"):
    return Disciplina(i, f"D{i}", f"Disciplina {i}", creditos, "obrigatoria", None, per)


def enc(dia, ini, fim):
    return Encontro(dia, time(ini), time(fim))


def sem(periodo, *ids):
    return SemestrePlano(tuple(ItemPlano(i) for i in ids), periodo)


def catalogo(discs, reqs=()):
    requisitos = {d.id: [] for d in discs}
    for r in reqs:
        requisitos[r.disciplina_id].append(r)
    return {d.id: d for d in discs}, requisitos


def simular(discs, plano, reqs=(), turmas=None, limite=None, **kw):
    cat, req = catalogo(discs, reqs)
    kw.setdefault("n_monte_carlo", 0)
    return simular_plano(plano, plano[0].periodo_letivo, cat, req, turmas or {}, limite, **kw)


def tipos(sim):
    return {r.tipo for r in sim.riscos}


# ── prazo ────────────────────────────────────────────────────────────────────
def test_prazo_regular_e_maximo():
    assert avaliar_prazo("2024/1", "2027/2", 8).no_prazo_regular is True
    a = avaliar_prazo("2024/1", "2028/2", 8)
    assert a.semestres_usados == 10 and not a.no_prazo_regular and a.no_prazo_maximo and a.maximo == 12
    assert avaliar_prazo("2024/1", "2030/2", 8).no_prazo_maximo is False
    assert avaliar_prazo("2024/1", "2028/2", 8, fator=1.0).no_prazo_maximo is False


def test_trancamento_nao_conta_no_prazo():
    a = avaliar_prazo("2024/1", "2028/1", 8, pulados=["2025/2"])
    assert a.trancados == 1 and a.semestres_usados == 8 and a.no_prazo_regular


def test_sem_duracao_ou_sem_ingresso_nao_afirma_nada():
    assert avaliar_prazo("2024/1", "2030/1", None).no_prazo_regular is None
    assert avaliar_prazo(None, "2030/1", 8).no_prazo_maximo is None


def test_ingresso_vem_do_informado_do_historico_ou_do_inicio_se_nao_ha_historico():
    assert ingresso_do_aluno("2023.2", ["2024/1"], True, "2027/1") == ("2023/2", "informado")
    assert ingresso_do_aluno(None, ["2025/1", "2024/2", None], True, "2027/1") == ("2024/2", "historico")
    assert ingresso_do_aluno(None, [], False, "2027/1") == ("2027/1", "inicio_do_plano")
    assert ingresso_do_aluno(None, [None], True, "2027/1") == (None, None)      # há histórico, sem datas


def test_simulador_aponta_formatura_alem_da_duracao_e_do_prazo_maximo():
    discs = [disc(i) for i in range(1, 4)]
    plano = [sem("2027/1", 1), sem("2027/2", 2), sem("2028/1", 3)]
    assert R_PRAZO_REGULAR in tipos(simular(discs, plano, duracao_semestres=2, periodo_ingresso="2027/1",
                                            creditos_obrigatorios=12))
    assert R_PRAZO_MAXIMO in tipos(simular(discs, plano, duracao_semestres=2, periodo_ingresso="2026/1",
                                           creditos_obrigatorios=12))
    neutro = simular(discs, plano, periodo_ingresso="2026/1", creditos_obrigatorios=12)    # curso sem duração
    assert not {R_PRAZO_REGULAR, R_PRAZO_MAXIMO} & tipos(neutro) and neutro.prazo.no_prazo_regular is None


# ── replanejamento estendido ─────────────────────────────────────────────────
def test_periodo_trancado_nao_recebe_disciplina_e_tudo_espera():
    cat, req = catalogo([disc(1), disc(2)])
    r = replanejar([{1}, {2}], SEMPRE, req, {1: 4, 2: 4}, lambda t: 0 if t == 0 else None)
    assert r.semestres[0] == () and r.concluida_em == {1: 1, 2: 1}


def test_maximo_de_pesadas_por_semestre():
    cat, req = catalogo([disc(1), disc(2), disc(3)])
    r = replanejar([{1, 2, 3}], SEMPRE, req, {}, None, max_pesadas=1, pesadas={1, 2})
    assert sorted(r.semestres[0]) == [1, 3] and r.concluida_em[2] == 1


def test_reprovar_mais_de_uma_vez_na_mesma_disciplina():
    cat, req = catalogo([disc(1)])
    tentativas = iter([True, True, False])
    r = replanejar([{1}], SEMPRE, req, {}, None, reprova=lambda d, t: next(tentativas))
    assert r.semestres[:3] == ((1,), (1,), (1,)) and r.concluida_em[1] == 2


# ── Monte Carlo ──────────────────────────────────────────────────────────────
def test_taxa_vem_do_historico_suavizada_e_padrao_sem_historico():
    assert taxa_de_aprovacao(0, 0) == Taxa(TAXA_PADRAO, "padrao")
    t = taxa_de_aprovacao(2, 0)
    assert t.origem == "historico" and TAXA_PADRAO < t.valor < 1.0        # 2 de 2 não vira 100%
    assert taxa_de_aprovacao(5, 5).valor < 0.65


def _cadeia(n=4):
    discs = [disc(i) for i in range(1, n + 1)]
    cat, req = catalogo(discs, [Requisito(i + 1, i) for i in range(1, n)])
    return [{i} for i in range(1, n + 1)], req


def test_monte_carlo_e_deterministico_e_coerente():
    plano, req = _cadeia()
    a = simular_formatura(plano, SEMPRE, req, {}, None, n=300, semente=7)
    b = simular_formatura(plano, SEMPRE, req, {}, None, n=300, semente=7)
    assert a == b
    assert a.fim_base == 3 and sum(q for _i, q in a.distribuicao) + a.nao_formou == 300
    assert a.p50 <= a.p80 <= a.p90 and a.p50 >= a.fim_base
    assert 0 < a.chance_no_prazo_do_plano < 1
    assert abs(a.chance_no_prazo_do_plano - TAXA_PADRAO ** 4) < 0.1      # 4 elos sem folga


def test_quem_ja_reprovou_tem_chance_menor_e_aparece_na_sensibilidade():
    plano, req = _cadeia()
    sem_hist = simular_formatura(plano, SEMPRE, req, {}, None, n=400)
    com = simular_formatura(plano, SEMPRE, req, {}, None, n=400, ja_reprovadas={2})
    assert com.chance_no_prazo_do_plano < sem_hist.chance_no_prazo_do_plano
    assert com.sensibilidade[0].disciplina_id == 2


def test_sensibilidade_poe_primeiro_quem_esta_na_cadeia():
    # 1 → 2 → 3 sem folga e 4 solta no fim: reprovar em 4 também atrasa, mas a cadeia pesa mais
    discs = [disc(i) for i in range(1, 5)]
    cat, req = catalogo(discs, [Requisito(2, 1), Requisito(3, 2)])
    mc = simular_formatura([{1, 4}, {2}, {3}], SEMPRE, req, {}, None, n=400)
    ordem = [s.disciplina_id for s in mc.sensibilidade]
    assert ordem[:3] == sorted(ordem[:3], key=lambda d: ordem.index(d)) and set(ordem[:3]) == {1, 2, 3}
    # 4 tem folga: só atrasa se reprovar várias vezes seguidas, então pesa bem menos
    quatro = next((s for s in mc.sensibilidade if s.disciplina_id == 4), None)
    assert quatro is None or quatro.contribuicao < mc.sensibilidade[0].contribuicao / 2


# ── semana ───────────────────────────────────────────────────────────────────
def test_metricas_da_semana():
    prefs = PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(8), time(12)),), dias_livres=("SEX",))
    m = metricas_semana([enc("SEG", 10, 12), enc("SEG", 14, 16), enc("SEX", 8, 10)], prefs)
    assert m.horas_aula == 6 and m.dias_livres == ("TER", "QUA", "QUI") and m.janelas_horas == 2
    assert m.choques_indisponiveis == 1 and m.aulas_em_dias_livres == ("SEX",)


def test_simulador_mostra_a_semana_e_avisa_turma_em_horario_indisponivel():
    turmas = {1: [Turma(10, 1, (enc("SEG", 8, 10),), "2027/1", "T1")]}
    prefs = PreferenciasAluno(semana=PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12), "estágio"),)))
    sim = simular([disc(1)], [sem("2027/1", 1)], turmas=turmas, preferencias=prefs)
    risco = next(r for r in sim.riscos if r.tipo == R_INDISPONIVEL)
    assert risco.gravidade == "alta" and risco.detalhe["motivo"] == "estágio"
    assert sim.semestres[0].semana.horas_aula == 2 and sim.semestres[0].semana.choques_indisponiveis == 1


def test_simulador_usa_a_outra_turma_quando_uma_bate_no_indisponivel():
    turmas = {1: [Turma(10, 1, (enc("SEG", 8, 10),), "2027/1", "T1"), Turma(11, 1, (enc("TER", 19, 21),), "2027/1", "T2")]}
    prefs = PreferenciasAluno(semana=PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12)),)))
    sim = simular([disc(1)], [sem("2027/1", 1)], turmas=turmas, preferencias=prefs)
    assert sim.semestres[0].itens[0].turma_id == 11 and R_INDISPONIVEL not in tipos(sim)


def test_teto_especifico_trancamento_e_pesadas_no_simulador():
    discs = [disc(1), disc(2), disc(3)]
    prefs = PreferenciasAluno(teto_por_periodo={"2027/1": 4}, periodos_pulados=frozenset({"2027/2"}),
                              max_pesadas=1, pesadas=frozenset({1, 2}))
    sim = simular(discs, [sem("2027/1", 1, 2), sem("2027/2", 3)], limite=20, preferencias=prefs)
    sobre = next(r for r in sim.riscos if r.tipo == R_SOBRECARGA)
    assert sobre.detalhe["limite"] == 4 and sobre.detalhe["especifico"]
    assert R_PESADAS in tipos(sim) and R_SEMESTRE_TRANCADO in tipos(sim)
    assert sim.semestres[1].trancado


def test_simulador_traz_monte_carlo_quando_pedido():
    discs = [disc(1), disc(2)]
    sim = simular(discs, [sem("2027/1", 1), sem("2027/2", 2)], [Requisito(2, 1)], n_monte_carlo=200)
    assert sim.monte_carlo.n == 200 and sim.monte_carlo.fim_base == 1


# ── otimizador com preferências ──────────────────────────────────────────────
def otimizar(discs, reqs=(), turmas=None, **kw):
    cat, req = catalogo(discs, reqs)
    return otimizar_plano(cat, req, turmas or {}, set(), "2027/1", ParametrosOtimizacao(**kw))


def posicoes(res):
    return {i.disciplina_id: s.periodo for s in res.semestres for i in s.itens}


def test_sugestao_nao_usa_periodo_trancado():
    res = otimizar([disc(1), disc(2)], [Requisito(2, 1)],
                   preferencias=PreferenciasAluno(periodos_pulados=frozenset({"2027/2"})))
    assert posicoes(res) == {1: "2027/1", 2: "2028/1"}


def test_sugestao_respeita_teto_de_um_periodo_especifico():
    discs = [disc(i, creditos=4) for i in range(1, 5)]
    res = otimizar(discs, max_creditos=8, preferencias=PreferenciasAluno(teto_por_periodo={"2027/1": 4}))
    assert res.semestres[0].creditos <= 4 and all(s.creditos <= 8 for s in res.semestres)


def test_sugestao_separa_as_pesadas():
    discs = [disc(i, creditos=4) for i in range(1, 5)]
    res = otimizar(discs, max_creditos=8, preferencias=PreferenciasAluno(max_pesadas=1, pesadas=frozenset({1, 2})))
    p = posicoes(res)
    assert p[1] != p[2]


def test_sugestao_tira_disciplina_do_semestre_em_que_todas_as_turmas_caem_no_indisponivel():
    # 1 só tem turma SEG de manhã em períodos ímpares; nos pares, à noite. A pessoa trabalha SEG de manhã.
    turmas = {1: [Turma(10, 1, (enc("SEG", 8, 10),), "2026/1", "T1"), Turma(11, 1, (enc("SEG", 19, 21),), "2026/2", "T1")],
              2: [Turma(20, 2, (enc("TER", 8, 10),), "2026/1", "T1")]}
    prefs = PreferenciasAluno(semana=PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12)),)))
    sem_pref = otimizar([disc(1), disc(2)], turmas=turmas, max_creditos=4)
    com_pref = otimizar([disc(1), disc(2)], turmas=turmas, max_creditos=4, preferencias=prefs)
    assert posicoes(sem_pref)[1] == "2027/1"
    assert posicoes(com_pref)[1] == "2027/2"


def test_sem_preferencias_a_sugestao_e_a_mesma():
    discs = [disc(i) for i in range(1, 9)]
    reqs = [Requisito(3, 1), Requisito(4, 2), Requisito(6, 3)]
    assert posicoes(otimizar(discs, reqs, max_creditos=12)) == \
        posicoes(otimizar(discs, reqs, max_creditos=12, preferencias=PreferenciasAluno()))


# ── choque visível no item ───────────────────────────────────────────────────
from planner.services.simulacao_json import marcas_do_item, serializar_simulacao


def _turma(tid, d, periodo, *encs):
    return Turma(tid, d, tuple(encs), periodo, f"T{tid}")


def _tags(sim, cat, d):
    j = serializar_simulacao(sim, cat)
    item = next(i for s in j["semestres"] for i in s["itens"] if i["disciplina"]["id"] == d)
    return item, [t["tipo"] for t in item["tags"]], j


def test_item_com_choque_firme_mostra_com_quem_e_quando():
    discs = [disc(1), disc(2)]
    turmas = {1: [_turma(10, 1, "2027/1", enc("SEG", 14, 16))], 2: [_turma(20, 2, "2027/1", enc("SEG", 15, 17))]}
    sim = simular(discs, [sem("2027/1", 1, 2)], turmas=turmas)
    item, tipos_, j = _tags(sim, {d.id: d for d in discs}, 1)
    assert tipos_ == ["choque"] and item["tags"][0]["texto"] == "Choque com D2 (Seg 15–16)"
    assert item["choques"][0]["firme"] and j["semestres"][0]["choques_texto"] == "1 choque"


def test_item_com_horario_projetado_mostra_possivel_choque():
    discs = [disc(1), disc(2)]
    turmas = {1: [_turma(10, 1, "2026/1", enc("SEG", 14, 16))], 2: [_turma(20, 2, "2026/1", enc("SEG", 14, 16))]}
    sim = simular(discs, [sem("2027/1", 1, 2)], turmas=turmas)       # quadro de 2026/1 projetado em 2027/1
    item, tipos_, _ = _tags(sim, {d.id: d for d in discs}, 2)
    assert tipos_ == ["possivel_choque"] and item["tags"][0]["cor"] == "yellow"


def test_item_sem_horario_nunca_parece_sem_choque():
    sim = simular([disc(1)], [sem("2027/1", 1)])
    item, tipos_, _ = _tags(sim, {1: disc(1)}, 1)
    assert tipos_ == ["sem_horario"] and "não verificado" in item["tags"][0]["texto"]


def test_item_que_bate_com_a_disponibilidade():
    turmas = {1: [_turma(10, 1, "2027/1", enc("SEG", 8, 10))]}
    prefs = PreferenciasAluno(semana=PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12)),)))
    sim = simular([disc(1)], [sem("2027/1", 1)], turmas=turmas, preferencias=prefs)
    _item, tipos_, _ = _tags(sim, {1: disc(1)}, 1)
    assert tipos_ == ["disponibilidade"]


# ── optativas no simulador ───────────────────────────────────────────────────
from planner.domain.simulacao import R_FALTAM_OPTATIVAS


def _opt(i, creditos=4):
    return Disciplina(i, f"OP{i}", f"Optativa {i}", creditos, "optativa", None, "sempre")


def test_optativas_exigidas_cumpridas_planejadas_e_o_que_falta():
    discs = [disc(1, creditos=4), disc(2, creditos=4), _opt(3), _opt(4)]
    plano = [sem("2027/1", 1, 3), sem("2027/2", 2)]
    sim = simular(discs, plano, limite=8, aprovadas={4}, creditos_obrigatorios=8, creditos_optativos_exigidos=16)
    r = sim.resumo
    assert (r.optativas_exigidas, r.optativas_cumpridas, r.optativas_planejadas, r.optativas_faltam) == (16, 4, 4, 8)
    assert R_FALTAM_OPTATIVAS in tipos(sim)
    # só obrigatórias: 2027/2. Com as 8 que faltam: o 2º semestre tem 4 livres; os outros 4 pedem 2028/1
    assert r.formatura_so_obrigatorias == "2027/2" and r.formatura_com_optativas == "2028/1"
    assert [s.espaco_optativa for s in sim.semestres] == [0, 4]
    item, tipos_, j = _tags(sim, {d.id: d for d in discs}, 3)
    assert "optativa" in tipos_ and j["semestres"][1]["espaco_optativa_texto"] == "Cabem mais 4 créditos de optativa aqui."


def test_sem_creditos_optativos_informados_nao_afirma_nada():
    discs = [disc(1), _opt(3)]
    sim = simular(discs, [sem("2027/1", 1, 3)], creditos_obrigatorios=4)
    assert sim.resumo.optativas_faltam is None and R_FALTAM_OPTATIVAS not in tipos(sim)
    j = serializar_simulacao(sim, {d.id: d for d in discs})
    assert "não informa" in j["resumo"]["optativas"]["mensagem"]


def test_optativa_planejada_entra_na_oferta_como_qualquer_disciplina():
    discs = [disc(1), Disciplina(3, "OP3", "Optativa 3", 4, "optativa", None, "impar")]
    sim = simular(discs, [sem("2027/2", 1, 3)])
    assert any(r.tipo == "fora_de_oferta" and r.disciplinas == (3,) for r in sim.riscos)

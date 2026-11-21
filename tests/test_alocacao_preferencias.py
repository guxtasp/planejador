"""Fase 1 — critérios secundários na alocação de turmas (preferências da semana). Domínio puro."""
import random
from datetime import time

from planner.domain.alocacao import alocar_turmas
from planner.domain.conflitos import Selecao, sobreposicoes_entre_turmas
from planner.domain.entidades import Encontro, Turma
from planner.domain.semana import (BlocoIndisponivel, PreferenciasSemana, janelas_horas, penalidade,
                                   turno_do)


def enc(dia, ini, fim):
    return Encontro(dia, time(ini), time(fim))


def turma(tid, disc, *encontros):
    return Turma(tid, disc, tuple(encontros))


# ── referência: a alocação ANTES da Fase 1 (só colisões), copiada para o teste de regressão ──
def _alocar_antigo(selecoes, limite_nos=20_000):
    julgaveis = [s for s in selecoes if s.candidatas()]
    escolha = {s.disciplina_id: None for s in selecoes}
    if not julgaveis:
        return escolha
    ordem = sorted(julgaveis, key=lambda s: (len(s.candidatas()), s.disciplina_id))
    melhor_custo, melhor, nos, cortado = [float("inf")], [[]], [0], [False]

    def busca(i, atual, custo):
        if custo >= melhor_custo[0] or cortado[0]:
            return
        if i == len(ordem):
            melhor_custo[0], melhor[0] = custo, list(atual)
            return
        nos[0] += 1
        if nos[0] > limite_nos:
            cortado[0] = True
            return
        pontuadas = sorted(((sum(1 for t in atual if sobreposicoes_entre_turmas(c, t)), k, c)
                            for k, c in enumerate(ordem[i].candidatas())), key=lambda x: (x[0], x[1]))
        for extra, _, c in pontuadas:
            atual.append(c)
            busca(i + 1, atual, custo + extra)
            atual.pop()
            if melhor_custo[0] == 0:
                return

    busca(0, [], 0)
    if not melhor[0]:
        melhor[0] = [s.candidatas()[0] for s in ordem]
    for s, t in zip(ordem, melhor[0]):
        escolha[s.disciplina_id] = t.id
    return escolha


def _instancia(rng, n_disc):
    dias = ["SEG", "TER", "QUA", "QUI", "SEX"]
    selecoes, tid = [], 0
    for d in range(1, n_disc + 1):
        turmas = []
        for _ in range(rng.randint(1, 3)):
            tid += 1
            encs = [enc(rng.choice(dias), h, h + 2) for h in rng.sample([8, 10, 14, 16, 19], rng.randint(1, 2))]
            turmas.append(turma(tid, d, *encs))
        selecoes.append(Selecao(d, tuple(turmas), None))
    return selecoes


def test_sem_preferencias_o_resultado_e_identico_ao_de_antes():
    rng = random.Random(42)
    for _ in range(300):
        sel = _instancia(rng, rng.randint(2, 6))
        novo = alocar_turmas(sel)
        assert dict(novo.escolha) == _alocar_antigo(sel)
        assert novo.penalidade == 0.0


def test_preferencias_macias_nunca_trocam_menos_colisoes_por_conforto():
    rng = random.Random(7)
    prefs = PreferenciasSemana(turno="noite", dias_livres=("SEX",))
    for _ in range(150):
        sel = _instancia(rng, rng.randint(2, 5))
        assert len(alocar_turmas(sel, preferencias=prefs).colisoes) == len(alocar_turmas(sel).colisoes)


def test_evita_turma_que_bate_no_horario_indisponivel():
    a = Selecao(1, (turma(1, 1, enc("SEG", 8, 10)), turma(2, 1, enc("TER", 8, 10))))
    prefs = PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12), "trabalho"),))
    assert alocar_turmas([a]).escolha[1] == 1                     # sem preferência: a primeira
    assert alocar_turmas([a], preferencias=prefs).escolha[1] == 2


def test_prefere_o_turno_escolhido():
    a = Selecao(1, (turma(1, 1, enc("SEG", 8, 10)), turma(2, 1, enc("SEG", 19, 21))))
    assert alocar_turmas([a], preferencias=PreferenciasSemana(turno="noite")).escolha[1] == 2


def test_junta_as_aulas_em_menos_dias_e_sem_buraco():
    a = Selecao(1, (turma(1, 1, enc("SEG", 8, 10)),))
    b = Selecao(2, (turma(2, 2, enc("QUA", 8, 10)), turma(3, 2, enc("SEG", 14, 16)), turma(4, 2, enc("SEG", 10, 12))))
    res = alocar_turmas([a, b], preferencias=PreferenciasSemana())
    assert res.escolha[2] == 4                    # mesmo dia (SEG) e colada: sem janela


def test_dia_livre_pedido_e_respeitado_quando_ha_alternativa():
    a = Selecao(1, (turma(1, 1, enc("SEX", 8, 10)), turma(2, 1, enc("QUI", 8, 10))))
    assert alocar_turmas([a], preferencias=PreferenciasSemana(dias_livres=("SEX",))).escolha[1] == 2


def test_medidas_da_semana():
    encs = [enc("SEG", 8, 10), enc("SEG", 14, 16), enc("TER", 19, 21)]
    assert janelas_horas(encs) == 4.0
    assert turno_do(encs[0]) == "manha" and turno_do(encs[1]) == "tarde" and turno_do(encs[2]) == "noite"
    assert penalidade(encs, None) == 0.0
    assert penalidade(encs, PreferenciasSemana()) == 2 * 2.0 + 4.0      # 2 dias + 4 h de janela


def test_horario_indisponivel_e_regra_dura_quando_ha_turma_alternativa():
    # A só não colide com B na turma de SEG de manhã, mas a pessoa trabalha SEG de manhã:
    # vale a regra dura (fica a turma de TER, mesmo colidindo com B).
    a = Selecao(1, (turma(1, 1, enc("SEG", 8, 10)), turma(2, 1, enc("TER", 8, 10))))
    b = Selecao(2, (turma(3, 2, enc("TER", 8, 10)),))
    prefs = PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12)),))
    assert alocar_turmas([a, b]).escolha[1] == 1
    res = alocar_turmas([a, b], preferencias=prefs)
    assert res.escolha[1] == 2 and len(res.colisoes) == 1


def test_sem_turma_alternativa_a_disciplina_fica_mesmo_no_horario_indisponivel():
    a = Selecao(1, (turma(1, 1, enc("SEG", 8, 10)),))
    prefs = PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12)),))
    res = alocar_turmas([a], preferencias=prefs)
    assert res.escolha[1] == 1 and res.penalidade > 0

"""Etapa 4B — grade derivada dos dados e análise de plano (domínio puro)."""
from datetime import time

from planner.domain.analise import (
    DISCIPLINA_DESCONHECIDA, DISCIPLINA_REPETIDA, SEMESTRE_SEM_PERIODO, TURMA_INVALIDA,
    ItemPlano, SemestrePlano, analisar_plano,
)
from planner.domain.conflitos import CONFLITO, CONFLITO_POSSIVEL, SEM_TURMA_COMPATIVEL
from planner.domain.entidades import REQ_PRE, Disciplina, Encontro, Requisito, Turma
from planner.domain.grade import DIAS_PADRAO, FAIXA_PADRAO, derivar_grade


def h(s):
    return time(*map(int, s.split(":")))


def enc(dia, ini, fim):
    return Encontro(dia, h(ini), h(fim))


# ── grade ────────────────────────────────────────────────────────────────────
def test_sem_nenhum_dado_a_grade_e_so_o_padrao_visual():
    g = derivar_grade([])
    assert g.dias == DIAS_PADRAO and (g.hora_inicio, g.hora_fim) == FAIXA_PADRAO


def test_sabado_aparece_quando_ha_encontro_no_sabado():
    g = derivar_grade([enc("SEG", "08:00", "10:00"), enc("SAB", "08:00", "12:00")])
    assert g.dias == ("SEG", "SAB")


def test_dias_letivos_do_curso_entram_mesmo_sem_encontros():
    g = derivar_grade([enc("SEG", "08:00", "10:00")], ["SEG", "TER", "QUA", "QUI", "SEX", "SAB"])
    assert g.dias == ("SEG", "TER", "QUA", "QUI", "SEX", "SAB")


def test_dias_letivos_nunca_escondem_um_encontro():
    g = derivar_grade([enc("SAB", "08:00", "10:00")], ["SEG", "TER"])
    assert g.dias == ("SEG", "TER", "SAB")


def test_dias_vem_em_ordem_de_semana_e_ignora_sigla_desconhecida():
    g = derivar_grade([enc("QUI", "08:00", "10:00")], ["SEX", "XXX", "SEG"])
    assert g.dias == ("SEG", "QUI", "SEX")


def test_faixa_de_horas_acompanha_noturno_e_arredonda_para_cima():
    g = derivar_grade([enc("SEG", "18:30", "22:30"), enc("TER", "19:00", "21:00")])
    assert (g.hora_inicio, g.hora_fim) == (18, 23)


def test_fim_em_hora_cheia_nao_cria_linha_extra():
    assert derivar_grade([enc("SEG", "08:00", "10:00")]).hora_fim == 10


# ── análise: catálogo de teste ───────────────────────────────────────────────
DISCS = {
    1: Disciplina(1, "A", "Alfa", 4),
    2: Disciplina(2, "B", "Beta", 4),
    3: Disciplina(3, "C", "Gama", None),
}
SEG_8 = enc("SEG", "08:00", "10:00")
SEG_9 = enc("SEG", "09:00", "11:00")
TER_8 = enc("TER", "08:00", "10:00")
TURMAS = {
    1: [Turma(10, 1, (SEG_8,), "2026/1", "T1")],
    2: [Turma(20, 2, (SEG_9,), "2026/1", "T1"), Turma(21, 2, (TER_8,), "2026/1", "T2"),
        Turma(22, 2, (SEG_9,), "2026/2", "T1")],
    3: [],
}


def analisar(semestres, limite=None, requisitos=None):
    return analisar_plano(semestres, DISCS, requisitos or {}, TURMAS, limite)


def sem(*itens, periodo="2026/1"):
    return SemestrePlano(tuple(ItemPlano(*i) for i in itens), periodo)


def test_duas_turmas_escolhidas_que_colidem_e_conflito():
    (a,) = analisar([sem((1, 10), (2, 20))])
    assert [c.tipo for c in a.conflitos] == [CONFLITO]


def test_turma_escolhida_que_resolve_nao_gera_conflito():
    (a,) = analisar([sem((1, 10), (2, 21))])
    assert a.conflitos == ()


def test_sem_escolher_turma_vira_conflito_possivel_e_pede_escolha():
    (a,) = analisar([sem((1, 10), (2, None))])
    assert [c.tipo for c in a.conflitos] == [CONFLITO_POSSIVEL]
    assert a.sem_turma_escolhida == (2,)


def test_sem_turma_compativel_quando_toda_oferta_colide():
    colide = {1: TURMAS[1], 2: [TURMAS[2][0]], 3: []}
    (a,) = analisar_plano([sem((1, 10), (2, None))], DISCS, {}, colide, None)
    assert [c.tipo for c in a.conflitos] == [SEM_TURMA_COMPATIVEL]


def test_so_as_turmas_do_periodo_do_semestre_sao_consideradas():
    """No 2026/2 a Beta só tem a T1 (segunda 9h) e a Alfa não tem oferta: sem julgamento."""
    (a,) = analisar([sem((1, None), (2, None), periodo="2026/2")])
    assert a.conflitos == () and a.sem_turma_escolhida == (2,)


def test_semestre_sem_periodo_nao_julga_horario_e_recusa_turma():
    (a,) = analisar([sem((1, 10), (2, 20), periodo=None)])
    assert a.conflitos == ()
    assert {i.motivo for i in a.invalidos} == {SEMESTRE_SEM_PERIODO}
    assert [i.disciplina_id for i in a.invalidos] == [1, 2]


def test_disciplina_sem_oferta_nao_pede_turma():
    (a,) = analisar([sem((3, None))])
    assert a.sem_turma_escolhida == () and a.invalidos == ()


def test_turma_de_outra_disciplina_ou_periodo_e_invalida_e_a_disciplina_continua():
    (a,) = analisar([sem((1, 20), (2, 22))])
    assert [(i.disciplina_id, i.motivo) for i in a.invalidos] == [(1, TURMA_INVALIDA), (2, TURMA_INVALIDA)]
    assert a.carga.creditos == 8          # as disciplinas seguem no plano
    assert a.sem_turma_escolhida == (1, 2)


def test_disciplina_desconhecida_e_repetida_sao_separadas_e_nao_contam():
    (a,) = analisar([sem((1, 10), (99, None), (1, 10))])
    assert [(i.disciplina_id, i.motivo) for i in a.invalidos] == [
        (99, DISCIPLINA_DESCONHECIDA), (1, DISCIPLINA_REPETIDA)]
    assert a.carga.creditos == 4


def test_carga_usa_limite_do_curso_e_sinaliza_credito_desconhecido():
    (a,) = analisar([sem((1, None), (2, None), (3, None))], limite=7)
    assert a.carga.creditos == 8 and a.carga.sobrecarga and a.carga.disciplinas_sem_creditos == (3,)
    (b,) = analisar([sem((1, None), (2, None))], limite=None)
    assert not b.carga.sobrecarga          # limite desconhecido: sem julgamento


def test_requisito_cumprido_por_semestre_anterior_do_proprio_plano():
    reqs = {2: [Requisito(2, 1, REQ_PRE)]}
    a1, a2 = analisar([sem((1, None)), sem((2, None), periodo="2026/2")], requisitos=reqs)
    assert a1.pendencias == () and a2.pendencias == ()


def test_requisito_no_mesmo_semestre_ou_ausente_gera_pendencia_no_semestre_certo():
    reqs = {2: [Requisito(2, 1, REQ_PRE)]}
    (a,) = analisar([sem((1, None), (2, None))], requisitos=reqs)
    assert [(p.posicao_semestre, p.disciplina_id) for p in a.pendencias] == [(1, 2)]


def test_pendencias_vao_para_o_semestre_a_que_pertencem():
    reqs = {2: [Requisito(2, 1, REQ_PRE)]}
    a1, a2 = analisar([sem((2, None)), sem((1, None))], requisitos=reqs)
    assert len(a1.pendencias) == 1 and a2.pendencias == ()


def test_resultado_tem_um_item_por_semestre_na_ordem():
    analises = analisar([sem(), sem((1, None)), sem()])
    assert [a.posicao for a in analises] == [1, 2, 3]

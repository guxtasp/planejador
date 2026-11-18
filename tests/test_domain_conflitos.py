"""Motor de regras: conflitos de horário por turma."""
from datetime import time

from planner.domain.conflitos import (
    CONFLITO, CONFLITO_POSSIVEL, SEM_TURMA_COMPATIVEL, Selecao,
    detectar_conflitos, encontros_se_sobrepoem,
)
from planner.domain.entidades import Encontro, Turma


def enc(dia, ini, fim):
    h = lambda s: time(*map(int, s.split(":")))
    return Encontro(dia, h(ini), h(fim))


def turma(i, disc, *encontros):
    return Turma(id=i, disciplina_id=disc, encontros=tuple(encontros))


def test_bordas_que_se_tocam_nao_colidem():
    assert not encontros_se_sobrepoem(enc("SEG", "14:00", "16:00"), enc("SEG", "16:00", "18:00"))


def test_dias_diferentes_nao_colidem():
    assert not encontros_se_sobrepoem(enc("SEG", "14:00", "16:00"), enc("TER", "14:00", "16:00"))


def test_caso_real_inf110_x_est105_colidem_em_seg_e_qui():
    """Mesmo caso do teste de caracterização do legado, agora por turma."""
    inf110 = turma(1, 10, enc("SEG", "16:00", "18:00"), enc("QUI", "14:00", "16:00"))
    est105 = turma(2, 20, enc("SEG", "16:00", "18:00"), enc("QUI", "14:00", "16:00"))
    sel = [Selecao(10, (inf110,), 1), Selecao(20, (est105,), 2)]
    (c,) = detectar_conflitos(sel)
    assert c.tipo == CONFLITO and {s.dia for s in c.sobreposicoes} == {"SEG", "QUI"}


def test_so_um_encontro_colidindo_ja_basta():
    a = turma(1, 10, enc("SEG", "08:00", "10:00"), enc("QUA", "08:00", "10:00"))
    b = turma(2, 20, enc("QUA", "09:00", "11:00"))
    assert [c.tipo for c in detectar_conflitos([Selecao(10, (a,), 1), Selecao(20, (b,), 2)])] == [CONFLITO]


def test_conflito_possivel_quando_uma_turma_alternativa_resolve():
    fixa = turma(1, 10, enc("SEG", "08:00", "10:00"))
    t1 = turma(2, 20, enc("SEG", "09:00", "11:00"))   # colide
    t2 = turma(3, 20, enc("TER", "09:00", "11:00"))   # livre
    (c,) = detectar_conflitos([Selecao(10, (fixa,), 1), Selecao(20, (t1, t2))])
    assert c.tipo == CONFLITO_POSSIVEL


def test_sem_turma_compativel_quando_todas_colidem():
    fixa = turma(1, 10, enc("SEG", "08:00", "10:00"))
    t1 = turma(2, 20, enc("SEG", "09:00", "11:00"))
    t2 = turma(3, 20, enc("SEG", "08:30", "09:30"))
    (c,) = detectar_conflitos([Selecao(10, (fixa,), 1), Selecao(20, (t1, t2))])
    assert c.tipo == SEM_TURMA_COMPATIVEL


def test_escolher_a_turma_livre_elimina_o_conflito():
    fixa = turma(1, 10, enc("SEG", "08:00", "10:00"))
    t1 = turma(2, 20, enc("SEG", "09:00", "11:00"))
    t2 = turma(3, 20, enc("TER", "09:00", "11:00"))
    assert detectar_conflitos([Selecao(10, (fixa,), 1), Selecao(20, (t1, t2), 3)]) == ()


def test_sem_turmas_ofertadas_nao_ha_julgamento():
    fixa = turma(1, 10, enc("SEG", "08:00", "10:00"))
    assert detectar_conflitos([Selecao(10, (fixa,), 1), Selecao(20, ())]) == ()


def test_varias_disciplinas_comparam_todos_os_pares():
    ts = [turma(i, 10 * i, enc("SEG", "08:00", "10:00")) for i in (1, 2, 3)]
    sel = [Selecao(t.disciplina_id, (t,), t.id) for t in ts]
    assert len(detectar_conflitos(sel)) == 3

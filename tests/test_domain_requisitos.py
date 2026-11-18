"""Motor de regras: requisitos, histórico com N tentativas e plano sequencial."""
from planner.domain.entidades import Disciplina, Requisito, Tentativa
from planner.domain.historico import APROVADA, CURSANDO, REPROVADA, aprovadas, cursando, situacoes
from planner.domain.requisitos import (
    avaliar_requisitos, classificar_disciplinas, verificar_plano,
)

INF110, INF112, MAT135, EST105 = 1, 2, 3, 4


def pre(d, r, grupo=None):
    return Requisito(d, r, "pre", grupo)


def co(d, r, grupo=None):
    return Requisito(d, r, "co", grupo)


# ── avaliar_requisitos ─────────────────────────────────────────────────────
def test_pre_pendente_sem_historico():
    """Preserva o comportamento do legado: INF112 exige INF110."""
    pend = avaliar_requisitos([pre(INF112, INF110)], concluidas=set())
    assert [p.alternativas for p in pend] == [(INF110,)]


def test_pre_cumprido():
    assert avaliar_requisitos([pre(INF112, INF110)], concluidas={INF110}) == ()


def test_pre_nao_e_cumprido_por_cursando_ou_mesmo_semestre():
    pend = avaliar_requisitos([pre(INF112, INF110)], concluidas=set(), simultaneas={INF110})
    assert len(pend) == 1


def test_co_aceita_cursando_ou_mesmo_semestre():
    assert avaliar_requisitos([co(INF112, INF110)], set(), simultaneas={INF110}) == ()


def test_grupo_ou_basta_uma_alternativa():
    reqs = [pre(9, INF110, "A"), pre(9, MAT135, "A")]
    assert avaliar_requisitos(reqs, concluidas={MAT135}) == ()


def test_grupo_ou_pendente_lista_todas_as_alternativas():
    reqs = [pre(9, MAT135, "A"), pre(9, INF110, "A")]
    (p,) = avaliar_requisitos(reqs, concluidas=set())
    assert p.alternativas == (INF110, MAT135) and p.e_alternativa


def test_and_e_ou_combinados():
    reqs = [pre(9, INF110), pre(9, MAT135, "A"), pre(9, EST105, "A")]
    pend = avaliar_requisitos(reqs, concluidas={EST105})
    assert [p.alternativas for p in pend] == [(INF110,)]


def test_grupos_de_tipos_diferentes_nao_se_misturam():
    """Mesmo rótulo de grupo em `pre` e `co` são termos distintos."""
    reqs = [pre(9, INF110, "A"), co(9, MAT135, "A")]
    pend = avaliar_requisitos(reqs, concluidas={INF110})
    assert [(p.tipo, p.alternativas) for p in pend] == [("co", (MAT135,))]


# ── histórico com N tentativas (inverte legacy_bug #4) ─────────────────────
def test_reprovacao_seguida_de_aprovacao_acumula():
    """Legado: o 2º registro sobrescrevia o 1º. Agora ambos existem e vale a aprovação."""
    hist = [Tentativa(INF110, "reprovado", "2025/1"), Tentativa(INF110, "aprovado", "2025/2")]
    assert situacoes(hist) == {INF110: APROVADA}
    assert aprovadas(hist) == {INF110}


def test_cursando_vale_mais_que_reprovacao_antiga():
    hist = [Tentativa(INF110, "reprovado"), Tentativa(INF110, "cursando")]
    assert situacoes(hist) == {INF110: CURSANDO} and cursando(hist) == {INF110}


def test_so_reprovado_fica_reprovada_e_nao_conta_como_feita():
    hist = [Tentativa(INF110, "reprovado")]
    assert situacoes(hist) == {INF110: REPROVADA} and aprovadas(hist) == frozenset()


def test_status_desconhecido_e_ignorado():
    assert situacoes([Tentativa(INF110, "trancado")]) == {}


# ── plano sequencial (inverte legacy_bug #5) ───────────────────────────────
REQS = {INF112: [pre(INF112, INF110)]}


def test_plano_considera_semestres_anteriores():
    """Legado: INF110 no sem. 1 e INF112 no sem. 2 ainda acusava pendência."""
    assert verificar_plano([{INF110}, {INF112}], REQS, aprovadas=set()) == ()


def test_plano_acusa_quando_a_ordem_esta_errada():
    problemas = verificar_plano([{INF112}, {INF110}], REQS, aprovadas=set())
    assert [(p.posicao_semestre, p.disciplina_id) for p in problemas] == [(1, INF112)]


def test_plano_pre_no_mesmo_semestre_e_pendente_mas_co_nao():
    assert len(verificar_plano([{INF110, INF112}], REQS, set())) == 1
    reqs_co = {INF112: [co(INF112, INF110)]}
    assert verificar_plano([{INF110, INF112}], reqs_co, set()) == ()


def test_plano_usa_historico_aprovado():
    assert verificar_plano([{INF112}], REQS, aprovadas={INF110}) == ()


# ── assistente ─────────────────────────────────────────────────────────────
def test_classificar_disciplinas():
    d = [Disciplina(i, f"C{i}", f"D{i}") for i in (INF110, INF112, MAT135, EST105)]
    reqs = {INF112: [pre(INF112, INF110)], MAT135: [pre(MAT135, EST105)]}
    c = classificar_disciplinas(d, reqs, aprovadas={INF110}, cursando={EST105})
    assert [x.id for x in c.concluidas] == [INF110]
    assert [x.id for x in c.em_andamento] == [EST105]
    assert [x.id for x in c.elegiveis] == [INF112]
    assert [x.id for x, _ in c.bloqueadas] == [MAT135]

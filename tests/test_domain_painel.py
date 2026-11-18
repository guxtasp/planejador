"""Etapa 5B-2 — painel do aluno (domínio puro): status, progresso e previsão a partir do histórico."""
import pytest

from planner.domain.entidades import Disciplina, Requisito, Tentativa
from planner.domain.painel import (
    BLOQUEADA, CONCLUIDA, CURSANDO, ELEGIVEL, MEDIA_DO_ALUNO, MEDIA_DO_CURSO,
    creditos_aprovados_por_periodo, media_do_curso, montar_painel,
)
from planner.domain.previsao import normalizar_periodo


def disc(i, creditos=4, tipo="obrigatoria", periodo=1):
    return Disciplina(i, f"D{i}", f"Disciplina {i}", creditos, tipo, periodo)


def tent(i, status="aprovado", periodo="2024/1"):
    return Tentativa(i, status, periodo)


def situacoes(painel):
    return {s.disciplina_id: s.situacao for s in painel.status}


# ── normalizar_periodo ───────────────────────────────────────────────────────
@pytest.mark.parametrize("texto,esperado", [
    ("2024/1", "2024/1"), ("2024.2", "2024/2"), ("2024-1", "2024/1"), (" 2024 / 01 ", "2024/1"),
    ("2024/3", None), ("2024/0", None), ("24/1", None), ("", None), (None, None), ("abc", None),
])
def test_normalizar_periodo(texto, esperado):
    assert normalizar_periodo(texto) == esperado


def test_normalizar_periodo_respeita_periodos_por_ano():
    assert normalizar_periodo("2024/3", periodos_por_ano=3) == "2024/3"


# ── status por disciplina ────────────────────────────────────────────────────
def test_sem_historico_o_que_nao_tem_requisito_e_elegivel_e_o_resto_bloqueado():
    ds = [disc(1), disc(2)]
    p = montar_painel(ds, {2: [Requisito(2, 1, "pre")]}, [])
    assert situacoes(p) == {1: ELEGIVEL, 2: BLOQUEADA}
    bloqueada = next(s for s in p.status if s.disciplina_id == 2)
    assert bloqueada.pendencias[0].alternativas == (1,)


def test_aprovar_o_requisito_libera_a_disciplina_seguinte():
    ds = [disc(1), disc(2)]
    p = montar_painel(ds, {2: [Requisito(2, 1, "pre")]}, [tent(1)])
    assert situacoes(p) == {1: CONCLUIDA, 2: ELEGIVEL}


def test_cursando_nao_satisfaz_prerequisito_mas_satisfaz_correquisito():
    ds = [disc(1), disc(2), disc(3)]
    reqs = {2: [Requisito(2, 1, "pre")], 3: [Requisito(3, 1, "co")]}
    p = montar_painel(ds, reqs, [tent(1, "cursando")])
    assert situacoes(p) == {1: CURSANDO, 2: BLOQUEADA, 3: ELEGIVEL}


def test_reprovou_e_depois_passou_conta_como_concluida():
    p = montar_painel([disc(1)], {}, [tent(1, "reprovado", "2024/1"), tent(1, "aprovado", "2024/2")])
    s = p.status[0]
    assert s.situacao == CONCLUIDA and not s.reprovada_antes


def test_so_reprovada_continua_elegivel_e_marcada_como_reprovada_antes():
    p = montar_painel([disc(1)], {}, [tent(1, "reprovado")])
    s = p.status[0]
    assert s.situacao == ELEGIVEL and s.reprovada_antes


def test_grupo_ou_basta_uma_das_alternativas():
    ds = [disc(1), disc(2), disc(3)]
    reqs = {3: [Requisito(3, 1, "pre", "g"), Requisito(3, 2, "pre", "g")]}
    assert situacoes(montar_painel(ds, reqs, [tent(2)]))[3] == ELEGIVEL


# ── progresso ────────────────────────────────────────────────────────────────
def test_progresso_usa_creditos_do_curso_e_limita_optativas():
    ds = [disc(1, 4), disc(2, 4), disc(3, 6, "optativa", None), disc(4, 6, "optativa", None)]
    p = montar_painel(ds, {}, [tent(1), tent(3), tent(4)], creditos_obrigatorios=8, creditos_optativos_exigidos=6)
    assert p.progresso.percentual == pytest.approx(71.4, abs=0.1)     # (4 + 6) de (8 + 6)
    assert p.progresso.creditos_restantes == 4
    assert (p.progresso.creditos_validos, p.progresso.creditos_exigidos) == (10, 14)
    assert p.disciplinas_concluidas == 3 and p.total_disciplinas == 4


def test_curso_sem_creditos_conhecidos_nao_inventa_percentual_nem_previsao():
    ds = [Disciplina(1, "D1", "x", None, "obrigatoria", 1)]
    p = montar_painel(ds, {}, [tent(1)])
    assert p.progresso.percentual is None and p.previsao_formatura is None
    assert p.semestres_restantes is None


# ── previsão ─────────────────────────────────────────────────────────────────
def test_previsao_usa_a_media_do_proprio_aluno():
    ds = [disc(i, 4) for i in range(1, 7)]          # 24 créditos obrigatórios
    historico = [tent(1, periodo="2024/1"), tent(2, periodo="2024/1"), tent(3, periodo="2024/2")]
    p = montar_painel(ds, {}, historico, creditos_obrigatorios=24)
    # média = (8 + 4) / 2 = 6; restam 12 → 2 períodos; o próximo livre é 2025/1 → termina em 2025/2
    assert p.origem_media == MEDIA_DO_ALUNO and p.media_creditos_periodo == 6.0
    assert p.primeiro_periodo_livre == "2025/1"
    assert p.semestres_restantes == 2 and p.previsao_formatura == "2025/2"


def test_sem_historico_usa_a_media_do_curso_mas_nao_chuta_o_periodo():
    ds = [disc(i, 4) for i in range(1, 6)]          # 20 créditos
    p = montar_painel(ds, {}, [], creditos_obrigatorios=20, duracao_semestres=4)
    assert p.origem_media == MEDIA_DO_CURSO and p.media_creditos_periodo == 5.0
    assert p.semestres_restantes == 4
    assert p.previsao_formatura is None            # sem período no histórico não há "a partir de quando"


def test_sem_media_do_aluno_nem_do_curso_nao_ha_previsao():
    p = montar_painel([disc(1, 4), disc(2, 4)], {}, [tent(1, periodo=None)], creditos_obrigatorios=8)
    assert p.origem_media is None and p.semestres_restantes is None and p.previsao_formatura is None


def test_curso_concluido_tem_zero_semestres_e_sem_data():
    p = montar_painel([disc(1, 4)], {}, [tent(1)], creditos_obrigatorios=4)
    assert p.progresso.concluido and p.semestres_restantes == 0 and p.previsao_formatura is None


def test_periodo_de_historico_em_formato_estranho_e_ignorado_na_previsao():
    p = montar_painel([disc(1, 4), disc(2, 4)], {}, [tent(1, periodo="semestre passado")],
                      creditos_obrigatorios=8, duracao_semestres=2)
    assert p.primeiro_periodo_livre is None and p.origem_media == MEDIA_DO_CURSO


def test_creditos_por_periodo_conta_a_primeira_aprovacao_de_cada_disciplina():
    ds = {1: disc(1, 4), 2: disc(2, None)}
    por_periodo = creditos_aprovados_por_periodo(
        [tent(1, periodo="2024/2"), tent(1, periodo="2024/1"), tent(2, periodo="2024/1"),
         tent(1, "reprovado", "2023/1")], ds)
    assert por_periodo == {"2024/1": 4}            # créditos desconhecidos valem 0, sem duplicar


def test_media_do_curso_exige_os_dois_dados():
    assert media_do_curso(240, 8) == 30
    assert media_do_curso(None, 8) is None and media_do_curso(240, None) is None and media_do_curso(240, 0) is None


def test_creditos_validos_e_exigidos_sem_base_ficam_coerentes():
    ds = [Disciplina(1, "D1", "x", 4, "obrigatoria", 1), Disciplina(2, "D2", "y", 6, "optativa", None)]
    p = montar_painel(ds, {}, [tent(1), tent(2)])          # curso sem nenhum total informado
    assert p.progresso.creditos_exigidos == 4              # só o que o catálogo prova (obrigatórias)
    assert p.progresso.creditos_validos == 10

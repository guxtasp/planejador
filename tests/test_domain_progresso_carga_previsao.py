"""Motor de regras: progresso, carga e previsão (substituem regras hardcoded do legado)."""
import pytest

from planner.domain.carga import avaliar_carga
from planner.domain.entidades import Disciplina
from planner.domain.previsao import (
    media_creditos_por_periodo, previsao_formatura, semestres_restantes, somar_periodos,
)
from planner.domain.progresso import calcular_progresso


def disc(i, creditos, tipo="obrigatoria"):
    return Disciplina(i, f"D{i}", f"Disc {i}", creditos, tipo)


# ── carga (inverte legacy_bug "28 fixo") ───────────────────────────────────
def test_sobrecarga_usa_o_limite_do_curso():
    d = [disc(i, 4) for i in range(8)]  # 32 créditos
    assert avaliar_carga(d, limite=28).sobrecarga is True
    assert avaliar_carga(d, limite=32).sobrecarga is False  # limite exato não é sobrecarga
    assert avaliar_carga(d, limite=40).sobrecarga is False  # curso com limite maior


def test_limite_desconhecido_nao_julga_sobrecarga():
    assert avaliar_carga([disc(i, 10) for i in range(9)], limite=None).sobrecarga is False


def test_creditos_desconhecidos_sao_sinalizados_nao_zerados_em_silencio():
    r = avaliar_carga([disc(1, 4), disc(2, None)], limite=28)
    assert r.creditos == 4 and r.disciplinas_sem_creditos == (2,)


# ── progresso (inverte legacy_bug "optativas no denominador") ──────────────
CATALOGO = [disc(1, 4), disc(2, 4), disc(3, 2, "optativa"), disc(4, 2, "optativa"), disc(5, 2, "optativa")]


def test_optativas_nao_entram_no_denominador_alem_do_exigido():
    # exige 8 obrigatórios + 4 de optativas; o catálogo tem 6 de optativas
    p = calcular_progresso(CATALOGO, aprovadas={1}, creditos_obrigatorios=8, creditos_optativos_exigidos=4)
    assert p.creditos_restantes == 8        # 4 obrig + 4 optativos
    assert p.percentual == 33.3             # 4 de 12


def test_optativas_alem_do_exigido_nao_sobram():
    p = calcular_progresso(CATALOGO, {1, 2, 3, 4, 5}, 8, 4)
    assert p.optativos_cumpridos == 6 and p.optativos_validos == 4
    assert p.creditos_restantes == 0 and p.percentual == 100.0 and p.concluido


def test_exigido_dos_obrigatorios_cai_para_soma_do_catalogo():
    p = calcular_progresso(CATALOGO, {1}, creditos_obrigatorios=None, creditos_optativos_exigidos=0)
    assert p.obrigatorios_exigidos == 8 and p.percentual == 50.0


def test_sem_base_nao_inventa_percentual():
    p = calcular_progresso([disc(1, None)], set())
    assert p.percentual is None and p.creditos_restantes is None and not p.concluido
    assert p.disciplinas_sem_creditos == (1,)


def test_optativas_sem_exigido_informado_ficam_fora_do_calculo():
    p = calcular_progresso(CATALOGO, {1, 3}, creditos_obrigatorios=8)
    assert p.creditos_restantes == 4 and p.optativos_cumpridos == 2


# ── previsão (inverte "média 20 fixa" e `getMonth() < 6`) ──────────────────
@pytest.mark.parametrize("base,n,esperado", [
    ("2026/1", 1, "2026/2"), ("2026/2", 1, "2027/1"),
    ("2026/1", 0, "2026/1"), ("2026/2", 3, "2028/1"),
    ("2026/1", -1, "2025/2"),
])
def test_somar_periodos(base, n, esperado):
    assert somar_periodos(base, n) == esperado


def test_somar_periodos_trimestral():
    assert somar_periodos("2026/3", 1, periodos_por_ano=3) == "2027/1"


@pytest.mark.parametrize("ruim", ["2026", "26/1", "2026/3", "2026/0", "abc"])
def test_periodo_invalido(ruim):
    with pytest.raises(ValueError):
        somar_periodos(ruim, 1)


def test_media_do_aluno_ignora_periodos_sem_aprovacao():
    assert media_creditos_por_periodo({"2025/1": 24, "2025/2": 0, "2026/1": 16}) == 20
    assert media_creditos_por_periodo({}) is None


def test_semestres_restantes_usa_media_do_aluno_e_so_depois_o_fallback():
    assert semestres_restantes(100, 25, media_fallback=20) == 4
    assert semestres_restantes(100, None, media_fallback=20) == 5
    assert semestres_restantes(101, 25, media_fallback=20) == 5   # arredonda para cima
    assert semestres_restantes(0, 25, media_fallback=20) == 0


def test_previsao_de_formatura():
    # 3 períodos a partir de 2026/2 → 2026/2, 2027/1, 2027/2
    assert previsao_formatura(60, "2026/2", 20, 20) == "2027/2"
    assert previsao_formatura(0, "2026/2", 20, 20) is None

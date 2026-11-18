"""
Previsão de formatura pela média do PRÓPRIO aluno.

Substitui duas regras do legado: `media_cred_sem = 20` fixo e o
`getMonth() < 6` para descobrir o semestre. O calendário vem do
`periodo_letivo` ("AAAA/N", ex.: "2026/1"); `periodos_por_ano` é parâmetro
(2 = semestral; um curso trimestral usaria 3).
"""
from __future__ import annotations

import math
import re
from typing import Mapping

_PERIODO = re.compile(r"^(\d{4})/(\d{1,2})$")


def _decompor(periodo: str, periodos_por_ano: int) -> tuple[int, int]:
    """'2026/2' → (2026, 2). Levanta ValueError se o formato/número for inválido."""
    m = _PERIODO.match(periodo)
    if not m or not 1 <= int(m.group(2)) <= periodos_por_ano:
        raise ValueError(f"periodo_letivo inválido: {periodo!r}")
    return int(m.group(1)), int(m.group(2))


_PERIODO_LIVRE = re.compile(r"^(\d{4})\s*[./-]\s*(\d{1,2})$")


def normalizar_periodo(texto: str | None, periodos_por_ano: int = 2) -> str | None:
    """
    Escreve um período letivo digitado à mão no formato canônico "AAAA/N".

    Aceita "2024.1", "2024-1", "2024/01"… Devolve `None` quando o texto não é um
    período válido (inclusive N fora de 1..`periodos_por_ano`); quem chama decide
    se isso é erro ou campo vazio.
    """
    m = _PERIODO_LIVRE.match((texto or "").strip())
    if not m or not 1 <= int(m.group(2)) <= periodos_por_ano:
        return None
    return f"{m.group(1)}/{int(m.group(2))}"


def somar_periodos(periodo: str, quantidade: int, periodos_por_ano: int = 2) -> str:
    """Avança (ou recua, se negativo) `quantidade` períodos letivos."""
    ano, n = _decompor(periodo, periodos_por_ano)
    indice = ano * periodos_por_ano + (n - 1) + quantidade
    return f"{indice // periodos_por_ano}/{indice % periodos_por_ano + 1}"


def media_creditos_por_periodo(
    creditos_aprovados_por_periodo: Mapping[str, int],
) -> float | None:
    """
    Média de créditos aprovados por período em que o aluno concluiu algo.
    `None` quando não há histórico (o chamador usa o fallback configurável).
    """
    valores = [c for c in creditos_aprovados_por_periodo.values() if c > 0]
    return sum(valores) / len(valores) if valores else None


def semestres_restantes(
    creditos_restantes: int, media_do_aluno: float | None, media_fallback: float
) -> int:
    """Períodos necessários, arredondando para cima. 0 se nada resta."""
    if creditos_restantes <= 0:
        return 0
    media = media_do_aluno if media_do_aluno and media_do_aluno > 0 else media_fallback
    if media <= 0:
        raise ValueError("media_fallback deve ser positiva")
    return math.ceil(creditos_restantes / media)


def previsao_formatura(
    creditos_restantes: int,
    primeiro_periodo_livre: str,
    media_do_aluno: float | None,
    media_fallback: float,
    periodos_por_ano: int = 2,
) -> str | None:
    """
    Último período letivo previsto. `primeiro_periodo_livre` é o próximo em que
    o aluno ainda pode se matricular. `None` = já concluiu.
    """
    n = semestres_restantes(creditos_restantes, media_do_aluno, media_fallback)
    if n == 0:
        return None
    return somar_periodos(primeiro_periodo_livre, n - 1, periodos_por_ano)

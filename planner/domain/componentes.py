"""
Turma teórica e turma prática separadas (ex.: T1, P1, P2 no quadro de horários).

A matrícula numa disciplina assim é UMA teórica + UMA prática do mesmo período. Em vez de ensinar
isso a cada regra (alocação, otimizador, simulador, calendário), as partes viram "opções de
matrícula" combinadas: uma turma virtual com os encontros das duas e um id negativo que se desfaz
nas partes. Tudo que já sabe escolher UMA turma por disciplina continua funcionando.

  * turma sem componente (completa)      → opção sozinha, como sempre;
  * só teóricas ou só práticas no período → cada uma é uma opção sozinha (nada para combinar);
  * teóricas e práticas no período        → todas as combinações teórica × prática.

Pura, só stdlib.
"""
from __future__ import annotations

from typing import Sequence, TypeVar

TEORICA, PRATICA = "teorica", "pratica"
COMPONENTES = (TEORICA, PRATICA)
_BASE = 10**7          # ids reais abaixo de 10 milhões cabem na codificação (e no inteiro seguro do JS)
MAX_COMBINACOES = 200  # por disciplina e período: o quadro real nunca chega perto

T = TypeVar("T")


def normalizar_componente(texto: str | None) -> str | None:
    """"Teórica", "T", "teoria" → teorica; "Prática", "P", "lab" → pratica; vazio → None; outro → ValueError."""
    if texto is None or not str(texto).strip():
        return None
    t = str(texto).strip().lower()
    t = t.translate(str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc"))
    if t in ("t", "teo", "teorica", "teoria", "teorico"):
        return TEORICA
    if t in ("p", "pra", "pratica", "pratico", "lab", "laboratorio"):
        return PRATICA
    raise ValueError(texto)


def id_combinado(teorica_id: int, pratica_id: int) -> int:
    """Id da opção "teórica + prática" (negativo, decodificável por `partes_do_id`)."""
    if not (0 < teorica_id < _BASE and 0 < pratica_id < _BASE):
        raise ValueError("id de turma fora da faixa da combinação")
    return -(teorica_id * _BASE + pratica_id)


def partes_do_id(turma_id: int) -> tuple[int, ...]:
    """(id,) para turma real; (teórica, prática) para uma opção combinada."""
    if turma_id >= 0:
        return (turma_id,)
    t, p = divmod(-turma_id, _BASE)
    return (t, p)


def e_combinado(turma_id: int | None) -> bool:
    return turma_id is not None and turma_id <= -_BASE


def opcoes_de_matricula(turmas: Sequence[T]) -> list[tuple[T, ...]]:
    """
    As opções de matrícula de UMA disciplina: tuplas de 1 turma (completa) ou 2 (teórica, prática).
    Cada turma precisa de `periodo_letivo` e `componente` (None = completa). Ordem estável.
    """
    por_periodo: dict[object, list[T]] = {}
    for t in turmas:
        por_periodo.setdefault(t.periodo_letivo, []).append(t)
    saida: list[tuple[T, ...]] = []
    for periodo in sorted(por_periodo, key=lambda p: (p is None, str(p))):
        ts = por_periodo[periodo]
        teoricas = [t for t in ts if getattr(t, "componente", None) == TEORICA]
        praticas = [t for t in ts if getattr(t, "componente", None) == PRATICA]
        saida += [(t,) for t in ts if getattr(t, "componente", None) not in COMPONENTES]
        if teoricas and praticas:
            saida += [(a, b) for a in teoricas for b in praticas][:MAX_COMBINACOES]
        else:
            saida += [(t,) for t in teoricas + praticas]
    return saida

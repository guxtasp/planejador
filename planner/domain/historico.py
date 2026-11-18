"""
Situação do aluno por disciplina, a partir de N tentativas.

Corrige o defeito #4 do legado (um único registro por disciplina: uma
reprovação seguida de aprovação sobrescrevia a anterior). Aqui as tentativas
se ACUMULAM e a situação é derivada delas.

Decisão da Etapa 2 sobre `StatusHistorico`: NÃO foram criados `trancado` nem
`dispensado`. Trancamento não conclui nada (basta não registrar tentativa) e
dispensa/equivalência é registrada como `aprovado`. Status desconhecidos são
ignorados pelo motor, então acrescentar um depois não quebra nada.
"""
from __future__ import annotations

from typing import Iterable

from .entidades import (
    STATUS_APROVADO,
    STATUS_CURSANDO,
    STATUS_REPROVADO,
    Tentativa,
)

APROVADA = "aprovada"
CURSANDO = "cursando"
REPROVADA = "reprovada"  # só há tentativas reprovadas


def situacoes(tentativas: Iterable[Tentativa]) -> dict[int, str]:
    """
    Situação atual de cada disciplina que aparece no histórico.

    Precedência: qualquer aprovação vale (aprovou, está feito); senão, estar
    cursando vale mais que uma reprovação antiga; senão, reprovada.
    """
    por_disciplina: dict[int, set[str]] = {}
    for t in tentativas:
        por_disciplina.setdefault(t.disciplina_id, set()).add(t.status)

    resultado: dict[int, str] = {}
    for disciplina_id, status in por_disciplina.items():
        if STATUS_APROVADO in status:
            resultado[disciplina_id] = APROVADA
        elif STATUS_CURSANDO in status:
            resultado[disciplina_id] = CURSANDO
        elif STATUS_REPROVADO in status:
            resultado[disciplina_id] = REPROVADA
    return resultado


def aprovadas(tentativas: Iterable[Tentativa]) -> frozenset[int]:
    """IDs das disciplinas com ao menos uma aprovação."""
    return frozenset(d for d, s in situacoes(tentativas).items() if s == APROVADA)


def cursando(tentativas: Iterable[Tentativa]) -> frozenset[int]:
    """IDs das disciplinas em andamento (e ainda não aprovadas)."""
    return frozenset(d for d, s in situacoes(tentativas).items() if s == CURSANDO)

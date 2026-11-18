"""
Carga de créditos de um semestre.

Corrige a regra hardcoded do legado (`creditos > 28` para qualquer curso): o
limite vem de `curso.max_creditos_semestre`. Limite desconhecido (`None`)
significa que NÃO há julgamento de sobrecarga — nunca se assume um número.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .entidades import Disciplina


@dataclass(frozen=True)
class AvaliacaoCarga:
    creditos: int
    limite: int | None
    sobrecarga: bool
    disciplinas_sem_creditos: tuple[int, ...]  # somadas como 0, mas sinalizadas


def avaliar_carga(
    disciplinas: Iterable[Disciplina], limite: int | None
) -> AvaliacaoCarga:
    """Soma os créditos conhecidos e compara com o limite do curso."""
    lista = list(disciplinas)
    total = sum(d.creditos or 0 for d in lista)
    return AvaliacaoCarga(
        creditos=total,
        limite=limite,
        sobrecarga=limite is not None and total > limite,
        disciplinas_sem_creditos=tuple(sorted(d.id for d in lista if d.creditos is None)),
    )

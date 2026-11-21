"""
Regras para editar uma disciplina do catálogo pela tela (sem reimportar CSV).

Pura, só stdlib. O serviço monta as arestas atuais do curso e pergunta se os NOVOS
pré-requisitos de uma disciplina fecham um círculo (A exige B, B exige A): isso tornaria
as duas impossíveis de cursar, então a edição é recusada com os envolvidos.
"""
from __future__ import annotations

from typing import Iterable

from .ciclos import componentes_ciclicos


def ciclo_com_novos_requisitos(
    disciplina_id: int,
    novos_pre: Iterable[int],
    pre_do_curso: Iterable[tuple[int, int]],
) -> tuple[int, ...]:
    """
    Disciplinas que passariam a se exigir em círculo se `disciplina_id` tivesse `novos_pre`
    como pré-requisitos (correquisito mútuo é permitido e não entra aqui).

    `pre_do_curso` são as arestas atuais `(quem_exige, exigida)`; as da própria disciplina
    são substituídas pelas novas. Devolve `()` quando não há ciclo.
    """
    arestas = [(a, b) for a, b in pre_do_curso if a != disciplina_id]
    arestas += [(disciplina_id, b) for b in novos_pre]
    for grupo in componentes_ciclicos(arestas):
        if disciplina_id in grupo:
            return grupo
    return ()

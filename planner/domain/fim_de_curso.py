"""
Disciplinas de FIM DE CURSO (TCC, Trabalho de Conclusão, Monografia, Projeto Final, Elaboração de TCC e os
seminários que as acompanham): fecham o curso, então ficam nos ÚLTIMOS semestres do plano.

Muitos catálogos não dizem isso nos pré-requisitos (o Projeto Final do exemplo de CC só exige INF221), e
o otimizador as punha cedo. Aqui:

  * `disciplinas_de_fim_de_curso`  quais são, por nome (família "conclusão") ou, para seminários, por estarem
                                   no último ano do curso ou ligadas por requisito a uma de conclusão;
  * cada uma recebe um DEGRAU: quantos semestres ainda vêm depois dela dentro do fim de curso
    (0 = último semestre). Vem do período sugerido (TCC I/Elaboração no 7º e TCC II/Seminário no 8º → 1 e 0)
    ou, sem ele, da cadeia de requisitos entre elas (TCC I → TCC II).

Função pura, só stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Mapping, Sequence

from .entidades import Disciplina, Requisito

_CONCLUSAO = re.compile(r"\b(tcc|trabalho de conclusao|monografia|projeto final|projeto de conclusao|"
                        r"elaboracao de tcc|elaboracao do tcc|trabalho final de curso)\b")
_SEMINARIO = re.compile(r"\bseminario")


def _norm(texto: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower().split())


def e_conclusao(d: Disciplina) -> bool:
    return bool(_CONCLUSAO.search(_norm(d.nome) + " " + _norm(d.codigo)))


def disciplinas_de_fim_de_curso(
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
) -> dict[int, int]:
    """{id: degrau} das disciplinas de fim de curso (degrau 0 = último semestre do plano)."""
    conclusao = {i for i, d in disciplinas.items() if e_conclusao(d)}
    if not conclusao:
        return {}
    sugeridos = [d.periodo_sugerido for d in disciplinas.values() if d.periodo_sugerido is not None]
    ultimo_ano = (max(sugeridos) - 1) if sugeridos else None

    def ligada(i: int) -> bool:                    # requisito em qualquer sentido com uma de conclusão
        if any(r.requisito_id in conclusao for r in requisitos.get(i, ())):
            return True
        return any(r.requisito_id == i for c in conclusao for r in requisitos.get(c, ()))

    fim = set(conclusao)
    for i, d in disciplinas.items():
        if i in fim or not _SEMINARIO.search(_norm(d.nome)):
            continue
        no_ultimo_ano = d.periodo_sugerido is not None and ultimo_ano is not None and d.periodo_sugerido >= ultimo_ano
        if no_ultimo_ano or ligada(i):
            fim.add(i)

    # degrau pelo período sugerido (quando todas têm), senão pela cadeia de pré-requisitos entre elas
    sug = {i: disciplinas[i].periodo_sugerido for i in fim}
    if all(v is not None for v in sug.values()):
        topo = max(sug.values())
        return {i: topo - v for i, v in sug.items()}
    degrau = {i: 0 for i in fim}
    for _ in range(len(fim)):
        mudou = False
        for j in fim:                               # j exige i (pré) → i fica um degrau antes de j
            for r in requisitos.get(j, ()):
                i = r.requisito_id
                if i in fim and r.tipo == "pre" and degrau[i] < degrau[j] + 1:
                    degrau[i], mudou = degrau[j] + 1, True
        if not mudou:
            break
    return degrau

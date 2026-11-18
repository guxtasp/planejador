"""
Pré-requisitos e correquisitos, com grupos "A ou B" e plano sequencial.

Corrige os defeitos #5 (o legado só olhava o histórico e ignorava semestres
anteriores do próprio plano) e #6 (só havia AND).

Regras:
  * `pre` é cumprido apenas por disciplinas CONCLUÍDAS (aprovadas no histórico
    ou planejadas em semestres anteriores).
  * `co` também é cumprido por quem está cursando ou está no MESMO semestre.
  * Requisitos com o mesmo (tipo, grupo_alt) formam um OR; sem grupo, cada um
    é um AND independente.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Iterable, Mapping, Sequence

from .entidades import REQ_CO, Disciplina, Requisito


@dataclass(frozen=True)
class Pendencia:
    """
    Um requisito não cumprido. `alternativas` tem 1 id (AND) ou vários (OR:
    basta cumprir UM deles). Ids em ordem crescente, para saída determinística.
    """

    tipo: str
    alternativas: tuple[int, ...]

    @property
    def e_alternativa(self) -> bool:
        """True quando é um "A ou B" (mais de uma opção)."""
        return len(self.alternativas) > 1


@dataclass(frozen=True)
class ProblemaPlano:
    """Pendência de uma disciplina em um semestre do plano (posição a partir de 1)."""

    posicao_semestre: int
    disciplina_id: int
    pendencia: Pendencia


def _agrupar(requisitos: Iterable[Requisito]) -> list[tuple[str, list[int]]]:
    """
    Agrupa requisitos em termos (tipo, alternativas), mantendo a ordem de
    aparição. Sem `grupo_alt`, cada requisito é seu próprio termo (AND).
    """
    termos: dict[tuple, tuple[str, list[int]]] = {}
    for r in requisitos:
        chave = (r.tipo, r.grupo_alt) if r.grupo_alt else (r.tipo, None, r.requisito_id)
        termos.setdefault(chave, (r.tipo, []))[1].append(r.requisito_id)
    return list(termos.values())


agrupar_requisitos = _agrupar   # nome público: o grafo e o otimizador usam a mesma regra de E/OU


def avaliar_requisitos(
    requisitos: Iterable[Requisito],
    concluidas: Collection[int],
    simultaneas: Collection[int] = (),
) -> tuple[Pendencia, ...]:
    """
    Pendências de UMA disciplina (lista vazia = pode cursar).

    `concluidas`: já feitas (satisfazem pre e co).
    `simultaneas`: cursando agora / no mesmo semestre (satisfazem só co).
    """
    pendencias = []
    for tipo, alternativas in _agrupar(requisitos):
        disponiveis = set(concluidas) | (set(simultaneas) if tipo == REQ_CO else set())
        if not disponiveis.intersection(alternativas):
            pendencias.append(Pendencia(tipo, tuple(sorted(set(alternativas)))))
    return tuple(pendencias)


def verificar_plano(
    semestres: Sequence[Collection[int]],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    aprovadas: Collection[int] = (),
    cursando: Collection[int] = (),
) -> tuple[ProblemaPlano, ...]:
    """
    Valida um plano sequencial: `semestres[0]` é o primeiro a cursar.

    Premissa deliberada: o que está planejado num semestre ANTERIOR conta como
    concluído nos seguintes (o plano é uma projeção otimista). Quem planeja
    sabe que isso depende de aprovação; o aviso aparece, mas nada é bloqueado.
    """
    concluidas = set(aprovadas)
    problemas: list[ProblemaPlano] = []
    for posicao, semestre in enumerate(semestres, start=1):
        simultaneas = set(cursando) | set(semestre)
        for disciplina_id in sorted(semestre):
            reqs = requisitos_por_disciplina.get(disciplina_id, ())
            for p in avaliar_requisitos(reqs, concluidas, simultaneas):
                problemas.append(ProblemaPlano(posicao, disciplina_id, p))
        concluidas |= set(semestre)
    return tuple(problemas)


@dataclass(frozen=True)
class Classificacao:
    """Resultado do "assistente": onde cada disciplina do catálogo se encaixa."""

    concluidas: tuple[Disciplina, ...]
    em_andamento: tuple[Disciplina, ...]
    elegiveis: tuple[Disciplina, ...]
    bloqueadas: tuple[tuple[Disciplina, tuple[Pendencia, ...]], ...]


def classificar_disciplinas(
    disciplinas: Iterable[Disciplina],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    aprovadas: Collection[int],
    cursando: Collection[int] = (),
) -> Classificacao:
    """Separa o catálogo em concluídas, em andamento, elegíveis e bloqueadas."""
    concluidas, andamento, elegiveis, bloqueadas = [], [], [], []
    for d in disciplinas:
        if d.id in aprovadas:
            concluidas.append(d)
        elif d.id in cursando:
            andamento.append(d)
        else:
            pend = avaliar_requisitos(
                requisitos_por_disciplina.get(d.id, ()), aprovadas, cursando
            )
            (bloqueadas.append((d, pend)) if pend else elegiveis.append(d))
    return Classificacao(
        tuple(concluidas), tuple(andamento), tuple(elegiveis), tuple(bloqueadas)
    )

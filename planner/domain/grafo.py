"""
Grafo de dependências do que FALTA cursar, e o método do caminho crítico (CPM)
com calendário de oferta.

Visão de grafos: cada disciplina pendente é um nó; "A exige B" é uma aresta B → A
de peso 1 (pré-requisito: B num semestre ANTERIOR) ou 0 (correquisito: B no MESMO
semestre ou antes). Requisito "B ou C" é um grupo de arestas alternativas: basta UMA.

O que o grafo responde (todas as funções são puras, só stdlib):

  * `construir_grafo`    quais exigências ainda não estão cumpridas (e quais são impossíveis);
  * `ciclos`             pré-requisitos circulares (plano impossível);
  * `descendentes`       quantas disciplinas dependem, direta ou indiretamente, de cada uma;
  * `primeiros_semestres` menor semestre em que cada disciplina PODE ser cursada,
                         já respeitando em que períodos ela é ofertada (paridade);
  * `ultimos_semestres`  maior semestre em que ainda dá para cursá-la sem atrasar o fim;
  * `folgas`             última − primeira; folga 0 = caminho crítico (atrasar = atrasar a formatura).

Semestres são ÍNDICES (0 = primeiro período planejado). `oferta(no, indice)` diz se
o nó é ofertado naquele índice; quem chama traduz índice → período letivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Collection, Iterable, Mapping, Sequence

from .ciclos import componentes_ciclicos
from .entidades import REQ_CO, REQ_PRE, Requisito
from .requisitos import agrupar_requisitos

Oferta = Callable[[int, int], bool]
INF = float("inf")


@dataclass(frozen=True)
class Termo:
    """Uma exigência: cumprir UMA das `alternativas` (1 = obrigatória). `tipo` = 'pre' | 'co'."""

    tipo: str
    alternativas: tuple[int, ...]

    @property
    def folga_entre_semestres(self) -> int:
        """Distância mínima: pré = 1 semestre à frente; correquisito = mesmo semestre."""
        return 0 if self.tipo == REQ_CO else 1

    @property
    def e_obrigatoria(self) -> bool:
        return len(self.alternativas) == 1


@dataclass(frozen=True)
class Grafo:
    nos: tuple[int, ...]
    termos: Mapping[int, tuple[Termo, ...]]       # só exigências AINDA não cumpridas
    impossiveis: Mapping[int, tuple[Termo, ...]]  # nenhuma alternativa está no conjunto a cursar


def construir_grafo(
    nos: Iterable[int],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    concluidas: Collection[int] = (),
) -> Grafo:
    """
    Reduz o catálogo ao que falta. Exigência com alguma alternativa já concluída
    some. As alternativas restantes são limitadas a `nos` (o que será cursado);
    se não sobrar nenhuma, a exigência é IMPOSSÍVEL neste conjunto.
    """
    conjunto = set(nos)
    feitas = set(concluidas)
    termos: dict[int, tuple[Termo, ...]] = {}
    impossiveis: dict[int, tuple[Termo, ...]] = {}
    for n in sorted(conjunto):
        validos, perdidos = [], []
        for tipo, alternativas in agrupar_requisitos(requisitos_por_disciplina.get(n, ())):
            if feitas.intersection(alternativas):
                continue
            restantes = tuple(sorted(a for a in set(alternativas) if a in conjunto and a != n))
            (validos if restantes else perdidos).append(Termo(tipo, restantes or tuple(sorted(set(alternativas)))))
        termos[n] = tuple(validos)
        if perdidos:
            impossiveis[n] = tuple(perdidos)
    return Grafo(tuple(sorted(conjunto)), termos, impossiveis)


def ciclos(grafo: Grafo) -> tuple[tuple[int, ...], ...]:
    """Grupos que se exigem em círculo (só pré-requisitos; correquisito mútuo é permitido)."""
    arestas = [
        (n, a) for n, ts in grafo.termos.items() for t in ts if t.tipo == REQ_PRE for a in t.alternativas
    ]
    return componentes_ciclicos(arestas)


def descendentes(grafo: Grafo) -> dict[int, frozenset[int]]:
    """Para cada nó, todos os que dependem dele (por qualquer alternativa), direta ou indiretamente."""
    dependentes: dict[int, set[int]] = {n: set() for n in grafo.nos}
    for n, ts in grafo.termos.items():
        for t in ts:
            for a in t.alternativas:
                dependentes[a].add(n)
    resultado: dict[int, frozenset[int]] = {}
    for n in grafo.nos:
        visto: set[int] = set()
        pilha = list(dependentes[n])
        while pilha:
            v = pilha.pop()
            if v in visto or v == n:
                continue
            visto.add(v)
            pilha.extend(dependentes[v])
        resultado[n] = frozenset(visto)
    return resultado


def _primeiro_ofertado(no: int, a_partir_de: int, horizonte: int, oferta: Oferta) -> float:
    for t in range(a_partir_de, horizonte):
        if oferta(no, t):
            return t
    return INF


def primeiros_semestres(grafo: Grafo, horizonte: int, oferta: Oferta) -> dict[int, float]:
    """
    Menor índice de semestre em que cada nó pode ser cursado (INF = não cabe no horizonte).

    Relaxamento tipo Bellman-Ford: parte do primeiro semestre ofertado e empurra para
    frente até estabilizar. OR = mínimo entre as alternativas; AND = máximo entre exigências.
    """
    e = {n: _primeiro_ofertado(n, 0, horizonte, oferta) for n in grafo.nos}
    for n in grafo.impossiveis:
        e[n] = INF
    for _ in range(len(grafo.nos) * 2 + 2):
        mudou = False
        for n in grafo.nos:
            if e[n] == INF:
                continue
            piso = 0.0
            for t in grafo.termos[n]:
                piso = max(piso, min(e[a] + t.folga_entre_semestres for a in t.alternativas))
            if piso == INF:
                novo = INF
            else:
                novo = _primeiro_ofertado(n, int(max(piso, e[n])), horizonte, oferta)
            if novo != e[n]:
                e[n], mudou = novo, True
        if not mudou:
            break
    return e


def ultimos_semestres(grafo: Grafo, horizonte: int, oferta: Oferta) -> dict[int, float]:
    """
    Maior índice de semestre (≤ horizonte−1) em que cada nó ainda pode ser cursado para
    TODOS os que dependem dele caberem até o fim (-INF = impossível). Só exigências
    obrigatórias limitam: num "B ou C", nenhum dos dois é indispensável sozinho.
    """
    ultimo_ofertado = lambda n, teto: next(
        (t for t in range(min(int(teto), horizonte - 1), -1, -1) if oferta(n, t)), -INF)
    folga: dict[int, float] = {n: ultimo_ofertado(n, horizonte - 1) for n in grafo.nos}
    for _ in range(len(grafo.nos) * 2 + 2):
        mudou = False
        for s in grafo.nos:
            for t in grafo.termos[s]:
                if not t.e_obrigatoria:
                    continue
                (a,) = t.alternativas
                teto = folga[s] - t.folga_entre_semestres
                novo = ultimo_ofertado(a, teto) if teto > -INF else -INF
                if novo < folga[a]:
                    folga[a], mudou = novo, True
        if not mudou:
            break
    return folga


def folgas(primeiros: Mapping[int, float], ultimos: Mapping[int, float]) -> dict[int, float]:
    """Semestres de folga de cada nó (0 = crítico; -INF/INF onde o horizonte não comporta)."""
    return {n: ultimos[n] - primeiros[n] for n in primeiros}


def menor_horizonte(primeiros: Mapping[int, float]) -> float:
    """Menor nº de semestres que o grafo + calendário permitem (ignora créditos). INF = impossível."""
    return INF if not primeiros else (max(primeiros.values()) + 1 if INF not in primeiros.values() else INF)

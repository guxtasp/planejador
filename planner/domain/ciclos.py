"""
Ciclos em grafos de dependência (ex.: A exige B, B exige C, C exige A).

Regra pura, só stdlib. Usada pelo importador (Etapa 3B) para recusar
pré-requisitos impossíveis de cumprir. Genérica no tipo do nó (ids, códigos…).
Algoritmo de Tarjan na versão iterativa: não estoura o limite de recursão do
Python mesmo em catálogos grandes.
"""
from __future__ import annotations

from typing import Hashable, Iterable, TypeVar

N = TypeVar("N", bound=Hashable)


def componentes_ciclicos(arestas: Iterable[tuple[N, N]]) -> tuple[tuple[N, ...], ...]:
    """
    Grupos de nós que dependem uns dos outros, direta ou indiretamente.

    Cada aresta `(a, b)` significa "a depende de b". Um grupo só é devolvido se
    houver ciclo: 2+ nós mutuamente alcançáveis, ou um nó que depende de si mesmo.
    A saída é determinística: nós ordenados dentro do grupo e grupos ordenados
    pelo primeiro nó (por isso os nós precisam ser comparáveis entre si).
    """
    vizinhos: dict[N, list[N]] = {}
    for origem, destino in arestas:
        vizinhos.setdefault(origem, []).append(destino)
        vizinhos.setdefault(destino, [])
    auto_dependentes = {n for n, vs in vizinhos.items() if n in vs}

    indice: dict[N, int] = {}
    baixo: dict[N, int] = {}
    na_pilha: set[N] = set()
    pilha: list[N] = []
    grupos: list[tuple[N, ...]] = []

    for raiz in sorted(vizinhos):
        if raiz in indice:
            continue
        # Pilha de trabalho: (nó, iterador sobre os vizinhos ainda não visitados).
        trabalho = [(raiz, iter(sorted(set(vizinhos[raiz]))))]
        indice[raiz] = baixo[raiz] = len(indice)
        pilha.append(raiz)
        na_pilha.add(raiz)
        while trabalho:
            no, restantes = trabalho[-1]
            avancou = False
            for v in restantes:
                if v not in indice:
                    indice[v] = baixo[v] = len(indice)
                    pilha.append(v)
                    na_pilha.add(v)
                    trabalho.append((v, iter(sorted(set(vizinhos[v])))))
                    avancou = True
                    break
                if v in na_pilha:
                    baixo[no] = min(baixo[no], indice[v])
            if avancou:
                continue
            trabalho.pop()
            if trabalho:
                pai = trabalho[-1][0]
                baixo[pai] = min(baixo[pai], baixo[no])
            if baixo[no] == indice[no]:  # `no` é a raiz de um componente
                componente = []
                while True:
                    m = pilha.pop()
                    na_pilha.discard(m)
                    componente.append(m)
                    if m == no:
                        break
                if len(componente) > 1 or no in auto_dependentes:
                    grupos.append(tuple(sorted(componente)))
    return tuple(sorted(grupos))

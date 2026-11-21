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
  * `folgas`             última − primeira; folga 0 = caminho crítico (atrasar = atrasar a formatura);
  * `alturas`            caminho mais longo até um sumidouro (pré = 1, co = 0): quantos semestres
                         ainda vêm DEPOIS de cada nó, no mínimo;
  * `pesos_posicionais`  créditos do nó + de todos os descendentes (quanto trabalho ele segura);
  * `cadeia_critica`     a sequência explícita A → B → C que define o prazo;
  * `limite_energetico`  limite inferior por créditos que não cabem antes/depois de cada semestre;
  * `horizonte_por_janelas` raciocínio energético com janelas [mais cedo, mais tarde] e calendário.

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


# ── prioridade (Hu / Coffman-Graham) e cadeia crítica ─────────────────────────
def _dependentes(grafo: Grafo, so_obrigatorias: bool) -> dict[int, list[tuple[int, int]]]:
    """Para cada nó, os que dependem dele: [(dependente, distância mínima em semestres)]."""
    deps: dict[int, list[tuple[int, int]]] = {n: [] for n in grafo.nos}
    for n, ts in grafo.termos.items():
        for t in ts:
            if so_obrigatorias and not t.e_obrigatoria:
                continue
            for a in t.alternativas:
                deps[a].append((n, t.folga_entre_semestres))
    return deps


def alturas(grafo: Grafo, so_obrigatorias: bool = False) -> dict[int, int]:
    """
    Altura de cada nó: o caminho mais longo até um sumidouro, com peso 1 para pré-requisito e 0
    para correquisito. É o nº mínimo de semestres que ainda vêm DEPOIS do nó (Hu, 1961).

    `so_obrigatorias=True` ignora arestas de "A ou B" (nenhuma alternativa é indispensável sozinha):
    assim a altura vira um limite seguro para provas. Supõe o grafo sem ciclo de pré-requisito
    (ver `ciclos`); correquisito mútuo tem peso 0 e não atrapalha.
    """
    deps = _dependentes(grafo, so_obrigatorias)
    h = {n: 0 for n in grafo.nos}
    for _ in range(len(grafo.nos) + 1):        # relaxação: sem ciclo positivo, estabiliza em ≤ n passos
        mudou = False
        for n in grafo.nos:
            novo = max((f + h[d] for d, f in deps[n]), default=0)
            if novo > h[n]:
                h[n], mudou = novo, True
        if not mudou:
            break
    return h


def pesos_posicionais(grafo: Grafo, creditos: Mapping[int, int | None]) -> dict[int, int]:
    """Créditos do nó + de todos os seus descendentes. Crédito desconhecido soma 0 (não se inventa)."""
    desc = descendentes(grafo)
    cred = lambda n: creditos.get(n) or 0
    return {n: cred(n) + sum(cred(d) for d in desc[n]) for n in grafo.nos}


def cadeia_critica(grafo: Grafo, primeiros: Mapping[int, float]) -> tuple[int, ...]:
    """
    A sequência explícita de disciplinas que define o prazo (A → B → C), da primeira à última.

    Parte do nó que termina mais tarde e volta pela exigência que o "segura": o termo cujo
    menor (primeiro semestre da alternativa + distância) é o maior; dentro dele, a alternativa
    que chega primeiro. Empate: maior primeiro semestre, depois menor id (determinístico).
    Nós inalcançáveis (INF) não entram.
    """
    alcancaveis = [n for n in grafo.nos if primeiros.get(n, INF) != INF]
    if not alcancaveis:
        return ()
    fim = max(alcancaveis, key=lambda n: (primeiros[n], -n))
    cadeia = [fim]
    visto = {fim}
    atual = fim
    while True:
        melhor: tuple[float, int] | None = None   # (chegada da alternativa, id)
        piso = -INF
        for t in grafo.termos.get(atual, ()):
            opcoes = [(primeiros[a] + t.folga_entre_semestres, a) for a in t.alternativas
                      if primeiros.get(a, INF) != INF and a not in visto]
            if not opcoes:
                continue
            chegada, a = min(opcoes, key=lambda x: (x[0], x[1]))
            if chegada > piso or (chegada == piso and melhor is not None and a < melhor[1]):
                piso, melhor = chegada, (chegada, a)
        if melhor is None:
            break
        atual = melhor[1]
        cadeia.append(atual)
        visto.add(atual)
    return tuple(reversed(cadeia))


# ── limites inferiores por créditos (raciocínio "energético") ─────────────────
def limite_energetico(
    primeiros: Mapping[int, float],
    caudas: Mapping[int, int],
    creditos: Mapping[int, int | None],
    teto: int | None,
) -> int:
    """
    Limite inferior de semestres pelos créditos que não podem ir para o começo nem para o fim.

    Quem tem primeiro semestre ≥ a não cabe nos `a` primeiros; quem tem cauda (altura) ≥ b precisa
    de `b` semestres depois de si, logo não cabe nos `b` últimos. Para todo par (a, b):

        H ≥ a + b + ceil(créditos desses nós / teto)

    Com b = 0 é o lado das "cabeças"; com a = 0, o das caudas; a = b = 0 é a soma simples.
    Sem teto conhecido não há limite por créditos (devolve 0).
    """
    if not teto:
        return 0
    nos = [n for n in primeiros if primeiros[n] != INF]
    if not nos:
        return 0
    max_a = int(max(primeiros[n] for n in nos))
    max_b = max((caudas.get(n, 0) for n in nos), default=0)
    melhor = 0
    for a in range(max_a + 1):
        for b in range(max_b + 1):
            soma = sum(creditos.get(n) or 0 for n in nos if primeiros[n] >= a and caudas.get(n, 0) >= b)
            if soma:
                melhor = max(melhor, a + b + -(-soma // teto))
    return melhor


def janelas_cabem(
    primeiros: Mapping[int, float],
    ultimos: Mapping[int, float],
    creditos: Mapping[int, int | None],
    teto: "int | Callable[[int], int]",
    oferta: Oferta | None = None,
) -> bool:
    """
    Teste energético num horizonte fixo: cada nó só pode ir para [primeiro, último]. Para toda
    janela [i, j], os créditos dos nós presos dentro dela têm de caber nos semestres da janela.

    Com `oferta`, o teste também olha QUAIS semestres da janela cada nó pode usar (condição de
    Hall): os nós que só abrem num subconjunto K desses semestres (ex.: só os ímpares) têm de
    caber em |K| × teto. Falhar prova que o horizonte é curto demais (nunca o contrário).
    """
    # `teto` pode ser um número ou a capacidade de cada semestre (teto específico; trancado = 0)
    cap = teto if callable(teto) else (lambda _t: teto)
    nos = list(primeiros)
    if any(ultimos[n] < primeiros[n] for n in nos):
        return False
    pontos = sorted({int(primeiros[n]) for n in nos} | {int(ultimos[n]) for n in nos})
    for i in pontos:
        for j in pontos:
            if j < i:
                continue
            presos = [n for n in nos if primeiros[n] >= i and ultimos[n] <= j]
            if not presos:
                continue
            if sum(creditos.get(n) or 0 for n in presos) > sum(cap(t) for t in range(i, j + 1)):
                return False
            if oferta is None:
                continue
            usaveis = {n: frozenset(t for t in range(int(primeiros[n]), int(ultimos[n]) + 1) if oferta(n, t))
                       for n in presos}
            for k in set(usaveis.values()):
                soma = sum(creditos.get(n) or 0 for n in presos if usaveis[n] <= k)
                if soma > sum(cap(t) for t in k):
                    return False
    return True


def horizonte_por_janelas(
    grafo: Grafo,
    primeiros: Mapping[int, float],
    creditos: Mapping[int, int | None],
    teto: "int | Callable[[int], int] | None",
    oferta: Oferta,
    a_partir_de: int,
    horizonte_max: int,
) -> int:
    """
    Menor horizonte H ≥ `a_partir_de` que passa no teste de janelas (`janelas_cabem`), com o último
    semestre de cada nó recalculado para H (calendário par/ímpar incluído). É um LIMITE INFERIOR:
    abaixo dele é impossível. Sem teto, devolve `a_partir_de`.
    """
    if not teto:
        return a_partir_de
    for h in range(max(1, a_partir_de), horizonte_max + 1):
        ultimos = ultimos_semestres(grafo, h, oferta)
        if all(u != -INF for u in ultimos.values()) and janelas_cabem(primeiros, ultimos, creditos, teto, oferta):
            return h
    return horizonte_max + 1

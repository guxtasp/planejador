"""
O que FALTA cursar, e quando cada disciplina pode ser cursada (calendário de oferta).

Base comum do simulador e do otimizador (funções puras, só stdlib):

  * `CalendarioDeOferta`  traduz ÍNDICE de semestre (0 = primeiro período planejado) em período
                          letivo real ("2027/1") e responde "esta disciplina existe neste semestre?"
                          pela periodicidade efetiva (par / ímpar / sempre). É um `Oferta` do `grafo`.
  * `nos_a_cursar`        obrigatórias pendentes + o que elas exigem (fechamento de requisitos).

Periodicidade desconhecida NÃO vira "sempre" em silêncio: `periodicidade_efetiva` estima pelo
período sugerido na matriz e marca a origem (cadastrada / estimada / desconhecida).
"""
from __future__ import annotations

from typing import Collection, Iterable, Mapping, Sequence

from .entidades import PER_SEMPRE, TIPO_OBRIGATORIA, Disciplina, Requisito
from .periodicidade import PeriodicidadeEfetiva, ofertada_em, periodicidade_efetiva
from .previsao import somar_periodos
from .requisitos import agrupar_requisitos


class CalendarioDeOferta:
    """Índice de semestre → período letivo → a disciplina é ofertada?"""

    def __init__(
        self,
        periodo_inicial: str,
        efetivas: Mapping[int, PeriodicidadeEfetiva],
        periodos_por_ano: int = 2,
    ) -> None:
        self.periodo_inicial = periodo_inicial
        self.efetivas = efetivas
        self.periodos_por_ano = periodos_por_ano
        self._periodos: dict[int, str] = {}

    def periodo(self, indice: int) -> str:
        if indice not in self._periodos:
            self._periodos[indice] = somar_periodos(self.periodo_inicial, indice, self.periodos_por_ano)
        return self._periodos[indice]

    def __call__(self, disciplina_id: int, indice: int) -> bool:
        efetiva = self.efetivas.get(disciplina_id)
        valor = efetiva.valor if efetiva else PER_SEMPRE
        return ofertada_em(valor, self.periodo(indice), self.periodos_por_ano)


def periodicidades_efetivas(
    disciplinas: Iterable[Disciplina], estimar: bool = True
) -> dict[int, PeriodicidadeEfetiva]:
    return {d.id: periodicidade_efetiva(d, estimar) for d in disciplinas}


def nos_a_cursar(
    disciplinas: Mapping[int, Disciplina],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    concluidas: Collection[int],
    extras: Iterable[int] = (),
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """
    Devolve `(nos, incluidas_por_requisito)`.

    `nos` = obrigatórias ainda não concluídas (+ `extras`, ex.: optativas que o aluno quer).
    Se um nó exige algo que não é obrigatório (ex.: uma optativa), esse requisito entra
    também (senão o plano seria impossível). Num "B ou C" já satisfeito por algum nó ou
    por algo concluído nada é acrescentado; senão entra a alternativa de MENOR id (determinístico).
    """
    feitas = set(concluidas)
    nos = {
        d.id for d in disciplinas.values()
        if (d.tipo == TIPO_OBRIGATORIA and d.id not in feitas)
    }
    nos |= {i for i in extras if i in disciplinas and i not in feitas}
    incluidas: set[int] = set()

    fila = sorted(nos)
    while fila:
        atual = fila.pop()
        for _tipo, alternativas in agrupar_requisitos(requisitos_por_disciplina.get(atual, ())):
            validas = [a for a in alternativas if a in disciplinas and a != atual]
            if not validas or feitas.intersection(validas) or nos.intersection(validas):
                continue
            escolhida = min(validas)
            nos.add(escolhida)
            incluidas.add(escolhida)
            fila.append(escolhida)
    return tuple(sorted(nos)), tuple(sorted(incluidas))

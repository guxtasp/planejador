"""
Conflitos de horário, calculados POR TURMA.

O legado comparava horários soltos da disciplina (sem turma, sem semestre).
Aqui cada disciplina tem uma turma ESCOLHIDA ou ainda não. Três resultados:

  * CONFLITO              — as duas turmas já estão escolhidas e se sobrepõem;
  * CONFLITO_POSSIVEL     — falta escolher turma e SOMENTE ALGUMAS combinações
                            colidem (dá para evitar escolhendo bem);
  * SEM_TURMA_COMPATIVEL  — falta escolher turma e TODAS as combinações colidem.

Limite conhecido: a análise é par a par. Três disciplinas que só colidem em
conjunto não são detectadas aqui.
Disciplina sem nenhuma turma ofertada não é julgada (oferta desconhecida).
Horários que apenas se tocam (fim == início) não colidem, como no legado.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable

from .entidades import Encontro, Turma

CONFLITO = "conflito"
CONFLITO_POSSIVEL = "conflito_possivel"
SEM_TURMA_COMPATIVEL = "sem_turma_compativel"


@dataclass(frozen=True)
class Selecao:
    """Disciplina no plano: turmas ofertadas e, se já decidida, a escolhida."""

    disciplina_id: int
    turmas_ofertadas: tuple[Turma, ...] = ()
    turma_escolhida_id: int | None = None

    def candidatas(self) -> tuple[Turma, ...]:
        """Turma escolhida (só ela) ou, se nenhuma, todas as ofertadas."""
        if self.turma_escolhida_id is None:
            return self.turmas_ofertadas
        return tuple(t for t in self.turmas_ofertadas if t.id == self.turma_escolhida_id)


@dataclass(frozen=True)
class Sobreposicao:
    """Dois encontros que colidem no mesmo dia."""

    dia: str
    a: Encontro
    b: Encontro


@dataclass(frozen=True)
class Conflito:
    tipo: str
    disciplina_a: int
    disciplina_b: int
    sobreposicoes: tuple[Sobreposicao, ...]  # exemplo de uma combinação que colide


def encontros_se_sobrepoem(a: Encontro, b: Encontro) -> bool:
    """Mesmo dia e intervalos que se cruzam (tocar na borda não conta)."""
    return a.dia == b.dia and a.inicio < b.fim and a.fim > b.inicio


def sobreposicoes_entre_turmas(a: Turma, b: Turma) -> tuple[Sobreposicao, ...]:
    """Todos os pares de encontros que colidem entre duas turmas."""
    return tuple(
        Sobreposicao(x.dia, x, y)
        for x, y in product(a.encontros, b.encontros)
        if encontros_se_sobrepoem(x, y)
    )


def _classificar_par(a: Selecao, b: Selecao) -> Conflito | None:
    cand_a, cand_b = a.candidatas(), b.candidatas()
    if not cand_a or not cand_b:
        return None  # sem oferta (ou turma escolhida inexistente): sem julgamento

    colisoes = [
        (ta, tb, sob)
        for ta, tb in product(cand_a, cand_b)
        if (sob := sobreposicoes_entre_turmas(ta, tb))
    ]
    if not colisoes:
        return None

    todas_colidem = len(colisoes) == len(cand_a) * len(cand_b)
    ambas_escolhidas = (
        a.turma_escolhida_id is not None and b.turma_escolhida_id is not None
    )
    if ambas_escolhidas:
        tipo = CONFLITO
    elif todas_colidem:
        tipo = SEM_TURMA_COMPATIVEL
    else:
        tipo = CONFLITO_POSSIVEL
    return Conflito(tipo, a.disciplina_id, b.disciplina_id, colisoes[0][2])


def detectar_conflitos(selecoes: Iterable[Selecao]) -> tuple[Conflito, ...]:
    """Conflitos entre todos os pares de disciplinas de UM semestre."""
    conflitos = (_classificar_par(a, b) for a, b in combinations(list(selecoes), 2))
    return tuple(c for c in conflitos if c is not None)

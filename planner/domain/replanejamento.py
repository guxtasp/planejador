"""
Replanejamento: o que acontece com o plano quando alguém NÃO passa (ou não pode cursar na data).

`replanejar` executa o plano semestre a semestre, como o aluno viveria:

  * o que não pode ser cursado no semestre (fora da oferta par/ímpar, pré-requisito ainda não
    concluído, créditos acima do limite) é ADIADO para o semestre seguinte;
  * quem reprova ocupa o semestre, não conclui nada e volta para a fila de adiados;
  * os adiados têm prioridade sobre o que estava planejado para o semestre.

Com ele se mede o efeito dominó: reprovar numa disciplina "ímpar" custa DOIS semestres
(só reabre no próximo ano), e tudo que depende dela escorrega junto.

Funções puras, só stdlib. Os semestres são ÍNDICES (0 = primeiro planejado); `oferta(id, indice)`
diz se a disciplina existe naquele índice (ver `restante.CalendarioDeOferta`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Collection, Mapping, Sequence

from .entidades import REQ_CO, Requisito
from .requisitos import agrupar_requisitos

Oferta = Callable[[int, int], bool]

EXTRA_PADRAO = 8   # semestres além do plano em que ainda se tenta encaixar o que foi adiado


@dataclass(frozen=True)
class ResultadoReplano:
    semestres: tuple[tuple[int, ...], ...]   # ids cursados em cada índice (inclui quem reprovou)
    fim: int                                 # índice do último semestre com disciplina; -1 se nenhum
    concluida_em: Mapping[int, int]          # id → índice em que foi concluída
    nao_alocadas: tuple[int, ...]            # não coube no horizonte (ex.: requisito impossível)
    reprovou_em: Mapping[int, int]           # id → índice em que reprovou (só as simuladas)


def _requisitos_ok(
    disciplina_id: int,
    requisitos: Mapping[int, Sequence[Requisito]],
    concluidas: Collection[int],
    no_semestre: Collection[int],
) -> bool:
    for tipo, alternativas in agrupar_requisitos(requisitos.get(disciplina_id, ())):
        base = set(concluidas) | (set(no_semestre) if tipo == REQ_CO else set())
        if not base.intersection(alternativas):
            return False
    return True


def replanejar(
    plano: Sequence[Collection[int]],
    oferta: Oferta,
    requisitos: Mapping[int, Sequence[Requisito]],
    creditos: Mapping[int, int | None],
    limite_creditos: int | None,
    concluidas: Collection[int] = (),
    reprovar: Collection[int] = (),
    extra: int = EXTRA_PADRAO,
) -> ResultadoReplano:
    """
    Executa `plano` (lista de conjuntos de ids por semestre).

    `reprovar`: disciplinas que reprovam na PRIMEIRA vez em que são cursadas.
    """
    feitas = set(concluidas)
    pendentes = {i for s in plano for i in s}
    falhas = set(reprovar) & pendentes
    reprovou_em: dict[int, int] = {}
    concluida_em: dict[int, int] = {}
    adiadas: list[int] = []
    semestres: list[tuple[int, ...]] = []
    fim = -1

    for t in range(len(plano) + max(0, extra)):
        planejadas = sorted(plano[t]) if t < len(plano) else []
        candidatas = [c for c in adiadas if c not in planejadas] + [c for c in planejadas if c not in feitas]
        escolhidas: list[int] = []
        carga = 0
        restantes = list(dict.fromkeys(candidatas))

        mudou = True
        while mudou:    # ponto fixo: um correquisito pode liberar o outro no mesmo semestre
            mudou = False
            for c in list(restantes):
                # correquisito pode estar no mesmo semestre: já escolhido ou candidato ofertado agora
                simultaneas = set(escolhidas) | {r for r in restantes if r != c and oferta(r, t)}
                if not oferta(c, t) or not _requisitos_ok(c, requisitos, feitas, simultaneas):
                    continue
                cred = creditos.get(c) or 0
                if limite_creditos is not None and escolhidas and carga + cred > limite_creditos:
                    continue
                escolhidas.append(c)
                carga += cred
                restantes.remove(c)
                mudou = True

        reprovadas = [c for c in escolhidas if c in falhas]
        for c in reprovadas:
            falhas.discard(c)
            reprovou_em[c] = t
        for c in escolhidas:
            if c not in reprovadas:
                feitas.add(c)
                concluida_em[c] = t
        adiadas = restantes + reprovadas
        semestres.append(tuple(escolhidas))
        if escolhidas:
            fim = t
        if not adiadas and t >= len(plano) - 1:
            break

    return ResultadoReplano(
        tuple(semestres), fim, concluida_em, tuple(sorted(adiadas)), reprovou_em
    )


@dataclass(frozen=True)
class CenarioReprovacao:
    """O que muda se a pessoa reprovar em `disciplina_id` na primeira vez em que a cursar."""

    disciplina_id: int
    atraso: int                       # semestres a mais até concluir tudo (0 = sem efeito no fim)
    novo_fim: int                     # índice do último semestre no cenário
    reoferta: int | None              # índice em que a disciplina é refeita
    espera: int | None                # semestres entre reprovar e refazer
    afetadas: tuple[int, ...]         # outras disciplinas que escorregam de semestre


def cenarios_de_reprovacao(
    plano: Sequence[Collection[int]],
    oferta: Oferta,
    requisitos: Mapping[int, Sequence[Requisito]],
    creditos: Mapping[int, int | None],
    limite_creditos: int | None,
    concluidas: Collection[int] = (),
    extra: int = EXTRA_PADRAO,
) -> tuple[ResultadoReplano, tuple[CenarioReprovacao, ...]]:
    """
    Base (ninguém reprova) e um cenário por disciplina do plano.
    O atraso é comparado com a BASE (que já adia o que não cabe), não com o plano bruto:
    mede o custo da reprovação, não os problemas que o plano já tinha.
    """
    base = replanejar(plano, oferta, requisitos, creditos, limite_creditos, concluidas, (), extra)
    cenarios = []
    for d in sorted({i for s in plano for i in s}):
        r = replanejar(plano, oferta, requisitos, creditos, limite_creditos, concluidas, (d,), extra)
        if d not in r.reprovou_em:      # nunca chegou a ser cursada (plano com problema): sem cenário
            continue
        reoferta = r.concluida_em.get(d)
        afetadas = tuple(sorted(
            x for x, t in r.concluida_em.items()
            if x != d and base.concluida_em.get(x) != t
        ))
        cenarios.append(CenarioReprovacao(
            disciplina_id=d,
            atraso=max(0, r.fim - base.fim) if base.fim >= 0 else 0,
            novo_fim=r.fim,
            reoferta=reoferta,
            espera=None if reoferta is None else reoferta - r.reprovou_em[d],
            afetadas=afetadas,
        ))
    cenarios.sort(key=lambda c: (-c.atraso, -len(c.afetadas), c.disciplina_id))
    return base, tuple(cenarios)


def robustez(cenarios: Sequence[CenarioReprovacao]) -> tuple[float, int]:
    """(atraso médio, pior atraso) entre os cenários de reprovação. Quanto menor, mais robusto."""
    if not cenarios:
        return 0.0, 0
    atrasos = [c.atraso for c in cenarios]
    return sum(atrasos) / len(atrasos), max(atrasos)

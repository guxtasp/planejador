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


Limite = int | None | Callable[[int], "int | None"]   # teto fixo ou por índice de semestre (0 = trancado)


def _requisitos_ok(
    disciplina_id: int,
    requisitos: Mapping[int, Sequence[Requisito]],
    concluidas: Collection[int],
    no_semestre: Collection[int],
    grupos: dict | None = None,
) -> bool:
    if grupos is not None:
        termos = grupos.get(disciplina_id)
        if termos is None:
            termos = grupos[disciplina_id] = agrupar_requisitos(requisitos.get(disciplina_id, ()))
    else:
        termos = agrupar_requisitos(requisitos.get(disciplina_id, ()))
    for tipo, alternativas in termos:
        if any(a in concluidas or (tipo == REQ_CO and a in no_semestre) for a in alternativas):
            continue
        return False
    return True


def replanejar(
    plano: Sequence[Collection[int]],
    oferta: Oferta,
    requisitos: Mapping[int, Sequence[Requisito]],
    creditos: Mapping[int, int | None],
    limite_creditos: Limite,
    concluidas: Collection[int] = (),
    reprovar: Collection[int] = (),
    extra: int = EXTRA_PADRAO,
    reprova: Callable[[int, int], bool] | None = None,
    max_pesadas: int | None = None,
    pesadas: Collection[int] = (),
    grupos: dict | None = None,
    juntas: Sequence[Collection[int]] = (),
) -> ResultadoReplano:
    """
    Executa `plano` (lista de conjuntos de ids por semestre).

    `reprovar`: disciplinas que reprovam na PRIMEIRA vez em que são cursadas.
    `reprova(id, indice)`: sorteio de reprovação a cada tentativa (Monte Carlo; pode reprovar de novo).
    `limite_creditos`: teto fixo ou função do índice (teto específico; 0 = período trancado).
    `max_pesadas`/`pesadas`: no máximo N disciplinas "pesadas" por semestre (as demais esperam).
    `grupos`: cache de requisitos agrupados, para quem chama muitas vezes.
    `juntas`: grupos "cursar junto" OBRIGATÓRIOS: só entram no semestre se TODOS os membros pendentes
    entram; e reprovar em um adia o grupo junto (os outros também voltam para a fila, sem contar
    como reprovação deles).
    """
    juntas = [set(g) for g in juntas]
    limite_de = limite_creditos if callable(limite_creditos) else (lambda _t: limite_creditos)
    pesadas = set(pesadas)
    if grupos is None:
        grupos = {}
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
        n_pesadas = 0
        restantes = list(dict.fromkeys(candidatas))
        limite = limite_de(t)

        mudou = limite != 0          # período trancado: nada é cursado, tudo espera
        while mudou:    # ponto fixo: um correquisito pode liberar o outro no mesmo semestre
            mudou = False
            for c in list(restantes):
                # correquisito pode estar no mesmo semestre: já escolhido ou candidato ofertado agora
                simultaneas = set(escolhidas) | {r for r in restantes if r != c and oferta(r, t)}
                if not oferta(c, t) or not _requisitos_ok(c, requisitos, feitas, simultaneas, grupos):
                    continue
                cred = creditos.get(c) or 0
                if limite is not None and escolhidas and carga + cred > limite:
                    continue
                if max_pesadas is not None and c in pesadas and n_pesadas >= max_pesadas:
                    continue
                escolhidas.append(c)
                carga += cred
                n_pesadas += c in pesadas
                restantes.remove(c)
                mudou = True

        for g in juntas:            # tudo ou nada: membro sem o grupo completo espera
            pendentes = g - feitas
            no_sem = pendentes.intersection(escolhidas)
            if no_sem and no_sem != pendentes:
                for c in no_sem:
                    escolhidas.remove(c)
                    restantes.append(c)
        reprovadas = [c for c in escolhidas if c in falhas or (reprova is not None and reprova(c, t))]
        arrastadas = [c for g in juntas if g.intersection(reprovadas) for c in g
                      if c in escolhidas and c not in reprovadas]
        for c in reprovadas:
            falhas.discard(c)
            reprovou_em.setdefault(c, t)
        for c in escolhidas:
            if c not in reprovadas and c not in arrastadas:
                feitas.add(c)
                concluida_em[c] = t
        adiadas = restantes + reprovadas + arrastadas
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
    limite_creditos: Limite,
    concluidas: Collection[int] = (),
    extra: int = EXTRA_PADRAO,
    max_pesadas: int | None = None,
    pesadas: Collection[int] = (),
    juntas: Sequence[Collection[int]] = (),
) -> tuple[ResultadoReplano, tuple[CenarioReprovacao, ...]]:
    """
    Base (ninguém reprova) e um cenário por disciplina do plano.
    O atraso é comparado com a BASE (que já adia o que não cabe), não com o plano bruto:
    mede o custo da reprovação, não os problemas que o plano já tinha.
    """
    grupos: dict = {}
    kw = dict(max_pesadas=max_pesadas, pesadas=pesadas, grupos=grupos, juntas=juntas)
    base = replanejar(plano, oferta, requisitos, creditos, limite_creditos, concluidas, (), extra, **kw)
    cenarios = []
    for d in sorted({i for s in plano for i in s}):
        r = replanejar(plano, oferta, requisitos, creditos, limite_creditos, concluidas, (d,), extra, **kw)
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

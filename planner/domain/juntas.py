"""
Disciplinas que andam JUNTAS (ex.: TCC + Seminário): cursadas no mesmo semestre por escolha do aluno,
mesmo sem correquisito no catálogo.

  * `candidatas_a_juntas`  pares que PARECEM andar juntos — só para perguntar ao aluno, nunca regra
                           automática: nomes de fim de curso (TCC, Trabalho de Conclusão, Monografia,
                           Seminário, Projeto Final, Estágio) no mesmo período sugerido (ou sem período),
                           ou correquisito mútuo no catálogo;
  * `problemas_do_grupo`   por que um grupo é impossível: ofertas sem período em comum (só ímpar × só par)
                           ou uma exige a outra como pré-requisito (direta ou indiretamente). O grupo
                           impossível é ignorado (avisado), sem bloquear o resto.

Função pura, só stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Mapping, Sequence

from .entidades import PER_IMPAR, PER_PAR, REQ_CO, REQ_PRE, Disciplina, Requisito
from .periodicidade import periodicidade_efetiva
from .preferencias import GrupoJunto

MOTIVO_NOMES = "nomes"                   # nomes de fim de curso no mesmo período sugerido
MOTIVO_CORREQUISITO = "correquisito"     # uma é correquisito da outra e vice-versa

PROBLEMA_OFERTA = "ofertas_incompativeis"
PROBLEMA_PRE = "pre_requisito_entre_elas"

# famílias de nome (texto normalizado: sem acento, minúsculo)
_CONCLUSAO = re.compile(r"\b(tcc|trabalho de conclusao|monografia|projeto final|projeto de conclusao)\b")
_SEMINARIO = re.compile(r"\bseminario")
_ESTAGIO = re.compile(r"\bestagio\b")


def _norm(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower().split())


def _familia(d: Disciplina) -> str | None:
    n = _norm(d.nome) + " " + _norm(d.codigo)
    if _CONCLUSAO.search(n):
        return "conclusao"
    if _SEMINARIO.search(n):
        return "seminario"
    if _ESTAGIO.search(n):
        return "estagio"
    return None


@dataclass(frozen=True)
class CandidatoJunto:
    disciplinas: tuple[int, ...]
    motivo: str


def _exige(requisitos: Mapping[int, Sequence[Requisito]], a: int, b: int, tipo: str) -> bool:
    return any(r.requisito_id == b and r.tipo == tipo for r in requisitos.get(a, ()))


def _exige_pre_transitivo(requisitos: Mapping[int, Sequence[Requisito]], a: int, b: int) -> bool:
    """a exige b como pré-requisito, direta ou indiretamente (qualquer alternativa conta)."""
    pilha, visto = [a], set()
    while pilha:
        x = pilha.pop()
        for r in requisitos.get(x, ()):
            if r.tipo != REQ_PRE:
                continue
            if r.requisito_id == b:
                return True
            if r.requisito_id not in visto:
                visto.add(r.requisito_id)
                pilha.append(r.requisito_id)
    return False


def candidatas_a_juntas(
    disciplinas: Iterable[Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
    excluir: Iterable[int] = (),
) -> tuple[CandidatoJunto, ...]:
    """Pares sugeridos (nunca aplicados sozinhos). `excluir` = já concluídas/cursando."""
    fora = set(excluir)
    lista = [d for d in disciplinas if d.id not in fora]
    saida: list[CandidatoJunto] = []
    for a, b in combinations(sorted(lista, key=lambda d: d.id), 2):
        if _exige_pre_transitivo(requisitos, a.id, b.id) or _exige_pre_transitivo(requisitos, b.id, a.id):
            continue          # uma vem antes da outra: nunca juntas (ex.: Estágio I → Estágio II)
        if _exige(requisitos, a.id, b.id, REQ_CO) and _exige(requisitos, b.id, a.id, REQ_CO):
            saida.append(CandidatoJunto((a.id, b.id), MOTIVO_CORREQUISITO))
            continue
        fa, fb = _familia(a), _familia(b)
        mesmo_periodo = a.periodo_sugerido is None or b.periodo_sugerido is None or a.periodo_sugerido == b.periodo_sugerido
        if not (fa and fb and mesmo_periodo):
            continue
        # duas da mesma família: TCC I e TCC II costumam ser sequenciais (não juntas), mas "TCC I" e
        # "Elaboração de TCC" no MESMO período sugerido andam juntas (pré-requisito entre elas já foi excluído)
        if fa == fb and fa != "estagio" and not (a.periodo_sugerido is not None and a.periodo_sugerido == b.periodo_sugerido):
            continue
        saida.append(CandidatoJunto((a.id, b.id), MOTIVO_NOMES))
    return tuple(saida)


@dataclass(frozen=True)
class ProblemaGrupo:
    tipo: str                         # ofertas_incompativeis | pre_requisito_entre_elas
    disciplinas: tuple[int, ...]      # o par que causa o problema


def problemas_do_grupo(
    grupo: GrupoJunto,
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
) -> tuple[ProblemaGrupo, ...]:
    """Vazio = o grupo é possível. A oferta usada é a efetiva (cadastrada ou estimada)."""
    ids = [i for i in grupo.disciplinas if i in disciplinas]
    saida = []
    ofertas = {i: periodicidade_efetiva(disciplinas[i]).valor for i in ids}
    for a, b in combinations(ids, 2):
        if {ofertas[a], ofertas[b]} == {PER_IMPAR, PER_PAR}:
            saida.append(ProblemaGrupo(PROBLEMA_OFERTA, (a, b)))
        if _exige_pre_transitivo(requisitos, a, b):
            saida.append(ProblemaGrupo(PROBLEMA_PRE, (a, b)))
        elif _exige_pre_transitivo(requisitos, b, a):
            saida.append(ProblemaGrupo(PROBLEMA_PRE, (b, a)))
    return tuple(saida)


def grupos_validos(
    grupos: Iterable[GrupoJunto],
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
) -> tuple[GrupoJunto, ...]:
    """Só os grupos possíveis (os impossíveis são avisados por quem chama, não aplicados)."""
    return tuple(g for g in grupos if not problemas_do_grupo(g, disciplinas, requisitos))

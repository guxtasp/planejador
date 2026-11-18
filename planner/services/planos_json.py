"""
Formato JSON dos planos do aluno (Etapa 5B-2): valida o corpo da requisição,
confere as referências ao catálogo e serializa. Sem SQLAlchemy/Flask — testável
sem banco.

Forma de um plano (a mesma na ida e na volta):
  {"nome": "...", "semestres": [{"rotulo": "...", "periodo_letivo": "2026/1"|null,
                                  "itens": [{"disciplina_id": 1, "turma_id": 3|null,
                                             "encontros_livres": [{"dia","inicio","fim"}]  (opcional)}]}]}
`encontros_livres` = horários definidos pelo aluno, para quando o curso não tem quadro
importado; excluem `turma_id` (um ou outro).
A ordem dos semestres é a ordem da lista. Ids de semestre não existem no contrato:
o cliente edita o plano inteiro e o servidor o guarda inteiro.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..api.errors import AppError
from ..domain.previsao import normalizar_periodo
from ..domain.entidades import Encontro
from .analise_json import (MAX_ITENS_POR_SEMESTRE, MAX_SEMESTRES, encontros_para_json,
                           ler_encontros_livres)

MAX_NOME = 200
MAX_ROTULO = 50


@dataclass(frozen=True)
class ItemEntrada:
    disciplina_id: int
    turma_id: int | None
    encontros_livres: tuple[Encontro, ...] = ()


@dataclass(frozen=True)
class SemestreEntrada:
    rotulo: str
    periodo_letivo: str | None
    itens: tuple[ItemEntrada, ...]


@dataclass(frozen=True)
class PlanoEntrada:
    nome: str
    semestres: tuple[SemestreEntrada, ...]


def _inteiro(valor, onde: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise AppError(f"{onde} deve ser um número inteiro.")
    return valor


def ler_plano(payload) -> PlanoEntrada:
    """Valida só o FORMATO e os limites; as referências ao catálogo vêm em `validar_referencias`."""
    if not isinstance(payload, dict):
        raise AppError("Envie o plano em JSON.")
    nome = payload.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        raise AppError("Informe o nome do plano.")
    nome = nome.strip()
    if len(nome) > MAX_NOME:
        raise AppError(f"O nome do plano pode ter no máximo {MAX_NOME} caracteres.")

    brutos = payload.get("semestres", [])
    if not isinstance(brutos, list):
        raise AppError("`semestres` deve ser uma lista.")
    if len(brutos) > MAX_SEMESTRES:
        raise AppError(f"No máximo {MAX_SEMESTRES} semestres por plano.")

    semestres = []
    for i, s in enumerate(brutos, start=1):
        if not isinstance(s, dict) or not isinstance(s.get("itens", []), list):
            raise AppError(f"Semestre {i}: formato inválido.")
        rotulo = s.get("rotulo")
        if rotulo is not None and not isinstance(rotulo, str):
            raise AppError(f"Semestre {i}: rótulo inválido.")
        rotulo = (rotulo or "").strip() or f"Semestre {i}"
        if len(rotulo) > MAX_ROTULO:
            raise AppError(f"Semestre {i}: o rótulo pode ter no máximo {MAX_ROTULO} caracteres.")

        periodo = s.get("periodo_letivo")
        if periodo is not None and not isinstance(periodo, str):
            raise AppError(f"Semestre {i}: período letivo inválido.")
        periodo = (periodo or "").strip() or None
        if periodo is not None:
            periodo = normalizar_periodo(periodo)
            if periodo is None:
                raise AppError(f"Semestre {i}: período letivo inválido. Use AAAA/N, por exemplo 2026/1.")

        itens_brutos = s.get("itens", [])
        if len(itens_brutos) > MAX_ITENS_POR_SEMESTRE:
            raise AppError(f"Semestre {i}: no máximo {MAX_ITENS_POR_SEMESTRE} disciplinas.")
        itens = []
        for item in itens_brutos:
            if not isinstance(item, dict):
                raise AppError(f"Semestre {i}: formato de disciplina inválido.")
            turma = item.get("turma_id")
            itens.append(ItemEntrada(
                _inteiro(item.get("disciplina_id"), f"Semestre {i}: disciplina_id"),
                None if turma is None else _inteiro(turma, f"Semestre {i}: turma_id"),
                ler_encontros_livres(item.get("encontros_livres"), f"Semestre {i}"),
            ))
        semestres.append(SemestreEntrada(rotulo, periodo, tuple(itens)))
    return PlanoEntrada(nome, tuple(semestres))


def validar_referencias(
    plano: PlanoEntrada,
    disciplinas_do_curso: set[int],
    turmas_do_curso: Mapping[int, tuple[int, str]],
) -> None:
    """
    Garante que o plano só aponta para o que existe NESTE curso.

    `turmas_do_curso`: `{turma_id: (disciplina_id, periodo_letivo)}`. Regras (as que o
    banco não garante, ver docstring de `PlanoItem`): a disciplina é do curso; aparece
    uma única vez no plano; a turma é DAQUELA disciplina e do período do semestre.
    """
    vistas: set[int] = set()
    for i, semestre in enumerate(plano.semestres, start=1):
        for item in semestre.itens:
            onde = f"Semestre {i}"
            if item.disciplina_id not in disciplinas_do_curso:
                raise AppError(f"{onde}: há uma disciplina que não pertence a este curso.", 422)
            if item.disciplina_id in vistas:
                raise AppError(f"{onde}: uma disciplina aparece mais de uma vez no plano.", 422)
            vistas.add(item.disciplina_id)
            if item.turma_id is not None and item.encontros_livres:
                raise AppError(f"{onde}: uma disciplina usa a turma OU horários próprios, não os dois.", 422)
            if item.turma_id is None:
                continue
            turma = turmas_do_curso.get(item.turma_id)
            if turma is None or turma[0] != item.disciplina_id:
                raise AppError(f"{onde}: há uma turma que não pertence à disciplina escolhida.", 422)
            if semestre.periodo_letivo is None:
                raise AppError(f"{onde}: escolha o período letivo antes de escolher a turma.", 422)
            if turma[1] != semestre.periodo_letivo:
                raise AppError(f"{onde}: há uma turma de outro período letivo.", 422)


def _item_json(i) -> dict:
    base = {"disciplina_id": i.disciplina_id, "turma_id": i.turma_id}
    if getattr(i, "encontros_livres", None):   # só aparece quando existe: contrato anterior intacto
        base["encontros_livres"] = list(i.encontros_livres)
    return base


def serializar_plano(plano) -> dict:
    """`plano` é um `Plano` com semestres, itens e disciplinas carregados."""
    return {
        "id": plano.id,
        "nome": plano.nome,
        "semestres": [
            {
                "rotulo": s.label,
                "periodo_letivo": s.periodo_letivo,
                # Ordem estável (o banco não guarda a ordem dos itens dentro do semestre).
                "itens": [
                    _item_json(i)
                    for i in sorted(s.itens, key=lambda i: (i.disciplina.codigo, i.disciplina_id))
                ],
            }
            for s in sorted(plano.semestres, key=lambda s: s.ordem)
        ],
    }

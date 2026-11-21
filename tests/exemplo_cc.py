"""
Exemplo de Ciência da Computação (`examples/ciencia-da-computacao`) carregado direto nas estruturas do
domínio, sem banco: base dos testes de desempenho e da medição do otimizador (`tools/medir_otimizador.py`).

Lê os CSVs com o módulo `csv` e os horários com o mesmo parser da importação. Ids são sequenciais
pela ordem dos arquivos (determinístico).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from planner.domain.entidades import Disciplina, Requisito, Turma
from planner.importers.horarios import parse_horarios

PASTA = Path(__file__).resolve().parent.parent / "examples" / "ciencia-da-computacao"


@dataclass(frozen=True)
class ExemploCC:
    disciplinas: dict[int, Disciplina]
    requisitos: dict[int, list[Requisito]]
    turmas: dict[int, list[Turma]]
    id_de: dict[str, int]                 # código → id


def _linhas(nome: str) -> list[dict[str, str]]:
    with open(PASTA / nome, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _int(texto: str) -> int | None:
    return int(texto) if texto.strip() else None


def carregar() -> ExemploCC:
    disciplinas: dict[int, Disciplina] = {}
    id_de: dict[str, int] = {}
    for i, r in enumerate(_linhas("disciplinas.csv"), start=1):
        id_de[r["codigo"]] = i
        disciplinas[i] = Disciplina(i, r["codigo"], r["nome"], _int(r["creditos"]), r["tipo"],
                                    _int(r["periodo_sugerido"]), r.get("periodicidade") or None)
    requisitos: dict[int, list[Requisito]] = {i: [] for i in disciplinas}
    for r in _linhas("requisitos.csv"):
        d, q = id_de[r["disciplina"]], id_de[r["requisito"]]
        requisitos[d].append(Requisito(d, q, r["tipo"], r.get("grupo_alt") or None))
    turmas: dict[int, list[Turma]] = {}
    for k, r in enumerate(_linhas("turmas.csv"), start=1):
        d = id_de[r["disciplina"]]
        encontros, _erros = parse_horarios(r["horarios"])
        turmas.setdefault(d, []).append(Turma(k, d, encontros, r["periodo_letivo"], r["codigo_turma"]))
    return ExemploCC(disciplinas, requisitos, turmas, id_de)

"""
Registros produzidos pelos importadores: uma linha de CSV já validada e tipada.

São Value Objects imutáveis, sem relação com o banco. A etapa 3B os cruza entre
si (referências, duplicatas) e a 3C os grava. `linha` permite apontar o erro
exato mais adiante, mesmo depois da leitura.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..domain.entidades import Encontro


@dataclass(frozen=True)
class CursoCsv:
    linha: int
    nome: str
    instituicao: str | None = None
    versao_matriz: str | None = None
    creditos_obrigatorios: int | None = None
    creditos_optativos_exigidos: int | None = None
    ch_total: int | None = None
    max_creditos_semestre: int | None = None
    duracao_semestres: int | None = None
    dias_letivos: tuple[str, ...] | None = None


@dataclass(frozen=True)
class DisciplinaCsv:
    linha: int
    codigo: str
    nome: str
    tipo: str
    creditos: int | None = None
    carga_h: int | None = None
    periodo_sugerido: int | None = None
    cor: str | None = None
    periodicidade: str | None = None   # sempre | impar | par


@dataclass(frozen=True)
class RequisitoCsv:
    linha: int
    disciplina: str   # código da disciplina que EXIGE
    requisito: str    # código da disciplina exigida
    tipo: str         # "pre" | "co"
    grupo_alt: str | None = None


@dataclass(frozen=True)
class TurmaCsv:
    linha: int
    disciplina: str
    periodo_letivo: str
    codigo_turma: str
    docente: str | None = None
    vagas: int | None = None
    encontros: tuple[Encontro, ...] = ()
    local: str | None = None  # sala; vale para todos os encontros da turma

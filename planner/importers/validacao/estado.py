"""
`EstadoExistente`: retrato (somente leitura) do que já está gravado no curso.

A validação precisa saber o que já existe para (a) resolver referências a
disciplinas que não estão no CSV enviado e (b) dizer, na prévia, o que é novo,
o que muda e o que fica igual. Estes Value Objects são dados simples: quem os
monta a partir do banco é o serviço (`services/previa_importacao.py`), de modo
que `importers/` continua sem importar SQLAlchemy, Flask ou repositories.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.entidades import Encontro


@dataclass(frozen=True)
class CursoExistente:
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
class DisciplinaExistente:
    codigo: str
    nome: str
    tipo: str
    creditos: int | None = None
    carga_h: int | None = None
    periodo_sugerido: int | None = None
    cor: str | None = None
    periodicidade: str | None = None


@dataclass(frozen=True)
class RequisitoExistente:
    disciplina: str   # código de quem exige
    requisito: str    # código de quem é exigido
    tipo: str
    grupo_alt: str | None = None


@dataclass(frozen=True)
class TurmaExistente:
    disciplina: str
    periodo_letivo: str
    codigo_turma: str
    docente: str | None = None
    vagas: int | None = None
    encontros: tuple[Encontro, ...] = ()
    local: str | None = None
    componente: str | None = None


@dataclass(frozen=True)
class EstadoExistente:
    """Tudo que o curso alvo já tem. O padrão (tudo vazio) representa um curso novo."""

    curso: CursoExistente | None = None
    disciplinas: tuple[DisciplinaExistente, ...] = ()
    requisitos: tuple[RequisitoExistente, ...] = ()
    turmas: tuple[TurmaExistente, ...] = ()

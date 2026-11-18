"""
Vocabulários fechados do domínio (tipos de disciplina, dias, status…).

Os valores são gravados como TEXTO no banco, protegidos por `CHECK`. Preferimos
isso ao tipo ENUM nativo porque funciona igual em SQLite (dev) e Postgres (prod)
e porque acrescentar um valor novo é uma simples migração de CHECK, sem
`ALTER TYPE`.
"""
from enum import Enum

from sqlalchemy import CheckConstraint


class TipoDisciplina(str, Enum):
    OBRIGATORIA = "obrigatoria"
    OPTATIVA = "optativa"
    ELETIVA = "eletiva"


class TipoRequisito(str, Enum):
    PRE = "pre"  # precisa ter sido cursado ANTES
    CO = "co"    # pode ser cursado NO MESMO semestre


class DiaSemana(str, Enum):
    SEG = "SEG"
    TER = "TER"
    QUA = "QUA"
    QUI = "QUI"
    SEX = "SEX"
    SAB = "SAB"
    DOM = "DOM"


class Visibilidade(str, Enum):
    PRIVADO = "privado"  # padrão: só o dono enxerga o curso
    PUBLICO = "publico"


class StatusHistorico(str, Enum):
    # Mesmos valores do app original (legacy). Novos status entram na Etapa 2,
    # se o motor de regras precisar (ex.: trancado, dispensado).
    APROVADO = "aprovado"
    REPROVADO = "reprovado"
    CURSANDO = "cursando"


def check_enum(coluna: str, enum: type[Enum], nome: str) -> CheckConstraint:
    """
    Gera `CHECK (coluna IN ('a','b',…))` a partir de um Enum.

    `nome` é obrigatório: a convenção de nomes do banco (ver `extensions.py`)
    precisa dele para que o Alembic consiga alterar/remover a constraint depois.
    """
    valores = ", ".join(f"'{membro.value}'" for membro in enum)
    return CheckConstraint(f"{coluna} IN ({valores})", name=nome)

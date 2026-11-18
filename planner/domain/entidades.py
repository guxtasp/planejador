"""
Value Objects do domínio: dados imutáveis que o motor de regras recebe.

Nada aqui conhece SQLAlchemy ou Flask. Quem chama (os serviços) converte os
modelos do banco nestas estruturas; assim as regras são testáveis sem banco.

Os vocabulários (`"pre"`, `"aprovado"`…) repetem os valores gravados no banco
(`planner/models/enums.py`) como texto simples, para o domínio não importar
a camada de persistência.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal

# ── vocabulários (mesmos valores de planner/models/enums.py) ───────────────
TIPO_OBRIGATORIA = "obrigatoria"
TIPO_OPTATIVA = "optativa"
TIPO_ELETIVA = "eletiva"

REQ_PRE = "pre"  # precisa ter sido CONCLUÍDO antes
REQ_CO = "co"    # pode ser cursado no MESMO semestre

STATUS_APROVADO = "aprovado"
STATUS_REPROVADO = "reprovado"
STATUS_CURSANDO = "cursando"
STATUS_VALIDOS = (STATUS_APROVADO, STATUS_REPROVADO, STATUS_CURSANDO)


@dataclass(frozen=True)
class Disciplina:
    """Disciplina do catálogo. `creditos=None` significa DESCONHECIDO, não zero."""

    id: int
    codigo: str
    nome: str
    creditos: int | None = None
    tipo: str = TIPO_OBRIGATORIA
    periodo_sugerido: int | None = None


@dataclass(frozen=True)
class Requisito:
    """
    "`disciplina_id` exige `requisito_id`".

    `grupo_alt` vazio = obrigatório (AND). Requisitos do MESMO tipo e do mesmo
    `grupo_alt` são alternativas entre si (OR).
    """

    disciplina_id: int
    requisito_id: int
    tipo: str = REQ_PRE
    grupo_alt: str | None = None


@dataclass(frozen=True)
class Tentativa:
    """Uma tentativa no histórico. Uma disciplina pode ter várias (N tentativas)."""

    disciplina_id: int
    status: str
    periodo_letivo: str | None = None
    nota: Decimal | None = None


@dataclass(frozen=True)
class Encontro:
    """Um horário semanal (ex.: SEG 16:00–18:00)."""

    dia: str
    inicio: time
    fim: time


@dataclass(frozen=True)
class Turma:
    """Alternativa de matrícula; TODOS os seus encontros são obrigatórios."""

    id: int
    disciplina_id: int
    encontros: tuple[Encontro, ...] = ()
    periodo_letivo: str | None = None
    codigo_turma: str | None = None

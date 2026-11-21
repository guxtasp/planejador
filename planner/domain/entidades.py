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

PER_SEMPRE = "sempre"  # oferecida em todo período letivo
PER_IMPAR = "impar"    # só nos períodos ímpares ("AAAA/1", "AAAA/3"…)
PER_PAR = "par"        # só nos períodos pares ("AAAA/2"…)
PERIODICIDADES = (PER_SEMPRE, PER_IMPAR, PER_PAR)

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
    # "sempre" | "impar" | "par"; None = oferta desconhecida (ver `domain.periodicidade`).
    periodicidade: str | None = None
    # False = os créditos contam para formar, mas NÃO para o limite de créditos do semestre
    # (ex.: estágio/TCC de 10 créditos com 2 h de aula, em cursos que não os somam na matrícula).
    conta_no_limite: bool = True

    @property
    def creditos_no_limite(self) -> int:
        """O que a disciplina ocupa do limite de créditos do semestre (desconhecido = 0)."""
        return (self.creditos or 0) if self.conta_no_limite else 0


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

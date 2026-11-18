"""
Calendário de oferta: em quais períodos letivos uma disciplina pode ser cursada.

Regras puras (só stdlib), usadas pelo simulador e pelo otimizador.

  * Paridade = paridade do NÚMERO do período no ano: "2026/1" é ímpar, "2026/2" é par.
    Disciplina `impar` só existe em "AAAA/1"; `par`, só em "AAAA/2"; `sempre`, em todos.
  * `periodicidade=None` é DESCONHECIDO. Nunca vira "sempre" em silêncio:
    `periodicidade_efetiva` devolve também a ORIGEM do valor (cadastrada, estimada
    ou desconhecida) para a tela poder avisar.
  * A estimativa (opcional) usa a paridade do período sugerido na matriz: quem é
    sugerida no 3º período costuma ser ofertada nos semestres ímpares.
  * Horários de períodos futuros não existem ainda. `turmas_para_periodo` PROJETA os do
    último período de mesma paridade (e diz que é projeção): é a melhor aposta, não um fato.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .entidades import PER_IMPAR, PER_PAR, PER_SEMPRE, Disciplina, Turma
from .previsao import normalizar_periodo, somar_periodos

ORIGEM_CADASTRADA = "cadastrada"
ORIGEM_ESTIMADA = "estimada"
ORIGEM_DESCONHECIDA = "desconhecida"

HORARIO_REAL = "real"              # a turma é do próprio período
HORARIO_PROJETADO = "projetado"    # copiado do último período de mesma paridade
HORARIO_DESCONHECIDO = "desconhecido"


def numero_do_periodo(periodo: str, periodos_por_ano: int = 2) -> int:
    """'2026/2' → 2. ValueError se o período for inválido."""
    normal = normalizar_periodo(periodo, periodos_por_ano)
    if normal is None:
        raise ValueError(f"periodo_letivo inválido: {periodo!r}")
    return int(normal.split("/")[1])


def paridade_do_periodo(periodo: str, periodos_por_ano: int = 2) -> str:
    """'impar' ou 'par' (nunca 'sempre')."""
    return PER_IMPAR if numero_do_periodo(periodo, periodos_por_ano) % 2 == 1 else PER_PAR


def ofertada_em(periodicidade: str | None, periodo: str, periodos_por_ano: int = 2) -> bool:
    """Pode ser cursada neste período? Desconhecida (None) não bloqueia."""
    if periodicidade in (None, PER_SEMPRE):
        return True
    return periodicidade == paridade_do_periodo(periodo, periodos_por_ano)


def proximo_periodo_ofertado(
    periodicidade: str | None, a_partir_de: str, periodos_por_ano: int = 2
) -> str:
    """Primeiro período ≥ `a_partir_de` em que a disciplina é ofertada."""
    periodo = a_partir_de
    for _ in range(max(2, periodos_por_ano) + 1):
        if ofertada_em(periodicidade, periodo, periodos_por_ano):
            return periodo
        periodo = somar_periodos(periodo, 1, periodos_por_ano)
    return periodo   # periodicidade inalcançável com `periodos_por_ano` atípico


@dataclass(frozen=True)
class PeriodicidadeEfetiva:
    valor: str          # PER_SEMPRE | PER_IMPAR | PER_PAR (o que o motor usa)
    origem: str         # ORIGEM_*


def periodicidade_efetiva(d: Disciplina, estimar: bool = True) -> PeriodicidadeEfetiva:
    """
    O que o motor deve assumir para `d`. Cadastrada vale sempre. Sem cadastro:
    com `estimar`, a paridade do período sugerido; sem período sugerido (ou sem
    `estimar`), "sempre" marcado como DESCONHECIDA.
    """
    if d.periodicidade is not None:
        return PeriodicidadeEfetiva(d.periodicidade, ORIGEM_CADASTRADA)
    if estimar and d.periodo_sugerido is not None:
        valor = PER_IMPAR if d.periodo_sugerido % 2 == 1 else PER_PAR
        return PeriodicidadeEfetiva(valor, ORIGEM_ESTIMADA)
    return PeriodicidadeEfetiva(PER_SEMPRE, ORIGEM_DESCONHECIDA)


def turmas_para_periodo(
    turmas: Sequence[Turma], periodo: str, periodos_por_ano: int = 2, projetar: bool = True
) -> tuple[tuple[Turma, ...], str]:
    """
    Turmas candidatas de UMA disciplina em `periodo`, e de onde vieram.

    Real: há turmas do próprio período. Senão, com `projetar`, usa as do período
    mais recente de MESMA paridade (o quadro costuma se repetir de ano em ano);
    preferindo um período anterior ao pedido, mas aceitando um posterior se for o único.
    """
    alvo = normalizar_periodo(periodo, periodos_por_ano)
    reais = tuple(t for t in turmas if normalizar_periodo(t.periodo_letivo, periodos_por_ano) == alvo)
    if reais:
        return reais, HORARIO_REAL
    if not projetar or alvo is None:
        return (), HORARIO_DESCONHECIDO
    n = int(alvo.split("/")[1])
    por_periodo: dict[str, list[Turma]] = {}
    for t in turmas:
        p = normalizar_periodo(t.periodo_letivo, periodos_por_ano)
        if p and int(p.split("/")[1]) == n:
            por_periodo.setdefault(p, []).append(t)
    if not por_periodo:
        return (), HORARIO_DESCONHECIDO
    anteriores = [p for p in por_periodo if p < alvo]
    escolhido = max(anteriores) if anteriores else min(por_periodo)
    return tuple(por_periodo[escolhido]), HORARIO_PROJETADO


def periodos_a_partir_de(inicio: str, quantidade: int, periodos_por_ano: int = 2) -> list[str]:
    """['2027/1', '2027/2', …] com `quantidade` períodos consecutivos."""
    return [somar_periodos(inicio, i, periodos_por_ano) for i in range(quantidade)]


def contar_por_origem(origens: Iterable[str]) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for o in origens:
        contagem[o] = contagem.get(o, 0) + 1
    return contagem

"""
"Vou formar no prazo?" — compara a formatura com a duração do curso.

  * prazo REGULAR  = `duracao_semestres` do curso;
  * prazo MÁXIMO   = duração × fator de integralização (padrão 1,5×, arredondado para cima).

Semestres usados = períodos do ingresso até a formatura, inclusive, menos os trancados
(trancamento, em regra, não conta no prazo de integralização — e a tela diz isso).

Se o curso não informa a duração, ou não se sabe o ingresso ou a formatura, NADA é afirmado
(campos `None`): vazio = desconhecido. Função pura, só stdlib.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Collection

from .previsao import normalizar_periodo

FATOR_PADRAO = 1.5


@dataclass(frozen=True)
class AvaliacaoPrazo:
    semestres_usados: int | None
    regular: int | None                # duração do curso
    maximo: int | None                 # duração × fator
    no_prazo_regular: bool | None      # None = sem base para afirmar
    no_prazo_maximo: bool | None
    trancados: int = 0


def indice_absoluto(periodo: str, periodos_por_ano: int = 2) -> int:
    """'2027/2' → 2027 × 2 + 1: períodos consecutivos têm índices consecutivos."""
    normal = normalizar_periodo(periodo, periodos_por_ano)
    if normal is None:
        raise ValueError(f"periodo_letivo inválido: {periodo!r}")
    ano, n = normal.split("/")
    return int(ano) * periodos_por_ano + int(n) - 1


def semestres_entre(inicio: str, fim: str, periodos_por_ano: int = 2) -> int:
    """Quantos períodos de `inicio` a `fim`, inclusive (0 se fim < início)."""
    return max(0, indice_absoluto(fim, periodos_por_ano) - indice_absoluto(inicio, periodos_por_ano) + 1)


def avaliar_prazo(
    ingresso: str | None,
    formatura: str | None,
    duracao_semestres: int | None,
    fator: float = FATOR_PADRAO,
    pulados: Collection[str] = (),
    periodos_por_ano: int = 2,
) -> AvaliacaoPrazo:
    if not ingresso or not formatura:
        return AvaliacaoPrazo(None, duracao_semestres, None, None, None)
    trancados = sum(1 for p in set(pulados)
                    if indice_absoluto(ingresso, periodos_por_ano) <= indice_absoluto(p, periodos_por_ano)
                    <= indice_absoluto(formatura, periodos_por_ano))
    usados = semestres_entre(ingresso, formatura, periodos_por_ano) - trancados
    if not duracao_semestres:
        return AvaliacaoPrazo(usados, None, None, None, None, trancados)
    maximo = math.ceil(duracao_semestres * fator)
    return AvaliacaoPrazo(usados, duracao_semestres, maximo, usados <= duracao_semestres, usados <= maximo, trancados)


ORIGEM_INFORMADO = "informado"
ORIGEM_HISTORICO = "historico"
ORIGEM_INICIO_DO_PLANO = "inicio_do_plano"


def ingresso_do_aluno(
    informado: str | None,
    periodos_do_historico: Collection[str | None],
    tem_historico: bool,
    inicio_do_plano: str,
    periodos_por_ano: int = 2,
) -> tuple[str | None, str | None]:
    """
    (período de ingresso, de onde veio). Ordem: o informado pelo aluno; o período mais antigo do
    histórico; com o histórico VAZIO, o início do plano (o aluno está começando). Histórico com
    tentativas mas sem períodos: desconhecido — não se afirma nada sobre o prazo.
    """
    if informado:
        return normalizar_periodo(informado, periodos_por_ano), ORIGEM_INFORMADO
    validos = [p for p in (normalizar_periodo(x, periodos_por_ano) for x in periodos_do_historico if x) if p]
    if validos:
        return min(validos, key=lambda p: indice_absoluto(p, periodos_por_ano)), ORIGEM_HISTORICO
    if not tem_historico:
        return inicio_do_plano, ORIGEM_INICIO_DO_PLANO
    return None, None

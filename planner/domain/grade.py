"""
Grade semanal derivada dos DADOS do curso (Etapa 4B).

O legado desenhava sempre SEG–SEX, 07:00–22:00, então um curso com aulas no
sábado ou à noite ficava com encontros fora da tela. Aqui os dias e a faixa de
horas saem dos encontros reais (e de `dias_letivos`, quando o curso informa).

Quando não há nenhum dado para derivar, devolve um padrão VISUAL (SEG–SEX,
07–22): serve só para desenhar a grade vazia, não afirma nada sobre o curso.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .entidades import Encontro

DIAS_ORDEM = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")
DIAS_PADRAO = DIAS_ORDEM[:5]
FAIXA_PADRAO = (7, 22)


@dataclass(frozen=True)
class Grade:
    dias: tuple[str, ...]   # em ordem de semana
    hora_inicio: int        # hora cheia em que a grade começa
    hora_fim: int           # hora cheia em que a grade termina (exclusive)


def derivar_grade(
    encontros: Iterable[Encontro], dias_letivos: Iterable[str] | None = None
) -> Grade:
    """
    Dias = `dias_letivos` do curso ∪ dias que têm encontro (nunca esconde um
    encontro). Horas = do menor início ao maior fim, arredondados para a hora cheia.
    """
    lista = list(encontros)
    dias = {d for d in (dias_letivos or ()) if d in DIAS_ORDEM} | {e.dia for e in lista}
    dias_ordenados = tuple(d for d in DIAS_ORDEM if d in dias) or DIAS_PADRAO

    if not lista:
        return Grade(dias_ordenados, *FAIXA_PADRAO)

    inicio = min(e.inicio.hour for e in lista)
    # 18:30 precisa de uma linha até 19h; 18:00 exato termina em 18h.
    fim = max(e.fim.hour + (1 if (e.fim.minute or e.fim.second) else 0) for e in lista)
    return Grade(dias_ordenados, inicio, max(fim, inicio + 1))

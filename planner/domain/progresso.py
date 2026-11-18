"""
Progresso no curso: obrigatórias + optativas até o exigido.

Corrige a regra acoplada do legado (total = soma de TODAS as disciplinas, o
que contava as optativas no denominador). Aqui:
  * obrigatórias: exigido = `creditos_obrigatorios` do curso; se desconhecido,
    soma dos créditos conhecidos das obrigatórias do catálogo;
  * optativas e eletivas formam um único pool ("X créditos de uma lista",
    ARQUITETURA.md §6): só contam até `creditos_optativos_exigidos`;
    se o curso não informa esse valor, não entram no denominador.
`creditos=None` é desconhecido: a disciplina é listada em
`disciplinas_sem_creditos` em vez de valer zero em silêncio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Iterable

from .entidades import TIPO_OBRIGATORIA, Disciplina


@dataclass(frozen=True)
class Progresso:
    obrigatorios_exigidos: int | None   # None = não dá para saber
    obrigatorios_cumpridos: int
    optativos_exigidos: int | None
    optativos_cumpridos: int            # tudo que foi aprovado no pool
    optativos_validos: int              # limitado ao exigido
    creditos_restantes: int | None
    percentual: float | None            # None = sem base para calcular
    disciplinas_sem_creditos: tuple[int, ...]

    @property
    def creditos_exigidos(self) -> int | None:
        """Obrigatórios + optativos exigidos; `None` se o total não é conhecido."""
        if self.obrigatorios_exigidos is None:
            return None
        return self.obrigatorios_exigidos + (self.optativos_exigidos or 0)

    @property
    def creditos_validos(self) -> int:
        """Créditos que contam para a formatura (obrigatórios até o exigido + optativos até o limite)."""
        obrig = self.obrigatorios_cumpridos
        if self.obrigatorios_exigidos is not None:
            obrig = min(obrig, self.obrigatorios_exigidos)
        return obrig + self.optativos_validos

    @property
    def concluido(self) -> bool:
        """Só afirma conclusão quando há base para isso."""
        return self.creditos_restantes == 0


def calcular_progresso(
    disciplinas: Iterable[Disciplina],
    aprovadas: Collection[int],
    creditos_obrigatorios: int | None = None,
    creditos_optativos_exigidos: int | None = None,
) -> Progresso:
    """Calcula o andamento do aluno a partir do catálogo e das aprovações."""
    catalogo = list(disciplinas)
    sem_creditos = tuple(sorted(d.id for d in catalogo if d.creditos is None))

    obrigatorias = [d for d in catalogo if d.tipo == TIPO_OBRIGATORIA]
    pool = [d for d in catalogo if d.tipo != TIPO_OBRIGATORIA]

    def soma(lista: list[Disciplina], so_aprovadas: bool) -> int:
        return sum(
            d.creditos or 0 for d in lista if not so_aprovadas or d.id in aprovadas
        )

    obrig_exigidos = creditos_obrigatorios
    if obrig_exigidos is None:
        total_catalogo = soma(obrigatorias, False)
        obrig_exigidos = total_catalogo or None  # 0 conhecido == nada sabido

    obrig_cumpridos = soma(obrigatorias, True)
    opt_cumpridos = soma(pool, True)
    opt_validos = (
        min(opt_cumpridos, creditos_optativos_exigidos)
        if creditos_optativos_exigidos is not None
        else opt_cumpridos
    )

    restantes = percentual = None
    if obrig_exigidos is not None:
        exigido_total = obrig_exigidos + (creditos_optativos_exigidos or 0)
        feito = min(obrig_cumpridos, obrig_exigidos) + (
            opt_validos if creditos_optativos_exigidos is not None else 0
        )
        restantes = max(0, exigido_total - feito)
        percentual = round(feito / exigido_total * 100, 1) if exigido_total else None

    return Progresso(
        obrigatorios_exigidos=obrig_exigidos,
        obrigatorios_cumpridos=obrig_cumpridos,
        optativos_exigidos=creditos_optativos_exigidos,
        optativos_cumpridos=opt_cumpridos,
        optativos_validos=opt_validos,
        creditos_restantes=restantes,
        percentual=percentual,
        disciplinas_sem_creditos=sem_creditos,
    )

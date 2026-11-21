"""
Preferências e restrições do ALUNO para o plano (além das do curso).

  * `semana`             blocos indisponíveis (trabalho, estágio, transporte), turno preferido e dias
                         que quer livres (ver `semana.PreferenciasSemana`);
  * `teto_por_periodo`   teto de créditos num período específico (TCC, estágio, intercâmbio…);
  * `periodos_pulados`   períodos em que não vai cursar nada (trancamento);
  * `max_pesadas`        máximo de disciplinas "pesadas" por semestre.

"Pesada" NÃO é palpite do app: é disciplina que o aluno já reprovou ou que ele mesmo marcou.
O app não inventa dificuldade. Função pura, só stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .semana import PreferenciasSemana

REGRA_OBRIGATORIA = "obrigatoria"   # o grupo só anda junto (reprovar em uma adia o grupo)
REGRA_PREFERENCIA = "preferencia"   # juntas se der; separar só custa uma penalidade
REGRAS_JUNTO = (REGRA_OBRIGATORIA, REGRA_PREFERENCIA)


@dataclass(frozen=True)
class GrupoJunto:
    """Disciplinas (2+) que o aluno quer cursar no MESMO semestre (ex.: TCC + Seminário)."""

    disciplinas: tuple[int, ...]
    regra: str = REGRA_OBRIGATORIA

    @property
    def obrigatoria(self) -> bool:
        return self.regra == REGRA_OBRIGATORIA


@dataclass(frozen=True)
class PreferenciasAluno:
    semana: PreferenciasSemana | None = None
    teto_por_periodo: Mapping[str, int] = field(default_factory=dict)
    periodos_pulados: frozenset[str] = frozenset()
    max_pesadas: int | None = None
    pesadas: frozenset[int] = frozenset()     # já reprovadas pelo aluno ∪ marcadas por ele
    juntas: tuple[GrupoJunto, ...] = ()       # grupos "cursar junto"
    fixas: Mapping[int, str] = field(default_factory=dict)   # disciplina → período em que o aluno QUER cursá-la

    def teto(self, periodo: str, teto_geral: int | None) -> int | None:
        """Teto do período: o específico (se houver) vale no lugar do geral; trancado = 0."""
        if periodo in self.periodos_pulados:
            return 0
        return self.teto_por_periodo.get(periodo, teto_geral)

    def pulado(self, periodo: str) -> bool:
        return periodo in self.periodos_pulados

    @property
    def vazia(self) -> bool:
        return (self.semana is None and not self.teto_por_periodo and not self.periodos_pulados
                and self.max_pesadas is None and not self.juntas and not self.fixas)


SEM_PREFERENCIAS = PreferenciasAluno()

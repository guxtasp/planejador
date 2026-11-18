"""Consultas de `Disciplina` (catálogo do curso)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import Disciplina, Turma
from .base import RepositorioBase


class DisciplinaRepository(RepositorioBase):
    def obter(self, disciplina_id: int) -> Disciplina | None:
        return self.sessao.get(Disciplina, disciplina_id)

    def obter_por_codigo(self, curso_id: int, codigo: str) -> Disciplina | None:
        return self.sessao.scalar(
            select(Disciplina).where(
                Disciplina.curso_id == curso_id, Disciplina.codigo == codigo
            )
        )

    def listar_do_curso(
        self, curso_id: int, *, com_requisitos: bool = False, com_turmas: bool = False
    ) -> list[Disciplina]:
        """
        Disciplinas do curso por período sugerido e código.

        `com_requisitos` / `com_turmas` pré-carregam as relações em consultas
        extras fixas (uma por relação), em vez de uma por disciplina.
        """
        consulta = (
            select(Disciplina)
            .where(Disciplina.curso_id == curso_id)
            # `IS NULL` primeiro na ordenação garante "sem período por último"
            # tanto no SQLite quanto no Postgres (que ordenam NULL diferente).
            .order_by(
                Disciplina.periodo_sugerido.is_(None),
                Disciplina.periodo_sugerido,
                Disciplina.codigo,
            )
        )
        if com_requisitos:
            consulta = consulta.options(selectinload(Disciplina.requisitos))
        if com_turmas:
            consulta = consulta.options(
                selectinload(Disciplina.turmas).selectinload(Turma.encontros)
            )
        return list(self.sessao.scalars(consulta))

    def mapa_por_codigo(self, curso_id: int) -> dict[str, Disciplina]:
        """`{codigo: Disciplina}` do curso — usado pelos importadores para resolver referências."""
        return {d.codigo: d for d in self.listar_do_curso(curso_id)}

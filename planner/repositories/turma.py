"""Consultas de `Turma` e seus `Encontro`s (oferta semestral)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import Disciplina, Turma
from .base import RepositorioBase


class TurmaRepository(RepositorioBase):
    def obter(self, turma_id: int) -> Turma | None:
        return self.sessao.get(Turma, turma_id)

    def obter_por_chave(
        self, disciplina_id: int, periodo_letivo: str, codigo_turma: str
    ) -> Turma | None:
        """Busca pela chave natural da turma (a mesma do `UNIQUE` do banco)."""
        return self.sessao.scalar(
            select(Turma).where(
                Turma.disciplina_id == disciplina_id,
                Turma.periodo_letivo == periodo_letivo,
                Turma.codigo_turma == codigo_turma,
            )
        )

    def listar_do_curso(self, curso_id: int, periodo_letivo: str | None = None) -> list[Turma]:
        """Turmas do curso (opcionalmente de um período), já com os encontros carregados."""
        consulta = (
            select(Turma)
            .join(Disciplina, Turma.disciplina_id == Disciplina.id)
            .where(Disciplina.curso_id == curso_id)
            .options(selectinload(Turma.encontros))
            .order_by(Disciplina.codigo, Turma.periodo_letivo, Turma.codigo_turma)
        )
        if periodo_letivo is not None:
            consulta = consulta.where(Turma.periodo_letivo == periodo_letivo)
        return list(self.sessao.scalars(consulta))

    def listar_periodos_do_curso(self, curso_id: int) -> list[str]:
        """Períodos letivos que têm oferta cadastrada, em ordem."""
        consulta = (
            select(Turma.periodo_letivo)
            .join(Disciplina, Turma.disciplina_id == Disciplina.id)
            .where(Disciplina.curso_id == curso_id)
            .distinct()
            .order_by(Turma.periodo_letivo)
        )
        return list(self.sessao.scalars(consulta))

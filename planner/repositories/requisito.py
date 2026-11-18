"""Consultas de `Requisito` (pré/co-requisitos)."""
from __future__ import annotations

from sqlalchemy import select

from ..models import Disciplina, Requisito
from .base import RepositorioBase


class RequisitoRepository(RepositorioBase):
    def listar_do_curso(self, curso_id: int) -> list[Requisito]:
        """Todos os requisitos das disciplinas do curso, em UMA consulta (com JOIN)."""
        consulta = (
            select(Requisito)
            .join(Disciplina, Requisito.disciplina_id == Disciplina.id)
            .where(Disciplina.curso_id == curso_id)
            .order_by(Requisito.id)
        )
        return list(self.sessao.scalars(consulta))

    def obter(self, disciplina_id: int, requisito_id: int, tipo: str) -> Requisito | None:
        return self.sessao.scalar(
            select(Requisito).where(
                Requisito.disciplina_id == disciplina_id,
                Requisito.requisito_id == requisito_id,
                Requisito.tipo == tipo,
            )
        )

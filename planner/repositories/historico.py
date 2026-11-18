"""Consultas de `Historico` (tentativas do aluno em disciplinas)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import Disciplina, Historico
from .base import RepositorioBase


class HistoricoRepository(RepositorioBase):
    def obter(self, historico_id: int) -> Historico | None:
        return self.sessao.get(Historico, historico_id)

    def obter_do_usuario(self, historico_id: int, usuario_id: int) -> Historico | None:
        """A tentativa só é devolvida se for DESTE usuário (isolamento entre contas)."""
        return self.sessao.scalar(
            select(Historico).where(Historico.id == historico_id, Historico.usuario_id == usuario_id)
        )

    def listar_do_usuario(
        self, usuario_id: int, curso_id: int | None = None, *, com_disciplina: bool = False
    ) -> list[Historico]:
        """
        Todas as tentativas do aluno (N por disciplina), opcionalmente de um só curso.

        `com_disciplina` pré-carrega a disciplina de cada tentativa em UMA consulta
        extra (sem N+1).
        """
        consulta = select(Historico).where(Historico.usuario_id == usuario_id)
        if curso_id is not None:
            consulta = consulta.join(Disciplina, Historico.disciplina_id == Disciplina.id).where(
                Disciplina.curso_id == curso_id
            )
        if com_disciplina:
            consulta = consulta.options(selectinload(Historico.disciplina))
        return list(self.sessao.scalars(consulta.order_by(Historico.id)))

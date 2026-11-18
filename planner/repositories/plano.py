"""Consultas de `Plano` (semestres e itens planejados pelo aluno)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import Plano, PlanoItem, PlanoSemestre
from .base import RepositorioBase


def _carregar_tudo():
    """Semestres, itens e as disciplinas/turmas dos itens, em consultas fixas (sem N+1)."""
    itens = selectinload(Plano.semestres).selectinload(PlanoSemestre.itens)
    return (itens, itens.selectinload(PlanoItem.disciplina), itens.selectinload(PlanoItem.turma))


class PlanoRepository(RepositorioBase):
    def obter(self, plano_id: int) -> Plano | None:
        return self.sessao.get(Plano, plano_id)

    def listar_do_usuario(self, usuario_id: int, curso_id: int | None = None) -> list[Plano]:
        consulta = select(Plano).where(Plano.usuario_id == usuario_id)
        if curso_id is not None:
            consulta = consulta.where(Plano.curso_id == curso_id)
        return list(self.sessao.scalars(consulta.order_by(Plano.id)))

    def listar_completos(self, usuario_id: int, curso_id: int) -> list[Plano]:
        """Todos os planos do aluno no curso, já com semestres e itens (5 consultas, qualquer quantidade)."""
        consulta = (
            select(Plano)
            .where(Plano.usuario_id == usuario_id, Plano.curso_id == curso_id)
            .options(*_carregar_tudo())
            .order_by(Plano.id)
        )
        return list(self.sessao.scalars(consulta))

    def obter_completo(self, plano_id: int) -> Plano | None:
        """Plano com semestres, itens e as disciplinas/turmas dos itens (sem N+1)."""
        consulta = select(Plano).where(Plano.id == plano_id).options(*_carregar_tudo())
        return self.sessao.scalar(consulta)

    def obter_completo_do_usuario(self, plano_id: int, usuario_id: int, curso_id: int) -> Plano | None:
        """Como `obter_completo`, mas só se o plano for deste usuário E deste curso."""
        consulta = (
            select(Plano)
            .where(Plano.id == plano_id, Plano.usuario_id == usuario_id, Plano.curso_id == curso_id)
            .options(*_carregar_tudo())
        )
        return self.sessao.scalar(consulta)

    def contar_do_usuario(self, usuario_id: int, curso_id: int) -> int:
        return len(self.listar_do_usuario(usuario_id, curso_id))

    def substituir_semestres(self, plano: Plano, novos: list[PlanoSemestre]) -> None:
        """
        Troca TODOS os semestres do plano pelos `novos`.

        O `flush` entre as duas etapas é necessário: o SQLAlchemy executa INSERTs
        antes de DELETEs na mesma sincronização, e `(plano_id, ordem)` é UNIQUE —
        sem ele, o semestre novo de mesma `ordem` bateria no antigo.
        O plano deve ter vindo de `obter_completo*` (itens carregados), para o ORM
        remover também os itens antigos da sessão.
        """
        plano.semestres.clear()
        self.sessao.flush()
        plano.semestres.extend(novos)
        self.sessao.flush()

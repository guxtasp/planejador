"""Consultas de `Curso`."""
from __future__ import annotations

from sqlalchemy import func, or_, select

from ..models import Curso, Disciplina, Turma, Visibilidade
from .base import RepositorioBase


class CursoRepository(RepositorioBase):
    def obter(self, curso_id: int) -> Curso | None:
        return self.sessao.get(Curso, curso_id)

    def listar_acessiveis(self, usuario_id: int | None = None) -> list[Curso]:
        """
        Cursos públicos mais os do próprio usuário (visitante vê só os públicos).

        Curso SEM dono (criado antes da autenticação) não é listado para ninguém;
        quem administra a instalação o atribui a uma conta com
        `flask reivindicar-cursos` (ver `PosseService`).
        """
        visivel = Curso.visibilidade == Visibilidade.PUBLICO.value
        if usuario_id is not None:
            visivel = or_(visivel, Curso.dono_id == usuario_id)
        consulta = select(Curso).where(visivel).order_by(Curso.nome, Curso.id)
        return list(self.sessao.scalars(consulta))

    def listar_sem_dono(self) -> list[Curso]:
        """Cursos órfãos (`dono_id` nulo), na ordem de criação."""
        return list(self.sessao.scalars(
            select(Curso).where(Curso.dono_id.is_(None)).order_by(Curso.id)))

    def contagens(self, curso_ids: list[int]) -> dict[int, tuple[int, int]]:
        """`{curso_id: (n_disciplinas, n_turmas)}` em 2 consultas agrupadas (sem N+1)."""
        if not curso_ids:
            return {}
        discs = dict(self.sessao.execute(
            select(Disciplina.curso_id, func.count(Disciplina.id))
            .where(Disciplina.curso_id.in_(curso_ids)).group_by(Disciplina.curso_id)
        ).all())
        turmas = dict(self.sessao.execute(
            select(Disciplina.curso_id, func.count(Turma.id))
            .join(Turma, Turma.disciplina_id == Disciplina.id)
            .where(Disciplina.curso_id.in_(curso_ids)).group_by(Disciplina.curso_id)
        ).all())
        return {i: (discs.get(i, 0), turmas.get(i, 0)) for i in curso_ids}

    def obter_por_nome(self, nome: str, dono_id: int | None) -> Curso | None:
        """Busca um curso pelo nome entre os do mesmo dono (`None` = sem dono)."""
        dono = Curso.dono_id.is_(None) if dono_id is None else Curso.dono_id == dono_id
        return self.sessao.scalar(select(Curso).where(Curso.nome == nome, dono))

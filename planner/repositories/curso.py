"""Consultas de `Curso`."""
from __future__ import annotations

from sqlalchemy import delete, func, or_, select

from ..models import Curso, Disciplina, Historico, Turma, Visibilidade
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

    def listar_do_dono_com_codigos(self, dono_id: int | None) -> list[tuple[Curso, list[str]]]:
        """Cursos do dono com os códigos das suas disciplinas (2 consultas). `None` = os cursos sem dono."""
        dono = Curso.dono_id.is_(None) if dono_id is None else Curso.dono_id == dono_id
        cursos = list(self.sessao.scalars(select(Curso).where(dono).order_by(Curso.id)))
        if not cursos:
            return []
        codigos: dict[int, list[str]] = {c.id: [] for c in cursos}
        for cid, codigo in self.sessao.execute(
                select(Disciplina.curso_id, Disciplina.codigo).where(Disciplina.curso_id.in_(list(codigos)))):
            codigos[cid].append(codigo)
        return [(c, codigos[c.id]) for c in cursos]

    def obter_por_nome(self, nome: str, dono_id: int | None) -> Curso | None:
        """Busca um curso pelo nome entre os do mesmo dono (`None` = sem dono)."""
        dono = Curso.dono_id.is_(None) if dono_id is None else Curso.dono_id == dono_id
        return self.sessao.scalar(select(Curso).where(Curso.nome == nome, dono))

    def usuarios_com_historico(self, curso_id: int) -> set[int]:
        """Ids das contas que têm histórico em disciplinas deste curso."""
        return set(self.sessao.scalars(
            select(Historico.usuario_id).distinct()
            .join(Disciplina, Historico.disciplina_id == Disciplina.id)
            .where(Disciplina.curso_id == curso_id)))

    def apagar_historico_do_curso(self, curso_id: int) -> None:
        """
        Remove o histórico ligado às disciplinas do curso. Necessário antes de apagar o curso:
        `historico.disciplina_id` é RESTRICT de propósito (o banco recusa apagar disciplina com histórico).
        """
        ids = select(Disciplina.id).where(Disciplina.curso_id == curso_id)
        self.sessao.execute(delete(Historico).where(Historico.disciplina_id.in_(ids)))

"""
Oferta de turmas de um curso (Etapa 4B): o que o planejador e o calendário
precisam para escolher turma e desenhar a grade.

Só leitura. A grade (dias e faixa de horas) é derivada dos encontros reais
pela regra pura `domain.grade`, não fixada no front.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain.entidades import Encontro as EncontroDominio
from ..domain.grade import derivar_grade
from ..repositories import TurmaRepository
from .cursos import CursoService


def hhmm(t) -> str:
    return t.strftime("%H:%M")


class OfertaService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoService(sessao)
        self._turmas = TurmaRepository(sessao)

    def listar(
        self, curso_id: int, periodo_letivo: str | None = None, usuario_id: int | None = None
    ) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)   # também valida o acesso
        turmas = self._turmas.listar_do_curso(curso_id, periodo_letivo)
        # Os períodos listados são sempre os do curso todo, mesmo com filtro.
        periodos = self._turmas.listar_periodos_do_curso(curso_id)

        grade = derivar_grade(
            (EncontroDominio(e.dia, e.inicio, e.fim) for t in turmas for e in t.encontros),
            curso["dias_letivos"],
        )
        return {
            "periodos": periodos,
            "grade": {"dias": list(grade.dias), "hora_inicio": grade.hora_inicio, "hora_fim": grade.hora_fim},
            "turmas": [
                {
                    "id": t.id, "disciplina_id": t.disciplina_id,
                    "periodo_letivo": t.periodo_letivo, "codigo_turma": t.codigo_turma,
                    "docente": t.docente, "vagas": t.vagas,
                    "encontros": [
                        {"dia": e.dia, "inicio": hhmm(e.inicio), "fim": hhmm(e.fim), "local": e.local}
                        for e in t.encontros
                    ],
                }
                for t in turmas
            ],
        }

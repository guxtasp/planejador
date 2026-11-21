"""
Oferta de turmas de um curso (Etapa 4B): o que o planejador e o calendário
precisam para escolher turma e desenhar a grade.

Só leitura. A grade (dias e faixa de horas) é derivada dos encontros reais
pela regra pura `domain.grade`, não fixada no front.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain.componentes import id_combinado, opcoes_de_matricula
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
            # opções de matrícula: turma completa, ou teórica + prática combinadas (id negativo)
            "turmas": [_opcao_json(partes) for partes in _opcoes(turmas)],
        }


def _opcoes(turmas) -> list[tuple]:
    por_disciplina: dict[int, list] = {}
    for t in turmas:
        por_disciplina.setdefault(t.disciplina_id, []).append(t)
    return [p for ts in por_disciplina.values() for p in opcoes_de_matricula(ts)]


def _encontros(t) -> list[dict]:
    return [{"dia": e.dia, "inicio": hhmm(e.inicio), "fim": hhmm(e.fim), "local": e.local,
             **({"componente": t.componente} if t.componente else {})} for e in t.encontros]


def _opcao_json(partes) -> dict:
    t = partes[0]
    if len(partes) == 1:
        return {"id": t.id, "disciplina_id": t.disciplina_id, "periodo_letivo": t.periodo_letivo,
                "codigo_turma": t.codigo_turma, "docente": t.docente, "vagas": t.vagas,
                "componente": t.componente, "encontros": _encontros(t)}
    teo, pra = partes
    docentes = [x for x in (teo.docente, pra.docente) if x]
    vagas = [x for x in (teo.vagas, pra.vagas) if x is not None]
    return {"id": id_combinado(teo.id, pra.id), "disciplina_id": t.disciplina_id, "periodo_letivo": t.periodo_letivo,
            "codigo_turma": f"{teo.codigo_turma}+{pra.codigo_turma}",
            "docente": " / ".join(dict.fromkeys(docentes)) or None, "vagas": min(vagas) if vagas else None,
            "componente": "combinada",
            "partes": [{"id": x.id, "codigo_turma": x.codigo_turma, "componente": x.componente} for x in partes],
            "encontros": _encontros(teo) + _encontros(pra)}

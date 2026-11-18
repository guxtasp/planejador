"""
Edição da oferta (par / ímpar / sempre) pela tela (Peça 3, parte C).

Até aqui a oferta só entrava por CSV. Quem criou o curso agora também pode ajustá-la na
tela Disciplinas. `None` volta a "não informada" (o simulador então estima e avisa).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import AppError, NotFoundError, ProibidoError
from ..extensions import db
from ..repositories import CursoRepository, DisciplinaRepository
from .cursos import CursoService
from .simulacao_json import ler_edicoes_periodicidade


class PeriodicidadeService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoService(sessao)
        self._repo_cursos = CursoRepository(sessao)
        self._disciplinas = DisciplinaRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def pode_editar(self, curso_id: int, usuario_id: int | None) -> bool:
        curso = self._repo_cursos.obter(curso_id)
        return curso is not None and usuario_id is not None and curso.dono_id == usuario_id

    def definir(self, curso_id: int, usuario_id: int, payload) -> dict:
        self._cursos.obter(curso_id, usuario_id)          # 404 se não pode nem ver o curso
        if not self.pode_editar(curso_id, usuario_id):
            raise ProibidoError("Só quem trouxe o curso pode alterar em que períodos as disciplinas abrem.")
        edicoes = ler_edicoes_periodicidade(payload)

        por_id = {d.id: d for d in self._disciplinas.listar_do_curso(curso_id)}
        fora = [i for i in edicoes if i not in por_id]
        if fora:
            raise NotFoundError("Há uma disciplina que não pertence a este curso.")
        try:                                              # tudo ou nada
            for did, valor in edicoes.items():
                por_id[did].periodicidade = valor
            self.sessao.commit()
        except Exception:
            self.sessao.rollback()
            raise AppError("Não foi possível salvar a oferta. Tente de novo.", 500)
        return {"atualizadas": [{"disciplina_id": i, "periodicidade": v} for i, v in edicoes.items()]}

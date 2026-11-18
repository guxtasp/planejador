"""
Histórico escolar do aluno (Etapa 5B-2): N tentativas por disciplina.

Cada operação vale só para o usuário informado: tentativa de outra pessoa dá o
mesmo 404 de uma que não existe. O histórico é do ALUNO, não do curso — mas cada
tentativa aponta para uma disciplina, e o curso dela precisa ser acessível.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import NotFoundError
from ..extensions import db
from ..models import Historico
from ..repositories import DisciplinaRepository, HistoricoRepository
from .cursos import CursoService
from .historico_json import ler_tentativa, serializar_tentativa


class HistoricoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def listar(self, curso_id: int, usuario_id: int) -> list[dict]:
        self._cursos.obter(curso_id, usuario_id)     # valida o acesso ao curso
        tentativas = self._historico.listar_do_usuario(usuario_id, curso_id, com_disciplina=True)
        return [serializar_tentativa(h) for h in tentativas]

    def criar(self, curso_id: int, usuario_id: int, payload) -> dict:
        self._cursos.obter(curso_id, usuario_id)
        dados = ler_tentativa(payload, com_disciplina=True)
        disciplina = self._disciplinas.obter(dados.disciplina_id)
        # Disciplina de outro curso = mesmo erro de disciplina inexistente.
        if disciplina is None or disciplina.curso_id != curso_id:
            raise NotFoundError("Disciplina não encontrada neste curso.")
        h = self._historico.adicionar(Historico(
            usuario_id=usuario_id, disciplina_id=disciplina.id,
            status=dados.status, periodo_letivo=dados.periodo_letivo, nota=dados.nota,
        ))
        self.sessao.commit()
        return serializar_tentativa(h)

    def atualizar(self, curso_id: int, historico_id: int, usuario_id: int, payload) -> dict:
        h = self._obter_do_curso(curso_id, historico_id, usuario_id)
        dados = ler_tentativa(payload, com_disciplina=False)
        h.status, h.periodo_letivo, h.nota = dados.status, dados.periodo_letivo, dados.nota
        self.sessao.commit()
        return serializar_tentativa(h)

    def remover(self, curso_id: int, historico_id: int, usuario_id: int) -> None:
        self._historico.remover(self._obter_do_curso(curso_id, historico_id, usuario_id))
        self.sessao.commit()

    def _obter_do_curso(self, curso_id: int, historico_id: int, usuario_id: int) -> Historico:
        self._cursos.obter(curso_id, usuario_id)
        h = self._historico.obter_do_usuario(historico_id, usuario_id)
        if h is None or h.disciplina.curso_id != curso_id:
            raise NotFoundError("Registro não encontrado.")
        return h

"""
Planos de matrícula do aluno, guardados no servidor (Etapa 5B-2).

Cada plano pertence a um usuário e a um curso. O cliente edita o plano inteiro e o
envia inteiro (`salvar` troca todos os semestres numa transação). Plano de outra
pessoa dá o mesmo 404 de plano inexistente.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import AppError, NotFoundError
from ..extensions import db
from ..models import Plano, PlanoItem, PlanoSemestre
from ..repositories import DisciplinaRepository, PlanoRepository, TurmaRepository
from .cursos import CursoService
from .analise_json import encontros_para_json
from .planos_json import PlanoEntrada, ler_plano, serializar_plano, validar_referencias

MAX_PLANOS_POR_CURSO = 20


class PlanoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._turmas = TurmaRepository(sessao)
        self._planos = PlanoRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def listar(self, curso_id: int, usuario_id: int) -> list[dict]:
        self._cursos.obter(curso_id, usuario_id)
        return [serializar_plano(p) for p in self._planos.listar_completos(usuario_id, curso_id)]

    def criar(self, curso_id: int, usuario_id: int, payload) -> dict:
        self._cursos.obter(curso_id, usuario_id)
        entrada = self._ler_e_validar(curso_id, payload)
        if self._planos.contar_do_usuario(usuario_id, curso_id) >= MAX_PLANOS_POR_CURSO:
            raise AppError(f"Limite de {MAX_PLANOS_POR_CURSO} planos por curso. Exclua algum para criar outro.", 422)
        plano = self._planos.adicionar(Plano(usuario_id=usuario_id, curso_id=curso_id, nome=entrada.nome))
        # Plano recém-criado: sem semestres antigos, basta acrescentar os novos.
        plano.semestres.extend(self._semestres(entrada))
        self.sessao.commit()
        return serializar_plano(self._planos.obter_completo(plano.id))

    def salvar(self, curso_id: int, plano_id: int, usuario_id: int, payload) -> dict:
        plano = self._obter(curso_id, plano_id, usuario_id)
        entrada = self._ler_e_validar(curso_id, payload)
        try:
            plano.nome = entrada.nome
            self._planos.substituir_semestres(plano, self._semestres(entrada))
            self.sessao.commit()
        except Exception:
            self.sessao.rollback()
            raise
        return serializar_plano(self._planos.obter_completo(plano_id))

    def excluir(self, curso_id: int, plano_id: int, usuario_id: int) -> None:
        self._planos.remover(self._obter(curso_id, plano_id, usuario_id))
        self.sessao.commit()

    # ── internos ──────────────────────────────────────────────────────────
    def _obter(self, curso_id: int, plano_id: int, usuario_id: int) -> Plano:
        self._cursos.obter(curso_id, usuario_id)
        plano = self._planos.obter_completo_do_usuario(plano_id, usuario_id, curso_id)
        if plano is None:
            raise NotFoundError("Plano não encontrado.")
        return plano

    def _ler_e_validar(self, curso_id: int, payload) -> PlanoEntrada:
        entrada = ler_plano(payload)
        disciplinas = {d.id for d in self._disciplinas.listar_do_curso(curso_id)}
        turmas = {t.id: (t.disciplina_id, t.periodo_letivo) for t in self._turmas.listar_do_curso(curso_id)}
        validar_referencias(entrada, disciplinas, turmas)
        return entrada

    @staticmethod
    def _semestres(entrada: PlanoEntrada) -> list[PlanoSemestre]:
        return [
            PlanoSemestre(
                ordem=i, label=s.rotulo, periodo_letivo=s.periodo_letivo,
                itens=[
                    PlanoItem(
                        disciplina_id=it.disciplina_id, turma_id=it.turma_id,
                        encontros_livres=encontros_para_json(it.encontros_livres) or None,
                    )
                    for it in s.itens
                ],
            )
            for i, s in enumerate(entrada.semestres, start=1)
        ]

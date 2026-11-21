"""Consultas de `PreferenciaAluno` (uma por aluno e curso)."""
from __future__ import annotations

from sqlalchemy import select

from ..models import PreferenciaAluno
from .base import RepositorioBase


class PreferenciaRepository(RepositorioBase):
    def obter(self, usuario_id: int, curso_id: int) -> PreferenciaAluno | None:
        return self.sessao.scalar(select(PreferenciaAluno).where(
            PreferenciaAluno.usuario_id == usuario_id, PreferenciaAluno.curso_id == curso_id))

    def salvar(self, usuario_id: int, curso_id: int, dados: dict) -> PreferenciaAluno:
        registro = self.obter(usuario_id, curso_id)
        if registro is None:
            registro = PreferenciaAluno(usuario_id=usuario_id, curso_id=curso_id, dados=dados)
            self.sessao.add(registro)
        else:
            registro.dados = dados
        self.sessao.flush()
        return registro

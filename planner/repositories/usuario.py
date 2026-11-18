"""Consultas de `Usuario`."""
from __future__ import annotations

from sqlalchemy import select

from ..models import Usuario
from .base import RepositorioBase


class UsuarioRepository(RepositorioBase):
    def obter(self, usuario_id: int) -> Usuario | None:
        return self.sessao.get(Usuario, usuario_id)

    def obter_por_email(self, email: str) -> Usuario | None:
        return self.sessao.scalar(select(Usuario).where(Usuario.email == email))

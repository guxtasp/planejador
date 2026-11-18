"""
Posse de cursos (Etapa 5A): atribuir a uma conta os cursos que ficaram SEM dono.

Antes da autenticação, toda importação criava um curso sem dono. Depois do login
esses cursos deixam de aparecer para todo mundo (ninguém é o dono). Quem
administra a instalação os entrega a uma conta com `flask reivindicar-cursos EMAIL`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import AppError
from ..domain.identidade import email_valido, normalizar_email
from ..extensions import db
from ..models import Usuario
from ..repositories import CursoRepository, UsuarioRepository


class PosseService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoRepository(sessao)
        self._usuarios = UsuarioRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def reivindicar_orfaos(self, email_bruto: str) -> int:
        """
        Dá à conta de `email_bruto` todos os cursos sem dono e devolve quantos foram.
        Cria a conta se ainda não existir (no primeiro login por link ela é reaproveitada).
        """
        email = normalizar_email(email_bruto)
        if not email_valido(email):
            raise AppError("E-mail inválido.")
        usuario = self._usuarios.obter_por_email(email) or self._usuarios.adicionar(Usuario(email=email))
        orfaos = self._cursos.listar_sem_dono()
        for curso in orfaos:
            curso.dono_id = usuario.id
        self.sessao.commit()
        return len(orfaos)

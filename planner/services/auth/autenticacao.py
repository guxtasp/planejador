"""
Casos de uso de autenticação (Etapa 5A, revista para o Supabase).

`entrar(token)`: confere o token com o provedor, cria a conta se for a primeira
vez e devolve a conta. Abrir a sessão (cookie) é da camada HTTP. A conta só nasce
depois de o provedor confirmar que a pessoa controla o e-mail.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.identidade import caminho_interno_seguro
from ...extensions import db
from ...models import Usuario
from ...repositories import UsuarioRepository
from .verificador import VerificadorDeToken


def usuario_para_dict(u: Usuario) -> dict:
    """Só o que a tela precisa saber da conta."""
    return {"id": u.id, "email": u.email, "nome": u.nome}


class AutenticacaoService:
    def __init__(self, verificador: VerificadorDeToken, sessao: Session | None = None) -> None:
        self._verificador = verificador
        self._sessao = sessao
        self._usuarios = UsuarioRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def entrar(self, token: object, proximo: object = None) -> tuple[dict, str]:
        """Devolve `(usuario, caminho_de_retorno)`; levanta `TokenInvalido` se o token não vale."""
        identidade = self._verificador.verificar(token)
        usuario = self._obter_ou_criar(identidade.email)
        self.sessao.commit()
        return usuario_para_dict(usuario), caminho_interno_seguro(proximo)

    def _obter_ou_criar(self, email: str) -> Usuario:
        usuario = self._usuarios.obter_por_email(email)
        if usuario is not None:
            return usuario
        try:
            return self._usuarios.adicionar(Usuario(email=email))
        except IntegrityError:   # dois logins simultâneos: o outro criou a conta primeiro
            self.sessao.rollback()
            return self._usuarios.obter_por_email(email)

    def obter_usuario(self, usuario_id: int) -> dict | None:
        """Conta da sessão (ou `None` se foi apagada)."""
        usuario = self._usuarios.obter(usuario_id)
        return usuario_para_dict(usuario) if usuario else None

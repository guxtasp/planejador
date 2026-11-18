"""
Link mágico de entrada (Etapa 5A): emissão e leitura de um token ASSINADO.

O token carrega `{e-mail, versão, destino}` e uma data; a assinatura (HMAC com a
`SECRET_KEY`) impede adulteração, e a data limita a validade. A *versão* é o que
faz o link valer UMA vez só: ela é a `usuario.versao_login` de quando o link foi
emitido, e cada login bem-sucedido incrementa o contador no banco (ver
`AutenticacaoService.entrar`). Não há tabela de tokens.
"""
from __future__ import annotations

from dataclasses import dataclass

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ...api.errors import AppError

MSG_LINK_INVALIDO = "Este link expirou, já foi usado ou não é válido. Peça um novo link."


class LinkInvalido(AppError):
    """Token adulterado, expirado ou já usado. Mensagem única: não ajuda quem tenta adivinhar."""

    status_code = 400

    def __init__(self) -> None:
        super().__init__(MSG_LINK_INVALIDO)


@dataclass(frozen=True)
class DadosLink:
    """O que o token afirma (e a assinatura garante)."""

    email: str
    versao: int
    proximo: str | None = None


class EmissorDeLinks:
    """Cria e valida tokens de entrada. Não conhece banco nem HTTP."""

    # "Sal" próprio: um token deste tipo não vale como outro tipo de token assinado com a mesma chave.
    _SAL = "planner.link-de-entrada"

    def __init__(self, segredo: str, validade_segundos: int) -> None:
        self._serializador = URLSafeTimedSerializer(segredo, salt=self._SAL)
        self._validade = validade_segundos

    def emitir(self, email: str, versao: int, proximo: str | None = None) -> str:
        carga = {"e": email, "v": versao}
        if proximo:
            carga["p"] = proximo
        return self._serializador.dumps(carga)

    def ler(self, token: object) -> DadosLink:
        """Devolve os dados do token ou levanta `LinkInvalido`."""
        if not isinstance(token, str) or not token:
            raise LinkInvalido()
        try:
            carga = self._serializador.loads(token, max_age=self._validade)
        except (SignatureExpired, BadSignature):
            raise LinkInvalido() from None
        email, versao, proximo = carga.get("e"), carga.get("v"), carga.get("p")
        # Assinatura válida mas formato estranho (ex.: chave antiga): trata como inválido.
        if not isinstance(email, str) or not isinstance(versao, int) or isinstance(versao, bool):
            raise LinkInvalido()
        return DadosLink(email, versao, proximo if isinstance(proximo, str) else None)

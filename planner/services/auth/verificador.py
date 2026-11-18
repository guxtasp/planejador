"""
Verificação de identidade (Etapa 5A, revista): quem é o dono de um token de login.

O login em si (enviar e-mail, conferir código, link mágico) é feito pelo
Supabase Auth, direto do navegador: o projeto não tem servidor de e-mail. O
navegador recebe do Supabase um token de acesso (JWT) e o entrega ao nosso
servidor; este módulo o confere e devolve a identidade, e a sessão do Flask
(cookie assinado) segue como antes.

Padrão Strategy: `VerificadorDeToken` é a interface; cada provedor é uma classe.
  * `VerificadorSupabase`: pergunta ao próprio Supabase (`GET /auth/v1/user`);
  * `VerificadorDeDesenvolvimento`: aceita `dev:<email>` (só dev/testes; a
    configuração de produção o proíbe).
Trocar de provedor (ex.: Google direto) = nova classe, sem tocar no resto.

Por que perguntar ao Supabase em vez de validar o JWT aqui: funciona igual com
chaves simétricas e assimétricas (o Supabase mudou isso mais de uma vez), não
exige guardar o segredo JWT no servidor e só custa UMA chamada por login (depois
disso vale o nosso cookie de sessão).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Protocol

from ...api.errors import AppError, NaoAutenticadoError
from ...domain.identidade import email_valido, normalizar_email

log = logging.getLogger("planner.auth")

MSG_TOKEN_INVALIDO = "Não foi possível confirmar o seu login. Entre de novo."
TAMANHO_MAX_TOKEN = 8192   # JWTs reais têm ~1 KB; recusa lixo grande antes de gastar uma chamada de rede


class TokenInvalido(NaoAutenticadoError):
    """Token ausente, vencido, adulterado ou de e-mail não confirmado. Mensagem única, sem pistas."""

    def __init__(self) -> None:
        super().__init__(MSG_TOKEN_INVALIDO)


@dataclass(frozen=True)
class IdentidadeVerificada:
    """O que o provedor garante sobre quem entrou. O e-mail já vem normalizado."""

    email: str
    id_externo: str | None = None   # id da conta no provedor (informativo; a identidade do app é o e-mail)


class VerificadorDeToken(Protocol):
    def verificar(self, token: object) -> IdentidadeVerificada:
        """Devolve a identidade ou levanta `TokenInvalido` (ou `AppError` 503 se o provedor estiver fora)."""


class VerificadorSupabase:
    """Confere o token de acesso consultando o Supabase Auth."""

    def __init__(self, url: str, chave_publica: str, timeout: int = 8,
                 abrir: Callable = urllib.request.urlopen) -> None:
        # `abrir` é injetável para testar sem rede.
        self._url = url.rstrip("/")
        self._chave, self._timeout, self._abrir = chave_publica, timeout, abrir

    def verificar(self, token: object) -> IdentidadeVerificada:
        if not isinstance(token, str) or not token or len(token) > TAMANHO_MAX_TOKEN:
            raise TokenInvalido()
        pedido = urllib.request.Request(
            f"{self._url}/auth/v1/user",
            headers={"apikey": self._chave, "Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with self._abrir(pedido, timeout=self._timeout) as resposta:
                dados = json.load(resposta)
        except urllib.error.HTTPError as erro:   # antes de OSError: HTTPError é subclasse dele
            if erro.code in (400, 401, 403):
                raise TokenInvalido() from None
            log.error("Supabase respondeu %s ao conferir o login", erro.code)
            raise AppError("O serviço de login não respondeu direito. Tente de novo em instantes.", 503) from None
        except (OSError, ValueError):            # rede fora, timeout, resposta que não é JSON
            log.exception("Falha ao falar com o Supabase")
            raise AppError("Não foi possível falar com o serviço de login. Tente de novo em instantes.", 503) from None
        return self._identidade(dados)

    @staticmethod
    def _identidade(dados: object) -> IdentidadeVerificada:
        if not isinstance(dados, dict):
            raise TokenInvalido()
        email = normalizar_email(dados.get("email"))
        # Só vale e-mail CONFIRMADO: sem isso qualquer um poderia cadastrar o e-mail de outra pessoa.
        confirmado = dados.get("email_confirmed_at") or dados.get("confirmed_at")
        if not email_valido(email) or not confirmado:
            raise TokenInvalido()
        id_externo = dados.get("id")
        return IdentidadeVerificada(email, id_externo if isinstance(id_externo, str) else None)


class VerificadorDeDesenvolvimento:
    """
    Aceita `dev:<e-mail>` como token, sem consultar ninguém. Serve para rodar e
    testar sem projeto no Supabase. NUNCA em produção (`ProductionConfig.validate` proíbe).
    """

    PREFIXO = "dev:"

    def verificar(self, token: object) -> IdentidadeVerificada:
        if not isinstance(token, str) or not token.startswith(self.PREFIXO):
            raise TokenInvalido()
        email = normalizar_email(token[len(self.PREFIXO):])
        if not email_valido(email):
            raise TokenInvalido()
        return IdentidadeVerificada(email)

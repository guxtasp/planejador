"""
Entrega do link de entrada (Etapa 5A) — padrão Strategy.

`EnviadorDeLink` é a interface; cada forma de entrega é uma implementação:
  * `EnviadorConsole`: só registra o link no log (desenvolvimento e testes);
  * `EnviadorSMTP`: manda e-mail de verdade (produção).
Trocar de provedor (ex.: API de e-mail) = nova classe aqui, sem tocar no resto.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Mapping, Protocol

from ...api.errors import AppError

log = logging.getLogger("planner.auth")

ASSUNTO = "Seu link de acesso ao Planejador Acadêmico"


class EnviadorDeLink(Protocol):
    def enviar(self, email: str, link: str, validade_minutos: int) -> None:
        """Entrega `link` a `email` ou levanta `AppError` se não conseguir."""


def _corpo(link: str, validade_minutos: int) -> str:
    return (
        "Olá!\n\n"
        "Use o link abaixo para entrar no Planejador Acadêmico:\n\n"
        f"{link}\n\n"
        f"Ele vale por {validade_minutos} minutos e só funciona uma vez.\n"
        "Se não foi você quem pediu, ignore esta mensagem: nada será feito.\n"
    )


class EnviadorConsole:
    """Não envia nada: registra o link no log. Nunca usar em produção (a config proíbe)."""

    def enviar(self, email: str, link: str, validade_minutos: int) -> None:
        log.warning("Link de entrada para %s (válido por %d min): %s", email, validade_minutos, link)


class EnviadorSMTP:
    """Envio por SMTP (biblioteca padrão; sem dependência extra)."""

    def __init__(self, host: str, porta: int, remetente: str, usuario: str | None = None,
                 senha: str | None = None, usar_tls: bool = True, timeout: int = 10) -> None:
        self._host, self._porta, self._remetente = host, porta, remetente
        self._usuario, self._senha = usuario, senha
        self._usar_tls, self._timeout = usar_tls, timeout

    def enviar(self, email: str, link: str, validade_minutos: int) -> None:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = ASSUNTO, self._remetente, email
        msg.set_content(_corpo(link, validade_minutos))
        try:
            with smtplib.SMTP(self._host, self._porta, timeout=self._timeout) as servidor:
                if self._usar_tls:
                    servidor.starttls()
                if self._usuario:
                    servidor.login(self._usuario, self._senha or "")
                servidor.send_message(msg)
        except (OSError, smtplib.SMTPException):
            # O detalhe técnico vai para o log; a pessoa recebe uma mensagem útil, sem segredos.
            log.exception("Falha ao enviar o link de entrada")
            raise AppError("Não foi possível enviar o e-mail agora. Tente de novo em instantes.", 503) from None


def criar_enviador(config: Mapping) -> EnviadorDeLink:
    """Fábrica: escolhe a implementação pela configuração `AUTH_ENVIO` (`console` | `smtp`)."""
    modo = config.get("AUTH_ENVIO", "console")
    if modo == "smtp":
        return EnviadorSMTP(
            host=config["SMTP_HOST"], porta=int(config.get("SMTP_PORTA", 587)),
            remetente=config["SMTP_REMETENTE"], usuario=config.get("SMTP_USUARIO") or None,
            senha=config.get("SMTP_SENHA") or None, usar_tls=bool(config.get("SMTP_TLS", True)))
    if modo == "console":
        return EnviadorConsole()
    raise RuntimeError(f"AUTH_ENVIO inválido: {modo!r}. Use 'console' ou 'smtp'.")

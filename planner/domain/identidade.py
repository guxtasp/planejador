"""
Regras puras de identidade (Etapa 5A): e-mail e caminho de retorno após o login.

Só stdlib. Ficam no domínio porque são regras de negócio sem relação com HTTP
ou banco, e por isso podem ser testadas sozinhas.
"""
from __future__ import annotations

import re

TAMANHO_MAX_EMAIL = 254  # limite do RFC 5321 (e da coluna `usuario.email`)
TAMANHO_MAX_CAMINHO = 200

# Deliberadamente simples: o e-mail só é "provado" quando a pessoa abre o link
# enviado. O que importa aqui é recusar o que poderia virar vários destinatários
# (`a@x.com,b@y.com`) ou injeção de cabeçalho (quebras de linha).
_EMAIL = re.compile(r"^[^@\s,;<>\"()\[\]\\]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")


def normalizar_email(bruto: object) -> str:
    """Tira espaços e passa para minúsculas, para `Ana@X.com` e `ana@x.com` serem a mesma conta."""
    return bruto.strip().lower() if isinstance(bruto, str) else ""


def email_valido(email: str) -> bool:
    """`True` se `email` (já normalizado) tem a forma `algo@dominio.tld` e cabe no banco."""
    return 0 < len(email) <= TAMANHO_MAX_EMAIL and _EMAIL.match(email) is not None


def caminho_interno_seguro(valor: object, padrao: str = "/") -> str:
    """
    Aceita só caminhos DENTRO deste site como destino pós-login (`/importar`,
    `/curso/3`). Qualquer outra coisa vira `padrao`, o que impede o "open
    redirect" (usar o login para mandar a pessoa a um site de terceiros).
    """
    if not isinstance(valor, str) or not valor.startswith("/"):
        return padrao
    if valor.startswith("//") or "\\" in valor:      # `//outro.site` e `/\outro.site` saem do domínio
        return padrao
    if len(valor) > TAMANHO_MAX_CAMINHO or any(ord(c) < 32 or ord(c) == 127 for c in valor):
        return padrao
    return valor

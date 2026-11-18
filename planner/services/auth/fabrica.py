"""Fábrica do serviço de autenticação a partir da configuração (padrão Factory)."""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from .autenticacao import AutenticacaoService
from .verificador import VerificadorDeDesenvolvimento, VerificadorDeToken, VerificadorSupabase


def criar_verificador(config: Mapping) -> VerificadorDeToken:
    """Escolhe o provedor pela configuração `AUTH_PROVEDOR` (`supabase` | `dev`)."""
    provedor = config.get("AUTH_PROVEDOR", "dev")
    if provedor == "supabase":
        if not (config.get("SUPABASE_URL") and config.get("SUPABASE_ANON_KEY")):
            raise RuntimeError("AUTH_PROVEDOR=supabase exige SUPABASE_URL e SUPABASE_ANON_KEY.")
        return VerificadorSupabase(config["SUPABASE_URL"], config["SUPABASE_ANON_KEY"])
    if provedor == "dev":
        return VerificadorDeDesenvolvimento()
    raise RuntimeError(f"AUTH_PROVEDOR inválido: {provedor!r}. Use 'supabase' ou 'dev'.")


def criar_autenticacao(config: Mapping, sessao: Session | None = None) -> AutenticacaoService:
    """Monta verificador + serviço com os valores de `app.config`."""
    return AutenticacaoService(criar_verificador(config), sessao)

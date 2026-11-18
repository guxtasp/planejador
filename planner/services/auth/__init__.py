"""Autenticação por Supabase Auth, com sessão própria em cookie (Etapa 5A, revista)."""
from .autenticacao import AutenticacaoService, usuario_para_dict
from .fabrica import criar_autenticacao, criar_verificador
from .verificador import (IdentidadeVerificada, TokenInvalido, VerificadorDeDesenvolvimento,
                          VerificadorDeToken, VerificadorSupabase)

__all__ = [
    "AutenticacaoService", "usuario_para_dict", "criar_autenticacao", "criar_verificador",
    "IdentidadeVerificada", "TokenInvalido", "VerificadorDeDesenvolvimento", "VerificadorDeToken",
    "VerificadorSupabase",
]

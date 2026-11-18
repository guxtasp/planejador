"""Login pelo Supabase — verificadores de token (sem banco, sem rede: o `urlopen` é falso)."""
import io
import json
import urllib.error

import pytest

from planner.api.errors import AppError
from planner.services.auth import (TokenInvalido, VerificadorDeDesenvolvimento, VerificadorSupabase,
                                   criar_verificador)


class RespostaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def abrindo(dados, capturar=None):
    def abrir(pedido, timeout):
        if capturar is not None:
            capturar.append((pedido, timeout))
        return RespostaFalsa(json.dumps(dados).encode())
    return abrir


def falhando(erro):
    def abrir(pedido, timeout):
        raise erro
    return abrir


def verificador(abrir):
    return VerificadorSupabase("https://x.supabase.co/", "chave-publica", abrir=abrir)


USUARIO_OK = {"id": "uuid-1", "email": "  Ana@Exemplo.com ", "email_confirmed_at": "2026-01-01T00:00:00Z"}


def test_token_valido_devolve_identidade_normalizada():
    chamadas = []
    ident = verificador(abrindo(USUARIO_OK, chamadas)).verificar("jwt")
    assert (ident.email, ident.id_externo) == ("ana@exemplo.com", "uuid-1")
    pedido, timeout = chamadas[0]
    assert pedido.full_url == "https://x.supabase.co/auth/v1/user" and timeout == 8
    cab = {k.lower(): v for k, v in pedido.header_items()}
    assert cab["apikey"] == "chave-publica" and cab["authorization"] == "Bearer jwt"


def test_email_nao_confirmado_e_recusado():
    with pytest.raises(TokenInvalido):
        verificador(abrindo({**USUARIO_OK, "email_confirmed_at": None})).verificar("jwt")


@pytest.mark.parametrize("dados", [{}, {"email": "nao-e-email", "email_confirmed_at": "x"}, ["lista"], "texto"])
def test_resposta_sem_email_valido_e_recusada(dados):
    with pytest.raises(TokenInvalido):
        verificador(abrindo(dados)).verificar("jwt")


@pytest.mark.parametrize("token", [None, "", 123, "x" * 9000])
def test_token_ausente_ou_absurdo_nem_chega_a_rede(token):
    chamadas = []
    with pytest.raises(TokenInvalido):
        verificador(abrindo(USUARIO_OK, chamadas)).verificar(token)
    assert chamadas == []


@pytest.mark.parametrize("codigo", [400, 401, 403])
def test_supabase_recusando_o_token_vira_token_invalido(codigo):
    erro = urllib.error.HTTPError("u", codigo, "x", {}, None)
    with pytest.raises(TokenInvalido):
        verificador(falhando(erro)).verificar("jwt")


def test_supabase_fora_do_ar_da_503_e_nao_401():
    for erro in (urllib.error.HTTPError("u", 500, "x", {}, None), urllib.error.URLError("sem rede"), TimeoutError()):
        with pytest.raises(AppError) as e:
            verificador(falhando(erro)).verificar("jwt")
        assert e.value.status_code == 503


def test_resposta_que_nao_e_json_da_503():
    class Lixo(RespostaFalsa):
        pass
    with pytest.raises(AppError) as e:
        verificador(lambda p, timeout: Lixo(b"<html>")).verificar("jwt")
    assert e.value.status_code == 503


# ── provedor de desenvolvimento ──────────────────────────────────────────────────────────
def test_dev_aceita_so_o_prefixo_dev():
    v = VerificadorDeDesenvolvimento()
    assert v.verificar("dev: A@x.com ").email == "a@x.com"
    for ruim in ("a@x.com", "dev:nao-e-email", None, "jwt-de-verdade"):
        with pytest.raises(TokenInvalido):
            v.verificar(ruim)


# ── fábrica ──────────────────────────────────────────────────────────────────────────────
def test_fabrica_escolhe_pelo_provedor():
    assert isinstance(criar_verificador({"AUTH_PROVEDOR": "dev"}), VerificadorDeDesenvolvimento)
    cfg = {"AUTH_PROVEDOR": "supabase", "SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "k"}
    assert isinstance(criar_verificador(cfg), VerificadorSupabase)


def test_fabrica_falha_cedo_com_configuracao_incompleta_ou_invalida():
    with pytest.raises(RuntimeError):
        criar_verificador({"AUTH_PROVEDOR": "supabase"})
    with pytest.raises(RuntimeError):
        criar_verificador({"AUTH_PROVEDOR": "google"})

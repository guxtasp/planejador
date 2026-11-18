"""Etapa 5A — regras puras de identidade (e-mail e caminho de retorno)."""
import pytest

from planner.domain.identidade import caminho_interno_seguro, email_valido, normalizar_email


def test_normalizar_tira_espacos_e_caixa():
    assert normalizar_email("  Ana@Exemplo.COM ") == "ana@exemplo.com"


@pytest.mark.parametrize("bruto", [None, 3, [], {}])
def test_normalizar_nao_texto_vira_vazio(bruto):
    assert normalizar_email(bruto) == ""


@pytest.mark.parametrize("email", ["a@x.com", "nome.sobrenome+tag@ufv.br", "a@sub.dominio.edu.br"])
def test_emails_validos(email):
    assert email_valido(email)


@pytest.mark.parametrize("email", [
    "", "semarroba", "@x.com", "a@", "a@x", "a b@x.com", "a@x.com,b@y.com", "a@x.com;b@y.com",
    "a@x.com\nBcc: v@y.com", "<a@x.com>", "a@@x.com", "a@x..com", "a" * 250 + "@x.com",
])
def test_emails_invalidos(email):
    assert not email_valido(email)


@pytest.mark.parametrize("valor", ["/", "/importar", "/curso/3", "/importar?x=1"])
def test_caminhos_internos_passam(valor):
    assert caminho_interno_seguro(valor) == valor


@pytest.mark.parametrize("valor", [
    None, 5, "", "importar", "https://mal.com", "//mal.com", "/\\mal.com", "javascript:alert(1)",
    "/ok\nSet-Cookie: x=1", "/" + "a" * 300,
])
def test_caminhos_externos_ou_estranhos_viram_o_padrao(valor):
    assert caminho_interno_seguro(valor) == "/"
    assert caminho_interno_seguro(valor, padrao="/inicio") == "/inicio"

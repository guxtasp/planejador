"""
`ContextoValidacao`: o que os estágios da validação compartilham.

Cada estágio lê e altera este contexto: acrescenta problemas (`issues`), descarta
linhas inválidas e corrige códigos. As leituras da 3A NÃO são modificadas — o
contexto trabalha numa cópia —, então rodar a validação de novo dá o mesmo resultado.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, Mapping

from .. import IMPORTADORES
from ..base import Issue, ResultadoLeitura, Severidade
from ..leitor_csv import normalizar
from .estado import EstadoExistente

# Ordem de dependência dos arquivos (também a ordem de exibição da prévia).
ORDEM_ARQUIVOS: tuple[str, ...] = tuple(IMPORTADORES)


def chave(codigo: str) -> str:
    """Forma de comparar códigos: sem caixa, sem acento. 'inf110' == 'INF110'."""
    return normalizar(codigo)


class ContextoValidacao:
    """Estado mutável de UMA validação (um dry-run)."""

    def __init__(self, leituras: Mapping[str, ResultadoLeitura], estado: EstadoExistente) -> None:
        self.estado = estado
        self.arquivos: tuple[str, ...] = tuple(a for a in ORDEM_ARQUIVOS if a in leituras)
        self.linhas_lidas = {a: leituras[a].linhas_lidas for a in self.arquivos}
        self.registros: dict[str, list] = {a: list(leituras[a].registros) for a in self.arquivos}
        self.issues: list[Issue] = [i for a in self.arquivos for i in leituras[a].issues]
        # Arquivos que já tinham erro de schema na 3A: explicam referências "quebradas".
        self.com_erro_de_schema = {a for a in self.arquivos if leituras[a].tem_erros}
        # `chave(codigo)` → código canônico da disciplina; preenchido pelo estágio referencial.
        self.catalogo: dict[str, str] = {}

    # ── problemas ────────────────────────────────────────────────────────
    def erro(self, arquivo: str, linha: int | None, coluna: str | None, mensagem: str) -> None:
        self.issues.append(Issue(arquivo, linha, coluna, Severidade.ERRO, mensagem))

    def aviso(self, arquivo: str, linha: int | None, coluna: str | None, mensagem: str) -> None:
        self.issues.append(Issue(arquivo, linha, coluna, Severidade.AVISO, mensagem))

    # ── registros ────────────────────────────────────────────────────────
    def ativos(self, arquivo: str) -> list:
        """Registros ainda válidos do arquivo (vazio se o arquivo não foi enviado)."""
        return self.registros.get(arquivo, [])

    def descartar(self, arquivo: str, linhas: set[int]) -> None:
        """Remove as linhas indicadas (mesma política da 3A: linha com erro não segue adiante)."""
        if linhas:
            self.registros[arquivo] = [r for r in self.registros[arquivo] if r.linha not in linhas]

    def transformar(self, arquivo: str, funcao: Callable) -> None:
        """Substitui cada registro pelo resultado de `funcao` (registros são imutáveis)."""
        self.registros[arquivo] = [funcao(r) for r in self.registros.get(arquivo, [])]

    def canonico(self, codigo: str) -> str | None:
        """Código oficial da disciplina (como no catálogo) ou None se ela não existe."""
        return self.catalogo.get(chave(codigo))


def com_codigo(registro, campo: str, canonico: str):
    """Cópia do registro com o código do `campo` escrito como no catálogo."""
    return registro if getattr(registro, campo) == canonico else replace(registro, **{campo: canonico})

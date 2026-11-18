"""
Leitura bruta de CSV: encoding, delimitador, cabeçalho e linhas.

Esta etapa NÃO interpreta o conteúdo das células (isso é dos importadores);
ela só entrega `LinhaCsv` com os nomes de coluna oficiais, ou `None` quando o
arquivo é inutilizável (e o motivo vai para a lista de `issues`).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata

from .base import Esquema, Issue, LinhaCsv, Severidade, Tabela

# O Excel em pt-BR salva com ";"; o Sheets/IA costuma usar ",". TAB vem de colar planilhas.
DELIMITADORES = (",", ";", "\t")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e com espaços colapsados — para comparar rótulos."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()


def _problema(issues: list[Issue], arquivo: str, linha: int | None, coluna: str | None,
              severidade: Severidade, mensagem: str) -> None:
    issues.append(Issue(arquivo, linha, coluna, severidade, mensagem))


def decodificar(conteudo: bytes | str, arquivo: str, issues: list[Issue]) -> str | None:
    """
    Converte bytes em texto. UTF-8 (com ou sem BOM) é o padrão; se falhar, tenta
    Windows-1252 (Excel antigo) e AVISA, porque acentos podem ter sido trocados.
    """
    if isinstance(conteudo, str):
        return conteudo.lstrip("﻿")
    if b"\x00" in conteudo[:4096]:
        # .xlsx/.xls/.pdf têm bytes nulos: o usuário enviou o formato errado.
        _problema(issues, arquivo, None, None, Severidade.ERRO,
                  "O arquivo não parece ser texto CSV (talvez seja .xlsx ou PDF). "
                  "Exporte a planilha como CSV (UTF-8) e envie de novo.")
        return None
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        _problema(issues, arquivo, None, None, Severidade.AVISO,
                  "O arquivo não está em UTF-8; foi lido como Windows-1252. "
                  "Confira se os acentos estão corretos (ou salve como CSV UTF-8).")
        return conteudo.decode("cp1252", errors="replace")


def detectar_delimitador(texto: str) -> str:
    """Escolhe o delimitador que divide o cabeçalho em mais colunas (empate → vírgula)."""
    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    melhor, maior = ",", 1
    for candidato in DELIMITADORES:
        colunas = len(next(csv.reader([primeira], delimiter=candidato), []))
        if colunas > maior:
            melhor, maior = candidato, colunas
    return melhor


def _nome_canonico(rotulo: str, esquema: Esquema) -> str:
    """'Carga Horária' → 'carga_horaria' → (alias) 'carga_h'."""
    nome = normalizar(rotulo).replace(" ", "_").replace("-", "_")
    return esquema.aliases.get(nome, nome)


def ler_tabela(conteudo: bytes | str, arquivo: str, esquema: Esquema,
               issues: list[Issue]) -> Tabela | None:
    """
    Lê o CSV inteiro. Retorna `None` se o arquivo for inutilizável (vazio,
    binário, sem cabeçalho obrigatório…); linhas malformadas são puladas com um
    erro (e contadas em `Tabela.rejeitadas`) e o restante segue.
    """
    texto = decodificar(conteudo, arquivo, issues)
    if texto is None:
        return None
    if not texto.strip():
        _problema(issues, arquivo, None, None, Severidade.ERRO, "O arquivo está vazio.")
        return None

    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=detectar_delimitador(texto))
    cabecalho = _ler_cabecalho(leitor, arquivo, esquema, issues)
    if cabecalho is None:
        return None
    return _ler_linhas(leitor, cabecalho, arquivo, issues)


def _ler_cabecalho(leitor, arquivo: str, esquema: Esquema, issues: list[Issue]) -> list[str] | None:
    """Primeira linha não vazia. Valida obrigatórias, repetidas e desconhecidas."""
    for brutos in leitor:
        if any(c.strip() for c in brutos):
            break
    else:
        return None
    numero = leitor.line_num
    nomes = [_nome_canonico(c, esquema) for c in brutos]

    faltando = [c for c in esquema.obrigatorias if c not in nomes]
    if faltando:
        _problema(issues, arquivo, numero, None, Severidade.ERRO,
                  f"Coluna(s) obrigatória(s) ausente(s) no cabeçalho: {', '.join(faltando)}. "
                  f"Colunas esperadas: {', '.join(esquema.colunas)}.")
        return None
    repetidas = sorted({n for n in nomes if n and nomes.count(n) > 1})
    if repetidas:
        _problema(issues, arquivo, numero, None, Severidade.ERRO,
                  f"Coluna repetida no cabeçalho: {', '.join(repetidas)}.")
        return None
    for rotulo, nome in zip(brutos, nomes):
        if nome and nome not in esquema.colunas:
            _problema(issues, arquivo, numero, rotulo.strip(), Severidade.AVISO,
                      f"Coluna desconhecida '{rotulo.strip()}': será ignorada.")
    return nomes


def _ler_linhas(leitor, cabecalho: list[str], arquivo: str, issues: list[Issue]) -> Tabela:
    """Separa as linhas de dados (linhas totalmente vazias são ignoradas)."""
    tabela = Tabela()
    while True:
        inicio = leitor.line_num + 1  # linha onde o registro COMEÇA (aspas podem quebrar linha)
        try:
            brutos = next(leitor)
        except StopIteration:
            return tabela
        except csv.Error as erro:
            tabela.rejeitadas += 1
            _problema(issues, arquivo, inicio, None, Severidade.ERRO, f"Linha malformada: {erro}.")
            continue
        if not any(c.strip() for c in brutos):
            continue
        if any(c.strip() for c in brutos[len(cabecalho):]):
            tabela.rejeitadas += 1
            _problema(issues, arquivo, inicio, None, Severidade.ERRO,
                      f"A linha tem {len(brutos)} colunas, mas o cabeçalho tem {len(cabecalho)}. "
                      "Textos com vírgula precisam estar entre aspas.")
            continue
        brutos = brutos[:len(cabecalho)] + [""] * (len(cabecalho) - len(brutos))
        valores = {nome: (c.strip() or None) for nome, c in zip(cabecalho, brutos) if nome}
        tabela.linhas.append(LinhaCsv(inicio, valores))

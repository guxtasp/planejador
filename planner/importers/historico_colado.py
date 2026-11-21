"""
Histórico COLADO da tela do sistema acadêmico (alternativa ao cadastro manual).

Cada sistema cola de um jeito (TAB, ponto e vírgula, vários espaços; colunas em qualquer ordem;
cabeçalho, totais e linhas em branco no meio). Por isso cada linha é reconhecida pelo CONTEÚDO:

  * código   primeiro token no formato de código (2–5 letras + 2–4 dígitos, ex.: INF110, MAT 140);
  * período  AAAA/N, AAAA.N ou AAAA-N (opcional);
  * situação aprovado/APR/AP, reprovado/REP/RF/RM/RN, cursando/matriculado/MAT (obrigatória);
  * nota     de 0 a 100: a com casa decimal, ou a última quando há 2+ números (CH + nota); um número
             sozinho é ambíguo (pode ser a carga horária) e fica sem nota (opcional).

Linha sem código é ignorada (cabeçalho, totais). Linha com código e sem situação reconhecível vira
"não entendida" com o motivo: nada é adivinhado. Função pura, só stdlib.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

APROVADO, REPROVADO, CURSANDO = "aprovado", "reprovado", "cursando"
MAX_LINHAS = 400

_CODIGO = re.compile(r"\b([A-Za-z]{2,5})\s?(\d{2,4}[A-Za-z]?)\b")
_PERIODO = re.compile(r"\b((?:19|20)\d{2})\s*[./-]\s*([1-4])\b")
_NUMERO = re.compile(r"(?<![\d/.-])(\d{1,3}(?:[.,]\d{1,2})?)(?![\d/])")
_SITUACOES = {
    APROVADO: ("aprovado", "aprovada", "apr", "ap", "aprov", "dispensado", "dispensada", "aproveitamento",
               "aproveitada", "equivalencia", "cumprido", "cumprida"),
    REPROVADO: ("reprovado", "reprovada", "rep", "rf", "rm", "rn", "reprov", "reprovado por falta",
                "reprovado por nota", "reprovado por media"),
    CURSANDO: ("cursando", "matriculado", "matriculada", "em curso", "em andamento", "mat", "cur"),
}


@dataclass(frozen=True)
class LinhaColada:
    numero: int                    # linha no texto colado (a partir de 1)
    texto: str
    codigo: str | None
    periodo_letivo: str | None
    status: str | None
    nota: Decimal | None
    problema: str | None = None    # por que a linha não foi entendida


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()


def _situacao(texto: str) -> str | None:
    palavras = " " + re.sub(r"[^a-z]+", " ", _sem_acento(texto)) + " "
    # expressões mais longas primeiro ("reprovado por falta" antes de "rf")
    candidatos = sorted(((v, s) for s, vs in _SITUACOES.items() for v in vs), key=lambda x: -len(x[0]))
    for valor, status in candidatos:
        if f" {valor} " in palavras:
            return status
    return None


def ler_linha(numero: int, texto: str) -> LinhaColada | None:
    """Uma linha do texto colado; None = não tem código (cabeçalho, total, vazia)."""
    bruto = texto.strip()
    m = _CODIGO.search(bruto)
    if not bruto or not m:
        return None
    codigo = (m.group(1) + m.group(2)).upper()
    resto = bruto[:m.start()] + " " + bruto[m.end():]
    p = _PERIODO.search(resto)
    periodo = f"{p.group(1)}/{p.group(2)}" if p else None
    sem_periodo = resto[:p.start()] + " " + resto[p.end():] if p else resto
    status = _situacao(sem_periodo)
    nota = None
    numeros = []
    for n in _NUMERO.findall(sem_periodo):
        try:
            numeros.append((Decimal(n.replace(",", ".")), "," in n or "." in n))
        except InvalidOperation:
            continue
    # nota: a que tem casa decimal; ou, havendo 2+ números (créditos/CH e nota), o último.
    # Um número sozinho é ambíguo (pode ser a carga horária): fica sem nota. Cursando não tem nota.
    com_decimal = [v for v, dec in numeros if dec and 0 <= v <= 100]
    if status != CURSANDO:
        if com_decimal:
            nota = com_decimal[-1]
        elif len(numeros) >= 2 and 0 <= numeros[-1][0] <= 100:
            nota = numeros[-1][0]
    if status is None:
        return LinhaColada(numero, bruto, codigo, periodo, None, nota,
                           "Não deu para saber a situação (aprovado, reprovado ou cursando).")
    return LinhaColada(numero, bruto, codigo, periodo, status, nota)


def _como_colunas(linhas: list[str]) -> list[str]:
    """
    Arquivo CSV (vírgula ou ponto e vírgula) vira colunas separadas por TAB antes da leitura — senão
    "60,7" (carga horária, nota) pareceria a nota 60,7. Só é tratado como CSV quando a maioria das linhas
    tem 2+ separadores, na mesma quantidade (texto colado com uma nota "8,5" por linha não é CSV).
    """
    cheias = [l for l in linhas if l.strip()]
    if not cheias or any("\t" in l for l in cheias[:10]):
        return linhas
    for sep in (";", ","):
        # conta separadores FORA de aspas (o csv.reader já entende "Cálculo I, turma A")
        contagens = [len(next(csv.reader([l], delimiter=sep))) - 1 for l in cheias]
        moda = max(set(contagens), key=contagens.count)
        if moda >= 2 and contagens.count(moda) >= 0.8 * len(cheias):
            return ["\t".join(c.strip() for c in linha) for linha in csv.reader(linhas, delimiter=sep)]
    return linhas


def ler_historico_colado(texto: str) -> tuple[LinhaColada, ...]:
    """Texto colado OU conteúdo de um .csv exportado do sistema acadêmico."""
    if not isinstance(texto, str):
        return ()
    texto = texto.lstrip("﻿")                        # BOM do Excel
    linhas = _como_colunas(texto.replace("\r\n", "\n").split("\n")[:MAX_LINHAS])
    return tuple(x for x in (ler_linha(i, t) for i, t in enumerate(linhas, start=1)) if x is not None)

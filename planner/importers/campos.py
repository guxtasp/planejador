"""
`LeitorLinha`: lê e valida as células de UMA linha, acumulando os problemas.

Cada importador descreve a linha chamando `texto`, `inteiro`, `escolha`… e
nunca precisa montar mensagens de erro à mão. As validações de tamanho espelham
as colunas do banco (planner/models), para o erro aparecer na prévia e não
como uma exceção no commit.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Mapping

from .base import Issue, LinhaCsv, Severidade
from .horarios import DIAS_VALIDOS, parse_dia
from .leitor_csv import normalizar

_INTEIRO = re.compile(r"^\d+([.,]0+)?$")          # aceita "6", "6.0" e "6,0" (Excel)
_PERIODO_LETIVO = re.compile(r"^(\d{4})\s*[/.\-]\s*(\d{1,2})$")
_COR = re.compile(r"^#[0-9a-fA-F]{6}$")


def vocabulario(enum: type[Enum], sinonimos: Mapping[str, tuple[str, ...]] | None = None) -> dict[str, str]:
    """
    Tabela `valor normalizado → valor oficial` a partir de um Enum do banco, mais
    sinônimos aceitos (ex.: 'pré-requisito' → 'pre'). Assim o importador nunca
    diverge do vocabulário gravado no banco.
    """
    tabela = {normalizar(membro.value): membro.value for membro in enum}
    for oficial, apelidos in (sinonimos or {}).items():
        for apelido in apelidos:
            tabela[normalizar(apelido)] = oficial
    return tabela


class LeitorLinha:
    """Lê as células de uma linha; erros e avisos vão para `problemas`."""

    def __init__(self, arquivo: str, linha: LinhaCsv, problemas: list[Issue]) -> None:
        self._arquivo = arquivo
        self._linha = linha
        self._problemas = problemas

    @property
    def numero(self) -> int:
        """Número da linha no arquivo (para guardar no registro)."""
        return self._linha.numero

    # ── registro de problemas ────────────────────────────────────────────
    def erro(self, coluna: str | None, mensagem: str) -> None:
        self._problemas.append(Issue(self._arquivo, self._linha.numero, coluna, Severidade.ERRO, mensagem))

    def aviso(self, coluna: str | None, mensagem: str) -> None:
        self._problemas.append(Issue(self._arquivo, self._linha.numero, coluna, Severidade.AVISO, mensagem))

    def _bruto(self, coluna: str, obrigatorio: bool) -> str | None:
        valor = self._linha.valores.get(coluna)
        if valor is None and obrigatorio:
            self.erro(coluna, f"'{coluna}' é obrigatório e está em branco.")
        return valor

    # ── tipos básicos ────────────────────────────────────────────────────
    def texto(self, coluna: str, *, obrigatorio: bool = False, max_len: int | None = None) -> str | None:
        """Texto livre. `max_len` espelha o tamanho da coluna no banco."""
        valor = self._bruto(coluna, obrigatorio)
        if valor is not None and max_len is not None and len(valor) > max_len:
            self.erro(coluna, f"'{coluna}' tem {len(valor)} caracteres; o máximo é {max_len}.")
            return None
        return valor

    def codigo(self, coluna: str, *, obrigatorio: bool = True, max_len: int = 30) -> str | None:
        """Código de disciplina/turma: espaços internos colapsados; a caixa é preservada."""
        valor = self.texto(coluna, obrigatorio=obrigatorio, max_len=max_len)
        return re.sub(r"\s+", " ", valor) if valor is not None else None

    def inteiro(self, coluna: str, *, minimo: int = 0, maximo: int | None = None) -> int | None:
        """Inteiro ≥ `minimo`. Vazio = None (desconhecido, nunca zero)."""
        valor = self._bruto(coluna, False)
        if valor is None:
            return None
        if not _INTEIRO.match(valor):
            self.erro(coluna, f"'{valor}' não é um número inteiro.")
            return None
        numero = int(re.split(r"[.,]", valor)[0])
        if numero < minimo or (maximo is not None and numero > maximo):
            faixa = f"≥ {minimo}" if maximo is None else f"entre {minimo} e {maximo}"
            self.erro(coluna, f"Valor {numero} fora do permitido (deve ser {faixa}).")
            return None
        return numero

    def decimal(self, coluna: str, *, minimo: Decimal, maximo: Decimal, casas: int = 2) -> Decimal | None:
        """Número com vírgula ou ponto decimal, dentro de [minimo, maximo]."""
        valor = self._bruto(coluna, False)
        if valor is None:
            return None
        try:
            numero = Decimal(valor.replace(",", "."))
        except InvalidOperation:
            self.erro(coluna, f"'{valor}' não é um número.")
            return None
        if not numero.is_finite() or not minimo <= numero <= maximo:
            self.erro(coluna, f"Valor {valor} fora do permitido (de {minimo} a {maximo}).")
            return None
        if numero.as_tuple().exponent < -casas:
            self.erro(coluna, f"'{valor}' tem mais de {casas} casas decimais.")
            return None
        return numero

    # ── vocabulários e formatos do domínio ──────────────────────────────
    def escolha(self, coluna: str, opcoes: Mapping[str, str], *, obrigatorio: bool = True) -> str | None:
        """Valor de um vocabulário fechado (sem diferenciar caixa/acento) → valor oficial."""
        valor = self._bruto(coluna, obrigatorio)
        if valor is None:
            return None
        oficial = opcoes.get(normalizar(valor))
        if oficial is None:
            validos = ", ".join(sorted(set(opcoes.values())))
            self.erro(coluna, f"Valor '{valor}' inválido em '{coluna}'. Use: {validos}.")
        return oficial

    def periodo_letivo(self, coluna: str, *, obrigatorio: bool) -> str | None:
        """'2026/1' (também aceita '2026.1' e '2026-01') → '2026/1'."""
        valor = self._bruto(coluna, obrigatorio)
        if valor is None:
            return None
        casou = _PERIODO_LETIVO.match(valor)
        if not casou or int(casou[2]) < 1:
            self.erro(coluna, f"Período letivo '{valor}' inválido. Use AAAA/N, ex.: 2026/1.")
            return None
        return f"{casou[1]}/{int(casou[2])}"

    def cor(self, coluna: str) -> str | None:
        """Cor hexadecimal '#rrggbb'; vazio = sem cor (a UI escolhe uma)."""
        valor = self._bruto(coluna, False)
        if valor is None:
            return None
        if not _COR.match(valor):
            self.erro(coluna, f"Cor '{valor}' inválida. Use o formato #rrggbb, ex.: #3b82f6.")
            return None
        return valor.lower()

    def dias(self, coluna: str) -> tuple[str, ...] | None:
        """Lista de dias separados por | , ; ou espaço (ex.: 'SEG|TER|SAB'). Vazio = None."""
        valor = self._bruto(coluna, False)
        if valor is None:
            return None
        resultado: list[str] = []
        for parte in filter(None, re.split(r"[|,;\s]+", valor)):
            dia = parse_dia(parte)
            if dia is None:
                self.erro(coluna, f"Dia '{parte}' inválido. Use: {', '.join(DIAS_VALIDOS)}.")
                return None
            if dia not in resultado:
                resultado.append(dia)
        return tuple(resultado)

    def bruto(self, coluna: str) -> str | None:
        """Célula sem interpretação (para colunas com parser próprio, como `horarios`)."""
        return self._bruto(coluna, False)

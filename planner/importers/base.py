"""
Tipos compartilhados por todos os importadores CSV.

Aqui ficam só dados: o problema encontrado (`Issue`), o formato esperado de um
arquivo (`Esquema`), uma linha já lida (`LinhaCsv`) e o resultado da leitura
(`ResultadoLeitura`). A interface `CsvImporter` (Strategy) fica em `importador.py`
para não criar import circular com o leitor de CSV.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Mapping, TypeVar


class Severidade(str, Enum):
    ERRO = "erro"    # a linha (ou o arquivo) não pode ser importada
    AVISO = "aviso"  # importável, mas merece conferência


@dataclass(frozen=True)
class Issue:
    """Um problema encontrado, sempre com a localização exata no arquivo."""

    arquivo: str
    linha: int | None        # número da linha no arquivo (1 = cabeçalho); None = arquivo inteiro
    coluna: str | None
    severidade: Severidade
    mensagem: str

    def para_dict(self) -> dict[str, Any]:
        """Formato JSON usado pela API e pela tela de prévia (Etapa 3C)."""
        return {
            "arquivo": self.arquivo, "linha": self.linha, "coluna": self.coluna,
            "severidade": self.severidade.value, "mensagem": self.mensagem,
        }


@dataclass(frozen=True)
class Esquema:
    """Colunas aceitas por um arquivo. `aliases` mapeia nomes alternativos → nome oficial."""

    obrigatorias: tuple[str, ...]
    opcionais: tuple[str, ...] = ()
    aliases: Mapping[str, str] = field(default_factory=dict)

    @property
    def colunas(self) -> tuple[str, ...]:
        return self.obrigatorias + self.opcionais


@dataclass(frozen=True)
class LinhaCsv:
    """
    Uma linha de dados já separada em colunas.

    As chaves são os nomes OFICIAIS das colunas (aliases já resolvidos) e os
    valores vêm sem espaços nas pontas; célula vazia vira `None`
    (princípio do projeto: vazio = desconhecido).
    """

    numero: int
    valores: Mapping[str, str | None]


@dataclass
class Tabela:
    """
    O que o leitor de CSV entrega: as linhas utilizáveis e quantas foram
    rejeitadas já na leitura (colunas a mais, aspas quebradas) — elas contam
    como "lidas" na prévia, mesmo sem virar `LinhaCsv`.
    """

    linhas: list[LinhaCsv] = field(default_factory=list)
    rejeitadas: int = 0


R = TypeVar("R")


@dataclass
class ResultadoLeitura(Generic[R]):
    """
    Saída de um importador. `registros` só contém linhas SEM erro; as com erro
    são descartadas e explicadas em `issues`. Nada aqui toca o banco.
    """

    arquivo: str
    registros: list[R] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    linhas_lidas: int = 0

    @property
    def erros(self) -> list[Issue]:
        return [i for i in self.issues if i.severidade is Severidade.ERRO]

    @property
    def avisos(self) -> list[Issue]:
        return [i for i in self.issues if i.severidade is Severidade.AVISO]

    @property
    def tem_erros(self) -> bool:
        return any(i.severidade is Severidade.ERRO for i in self.issues)

    @property
    def linhas_descartadas(self) -> int:
        return self.linhas_lidas - len(self.registros)

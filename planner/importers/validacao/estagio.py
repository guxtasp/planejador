"""Interface de um estágio da validação (elo da cadeia / Pipeline)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from .contexto import ContextoValidacao


class Estagio(ABC):
    """
    Um passo pequeno e independente da validação: lê o contexto, registra
    problemas e descarta o que não pode seguir. Não conhece os outros estágios;
    só a ORDEM definida em `pipeline.py` importa.
    """

    nome: ClassVar[str]

    @abstractmethod
    def executar(self, ctx: ContextoValidacao) -> None:
        """Aplica o estágio ao contexto."""

"""
`CsvImporter`: a interface (Strategy) comum a todos os importadores.

O método `importar` é um Template Method: o esqueleto (ler a tabela, validar
linha a linha, descartar as inválidas) é igual para todos; cada subclasse só
diz QUAIS são suas colunas (`esquema`) e COMO converter uma linha (`converter`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Generic

from .base import Esquema, Issue, R, ResultadoLeitura, Severidade
from .campos import LeitorLinha
from .leitor_csv import ler_tabela


class CsvImporter(ABC, Generic[R]):
    """Lê um tipo de CSV e devolve registros tipados + problemas. Nunca grava no banco."""

    arquivo: ClassVar[str]      # nome esperado, ex.: "disciplinas.csv"
    esquema: ClassVar[Esquema]

    def importar(self, conteudo: bytes | str) -> ResultadoLeitura[R]:
        """Executa o pipeline de leitura + validação de schema."""
        resultado: ResultadoLeitura[R] = ResultadoLeitura(arquivo=self.arquivo)
        tabela = ler_tabela(conteudo, self.arquivo, self.esquema, resultado.issues)
        if tabela is None:
            return resultado

        resultado.linhas_lidas = len(tabela.linhas) + tabela.rejeitadas
        for linha in tabela.linhas:
            problemas: list[Issue] = []
            registro = self.converter(LeitorLinha(self.arquivo, linha, problemas))
            resultado.issues.extend(problemas)
            # Linha com QUALQUER erro é descartada inteira: importar parte dela
            # geraria um dado acadêmico incompleto sem o usuário perceber.
            if not any(p.severidade is Severidade.ERRO for p in problemas):
                resultado.registros.append(registro)

        self.verificar_arquivo(resultado)
        return resultado

    @abstractmethod
    def converter(self, leitor: LeitorLinha) -> R:
        """
        Converte uma linha em registro, lendo cada célula pelo `leitor`.

        Pode devolver um registro com campos `None` quando a linha tem erro:
        ele será descartado por `importar` e nunca chega a quem consome.
        """

    def verificar_arquivo(self, resultado: ResultadoLeitura[R]) -> None:
        """Gancho opcional para regras do arquivo como um todo (ex.: 'só 1 linha')."""

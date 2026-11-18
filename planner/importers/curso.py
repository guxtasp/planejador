"""Importador de `curso.csv`: UMA linha com os dados gerais da matriz."""
from __future__ import annotations

from .base import Esquema, Issue, ResultadoLeitura, Severidade
from .campos import LeitorLinha
from .importador import CsvImporter
from .registros import CursoCsv


class CursoImporter(CsvImporter[CursoCsv]):
    """Só `nome` é obrigatório; tudo que o documento oficial não informa fica vazio."""

    arquivo = "curso.csv"
    esquema = Esquema(
        obrigatorias=("nome",),
        opcionais=("instituicao", "versao_matriz", "creditos_obrigatorios",
                   "creditos_optativos_exigidos", "ch_total", "max_creditos_semestre",
                   "duracao_semestres", "dias_letivos"),
        aliases={"curso": "nome", "carga_horaria_total": "ch_total",
                 "creditos_optativos": "creditos_optativos_exigidos"},
    )

    def converter(self, leitor: LeitorLinha) -> CursoCsv:
        return CursoCsv(
            linha=leitor.numero,
            nome=leitor.texto("nome", obrigatorio=True, max_len=200),
            instituicao=leitor.texto("instituicao", max_len=200),
            versao_matriz=leitor.texto("versao_matriz", max_len=50),
            creditos_obrigatorios=leitor.inteiro("creditos_obrigatorios"),
            creditos_optativos_exigidos=leitor.inteiro("creditos_optativos_exigidos"),
            ch_total=leitor.inteiro("ch_total"),
            max_creditos_semestre=leitor.inteiro("max_creditos_semestre", minimo=1),
            duracao_semestres=leitor.inteiro("duracao_semestres", minimo=1),
            dias_letivos=leitor.dias("dias_letivos"),
        )

    def verificar_arquivo(self, resultado: ResultadoLeitura[CursoCsv]) -> None:
        """Um arquivo = um curso. Mais de uma linha é ambíguo: mantém a primeira e bloqueia."""
        for extra in resultado.registros[1:]:
            resultado.issues.append(Issue(
                self.arquivo, extra.linha, None, Severidade.ERRO,
                "curso.csv deve ter uma única linha de dados; esta foi descartada."))
        del resultado.registros[1:]

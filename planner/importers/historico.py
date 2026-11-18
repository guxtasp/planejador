"""Importador de `historico.csv`: tentativas do aluno (pode haver várias por disciplina)."""
from __future__ import annotations

from decimal import Decimal

from ..models.enums import StatusHistorico
from .base import Esquema
from .campos import LeitorLinha, vocabulario
from .importador import CsvImporter
from .registros import TentativaCsv

STATUS = vocabulario(StatusHistorico, {
    "aprovado": ("aprovada", "aprov"),
    "reprovado": ("reprovada", "reprov"),
    "cursando": ("em andamento", "matriculado", "matriculada"),
})


class HistoricoImporter(CsvImporter[TentativaCsv]):
    """
    Uma linha = uma tentativa. Reprovou e depois passou? São DUAS linhas.
    A nota vai de 0 a 100 (limite do banco); a escala usada (0–10, 0–100) é do curso.
    """

    arquivo = "historico.csv"
    esquema = Esquema(
        obrigatorias=("disciplina", "status"),
        opcionais=("periodo_letivo", "nota"),
        aliases={"codigo": "disciplina", "codigo_disciplina": "disciplina",
                 "situacao": "status", "periodo": "periodo_letivo"},
    )

    def converter(self, leitor: LeitorLinha) -> TentativaCsv:
        return TentativaCsv(
            linha=leitor.numero,
            disciplina=leitor.codigo("disciplina"),
            status=leitor.escolha("status", STATUS),
            periodo_letivo=leitor.periodo_letivo("periodo_letivo", obrigatorio=False),
            nota=leitor.decimal("nota", minimo=Decimal(0), maximo=Decimal(100)),
        )

"""Importador de `requisitos.csv`: pré-requisitos e correquisitos."""
from __future__ import annotations

from ..models.enums import TipoRequisito
from .base import Esquema
from .campos import LeitorLinha, vocabulario
from .importador import CsvImporter
from .leitor_csv import normalizar
from .registros import RequisitoCsv

TIPOS = vocabulario(TipoRequisito, {
    "pre": ("pré", "prerequisito", "pré-requisito", "pre-requisito", "pre_requisito"),
    "co": ("correquisito", "co-requisito", "corequisito", "co_requisito"),
})


class RequisitoImporter(CsvImporter[RequisitoCsv]):
    """
    Uma linha = "`disciplina` exige `requisito`". `grupo_alt` vazio = obrigatório (AND);
    linhas da mesma disciplina, do mesmo tipo e do mesmo grupo = alternativas (OR).
    Se existir o código nas duas colunas é erro aqui mesmo; a existência do código
    no catálogo só é checada na Etapa 3B (depende de outros arquivos).
    """

    arquivo = "requisitos.csv"
    esquema = Esquema(
        obrigatorias=("disciplina", "requisito", "tipo"),
        opcionais=("grupo_alt",),
        aliases={"codigo": "disciplina", "codigo_disciplina": "disciplina",
                 "codigo_requisito": "requisito", "grupo": "grupo_alt"},
    )

    def converter(self, leitor: LeitorLinha) -> RequisitoCsv:
        disciplina = leitor.codigo("disciplina")
        requisito = leitor.codigo("requisito")
        if disciplina and requisito and normalizar(disciplina) == normalizar(requisito):
            leitor.erro("requisito", f"{disciplina} não pode ser requisito de si mesma.")
        return RequisitoCsv(
            linha=leitor.numero,
            disciplina=disciplina,
            requisito=requisito,
            tipo=leitor.escolha("tipo", TIPOS),
            grupo_alt=leitor.codigo("grupo_alt", obrigatorio=False, max_len=30),
        )

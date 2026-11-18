"""Importador de `disciplinas.csv`: o catálogo (a matriz curricular)."""
from __future__ import annotations

from ..models.enums import TipoDisciplina
from .base import Esquema
from .campos import LeitorLinha, vocabulario
from .importador import CsvImporter
from .registros import DisciplinaCsv

TIPOS = vocabulario(TipoDisciplina, {
    "obrigatoria": ("obrigatório", "obrig"),
    "optativa": ("optativo", "opt"),
    "eletiva": ("eletivo",),
})


class DisciplinaImporter(CsvImporter[DisciplinaCsv]):
    """
    `codigo`, `nome` e `tipo` são obrigatórios. `tipo` NÃO tem padrão de propósito:
    ele decide o cálculo de progresso, e assumir "obrigatória" seria inventar.
    Créditos, carga horária, período e cor em branco = desconhecido.
    """

    arquivo = "disciplinas.csv"
    esquema = Esquema(
        obrigatorias=("codigo", "nome", "tipo"),
        opcionais=("creditos", "carga_h", "periodo_sugerido", "cor"),
        aliases={"cod": "codigo", "codigo_disciplina": "codigo", "disciplina": "nome",
                 "credito": "creditos", "carga_horaria": "carga_h", "ch": "carga_h",
                 "periodo": "periodo_sugerido", "semestre": "periodo_sugerido"},
    )

    def converter(self, leitor: LeitorLinha) -> DisciplinaCsv:
        return DisciplinaCsv(
            linha=leitor.numero,
            codigo=leitor.codigo("codigo", max_len=30),
            nome=leitor.texto("nome", obrigatorio=True, max_len=200),
            tipo=leitor.escolha("tipo", TIPOS),
            creditos=leitor.inteiro("creditos"),
            carga_h=leitor.inteiro("carga_h"),
            periodo_sugerido=leitor.inteiro("periodo_sugerido", minimo=1),
            cor=leitor.cor("cor"),
        )

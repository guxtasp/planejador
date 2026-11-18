"""Importador de `disciplinas.csv`: o catálogo (a matriz curricular)."""
from __future__ import annotations

from ..models.enums import Periodicidade, TipoDisciplina
from .base import Esquema
from .campos import LeitorLinha, vocabulario
from .importador import CsvImporter
from .registros import DisciplinaCsv

TIPOS = vocabulario(TipoDisciplina, {
    "obrigatoria": ("obrigatório", "obrig"),
    "optativa": ("optativo", "opt"),
    "eletiva": ("eletivo",),
})

PERIODICIDADES = vocabulario(Periodicidade, {
    "sempre": ("todo periodo", "todo semestre", "todos", "ambos", "qualquer", "regular", "anual"),
    "impar": ("impares", "periodo impar", "semestre impar", "1", "1o", "1o semestre", "primeiro semestre"),
    "par": ("pares", "periodo par", "semestre par", "2", "2o", "2o semestre", "segundo semestre"),
})


class DisciplinaImporter(CsvImporter[DisciplinaCsv]):
    """
    `codigo`, `nome` e `tipo` são obrigatórios. `tipo` NÃO tem padrão de propósito:
    ele decide o cálculo de progresso, e assumir "obrigatória" seria inventar.
    Créditos, carga horária, período, cor e periodicidade em branco = desconhecido.

    `periodicidade`: em que períodos letivos a disciplina é oferecida — `sempre`, `impar`
    (só "AAAA/1", "AAAA/3"…) ou `par` (só "AAAA/2"…). Vazio NÃO vira "sempre": o simulador
    então estima pela paridade do período sugerido e avisa que é estimativa.
    """

    arquivo = "disciplinas.csv"
    esquema = Esquema(
        obrigatorias=("codigo", "nome", "tipo"),
        opcionais=("creditos", "carga_h", "periodo_sugerido", "cor", "periodicidade"),
        aliases={"cod": "codigo", "codigo_disciplina": "codigo", "disciplina": "nome",
                 "credito": "creditos", "carga_horaria": "carga_h", "ch": "carga_h",
                 "periodo": "periodo_sugerido", "semestre": "periodo_sugerido",
                 "oferta": "periodicidade", "paridade": "periodicidade", "periodo_oferta": "periodicidade",
                 "oferecida": "periodicidade", "oferecimento": "periodicidade"},
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
            periodicidade=leitor.escolha("periodicidade", PERIODICIDADES, obrigatorio=False),
        )

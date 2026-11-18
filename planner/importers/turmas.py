"""Importador de `turmas.csv`: a oferta de um período letivo (turmas + encontros)."""
from __future__ import annotations

from .base import Esquema
from .campos import LeitorLinha
from .horarios import parse_horarios
from .importador import CsvImporter
from .registros import TurmaCsv


class TurmaImporter(CsvImporter[TurmaCsv]):
    """
    Uma linha = UMA turma (uma opção de matrícula); o `|` em `horarios` separa os
    encontros dela, todos obrigatórios. Alternativas de oferta = linhas distintas.
    `codigo_turma` é obrigatório (identifica a opção; ex.: T1, T2, P1) e não é
    assumido. `local` (sala) é opcional e vale para todos os encontros da turma.
    Turma sem horários é aceita com aviso: não aparece no calendário.
    """

    arquivo = "turmas.csv"
    esquema = Esquema(
        obrigatorias=("disciplina", "periodo_letivo", "codigo_turma"),
        opcionais=("docente", "vagas", "horarios", "local"),
        aliases={"codigo": "disciplina", "codigo_disciplina": "disciplina", "turma": "codigo_turma",
                 "periodo": "periodo_letivo", "horario": "horarios", "professor": "docente",
                 "sala": "local"},
    )

    def converter(self, leitor: LeitorLinha) -> TurmaCsv:
        encontros = self._ler_encontros(leitor)
        return TurmaCsv(
            linha=leitor.numero,
            disciplina=leitor.codigo("disciplina"),
            periodo_letivo=leitor.periodo_letivo("periodo_letivo", obrigatorio=True),
            codigo_turma=leitor.codigo("codigo_turma", max_len=20),
            docente=leitor.texto("docente", max_len=200),
            vagas=leitor.inteiro("vagas"),
            encontros=encontros,
            local=leitor.texto("local", max_len=100),
        )

    @staticmethod
    def _ler_encontros(leitor: LeitorLinha) -> tuple:
        texto = leitor.bruto("horarios")
        if texto is None:
            leitor.aviso("horarios", "Turma sem horários: não aparecerá no calendário nem nos conflitos.")
            return ()
        encontros, erros = parse_horarios(texto)
        for mensagem in erros:
            leitor.erro("horarios", mensagem)
        return encontros

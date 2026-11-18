"""
Parser da coluna `horarios` dos CSVs: `"SEG 16:00-18:00 | QUI 14:00-16:00"`.

Cada `|` separa um encontro da MESMA turma (todos obrigatórios). Alternativas
de matrícula são linhas diferentes do `turmas.csv`, nunca `|`.
"""
from __future__ import annotations

import re
from datetime import time

from ..domain.entidades import Encontro
from .leitor_csv import normalizar

# Siglas e nomes por extenso aceitos → sigla oficial (planner/models/enums.py: DiaSemana).
_DIAS = {
    "seg": "SEG", "segunda": "SEG", "ter": "TER", "terca": "TER", "qua": "QUA", "quarta": "QUA",
    "qui": "QUI", "quinta": "QUI", "sex": "SEX", "sexta": "SEX",
    "sab": "SAB", "sabado": "SAB", "dom": "DOM", "domingo": "DOM",
}
DIAS_VALIDOS = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")

_ENCONTRO = re.compile(
    r"^(?P<dia>[^\W\d_]+(?:-feira)?)\s+(?P<ini>\d{1,2}:\d{2})\s*[-–—]\s*(?P<fim>\d{1,2}:\d{2})$"
)


def parse_dia(texto: str) -> str | None:
    """'Seg', 'SÁB', 'terça-feira' → 'SEG', 'SAB', 'TER'; desconhecido → None."""
    return _DIAS.get(normalizar(texto).removesuffix("-feira"))


def _parse_hora(texto: str) -> time | None:
    horas, minutos = (int(p) for p in texto.split(":"))
    return time(horas, minutos) if horas < 24 and minutos < 60 else None


def parse_horarios(texto: str) -> tuple[tuple[Encontro, ...], list[str]]:
    """
    Converte o texto em encontros. Retorna `(encontros, erros)`; se houver
    qualquer erro, quem chama deve descartar a linha inteira (a turma é um todo:
    importar só parte dos encontros daria uma grade falsa).
    """
    encontros: list[Encontro] = []
    erros: list[str] = []
    for parte in (p.strip() for p in texto.split("|")):
        if not parte:
            continue  # "SEG 08:00-10:00 |" (barra sobrando) não é problema
        casou = _ENCONTRO.match(parte)
        if not casou:
            erros.append(f"Horário '{parte}' fora do formato 'DIA HH:MM-HH:MM' (ex.: SEG 16:00-18:00).")
            continue
        dia = parse_dia(casou["dia"])
        inicio, fim = _parse_hora(casou["ini"]), _parse_hora(casou["fim"])
        if dia is None:
            erros.append(f"Dia '{casou['dia']}' inválido em '{parte}' (use SEG, TER, QUA, QUI, SEX, SAB ou DOM).")
        elif inicio is None or fim is None:
            erros.append(f"Hora inexistente em '{parte}' (use 00:00 a 23:59).")
        elif fim <= inicio:
            erros.append(f"Em '{parte}' o fim deve ser depois do início.")
        else:
            encontros.append(Encontro(dia=dia, inicio=inicio, fim=fim))
    return tuple(encontros), erros

"""
Importadores CSV: parse → validação → prévia → commit (Etapa 3).

Etapa 3A: leitura e validação de SCHEMA de cada arquivo, isoladamente.
Nada é gravado no banco; referências entre arquivos e duplicatas são da 3B.
"""
from __future__ import annotations

from .base import Esquema, Issue, LinhaCsv, ResultadoLeitura, Severidade
from .curso import CursoImporter
from .disciplinas import DisciplinaImporter
from .importador import CsvImporter
from .requisitos import RequisitoImporter
from .turmas import TurmaImporter

# Ordem de dependência: o catálogo vem antes de quem o referencia.
IMPORTADORES: dict[str, CsvImporter] = {
    imp.arquivo: imp
    for imp in (CursoImporter(), DisciplinaImporter(), RequisitoImporter(),
                TurmaImporter())
}

__all__ = [
    "CsvImporter", "Esquema", "IMPORTADORES", "Issue", "LinhaCsv", "ResultadoLeitura", "Severidade",
    "CursoImporter", "DisciplinaImporter", "RequisitoImporter", "TurmaImporter",
]

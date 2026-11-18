"""
Validação referencial/semântica e prévia (dry-run) da importação — Etapa 3B.

Entrada: `ResultadoLeitura` de cada CSV (3A) + `EstadoExistente` do curso.
Saída: `ImportPreview`. Nada é gravado; este pacote só usa dados simples
(sem SQLAlchemy/Flask) — o serviço `previa_importacao` monta o estado a partir do banco.
"""
from __future__ import annotations

from .estado import (CursoExistente, DisciplinaExistente, EstadoExistente, RequisitoExistente,
                     TurmaExistente)
from .pipeline import estagios_padrao, gerar_previa
from .previa import ATUALIZAR, INALTERADO, NOVO, ImportPreview, ItemPrevia, Mudanca, PreviaArquivo

__all__ = [
    "ATUALIZAR", "INALTERADO", "NOVO", "CursoExistente", "DisciplinaExistente", "EstadoExistente",
    "ImportPreview", "ItemPrevia", "Mudanca", "PreviaArquivo", "RequisitoExistente", "TurmaExistente",
    "estagios_padrao", "gerar_previa",
]

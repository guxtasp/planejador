"""
Formato JSON do histórico (Etapa 5B-2): valida o corpo da requisição e
serializa a tentativa. Sem SQLAlchemy/Flask — testável sem banco.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..api.errors import AppError
from ..domain.entidades import STATUS_VALIDOS
from ..domain.previsao import normalizar_periodo

NOTA_MAXIMA = 100   # mesmo limite do CHECK do banco; a escala (0–10, 0–100) é do curso


@dataclass(frozen=True)
class TentativaEntrada:
    disciplina_id: int | None
    status: str
    periodo_letivo: str | None
    nota: float | None


def ler_tentativa(payload, *, com_disciplina: bool) -> TentativaEntrada:
    """
    Valida uma tentativa. `com_disciplina=False` é a edição (PUT): a disciplina de uma
    tentativa não muda; para trocar, remove-se e cria-se outra.
    """
    if not isinstance(payload, dict):
        raise AppError("Envie os dados da tentativa em JSON.")

    disciplina_id = None
    if com_disciplina:
        disciplina_id = payload.get("disciplina_id")
        if isinstance(disciplina_id, bool) or not isinstance(disciplina_id, int):
            raise AppError("Escolha a disciplina.")

    status = payload.get("status")
    if status not in STATUS_VALIDOS:
        raise AppError(f"Status inválido. Use: {', '.join(STATUS_VALIDOS)}.")

    periodo = payload.get("periodo_letivo")
    if periodo is not None and not isinstance(periodo, str):
        raise AppError("Período letivo inválido. Use AAAA/N, por exemplo 2026/1.")
    periodo = (periodo or "").strip() or None
    if periodo is not None:
        canonico = normalizar_periodo(periodo)
        if canonico is None:
            raise AppError("Período letivo inválido. Use AAAA/N, por exemplo 2026/1.")
        periodo = canonico

    nota = payload.get("nota")
    if nota is not None:
        if isinstance(nota, bool) or not isinstance(nota, (int, float)) or not math.isfinite(nota):
            raise AppError("Nota inválida.")
        if not 0 <= nota <= NOTA_MAXIMA:
            raise AppError(f"A nota deve estar entre 0 e {NOTA_MAXIMA}.")
        nota = round(float(nota), 2)

    return TentativaEntrada(disciplina_id, status, periodo, nota)


def serializar_tentativa(h) -> dict:
    """`h` é um `Historico` com a disciplina carregada. Desconhecido sai `null` (nunca 0)."""
    d = h.disciplina
    return {
        "id": h.id,
        "disciplina_id": h.disciplina_id,
        "codigo": d.codigo, "nome": d.nome,
        "creditos": d.creditos, "periodo_sugerido": d.periodo_sugerido,
        "status": h.status,
        "periodo_letivo": h.periodo_letivo,
        "nota": h.nota,
    }

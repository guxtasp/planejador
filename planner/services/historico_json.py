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


# ── histórico colado do sistema acadêmico ─────────────────────────────────────
MAX_TEXTO_COLADO = 100_000
STATUS_TXT = {"aprovado": "Aprovado", "reprovado": "Reprovado", "cursando": "Cursando"}


def ler_texto_colado(payload) -> tuple[str, bool]:
    """`{"texto": "...", "confirmar": bool}` → (texto, confirmar)."""
    from ..api.errors import AppError
    if not isinstance(payload, dict):
        raise AppError("Envie um objeto JSON com o campo `texto`.", 422, {"campo": "texto"})
    texto = payload.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        raise AppError("Cole a tabela do sistema acadêmico (código, período, situação e nota).", 422, {"campo": "texto"})
    if len(texto) > MAX_TEXTO_COLADO:
        raise AppError("Texto grande demais: cole só a tabela de disciplinas.", 422, {"campo": "texto"})
    return texto, bool(payload.get("confirmar"))


def previa_colado_json(linhas: list[dict], gravadas: int | None) -> dict:
    """`linhas` = [{numero, texto, codigo, periodo_letivo, status, nota, resultado, motivo, disciplina?}]."""
    conta = {k: sum(1 for x in linhas if x["resultado"] == k)
             for k in ("reconhecida", "nao_encontrada", "duplicada", "nao_entendida")}
    partes = [f"{conta['reconhecida']} reconhecida{'s' if conta['reconhecida'] != 1 else ''}"]
    if conta["nao_encontrada"]:
        partes.append(f"{conta['nao_encontrada']} não encontrada{'s' if conta['nao_encontrada'] > 1 else ''} no curso")
    if conta["duplicada"]:
        partes.append(f"{conta['duplicada']} repetida{'s' if conta['duplicada'] > 1 else ''} (já no histórico ou na colagem)")
    if conta["nao_entendida"]:
        partes.append(f"{conta['nao_entendida']} não entendida{'s' if conta['nao_entendida'] > 1 else ''}")
    resumo = ", ".join(partes) + "."
    if gravadas is not None:
        resumo = f"{gravadas} tentativa{'s' if gravadas != 1 else ''} adicionada{'s' if gravadas != 1 else ''} ao histórico."
    elif not linhas:
        resumo = "Não achamos nenhuma linha com código de disciplina. Confira se colou a tabela inteira."
    return {"linhas": linhas, "totais": conta, "resumo": resumo, "gravadas": gravadas,
            "pode_confirmar": gravadas is None and conta["reconhecida"] > 0}

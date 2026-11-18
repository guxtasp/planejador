"""
Formato JSON da análise de plano (Etapa 4B): lê o corpo da requisição e
serializa o resultado do domínio. Sem SQLAlchemy/Flask — testável sem banco.
"""
from __future__ import annotations

from typing import Mapping

from ..api.errors import AppError
from ..domain import analise as dom
from ..domain.conflitos import Conflito
from ..domain.entidades import Disciplina, Encontro
from ..domain.grade import DIAS_ORDEM

MAX_SEMESTRES = 20
MAX_ITENS_POR_SEMESTRE = 40
MAX_ENCONTROS_LIVRES = 14   # 7 dias x 2 turnos: mais que isso é erro de digitação


def _hora(v, onde: str):
    from datetime import time
    try:
        hh, mm = str(v).split(":")
        if not (hh.isdigit() and mm.isdigit() and len(mm) == 2):
            raise ValueError
        return time(int(hh), int(mm))
    except (ValueError, TypeError):
        raise AppError(f"{onde}: horário inválido. Use HH:MM, por exemplo 14:00.", 422) from None


def ler_encontros_livres(brutos, onde: str) -> tuple[Encontro, ...]:
    """
    Horários próprios de uma disciplina: `[{"dia":"SEG","inicio":"14:00","fim":"16:00"}]`.
    Vazio/ausente = nenhum. Dia da semana válido, início < fim, sem sobreposição
    entre si (a mesma disciplina não conflita consigo mesma).
    """
    if brutos in (None, []):
        return ()
    if not isinstance(brutos, list):
        raise AppError(f"{onde}: `encontros_livres` deve ser uma lista.")
    if len(brutos) > MAX_ENCONTROS_LIVRES:
        raise AppError(f"{onde}: no máximo {MAX_ENCONTROS_LIVRES} horários por disciplina.")
    encontros: list[Encontro] = []
    for e in brutos:
        if not isinstance(e, dict):
            raise AppError(f"{onde}: formato de horário inválido.")
        dia = e.get("dia")
        if dia not in DIAS_ORDEM:
            raise AppError(f"{onde}: dia inválido. Use {', '.join(DIAS_ORDEM)}.", 422)
        inicio, fim = _hora(e.get("inicio"), onde), _hora(e.get("fim"), onde)
        if inicio >= fim:
            raise AppError(f"{onde}: o horário deve terminar depois de começar.", 422)
        novo = Encontro(dia, inicio, fim)
        if any(o.dia == dia and o.inicio < fim and o.fim > inicio for o in encontros):
            raise AppError(f"{onde}: dois horários da mesma disciplina se sobrepõem.", 422)
        encontros.append(novo)
    return tuple(encontros)


def encontros_para_json(encontros) -> list[dict]:
    return [{"dia": e.dia, "inicio": _hhmm(e.inicio), "fim": _hhmm(e.fim)} for e in encontros]


def ler_payload(payload) -> list[dom.SemestrePlano]:
    """Valida o formato. Só o que é estruturalmente inválido vira erro 400."""
    brutos = payload.get("semestres") if isinstance(payload, dict) else None
    if not isinstance(brutos, list):
        raise AppError("Envie {\"semestres\": [...]}.")
    if len(brutos) > MAX_SEMESTRES:
        raise AppError(f"No máximo {MAX_SEMESTRES} semestres por análise.")

    def inteiro(v, onde):
        if isinstance(v, bool) or not isinstance(v, int):
            raise AppError(f"{onde} deve ser um número inteiro.")
        return v

    resultado = []
    for i, s in enumerate(brutos, start=1):
        if not isinstance(s, dict) or not isinstance(s.get("itens", []), list):
            raise AppError(f"Semestre {i}: formato inválido.")
        itens_brutos = s.get("itens", [])
        if len(itens_brutos) > MAX_ITENS_POR_SEMESTRE:
            raise AppError(f"Semestre {i}: no máximo {MAX_ITENS_POR_SEMESTRE} disciplinas.")
        periodo = s.get("periodo_letivo")
        if periodo is not None and not isinstance(periodo, str):
            raise AppError(f"Semestre {i}: período letivo inválido.")
        itens = []
        for item in itens_brutos:
            if not isinstance(item, dict):
                raise AppError(f"Semestre {i}: formato de disciplina inválido.")
            turma = item.get("turma_id")
            itens.append(dom.ItemPlano(
                inteiro(item.get("disciplina_id"), f"Semestre {i}: disciplina_id"),
                None if turma is None else inteiro(turma, f"Semestre {i}: turma_id"),
                ler_encontros_livres(item.get("encontros_livres"), f"Semestre {i}"),
            ))
        resultado.append(dom.SemestrePlano(tuple(itens), periodo or None))
    return resultado


def _hhmm(t) -> str:
    return t.strftime("%H:%M")


def _ref(d: Disciplina) -> dict:
    return {"id": d.id, "codigo": d.codigo, "nome": d.nome}


def contar_problemas(a: dom.AnaliseSemestre) -> int:
    return len(a.conflitos) + len(a.pendencias) + int(a.carga.sobrecarga)


def serializar_semestre(a: dom.AnaliseSemestre, disciplinas: Mapping[int, Disciplina]) -> dict:
    def conflito(c: Conflito) -> dict:
        s = c.sobreposicoes[0]   # um exemplo basta para a mensagem
        return {
            "tipo": c.tipo,
            "a": _ref(disciplinas[c.disciplina_a]), "b": _ref(disciplinas[c.disciplina_b]),
            "dia": s.dia,
            "horario_a": f"{_hhmm(s.a.inicio)}–{_hhmm(s.a.fim)}",
            "horario_b": f"{_hhmm(s.b.inicio)}–{_hhmm(s.b.fim)}",
        }

    return {
        "posicao": a.posicao,
        "creditos": a.carga.creditos, "limite_creditos": a.carga.limite,
        "sobrecarga": a.carga.sobrecarga,
        "disciplinas_sem_creditos": list(a.carga.disciplinas_sem_creditos),
        "conflitos": [conflito(c) for c in a.conflitos],
        "pendencias": [
            {
                "disciplina": _ref(disciplinas[p.disciplina_id]),
                "tipo": p.pendencia.tipo,
                "e_alternativa": p.pendencia.e_alternativa,
                "alternativas": [_ref(disciplinas[i]) for i in p.pendencia.alternativas if i in disciplinas],
            }
            for p in a.pendencias
        ],
        "sem_turma_escolhida": list(a.sem_turma_escolhida),
        "invalidos": [
            {"disciplina_id": i.disciplina_id, "turma_id": i.turma_id, "motivo": i.motivo}
            for i in a.invalidos
        ],
    }

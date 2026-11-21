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
                bool(item.get("turma_auto")),
            ))
        resultado.append(dom.SemestrePlano(tuple(itens), periodo or None))
    return resultado


def _hhmm(t) -> str:
    return t.strftime("%H:%M")


def _ref(d: Disciplina) -> dict:
    return {"id": d.id, "codigo": d.codigo, "nome": d.nome}


# ── marcas do item: choque, disponibilidade, horário desconhecido, optativa ──
_DIA_CURTO = {"SEG": "Seg", "TER": "Ter", "QUA": "Qua", "QUI": "Qui", "SEX": "Sex", "SAB": "Sáb", "DOM": "Dom"}


def _h(t) -> str:
    return f"{t.hour}" if t.minute == 0 else f"{t.hour}:{t.minute:02d}"


def marcas_do_item(choques, bate_indisponivel: bool, horario_origem: str, tipo: str, creditos,
                   disciplinas: Mapping[int, Disciplina], nao_cabe: bool = False, turma_que_cabe: str | None = None,
                   checa_disponibilidade: bool = False, junto_com=()) -> dict:
    """
    O que o cartão da disciplina mostra, já em texto (a tela não recalcula). Regra única para
    simulação, sugestão, Planejamento e Calendário:
      vermelho  "Choque com XXX (Seg 14–16)"          — os dois horários são reais/próprios;
      amarelo   "Possível choque com XXX (…)"          — algum horário é projeção;
      vermelho  "Bate com sua disponibilidade";
      cinza     "Sem horário — choque não verificado"  — nunca parece "sem choque" quando não deu para checar.
    """
    lista, tags = [], []
    for c in choques:
        quem = disciplinas[c.com].codigo if c.com in disciplinas else str(c.com)
        quando = f"{_DIA_CURTO.get(c.dia, c.dia)} {_h(c.inicio)}–{_h(c.fim)}"
        texto = f"Choque com {quem} ({quando})" if c.firme else f"Possível choque com {quem} ({quando})"
        lista.append({"com": _ref(disciplinas[c.com]) if c.com in disciplinas else {"id": c.com},
                      "dia": c.dia, "horario": f"{_hhmm(c.inicio)}–{_hhmm(c.fim)}", "firme": c.firme, "texto": texto})
        tags.append({"tipo": "choque" if c.firme else "possivel_choque", "cor": "red" if c.firme else "yellow",
                     "texto": texto})
    if nao_cabe:
        tags.append({"tipo": "nao_cabe", "cor": "red", "texto": "Não cabe na sua disponibilidade"})
    elif bate_indisponivel:
        tags.append({"tipo": "disponibilidade", "cor": "red", "texto": "Bate com sua disponibilidade"})
    if turma_que_cabe:
        tags.append({"tipo": "turma_que_cabe", "cor": "yellow", "texto": f"A turma {turma_que_cabe} cabe na sua disponibilidade"})
    if horario_origem == "desconhecido":
        texto = ("Sem horário — choque e disponibilidade não verificados" if checa_disponibilidade
                 else "Sem horário — choque não verificado")
        tags.append({"tipo": "sem_horario", "cor": "gray", "texto": texto})
    if junto_com:
        nomes = ", ".join(disciplinas[i].codigo for i in junto_com if i in disciplinas)
        tags.append({"tipo": "junto", "cor": "accent", "texto": f"Junto com {nomes}"})
    if tipo != "obrigatoria":
        tags.append({"tipo": "optativa", "cor": "accent",
                     "texto": f"Optativa{f' · {creditos} cr' if creditos else ''}"})
    return {"choques": lista, "tags": tags}


def contar_problemas(a: dom.AnaliseSemestre) -> int:
    return len(a.conflitos) + len(a.pendencias) + int(a.carga.sobrecarga)


def serializar_semestre(a: dom.AnaliseSemestre, disciplinas: Mapping[int, Disciplina],
                        codigo_turma: Mapping[int, str] | None = None, checa_disponibilidade: bool = False,
                        junto_com: Mapping[int, tuple[int, ...]] | None = None) -> dict:
    codigo_turma = codigo_turma or {}
    junto_com = junto_com or {}
    def conflito(c: Conflito) -> dict:
        s = c.sobreposicoes[0]   # um exemplo basta para a mensagem
        return {
            "tipo": c.tipo,
            "a": _ref(disciplinas[c.disciplina_a]), "b": _ref(disciplinas[c.disciplina_b]),
            "dia": s.dia,
            "horario_a": f"{_hhmm(s.a.inicio)}–{_hhmm(s.a.fim)}",
            "horario_b": f"{_hhmm(s.b.inicio)}–{_hhmm(s.b.fim)}",
        }

    n_choques = sum(len(m.choques) for m in (a.marcas or {}).values()) // 2   # cada choque aparece nos 2 lados
    return {
        "posicao": a.posicao,
        "n_choques": n_choques,
        "choques_texto": f"{n_choques} choque{'s' if n_choques > 1 else ''}" if n_choques else None,
        "creditos": a.carga.creditos, "limite_creditos": a.carga.limite,
        "creditos_no_limite": a.carga.creditos_no_limite,
        "creditos_fora_do_limite": a.carga.creditos - a.carga.creditos_no_limite,
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
        # disciplina → tags prontas (mesma regra e texto do simulador)
        "marcas": {
            str(d): {
                **marcas_do_item(m.choques, m.bate_indisponivel, "desconhecido" if m.sem_horario else
                                 ("real" if m.firme else "projetado"),
                                 disciplinas[d].tipo, disciplinas[d].creditos, disciplinas, m.nao_cabe,
                                 codigo_turma.get(m.turma_que_cabe), checa_disponibilidade,
                                 junto_com.get(d, ())),
                "turma_que_cabe": m.turma_que_cabe, "nao_cabe": m.nao_cabe,
                "turma_sugerida": m.turma_sugerida, "turma_projetada": m.turma_projetada,
            }
            for d, m in (a.marcas or {}).items() if d in disciplinas
        },
    }

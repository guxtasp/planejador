"""
Formato JSON do simulador e da sugestão de plano (Peças 3 e 4, parte C).

Lê o corpo das requisições e serializa o resultado do domínio. Sem SQLAlchemy/Flask:
testável sem banco.

Cada risco e cada cenário saem com `mensagem` (o que está acontecendo) e, quando há, `acao`
(o que fazer a respeito), já em português. A tela só mostra; assim o texto fica num lugar
só e é testado. Regra do feedback: nunca devolver só um código ("fora_de_oferta"), sempre
a frase que a pessoa lê.
"""
from __future__ import annotations

from datetime import time as _hora
from typing import Mapping, Sequence

from ..api.errors import AppError
from ..domain import analise as dom
from ..domain.entidades import Disciplina
from ..domain.otimizador import (LIM_CREDITOS, LIM_OFERTA, LIM_REQUISITOS, M_CICLO, M_INALCANCAVEL,
                                 M_SEM_SOLUCAO, ResultadoOtimizacao)
from ..domain.periodicidade import paridade_do_periodo
from ..domain.previsao import normalizar_periodo, somar_periodos
from ..domain.simulacao import (PREMISSA_CURSANDO, PREMISSA_HORARIO_PROJETADO, PREMISSA_OFERTA_ESTIMADA,
                                PREMISSA_PLANEJADO, R_CONFLITO, R_FALTAM_OBRIGATORIAS, R_FORA_DE_OFERTA,
                                R_HORARIO_DESCONHECIDO, R_HORARIO_PROJETADO, R_INDISPONIVEL, R_JA_CURSADA,
                                R_OFERTA_DESCONHECIDA, R_OFERTA_ESTIMADA, R_PERIODO_FORA_DE_ORDEM, R_PESADAS,
                                R_PRAZO_MAXIMO, R_PRAZO_REGULAR, R_PRE_REQUISITO, R_SEM_TURMA_NO_QUADRO,
                                R_SEMESTRE_TRANCADO, R_SOBRECARGA, R_FALTAM_OPTATIVAS, R_GRUPO_IMPOSSIVEL,
                                R_JUNTAS_SEPARADAS, R_FIM_CEDO, R_FIXA_FORA, Risco, Simulacao,
                                GRAVIDADE_ALTA, GRAVIDADE_BAIXA)

from ..domain.monte_carlo import N_PADRAO, ResultadoMonteCarlo
from ..domain.prazo import FATOR_PADRAO, AvaliacaoPrazo
from ..domain.preferencias import REGRA_OBRIGATORIA, REGRAS_JUNTO, GrupoJunto
from ..domain.semana import TURNOS, BlocoIndisponivel, MetricasSemana, PreferenciasSemana
from .analise_json import _hhmm, ler_payload, marcas_do_item

MAX_EXTRAS = 4              # folga voluntária máxima na sugestão (semestres a mais)
MAX_CREDITOS = 60
MAX_OPTATIVAS_ESCOLHIDAS = 30
MAX_OPTATIVAS_FEITAS = 120
MAX_CREDITOS_OPTATIVOS = 120

_PARIDADE = {"impar": "ímpar", "par": "par"}
_PERIODICIDADE_TXT = {"impar": "só em períodos ímpares (AAAA/1)", "par": "só em períodos pares (AAAA/2)",
                      "sempre": "todo período"}

PREMISSAS_TXT = {
    PREMISSA_CURSANDO: "O que você está cursando agora conta como concluído quando o plano começa.",
    PREMISSA_PLANEJADO: "O que está planejado em um semestre conta como concluído nos seguintes "
                        "(a simulação não assume reprovação, a não ser no bloco “E se eu reprovar?”).",
    PREMISSA_HORARIO_PROJETADO: "Horários de períodos futuros são PROJEÇÃO: copiamos os do último período "
                                "de mesma paridade. O quadro real pode mudar.",
    PREMISSA_OFERTA_ESTIMADA: "Quando o curso não informa em que períodos a disciplina abre, estimamos pelo "
                              "período sugerido na matriz. Informe a oferta em Disciplinas para ficar exato.",
}


# ── leitura dos pedidos ──────────────────────────────────────────────────────
def _periodo_opcional(valor, onde: str) -> str | None:
    if valor in (None, ""):
        return None
    if not isinstance(valor, str):
        raise AppError(f"{onde}: período inválido. Use AAAA/N, por exemplo 2027/1.", 422)
    normal = normalizar_periodo(valor)
    if normal is None:
        raise AppError(f"{onde}: período inválido. Use AAAA/N, por exemplo 2027/1.", 422)
    return normal


def ler_pedido_simulacao(payload) -> tuple[list[dom.SemestrePlano], str | None]:
    """`{"semestres": [...], "periodo_inicial": "2027/1"?}` → (semestres, período inicial)."""
    semestres = ler_payload(payload)
    # normaliza os períodos digitados à mão ("2027.1" → "2027/1"); inválido é erro claro, não silêncio
    normalizados = []
    for i, s in enumerate(semestres, start=1):
        periodo = _periodo_opcional(s.periodo_letivo, f"Semestre {i}")
        normalizados.append(dom.SemestrePlano(s.itens, periodo))
    inicial = _periodo_opcional(payload.get("periodo_inicial"), "Período inicial")
    return normalizados, inicial


def _inteiro_opcional(valor, onde: str, minimo: int, maximo: int) -> int | None:
    if valor in (None, ""):
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise AppError(f"{onde} deve ser um número inteiro.", 422)
    if not minimo <= valor <= maximo:
        raise AppError(f"{onde} deve ficar entre {minimo} e {maximo}.", 422)
    return valor


def ler_pedido_sugestao(payload) -> dict:
    """
    `{"periodo_inicial"?, "max_creditos"?, "semestres_extras"?, "optativas"?: [ids],
    "optativas_faltando"?: créditos, "optativas_feitas"?: [ids]}`.
    Tudo opcional; o serviço completa o que faltar com o curso e o histórico.
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise AppError("Envie um objeto JSON com os parâmetros da sugestão.")
    optativas = payload.get("optativas", [])
    if not isinstance(optativas, list) or len(optativas) > MAX_OPTATIVAS_ESCOLHIDAS:
        raise AppError(f"`optativas` deve ser uma lista com no máximo {MAX_OPTATIVAS_ESCOLHIDAS} disciplinas.")
    if any(isinstance(i, bool) or not isinstance(i, int) for i in optativas):
        raise AppError("`optativas` deve conter apenas números inteiros (ids de disciplina).")
    feitas = payload.get("optativas_feitas", [])
    if not isinstance(feitas, list) or len(feitas) > MAX_OPTATIVAS_FEITAS:
        raise AppError(f"`optativas_feitas` deve ser uma lista com no máximo {MAX_OPTATIVAS_FEITAS} disciplinas.")
    if any(isinstance(i, bool) or not isinstance(i, int) for i in feitas):
        raise AppError("`optativas_feitas` deve conter apenas números inteiros (ids de disciplina).")
    return {
        "periodo_inicial": _periodo_opcional(payload.get("periodo_inicial"), "Período inicial"),
        "max_creditos": _inteiro_opcional(payload.get("max_creditos"), "O limite de créditos", 1, MAX_CREDITOS),
        "semestres_extras": _inteiro_opcional(payload.get("semestres_extras"), "A folga", 0, MAX_EXTRAS) or 0,
        "optativas": sorted(set(optativas)),
        # None = o app calcula (exigido pelo curso − cursadas); número = vale o que a pessoa disse
        "optativas_faltando": _inteiro_opcional(payload.get("optativas_faltando"),
                                                "Os créditos de optativas que faltam", 0, MAX_CREDITOS_OPTATIVOS),
        "optativas_feitas": sorted(set(feitas)),
    }


# ── preferências do aluno (simular e sugerir) ────────────────────────────────
DIAS_SEMANA = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")
MAX_BLOCOS = 40
MAX_PERIODOS_PREF = 20
MAX_PESADAS_MARCADAS = 100
MIN_SIMULACOES, MAX_SIMULACOES = 50, 2000
_TURNO_TXT = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}


def _erro_campo(msg: str, campo: str) -> AppError:
    """Erro de um campo específico: a tela mostra a mensagem junto ao campo (`detalhes.campo`)."""
    return AppError(msg, 422, {"campo": campo})


def _hora_txt(valor, campo: str) -> _hora:
    if not isinstance(valor, str) or len(valor) != 5 or valor[2] != ":":
        raise _erro_campo("Use o horário no formato HH:MM, por exemplo 08:00.", campo)
    try:
        h, m = int(valor[:2]), int(valor[3:])
        return _hora(h, m)
    except ValueError:
        raise _erro_campo("Horário inválido. Use HH:MM entre 00:00 e 23:59.", campo) from None


def ler_preferencias(payload) -> dict:
    """
    `{"preferencias": {...}}` → dicionário pronto para o domínio. Tudo opcional:

      indisponiveis: [{dia: "SEG", inicio: "08:00", fim: "12:00", motivo?: "trabalho"}]
      turno: manha | tarde | noite;  dias_livres: ["SEX"]
      teto_por_periodo: {"2028/1": 12};  periodos_pulados: ["2028/2"]
      max_pesadas: 1..10;  pesadas: [ids que a pessoa acha pesadas]
      fator_prazo_maximo: 1.0..3.0 (padrão 1,5);  periodo_ingresso: "2024/1";  simulacoes: 50..2000
    """
    bruto = (payload or {}).get("preferencias") if isinstance(payload, dict) else None
    if bruto is None:
        bruto = {}
    if not isinstance(bruto, dict):
        raise _erro_campo("`preferencias` deve ser um objeto.", "preferencias")

    blocos = bruto.get("indisponiveis") or []
    if not isinstance(blocos, list) or len(blocos) > MAX_BLOCOS:
        raise _erro_campo(f"Horários indisponíveis: no máximo {MAX_BLOCOS} blocos.", "indisponiveis")
    lidos = []
    for k, b in enumerate(blocos):
        campo = f"indisponiveis.{k}"
        if not isinstance(b, dict):
            raise _erro_campo("Bloco indisponível inválido.", campo)
        dia = str(b.get("dia", "")).upper()
        if dia not in DIAS_SEMANA:
            raise _erro_campo("Dia inválido. Use SEG, TER, QUA, QUI, SEX, SAB ou DOM.", campo + ".dia")
        ini, fim = _hora_txt(b.get("inicio"), campo + ".inicio"), _hora_txt(b.get("fim"), campo + ".fim")
        if fim <= ini:
            raise _erro_campo("O fim do bloco precisa ser depois do início.", campo + ".fim")
        motivo = b.get("motivo")
        if motivo is not None and (not isinstance(motivo, str) or len(motivo) > 40):
            raise _erro_campo("O motivo deve ter até 40 letras.", campo + ".motivo")
        lidos.append(BlocoIndisponivel(dia, ini, fim, (motivo or "").strip() or None))

    turno = bruto.get("turno") or None
    if turno is not None and turno not in TURNOS:
        raise _erro_campo("Turno inválido. Use manhã, tarde ou noite.", "turno")
    dias_livres = bruto.get("dias_livres") or []
    if not isinstance(dias_livres, list) or any(str(d).upper() not in DIAS_SEMANA for d in dias_livres):
        raise _erro_campo("Dias livres inválidos. Use SEG, TER, QUA, QUI, SEX, SAB ou DOM.", "dias_livres")
    dias_livres = tuple(sorted({str(d).upper() for d in dias_livres}, key=DIAS_SEMANA.index))

    tetos_brutos = bruto.get("teto_por_periodo") or {}
    if not isinstance(tetos_brutos, dict) or len(tetos_brutos) > MAX_PERIODOS_PREF:
        raise _erro_campo(f"Teto por período: no máximo {MAX_PERIODOS_PREF} períodos.", "teto_por_periodo")
    tetos = {}
    try:
        for per, val in tetos_brutos.items():
            normal = _periodo_opcional(per, "Teto por período")
            tetos[normal] = _inteiro_opcional(val, f"O teto de {normal}", 1, MAX_CREDITOS)
    except AppError as e:
        raise _erro_campo(e.message, "teto_por_periodo") from None
    tetos = {k: v for k, v in tetos.items() if v is not None}

    pulados = bruto.get("periodos_pulados") or []
    if not isinstance(pulados, list) or len(pulados) > MAX_PERIODOS_PREF:
        raise _erro_campo(f"Períodos trancados: no máximo {MAX_PERIODOS_PREF}.", "periodos_pulados")
    try:
        pulados = frozenset(_periodo_opcional(x, "Período trancado") for x in pulados) - {None}
    except AppError as e:
        raise _erro_campo(e.message, "periodos_pulados") from None

    marcadas = bruto.get("pesadas") or []
    if (not isinstance(marcadas, list) or len(marcadas) > MAX_PESADAS_MARCADAS
            or any(isinstance(i, bool) or not isinstance(i, int) for i in marcadas)):
        raise _erro_campo("`pesadas` deve ser uma lista de ids de disciplina.", "pesadas")

    fator = bruto.get("fator_prazo_maximo", None)
    if fator is None:
        fator = FATOR_PADRAO
    elif isinstance(fator, bool) or not isinstance(fator, (int, float)) or not 1.0 <= fator <= 3.0:
        raise _erro_campo("O fator do prazo máximo deve ficar entre 1 e 3 (por exemplo 1,5).", "fator_prazo_maximo")

    def campo(fn, nome):
        try:
            return fn()
        except AppError as e:
            raise _erro_campo(e.message, nome) from None

    juntas_brutas = bruto.get("juntas") or []
    if not isinstance(juntas_brutas, list) or len(juntas_brutas) > 20:
        raise _erro_campo("Disciplinas para cursar juntas: no máximo 20 grupos.", "juntas")
    juntas = []
    for k, g in enumerate(juntas_brutas):
        ids = g.get("disciplinas") if isinstance(g, dict) else None
        if (not isinstance(ids, list) or len(set(ids)) < 2 or len(ids) > 6
                or any(isinstance(i, bool) or not isinstance(i, int) for i in ids)):
            raise _erro_campo("Cada grupo precisa de 2 a 6 disciplinas diferentes.", f"juntas.{k}")
        regra = g.get("regra", REGRA_OBRIGATORIA)
        if regra not in REGRAS_JUNTO:
            raise _erro_campo("A regra do grupo deve ser “obrigatoria” ou “preferencia”.", f"juntas.{k}")
        juntas.append(GrupoJunto(tuple(sorted(set(ids))), regra))

    feitas = bruto.get("optativas_feitas") or []
    if (not isinstance(feitas, list) or len(feitas) > MAX_OPTATIVAS_FEITAS
            or any(isinstance(i, bool) or not isinstance(i, int) for i in feitas)):
        raise _erro_campo("Optativas já feitas: lista de ids de disciplina.", "optativas_feitas")
    precisa = None
    try:
        precisa = _inteiro_opcional(bruto.get("optativas_faltando"), "Os créditos de optativas que faltam",
                                    0, MAX_CREDITOS_OPTATIVOS)
    except AppError as e:
        raise _erro_campo(e.message, "optativas_faltando") from None

    fixas_brutas = bruto.get("fixas") or []
    if not isinstance(fixas_brutas, list) or len(fixas_brutas) > 30:
        raise _erro_campo("Disciplinas em período específico: no máximo 30.", "fixas")
    fixas: dict[int, str] = {}
    for k, f in enumerate(fixas_brutas):
        did = f.get("disciplina_id") if isinstance(f, dict) else None
        if isinstance(did, bool) or not isinstance(did, int):
            raise _erro_campo("Escolha a disciplina.", f"fixas.{k}")
        try:
            per = _periodo_opcional(f.get("periodo"), "Período")
        except AppError as e:
            raise _erro_campo(e.message, f"fixas.{k}") from None
        if per is None:
            raise _erro_campo("Escolha o período.", f"fixas.{k}")
        fixas[did] = per

    semana = PreferenciasSemana(tuple(lidos), turno, dias_livres) if (lidos or turno or dias_livres) else None
    return {
        "fixas": fixas,
        "optativas_feitas": sorted(set(feitas)), "optativas_faltando": precisa,
        "juntas": tuple(juntas), "juntas_respondida": bool(bruto.get("juntas_respondida")),
        "semana": semana, "teto_por_periodo": tetos, "periodos_pulados": pulados,
        "max_pesadas": campo(lambda: _inteiro_opcional(bruto.get("max_pesadas"), "O máximo de disciplinas pesadas", 1, 10), "max_pesadas"),
        "pesadas_marcadas": sorted(set(marcadas)), "fator_prazo": float(fator),
        "periodo_ingresso": campo(lambda: _periodo_opcional(bruto.get("periodo_ingresso"), "Período de ingresso"), "periodo_ingresso"),
        "simulacoes": campo(lambda: _inteiro_opcional(bruto.get("simulacoes"), "O número de simulações",
                                                       MIN_SIMULACOES, MAX_SIMULACOES), "simulacoes") or N_PADRAO,
    }


def preferencias_para_salvar(bruto) -> dict:
    """Valida (mesmas regras do pedido) e devolve a forma NORMALIZADA que fica guardada no banco."""
    p = ler_preferencias({"preferencias": bruto})
    s = p["semana"]
    return {
        "indisponiveis": [{"dia": b.dia, "inicio": _hhmm(b.inicio), "fim": _hhmm(b.fim),
                           **({"motivo": b.motivo} if b.motivo else {})} for b in (s.indisponiveis if s else ())],
        "turno": s.turno if s else None, "dias_livres": list(s.dias_livres) if s else [],
        "teto_por_periodo": dict(p["teto_por_periodo"]),
        "periodos_pulados": sorted(p["periodos_pulados"], key=lambda x: tuple(int(v) for v in x.split("/"))),
        "max_pesadas": p["max_pesadas"], "pesadas": p["pesadas_marcadas"],
        "fator_prazo_maximo": p["fator_prazo"] if p["fator_prazo"] != FATOR_PADRAO else None,
        "periodo_ingresso": p["periodo_ingresso"],
        "juntas": [{"disciplinas": list(g.disciplinas), "regra": g.regra} for g in p["juntas"]],
        "juntas_respondida": p["juntas_respondida"],
        "optativas_feitas": p["optativas_feitas"], "optativas_faltando": p["optativas_faltando"],
        "fixas": [{"disciplina_id": d, "periodo": per} for d, per in sorted(p["fixas"].items())],
    }


def proximo_periodo_livre(periodos: Sequence[str | None], periodos_por_ano: int = 2) -> str | None:
    """Período seguinte ao mais recente do histórico (None se o histórico não tem períodos)."""
    validos = [p for p in (normalizar_periodo(x, periodos_por_ano) for x in periodos) if p]
    if not validos:
        return None
    ultimo = max(validos, key=lambda p: tuple(int(x) for x in p.split("/")))
    return somar_periodos(ultimo, 1, periodos_por_ano)


# ── apoio ────────────────────────────────────────────────────────────────────
def _ref(d: Disciplina) -> dict:
    return {"id": d.id, "codigo": d.codigo, "nome": d.nome}


def _nome(disciplinas: Mapping[int, Disciplina], i: int) -> str:
    d = disciplinas.get(i)
    return d.codigo if d else f"#{i}"


def _lista(nomes: Sequence[str]) -> str:
    nomes = list(nomes)
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _semestres_txt(n: int) -> str:
    return f"{n} semestre" + ("" if n == 1 else "s")


def _paridade_txt(periodo: str) -> str:
    return _PARIDADE[paridade_do_periodo(periodo)]


# ── mensagens dos riscos ─────────────────────────────────────────────────────
def mensagem_risco(r: Risco, disciplinas: Mapping[int, Disciplina]) -> tuple[str, str | None]:
    """(o que acontece, o que fazer). A ação pode ser None quando só há o que saber."""
    n = [_nome(disciplinas, i) for i in r.disciplinas]
    quem = _lista(n)
    onde = f"no semestre {r.posicao} ({r.periodo})" if r.posicao else "no plano"
    det = r.detalhe

    if r.tipo == R_FORA_DE_OFERTA:
        return (f"{quem} é ofertada {_PERIODICIDADE_TXT.get(det.get('periodicidade'), '')}, "
                f"mas o semestre {r.posicao} é {r.periodo}.",
                f"Mova {quem} para {det.get('proximo_periodo')}.")
    if r.tipo == R_OFERTA_ESTIMADA:
        return (f"Pela matriz, {quem} costuma abrir {_PERIODICIDADE_TXT.get(det.get('periodicidade'), '')}, "
                f"e {r.periodo} não está nessa regra. O curso não informou a oferta, então é uma estimativa.",
                f"Confira na tela Disciplinas; se abrir em {det.get('proximo_periodo')}, mova para lá.")
    if r.tipo == R_OFERTA_DESCONHECIDA:
        return (f"Sem informação de oferta (par/ímpar) para {quem}. A simulação não bloqueia, mas pode errar.",
                "Informe a oferta em Disciplinas (ou na coluna `periodicidade` do CSV).")
    if r.tipo == R_SEM_TURMA_NO_QUADRO:
        return (f"O quadro de {r.periodo} já foi publicado e {quem} não está nele.",
                "Escolha outro semestre ou confirme se a disciplina será ofertada.")
    if r.tipo == R_PRE_REQUISITO:
        alts = [_nome(disciplinas, i) for i in det.get("alternativas", [])]
        tipo = "correquisito" if det.get("tipo") == "co" else "pré-requisito"
        ou = " ou ".join(alts)
        return (f"{quem} exige {tipo} {ou}, que não está concluído {onde}.",
                f"Coloque {ou} em um semestre anterior." if det.get("tipo") != "co"
                else f"Coloque {ou} no mesmo semestre ou antes.")
    if r.tipo == R_CONFLITO:
        proj = " (horário projetado, não confirmado)" if det.get("projetado") else ""
        return (f"{quem} batem {onde} na {det.get('dia')}: {det.get('horario_a')} × {det.get('horario_b')}{proj}.",
                "Troque uma delas de semestre ou escolha outra turma." if not det.get("projetado")
                else "Aguarde o quadro real do período ou separe as duas por precaução.")
    if r.tipo == R_SOBRECARGA:
        qual = "o teto que você definiu para este período" if det.get("especifico") else "o limite"
        return (f"{det.get('creditos')} créditos {onde}, acima de {qual} ({det.get('limite')}).",
                "Passe uma disciplina para outro semestre.")
    if r.tipo == R_PRAZO_MAXIMO:
        est = " (estimativa)" if det.get("estimada") else ""
        return (f"Formatura em {r.periodo}{est}: {det.get('usados')} semestres, além do prazo máximo de "
                f"integralização ({det.get('maximo')} = duração × {str(det.get('fator')).replace('.', ',')}).",
                "Aumente a carga, peça uma sugestão de plano ou converse com a coordenação sobre prorrogação.")
    if r.tipo == R_PRAZO_REGULAR:
        est = " (estimativa)" if det.get("estimada") else ""
        extra = (det.get("usados") or 0) - (det.get("regular") or 0)
        return (f"Formatura em {r.periodo}{est}: {det.get('usados')} semestres, {_semestres_txt(extra)} além da "
                f"duração do curso ({det.get('regular')}).",
                "Ainda dentro do prazo máximo. Para formar no prazo, peça uma sugestão de plano.")
    if r.tipo == R_INDISPONIVEL:
        motivo = f" ({det.get('motivo')})" if det.get("motivo") else ""
        proj = " — horário projetado, pode mudar" if det.get("projetado") else ""
        return (f"{quem} cai na {det.get('dia')} {det.get('horario')}, um horário em que você não pode{motivo}{proj}.",
                "Troque a turma escolhida." if det.get("fixa")
                else "Não há outra turma neste período: mova a disciplina para outro semestre.")
    if r.tipo == R_PESADAS:
        return (f"{len(r.disciplinas)} disciplinas pesadas {onde} ({quem}); seu máximo é {det.get('maximo')}.",
                "Separe uma delas em outro semestre.")
    if r.tipo == R_FIXA_FORA:
        onde_esta = f"o plano põe em {det.get('periodo_atual')}" if det.get("periodo_atual") else "ela não está no plano"
        return (f"Você quer cursar {quem} em {det.get('periodo_pedido')}, mas {onde_esta}.",
                f"Mova para {det.get('periodo_pedido')} ou mude o pedido em Minha rotina.")
    if r.tipo == R_FIM_CEDO:
        return (f"{quem} fecha o curso, mas está {onde}, antes dos últimos semestres do plano.",
                f"Mova para o semestre {det.get('destino')} ({det.get('periodo_destino')}).")
    if r.tipo == R_JUNTAS_SEPARADAS:
        fora = [_nome(disciplinas, i) for i in det.get("fora_do_plano", [])]
        if fora:
            return (f"{quem} são para cursar juntas, mas {_lista(fora)} não está no plano.",
                    f"Adicione {_lista(fora)} ao semestre {det.get('destino')} ({r.periodo}).")
        return (f"{quem} estão em semestres diferentes, mas você quer cursá-las juntas.",
                f"Mova para o semestre {det.get('destino')} ({r.periodo}).")
    if r.tipo == R_GRUPO_IMPOSSIVEL:
        motivo = ("uma só abre em período ímpar e a outra só em par" if det.get("motivo") == "ofertas_incompativeis"
                  else f"{_nome(disciplinas, r.disciplinas[0])} exige {_nome(disciplinas, r.disciplinas[1])} antes")
        return (f"{quem} não podem ficar no mesmo semestre: {motivo}. O grupo foi ignorado.",
                "Desfaça o grupo em Preferências › Cursar junto.")
    if r.tipo == R_FALTAM_OPTATIVAS:
        return (f"Faltam {det.get('faltam')} créditos de optativas; o plano não fecha o curso "
                f"(exigidos {det.get('exigidas')}, cumpridos {det.get('cumpridas')}, "
                f"planejados {det.get('planejadas')}).",
                "Inclua optativas no plano (veja onde cabem em cada semestre) ou peça uma sugestão.")
    if r.tipo == R_SEMESTRE_TRANCADO:
        return (f"{r.periodo} está marcado como trancado, mas o plano tem disciplinas nele: {quem}.",
                "Mova essas disciplinas ou desmarque o trancamento nas preferências.")
    if r.tipo == R_PERIODO_FORA_DE_ORDEM:
        return (f"O semestre {r.posicao} ({r.periodo}) não vem depois do anterior.",
                "Ajuste o período letivo dos semestres em Planejamento.")
    if r.tipo == R_FALTAM_OBRIGATORIAS:
        return (f"O plano não inclui obrigatórias: {quem}.", "Inclua essas disciplinas ou peça uma sugestão de plano.")
    if r.tipo == R_JA_CURSADA:
        return (f"{quem} já consta como concluída ou em andamento, mas está planejada {onde}.",
                "Remova do plano, a menos que vá cursar de novo.")
    if r.tipo == R_HORARIO_PROJETADO:
        return (f"Horários {onde} são projeção do último período de mesma paridade ({quem}).", None)
    if r.tipo == R_HORARIO_DESCONHECIDO:
        return (f"Sem horário conhecido para {quem} {onde}; não dá para checar choque.",
                "Defina horários próprios no Planejamento, se quiser incluí-los na checagem.")
    return (f"Atenção {onde}: {r.tipo}.", None)


def _risco_json(r: Risco, disciplinas: Mapping[int, Disciplina]) -> dict:
    mensagem, acao = mensagem_risco(r, disciplinas)
    return {
        "tipo": r.tipo, "gravidade": r.gravidade, "posicao": r.posicao, "periodo": r.periodo,
        "disciplinas": [_ref(disciplinas[i]) for i in r.disciplinas if i in disciplinas],
        "detalhe": dict(r.detalhe), "mensagem": mensagem, "acao": acao,
    }


# ── simulação ────────────────────────────────────────────────────────────────
def _periodo_do_indice(sim: Simulacao, indice: int) -> str | None:
    if not sim.semestres:
        return None
    if indice < len(sim.semestres):
        return sim.semestres[indice].periodo
    return somar_periodos(sim.semestres[-1].periodo, indice - len(sim.semestres) + 1)


def _cenario_json(c, sim: Simulacao, disciplinas: Mapping[int, Disciplina]) -> dict:
    nome = _nome(disciplinas, c.disciplina_id)
    refaz = _periodo_do_indice(sim, c.reoferta) if c.reoferta is not None else None
    if c.reoferta is None:
        msg = f"Se você reprovar em {nome}, não há como refazer dentro do horizonte simulado."
    else:
        espera = "no semestre seguinte" if c.espera == 1 else f"daqui a {_semestres_txt(c.espera or 0)}"
        msg = f"Se você reprovar em {nome}, refaz em {refaz} ({espera})"
        msg += (f" e a formatura atrasa {_semestres_txt(c.atraso)}." if c.atraso
                else " e a formatura não muda.")
    return {
        "disciplina": _ref(disciplinas[c.disciplina_id]), "atraso": c.atraso,
        "refaz_em": refaz, "espera": c.espera,
        "novo_fim": _periodo_do_indice(sim, c.novo_fim) if c.novo_fim >= 0 else None,
        "afetadas": [_ref(disciplinas[i]) for i in c.afetadas if i in disciplinas],
        "mensagem": msg,
    }


def _critico_json(c, disciplinas: Mapping[int, Disciplina], inicio: str) -> dict:
    def ref(i):
        return _ref(disciplinas[i])

    return {
        "menor_semestres": c.menor_semestres, "menor_sem_calendario": c.menor_sem_calendario,
        "custo_da_oferta": (None if c.menor_semestres is None or c.menor_sem_calendario is None
                            else c.menor_semestres - c.menor_sem_calendario),
        "etapas": [{"indice": i, "periodo": somar_periodos(inicio, i),
                    "disciplinas": [ref(d) for d in ids if d in disciplinas]} for i, ids in c.etapas],
        "gargalos": [{"disciplina": ref(d), "dependentes": n} for d, n in c.gargalos if d in disciplinas],
        "ciclos": [[ref(d) for d in ciclo if d in disciplinas] for ciclo in c.ciclos],
        "inalcancaveis": [ref(d) for d in c.inalcancaveis if d in disciplinas],
        "cadeia": [{"disciplina": ref(d), "periodo": somar_periodos(inicio, i)}
                   for d, i in c.cadeia if d in disciplinas],
        "cadeia_mensagem": mensagem_cadeia([d for d, _ in c.cadeia], disciplinas),
    }


def mensagem_cadeia(ids: Sequence[int], disciplinas: Mapping[int, Disciplina]) -> str | None:
    """Frase da cadeia crítica: "Cálculo I → Cálculo II → Cálculo III define o prazo"."""
    nomes = [disciplinas[i].nome for i in ids if i in disciplinas]
    if len(nomes) < 2:
        return None
    return f"{' → '.join(nomes)} define o prazo: atrasar qualquer uma atrasa a formatura."


def optativas_json(r) -> dict:
    """Resumo das optativas na simulação (nada afirmado se o curso não informa o exigido)."""
    if r.optativas_informadas is not None:
        msg = (f"Você informou na sua rotina que ainda precisa de {r.optativas_informadas} créditos de optativas; "
               f"o plano tem {r.optativas_planejadas}.")
        msg += (f" Faltam {r.optativas_faltam}" + (f"; com elas, formatura em {r.formatura_com_optativas}." if
                r.formatura_com_optativas else ".")) if r.optativas_faltam else " Optativas fechadas."
        return {"exigidas": r.optativas_exigidas, "cumpridas": r.optativas_cumpridas,
                "planejadas": r.optativas_planejadas, "faltam": r.optativas_faltam, "origem": "informado",
                "so_obrigatorias": r.formatura_so_obrigatorias, "com_optativas": r.formatura_com_optativas,
                "mensagem": msg}
    if r.optativas_exigidas is None:
        return {"exigidas": None, "cumpridas": r.optativas_cumpridas, "planejadas": r.optativas_planejadas,
                "faltam": None, "so_obrigatorias": r.formatura_so_obrigatorias, "com_optativas": None,
                "mensagem": "O curso não informa quantos créditos de optativas exige "
                            "(creditos_optativos_exigidos em curso.csv): não dá para dizer se faltam. "
                            "Se você sabe, informe em Minha rotina › Optativas."}
    if r.optativas_faltam:
        msg = (f"Faltam {r.optativas_faltam} créditos de optativas (exigidos {r.optativas_exigidas}, "
               f"cumpridos {r.optativas_cumpridas}, planejados {r.optativas_planejadas}).")
        if r.formatura_com_optativas:
            msg += f" Com elas, formatura em {r.formatura_com_optativas}."
    else:
        msg = (f"Optativas fechadas: {r.optativas_cumpridas} cumpridos + {r.optativas_planejadas} planejados "
               f"de {r.optativas_exigidas} exigidos.")
    return {"exigidas": r.optativas_exigidas, "cumpridas": r.optativas_cumpridas,
            "planejadas": r.optativas_planejadas, "faltam": r.optativas_faltam,
            "so_obrigatorias": r.formatura_so_obrigatorias, "com_optativas": r.formatura_com_optativas,
            "mensagem": msg}


def semana_json(m: MetricasSemana | None) -> dict | None:
    if m is None:
        return None
    partes = [f"{str(m.horas_aula).replace('.', ',').removesuffix(',0')} h de aula"]
    partes.append(f"{len(m.dias_livres)} dia{'s' if len(m.dias_livres) != 1 else ''} livre"
                  f"{'s' if len(m.dias_livres) != 1 else ''}" + (f" ({', '.join(m.dias_livres)})" if m.dias_livres else ""))
    if m.janelas_horas:
        partes.append(f"{str(m.janelas_horas).replace('.', ',').removesuffix(',0')} h de janela")
    if m.choques_indisponiveis:
        partes.append(f"{m.choques_indisponiveis} aula{'s' if m.choques_indisponiveis > 1 else ''} em horário indisponível")
    if m.aulas_em_dias_livres:
        partes.append(f"aula em dia que você queria livre ({', '.join(m.aulas_em_dias_livres)})")
    if not m.completo:
        partes.append("sem o horário de alguma disciplina")
    return {
        "horas_aula": m.horas_aula, "dias_com_aula": list(m.dias_com_aula), "dias_livres": list(m.dias_livres),
        "janelas_horas": m.janelas_horas, "choques_indisponiveis": m.choques_indisponiveis,
        "aulas_em_dias_livres": list(m.aulas_em_dias_livres), "fora_do_turno": m.fora_do_turno,
        "completo": m.completo, "resumo": " · ".join(partes),
    }


ORIGEM_INGRESSO_TXT = {"informado": "informado por você", "historico": "o período mais antigo do seu histórico",
                       "inicio_do_plano": "o início do plano (seu histórico está vazio)"}


def prazo_json(a: AvaliacaoPrazo | None, ingresso: str | None, origem: str | None, formatura: str | None,
               estimada: bool, fator: float) -> dict:
    base = {"ingresso": ingresso, "origem_ingresso": origem, "formatura": formatura, "estimada": estimada,
            "fator": fator, "semestres_usados": None, "regular": None, "maximo": None, "trancados": 0,
            "no_prazo_regular": None, "no_prazo_maximo": None}
    if a is None or a.regular is None:
        return {**base, "mensagem": "O curso não informa a duração em semestres: não dá para dizer se você forma no prazo."}
    if ingresso is None:
        return {**base, "regular": a.regular,
                "mensagem": "Informe o período de ingresso nas preferências para checar o prazo."}
    if formatura is None or a.semestres_usados is None:
        return {**base, "regular": a.regular, "mensagem": "Sem data de formatura prevista para comparar com o prazo."}
    dados = {**base, "semestres_usados": a.semestres_usados, "regular": a.regular, "maximo": a.maximo,
             "trancados": a.trancados, "no_prazo_regular": a.no_prazo_regular, "no_prazo_maximo": a.no_prazo_maximo}
    est = " (estimativa)" if estimada else ""
    tranc = f", sem contar {_semestres_txt(a.trancados)} trancado{'s' if a.trancados > 1 else ''}" if a.trancados else ""
    if a.no_prazo_regular:
        msg = f"Formatura em {formatura}{est}: {a.semestres_usados} de {a.regular} semestres{tranc}. No prazo."
    elif a.no_prazo_maximo:
        msg = (f"Formatura em {formatura}{est}: {a.semestres_usados} semestres{tranc}, "
               f"{_semestres_txt(a.semestres_usados - a.regular)} além da duração ({a.regular}). "
               f"Dentro do prazo máximo ({a.maximo}).")
    else:
        msg = (f"Formatura em {formatura}{est}: {a.semestres_usados} semestres{tranc}, "
               f"além do prazo máximo de integralização ({a.maximo}).")
    return {**dados, "mensagem": msg}


def _pct(x: float) -> int:
    return int(round(x * 100))


def monte_carlo_json(mc: ResultadoMonteCarlo | None, periodo_de, disciplinas: Mapping[int, Disciplina]) -> dict | None:
    """`periodo_de(indice)` traduz o índice de semestre em "AAAA/N"."""
    if mc is None:
        return None
    acumulado = 0
    distribuicao = []
    for indice, qtd in mc.distribuicao:
        acumulado += qtd
        distribuicao.append({"periodo": periodo_de(indice), "execucoes": qtd, "pct": round(100 * qtd / mc.n, 1),
                             "acumulado_pct": round(100 * acumulado / mc.n, 1)})
    p = {k: (periodo_de(v) if v is not None else None) for k, v in (("p50", mc.p50), ("p80", mc.p80), ("p90", mc.p90))}
    fim_plano = periodo_de(mc.fim_base) if mc.fim_base >= 0 else None
    taxa = mc.taxa
    taxa_txt = (f"Chance de passar em cada disciplina: {_pct(taxa.valor)}%, pelo seu histórico "
                f"({taxa.aprovacoes} aprovações e {taxa.reprovacoes} reprovações)." if taxa.origem == "historico"
                else f"Chance de passar em cada disciplina: {_pct(taxa.valor)}% (padrão; seu histórico ainda não tem resultados).")
    taxa_txt += " Disciplina que você já reprovou conta com chance menor."
    frases = []
    if p["p50"]:
        frases.append(f"50% de chance de formar até {p['p50']}")
    if p["p80"]:
        frases.append(f"80% até {p['p80']}")
    if p["p90"]:
        frases.append(f"90% até {p['p90']}")
    mensagem = ("; ".join(frases) + ".") if frases else "Na maioria das simulações o curso não fecha dentro do horizonte."
    sens = []
    for s in mc.sensibilidade:
        if s.disciplina_id not in disciplinas:
            continue
        nome = disciplinas[s.disciplina_id].nome
        sens.append({
            "disciplina": _ref(disciplinas[s.disciplina_id]),
            "chance_reprovar_pct": _pct(s.chance_reprovar), "atraso_se_reprovar": s.atraso_se_reprovar,
            "contribuicao": s.contribuicao,
            "atraso_a_mais": s.atraso_a_mais,
            "mensagem": (f"{nome}: reprovar nela ({_pct(s.chance_reprovar)}% das simulações) acrescenta em média "
                         f"{str(round(s.atraso_a_mais, 1)).replace('.', ',')} semestre"
                         f"{'s' if round(s.atraso_a_mais, 1) != 1 else ''} à formatura."),
        })
    return {
        "n": mc.n, "semente": mc.semente,
        "taxa": {"valor": taxa.valor, "origem": taxa.origem, "aprovacoes": taxa.aprovacoes,
                 "reprovacoes": taxa.reprovacoes, "texto": taxa_txt},
        "distribuicao": distribuicao, "nao_formou_pct": round(100 * mc.nao_formou / mc.n, 1),
        **p, "periodo_do_plano": fim_plano,
        "chance_no_prazo_do_plano_pct": _pct(mc.chance_no_prazo_do_plano),
        "mensagem": mensagem,
        "mensagem_plano": (f"{_pct(mc.chance_no_prazo_do_plano)}% de chance de formar até {fim_plano}, "
                           "o fim do plano sem nenhuma reprovação.") if fim_plano else None,
        "sensibilidade": sens,
    }


_TITULO_GRUPO = {
    R_INDISPONIVEL: "{n} disciplinas caem em horários que você bloqueou",
    R_SEM_TURMA_NO_QUADRO: "{n} disciplinas sem turma no quadro do período",
    R_OFERTA_ESTIMADA: "{n} disciplinas com oferta estimada (o curso não informou)",
    R_FORA_DE_OFERTA: "{n} disciplinas num período em que não abrem",
    R_CONFLITO: "{n} choques de horário sem turma alternativa",
}


def grupos_de_riscos(riscos) -> list[dict]:
    """Riscos repetidos (3+ do mesmo tipo) viram um grupo com um título só: a lista fica legível."""
    contagem: dict[str, int] = {}
    for r in riscos:
        if r.gravidade != GRAVIDADE_BAIXA:
            contagem[r.tipo] = contagem.get(r.tipo, 0) + 1
    return [{"tipo": t, "n": n, "titulo": _TITULO_GRUPO.get(t, "{n} avisos do mesmo tipo").format(n=n)}
            for t, n in contagem.items() if n >= 3]


def veredito(sim: Simulacao) -> dict:
    """Frase-síntese no topo da tela: o plano funciona ou não, e por quê."""
    altos = sim.resumo.riscos_por_gravidade.get("alta", 0)
    medios = sim.resumo.riscos_por_gravidade.get("media", 0)
    # a maior parte dos problemas é a rotina? diz isso de uma vez, em vez de "N pontos de atenção"
    bloqueados = [r for r in sim.riscos if r.tipo == R_INDISPONIVEL]
    if len(bloqueados) >= 2 and 2 * len(bloqueados) >= altos + medios:
        n = len({d for r in bloqueados for d in r.disciplinas})
        return {"nivel": "alto" if any(r.gravidade == GRAVIDADE_ALTA for r in bloqueados) else "medio", "tipo": "rotina",
                "titulo": f"Sua rotina bate com {n} disciplinas do plano",
                "texto": "Elas só têm turma em horários que você bloqueou. Veja quais na aba Riscos e decida: "
                         "mover, liberar esses horários em algum semestre ou falar com a coordenação."}
    if altos:
        return {"nivel": "alto", "titulo": f"{altos} problema{'s' if altos > 1 else ''} para resolver",
                "texto": "Este plano não funcionaria como está. Veja o que corrigir na aba Riscos."}
    if medios:
        return {"nivel": "medio", "titulo": "Funciona, com pontos de atenção",
                "texto": f"{medios} ponto{'s' if medios > 1 else ''} de atenção. Nada impede o plano, mas vale conferir."}
    return {"nivel": "ok", "titulo": "Nenhum problema encontrado",
            "texto": "Pela simulação, o plano é viável com a oferta e os requisitos conhecidos."}


def rotina_json(res, disciplinas: Mapping[int, Disciplina], tem_bloqueios: bool) -> dict | None:
    """
    "Dá para cursar o que falta com a sua rotina?": uma resposta só, com as disciplinas que não cabem.
    `None` quando o aluno não bloqueou nenhum horário (não há o que responder).
    """
    if not tem_bloqueios:
        return None
    nao = [_ref(disciplinas[i]) for i in res.nao_cabem if i in disciplinas]
    sem = len(res.sem_turma)
    nota_sem = (f" {sem} disciplina{'s' if sem > 1 else ''} ainda não {'têm' if sem > 1 else 'tem'} turma conhecida: "
                "não dá para saber." if sem else "")
    if nao:
        n = len(nao)
        lista = ", ".join(x["codigo"] for x in nao[:6]) + ("…" if n > 6 else "")
        return {"nivel": "alto", "nao_cabem": nao, "sem_turma": sem,
                "titulo": f"Com a sua rotina, {n} obrigatória{'s' if n > 1 else ''} não {'cabem' if n > 1 else 'cabe'}",
                "texto": f"Todas as turmas conhecidas de {lista} caem em horários que você bloqueou." + nota_sem,
                "acao": "Para formar, você vai precisar liberar esses horários em algum semestre "
                        "(por exemplo, um semestre sem trabalhar nesse turno) ou pedir outra turma à coordenação."}
    n = len(res.cabem)
    if not n:
        return {"nivel": "info", "nao_cabem": [], "sem_turma": sem, "titulo": "Ainda não dá para saber",
                "texto": "O curso não informou horários das disciplinas que faltam." , "acao": None}
    return {"nivel": "ok", "nao_cabem": [], "sem_turma": sem,
            "titulo": "Sua rotina comporta o curso",
            "texto": f"{'Todas as' if n > 1 else 'A'} {n} obrigatória{'s' if n > 1 else ''} que falta{'m' if n > 1 else ''} "
                     f"{'têm' if n > 1 else 'tem'} alguma turma fora dos horários bloqueados." + nota_sem,
            "acao": None}


def _fora_do_limite(creditos: int, no_limite: int | None) -> dict:
    """Créditos que contam no limite do semestre e os que ficam fora (estágio/TCC, quando o curso permite)."""
    no_limite = creditos if no_limite is None else no_limite
    return {"creditos_no_limite": no_limite, "creditos_fora_do_limite": creditos - no_limite}


def serializar_simulacao(sim: Simulacao, disciplinas: Mapping[int, Disciplina]) -> dict:
    r = sim.resumo
    saida = {
        "veredito": veredito(sim),
        "resumo": {
            "periodo_inicio": r.periodo_inicio, "periodo_fim": r.periodo_fim, "n_semestres": r.n_semestres,
            "creditos_planejados": r.creditos_planejados, "creditos_restantes": r.creditos_restantes,
            "completo": r.completo, "formatura_prevista": r.formatura_prevista,
            "formatura_estimada": r.formatura_estimada,
            "faltam_obrigatorias": [_ref(disciplinas[i]) for i in r.faltam_obrigatorias if i in disciplinas],
            "riscos_por_gravidade": dict(r.riscos_por_gravidade),
            "horarios": dict(r.horarios), "ofertas": dict(r.ofertas),
            "atraso_maximo_reprovacao": r.atraso_maximo_reprovacao,
            "optativas": optativas_json(r),
        },
        "semestres": [
            {
                "posicao": s.posicao, "periodo": s.periodo, "paridade": s.paridade,
                "creditos": s.creditos, "limite_creditos": s.limite_creditos, "sobrecarga": s.sobrecarga,
                **_fora_do_limite(s.creditos, s.creditos_no_limite),
                "sem_creditos": [_nome(disciplinas, i) for i in s.sem_creditos],
                "semana": semana_json(s.semana), "trancado": s.trancado,
                "pesadas": [_ref(disciplinas[i]) for i in s.pesadas if i in disciplinas],
                "itens": [
                    {
                        "disciplina": _ref(disciplinas[i.disciplina_id]),
                        "periodicidade": i.periodicidade, "origem_periodicidade": i.origem_periodicidade,
                        "ofertada": i.ofertada, "horario_origem": i.horario_origem,
                        "turma_id": i.turma_id, "turma_codigo": i.turma_codigo,
                        "periodo_da_turma": i.periodo_da_turma, "turma_fixa": i.turma_fixa,
                        "encontros": [{"dia": e.dia, "inicio": _hhmm(e.inicio), "fim": _hhmm(e.fim)}
                                      for e in i.encontros],
                        "tipo": i.tipo, "creditos": i.creditos,
                        **marcas_do_item(i.choques, i.bate_indisponivel, i.horario_origem, i.tipo, i.creditos,
                                         disciplinas, junto_com=i.junto_com),
                    }
                    for i in s.itens
                ],
                "n_choques": s.n_choques,
                "choques_texto": (f"{s.n_choques} choque{'s' if s.n_choques > 1 else ''}" if s.n_choques else None),
                "espaco_optativa": s.espaco_optativa,
                "espaco_optativa_texto": (f"Cabem mais {s.espaco_optativa} créditos de optativa aqui."
                                          if s.espaco_optativa and r.optativas_faltam else None),
            }
            for s in sim.semestres
        ],
        "riscos": [_risco_json(x, disciplinas) for x in sim.riscos],
        "riscos_grupos": grupos_de_riscos(sim.riscos),
        "critico": _critico_json(sim.critico, disciplinas, _periodo_do_indice(sim, 0) or r.periodo_inicio),
        "cenarios": [_cenario_json(c, sim, disciplinas) for c in sim.cenarios],
        "premissas": [{"codigo": p, "texto": PREMISSAS_TXT.get(p, p)} for p in sim.premissas],
        "ignorados": list(sim.ignorados),
        "monte_carlo": monte_carlo_json(sim.monte_carlo, lambda i: _periodo_do_indice(sim, i), disciplinas),
    }
    saida["indicadores"] = indicadores_da_simulacao(sim, saida["monte_carlo"])
    return saida


# ── sugestão ─────────────────────────────────────────────────────────────────
# (com preposição: "por causa da cadeia…", "limitado pela…")
_LIMITE_TXT = {
    LIM_REQUISITOS: ("da cadeia de pré-requisitos", "pela cadeia de pré-requisitos"),
    LIM_OFERTA: ("da oferta par/ímpar das disciplinas", "pela oferta par/ímpar das disciplinas"),
    LIM_CREDITOS: ("do limite de créditos por semestre", "pelo limite de créditos por semestre"),
}


def mensagem_inviavel(res: ResultadoOtimizacao, disciplinas: Mapping[int, Disciplina]) -> tuple[str, str]:
    """(o que houve, o que fazer) quando não existe plano possível."""
    if res.motivo == M_CICLO:
        ciclo = _lista([_nome(disciplinas, i) for i in (res.ciclos[0] if res.ciclos else ())])
        return (f"Há pré-requisitos circulares ({ciclo}): nenhuma ordem é possível.",
                "Revise os requisitos dessas disciplinas no CSV do curso.")
    if res.motivo == M_INALCANCAVEL:
        quem = _lista([_nome(disciplinas, i) for i in res.inalcancaveis])
        return (f"{quem} não cabe em nenhum período: a oferta e os requisitos se contradizem.",
                "Confira a oferta (par/ímpar) e os pré-requisitos dessas disciplinas.")
    if res.motivo == M_SEM_SOLUCAO:
        return (f"Não encontrei plano em até o limite de semestres (mínimo teórico: {res.limite_inferior}).",
                "Tente sem limite de créditos ou aceite mais semestres.")
    return ("Não foi possível montar uma sugestão.", "Tente de novo com outros parâmetros.")


def explicar_sugestao(res: ResultadoOtimizacao) -> str:
    """Uma frase que diz se o prazo da sugestão é o menor possível e por que não é menor."""
    m = res.metricas
    if m is None or not res.semestres:
        return "Não há nada a cursar: o curso já está completo."
    de, pela = _LIMITE_TXT.get(res.limitado_por or "", ("das restrições do curso", "pelas restrições do curso"))
    if res.otimo_comprovado:
        return (f"{_semestres_txt(m.n_semestres)} é o MENOR prazo possível: abaixo disso é impossível "
                f"por causa {de}.")
    if m.n_semestres > res.limite_inferior:
        return (f"{_semestres_txt(m.n_semestres)}. O mínimo teórico é {res.limite_inferior} "
                f"(limitado {pela}); a sugestão usa a diferença para equilibrar a carga ou evitar choques.")
    return f"{_semestres_txt(m.n_semestres)}, limitado {pela}."


def mensagem_optativas(res: ResultadoOtimizacao) -> str | None:
    """Uma frase sobre as optativas: couberam, couberam em parte ou não couberam."""
    if not res.optativas_reservadas:
        return None
    if not res.optativas_sem_encaixe:
        onde = [s.periodo for s in res.semestres if s.creditos_optativos]
        lugar = f" ({', '.join(onde)})" if onde else ""
        return (f"Os {res.optativas_reservadas} créditos de optativas já estão no plano, no meio do curso{lugar}: "
                "é espaço reservado para você escolher quais cursar.")
    adia = (f" Para fechá-las seria preciso chegar a {res.periodo_fim_com_optativas}."
            if res.periodo_fim_com_optativas else "")
    return (f"Faltam encaixar {res.optativas_sem_encaixe} créditos de optativas: os semestres já estão no limite "
            f"de créditos.{adia} Se você precisa de menos optativas, informe o número em Minha rotina › Optativas.")


def _junto_com(juntas) -> dict[int, tuple[int, ...]]:
    saida: dict[int, set[int]] = {}
    for g in juntas or ():
        for i in g.disciplinas:
            saida.setdefault(i, set()).update(x for x in g.disciplinas if x != i)
    return {i: tuple(sorted(v)) for i, v in saida.items()}


def serializar_sugestao(res: ResultadoOtimizacao, disciplinas: Mapping[int, Disciplina], nome_plano: str,
                        juntas=()) -> dict:
    junto = _junto_com(juntas)
    if not res.viavel:
        mensagem, acao = mensagem_inviavel(res, disciplinas)
        return {"viavel": False, "motivo": res.motivo, "mensagem": mensagem, "acao": acao,
                "limite_inferior": res.limite_inferior}
    m = res.metricas
    return {
        "viavel": True,
        "explicacao": explicar_sugestao(res),
        "selo": selo_otimo(res), "etapas": etapas_json(res),
        "fim_de_curso_mensagem": _mensagem_fim(res, disciplinas),
        "fixas_mensagens": _mensagens_fixas(res, disciplinas),
        "partiu_do_plano": res.partiu_do_plano,
        "limite_inferior": res.limite_inferior, "limitado_por": res.limitado_por,
        "otimo_comprovado": res.otimo_comprovado,
        "cadeia_critica": _cadeia_sugerida(res, disciplinas),
        "cadeia_mensagem": mensagem_cadeia(res.cadeia_critica, disciplinas),
        "metricas": {
            "n_semestres": m.n_semestres, "periodo_fim": m.periodo_fim, "creditos_total": m.creditos_total,
            "carga_media": m.carga_media, "carga_desvio": m.carga_desvio, "carga_maxima": m.carga_maxima,
            "colisoes": m.colisoes, "atraso_medio_reprovacao": m.atraso_medio_reprovacao,
            "atraso_maximo_reprovacao": m.atraso_maximo_reprovacao,
        },
        "optativas_reservadas": res.optativas_reservadas,
        "optativas": {
            "pedidas": res.optativas_reservadas,
            "encaixadas": res.optativas_encaixadas,
            "sem_encaixe": res.optativas_sem_encaixe,
            "mensagem": mensagem_optativas(res),
        },
        # as duas datas lado a lado: só com as obrigatórias × com as optativas que faltam
        "formatura": {
            "so_obrigatorias": m.periodo_fim,
            "com_optativas": res.periodo_fim_com_optativas,
            "optativas_adiam": bool(res.optativas_sem_encaixe),
        },
        "incluidas_por_requisito": [_ref(disciplinas[i]) for i in res.incluidas_por_requisito if i in disciplinas],
        "semestres": [
            {
                "posicao": s.posicao, "periodo": s.periodo, "creditos": s.creditos,
                "creditos_optativos": s.creditos_optativos, "semana": semana_json(s.semana), "trancado": s.trancado,
                "pesadas": [_ref(disciplinas[i]) for i in s.pesadas if i in disciplinas],
                "itens": [
                    {"disciplina": _ref(disciplinas[i.disciplina_id]), "turma_id": i.turma_id,
                     "horario_origem": i.horario_origem, "incluida_por_requisito": i.incluida_por_requisito,
                     **marcas_do_item(i.choques, i.bate_indisponivel, i.horario_origem,
                                      disciplinas[i.disciplina_id].tipo, disciplinas[i.disciplina_id].creditos,
                                      disciplinas, junto_com=junto.get(i.disciplina_id, ()))}
                    for i in s.itens
                ],
                "n_choques": len(s.colisoes),
                "choques_texto": (f"{len(s.colisoes)} choque{'s' if len(s.colisoes) > 1 else ''}" if s.colisoes else None),
                "colisoes": [
                    {"a": _ref(disciplinas[c.disciplina_a]), "b": _ref(disciplinas[c.disciplina_b]),
                     "dia": c.sobreposicao.dia}
                    for c in s.colisoes
                ],
            }
            for s in res.semestres
        ],
        # Pronto para `POST /planos` (turma só quando o período já tem quadro real).
        "plano": {
            "nome": nome_plano,
            "semestres": [
                {"rotulo": f"Semestre {s.posicao}", "periodo_letivo": s.periodo,
                 # turma escolhida pelo Rumo: fica "automática" (acompanha mudanças até você trocar)
                 "itens": [{"disciplina_id": i.disciplina_id, "turma_id": i.turma_id,
                            **({"turma_auto": True} if i.turma_id else {})} for i in s.itens]}
                for s in res.semestres
            ],
        },
        "iteracoes": res.iteracoes, "semente": res.semente,
    }


_MOTIVO_FIXA = {"nao_abre": "ela não abre nesse período (oferta par/ímpar)",
                "requisitos": "os pré-requisitos dela não ficam prontos até lá",
                "sem_turma": "o quadro de turmas desse período já saiu e ela não está nele"}


def _mensagens_fixas(res: ResultadoOtimizacao, disciplinas: Mapping[int, Disciplina]) -> list[dict]:
    """O que o aluno pediu para cursar num período: respeitado (✓) ou ignorado, com o motivo."""
    saida = [{"ok": True, "texto": f"{disciplinas[d].codigo} em {per}, como você pediu."}
             for d, per in sorted(res.fixas_respeitadas.items()) if d in disciplinas]
    saida += [{"ok": False, "texto": f"Não deu para pôr {disciplinas[d].codigo} onde você pediu: {_MOTIVO_FIXA.get(m, m)}. "
                                     "Ela ficou onde cabe."}
              for d, m in sorted(res.fixas_ignoradas.items()) if d in disciplinas]
    return saida


def _mensagem_fim(res: ResultadoOtimizacao, disciplinas: Mapping[int, Disciplina]) -> str | None:
    """ "TCC e seminários ficaram no fim do curso: …", com o período de cada um na sugestão."""
    periodo_de = {i.disciplina_id: s.periodo for s in res.semestres for i in s.itens}
    no_plano = [d for d in res.fim_de_curso if d in periodo_de and d in disciplinas]
    if not no_plano:
        return None
    por_periodo: dict[str, list[str]] = {}
    for d in sorted(no_plano, key=lambda x: (periodo_de[x], disciplinas[x].codigo)):
        por_periodo.setdefault(periodo_de[d], []).append(disciplinas[d].codigo)
    partes = "; ".join(f"{' e '.join(cods)} em {per}" for per, cods in por_periodo.items())
    return f"TCC e seminários de conclusão ficaram no fim do curso: {partes}."


def _cadeia_sugerida(res: ResultadoOtimizacao, disciplinas: Mapping[int, Disciplina]) -> list[dict]:
    """Cadeia crítica com o período em que a SUGESTÃO coloca cada disciplina."""
    periodo_de = {i.disciplina_id: s.periodo for s in res.semestres for i in s.itens}
    return [{"disciplina": _ref(disciplinas[d]), "periodo": periodo_de.get(d)}
            for d in res.cadeia_critica if d in disciplinas]


# ── edição da oferta (par/ímpar) ─────────────────────────────────────────────
VALORES_PERIODICIDADE = ("sempre", "impar", "par")
MAX_EDICOES_OFERTA = 200


def ler_edicoes_periodicidade(payload) -> dict[int, str | None]:
    """`{"itens": [{"disciplina_id": 3, "periodicidade": "impar"|"par"|"sempre"|null}]}`."""
    itens = payload.get("itens") if isinstance(payload, dict) else None
    if not isinstance(itens, list) or not itens:
        raise AppError('Envie {"itens": [{"disciplina_id": 1, "periodicidade": "impar"}]}.')
    if len(itens) > MAX_EDICOES_OFERTA:
        raise AppError(f"No máximo {MAX_EDICOES_OFERTA} disciplinas por vez.")
    saida: dict[int, str | None] = {}
    for k, it in enumerate(itens, start=1):
        if not isinstance(it, dict):
            raise AppError(f"Item {k}: formato inválido.")
        did, valor = it.get("disciplina_id"), it.get("periodicidade")
        if isinstance(did, bool) or not isinstance(did, int):
            raise AppError(f"Item {k}: disciplina_id deve ser um número inteiro.")
        if valor is not None and valor not in VALORES_PERIODICIDADE:
            raise AppError(f"Item {k}: oferta inválida. Use impar, par, sempre ou null (não informada).", 422)
        saida[did] = valor
    return saida


# ── optativas que cabem num semestre (o aluno escolhe; nada é adicionado sozinho) ──
_DIA_CURTO_OPT = {"SEG": "Seg", "TER": "Ter", "QUA": "Qua", "QUI": "Qui", "SEX": "Sex", "SAB": "Sáb", "DOM": "Dom"}


def ler_pedido_optativas(payload) -> tuple[list[dom.SemestrePlano], int, str | None]:
    semestres, inicial = ler_pedido_simulacao(payload)
    posicao = _inteiro_opcional((payload or {}).get("posicao"), "O semestre", 1, max(1, len(semestres)))
    if posicao is None:
        raise _erro_campo("Diga para qual semestre (posicao, a partir de 1).", "posicao")
    return semestres, posicao, inicial


def optativas_que_cabem_json(lista, disciplinas: Mapping[int, Disciplina], periodo: str, teto: int | None,
                             turmas_por_id: Mapping[int, object]) -> dict:
    itens = []
    for o in lista:
        d = disciplinas[o.disciplina_id]
        motivos = []
        if o.disponibilidade == "cabe":
            t = turmas_por_id.get(o.turma_id) if o.turma_id else None
            quando = ""
            if t:
                horarios = ", ".join(f"{_DIA_CURTO_OPT.get(e.dia, e.dia)} {_hhmm(e.inicio)}–{_hhmm(e.fim)}" for e in t.encontros)
                quando = f" ({t.codigo_turma}: {horarios})"
            motivos.append(("Cabe na sua disponibilidade" + quando + (" — horário projetado" if o.horario_projetado else ""), "green"))
        else:
            motivos.append(("Sem horário: disponibilidade não verificada", "gray"))
        if not o.sem_choque:
            motivos.append(("Bate com outra disciplina do semestre", "yellow"))
        if o.origem_oferta == "estimada":
            motivos.append(("Oferta estimada pelo período sugerido", "yellow"))
        elif o.origem_oferta == "desconhecida":
            motivos.append(("Oferta não informada pelo curso", "gray"))
        if o.cabe_no_teto is False:
            motivos.append((f"Passa do teto de {teto} créditos", "yellow"))
        itens.append({"disciplina": {**_ref(d), "creditos": d.creditos}, "turma_id": o.turma_id,
                      "disponibilidade": o.disponibilidade, "tags": [{"texto": t, "cor": c} for t, c in motivos]})
    if itens:
        n = len(itens)
        msg = (f"{n} optativa{'s' if n != 1 else ''} cabe{'m' if n != 1 else ''} em {periodo} "
               "(oferta, requisitos e disponibilidade). Escolha as que quiser.")
    else:
        msg = f"Nenhuma optativa cabe em {periodo} com a oferta, os requisitos e a sua disponibilidade."
    return {"periodo": periodo, "optativas": itens, "mensagem": msg}


# ── "cursar junto": candidatas (para perguntar) e o efeito na sugestão ─────────
_MOTIVO_JUNTO = {"nomes": "nomes de fim de curso no mesmo período sugerido",
                 "correquisito": "uma é correquisito da outra"}


def candidatas_juntas_json(candidatas, disciplinas: Mapping[int, Disciplina], respondida: bool, ja_tem: bool) -> dict:
    itens = [{"disciplinas": [_ref(disciplinas[i]) for i in c.disciplinas], "motivo": c.motivo,
              "texto": f"{' + '.join(disciplinas[i].nome for i in c.disciplinas)} ({_MOTIVO_JUNTO.get(c.motivo, c.motivo)})"}
             for c in candidatas]
    return {"candidatas": itens, "perguntar": bool(itens) and not respondida and not ja_tem,
            "pergunta": "Quer cursar alguma disciplina junto com outra? (ex.: TCC com Seminário)"}


def mensagem_efeito_pedidos(com: str | None, sem: str | None, pedidos: list[str]) -> str | None:
    """Custo (ou ganho) dos pedidos do aluno na formatura: "Seus pedidos (X em 2028/1) deixam…"."""
    if not com or not sem or not pedidos:
        return None
    lista = "; ".join(pedidos)
    chave = lambda p: tuple(map(int, p.split("/")))
    if com == sem:
        return f"Seus pedidos ({lista}) não mudam a formatura: {com}."
    if chave(com) > chave(sem):
        return (f"Seus pedidos ({lista}) deixam a formatura em {com}; sem eles seria {sem}. "
                "Se preferir formar antes, revise-os em Minha rotina.")
    return f"Seus pedidos ({lista}) até adiantam a formatura: {com} (sem eles, {sem})."


def mensagem_efeito_juntas(com_grupo: str | None, sem_grupo: str | None, nomes: list[str]) -> str | None:
    """Frase simples quando manter o grupo junto muda a formatura."""
    if not com_grupo or not sem_grupo or com_grupo == sem_grupo or not nomes:
        return None
    quem = " e ".join(nomes) if len(nomes) <= 2 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
    rumo = "atrasa" if tuple(map(int, com_grupo.split("/"))) > tuple(map(int, sem_grupo.split("/"))) else "adianta"
    return (f"Para manter {quem} juntas, a formatura fica em {com_grupo} "
            f"(separadas, seria {sem_grupo}: o grupo {rumo} o fim).")


# ── Fase 3: o que a sugestão garante, etapas e indicadores para comparar planos ──
ETAPAS = (("grafo", "Grafo de requisitos e limite mínimo"), ("guloso", "Primeiro plano (guloso)"),
          ("recozimento", "Melhorando (recozimento simulado)"), ("turmas", "Escolhendo turmas"))


def selo_otimo(res: ResultadoOtimizacao) -> dict | None:
    """ "Prazo mínimo garantido" × "melhor encontrado", em linguagem simples."""
    m = res.metricas
    if m is None or not res.semestres:
        return None
    com_pedidos = " Isso já com os seus pedidos (disciplina em período, cursar junto)."         if (res.fixas_respeitadas or res.grupos_aplicados) else ""
    if res.otimo_comprovado:
        return {"tipo": "otimo", "titulo": "Prazo mínimo garantido",
                "texto": f"Não existe plano com menos de {_semestres_txt(m.n_semestres)}: conferimos a cadeia de "
                         f"pré-requisitos, a oferta par/ímpar e o limite de créditos.{com_pedidos}"}
    if m.n_semestres > res.limite_inferior:
        dif = m.n_semestres - res.limite_inferior
        return {"tipo": "melhor", "titulo": "Melhor plano encontrado",
                "texto": f"Pode existir um plano com até {_semestres_txt(dif)} a menos, mas não o achamos no tempo de "
                         "busca (ou a folga foi usada para equilibrar a carga e evitar choques)."}
    return {"tipo": "melhor", "titulo": "Melhor plano encontrado",
            "texto": "É o melhor que achamos; a folga pedida deixa a carga mais leve."}


def etapas_json(res: ResultadoOtimizacao) -> list[dict]:
    return [{"chave": k, "rotulo": r, "ms": res.tempos_ms.get(k)} for k, r in ETAPAS]


def _media(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def indicadores(formatura: str | None, carga_media, carga_maxima, choques: int | None,
                dias_livres_media, p50: str | None, chance_pct: int | None) -> list[dict]:
    """Mesmas chaves no plano atual e na sugestão: a tela só põe lado a lado. `melhor` diz a direção."""
    def fmt(v, suf=""):
        return "–" if v is None else (str(v).replace(".", ",") + suf)
    return [
        {"chave": "formatura", "rotulo": "Formatura (sem reprovar)", "valor": formatura, "texto": fmt(formatura), "melhor": "menor"},
        {"chave": "p50", "rotulo": "Formatura provável (50%)", "valor": p50, "texto": fmt(p50), "melhor": "menor"},
        {"chave": "chance", "rotulo": "Chance de formar até o fim do plano", "valor": chance_pct,
         "texto": fmt(chance_pct, "%"), "melhor": "maior"},
        {"chave": "carga_media", "rotulo": "Carga média", "valor": carga_media, "texto": fmt(carga_media, " cr"), "melhor": "menor"},
        {"chave": "carga_maxima", "rotulo": "Carga máxima", "valor": carga_maxima, "texto": fmt(carga_maxima, " cr"), "melhor": "menor"},
        {"chave": "choques", "rotulo": "Choques de horário", "valor": choques, "texto": fmt(choques), "melhor": "menor"},
        {"chave": "dias_livres", "rotulo": "Dias livres por semana (média)", "valor": dias_livres_media,
         "texto": fmt(dias_livres_media), "melhor": "maior"},
    ]


def indicadores_da_simulacao(sim: Simulacao, mc_json: dict | None) -> list[dict]:
    com = [s for s in sim.semestres if s.itens]
    cargas = [s.creditos for s in com]
    livres = [len(s.semana.dias_livres) for s in com if s.semana and s.semana.completo]
    r = sim.resumo
    formatura = r.formatura_prevista or r.periodo_fim
    if r.optativas_faltam and r.formatura_com_optativas:
        formatura = r.formatura_com_optativas          # a sugestão já conta as optativas: compara igual com igual
    ind = indicadores(formatura, _media(cargas), max(cargas, default=None),
                      sum(s.n_choques for s in com), _media(livres),
                      (mc_json or {}).get("p50"), (mc_json or {}).get("chance_no_prazo_do_plano_pct"))
    if formatura != (r.formatura_prevista or r.periodo_fim):
        ind[0]["texto"] = f"{formatura} (com as {r.optativas_faltam} cr de optativas que faltam)"
    return ind


def indicadores_da_sugestao(res: ResultadoOtimizacao, mc_json: dict | None, dias_livres_media) -> list[dict]:
    m = res.metricas
    if m is None:
        return []
    return indicadores(m.periodo_fim, m.carga_media, m.carga_maxima, m.colisoes, dias_livres_media,
                       (mc_json or {}).get("p50"), (mc_json or {}).get("chance_no_prazo_do_plano_pct"))


def texto_problema_grupo(problema, disciplinas: Mapping[int, Disciplina]) -> str:
    a, b = (disciplinas[i].codigo if i in disciplinas else str(i) for i in problema.disciplinas)
    if problema.tipo == "ofertas_incompativeis":
        return f"{a} e {b} não podem ficar juntas: uma só abre em período ímpar e a outra só em par."
    return f"{a} e {b} não podem ficar juntas: {a} exige {b} antes."

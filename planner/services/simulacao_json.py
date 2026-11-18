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
                                R_HORARIO_DESCONHECIDO, R_HORARIO_PROJETADO, R_JA_CURSADA,
                                R_OFERTA_DESCONHECIDA, R_OFERTA_ESTIMADA, R_PERIODO_FORA_DE_ORDEM,
                                R_PRE_REQUISITO, R_SEM_TURMA_NO_QUADRO, R_SOBRECARGA, Risco, Simulacao)
from .analise_json import _hhmm, ler_payload

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
        return (f"{det.get('creditos')} créditos {onde}, acima do limite de {det.get('limite')}.",
                "Passe uma disciplina para outro semestre.")
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
    }


def veredito(sim: Simulacao) -> dict:
    """Frase-síntese no topo da tela: o plano funciona ou não, e por quê."""
    altos = sim.resumo.riscos_por_gravidade.get("alta", 0)
    medios = sim.resumo.riscos_por_gravidade.get("media", 0)
    if altos:
        return {"nivel": "alto", "titulo": f"{altos} problema{'s' if altos > 1 else ''} para resolver",
                "texto": "Este plano não funcionaria como está. Veja os riscos em vermelho abaixo."}
    if medios:
        return {"nivel": "medio", "titulo": "Funciona, com pontos de atenção",
                "texto": f"{medios} ponto{'s' if medios > 1 else ''} de atenção. Nada impede o plano, mas vale conferir."}
    return {"nivel": "ok", "titulo": "Nenhum problema encontrado",
            "texto": "Pela simulação, o plano é viável com a oferta e os requisitos conhecidos."}


def serializar_simulacao(sim: Simulacao, disciplinas: Mapping[int, Disciplina]) -> dict:
    r = sim.resumo
    return {
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
        },
        "semestres": [
            {
                "posicao": s.posicao, "periodo": s.periodo, "paridade": s.paridade,
                "creditos": s.creditos, "limite_creditos": s.limite_creditos, "sobrecarga": s.sobrecarga,
                "sem_creditos": [_nome(disciplinas, i) for i in s.sem_creditos],
                "itens": [
                    {
                        "disciplina": _ref(disciplinas[i.disciplina_id]),
                        "periodicidade": i.periodicidade, "origem_periodicidade": i.origem_periodicidade,
                        "ofertada": i.ofertada, "horario_origem": i.horario_origem,
                        "turma_id": i.turma_id, "turma_codigo": i.turma_codigo,
                        "periodo_da_turma": i.periodo_da_turma, "turma_fixa": i.turma_fixa,
                        "encontros": [{"dia": e.dia, "inicio": _hhmm(e.inicio), "fim": _hhmm(e.fim)}
                                      for e in i.encontros],
                    }
                    for i in s.itens
                ],
            }
            for s in sim.semestres
        ],
        "riscos": [_risco_json(x, disciplinas) for x in sim.riscos],
        "critico": _critico_json(sim.critico, disciplinas, _periodo_do_indice(sim, 0) or r.periodo_inicio),
        "cenarios": [_cenario_json(c, sim, disciplinas) for c in sim.cenarios],
        "premissas": [{"codigo": p, "texto": PREMISSAS_TXT.get(p, p)} for p in sim.premissas],
        "ignorados": list(sim.ignorados),
    }


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
        return (f"{res.optativas_reservadas} créditos de optativas couberam nos semestres que as obrigatórias "
                "já usam: a formatura não muda por causa delas.")
    adia = (f" Para fechá-las seria preciso chegar a {res.periodo_fim_com_optativas}."
            if res.periodo_fim_com_optativas else "")
    return (f"Faltam encaixar {res.optativas_sem_encaixe} créditos de optativas: os semestres já estão no limite "
            f"de créditos.{adia} Se você precisa de menos optativas, informe o número em “Optativas que ainda preciso”.")


def serializar_sugestao(res: ResultadoOtimizacao, disciplinas: Mapping[int, Disciplina], nome_plano: str) -> dict:
    if not res.viavel:
        mensagem, acao = mensagem_inviavel(res, disciplinas)
        return {"viavel": False, "motivo": res.motivo, "mensagem": mensagem, "acao": acao,
                "limite_inferior": res.limite_inferior}
    m = res.metricas
    return {
        "viavel": True,
        "explicacao": explicar_sugestao(res),
        "limite_inferior": res.limite_inferior, "limitado_por": res.limitado_por,
        "otimo_comprovado": res.otimo_comprovado,
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
                "creditos_optativos": s.creditos_optativos,
                "itens": [
                    {"disciplina": _ref(disciplinas[i.disciplina_id]), "turma_id": i.turma_id,
                     "horario_origem": i.horario_origem, "incluida_por_requisito": i.incluida_por_requisito}
                    for i in s.itens
                ],
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
                 "itens": [{"disciplina_id": i.disciplina_id, "turma_id": i.turma_id} for i in s.itens]}
                for s in res.semestres
            ],
        },
        "iteracoes": res.iteracoes, "semente": res.semente,
    }


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

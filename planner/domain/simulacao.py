"""
Simulador de futuro: "e se eu seguir ESTE plano, o que acontece nos próximos semestres?"

Diferente de `analise.analisar_plano` (que julga o plano no presente, semestre por semestre e só
com horários reais), o simulador projeta o plano num CALENDÁRIO REAL ("2027/1", "2027/2"…):

  * oferta       a disciplina existe naquele período? (par / ímpar / sempre; cadastrada, estimada ou
                 desconhecida — a origem sempre viaja junto, para a tela poder avisar);
  * horários     períodos futuros não têm quadro: projeta os do último período de MESMA paridade
                 (`periodicidade.turmas_para_periodo`) e diz que é projeção;
  * conflitos    o semestre inteiro é resolvido de uma vez (`alocacao.alocar_turmas`, busca com
                 poda): sobra colisão só quando NENHUMA combinação de turmas a evita;
  * requisitos   pré/co com grupos "A ou B"; o que está planejado antes conta como concluído;
  * grafo        caminho crítico das obrigatórias pendentes (`grafo`): quem não pode atrasar;
  * reprovação   "e se eu reprovar em X?": `replanejamento` mede o efeito dominó em semestres.

Premissas (devolvidas em `premissas`, para a tela dizer com clareza):
  * quem está CURSANDO conta como concluído no início do plano;
  * o que está planejado num semestre conta como concluído nos seguintes (projeção otimista);
  * horários de períodos futuros são projeções, não fatos.

Função pura, só stdlib. Nada é bloqueado: o resultado é uma lista de RISCOS com gravidade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Collection, Mapping, Sequence

from .alocacao import alocar_turmas
from .analise import ItemPlano, SemestrePlano
from .carga import avaliar_carga
from .conflitos import Selecao
from .entidades import TIPO_OBRIGATORIA, Disciplina, Encontro, Requisito, Turma
from .grafo import (INF, construir_grafo, ciclos as ciclos_do_grafo, descendentes, folgas,
                    menor_horizonte, primeiros_semestres, ultimos_semestres)
from .periodicidade import (HORARIO_DESCONHECIDO, HORARIO_PROJETADO, HORARIO_REAL, ORIGEM_CADASTRADA,
                            ORIGEM_DESCONHECIDA, ORIGEM_ESTIMADA, ofertada_em, paridade_do_periodo,
                            proximo_periodo_ofertado, turmas_para_periodo)
from .previsao import normalizar_periodo, somar_periodos
from .progresso import calcular_progresso
from .replanejamento import CenarioReprovacao, cenarios_de_reprovacao
from .requisitos import verificar_plano
from .restante import CalendarioDeOferta, nos_a_cursar, periodicidades_efetivas

HORARIO_PROPRIO = "proprio"        # horário que o aluno definiu à mão
HORIZONTE_GRAFO = 16               # semestres considerados no caminho crítico

GRAVIDADE_ALTA, GRAVIDADE_MEDIA, GRAVIDADE_BAIXA = "alta", "media", "baixa"
ORDEM_GRAVIDADE = {GRAVIDADE_ALTA: 0, GRAVIDADE_MEDIA: 1, GRAVIDADE_BAIXA: 2}

# tipos de risco
R_FORA_DE_OFERTA = "fora_de_oferta"            # oferta CADASTRADA diz que não abre neste período
R_OFERTA_ESTIMADA = "oferta_estimada_fora"     # a estimativa (período sugerido) diz que não abre
R_OFERTA_DESCONHECIDA = "oferta_desconhecida"  # o curso não informou par/ímpar
R_SEM_TURMA_NO_QUADRO = "sem_turma_no_quadro"  # o quadro do período existe e a disciplina não está nele
R_PRE_REQUISITO = "pre_requisito"
R_CONFLITO = "conflito_horario"
R_SOBRECARGA = "sobrecarga"
R_PERIODO_FORA_DE_ORDEM = "periodo_fora_de_ordem"
R_FALTAM_OBRIGATORIAS = "faltam_obrigatorias"
R_JA_CURSADA = "ja_cursada"
R_HORARIO_PROJETADO = "horario_projetado"
R_HORARIO_DESCONHECIDO = "horario_desconhecido"

PREMISSA_CURSANDO = "cursando_conta_como_concluida"
PREMISSA_PLANEJADO = "planejado_conta_como_concluido"
PREMISSA_HORARIO_PROJETADO = "horarios_projetados"
PREMISSA_OFERTA_ESTIMADA = "oferta_estimada"


@dataclass(frozen=True)
class ItemSimulado:
    disciplina_id: int
    periodicidade: str                 # valor efetivo: sempre | impar | par
    origem_periodicidade: str          # cadastrada | estimada | desconhecida
    ofertada: bool                     # existe neste período?
    horario_origem: str                # real | projetado | desconhecido | proprio
    turma_id: int | None               # turma usada pela melhor alocação (pode ser projetada)
    turma_codigo: str | None
    periodo_da_turma: str | None       # de que período veio a turma (≠ período do semestre se projetada)
    encontros: tuple[Encontro, ...]
    turma_fixa: bool                   # o aluno escolheu a turma / definiu o horário


@dataclass(frozen=True)
class SemestreSimulado:
    posicao: int                       # a partir de 1
    periodo: str                       # "AAAA/N" (dado ou calculado em sequência)
    paridade: str                      # impar | par
    itens: tuple[ItemSimulado, ...]
    creditos: int
    limite_creditos: int | None
    sobrecarga: bool
    sem_creditos: tuple[int, ...]      # disciplinas de créditos desconhecidos (somadas como 0)


@dataclass(frozen=True)
class Risco:
    tipo: str
    gravidade: str
    posicao: int | None                # semestre do plano (None = plano inteiro)
    periodo: str | None
    disciplinas: tuple[int, ...] = ()
    detalhe: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CaminhoCritico:
    """Obrigatórias pendentes vistas como grafo: o menor prazo possível e quem não pode atrasar."""

    menor_semestres: int | None                  # com a oferta par/ímpar (None = não cabe no horizonte)
    menor_sem_calendario: int | None             # se tudo fosse ofertado todo semestre
    etapas: tuple[tuple[int, tuple[int, ...]], ...]   # (índice de semestre, disciplinas críticas)
    folga: Mapping[int, int | None]              # semestres de folga por disciplina (0 = crítica)
    gargalos: tuple[tuple[int, int], ...]        # (disciplina, quantas dependem dela)
    ciclos: tuple[tuple[int, ...], ...]
    inalcancaveis: tuple[int, ...]               # não cabem no horizonte (oferta/requisito impossível)


@dataclass(frozen=True)
class ResumoSimulacao:
    periodo_inicio: str
    periodo_fim: str | None              # último período com disciplina no plano
    n_semestres: int                     # semestres com disciplina
    creditos_planejados: int
    creditos_restantes: int | None       # após o plano; None = o curso não informa créditos exigidos
    completo: bool | None                # o plano conclui o curso? None = sem base para afirmar
    formatura_prevista: str | None       # só quando `completo`
    formatura_estimada: str | None       # quando falta algo: estimativa pela média do plano
    faltam_obrigatorias: tuple[int, ...]
    riscos_por_gravidade: Mapping[str, int]
    horarios: Mapping[str, int]          # itens por origem do horário
    ofertas: Mapping[str, int]           # itens por origem da periodicidade
    atraso_maximo_reprovacao: int        # pior atraso entre os cenários "e se eu reprovar"


@dataclass(frozen=True)
class Simulacao:
    semestres: tuple[SemestreSimulado, ...]
    riscos: tuple[Risco, ...]
    resumo: ResumoSimulacao
    critico: CaminhoCritico
    cenarios: tuple[CenarioReprovacao, ...]
    fim_base: int                        # índice do último semestre no replanejamento sem reprovação
    premissas: tuple[str, ...]
    ignorados: tuple[int, ...]           # ids do plano que não existem no catálogo


# ── passos internos ──────────────────────────────────────────────────────────
def _chave(periodo: str) -> tuple[int, int]:
    ano, n = periodo.split("/")
    return int(ano), int(n)


def _resolver_periodos(
    semestres: Sequence[SemestrePlano], inicial: str, ppa: int
) -> tuple[list[str], list[int]]:
    """Período de cada semestre (dado ou em sequência) e as posições fora de ordem."""
    resolvidos: list[str] = []
    fora_de_ordem: list[int] = []
    anterior: str | None = None
    for i, s in enumerate(semestres, start=1):
        p = normalizar_periodo(s.periodo_letivo, ppa) if s.periodo_letivo else None
        if p is None:
            p = inicial if anterior is None else somar_periodos(anterior, 1, ppa)
        elif anterior is not None and _chave(p) <= _chave(anterior):
            fora_de_ordem.append(i)
        resolvidos.append(p)
        anterior = p
    return resolvidos, fora_de_ordem


class _OfertaPorPeriodos:
    """`Oferta` por índice de semestre sobre períodos já resolvidos (continua em sequência depois do fim)."""

    def __init__(self, periodos: Sequence[str], efetivas, ppa: int) -> None:
        self.periodos, self.efetivas, self.ppa = list(periodos), efetivas, ppa

    def periodo(self, t: int) -> str:
        if t < len(self.periodos):
            return self.periodos[t]
        return somar_periodos(self.periodos[-1], t - len(self.periodos) + 1, self.ppa)

    def __call__(self, disciplina_id: int, t: int) -> bool:
        e = self.efetivas.get(disciplina_id)
        return ofertada_em(e.valor if e else "sempre", self.periodo(t), self.ppa)


def _turma_propria(disciplina_id: int, encontros: tuple[Encontro, ...], periodo: str) -> Turma:
    return Turma(-disciplina_id, disciplina_id, encontros, periodo, "própria")


def _hhmm(t) -> str:
    return t.strftime("%H:%M")


def _faixa(e: Encontro) -> str:
    return f"{_hhmm(e.inicio)}–{_hhmm(e.fim)}"


def _caminho_critico(
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
    concluidas: Collection[int],
    inicial: str,
    efetivas,
    ppa: int,
) -> CaminhoCritico:
    nos, _ = nos_a_cursar(disciplinas, requisitos, concluidas)
    if not nos:
        return CaminhoCritico(0, 0, (), {}, (), (), ())
    grafo = construir_grafo(nos, requisitos, concluidas)
    calendario = CalendarioDeOferta(inicial, efetivas, ppa)
    primeiros = primeiros_semestres(grafo, HORIZONTE_GRAFO, calendario)
    livres = primeiros_semestres(grafo, HORIZONTE_GRAFO, lambda _n, _t: True)

    menor = menor_horizonte(primeiros)
    menor_livre = menor_horizonte(livres)
    inalcancaveis = tuple(sorted(n for n, v in primeiros.items() if v == INF))

    teto = int(menor) if menor != INF else HORIZONTE_GRAFO
    ultimos = ultimos_semestres(grafo, teto, calendario)
    f = folgas(primeiros, ultimos)
    folga_int = {n: (int(v) if abs(v) != INF else None) for n, v in f.items()}

    por_etapa: dict[int, list[int]] = {}
    for n, v in folga_int.items():
        if v == 0 and primeiros[n] != INF:
            por_etapa.setdefault(int(primeiros[n]), []).append(n)
    etapas = tuple((i, tuple(sorted(ids))) for i, ids in sorted(por_etapa.items()))

    desc = descendentes(grafo)
    gargalos = tuple(sorted(
        ((n, len(v)) for n, v in desc.items() if v), key=lambda x: (-x[1], x[0])
    )[:5])
    return CaminhoCritico(
        menor_semestres=None if menor == INF else int(menor),
        menor_sem_calendario=None if menor_livre == INF else int(menor_livre),
        etapas=etapas, folga=folga_int, gargalos=gargalos,
        ciclos=ciclos_do_grafo(grafo), inalcancaveis=inalcancaveis,
    )


def simular_plano(
    semestres: Sequence[SemestrePlano],
    periodo_inicial: str,
    disciplinas: Mapping[int, Disciplina],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    turmas_por_disciplina: Mapping[int, Sequence[Turma]],
    limite_creditos: int | None,
    aprovadas: Collection[int] = (),
    cursando: Collection[int] = (),
    creditos_obrigatorios: int | None = None,
    creditos_optativos_exigidos: int | None = None,
    periodos_por_ano: int = 2,
    com_cenarios: bool = True,
) -> Simulacao:
    ppa = periodos_por_ano
    inicial = normalizar_periodo(periodo_inicial, ppa)
    if inicial is None:
        raise ValueError(f"periodo_inicial inválido: {periodo_inicial!r}")

    concluidas = set(aprovadas) | set(cursando)      # premissa: cursando termina antes do plano
    efetivas = periodicidades_efetivas(disciplinas.values())
    periodos, fora_de_ordem = _resolver_periodos(semestres, inicial, ppa)
    riscos: list[Risco] = []

    # ── itens válidos por semestre (desconhecidos e repetidos saem, sem derrubar nada) ──
    vistos: set[int] = set()
    ignorados: list[int] = []
    itens_por_semestre: list[list[ItemPlano]] = []
    for s in semestres:
        validos: list[ItemPlano] = []
        for it in s.itens:
            if it.disciplina_id not in disciplinas:
                ignorados.append(it.disciplina_id)
            elif it.disciplina_id in vistos:
                continue
            else:
                vistos.add(it.disciplina_id)
                validos.append(it)
        itens_por_semestre.append(validos)

    quadro = {  # períodos que já têm quadro de horários real no catálogo
        normalizar_periodo(t.periodo_letivo, ppa)
        for ts in turmas_por_disciplina.values() for t in ts
    } - {None}

    # ── semestre a semestre ──────────────────────────────────────────────────
    simulados: list[SemestreSimulado] = []
    horarios: dict[str, int] = {}
    ofertas: dict[str, int] = {}
    desconhecidas: list[int] = []
    for pos, (periodo, itens) in enumerate(zip(periodos, itens_por_semestre), start=1):
        selecoes: list[Selecao] = []
        origens: dict[int, str] = {}
        for it in itens:
            d = disciplinas[it.disciplina_id]
            turmas_d = turmas_por_disciplina.get(d.id, ())
            if it.encontros_livres:
                propria = _turma_propria(d.id, it.encontros_livres, periodo)
                selecoes.append(Selecao(d.id, (propria,), propria.id))
                origens[d.id] = HORARIO_PROPRIO
                continue
            candidatas, origem = turmas_para_periodo(turmas_d, periodo, ppa)
            escolhida = it.turma_id if origem == HORARIO_REAL and it.turma_id in {t.id for t in candidatas} else None
            selecoes.append(Selecao(d.id, candidatas, escolhida))
            origens[d.id] = origem

        alocacao = alocar_turmas(selecoes)
        por_selecao = {s.disciplina_id: s for s in selecoes}

        itens_sim: list[ItemSimulado] = []
        for it in itens:
            d = disciplinas[it.disciplina_id]
            ef = efetivas[d.id]
            ofertada = ofertada_em(ef.valor, periodo, ppa)
            turma_id = alocacao.escolha.get(d.id)
            turma = next((t for t in por_selecao[d.id].turmas_ofertadas if t.id == turma_id), None)
            itens_sim.append(ItemSimulado(
                disciplina_id=d.id, periodicidade=ef.valor, origem_periodicidade=ef.origem,
                ofertada=ofertada, horario_origem=origens[d.id], turma_id=turma_id,
                turma_codigo=turma.codigo_turma if turma else None,
                periodo_da_turma=turma.periodo_letivo if turma else None,
                encontros=turma.encontros if turma else (),
                turma_fixa=por_selecao[d.id].turma_escolhida_id is not None,
            ))
            horarios[origens[d.id]] = horarios.get(origens[d.id], 0) + 1
            ofertas[ef.origem] = ofertas.get(ef.origem, 0) + 1

            # oferta
            if not ofertada:
                tipo, grav = (R_FORA_DE_OFERTA, GRAVIDADE_ALTA) if ef.origem == ORIGEM_CADASTRADA \
                    else (R_OFERTA_ESTIMADA, GRAVIDADE_MEDIA)
                riscos.append(Risco(tipo, grav, pos, periodo, (d.id,), {
                    "periodicidade": ef.valor, "origem": ef.origem,
                    "proximo_periodo": proximo_periodo_ofertado(ef.valor, periodo, ppa),
                }))
            if ef.origem == ORIGEM_DESCONHECIDA:
                desconhecidas.append(d.id)
            # quadro do período existe, a disciplina não está nele (e já apareceu em outros períodos)
            if (periodo in quadro and origens[d.id] != HORARIO_REAL and origens[d.id] != HORARIO_PROPRIO
                    and turmas_d and not it.encontros_livres):
                riscos.append(Risco(R_SEM_TURMA_NO_QUADRO, GRAVIDADE_MEDIA, pos, periodo, (d.id,)))
            if d.id in concluidas:
                riscos.append(Risco(R_JA_CURSADA, GRAVIDADE_BAIXA, pos, periodo, (d.id,)))

        # conflitos que NENHUMA escolha de turma evita
        for c in alocacao.colisoes:
            a, b = c.disciplina_a, c.disciplina_b
            firme = all(origens[x] in (HORARIO_REAL, HORARIO_PROPRIO) for x in (a, b))
            riscos.append(Risco(R_CONFLITO, GRAVIDADE_ALTA if firme else GRAVIDADE_MEDIA, pos, periodo, (a, b), {
                "dia": c.sobreposicao.dia,
                "horario_a": _faixa(c.sobreposicao.a), "horario_b": _faixa(c.sobreposicao.b),
                "projetado": not firme,
            }))
        proj = tuple(sorted(d for d, o in origens.items() if o == HORARIO_PROJETADO))
        if proj:
            riscos.append(Risco(R_HORARIO_PROJETADO, GRAVIDADE_BAIXA, pos, periodo, proj))
        sem_h = tuple(sorted(d for d, o in origens.items() if o == HORARIO_DESCONHECIDO))
        if sem_h:
            riscos.append(Risco(R_HORARIO_DESCONHECIDO, GRAVIDADE_BAIXA, pos, periodo, sem_h))

        carga = avaliar_carga((disciplinas[i.disciplina_id] for i in itens), limite_creditos)
        if carga.sobrecarga:
            riscos.append(Risco(R_SOBRECARGA, GRAVIDADE_ALTA, pos, periodo, (), {
                "creditos": carga.creditos, "limite": carga.limite}))
        simulados.append(SemestreSimulado(
            pos, periodo, paridade_do_periodo(periodo, ppa), tuple(itens_sim),
            carga.creditos, limite_creditos, carga.sobrecarga, carga.disciplinas_sem_creditos,
        ))

    for pos in fora_de_ordem:
        riscos.append(Risco(R_PERIODO_FORA_DE_ORDEM, GRAVIDADE_ALTA, pos, periodos[pos - 1]))
    if desconhecidas:
        riscos.append(Risco(R_OFERTA_DESCONHECIDA, GRAVIDADE_BAIXA, None, None, tuple(sorted(set(desconhecidas)))))

    # ── pré/correquisitos (o planejado antes conta como concluído) ───────────
    ids_por_semestre = [{i.disciplina_id for i in itens} for itens in itens_por_semestre]
    for p in verificar_plano(ids_por_semestre, requisitos_por_disciplina, concluidas, ()):
        riscos.append(Risco(R_PRE_REQUISITO, GRAVIDADE_ALTA, p.posicao_semestre, periodos[p.posicao_semestre - 1],
                            (p.disciplina_id,), {"tipo": p.pendencia.tipo,
                                                 "alternativas": list(p.pendencia.alternativas)}))

    # ── o plano fecha o curso? ───────────────────────────────────────────────
    planejadas = set().union(*ids_por_semestre) if ids_por_semestre else set()
    feitas_ate_o_fim = concluidas | planejadas
    faltam = tuple(sorted(
        d.id for d in disciplinas.values() if d.tipo == TIPO_OBRIGATORIA and d.id not in feitas_ate_o_fim
    ))
    progresso = calcular_progresso(disciplinas.values(), feitas_ate_o_fim,
                                   creditos_obrigatorios, creditos_optativos_exigidos)
    com_itens = [s for s in simulados if s.itens]
    periodo_fim = com_itens[-1].periodo if com_itens else None
    completo = None if progresso.creditos_restantes is None else (progresso.creditos_restantes == 0 and not faltam)
    if faltam:
        riscos.append(Risco(R_FALTAM_OBRIGATORIAS, GRAVIDADE_MEDIA, None, None, faltam))

    estimada = None
    if (progresso.creditos_restantes or 0) > 0:
        restantes = progresso.creditos_restantes or 0
        cargas = [s.creditos for s in com_itens if s.creditos > 0]
        media = (sum(cargas) / len(cargas)) if cargas else (limite_creditos or 0)
        if restantes > 0 and media > 0:
            n = math.ceil(restantes / media)
            estimada = somar_periodos(periodo_fim or inicial, n, ppa)

    critico = _caminho_critico(disciplinas, requisitos_por_disciplina, concluidas, inicial, efetivas, ppa)

    # ── "e se eu reprovar?" ──────────────────────────────────────────────────
    cenarios: tuple[CenarioReprovacao, ...] = ()
    fim_base = -1
    if com_cenarios and ids_por_semestre and any(ids_por_semestre):
        oferta = _OfertaPorPeriodos(periodos, efetivas, ppa)
        base, cenarios = cenarios_de_reprovacao(
            ids_por_semestre, oferta, requisitos_por_disciplina,
            {i: d.creditos for i, d in disciplinas.items()}, limite_creditos, concluidas,
        )
        fim_base = base.fim

    premissas = [PREMISSA_PLANEJADO]
    if set(cursando) - set(aprovadas):
        premissas.insert(0, PREMISSA_CURSANDO)
    if horarios.get(HORARIO_PROJETADO):
        premissas.append(PREMISSA_HORARIO_PROJETADO)
    if ofertas.get(ORIGEM_ESTIMADA):
        premissas.append(PREMISSA_OFERTA_ESTIMADA)

    riscos.sort(key=lambda r: (ORDEM_GRAVIDADE[r.gravidade], r.posicao if r.posicao is not None else 10**6, r.tipo))
    por_gravidade = {g: sum(1 for r in riscos if r.gravidade == g) for g in ORDEM_GRAVIDADE}
    resumo = ResumoSimulacao(
        periodo_inicio=inicial, periodo_fim=periodo_fim, n_semestres=len(com_itens),
        creditos_planejados=sum(s.creditos for s in simulados),
        creditos_restantes=progresso.creditos_restantes,
        completo=completo,
        formatura_prevista=periodo_fim if completo else None,
        formatura_estimada=estimada,
        faltam_obrigatorias=faltam, riscos_por_gravidade=por_gravidade,
        horarios=horarios, ofertas=ofertas,
        atraso_maximo_reprovacao=max((c.atraso for c in cenarios), default=0),
    )
    return Simulacao(
        tuple(simulados), tuple(riscos), resumo, critico, cenarios, fim_base,
        tuple(premissas), tuple(sorted(set(ignorados))),
    )

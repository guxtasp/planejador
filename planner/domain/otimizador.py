"""
Sugestão de plano: distribui o que FALTA cursar pelos próximos semestres do melhor jeito possível.

É um problema de otimização com restrições. Cada disciplina pendente recebe um semestre:

  RESTRIÇÕES (duras)                                  OBJETIVOS (macios, com peso)
  · só em período em que é ofertada (par/ímpar)       · terminar o quanto antes (menor nº de semestres)
  · pré-requisito num semestre ANTERIOR               · carga equilibrada entre os semestres
  · correquisito no MESMO semestre ou antes           · sem choque de horário (inclusive projetado)
  · "A ou B": basta uma alternativa                   · gargalos cedo: quem destrava muita coisa vem antes
  · créditos por semestre ≤ teto                      · perto do período sugerido na matriz

Método, em três camadas (cada uma usa uma técnica diferente):

  1. GRAFOS (`grafo`)  — nós = disciplinas, arestas = requisitos. O caminho crítico com o calendário
     par/ímpar e a soma de créditos dão o LIMITE INFERIOR de semestres: abaixo disso é impossível.
     Se o plano atinge o limite, é ótimo (prova); senão, é o melhor encontrado.
  2. GULOSO            — escalonamento por lista: semestre a semestre, prioriza quem tem MENOR FOLGA
     (caminho crítico) e mais dependentes. Dá uma solução inicial boa e rápida.
  3. RECOZIMENTO SIMULADO (metaheurística) — melhora a solução movendo/trocando disciplinas de
     semestre; aceita piora com probabilidade que cai com a "temperatura", para escapar de mínimos
     locais. Sementeado: mesmo pedido, mesmo resultado.

Depois, a escolha de turmas de cada semestre é resolvida de uma vez (`alocacao`, busca com poda) e a
robustez é medida com `replanejamento` (atraso médio se alguém reprovar em qualquer disciplina).

Créditos de OPTATIVAS que ainda faltam não viram disciplinas (não se inventa o que escolher): viram
um bloco "reservar N créditos", distribuído nos semestres com folga (enchimento por nível).

Função pura, só stdlib.
"""
from __future__ import annotations

import math
import random
import time as relogio
from dataclasses import dataclass, field
from typing import Collection, Mapping, Sequence

from .alocacao import Colisao, alocar_turmas
from .conflitos import Selecao, sobreposicoes_entre_turmas
from .entidades import Disciplina, Requisito, Turma
from .grafo import (INF, construir_grafo, ciclos as ciclos_do_grafo, descendentes, menor_horizonte,
                    primeiros_semestres, ultimos_semestres)
from .periodicidade import HORARIO_REAL, turmas_para_periodo
from .previsao import somar_periodos
from .replanejamento import cenarios_de_reprovacao, robustez
from .restante import CalendarioDeOferta, nos_a_cursar, periodicidades_efetivas

PESO_DURA = 1000.0

# motivos de inviabilidade
M_CICLO = "ciclo"
M_INALCANCAVEL = "inalcancavel"
M_SEM_SOLUCAO = "sem_solucao"

# o que limita o prazo
LIM_REQUISITOS = "requisitos"
LIM_OFERTA = "oferta"
LIM_CREDITOS = "creditos"


@dataclass(frozen=True)
class ParametrosOtimizacao:
    max_creditos: int | None = None     # teto por semestre (curso e vontade do aluno já combinados)
    semestres_extras: int = 0           # folga voluntária: +N semestres para aliviar a carga
    max_semestres: int = 14
    semente: int = 2027
    iteracoes: int = 9000
    tempo_max_s: float = 2.5
    peso_equilibrio: float = 1.0
    peso_risco: float = 1.0
    peso_sugerido: float = 0.3
    peso_conflito: float = 40.0
    optativas_faltando: int = 0         # créditos de optativas ainda exigidos
    periodos_por_ano: int = 2


@dataclass(frozen=True)
class ItemSugerido:
    disciplina_id: int
    turma_id: int | None               # só quando o período já tem quadro real
    horario_origem: str                # real | projetado | desconhecido
    incluida_por_requisito: bool       # não era obrigatória: entrou porque algo exige


@dataclass(frozen=True)
class SemestreSugerido:
    posicao: int                       # a partir de 1
    periodo: str
    itens: tuple[ItemSugerido, ...]
    creditos: int
    creditos_optativos: int            # reserva de optativas neste semestre
    colisoes: tuple[Colisao, ...]


@dataclass(frozen=True)
class MetricasSugestao:
    n_semestres: int
    periodo_fim: str | None
    creditos_total: int
    carga_media: float
    carga_desvio: float
    carga_maxima: int
    colisoes: int
    atraso_medio_reprovacao: float
    atraso_maximo_reprovacao: int
    custo: float


@dataclass(frozen=True)
class ResultadoOtimizacao:
    viavel: bool
    motivo: str | None = None
    semestres: tuple[SemestreSugerido, ...] = ()
    metricas: MetricasSugestao | None = None
    limite_inferior: int = 0
    limitado_por: str | None = None
    otimo_comprovado: bool = False     # atingiu o limite inferior
    ciclos: tuple[tuple[int, ...], ...] = ()
    inalcancaveis: tuple[int, ...] = ()
    incluidas_por_requisito: tuple[int, ...] = ()
    optativas_reservadas: int = 0      # créditos de optativas pedidos
    optativas_encaixadas: int = 0      # os que couberam nos semestres existentes
    optativas_sem_encaixe: int = 0     # os que NÃO couberam (exigiriam semestres a mais)
    periodo_fim_com_optativas: str | None = None   # fim se as optativas sem encaixe ganhassem semestres
    iteracoes: int = 0
    semente: int = 0
    avisos: tuple[str, ...] = field(default_factory=tuple)


# ── modelo numérico do problema ───────────────────────────────────────────────
class _Modelo:
    """Disciplinas indexadas 0..n-1 e tudo pré-calculado que a busca consulta milhares de vezes."""

    def __init__(self, nos, grafo, disciplinas, turmas, calendario, p: ParametrosOtimizacao, hmax: int) -> None:
        self.ids = list(nos)
        self.idx = {d: i for i, d in enumerate(self.ids)}
        n = len(self.ids)
        self.n, self.p, self.calendario, self.hmax = n, p, calendario, hmax
        self.disciplinas, self.turmas = disciplinas, turmas
        self.cred = [disciplinas[d].creditos or 0 for d in self.ids]
        maior = max(self.cred, default=0)
        # nenhuma disciplina sozinha pode estourar o teto: senão seria inviável por construção
        self.cap = None if p.max_creditos is None else max(p.max_creditos, maior)
        self.termos = [
            [(tuple(self.idx[a] for a in t.alternativas), t.folga_entre_semestres) for t in grafo.termos[d]]
            for d in self.ids
        ]
        desc = descendentes(grafo)
        self.ndesc = [len(desc[d]) for d in self.ids]
        self.ofer = [[bool(calendario(d, t)) for t in range(hmax)] for d in self.ids]
        sugeridos = [disciplinas[d].periodo_sugerido for d in self.ids]
        base = min((s for s in sugeridos if s is not None), default=None)
        self.sug = [None if s is None or base is None else s - base for s in sugeridos]
        self.tem_turma = [bool(turmas.get(d)) for d in self.ids]
        self._col: dict[tuple[int, int, int], float] = {}
        self.extra: dict[tuple[int, int, int], float] = {}

    # colisão prevista entre duas disciplinas no semestre t (turmas projetadas se preciso)
    def colisao(self, a: int, b: int, t: int) -> float:
        chave = (a, b, t) if a < b else (b, a, t)
        v = self._col.get(chave)
        if v is None:
            periodo = self.calendario.periodo(t)
            ta, _ = turmas_para_periodo(self.turmas.get(self.ids[a], ()), periodo, self.p.periodos_por_ano)
            tb, _ = turmas_para_periodo(self.turmas.get(self.ids[b], ()), periodo, self.p.periodos_por_ano)
            if not ta or not tb:
                v = 0.0
            else:
                batem = sum(1 for x in ta for y in tb if sobreposicoes_entre_turmas(x, y))
                total = len(ta) * len(tb)
                v = 1.0 if batem == total else (0.15 * batem / total)   # parcial: dá pra escolher turma
            self._col[chave] = v
        return v + self.extra.get(chave, 0.0)

    def custo(self, asg: Sequence[int], h: int, alvo: float) -> tuple[float, float]:
        """(custo total, violações duras). Duras = 0 significa solução viável."""
        p, cap = self.p, self.cap
        duras = 0.0
        cargas = [0] * h
        por_sem: list[list[int]] = [[] for _ in range(h)]
        risco = sug = 0.0
        for i, t in enumerate(asg):
            if not self.ofer[i][t]:
                duras += 1
            cargas[t] += self.cred[i]
            for alts, folga in self.termos[i]:
                m = min(asg[a] for a in alts) + folga
                if m > t:
                    duras += m - t
            risco += self.ndesc[i] * t
            s = self.sug[i]
            if s is not None:
                sug += abs(t - s)
            if self.tem_turma[i]:
                por_sem[t].append(i)
        if cap is not None:
            for c in cargas:
                if c > cap:
                    duras += c - cap
        equilibrio = sum((c - alvo) ** 2 for c in cargas)
        colisoes = 0.0
        for t, lista in enumerate(por_sem):
            for x in range(len(lista)):
                for y in range(x + 1, len(lista)):
                    colisoes += self.colisao(lista[x], lista[y], t)
        soft = (0.5 * p.peso_equilibrio * equilibrio + 0.6 * p.peso_risco * risco
                + p.peso_sugerido * sug + p.peso_conflito * colisoes)
        return PESO_DURA * duras + soft, duras

    def requisitos_ok(self, i: int, t: int, asg: Sequence[int]) -> bool:
        for alts, folga in self.termos[i]:
            if not any(asg[a] != -1 and asg[a] + folga <= t for a in alts):
                return False
        return True

    def guloso(self, h: int, ultimos: Mapping[int, float]) -> list[int]:
        """Escalonamento por lista: menor folga primeiro; respeita oferta, requisitos e teto."""
        asg = [-1] * self.n
        restante = sum(self.cred)
        ordem = sorted(range(self.n), key=lambda i: (
            (ultimos.get(self.ids[i], h) - 0) , -self.ndesc[i], -self.cred[i],
            self.sug[i] if self.sug[i] is not None else 99, self.ids[i]))
        for t in range(h):
            alvo_t = math.ceil(restante / (h - t)) if h - t > 0 else restante
            carga = 0
            mudou = True
            while mudou:
                mudou = False
                for i in ordem:
                    if asg[i] != -1 or not self.ofer[i][t] or not self.requisitos_ok(i, t, asg):
                        continue
                    urgente = ultimos.get(self.ids[i], h) <= t     # sem folga: tem que ser agora
                    if self.cap is not None and carga and carga + self.cred[i] > self.cap:
                        continue
                    if not urgente and carga >= alvo_t:
                        continue
                    asg[i] = t
                    carga += self.cred[i]
                    restante -= self.cred[i]
                    mudou = True
        for i in range(self.n):          # sobrou: põe no último semestre ofertado (a busca conserta)
            if asg[i] == -1:
                asg[i] = next((t for t in range(h - 1, -1, -1) if self.ofer[i][t]), h - 1)
        return asg

    def recozer(self, inicial: Sequence[int], h: int, alvo: float, iteracoes: int,
                rng: random.Random, limite_tempo: float) -> tuple[list[int], float, float, int]:
        """Recozimento simulado. Devolve (melhor, custo, duras, iterações feitas)."""
        atual = list(inicial)
        c_atual, d_atual = self.custo(atual, h, alvo)
        melhor, c_melhor, d_melhor = list(atual), c_atual, d_atual
        viaveis = [[t for t in range(h) if self.ofer[i][t]] for i in range(self.n)]
        mexiveis = [i for i in range(self.n) if len(viaveis[i]) > 1]
        if not mexiveis or iteracoes <= 0:
            return melhor, c_melhor, d_melhor, 0
        t0, tf = 25.0, 0.15
        alfa = (tf / t0) ** (1.0 / iteracoes)
        temp = t0
        feitas = 0
        for k in range(iteracoes):
            feitas = k + 1
            if k % 200 == 0 and relogio.monotonic() > limite_tempo:
                break
            temp *= alfa
            if rng.random() < 0.7:                               # mover uma disciplina
                i = rng.choice(mexiveis)
                novo = rng.choice(viaveis[i])
                if novo == atual[i]:
                    continue
                antigo = atual[i]
                atual[i] = novo
                c_novo, d_novo = self.custo(atual, h, alvo)
                if c_novo <= c_atual or rng.random() < math.exp((c_atual - c_novo) / temp):
                    c_atual, d_atual = c_novo, d_novo
                else:
                    atual[i] = antigo
            else:                                                # trocar duas de semestre
                i, j = rng.choice(mexiveis), rng.choice(mexiveis)
                ti, tj = atual[i], atual[j]
                if i == j or ti == tj or not self.ofer[i][tj] or not self.ofer[j][ti]:
                    continue
                atual[i], atual[j] = tj, ti
                c_novo, d_novo = self.custo(atual, h, alvo)
                if c_novo <= c_atual or rng.random() < math.exp((c_atual - c_novo) / temp):
                    c_atual, d_atual = c_novo, d_novo
                else:
                    atual[i], atual[j] = ti, tj
            if c_atual < c_melhor:
                melhor, c_melhor, d_melhor = list(atual), c_atual, d_atual
        return melhor, c_melhor, d_melhor, feitas


# ── optativas: enchimento por nível ───────────────────────────────────────────
def distribuir_optativas(cargas: Sequence[int], teto: int | None, faltando: int) -> tuple[list[int], int]:
    """
    Reparte `faltando` créditos de optativas entre os semestres, sempre no de MENOR carga que
    ainda tenha espaço. Sem espaço (e com teto conhecido), cria semestres no fim.
    Devolve (créditos de optativa por semestre — pode ter semestres a mais, semestres criados).
    """
    total = list(cargas)
    extra = [0] * len(total)
    criados = 0
    while faltando > 0:
        abertos = [k for k in range(len(total)) if teto is None or total[k] < teto]
        if not abertos:
            total.append(0)
            extra.append(0)
            criados += 1
            continue
        k = min(abertos, key=lambda x: (total[x], x))
        total[k] += 1
        extra[k] += 1
        faltando -= 1
    return extra, criados


def encaixar_optativas(cargas: Sequence[int], teto: int | None, faltando: int) -> tuple[list[int], int]:
    """
    Como `distribuir_optativas`, mas NUNCA cria semestres: só usa os que existem.
    Devolve (créditos de optativa por semestre, créditos que não couberam).
    Sem teto conhecido tudo cabe (reparte no de menor carga).
    """
    total = list(cargas)
    extra = [0] * len(total)
    if not total:
        return extra, max(0, faltando)
    while faltando > 0:
        abertos = [k for k in range(len(total)) if teto is None or total[k] < teto]
        if not abertos:
            break
        k = min(abertos, key=lambda x: (total[x], x))
        total[k] += 1
        extra[k] += 1
        faltando -= 1
    return extra, faltando


# ── entrada principal ─────────────────────────────────────────────────────────
def otimizar_plano(
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
    turmas_por_disciplina: Mapping[int, Sequence[Turma]],
    concluidas: Collection[int],
    periodo_inicial: str,
    parametros: ParametrosOtimizacao | None = None,
    extras: Collection[int] = (),
) -> ResultadoOtimizacao:
    p = parametros or ParametrosOtimizacao()
    ppa = p.periodos_por_ano
    inicio_relogio = relogio.monotonic()
    prazo = inicio_relogio + p.tempo_max_s
    rng = random.Random(p.semente)

    nos, incluidas = nos_a_cursar(disciplinas, requisitos, concluidas, extras)
    efetivas = periodicidades_efetivas(disciplinas.values())
    calendario = CalendarioDeOferta(periodo_inicial, efetivas, ppa)

    if not nos:
        return _montar(None, [], disciplinas, turmas_por_disciplina, calendario, p, (), 0, 0, None, 0, 0, prazo)

    grafo = construir_grafo(nos, requisitos, concluidas)
    cs = ciclos_do_grafo(grafo)
    if cs:
        return ResultadoOtimizacao(False, M_CICLO, ciclos=cs, incluidas_por_requisito=incluidas, semente=p.semente)

    hmax = max(1, p.max_semestres)
    primeiros = primeiros_semestres(grafo, hmax, calendario)
    inalcancaveis = tuple(sorted(n for n, v in primeiros.items() if v == INF))
    if inalcancaveis:
        return ResultadoOtimizacao(False, M_INALCANCAVEL, inalcancaveis=inalcancaveis,
                                   incluidas_por_requisito=incluidas, semente=p.semente)

    modelo = _Modelo(nos, grafo, disciplinas, turmas_por_disciplina, calendario, p, hmax)
    modelo.requisitos_originais = requisitos      # o replanejamento ("e se eu reprovar") precisa deles
    lb_grafo = int(menor_horizonte(primeiros))
    livres = primeiros_semestres(grafo, hmax, lambda _n, _t: True)
    lb_livre = int(menor_horizonte(livres))
    total_cred = sum(modelo.cred)   # optativas não adiam o prazo: ver `encaixar_optativas`
    lb_cred = math.ceil(total_cred / modelo.cap) if modelo.cap else 0
    limite_inferior = max(lb_grafo, lb_cred, 1)
    if lb_cred > lb_grafo:
        limitado_por = LIM_CREDITOS
    else:
        limitado_por = LIM_OFERTA if lb_grafo > lb_livre else LIM_REQUISITOS

    def resolver(h: int, iteracoes: int) -> tuple[list[int], float, float, int]:
        ultimos = ultimos_semestres(grafo, h, calendario)
        alvo = sum(modelo.cred) / h
        asg = modelo.guloso(h, ultimos)
        custo, duras = modelo.custo(asg, h, alvo)
        feitas = 0
        if duras > 0 or iteracoes > 0:
            asg2, c2, d2, feitas = modelo.recozer(asg, h, alvo, iteracoes, rng, prazo)
            if (d2, c2) <= (duras, custo):
                asg, custo, duras = asg2, c2, d2
        return asg, custo, duras, feitas

    # 1) menor h viável, subindo a partir do limite inferior
    h0, achada, iteracoes_total = None, None, 0
    for h in range(limite_inferior, hmax + 1):
        asg, custo, duras, feitas = resolver(h, min(2500, p.iteracoes))
        iteracoes_total += feitas
        if duras == 0:
            h0, achada = h, asg
            break
        if relogio.monotonic() > prazo:
            break
    if h0 is None:
        return ResultadoOtimizacao(False, M_SEM_SOLUCAO, limite_inferior=limite_inferior,
                                   limitado_por=limitado_por, incluidas_por_requisito=incluidas,
                                   iteracoes=iteracoes_total, semente=p.semente)

    # 2) refino no h escolhido (+ folga voluntária), com colisões previstas realimentando a busca
    h_final = min(h0 + max(0, p.semestres_extras), hmax)
    melhor_asg, melhor_custo = achada, None
    for rodada in range(3):
        asg, custo, duras, feitas = resolver(h_final, p.iteracoes if rodada == 0 else max(1500, p.iteracoes // 3))
        iteracoes_total += feitas
        if duras == 0 and (melhor_custo is None or custo < melhor_custo or h_final != h0):
            melhor_asg, melhor_custo = asg, custo
        elif melhor_custo is None and duras == 0:
            melhor_asg, melhor_custo = asg, custo
        reais = _colisoes_reais(modelo, melhor_asg, h_final)
        if not reais:
            break
        for (a, b, t) in reais:                      # empurra a busca para longe do choque inevitável
            chave = (a, b, t) if a < b else (b, a, t)
            modelo.extra[chave] = modelo.extra.get(chave, 0.0) + 2.0

    return _montar(modelo, melhor_asg, disciplinas, turmas_por_disciplina, calendario, p,
                   incluidas, limite_inferior, h_final, limitado_por, h0, iteracoes_total, prazo,
                   grafo_nos=nos)


def _colisoes_reais(modelo: _Modelo, asg: Sequence[int], h: int) -> list[tuple[int, int, int]]:
    """Colisões que NENHUMA escolha de turma evita, semestre a semestre (alocação exata)."""
    saida = []
    for t in range(h):
        membros = [i for i, x in enumerate(asg) if x == t and modelo.tem_turma[i]]
        if len(membros) < 2:
            continue
        periodo = modelo.calendario.periodo(t)
        selecoes = []
        for i in membros:
            cand, _ = turmas_para_periodo(modelo.turmas.get(modelo.ids[i], ()), periodo, modelo.p.periodos_por_ano)
            selecoes.append(Selecao(modelo.ids[i], cand, None))
        for c in alocar_turmas(selecoes).colisoes:
            saida.append((modelo.idx[c.disciplina_a], modelo.idx[c.disciplina_b], t))
    return saida


def _montar(modelo, asg, disciplinas, turmas, calendario, p, incluidas, limite_inferior, h, limitado_por,
            h0, iteracoes, prazo, grafo_nos=()) -> ResultadoOtimizacao:
    ppa = p.periodos_por_ano
    por_sem: list[list[int]] = [[] for _ in range(h)]
    if modelo is not None:
        for i, t in enumerate(asg):
            por_sem[t].append(modelo.ids[i])

    semestres: list[SemestreSugerido] = []
    cargas = [sum(disciplinas[d].creditos or 0 for d in ids) for ids in por_sem]
    teto_opt = modelo.cap if modelo else p.max_creditos
    ultimo_obrig = max((k for k, ids in enumerate(por_sem) if ids), default=-1)
    if ultimo_obrig >= 0:
        # optativas só entram nos semestres que as obrigatórias já usam; o resto vira aviso
        extra_opt, sobra = encaixar_optativas(cargas[:ultimo_obrig + 1], teto_opt, p.optativas_faltando)
        extra_opt += [0] * (len(por_sem) - len(extra_opt))
        n_novos = (math.ceil(sobra / teto_opt) if teto_opt else 1) if sobra else 0
        fim_com_opt = calendario.periodo(ultimo_obrig + n_novos)
    else:
        # nada de obrigatória a cursar: as optativas são tudo o que falta e formam os próprios semestres
        extra_opt, _criados = distribuir_optativas([], teto_opt, p.optativas_faltando)
        sobra = 0
        fim_com_opt = calendario.periodo(len(extra_opt) - 1) if extra_opt else None
    total_semestres = max(len(por_sem), len(extra_opt))
    por_sem += [[] for _ in range(total_semestres - len(por_sem))]
    cargas += [0] * (total_semestres - len(cargas))

    n_colisoes = 0
    for t, ids in enumerate(por_sem):
        periodo = calendario.periodo(t)
        selecoes, origens = [], {}
        for d in sorted(ids):
            cand, origem = turmas_para_periodo(turmas.get(d, ()), periodo, ppa)
            selecoes.append(Selecao(d, cand, None))
            origens[d] = origem
        aloc = alocar_turmas(selecoes)
        n_colisoes += len(aloc.colisoes)
        itens = tuple(ItemSugerido(
            d, aloc.escolha.get(d) if origens[d] == HORARIO_REAL else None, origens[d], d in incluidas,
        ) for d in sorted(ids))
        semestres.append(SemestreSugerido(t + 1, periodo, itens, cargas[t] + 0, extra_opt[t], aloc.colisoes))

    # robustez: atraso se alguém reprovar, usando o plano sugerido executado de verdade
    plano_ids = [set(ids) for ids in por_sem]
    oferta = _OfertaIdx(calendario)
    medio, pior = 0.0, 0
    if modelo is not None and any(plano_ids):
        _base, cen = cenarios_de_reprovacao(
            plano_ids, oferta, _requisitos_de(disciplinas, modelo), {i: d.creditos for i, d in disciplinas.items()},
            modelo.cap, (),
        )
        medio, pior = robustez(cen)

    cargas_tot = [s.creditos + s.creditos_optativos for s in semestres]
    ativos = [c for c in cargas_tot if c > 0] or [0]
    media = sum(ativos) / len(ativos)
    desvio = math.sqrt(sum((c - media) ** 2 for c in ativos) / len(ativos))
    ultimo = max((k for k, s in enumerate(semestres) if s.itens or s.creditos_optativos), default=-1)
    metricas = MetricasSugestao(
        n_semestres=ultimo + 1, periodo_fim=calendario.periodo(ultimo) if ultimo >= 0 else None,
        creditos_total=sum(cargas_tot), carga_media=round(media, 1), carga_desvio=round(desvio, 1),
        carga_maxima=max(cargas_tot, default=0), colisoes=n_colisoes,
        atraso_medio_reprovacao=round(medio, 2), atraso_maximo_reprovacao=pior,
        custo=0.0,
    )
    semestres = [s for k, s in enumerate(semestres) if k <= ultimo]
    return ResultadoOtimizacao(
        viavel=True, semestres=tuple(semestres), metricas=metricas,
        limite_inferior=limite_inferior,
        limitado_por=limitado_por,
        otimo_comprovado=bool(h0) and h0 == limite_inferior and p.semestres_extras == 0 and ultimo + 1 == h0,
        incluidas_por_requisito=tuple(incluidas), optativas_reservadas=p.optativas_faltando,
        optativas_encaixadas=p.optativas_faltando - sobra, optativas_sem_encaixe=sobra,
        periodo_fim_com_optativas=fim_com_opt if p.optativas_faltando else metricas.periodo_fim,
        iteracoes=iteracoes, semente=p.semente,
    )


class _OfertaIdx:
    def __init__(self, calendario: CalendarioDeOferta) -> None:
        self.c = calendario

    def __call__(self, d: int, t: int) -> bool:
        return self.c(d, t)


def _requisitos_de(disciplinas, modelo):
    """Requisitos já guardados no modelo não são reexportados; reconstrói a partir de `_Modelo.requisitos`."""
    return modelo.requisitos_originais


# `_Modelo` guarda os requisitos originais para o replanejamento (atribuído em `otimizar_plano`)

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
     par/ímpar e o raciocínio "energético" sobre créditos (o que não cabe antes/depois de cada
     semestre, e janelas [mais cedo, mais tarde]) dão o LIMITE INFERIOR de semestres: abaixo disso é
     impossível. Se o plano atinge o limite, é ótimo (prova); senão, é o melhor encontrado.
     A CADEIA CRÍTICA (A → B → C que define o prazo) sai explícita.
  2. GULOSO            — escalonamento por lista (estilo Hu / Coffman-Graham): semestre a semestre,
     prioriza MENOR FOLGA, depois maior ALTURA no grafo e maior PESO POSICIONAL (créditos presos
     atrás). Dá uma solução inicial boa e rápida.
  3. RECOZIMENTO SIMULADO (metaheurística) — melhora a solução com movimentos que preservam a
     viabilidade (janela, cadeia, troca), custo avaliado por DELTA, temperatura calibrada,
     reaquecimento e reinícios com sementes derivadas. Sementeado: mesmo pedido, mesmo resultado.

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
from dataclasses import dataclass, field, replace as _replace
from typing import Collection, Mapping, Sequence

from .alocacao import ChoqueItem, Colisao, alocar_turmas, choques_por_disciplina
from .preferencias import SEM_PREFERENCIAS, PreferenciasAluno
from .semana import MetricasSemana, bate_indisponivel, metricas_semana, turno_do
from .conflitos import Selecao, sobreposicoes_entre_turmas
from .entidades import Disciplina, Requisito, Turma
from .grafo import (INF, alturas, cadeia_critica, construir_grafo, ciclos as ciclos_do_grafo, descendentes,
                    horizonte_por_janelas, limite_energetico, menor_horizonte, pesos_posicionais,
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
    reinicios: int = 3                  # corridas do recozimento com sementes derivadas (fica a melhor)
    peso_equilibrio: float = 1.0
    peso_risco: float = 1.0
    peso_sugerido: float = 0.3
    peso_conflito: float = 40.0
    optativas_faltando: int = 0         # créditos de optativas ainda exigidos
    periodos_por_ano: int = 2
    # preferências do aluno: teto por período e trancamento são DUROS; o resto é penalidade macia
    preferencias: PreferenciasAluno = SEM_PREFERENCIAS
    peso_preferencias: float = 1.0      # turno, dias livres e horário indisponível (por disciplina)
    peso_sem_saida: float = 30.0        # todas as turmas da disciplina caem num horário indisponível
    peso_pesadas: float = 30.0          # por disciplina "pesada" acima do máximo no semestre
    peso_juntas: float = 20.0           # por grupo "cursar junto" (preferência) separado
    peso_fim: float = 60.0              # por semestre que uma disciplina de fim de curso (TCC…) fica antes do lugar
    peso_meio: float = 3.0              # por semestre que um bloco de optativa fica longe do meio do curso


@dataclass(frozen=True)
class ItemSugerido:
    disciplina_id: int
    turma_id: int | None               # só quando o período já tem quadro real
    horario_origem: str                # real | projetado | desconhecido
    incluida_por_requisito: bool       # não era obrigatória: entrou porque algo exige
    choques: tuple[ChoqueItem, ...] = ()
    bate_indisponivel: bool = False


@dataclass(frozen=True)
class SemestreSugerido:
    posicao: int                       # a partir de 1
    periodo: str
    itens: tuple[ItemSugerido, ...]
    creditos: int
    creditos_optativos: int            # reserva de optativas neste semestre
    colisoes: tuple[Colisao, ...]
    semana: MetricasSemana | None = None
    pesadas: tuple[int, ...] = ()
    trancado: bool = False             # período que o aluno vai trancar (fica vazio de propósito)


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
    cadeia_critica: tuple[int, ...] = ()   # A → B → C que define o prazo (ids, da primeira à última)
    grupos_aplicados: tuple[tuple[int, ...], ...] = ()   # blocos "cursar junto" respeitados
    fim_de_curso: Mapping[int, int] = field(default_factory=dict)   # TCC & cia: id → degrau (0 = último)
    fixas_respeitadas: Mapping[int, str] = field(default_factory=dict)   # disciplina → período pedido pelo aluno
    fixas_ignoradas: Mapping[int, str] = field(default_factory=dict)     # disciplina → motivo (nao_abre | requisitos)
    partiu_do_plano: bool = False       # o plano do aluno entrou como ponto de partida da busca
    tempos_ms: Mapping[str, int] = field(default_factory=dict)   # grafo | guloso | recozimento | turmas
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


class _CalendarioComTrancamento:
    """O calendário de oferta, mas sem nada nos períodos que o aluno vai trancar."""

    def __init__(self, calendario: CalendarioDeOferta, pulados) -> None:
        self.c, self.pulados = calendario, frozenset(pulados)

    def periodo(self, indice: int) -> str:
        return self.c.periodo(indice)

    def __call__(self, disciplina_id: int, indice: int) -> bool:
        return self.c(disciplina_id, indice) and self.c.periodo(indice) not in self.pulados


class _CalendarioComQuadro:
    """
    Quadro de turmas já publicado manda: se o período tem quadro e a disciplina (que tem turmas em
    outros períodos) não está nele, ela não abre ali. Mesma regra do aviso `sem_turma_no_quadro`
    do simulador — a sugestão não pode pôr a disciplina onde o próprio app acusaria o problema.
    """

    def __init__(self, calendario, turmas_por_disciplina: Mapping[int, Sequence[Turma]]) -> None:
        self.c = calendario
        self.com_quadro = frozenset(t.periodo_letivo for ts in turmas_por_disciplina.values() for t in ts
                                    if t.periodo_letivo)
        self.periodos_de = {d: frozenset(t.periodo_letivo for t in ts if t.periodo_letivo)
                            for d, ts in turmas_por_disciplina.items() if ts}

    def periodo(self, indice: int) -> str:
        return self.c.periodo(indice)

    def fora_do_quadro(self, disciplina_id: int, periodo: str) -> bool:
        seus = self.periodos_de.get(disciplina_id)
        return bool(seus) and periodo in self.com_quadro and periodo not in seus

    def __call__(self, disciplina_id: int, indice: int) -> bool:
        return self.c(disciplina_id, indice) and not self.fora_do_quadro(disciplina_id, self.c.periodo(indice))


class _CalendarioComFixas:
    """A disciplina fixada pelo aluno só "abre" no período que ele escolheu."""

    def __init__(self, calendario, fixas: Mapping[int, str]) -> None:
        self.c, self.fixas = calendario, dict(fixas)

    def periodo(self, indice: int) -> str:
        return self.c.periodo(indice)

    def __call__(self, disciplina_id: int, indice: int) -> bool:
        alvo = self.fixas.get(disciplina_id)
        return self.c(disciplina_id, indice) and (alvo is None or self.c.periodo(indice) == alvo)


# Optativas que ainda faltam entram na otimização como BLOCOS (sem requisito, abrem todo período):
# assim o plano já nasce com espaço para elas — no meio do curso — e a formatura conta com elas.
ID_BLOCO_OPTATIVA = -1_000_000_000


def _blocos_de_optativa(faltando: int, disciplinas: Mapping[int, Disciplina]) -> dict[int, Disciplina]:
    if faltando <= 0:
        return {}
    creditos = sorted(d.creditos for d in disciplinas.values() if d.tipo != "obrigatoria" and d.creditos)
    tamanho = creditos[len(creditos) // 2] if creditos else 4       # a optativa típica do curso (mediana)
    blocos, k = {}, 0
    while faltando > 0:
        cred = min(tamanho, faltando)
        bid = ID_BLOCO_OPTATIVA - k
        blocos[bid] = Disciplina(bid, "OPTATIVA", "Optativa (a escolher)", cred, "optativa", None, None)
        faltando -= cred
        k += 1
    return blocos


class _CalendarioComGrupos:
    """O bloco de um grupo "cursar junto" só abre quando TODOS os membros abrem (interseção das ofertas)."""

    def __init__(self, calendario, membros: Mapping[int, tuple[int, ...]]) -> None:
        self.c, self.membros = calendario, membros

    def periodo(self, indice: int) -> str:
        return self.c.periodo(indice)

    def __call__(self, disciplina_id: int, indice: int) -> bool:
        return all(self.c(m, indice) for m in self.membros.get(disciplina_id, (disciplina_id,)))


def _grupos_aplicaveis(juntas, nos, disciplinas, requisitos) -> tuple[list[tuple[int, ...]], list[tuple[int, ...]]]:
    """(obrigatórios, preferências) válidos, só com os membros que estão no que falta cursar (2+)."""
    from .juntas import problemas_do_grupo
    conjunto = set(nos)
    obrig, pref = [], []
    for g in juntas:
        membros = tuple(sorted(i for i in g.disciplinas if i in conjunto))
        if len(membros) < 2 or problemas_do_grupo(g, disciplinas, requisitos):
            continue                  # grupo impossível: avisado na tela, não aplicado
        (obrig if g.obrigatoria else pref).append(membros)
    # um membro só pode estar num bloco obrigatório: grupos que se tocam viram um só
    unidos: list[set[int]] = []
    for g in obrig:
        juntos = [u for u in unidos if u & set(g)]
        novo = set(g).union(*juntos) if juntos else set(g)
        unidos = [u for u in unidos if not (u & set(g))] + [novo]
    return [tuple(sorted(u)) for u in unidos], pref


def _contrair(nos, disciplinas, requisitos, turmas, blocos):
    """
    Cada bloco vira UMA disciplina virtual (id = menor membro): créditos somados, período sugerido = o
    menor, requisitos = união (sem os internos), e cada "turma" = uma combinação de turmas dos membros
    no MESMO período (encontros somados). Quem exigia um membro passa a exigir o bloco.
    """
    rep_de = {m: min(b) for b in blocos for m in b}
    membros = {min(b): b for b in blocos}
    disc_v = dict(disciplinas)
    for rep, b in membros.items():
        ds = [disciplinas[m] for m in b]
        cred = sum(d.creditos_no_limite for d in ds)       # o bloco ocupa do limite o que os membros ocupam
        sugeridos = [d.periodo_sugerido for d in ds if d.periodo_sugerido is not None]
        base = disciplinas[rep]
        disc_v[rep] = Disciplina(rep, base.codigo, base.nome, cred, base.tipo,
                                 min(sugeridos) if sugeridos else None, base.periodicidade)
    req_v: dict[int, list[Requisito]] = {}
    for d, rs in requisitos.items():
        alvo = rep_de.get(d, d)
        for r in rs:
            q = rep_de.get(r.requisito_id, r.requisito_id)
            if q == alvo:
                continue                                  # requisito interno ao bloco
            grupo = f"{d}:{r.grupo_alt}" if r.grupo_alt and d in rep_de else r.grupo_alt
            req_v.setdefault(alvo, []).append(Requisito(alvo, q, r.tipo, grupo))
    turmas_v = dict(turmas)
    proximo_id = -1_000_000
    for rep, b in membros.items():
        por_periodo: dict[str, list[list[Turma]]] = {}
        for m in b:
            for t in turmas.get(m, ()):
                por_periodo.setdefault(t.periodo_letivo, [[] for _ in b])[b.index(m)].append(t)
        combinadas = []
        for periodo, listas in sorted(por_periodo.items(), key=lambda x: str(x[0])):
            if any(not l for l in listas):
                continue                                  # algum membro sem turma nesse período
            combos = [[]]
            for l in listas:
                combos = [c + [t] for c in combos for t in l][:64]
            for c in combos:
                proximo_id -= 1
                combinadas.append(Turma(proximo_id, rep, tuple(e for t in c for e in t.encontros), periodo, "+".join(
                    t.codigo_turma or "?" for t in c)))
        turmas_v[rep] = combinadas
        for m in b:
            if m != rep:
                turmas_v.pop(m, None)
    nos_v = tuple(sorted({rep_de.get(n, n) for n in nos}))
    return nos_v, disc_v, req_v, turmas_v, membros


# ── modelo numérico do problema ───────────────────────────────────────────────
class _Modelo:
    """Disciplinas indexadas 0..n-1 e tudo pré-calculado que a busca consulta milhares de vezes."""

    def __init__(self, nos, grafo, disciplinas, requisitos, turmas, calendario,
                 p: ParametrosOtimizacao, hmax: int, fim_de_curso: Mapping[int, int] | None = None,
                 grupos_pref: Sequence[Sequence[int]] = ()) -> None:
        self.ids = list(nos)
        self.idx = {d: i for i, d in enumerate(self.ids)}
        n = len(self.ids)
        self.n, self.p, self.calendario, self.hmax = n, p, calendario, hmax
        self.disciplinas, self.turmas = disciplinas, turmas
        self.requisitos = requisitos          # catálogo completo: o replanejamento ("e se eu reprovar") usa
        self.cred = [disciplinas[d].creditos_no_limite for d in self.ids]   # o que ocupa do limite do semestre
        maior = max(self.cred, default=0)
        # nenhuma disciplina sozinha pode estourar o teto: senão seria inviável por construção
        self.cap = None if p.max_creditos is None else max(p.max_creditos, maior)
        prefs = p.preferencias
        self.prefs = prefs
        # teto de cada semestre: o específico do aluno vale no lugar do geral; trancado = 0
        self.cap_t: list[int | None] = []
        for t in range(hmax):
            teto = prefs.teto(calendario.periodo(t), p.max_creditos)
            self.cap_t.append(None if teto is None else (0 if teto == 0 else max(teto, maior)))
        self.pesada = [d in prefs.pesadas for d in self.ids]
        # TCC e cia.: degrau dentro do fim de curso (0 = último semestre); None = disciplina comum
        fim = fim_de_curso or {}
        self.degrau: list[int | None] = [fim.get(d) for d in self.ids]
        self.no_meio = [d <= ID_BLOCO_OPTATIVA + 10**6 for d in self.ids]      # blocos de optativa
        # grupos "cursar junto" de preferência (índices do modelo)
        self.grupos_pref: list[list[int]] = []
        self.grupos_de: list[list[int]] = [[] for _ in range(n)]
        for g in grupos_pref:
            indices = sorted({self.idx[i] for i in g if i in self.idx})
            if len(indices) > 1:
                for i in indices:
                    self.grupos_de[i].append(len(self.grupos_pref))
                self.grupos_pref.append(indices)
        self.max_pesadas = prefs.max_pesadas
        self._ind: dict[tuple[int, int], float] = {}
        self.termos = [
            [(tuple(self.idx[a] for a in t.alternativas), t.folga_entre_semestres) for t in grafo.termos[d]]
            for d in self.ids
        ]
        # termos em que cada disciplina aparece como alternativa: (dependente, nº do termo)
        self.usado_em: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        for j, ts in enumerate(self.termos):
            for k, (alts, _f) in enumerate(ts):
                for a in sorted(set(alts)):
                    self.usado_em[a].append((j, k))
        # termos cuja violação muda quando a disciplina i muda de semestre (os dela + os que a usam)
        self.afetados = [sorted({(i, k) for k in range(len(self.termos[i]))} | set(self.usado_em[i]))
                         for i in range(n)]
        desc = descendentes(grafo)
        self.ndesc = [len(desc[d]) for d in self.ids]
        alt = alturas(grafo)
        peso = pesos_posicionais(grafo, {d: disciplinas[d].creditos for d in self.ids})
        self.altura = [alt[d] for d in self.ids]
        self.peso = [peso[d] for d in self.ids]
        self.ofer = [[bool(calendario(d, t)) for t in range(hmax)] for d in self.ids]
        sugeridos = [disciplinas[d].periodo_sugerido for d in self.ids]
        base = min((s for s in sugeridos if s is not None), default=None)
        self.sug = [None if s is None or base is None else s - base for s in sugeridos]
        self.tem_turma = [bool(turmas.get(d)) for d in self.ids]
        self._col: dict[tuple[int, int, int], float] = {}
        self.extra: dict[tuple[int, int, int], float] = {}
        self._linhas: dict[tuple[int, int], list[float]] = {}   # (i, t) → colisão de i com cada j em t

    def linha_colisao(self, i: int, t: int) -> list[float]:
        """Colisão de i com cada disciplina no semestre t, numa lista (a busca consulta muito)."""
        linha = self._linhas.get((i, t))
        if linha is None:
            linha = [self.colisao(i, j, t) if j != i and self.tem_turma[j] else 0.0 for j in range(self.n)]
            self._linhas[(i, t)] = linha
        return linha

    def individual(self, i: int, t: int) -> float:
        """
        Quanto custa pôr i no semestre t pelas preferências da semana (turno, dias livres, horário
        indisponível): a MELHOR turma dela no período. Se todas caem num horário indisponível, soma
        `peso_sem_saida` (não há turma alternativa; a busca tenta outro semestre).
        """
        semana = self.prefs.semana
        if semana is None or not self.tem_turma[i]:
            return 0.0
        v = self._ind.get((i, t))
        if v is None:
            turmas, _ = turmas_para_periodo(self.turmas.get(self.ids[i], ()), self.calendario.periodo(t),
                                            self.p.periodos_por_ano)
            v = 0.0
            if turmas:
                notas = []
                for tu in turmas:
                    bloq = sum(1 for e in tu.encontros if bate_indisponivel(e, semana.indisponiveis))
                    fora = sum(1 for e in tu.encontros if semana.turno and turno_do(e) != semana.turno)
                    livres = len({e.dia for e in tu.encontros} & set(semana.dias_livres))
                    notas.append((bloq > 0, semana.peso_indisponivel * bloq + semana.peso_turno * fora
                                  + semana.peso_dia_livre * livres))
                sem_saida = all(b for b, _ in notas)
                v = min(n for _b, n in notas) + (self.p.peso_sem_saida if sem_saida else 0.0)
            self._ind[(i, t)] = v
        return v

    def fora_do_meio(self, i: int, t: int, h: int) -> float:
        """Distância do bloco de optativa ao meio do curso (0 para disciplinas comuns)."""
        return abs(t - (h - 1) / 2) if self.no_meio[i] else 0.0

    def cedo_demais(self, i: int, t: int, h: int) -> int:
        """Quantos semestres a disciplina de fim de curso está ANTES do seu lugar (0 = no lugar ou comum)."""
        d = self.degrau[i]
        return 0 if d is None else max(0, (h - 1 - d) - t)

    def excesso_pesadas(self, n: int) -> int:
        return 0 if self.max_pesadas is None else max(0, n - self.max_pesadas)

    def penalizar_choque(self, a: int, b: int, t: int, valor: float) -> None:
        """Choque que nenhuma escolha de turma evita: pesa mais na próxima rodada da busca."""
        chave = (a, b, t) if a < b else (b, a, t)
        self.extra[chave] = self.extra.get(chave, 0.0) + valor
        self._linhas.clear()

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
        """
        (custo total, violações duras), recalculado do zero. Duras = 0 significa solução viável.
        A busca usa `_Estado` (incremental); este cálculo completo é a referência e confere o resultado.
        """
        p = self.p
        duras = 0.0
        cargas = [0] * h
        pesadas = [0] * h
        por_sem: list[list[int]] = [[] for _ in range(h)]
        risco = sug = ind = 0.0
        for i, t in enumerate(asg):
            ind += self.individual(i, t)
            pesadas[t] += self.pesada[i]
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
        for t, c in enumerate(cargas):
            cap = self.cap_t[t]
            if cap is not None and c > cap:
                duras += c - cap
        excesso = sum(self.excesso_pesadas(n) for n in pesadas)
        separados = sum(1 for g in self.grupos_pref if len({asg[i] for i in g}) > 1)
        cedo = sum(self.cedo_demais(i, t, h) for i, t in enumerate(asg))
        meio = sum(self.fora_do_meio(i, t, h) for i, t in enumerate(asg))
        equilibrio = sum((c - alvo) ** 2 for c in cargas)
        colisoes = 0.0
        for t, lista in enumerate(por_sem):
            for x in range(len(lista)):
                for y in range(x + 1, len(lista)):
                    colisoes += self.colisao(lista[x], lista[y], t)
        soft = (0.5 * p.peso_equilibrio * equilibrio + 0.6 * p.peso_risco * risco
                + p.peso_sugerido * sug + p.peso_conflito * colisoes
                + p.peso_preferencias * ind + p.peso_pesadas * excesso + p.peso_juntas * separados
                + p.peso_fim * cedo + p.peso_meio * meio)
        return PESO_DURA * duras + soft, duras

    def requisitos_ok(self, i: int, t: int, asg: Sequence[int]) -> bool:
        for alts, folga in self.termos[i]:
            if not any(asg[a] != -1 and asg[a] + folga <= t for a in alts):
                return False
        return True

    def prioridade(self, i: int, ultimos: Mapping[int, float], h: int) -> tuple:
        """
        Ordem do escalonamento por lista (estilo Hu / Coffman-Graham): menor "último semestre
        possível" (folga) primeiro; depois maior ALTURA (mais semestres dependem dele em cadeia) e
        maior PESO POSICIONAL (mais créditos presos atrás dele); por fim créditos, período sugerido e id.
        """
        return (ultimos.get(self.ids[i], h), -self.altura[i], -self.peso[i], -self.cred[i],
                self.sug[i] if self.sug[i] is not None else 99, self.ids[i])

    def guloso(self, h: int, ultimos: Mapping[int, float], encher: bool = False) -> list[int]:
        """
        Escalonamento por lista: respeita oferta, requisitos e teto; ordem por `prioridade`.
        Normalmente para cada semestre na carga média que falta (equilíbrio); com `encher`, enche
        até o teto (melhor ponto de partida quando o prazo está apertado).
        """
        asg = [-1] * self.n
        restante = sum(self.cred)
        ordem = sorted(range(self.n), key=lambda i: self.prioridade(i, ultimos, h))
        for t in range(h):
            alvo_t = math.ceil(restante / (h - t)) if h - t > 0 else restante
            cap_t = self.cap_t[t]
            if encher and cap_t is not None:
                alvo_t = cap_t
            carga = 0
            mudou = True
            while mudou:
                mudou = False
                for i in ordem:
                    if asg[i] != -1 or not self.ofer[i][t] or not self.requisitos_ok(i, t, asg):
                        continue
                    urgente = ultimos.get(self.ids[i], h) <= t     # sem folga: tem que ser agora
                    if not urgente and self.cedo_demais(i, t, h):
                        continue                                    # TCC & cia.: só nos últimos semestres
                    if cap_t is not None and (cap_t == 0 or (carga and carga + self.cred[i] > cap_t)):
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

    # ── recozimento simulado ─────────────────────────────────────────────────
    def recozer(self, inicial: Sequence[int], h: int, alvo: float, iteracoes: int,
                rng: random.Random, limite_tempo: float,
                parar_se_viavel: bool = False) -> tuple[list[int], float, float, int]:
        """
        Uma corrida de recozimento simulado. Devolve (melhor, custo, duras, iterações feitas).

        * avaliação INCREMENTAL: cada movimento atualiza só as parcelas do custo que mudam (`_Estado`);
        * vizinhança que preserva a viabilidade quando a solução já é viável: mover dentro da janela
          [mais cedo pelos requisitos, mais tarde pelos dependentes] num semestre ofertado e com
          espaço; "cadeia" (move e empurra dependentes/requisitos junto); troca entre semestres;
        * temperatura inicial calibrada por uma amostra de pioras; reaquece quando estagna.

        `parar_se_viavel`: na busca do menor nº de semestres só interessa achar UMA solução viável
        (o refino vem depois). Nesse modo o custo vira "nº de violações" (os objetivos macios só
        desempatam) com temperatura própria, para a busca atravessar platôs de violações (consertar
        uma e criar outra tem custo +0, não +1000); para assim que achar.
        """
        est = _Estado(self, inicial, h, alvo, viabilidade=parar_se_viavel)
        melhor, c_melhor, d_melhor = list(est.asg), est.custo(), est.duras()
        mexiveis = any(sum(1 for t in range(h) if self.ofer[i][t]) > 1 for i in range(self.n))
        if iteracoes <= 0 or not mexiveis or (parar_se_viavel and d_melhor == 0):
            return melhor, c_melhor, d_melhor, 0
        if parar_se_viavel:
            t0, tf = 0.8, 0.05            # aceita +1 violação com ~30% de chance no começo, ~0 no fim
        else:
            t0 = _temperatura_inicial(est, rng)
            tf = max(t0 * 1e-3, 1e-3)
        alfa = (tf / t0) ** (1.0 / iteracoes)
        temp = t0
        estagnacao = max(400, iteracoes // 6)
        ultimo_ganho = 0
        c_atual = est.custo()
        feitas = 0
        for k in range(iteracoes):
            feitas = k + 1
            if k % 200 == 0 and relogio.monotonic() > limite_tempo:
                break
            temp *= alfa
            desfazer = est.vizinho(rng)
            if desfazer is None:
                continue
            c_novo = est.custo()
            if c_novo <= c_atual or rng.random() < math.exp((c_atual - c_novo) / temp):
                c_atual = c_novo
                if c_atual < c_melhor - 1e-9:
                    melhor, c_melhor, d_melhor = list(est.asg), c_atual, est.duras()
                    ultimo_ganho = k
                    if parar_se_viavel and d_melhor == 0:
                        break
            else:
                est.desfazer(desfazer)
            if k - ultimo_ganho > estagnacao:            # reaquecimento: volta ao melhor e esquenta
                est = _Estado(self, melhor, h, alvo, viabilidade=parar_se_viavel)
                c_atual = est.custo()
                temp = max(temp, t0 * 0.5)
                ultimo_ganho = k
        # custo de verdade, pelo cálculo completo (sem arredondamento acumulado nem o modo viabilidade)
        c_melhor, d_melhor = self.custo(melhor, h, alvo)
        return melhor, c_melhor, d_melhor, feitas

    def recozer_com_reinicios(self, inicial: Sequence[int], h: int, alvo: float, iteracoes: int,
                              semente: int, limite_tempo: float, reinicios: int = 3,
                              parar_se_viavel: bool = False) -> tuple[list[int], float, float, int]:
        """
        `reinicios` corridas independentes a partir da mesma solução inicial, cada uma com uma semente
        DERIVADA de `semente` (determinístico), dividindo as iterações; fica a melhor. Para no prazo
        (e, com `parar_se_viavel`, na primeira solução viável).
        """
        melhor = list(inicial)
        c_melhor, d_melhor = self.custo(melhor, h, alvo)
        total = 0
        por_corrida = max(1, iteracoes // max(1, reinicios))
        for r in range(max(1, reinicios)):
            if r and (relogio.monotonic() > limite_tempo or (parar_se_viavel and d_melhor == 0)):
                break
            rng = random.Random(semente * 1_000_003 + h * 7_919 + r)
            asg, c, d, feitas = self.recozer(inicial, h, alvo, por_corrida, rng, limite_tempo, parar_se_viavel)
            total += feitas
            if (d, c) < (d_melhor, c_melhor):
                melhor, c_melhor, d_melhor = asg, c, d
        return melhor, c_melhor, d_melhor, total


def _temperatura_inicial(est: "_Estado", rng: random.Random, amostras: int = 60, aceitar: float = 0.5) -> float:
    """
    Temperatura em que uma piora TÍPICA (média de uma amostra de movimentos que pioram só os
    objetivos macios) é aceita com probabilidade `aceitar`: T0 = −média / ln(aceitar).
    """
    pioras = []
    base_c, base_d = est.custo(), est.duras()
    for _ in range(amostras):
        desfazer = est.vizinho(rng)
        if desfazer is None:
            continue
        delta, mudou_dura = est.custo() - base_c, est.duras() != base_d
        est.desfazer(desfazer)
        if delta > 1e-9 and not mudou_dura:
            pioras.append(delta)
    if not pioras:
        return 25.0
    return max(1e-2, -(sum(pioras) / len(pioras)) / math.log(aceitar))


class _Estado:
    """
    Solução corrente + parcelas do custo mantidas por movimento (avaliação incremental, "delta").

    Mover a disciplina i de um semestre para outro só mexe em: oferta de i, carga dos dois
    semestres (equilíbrio e teto), risco e distância ao sugerido de i, colisões de i com os colegas
    dos dois semestres e os requisitos em que i aparece (`_Modelo.afetados`). O resto não muda.
    """

    def __init__(self, m: _Modelo, asg: Sequence[int], h: int, alvo: float, viabilidade: bool = False) -> None:
        self.m, self.h, self.alvo = m, h, alvo
        # modo viabilidade: cada violação vale 1 e os objetivos macios só desempatam
        self.peso_dura, self.escala_macia = (1.0, 1e-4) if viabilidade else (PESO_DURA, 1.0)
        self.asg = list(asg)
        self.cargas = [0] * h
        self.membros: list[set[int]] = [set() for _ in range(h)]    # quem tem turma (colisões)
        self.todos: list[set[int]] = [set() for _ in range(h)]      # todas as disciplinas do semestre
        self.d_oferta = 0
        self.d_req = 0
        self.risco = 0.0
        self.sug = 0.0
        self.col = 0.0
        self.ind = 0.0
        self.pesadas = [0] * h
        for i, t in enumerate(self.asg):
            self.cargas[t] += m.cred[i]
            self.ind += m.individual(i, t)
            self.pesadas[t] += m.pesada[i]
            self.todos[t].add(i)
            if not m.ofer[i][t]:
                self.d_oferta += 1
            self.risco += m.ndesc[i] * t
            if m.sug[i] is not None:
                self.sug += abs(t - m.sug[i])
            if m.tem_turma[i]:
                linha = m.linha_colisao(i, t)
                self.col += sum(linha[x] for x in self.membros[t])
                self.membros[t].add(i)
        for i in range(m.n):
            for k in range(len(m.termos[i])):
                self.d_req += self._viol(i, k)
        self.equil = sum((c - alvo) ** 2 for c in self.cargas)
        self.d_cap = sum(max(0, c - m.cap_t[t]) for t, c in enumerate(self.cargas) if m.cap_t[t] is not None)
        self.excesso = sum(m.excesso_pesadas(n) for n in self.pesadas)
        self.separados = sum(1 for g in m.grupos_pref if len({self.asg[i] for i in g}) > 1)
        self.cedo = sum(m.cedo_demais(i, t, h) for i, t in enumerate(self.asg))
        self.meio = sum(m.fora_do_meio(i, t, h) for i, t in enumerate(self.asg))

    def _viol(self, j: int, k: int) -> int:
        alts, folga = self.m.termos[j][k]
        asg = self.asg
        return max(0, min(asg[a] for a in alts) + folga - asg[j])

    def duras(self) -> float:
        return float(self.d_oferta + self.d_req + self.d_cap)

    def custo(self) -> float:
        p = self.m.p
        soft = (0.5 * p.peso_equilibrio * self.equil + 0.6 * p.peso_risco * self.risco
                + p.peso_sugerido * self.sug + p.peso_conflito * self.col
                + p.peso_preferencias * self.ind + p.peso_pesadas * self.excesso + p.peso_juntas * self.separados
                + p.peso_fim * self.cedo + p.peso_meio * self.meio)
        return self.peso_dura * self.duras() + self.escala_macia * soft

    def mover(self, i: int, novo: int) -> None:
        m, antigo = self.m, self.asg[i]
        if novo == antigo:
            return
        afetados = m.afetados[i]
        antes = sum(self._viol(j, k) for j, k in afetados)
        self.d_oferta += (not m.ofer[i][novo]) - (not m.ofer[i][antigo])
        c, alvo = m.cred[i], self.alvo
        ca, cn = self.cargas[antigo], self.cargas[novo]
        self.equil += ((ca - c - alvo) ** 2 - (ca - alvo) ** 2) + ((cn + c - alvo) ** 2 - (cn - alvo) ** 2)
        cap_a, cap_n = m.cap_t[antigo], m.cap_t[novo]
        if cap_a is not None:
            self.d_cap += max(0, ca - c - cap_a) - max(0, ca - cap_a)
        if cap_n is not None:
            self.d_cap += max(0, cn + c - cap_n) - max(0, cn - cap_n)
        self.cargas[antigo], self.cargas[novo] = ca - c, cn + c
        self.ind += m.individual(i, novo) - m.individual(i, antigo)
        if m.degrau[i] is not None:
            self.cedo += m.cedo_demais(i, novo, self.h) - m.cedo_demais(i, antigo, self.h)
        if m.no_meio[i]:
            self.meio += m.fora_do_meio(i, novo, self.h) - m.fora_do_meio(i, antigo, self.h)
        if m.pesada[i]:
            pa, pn = self.pesadas[antigo], self.pesadas[novo]
            self.excesso += (m.excesso_pesadas(pa - 1) - m.excesso_pesadas(pa)
                             + m.excesso_pesadas(pn + 1) - m.excesso_pesadas(pn))
            self.pesadas[antigo], self.pesadas[novo] = pa - 1, pn + 1
        self.risco += m.ndesc[i] * (novo - antigo)
        s = m.sug[i]
        if s is not None:
            self.sug += abs(novo - s) - abs(antigo - s)
        if m.tem_turma[i]:
            sai = self.membros[antigo]
            sai.discard(i)
            linha = m.linha_colisao(i, antigo)
            self.col -= sum(linha[x] for x in sai)
            entra = self.membros[novo]
            linha = m.linha_colisao(i, novo)
            self.col += sum(linha[x] for x in entra)
            entra.add(i)
        self.todos[antigo].discard(i)
        self.todos[novo].add(i)
        grupos = m.grupos_de[i]
        if grupos:
            antes_sep = sum(1 for k in grupos if len({self.asg[x] for x in m.grupos_pref[k]}) > 1)
        self.asg[i] = novo
        if grupos:
            self.separados += sum(1 for k in grupos if len({self.asg[x] for x in m.grupos_pref[k]}) > 1) - antes_sep
        self.d_req += sum(self._viol(j, k) for j, k in afetados) - antes

    def desfazer(self, movimentos: list[tuple[int, int]]) -> None:
        """Volta cada disciplina ao semestre anterior, na ordem inversa."""
        for i, antigo in reversed(movimentos):
            self.mover(i, antigo)

    def _aplicar(self, movimentos: list[tuple[int, int]], i: int, novo: int) -> None:
        movimentos.append((i, self.asg[i]))
        self.mover(i, novo)

    # ── vizinhança ───────────────────────────────────────────────────────────
    def janela(self, i: int) -> tuple[int, int]:
        """[mais cedo pelos requisitos de i, mais tarde pelos dependentes que só i atende]."""
        m, asg = self.m, self.asg
        cedo = 0
        for alts, folga in m.termos[i]:
            cedo = max(cedo, min(asg[a] for a in alts) + folga)
        tarde = self.h - 1
        for j, k in m.usado_em[i]:
            alts, folga = m.termos[j][k]
            if any(asg[a] + folga <= asg[j] for a in alts if a != i):
                continue                                   # outra alternativa já atende j
            tarde = min(tarde, asg[j] - folga)
        return cedo, tarde

    def _cabe(self, i: int, t: int) -> bool:
        cap = self.m.cap_t[t]
        if cap is None:
            return True
        return cap > 0 and (self.cargas[t] == 0 or self.cargas[t] + self.m.cred[i] <= cap)

    def vizinho(self, rng: random.Random) -> list[tuple[int, int]] | None:
        """Aplica um movimento aleatório e devolve como desfazê-lo (None = nenhum movimento possível)."""
        m = self.m
        viavel = self.d_oferta + self.d_req + self.d_cap == 0
        if not viavel and rng.random() < 0.35:
            return self._reparo(rng)
        r = rng.random()
        i = rng.randrange(m.n)
        mov: list[tuple[int, int]] = []
        if r < 0.55:                                       # mover uma disciplina
            if viavel:
                cedo, tarde = self.janela(i)
                opcoes = [t for t in range(max(0, cedo), min(self.h - 1, tarde) + 1)
                          if t != self.asg[i] and m.ofer[i][t] and self._cabe(i, t)]
            else:
                opcoes = [t for t in range(self.h) if t != self.asg[i] and m.ofer[i][t]]
            if not opcoes:
                return None
            self._aplicar(mov, i, rng.choice(opcoes))
            return mov
        if r < 0.70:                                       # cadeia: move e empurra quem depende
            return self._cadeia(i, rng)
        j = rng.randrange(m.n)                             # trocar duas de semestre
        ti, tj = self.asg[i], self.asg[j]
        if i == j or ti == tj or not m.ofer[i][tj] or not m.ofer[j][ti]:
            return None
        if viavel:
            ci, li = self.janela(i)
            cj, lj = self.janela(j)
            if not (ci <= tj <= li and cj <= ti <= lj):
                return None
        self._aplicar(mov, i, tj)
        self._aplicar(mov, j, ti)
        return mov

    def _em_violacao(self, i: int) -> bool:
        m, t = self.m, self.asg[i]
        if not m.ofer[i][t] or (m.cap_t[t] is not None and self.cargas[t] > m.cap_t[t]):
            return True
        return any(self._viol(i, k) for k in range(len(m.termos[i]))) or \
            any(self._viol(j, k) for j, k in m.usado_em[i])

    def _reparo(self, rng: random.Random) -> list[tuple[int, int]] | None:
        """
        Só com a solução inviável: pega uma disciplina envolvida numa violação (fora da oferta,
        semestre acima do teto ou requisito quebrado) e a leva para um semestre ofertado da sua
        janela que tenha espaço (senão, qualquer ofertado com espaço).
        """
        m = self.m
        if self.d_cap and rng.random() < 0.5:
            cheios = [t for t in range(self.h) if m.cap_t[t] is not None and self.cargas[t] > m.cap_t[t]]
            candidatos = sorted(self.todos[rng.choice(cheios)]) if cheios else []
        else:
            candidatos = [i for i in (rng.randrange(m.n) for _ in range(12)) if self._em_violacao(i)]
        if not candidatos:
            return None
        i = rng.choice(candidatos)
        cedo, tarde = self.janela(i)
        opcoes = [t for t in range(max(0, cedo), min(self.h - 1, tarde) + 1)
                  if t != self.asg[i] and m.ofer[i][t] and self._cabe(i, t)]
        if not opcoes:
            opcoes = [t for t in range(self.h) if t != self.asg[i] and m.ofer[i][t] and self._cabe(i, t)]
        if not opcoes:
            return None
        mov: list[tuple[int, int]] = []
        self._aplicar(mov, i, rng.choice(opcoes))
        return mov

    def _cadeia(self, i: int, rng: random.Random) -> list[tuple[int, int]] | None:
        """
        Move i para mais tarde (empurrando os dependentes que ficariam antes da hora) ou para mais
        cedo (puxando os requisitos). Cada empurrado vai para o semestre ofertado mais próximo que
        satisfaz a exigência. Se algum sair do horizonte, desfaz e devolve None.
        """
        m, h = self.m, self.h
        atual = self.asg[i]
        tarde = rng.random() < 0.5
        faixa = range(atual + 1, h) if tarde else range(0, atual)
        opcoes = [t for t in faixa if m.ofer[i][t]]
        if not opcoes:
            return None
        mov: list[tuple[int, int]] = []
        self._aplicar(mov, i, rng.choice(opcoes))
        fila = [i]
        passos = 0
        while fila:
            passos += 1
            if passos > 4 * m.n:
                self.desfazer(mov)
                return None
            x = fila.pop(0)
            if tarde:      # dependentes de x que agora ficaram cedo demais
                for j, k in m.usado_em[x]:
                    if self._viol(j, k) == 0:
                        continue
                    alts, folga = m.termos[j][k]
                    piso = min(self.asg[a] for a in alts) + folga
                    novo = next((t for t in range(piso, h) if m.ofer[j][t]), None)
                    if novo is None:
                        self.desfazer(mov)
                        return None
                    self._aplicar(mov, j, novo)
                    fila.append(j)
            else:          # requisitos de x que agora ficaram tarde demais
                for k in range(len(m.termos[x])):
                    if self._viol(x, k) == 0:
                        continue
                    alts, folga = m.termos[x][k]
                    a = min(alts, key=lambda y: (self.asg[y], y))     # a alternativa mais próxima
                    teto = self.asg[x] - folga
                    novo = next((t for t in range(teto, -1, -1) if m.ofer[a][t]), None)
                    if novo is None:
                        self.desfazer(mov)
                        return None
                    self._aplicar(mov, a, novo)
                    fila.append(a)
        return mov


# ── optativas: enchimento por nível ───────────────────────────────────────────
def _teto_em(teto, k: int) -> int | None:
    """Teto do semestre k: número fixo, None (sem limite) ou função do índice."""
    return teto(k) if callable(teto) else teto


def distribuir_optativas(cargas: Sequence[int], teto, faltando: int) -> tuple[list[int], int]:
    """
    Reparte `faltando` créditos de optativas entre os semestres, sempre no de MENOR carga que
    ainda tenha espaço. Sem espaço (e com teto conhecido), cria semestres no fim.
    Devolve (créditos de optativa por semestre — pode ter semestres a mais, semestres criados).
    """
    total = list(cargas)
    extra = [0] * len(total)
    criados = 0
    while faltando > 0:
        abertos = [k for k in range(len(total)) if _teto_em(teto, k) is None or total[k] < _teto_em(teto, k)]
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


def encaixar_optativas(cargas: Sequence[int], teto, faltando: int) -> tuple[list[int], int]:
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
        abertos = [k for k in range(len(total)) if _teto_em(teto, k) is None or total[k] < _teto_em(teto, k)]
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
    plano_atual: Sequence[tuple[str | None, Collection[int]]] = (),
) -> ResultadoOtimizacao:
    """
    `plano_atual` = o plano que o aluno já montou [(período, ids)]: entra como ponto de partida da busca,
    então a sugestão não sai PIOR que ele (se ele é viável, a busca já começa dele).
    """
    p = parametros or ParametrosOtimizacao()
    ppa = p.periodos_por_ano
    inicio_relogio = relogio.monotonic()
    prazo = inicio_relogio + p.tempo_max_s

    nos, incluidas = nos_a_cursar(disciplinas, requisitos, concluidas, extras)
    efetivas = periodicidades_efetivas(disciplinas.values())
    calendario = CalendarioDeOferta(periodo_inicial, efetivas, ppa)
    if p.preferencias.periodos_pulados:
        calendario = _CalendarioComTrancamento(calendario, p.preferencias.periodos_pulados)
    quadro = _CalendarioComQuadro(calendario, turmas_por_disciplina)
    if quadro.com_quadro:
        calendario = quadro
    disciplinas_reais, requisitos_reais, turmas_reais = disciplinas, requisitos, turmas_por_disciplina

    # disciplinas que o aluno QUER num período: só "abrem" nele. Fixação impossível é ignorada e explicada.
    from .periodicidade import ofertada_em
    fixas: dict[int, str] = {}
    fixas_ignoradas: dict[int, str] = {}
    for d, periodo in (p.preferencias.fixas or {}).items():
        if d not in disciplinas or d in concluidas:
            continue
        ef = efetivas.get(d)
        if ef is not None and not ofertada_em(ef.valor, periodo, ppa):
            fixas_ignoradas[d] = "nao_abre"
        elif quadro.fora_do_quadro(d, periodo):
            fixas_ignoradas[d] = "sem_turma"
        else:
            fixas[d] = periodo
    base_calendario = calendario

    def _camadas(fx):
        """Calendário em camadas: oferta → trancamento → quadro publicado → fixas (→ grupos "cursar junto")."""
        real = _CalendarioComFixas(base_calendario, fx) if fx else base_calendario
        return real, (_CalendarioComGrupos(real, membros) if membros else real)

    calendario = calendario_real = _CalendarioComFixas(base_calendario, fixas) if fixas else base_calendario

    # optativas que faltam viram blocos dentro da otimização (só quando há obrigatórias a distribuir)
    blocos_opt = _blocos_de_optativa(p.optativas_faltando, disciplinas) if nos else {}
    if blocos_opt:
        disciplinas = {**disciplinas, **blocos_opt}
        nos = tuple(sorted(set(nos) | set(blocos_opt)))

    # "cursar junto" (obrigatório): cada grupo vira um bloco; preferência só custa quando separado
    blocos, grupos_pref = _grupos_aplicaveis(p.preferencias.juntas, nos, disciplinas, requisitos)
    membros: dict[int, tuple[int, ...]] = {}
    if blocos:
        nos, disciplinas, requisitos, turmas_por_disciplina, membros = _contrair(
            nos, disciplinas, requisitos, turmas_por_disciplina, blocos)
        calendario = _CalendarioComGrupos(calendario, membros)

    if not nos:
        return _montar(None, [], disciplinas_reais, turmas_reais, calendario_real, p, (), 0, 0, None, 0, 0, prazo)

    grafo = construir_grafo(nos, requisitos, concluidas)
    cs = ciclos_do_grafo(grafo)
    if cs:
        return ResultadoOtimizacao(False, M_CICLO, ciclos=cs, incluidas_por_requisito=incluidas, semente=p.semente)

    hmax = max(1, p.max_semestres)
    primeiros = primeiros_semestres(grafo, hmax, calendario)
    inalcancaveis = tuple(sorted(n for n, v in primeiros.items() if v == INF))
    # fixada cedo demais para os requisitos: solta a fixação (e diz por quê) em vez de dizer "impossível"
    presas = [d for d in fixas if any(d in membros.get(n, (n,)) for n in inalcancaveis)]
    if presas:
        for d in presas:
            fixas_ignoradas[d] = "requisitos"
            del fixas[d]
        calendario_real, calendario = _camadas(fixas)
        primeiros = primeiros_semestres(grafo, hmax, calendario)
        inalcancaveis = tuple(sorted(n for n, v in primeiros.items() if v == INF))
    if inalcancaveis:
        return ResultadoOtimizacao(False, M_INALCANCAVEL, inalcancaveis=inalcancaveis,
                                   incluidas_por_requisito=incluidas, semente=p.semente)

    from .fim_de_curso import disciplinas_de_fim_de_curso
    fim_real = {d: g for d, g in disciplinas_de_fim_de_curso(disciplinas_reais, requisitos_reais).items() if d in set(
        m for n in nos for m in membros.get(n, (n,)))}
    fim_modelo: dict[int, int] = {}
    for n in nos:                                   # bloco "cursar junto": vale o menor degrau dos membros
        graus = [fim_real[m] for m in membros.get(n, (n,)) if m in fim_real]
        if graus:
            fim_modelo[n] = min(graus)
    rep_de = {m: r for r, b in membros.items() for m in b}
    modelo = _Modelo(nos, grafo, disciplinas, requisitos, turmas_por_disciplina, calendario, p, hmax, fim_modelo,
                     [[rep_de.get(i, i) for i in g] for g in grupos_pref])
    # plano do aluno → índice de semestre de cada nó do modelo (ponto de partida da busca)
    do_plano = _indices_do_plano(plano_atual, periodo_inicial, ppa, rep_de, modelo)
    cadeia = cadeia_critica(grafo, primeiros)
    limite_inferior, limitado_por = _limite_inferior(grafo, primeiros, modelo, calendario, hmax)
    chamadas = [0]
    tempos = {"grafo": relogio.monotonic() - inicio_relogio, "guloso": 0.0, "recozimento": 0.0, "turmas": 0.0}

    def resolver(h: int, iteracoes: int, so_viabilidade: bool = False) -> tuple[list[int], float, float, int]:
        ultimos = ultimos_semestres(grafo, h, calendario)
        alvo = sum(modelo.cred) / h
        t0 = relogio.monotonic()
        # dois pontos de partida (equilibrado e cheio até o teto): fica o de menos violações
        partidas = [modelo.guloso(h, ultimos), modelo.guloso(h, ultimos, True)]
        if do_plano:                                # o plano do aluno, completado pelo guloso no que faltar
            base = list(partidas[0])
            for i, t in do_plano.items():
                if t < h:
                    base[i] = t
            partidas.append(base)
        asg, custo, duras = min(((a, *modelo.custo(a, h, alvo)) for a in partidas), key=lambda x: (x[2], x[1]))
        tempos["guloso"] += relogio.monotonic() - t0
        t0 = relogio.monotonic()
        feitas = 0
        if duras > 0 or iteracoes > 0:
            chamadas[0] += 1     # cada chamada tem sementes próprias, derivadas da semente do pedido
            asg2, c2, d2, feitas = modelo.recozer_com_reinicios(
                asg, h, alvo, iteracoes, p.semente + 7_919 * chamadas[0], prazo, p.reinicios,
                parar_se_viavel=so_viabilidade)
            if (d2, c2) <= (duras, custo):
                asg, custo, duras = asg2, c2, d2
        tempos["recozimento"] += relogio.monotonic() - t0
        return asg, custo, duras, feitas

    # 1) menor h viável, subindo a partir do limite inferior
    h0, achada, iteracoes_total = None, None, 0
    for h in range(limite_inferior, hmax + 1):
        # só precisa provar que h cabe (o refino vem depois): orçamento cheio, para na 1ª viável
        asg, custo, duras, feitas = resolver(h, p.iteracoes, so_viabilidade=True)
        iteracoes_total += feitas
        if duras == 0:
            h0, achada = h, asg
            break
        if relogio.monotonic() > prazo:
            break
    if h0 is None:
        return ResultadoOtimizacao(False, M_SEM_SOLUCAO, limite_inferior=limite_inferior,
                                   limitado_por=limitado_por, incluidas_por_requisito=incluidas,
                                   cadeia_critica=cadeia, iteracoes=iteracoes_total, semente=p.semente)

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
            modelo.penalizar_choque(a, b, t, 2.0)

    t0 = relogio.monotonic()
    res = _montar(modelo, melhor_asg, disciplinas_reais, turmas_reais, calendario_real, p,
                  incluidas, limite_inferior, h_final, limitado_por, h0, iteracoes_total, prazo,
                  cadeia=cadeia, membros=membros, requisitos_reais=requisitos_reais, blocos=blocos)
    res = _replace(res, fim_de_curso=dict(fim_real), fixas_respeitadas=dict(fixas),
                   fixas_ignoradas=dict(fixas_ignoradas), partiu_do_plano=bool(do_plano))
    tempos["turmas"] = relogio.monotonic() - t0
    return _replace(res, tempos_ms={k: int(round(v * 1000)) for k, v in tempos.items()})


def _indices_do_plano(plano_atual, periodo_inicial: str, ppa: int, rep_de, modelo: "_Modelo") -> dict[int, int]:
    """{índice do nó no modelo: semestre} a partir do plano do aluno (semestre sem período segue o anterior)."""
    if not plano_atual:
        return {}
    from .prazo import indice_absoluto
    base = indice_absoluto(periodo_inicial, ppa)
    saida: dict[int, int] = {}
    anterior = None
    for per, ids in plano_atual:
        try:
            t = indice_absoluto(per, ppa) - base if per else (anterior + 1 if anterior is not None else 0)
        except ValueError:
            t = anterior + 1 if anterior is not None else 0
        anterior = t
        if t < 0:
            continue
        for d in ids:
            r = rep_de.get(d, d)
            if r in modelo.idx:
                i = modelo.idx[r]
                saida[i] = max(saida.get(i, t), t)          # bloco "cursar junto": o semestre mais tardio
    return saida


def _limite_inferior(grafo, primeiros, modelo: _Modelo, calendario, hmax: int) -> tuple[int, str]:
    """
    Maior dos limites inferiores de semestres (todos válidos; o maior é o mais útil) e o que limita:

      * grafo + calendário: o último "primeiro semestre possível" + 1;
      * créditos, energético: para cada (a, b), quem não cabe nos `a` primeiros nem nos `b` últimos
        (altura só por exigências obrigatórias) precisa de ceil(créditos / teto) semestres a mais;
      * janelas: com o horizonte H fixo, cada disciplina vai para [mais cedo, mais tarde(H)] e toda
        janela tem de comportar os créditos presos nela; sobe H até caber.
    """
    lb_grafo = int(menor_horizonte(primeiros))
    livres = primeiros_semestres(grafo, hmax, lambda _n, _t: True)
    lb_livre = int(menor_horizonte(livres))
    creditos = {d: modelo.cred[i] for i, d in enumerate(modelo.ids)}   # optativas não adiam o prazo
    # com teto por período, o maior teto vale para os limites "de soma" (continuam válidos) e as
    # janelas usam a capacidade real de cada semestre
    tetos = [c for c in modelo.cap_t if c is not None]
    cap = max(tetos) if tetos and len(tetos) == len(modelo.cap_t) else None
    lb_cred = math.ceil(sum(modelo.cred) / cap) if cap else 0
    lb_energ = limite_energetico(primeiros, alturas(grafo, so_obrigatorias=True), creditos, cap)
    base = max(lb_grafo, lb_cred, lb_energ, 1)
    capacidade = (lambda t: modelo.cap_t[t] if t < len(modelo.cap_t) else cap) if cap else None
    lb_janelas = horizonte_por_janelas(grafo, primeiros, creditos, capacidade, calendario, base, hmax)
    limite = max(base, lb_janelas)
    if limite > lb_grafo:
        return limite, LIM_CREDITOS
    return limite, (LIM_OFERTA if lb_grafo > lb_livre else LIM_REQUISITOS)


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
        for c in alocar_turmas(selecoes, preferencias=modelo.prefs.semana).colisoes:
            saida.append((modelo.idx[c.disciplina_a], modelo.idx[c.disciplina_b], t))
    return saida


def _montar(modelo, asg, disciplinas, turmas, calendario, p, incluidas, limite_inferior, h, limitado_por,
            h0, iteracoes, prazo, cadeia=(), membros=None, requisitos_reais=None,
            blocos=()) -> ResultadoOtimizacao:
    ppa = p.periodos_por_ano
    por_sem: list[list[int]] = [[] for _ in range(h)]
    opt_no_plano = [0] * h                      # créditos dos blocos de optativa em cada semestre
    if modelo is not None:
        for i, t in enumerate(asg):
            d = modelo.ids[i]
            if d <= ID_BLOCO_OPTATIVA + 10**6:
                opt_no_plano[t] += modelo.cred[i]
                continue
            por_sem[t].extend((membros or {}).get(d, (d,)))   # bloco "cursar junto" → seus membros

    semestres: list[SemestreSugerido] = []
    cargas = [sum(disciplinas[d].creditos_no_limite for d in ids) for ids in por_sem]
    prefs = p.preferencias
    teto_opt = lambda k: (prefs.teto(calendario.periodo(k), p.max_creditos))   # optativas: teto de cada semestre
    ultimo_obrig = max((k for k, ids in enumerate(por_sem) if ids), default=-1)
    if any(opt_no_plano):
        # as optativas já fazem parte do plano (blocos otimizados junto com as obrigatórias)
        extra_opt, sobra = list(opt_no_plano), 0
        ultimo = max(k for k in range(h) if por_sem[k] or opt_no_plano[k])
        fim_com_opt = calendario.periodo(ultimo)
    elif ultimo_obrig >= 0:
        # optativas só entram nos semestres que as obrigatórias já usam; o resto vira aviso
        extra_opt, sobra = encaixar_optativas(cargas[:ultimo_obrig + 1], teto_opt, p.optativas_faltando)
        extra_opt += [0] * (len(por_sem) - len(extra_opt))
        teto_novo = p.max_creditos
        n_novos = (math.ceil(sobra / teto_novo) if teto_novo else 1) if sobra else 0
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
        aloc = alocar_turmas(selecoes, preferencias=prefs.semana)
        n_colisoes += len(aloc.colisoes)
        choques = choques_por_disciplina(aloc.colisoes, {d for d, o in origens.items() if o == HORARIO_REAL})
        turma_de = {s.disciplina_id: tu for s in selecoes for tu in s.turmas_ofertadas
                    if tu.id == aloc.escolha.get(s.disciplina_id)}
        bloqueada = lambda d: bool(prefs.semana and d in turma_de and any(
            bate_indisponivel(e, prefs.semana.indisponiveis) for e in turma_de[d].encontros))
        itens = tuple(ItemSugerido(
            d, aloc.escolha.get(d) if origens[d] == HORARIO_REAL else None, origens[d], d in incluidas,
            choques.get(d, ()), bloqueada(d),
        ) for d in sorted(ids))
        escolhidas = list(turma_de.values())
        encontros = [e for tu in escolhidas for e in tu.encontros]
        semana = metricas_semana(encontros, prefs.semana, completo=all(aloc.escolha.get(d) for d in ids)) if ids else None
        semestres.append(SemestreSugerido(t + 1, periodo, itens, sum(disciplinas[d].creditos or 0 for d in ids), extra_opt[t], aloc.colisoes,
                                          semana, tuple(d for d in sorted(ids) if d in prefs.pesadas),
                                          prefs.pulado(periodo)))

    # robustez: atraso se alguém reprovar, usando o plano sugerido executado de verdade
    plano_ids = [set(ids) for ids in por_sem]
    oferta = _OfertaIdx(calendario)
    medio, pior = 0.0, 0
    if modelo is not None and any(plano_ids):
        _base, cen = cenarios_de_reprovacao(
            plano_ids, oferta, requisitos_reais if requisitos_reais is not None else modelo.requisitos,
            {i: d.creditos_no_limite for i, d in disciplinas.items()},
            lambda k: prefs.teto(calendario.periodo(k), modelo.cap), (),
            max_pesadas=prefs.max_pesadas, pesadas=prefs.pesadas, juntas=[set(b) for b in blocos],
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
        cadeia_critica=tuple(cadeia), grupos_aplicados=tuple(tuple(b) for b in blocos),
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


@dataclass(frozen=True)
class AvaliacaoSugestao:
    """O que a sugestão significa para o aluno: prazo e "vou formar quando?" (para comparar planos)."""

    prazo: "AvaliacaoPrazo"
    monte_carlo: "ResultadoMonteCarlo | None"
    dias_livres_media: float | None      # média de dias livres por semestre (só semestres com horário)


def avaliar_sugestao(
    res: ResultadoOtimizacao,
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
    concluidas: Collection[int],
    periodo_inicial: str,
    parametros: ParametrosOtimizacao,
    duracao_semestres: int | None = None,
    fator_prazo: float = 1.5,
    periodo_ingresso: str | None = None,
    taxa=None,
    ja_reprovadas: Collection[int] = (),
    n_monte_carlo: int = 500,
    semente: int = 2027,
) -> AvaliacaoSugestao:
    """Prazo e Monte Carlo do plano SUGERIDO, com as mesmas regras do simulador."""
    from .monte_carlo import simular_formatura
    from .prazo import avaliar_prazo

    p = parametros
    prefs = p.preferencias
    fim = res.periodo_fim_com_optativas or (res.metricas.periodo_fim if res.metricas else None)
    prazo = avaliar_prazo(periodo_ingresso, fim, duracao_semestres, fator_prazo, prefs.periodos_pulados,
                          p.periodos_por_ano)
    plano = [{i.disciplina_id for i in s.itens} for s in res.semestres]
    monte = None
    if res.viavel and any(plano) and n_monte_carlo > 0:
        efetivas = periodicidades_efetivas(disciplinas.values())
        calendario = CalendarioDeOferta(periodo_inicial, efetivas, p.periodos_por_ano)
        if prefs.periodos_pulados:
            calendario = _CalendarioComTrancamento(calendario, prefs.periodos_pulados)
        monte = simular_formatura(
            plano, _OfertaIdx(calendario), requisitos, {i: d.creditos_no_limite for i, d in disciplinas.items()},
            lambda k: prefs.teto(calendario.periodo(k), p.max_creditos), concluidas,
            taxa=taxa, ja_reprovadas=ja_reprovadas, n=n_monte_carlo, semente=semente,
            max_pesadas=prefs.max_pesadas, pesadas=prefs.pesadas,
        )
    livres = [len(s.semana.dias_livres) for s in res.semestres if s.semana and s.semana.completo and s.itens]
    return AvaliacaoSugestao(prazo, monte, round(sum(livres) / len(livres), 1) if livres else None)

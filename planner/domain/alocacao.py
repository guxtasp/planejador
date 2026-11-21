"""
Escolha de turmas SEM colisão dentro de um semestre (busca com poda).

`conflitos.detectar_conflitos` olha pares ("A×B colidem em algumas turmas"). Isso não
enxerga o caso em que cada par tem uma saída, mas as saídas se excluem entre si
(A×B pede T1, B×C pede T2 e C×A pede o contrário…). Aqui o semestre inteiro é
resolvido de uma vez: um problema de satisfação de restrições, onde cada disciplina
é uma variável e suas turmas são o domínio.

Busca em profundidade com ramificação-e-poda (branch & bound): variáveis com menos
turmas primeiro (heurística MRV), custo = pares que ainda colidem, poda quando o custo
parcial já iguala o melhor. `limite_nos` evita explosão; se for atingido, o resultado é o
melhor encontrado e `exata=False`.

Critérios SECUNDÁRIOS (só com `preferencias`, ver `semana`): choque com horário indisponível do
aluno, janelas no dia, nº de dias com aula, turno preferido e dias que quer livres. O custo vira o
par (colisões, penalidade) comparado em ordem: colisão continua dominante, a penalidade só desempata.
A poda usa a parte da penalidade que só cresce (`semana.penalidade_monotona`); janelas entram na folha.
Horário INDISPONÍVEL é regra dura quando há saída: turma que bate num bloco indisponível sai das
candidatas se a disciplina tiver outra turma que não bate (`sem_indisponiveis`). Sem saída, fica
(com penalidade) — não se esconde uma disciplina por falta de alternativa.
Sem preferências a penalidade é sempre 0 e o resultado é idêntico ao de antes.

Disciplina sem turma candidata (oferta desconhecida) não entra: não se julga o que não se sabe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .conflitos import Selecao, Sobreposicao, sobreposicoes_entre_turmas
from .entidades import Turma
from .semana import PreferenciasSemana, penalidade, penalidade_monotona, turma_bate_indisponivel

LIMITE_NOS = 20_000


@dataclass(frozen=True)
class Colisao:
    disciplina_a: int
    disciplina_b: int
    sobreposicao: Sobreposicao


@dataclass(frozen=True)
class Alocacao:
    escolha: Mapping[int, int | None]     # disciplina → turma escolhida (None: sem turma candidata)
    colisoes: tuple[Colisao, ...]         # o que NÃO deu para evitar (vazio = semestre limpo)
    exata: bool                           # False se a busca foi cortada pelo limite de nós
    penalidade: float = 0.0               # custo frente às preferências (0 sem preferências)

    @property
    def sem_colisao(self) -> bool:
        return not self.colisoes


def sem_indisponiveis(selecoes: Sequence[Selecao], p: PreferenciasSemana | None) -> list[Selecao]:
    """Tira das candidatas as turmas em horário indisponível, quando sobra alguma outra."""
    if p is None or not p.indisponiveis:
        return list(selecoes)
    saida = []
    for s in selecoes:
        if s.turma_escolhida_id is None:
            livres = tuple(t for t in s.turmas_ofertadas if not turma_bate_indisponivel(t.encontros, p))
            if livres and len(livres) < len(s.turmas_ofertadas):
                s = Selecao(s.disciplina_id, livres, None)
        saida.append(s)
    return saida


def alocar_turmas(
    selecoes: Sequence[Selecao],
    limite_nos: int = LIMITE_NOS,
    preferencias: PreferenciasSemana | None = None,
) -> Alocacao:
    """
    Melhor combinação de turmas entre as disciplinas do semestre: menos pares colidindo e, entre
    as que empatam, menor penalidade pelas `preferencias` do aluno (se houver).
    """
    selecoes = sem_indisponiveis(selecoes, preferencias)
    julgaveis = [s for s in selecoes if s.candidatas()]
    escolha: dict[int, int | None] = {s.disciplina_id: None for s in selecoes}
    if not julgaveis:
        return Alocacao(escolha, (), True)

    ordem = sorted(julgaveis, key=lambda s: (len(s.candidatas()), s.disciplina_id))
    cache: dict[tuple[int, int], tuple] = {}

    def choque(a: Turma, b: Turma) -> tuple:
        chave = (a.id, b.id) if a.id <= b.id else (b.id, a.id)
        if chave not in cache:
            cache[chave] = sobreposicoes_entre_turmas(a, b)
        return cache[chave]

    infinito = (float("inf"), float("inf"))
    melhor_custo: list[tuple[float, float]] = [infinito]
    melhor: list[list[Turma]] = [[]]
    nos = [0]
    cortado = [False]
    prefs = preferencias

    def encontros_de(turmas: Sequence[Turma]) -> list:
        return [e for t in turmas for e in t.encontros]

    def busca(i: int, atual: list[Turma], custo: int, pen_lb: float) -> None:
        if (custo, pen_lb) >= melhor_custo[0] or cortado[0]:
            return
        if i == len(ordem):
            total = (custo, penalidade(encontros_de(atual), prefs)) if prefs else (custo, 0.0)
            if total < melhor_custo[0]:
                melhor_custo[0], melhor[0] = total, list(atual)
            return
        nos[0] += 1
        if nos[0] > limite_nos:
            cortado[0] = True
            return
        candidatas = ordem[i].candidatas()
        base = encontros_de(atual) if prefs else []
        # primeiro as turmas que menos colidem com as já escolhidas (e, com preferências, as que menos pesam)
        pontuadas = sorted(
            ((sum(1 for t in atual if choque(c, t)),
              penalidade_monotona(base + list(c.encontros), prefs) if prefs else 0.0, k, c)
             for k, c in enumerate(candidatas)),
            key=lambda x: (x[0], x[1], x[2]),
        )
        for extra, pen, _, c in pontuadas:
            atual.append(c)
            busca(i + 1, atual, custo + extra, pen)
            atual.pop()
            if melhor_custo[0] == (0, 0.0):
                return

    busca(0, [], 0, 0.0)
    if not melhor[0]:   # cortou antes de completar qualquer solução: pega a 1ª turma de cada
        melhor[0] = [s.candidatas()[0] for s in ordem]

    for s, t in zip(ordem, melhor[0]):
        escolha[s.disciplina_id] = t.id
    colisoes = []
    for i in range(len(ordem)):
        for j in range(i + 1, len(ordem)):
            sob = choque(melhor[0][i], melhor[0][j])
            if sob:
                a, b = sorted((ordem[i].disciplina_id, ordem[j].disciplina_id))
                colisoes.append(Colisao(a, b, sob[0]))
    colisoes.sort(key=lambda c: (c.disciplina_a, c.disciplina_b))
    pen = penalidade(encontros_de(melhor[0]), prefs) if prefs else 0.0
    return Alocacao(escolha, tuple(colisoes), not cortado[0], pen)


@dataclass(frozen=True)
class ChoqueItem:
    """Um choque visto do lado de UMA disciplina: com quem, quando e se é firme ou projetado."""

    com: int                  # a outra disciplina
    dia: str
    inicio: object            # datetime.time do trecho em comum
    fim: object
    firme: bool               # os dois horários são reais/próprios (False = algum é projeção)


def choques_por_disciplina(colisoes: Sequence[Colisao], firmes: set[int] | frozenset[int]) -> dict[int, tuple[ChoqueItem, ...]]:
    """
    Cada colisão vira um choque nas DUAS disciplinas (para a tela marcar o cartão de cada uma sem
    recalcular). O horário é o trecho em comum; `firmes` = disciplinas com horário real ou próprio.
    """
    saida: dict[int, list[ChoqueItem]] = {}
    for c in colisoes:
        s = c.sobreposicao
        inicio, fim = max(s.a.inicio, s.b.inicio), min(s.a.fim, s.b.fim)
        firme = c.disciplina_a in firmes and c.disciplina_b in firmes
        saida.setdefault(c.disciplina_a, []).append(ChoqueItem(c.disciplina_b, s.dia, inicio, fim, firme))
        saida.setdefault(c.disciplina_b, []).append(ChoqueItem(c.disciplina_a, s.dia, inicio, fim, firme))
    return {d: tuple(v) for d, v in saida.items()}

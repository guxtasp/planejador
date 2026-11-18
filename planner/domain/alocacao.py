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

Disciplina sem turma candidata (oferta desconhecida) não entra: não se julga o que não se sabe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .conflitos import Selecao, Sobreposicao, sobreposicoes_entre_turmas
from .entidades import Turma

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

    @property
    def sem_colisao(self) -> bool:
        return not self.colisoes


def alocar_turmas(selecoes: Sequence[Selecao], limite_nos: int = LIMITE_NOS) -> Alocacao:
    """Melhor combinação de turmas (menos pares colidindo) entre as disciplinas do semestre."""
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

    melhor_custo = [float("inf")]
    melhor: list[list[Turma]] = [[]]
    nos = [0]
    cortado = [False]

    def busca(i: int, atual: list[Turma], custo: int) -> None:
        if custo >= melhor_custo[0] or cortado[0]:
            return
        if i == len(ordem):
            melhor_custo[0], melhor[0] = custo, list(atual)
            return
        nos[0] += 1
        if nos[0] > limite_nos:
            cortado[0] = True
            return
        candidatas = ordem[i].candidatas()
        # primeiro as turmas que menos colidem com as já escolhidas
        pontuadas = sorted(
            ((sum(1 for t in atual if choque(c, t)), k, c) for k, c in enumerate(candidatas)),
            key=lambda x: (x[0], x[1]),
        )
        for extra, _, c in pontuadas:
            atual.append(c)
            busca(i + 1, atual, custo + extra)
            atual.pop()
            if melhor_custo[0] == 0:
                return

    busca(0, [], 0)
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
    return Alocacao(escolha, tuple(colisoes), not cortado[0])

"""
"Vou formar quando?" — simulação de Monte Carlo do plano com reprovações aleatórias.

Cada execução vive o plano semestre a semestre (`replanejamento.replanejar`) e, a cada tentativa,
sorteia se o aluno passa. Pode reprovar mais de uma vez na mesma disciplina. N execuções com
semente fixa: mesmo pedido, mesma resposta.

Probabilidade de aprovação (nada inventado sobre a disciplina; só o histórico do PRÓPRIO aluno):
  * taxa = aprovações / tentativas encerradas do aluno, suavizada para a taxa padrão (85%) com
    `PSEUDO_TENTATIVAS` tentativas fictícias — com 1 ou 2 tentativas, 100% ou 0% seria exagero;
  * sem histórico: 85% (padrão declarado na tela);
  * disciplina que o aluno já reprovou (antes ou durante a simulação): × `penalidade` (uma vez só,
    sem espiral: reprovar 3 vezes não derruba a chance a quase zero).

Resultado: distribuição do semestre de formatura, P50/P80/P90, chance de formar até o fim do plano
e a SENSIBILIDADE (quais disciplinas mais contribuem para o atraso). Função pura, só stdlib.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Collection, Mapping, Sequence

from .entidades import Requisito
from .replanejamento import Limite, replanejar

TAXA_PADRAO = 0.85
PSEUDO_TENTATIVAS = 4
PENALIDADE_REPROVADA = 0.8
N_PADRAO = 500
SEMENTE_PADRAO = 2027
EXTRA_MC = 12           # semestres além do plano em que ainda se tenta concluir
PISO_PROBABILIDADE = 0.05

Oferta = Callable[[int, int], bool]


@dataclass(frozen=True)
class Taxa:
    valor: float                  # probabilidade de aprovação usada
    origem: str                   # "historico" | "padrao"
    aprovacoes: int = 0
    reprovacoes: int = 0


def taxa_de_aprovacao(aprovacoes: int, reprovacoes: int) -> Taxa:
    n = aprovacoes + reprovacoes
    if n == 0:
        return Taxa(TAXA_PADRAO, "padrao")
    valor = (aprovacoes + TAXA_PADRAO * PSEUDO_TENTATIVAS) / (n + PSEUDO_TENTATIVAS)
    return Taxa(round(valor, 4), "historico", aprovacoes, reprovacoes)


@dataclass(frozen=True)
class Sensibilidade:
    disciplina_id: int
    chance_reprovar: float        # fração das execuções em que reprovou ao menos uma vez
    atraso_se_reprovar: float     # atraso médio (semestres) nas execuções em que reprovou (inclui outras reprovações)
    contribuicao: float           # atraso esperado atribuível: chance × atraso_a_mais
    atraso_a_mais: float = 0.0    # quanto a mais atrasa reprovar NELA (com − sem): o efeito dela, não das outras


@dataclass(frozen=True)
class ResultadoMonteCarlo:
    n: int
    semente: int
    taxa: Taxa
    fim_base: int                              # índice do último semestre sem reprovação
    distribuicao: tuple[tuple[int, int], ...]  # (índice do semestre de formatura, nº de execuções)
    nao_formou: int                            # execuções que não fecham no horizonte
    p50: int | None
    p80: int | None
    p90: int | None
    chance_no_prazo_do_plano: float            # fração com formatura ≤ fim_base
    sensibilidade: tuple[Sensibilidade, ...]   # as que mais atrasam, em ordem


def _quantil(fins_ordenados: Sequence[float], q: float) -> int | None:
    if not fins_ordenados:
        return None
    k = min(len(fins_ordenados) - 1, max(0, math.ceil(q * len(fins_ordenados)) - 1))   # posto mais próximo
    v = fins_ordenados[k]
    return None if v == float("inf") else int(v)


def simular_formatura(
    plano: Sequence[Collection[int]],
    oferta: Oferta,
    requisitos: Mapping[int, Sequence[Requisito]],
    creditos: Mapping[int, int | None],
    limite_creditos: Limite,
    concluidas: Collection[int] = (),
    taxa: Taxa | None = None,
    ja_reprovadas: Collection[int] = (),
    penalidade: float = PENALIDADE_REPROVADA,
    n: int = N_PADRAO,
    semente: int = SEMENTE_PADRAO,
    max_pesadas: int | None = None,
    pesadas: Collection[int] = (),
    top: int = 5,
    juntas: Sequence[Collection[int]] = (),
) -> ResultadoMonteCarlo:
    taxa = taxa or Taxa(TAXA_PADRAO, "padrao")
    rng = random.Random(semente)
    grupos: dict = {}
    kw = dict(max_pesadas=max_pesadas, pesadas=pesadas, grupos=grupos, juntas=juntas)
    base = replanejar(plano, oferta, requisitos, creditos, limite_creditos, concluidas, extra=EXTRA_MC, **kw)
    reprov_hist = {d: 1 for d in ja_reprovadas}
    ids = sorted({i for s in plano for i in s})

    fins: list[float] = []
    reprovou_em_execucao: list[set[int]] = []
    for _ in range(n):
        falhas: dict[int, int] = dict(reprov_hist)
        nesta: set[int] = set()

        def reprova(d: int, _t: int) -> bool:
            p = max(PISO_PROBABILIDADE, taxa.valor * (penalidade if falhas.get(d) else 1.0))
            if rng.random() < p:
                return False
            falhas[d] = falhas.get(d, 0) + 1
            nesta.add(d)
            return True

        r = replanejar(plano, oferta, requisitos, creditos, limite_creditos, concluidas,
                       extra=EXTRA_MC, reprova=reprova, **kw)
        fins.append(float("inf") if r.nao_alocadas else r.fim)
        reprovou_em_execucao.append(nesta)

    finitos = [f for f in fins if f != float("inf")]
    contagem: dict[int, int] = {}
    for f in finitos:
        contagem[int(f)] = contagem.get(int(f), 0) + 1
    ordenados = sorted(fins)
    horizonte = len(plano) + EXTRA_MC          # quem não fecha conta como "depois do horizonte"
    atrasos = [(f if f != float("inf") else horizonte) - base.fim for f in fins]

    sens = []
    for d in ids:
        com = [a for a, rs in zip(atrasos, reprovou_em_execucao) if d in rs]
        if not com:
            continue
        sem = [a for a, rs in zip(atrasos, reprovou_em_execucao) if d not in rs]
        media_com = sum(com) / len(com)
        media_sem = sum(sem) / len(sem) if sem else 0.0
        chance = len(com) / n
        a_mais = max(0.0, media_com - media_sem)
        contrib = chance * a_mais
        sens.append(Sensibilidade(d, round(chance, 3), round(media_com, 2), round(contrib, 3), round(a_mais, 2)))
    sens.sort(key=lambda s: (-s.contribuicao, -s.atraso_se_reprovar, s.disciplina_id))

    return ResultadoMonteCarlo(
        n=n, semente=semente, taxa=taxa, fim_base=base.fim,
        distribuicao=tuple(sorted(contagem.items())),
        nao_formou=len(fins) - len(finitos),
        p50=_quantil(ordenados, 0.5), p80=_quantil(ordenados, 0.8), p90=_quantil(ordenados, 0.9),
        chance_no_prazo_do_plano=round(sum(1 for f in fins if f <= base.fim) / n, 3) if n else 0.0,
        sensibilidade=tuple(s for s in sens if s.contribuicao > 0)[:top],
    )

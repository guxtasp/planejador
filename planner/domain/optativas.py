"""
"Que optativa cabe neste semestre?" — lista para o aluno ESCOLHER (nunca se adiciona sozinho).

Para o semestre `alvo` do plano, entram as optativas/eletivas do catálogo que:
  * não foram feitas nem estão no plano;
  * abrem no período (oferta cadastrada; estimada entra marcada; desconhecida entra marcada);
  * têm os requisitos cumpridos pelo histórico + semestres ANTERIORES do plano (correquisito: o mesmo);
  * cabem na disponibilidade: alguma turma (real ou projetada) fora dos horários indisponíveis.
    Sem horário conhecido entra, marcada como "disponibilidade não verificada".

Ordem por encaixe: cabe na disponibilidade com horário conhecido > sem choque com o semestre >
oferta cadastrada > cabe no teto de créditos > mais perto do período sugerido. Função pura, só stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Mapping, Sequence

from .conflitos import sobreposicoes_entre_turmas
from .entidades import TIPO_OBRIGATORIA, Disciplina, Requisito, Turma
from .periodicidade import ORIGEM_CADASTRADA, ORIGEM_DESCONHECIDA, ofertada_em, periodicidade_efetiva, turmas_para_periodo
from .requisitos import agrupar_requisitos
from .semana import PreferenciasSemana, turma_bate_indisponivel

DISP_CABE = "cabe"
DISP_SEM_HORARIO = "sem_horario"


@dataclass(frozen=True)
class OptativaQueCabe:
    disciplina_id: int
    origem_oferta: str            # cadastrada | estimada | desconhecida
    disponibilidade: str          # cabe | sem_horario
    turma_id: int | None          # uma turma que cabe (só se o quadro do período é real)
    horario_projetado: bool
    sem_choque: bool              # alguma turma que cabe não bate com as turmas do semestre
    cabe_no_teto: bool | None     # None = sem teto conhecido
    nota: float                   # encaixe (maior = melhor), só para ordenar


def optativas_que_cabem(
    semestres: Sequence[tuple[str, Collection[int]]],
    alvo: int,
    disciplinas: Mapping[int, Disciplina],
    requisitos: Mapping[int, Sequence[Requisito]],
    turmas: Mapping[int, Sequence[Turma]],
    concluidas: Collection[int],
    preferencias: PreferenciasSemana | None = None,
    teto: int | None = None,
    periodos_por_ano: int = 2,
    limite: int = 30,
) -> tuple[OptativaQueCabe, ...]:
    """`semestres` = [(período "AAAA/N", ids)] do plano; `alvo` = índice do semestre (0 = primeiro)."""
    periodo, no_semestre = semestres[alvo][0], set(semestres[alvo][1])
    antes = set(concluidas).union(*[set(ids) for _p, ids in semestres[:alvo]]) if alvo else set(concluidas)
    no_plano = set().union(*[set(ids) for _p, ids in semestres]) if semestres else set()
    carga = sum(disciplinas[i].creditos_no_limite for i in no_semestre if i in disciplinas)
    turmas_do_semestre = [t for i in no_semestre for t in turmas_para_periodo(turmas.get(i, ()), periodo, periodos_por_ano)[0]]
    base_sug = [d.periodo_sugerido for d in disciplinas.values() if d.periodo_sugerido]

    saida = []
    for d in disciplinas.values():
        if d.tipo == TIPO_OBRIGATORIA or d.id in concluidas or d.id in no_plano:
            continue
        ef = periodicidade_efetiva(d)
        if ef.origem != ORIGEM_DESCONHECIDA and not ofertada_em(ef.valor, periodo, periodos_por_ano):
            continue
        ok = True
        for tipo, alternativas in agrupar_requisitos(requisitos.get(d.id, ())):
            base = antes | (no_semestre if tipo == "co" else set())
            if not base.intersection(alternativas):
                ok = False
                break
        if not ok:
            continue
        candidatas, origem_h = turmas_para_periodo(turmas.get(d.id, ()), periodo, periodos_por_ano)
        if candidatas:
            livres = [t for t in candidatas if not turma_bate_indisponivel(t.encontros, preferencias)]
            if not livres:
                continue                                     # todas as turmas caem no horário indisponível
            sem_choque = [t for t in livres if not any(sobreposicoes_entre_turmas(t, o) for o in turmas_do_semestre)]
            escolhida = (sem_choque or livres)[0]
            disp, turma_id, choque_ok = DISP_CABE, (escolhida.id if origem_h == "real" else None), bool(sem_choque)
        else:
            disp, turma_id, choque_ok = DISP_SEM_HORARIO, None, True
        cabe = None if teto is None else carga + d.creditos_no_limite <= teto
        distancia = 0.0
        if d.periodo_sugerido and base_sug:
            distancia = abs(d.periodo_sugerido - (min(base_sug) + alvo)) / 10
        nota = (3 * (disp == DISP_CABE) + 2 * choque_ok + 1 * (ef.origem == ORIGEM_CADASTRADA)
                + 1 * (cabe is not False) - distancia)
        saida.append(OptativaQueCabe(d.id, ef.origem, disp, turma_id, origem_h == "projetado", choque_ok, cabe, round(nota, 2)))
    saida.sort(key=lambda o: (-o.nota, disciplinas[o.disciplina_id].codigo))
    return tuple(saida[:limite])

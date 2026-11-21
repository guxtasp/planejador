"""
Análise de um plano de matrícula (Etapa 4B): junta carga, requisitos e
conflitos por turma, semestre a semestre.

Função pura: recebe o plano e o catálogo já convertidos em entidades. O serviço
é quem carrega do banco e traduz o resultado para JSON.

Entradas que não batem com o catálogo (disciplina inexistente, turma de outra
disciplina ou de outro período, disciplina repetida no semestre) NÃO derrubam
a análise: são separadas em `invalidos`. Isso importa porque, sem login (até a
5B), o plano mora no navegador e pode ficar velho se o curso for reimportado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .alocacao import ChoqueItem, alocar_turmas, choques_por_disciplina
from .carga import AvaliacaoCarga, avaliar_carga
from .semana import PreferenciasSemana, turma_bate_indisponivel
from .conflitos import Conflito, Selecao, detectar_conflitos
from .entidades import Disciplina, Encontro, Requisito, Turma
from .requisitos import ProblemaPlano, verificar_plano

DISCIPLINA_DESCONHECIDA = "disciplina_desconhecida"
DISCIPLINA_REPETIDA = "disciplina_repetida"
TURMA_INVALIDA = "turma_invalida"
SEMESTRE_SEM_PERIODO = "semestre_sem_periodo"


@dataclass(frozen=True)
class ItemPlano:
    disciplina_id: int
    turma_id: int | None = None
    # Horários que o ALUNO definiu (sem depender de quadro importado). Se houver,
    # valem no lugar de `turma_id`: viram uma turma própria já escolhida.
    encontros_livres: tuple[Encontro, ...] = ()
    # A turma foi escolhida pelo Rumo: não prende a alocação (a melhor combinação pode trocá-la).
    turma_auto: bool = False


@dataclass(frozen=True)
class SemestrePlano:
    itens: tuple[ItemPlano, ...] = ()
    periodo_letivo: str | None = None   # "AAAA/N"; sem ele a oferta é desconhecida


@dataclass(frozen=True)
class MarcasItem:
    """
    O que o cartão da disciplina mostra no Planejamento/Calendário — mesma regra do simulador:
    choques pela alocação exata do semestre (só os que nenhuma turma evita), disponibilidade e
    "sem horário" (choque/disponibilidade não verificados).
    """

    choques: tuple[ChoqueItem, ...] = ()
    bate_indisponivel: bool = False   # a turma escolhida (ou a única possível) cai num horário indisponível
    nao_cabe: bool = False            # NENHUMA turma do período cabe na disponibilidade
    turma_que_cabe: int | None = None # a escolhida bate na disponibilidade e esta outra cabe
    turma_sugerida: int | None = None # a turma da melhor combinação do semestre (só com quadro real)
    turma_projetada: int | None = None # período sem quadro: a turma (de outro período) usada como estimativa
    sem_horario: bool = False         # sem turma/horário conhecido: nada pôde ser checado
    firme: bool = True                # horário do quadro real/próprio (False = projetado)


@dataclass(frozen=True)
class ItemInvalido:
    disciplina_id: int
    motivo: str
    turma_id: int | None = None


@dataclass(frozen=True)
class AnaliseSemestre:
    posicao: int                                   # a partir de 1
    carga: AvaliacaoCarga
    conflitos: tuple[Conflito, ...]
    pendencias: tuple[ProblemaPlano, ...]
    sem_turma_escolhida: tuple[int, ...]           # há oferta, falta escolher
    invalidos: tuple[ItemInvalido, ...]
    marcas: Mapping[int, MarcasItem] = None        # disciplina → marcas do cartão


def _ofertadas(
    periodo: str | None, turmas: Sequence[Turma]
) -> tuple[Turma, ...]:
    """Turmas do período do semestre. Sem período no semestre, oferta desconhecida."""
    if periodo is None:
        return ()
    return tuple(t for t in turmas if t.periodo_letivo == periodo)


def _normalizar_semestre(
    semestre: SemestrePlano,
    disciplinas: Mapping[int, Disciplina],
    turmas_por_disciplina: Mapping[int, Sequence[Turma]],
) -> tuple[list[Selecao], list[ItemInvalido]]:
    """Separa itens válidos (já como `Selecao`) dos inválidos."""
    selecoes: list[Selecao] = []
    invalidos: list[ItemInvalido] = []
    vistos: set[int] = set()

    for item in semestre.itens:
        if item.disciplina_id not in disciplinas:
            invalidos.append(ItemInvalido(item.disciplina_id, DISCIPLINA_DESCONHECIDA))
            continue
        if item.disciplina_id in vistos:
            invalidos.append(ItemInvalido(item.disciplina_id, DISCIPLINA_REPETIDA))
            continue
        vistos.add(item.disciplina_id)

        if item.encontros_livres:
            propria = Turma(
                id=-item.disciplina_id,   # id negativo: nunca colide com turma do banco
                disciplina_id=item.disciplina_id,
                encontros=item.encontros_livres,
                periodo_letivo=semestre.periodo_letivo,
                codigo_turma="própria",
            )
            selecoes.append(Selecao(item.disciplina_id, (propria,), propria.id))
            continue

        ofertadas = _ofertadas(
            semestre.periodo_letivo, turmas_por_disciplina.get(item.disciplina_id, ())
        )
        escolhida = item.turma_id
        if escolhida is not None and escolhida not in {t.id for t in ofertadas}:
            motivo = SEMESTRE_SEM_PERIODO if semestre.periodo_letivo is None else TURMA_INVALIDA
            invalidos.append(ItemInvalido(item.disciplina_id, motivo, escolhida))
            escolhida = None   # a disciplina fica no plano, só sem turma
        if item.turma_auto:
            escolhida = None   # escolha do Rumo: a alocação do semestre decide de novo
        selecoes.append(Selecao(item.disciplina_id, ofertadas, escolhida))
    return selecoes, invalidos


def analisar_plano(
    semestres: Sequence[SemestrePlano],
    disciplinas: Mapping[int, Disciplina],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    turmas_por_disciplina: Mapping[int, Sequence[Turma]],
    limite_creditos: int | None,
    aprovadas: Sequence[int] = (),
    cursando: Sequence[int] = (),
    preferencias_semana: PreferenciasSemana | None = None,
) -> tuple[AnaliseSemestre, ...]:
    """Uma `AnaliseSemestre` por semestre do plano, na mesma ordem."""
    normalizados = [
        _normalizar_semestre(s, disciplinas, turmas_por_disciplina) for s in semestres
    ]
    pendencias = verificar_plano(
        [{sel.disciplina_id for sel in selecoes} for selecoes, _ in normalizados],
        requisitos_por_disciplina,
        aprovadas,
        cursando,
    )

    resultado = []
    for posicao, (selecoes, invalidos) in enumerate(normalizados, start=1):
        resultado.append(
            AnaliseSemestre(
                posicao=posicao,
                carga=avaliar_carga(
                    (disciplinas[s.disciplina_id] for s in selecoes), limite_creditos
                ),
                conflitos=detectar_conflitos(selecoes),
                pendencias=tuple(p for p in pendencias if p.posicao_semestre == posicao),
                sem_turma_escolhida=tuple(
                    s.disciplina_id
                    for s in selecoes
                    if s.turmas_ofertadas and s.turma_escolhida_id is None
                ),
                invalidos=tuple(invalidos),
                marcas=marcas_do_semestre(selecoes, preferencias_semana, turmas_por_disciplina,
                                          semestres[posicao - 1].periodo_letivo),
            )
        )
    return tuple(resultado)


def marcas_do_semestre(
    selecoes: Sequence[Selecao],
    semana: PreferenciasSemana | None,
    turmas_por_disciplina: Mapping[int, Sequence[Turma]] | None = None,
    periodo: str | None = None,
) -> dict[int, MarcasItem]:
    """
    Marcas de cada disciplina do semestre (ver `MarcasItem`). Mesma regra do simulador: período sem
    quadro publicado usa a PROJEÇÃO do último período de mesma paridade (choque vira "possível").
    """
    from .periodicidade import HORARIO_REAL, turmas_para_periodo
    firmes = {s.disciplina_id for s in selecoes if s.turmas_ofertadas}
    if periodo and turmas_por_disciplina:
        projetadas = []
        for s in selecoes:
            if s.turmas_ofertadas:
                projetadas.append(s)
                continue
            cand, origem = turmas_para_periodo(turmas_por_disciplina.get(s.disciplina_id, ()), periodo)
            projetadas.append(Selecao(s.disciplina_id, cand if origem != HORARIO_REAL else (), None))
        selecoes = projetadas
    aloc = alocar_turmas(selecoes, preferencias=semana)
    choques = choques_por_disciplina(aloc.colisoes, firmes)   # quadro real (ou horário próprio) = firme
    saida: dict[int, MarcasItem] = {}
    for s in selecoes:
        turmas = s.turmas_ofertadas
        if not turmas:
            saida[s.disciplina_id] = MarcasItem(sem_horario=True)
            continue
        escolhida = next((t for t in turmas if t.id == aloc.escolha.get(s.disciplina_id)), None)
        bate = escolhida is not None and turma_bate_indisponivel(escolhida.encontros, semana)
        livres = [t for t in turmas if not turma_bate_indisponivel(t.encontros, semana)]
        tem_bloco = bool(semana and semana.indisponiveis)
        saida[s.disciplina_id] = MarcasItem(
            choques=choques.get(s.disciplina_id, ()), bate_indisponivel=bate, firme=s.disciplina_id in firmes,
            nao_cabe=tem_bloco and not livres,
            turma_que_cabe=livres[0].id if bate and livres and s.disciplina_id in firmes else None,
            turma_sugerida=aloc.escolha.get(s.disciplina_id) if s.disciplina_id in firmes else None,
            turma_projetada=aloc.escolha.get(s.disciplina_id) if s.disciplina_id not in firmes else None,
        )
    return saida

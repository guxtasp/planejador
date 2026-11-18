"""
Painel do aluno (Etapa 5B-2): o que o histórico diz sobre cada disciplina,
quanto do curso já foi feito e quando termina.

Função pura que reúne as regras já prontas (histórico, requisitos, progresso,
previsão). Nada aqui lê o banco; o serviço converte modelos em entidades.

Regra de ouro do projeto: desconhecido é `None`, nunca um número inventado.
  * sem créditos exigidos conhecidos  → sem percentual e sem previsão;
  * sem período letivo no histórico   → sem "próximo período" e sem previsão;
  * sem média do aluno                → usa a média do PRÓPRIO curso (créditos
    exigidos ÷ duração em semestres), se o curso informar os dois; senão,
    sem previsão.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from . import historico as hist
from .entidades import STATUS_APROVADO, Disciplina, Requisito, Tentativa
from .previsao import (
    media_creditos_por_periodo,
    normalizar_periodo,
    semestres_restantes,
    somar_periodos,
)
from .progresso import Progresso, calcular_progresso
from .requisitos import Pendencia, classificar_disciplinas

CONCLUIDA = "concluida"
CURSANDO = "cursando"
ELEGIVEL = "elegivel"
BLOQUEADA = "bloqueada"

MEDIA_DO_ALUNO = "aluno"
MEDIA_DO_CURSO = "curso"


@dataclass(frozen=True)
class StatusDisciplina:
    disciplina_id: int
    situacao: str                              # CONCLUIDA | CURSANDO | ELEGIVEL | BLOQUEADA
    reprovada_antes: bool                      # já reprovou ao menos uma vez (e ainda não passou)
    pendencias: tuple[Pendencia, ...] = ()     # só em BLOQUEADA


@dataclass(frozen=True)
class Painel:
    status: tuple[StatusDisciplina, ...]
    progresso: Progresso
    disciplinas_concluidas: int
    total_disciplinas: int
    media_creditos_periodo: float | None
    origem_media: str | None                   # MEDIA_DO_ALUNO | MEDIA_DO_CURSO | None
    primeiro_periodo_livre: str | None
    semestres_restantes: int | None
    previsao_formatura: str | None             # None = concluído OU sem base para prever


def _periodos_validos(tentativas: Iterable[Tentativa], periodos_por_ano: int) -> list[str]:
    validos = (normalizar_periodo(t.periodo_letivo, periodos_por_ano) for t in tentativas)
    return [p for p in validos if p]


def creditos_aprovados_por_periodo(
    tentativas: Sequence[Tentativa],
    disciplinas: Mapping[int, Disciplina],
    periodos_por_ano: int = 2,
) -> dict[str, int]:
    """
    Créditos concluídos em cada período letivo. Cada disciplina vale no período
    da sua PRIMEIRA aprovação (re-aprovações não contam duas vezes); créditos
    desconhecidos valem 0; aprovação sem período válido fica de fora.
    """
    primeira: dict[int, str] = {}
    for t in tentativas:
        periodo = normalizar_periodo(t.periodo_letivo, periodos_por_ano)
        if t.status != STATUS_APROVADO or not periodo or t.disciplina_id not in disciplinas:
            continue
        if t.disciplina_id not in primeira or periodo < primeira[t.disciplina_id]:
            primeira[t.disciplina_id] = periodo
    por_periodo: dict[str, int] = {}
    for disciplina_id, periodo in primeira.items():
        por_periodo[periodo] = por_periodo.get(periodo, 0) + (disciplinas[disciplina_id].creditos or 0)
    return por_periodo


def media_do_curso(
    creditos_exigidos: int | None, duracao_semestres: int | None
) -> float | None:
    """Créditos por período que o PRÓPRIO curso sugere; `None` se faltar algum dado."""
    if not creditos_exigidos or not duracao_semestres or duracao_semestres <= 0:
        return None
    return creditos_exigidos / duracao_semestres


def montar_painel(
    disciplinas: Sequence[Disciplina],
    requisitos_por_disciplina: Mapping[int, Sequence[Requisito]],
    tentativas: Sequence[Tentativa],
    creditos_obrigatorios: int | None = None,
    creditos_optativos_exigidos: int | None = None,
    duracao_semestres: int | None = None,
    periodos_por_ano: int = 2,
) -> Painel:
    """Situação de cada disciplina + progresso + previsão de formatura."""
    aprovadas = hist.aprovadas(tentativas)
    cursando = hist.cursando(tentativas)
    situacoes = hist.situacoes(tentativas)

    classe = classificar_disciplinas(disciplinas, requisitos_por_disciplina, aprovadas, cursando)
    status: dict[int, StatusDisciplina] = {}
    for d in classe.concluidas:
        status[d.id] = StatusDisciplina(d.id, CONCLUIDA, False)
    for d in classe.em_andamento:
        status[d.id] = StatusDisciplina(d.id, CURSANDO, False)
    for d in classe.elegiveis:
        status[d.id] = StatusDisciplina(d.id, ELEGIVEL, situacoes.get(d.id) == hist.REPROVADA)
    for d, pendencias in classe.bloqueadas:
        status[d.id] = StatusDisciplina(d.id, BLOQUEADA, situacoes.get(d.id) == hist.REPROVADA, pendencias)

    progresso = calcular_progresso(
        disciplinas, aprovadas, creditos_obrigatorios, creditos_optativos_exigidos
    )

    # ── previsão ─────────────────────────────────────────────────────────
    por_periodo = creditos_aprovados_por_periodo(
        tentativas, {d.id: d for d in disciplinas}, periodos_por_ano
    )
    media = media_creditos_por_periodo(por_periodo)
    origem = MEDIA_DO_ALUNO if media else None
    if media is None:
        exigido = progresso.obrigatorios_exigidos
        total_exigido = None if exigido is None else exigido + (creditos_optativos_exigidos or 0)
        media = media_do_curso(total_exigido, duracao_semestres)
        origem = MEDIA_DO_CURSO if media else None

    periodos = _periodos_validos(tentativas, periodos_por_ano)
    primeiro_livre = somar_periodos(max(periodos), 1, periodos_por_ano) if periodos else None

    restantes = progresso.creditos_restantes
    n_semestres = previsao = None
    if restantes == 0:
        n_semestres = 0
    elif restantes is not None and media:
        n_semestres = semestres_restantes(restantes, media, media)
        if primeiro_livre:
            previsao = somar_periodos(primeiro_livre, n_semestres - 1, periodos_por_ano)

    return Painel(
        status=tuple(status[d.id] for d in disciplinas),
        progresso=progresso,
        disciplinas_concluidas=len(classe.concluidas),
        total_disciplinas=len(disciplinas),
        media_creditos_periodo=round(media, 1) if media else None,
        origem_media=origem,
        primeiro_periodo_livre=primeiro_livre,
        semestres_restantes=n_semestres,
        previsao_formatura=previsao,
    )

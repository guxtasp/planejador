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


# ── formatura pelo PLANO (não só pelo ritmo do histórico) ─────────────────────
SEM_DATA_CREDITOS = "creditos_nao_informados"     # o curso não informa os créditos obrigatórios exigidos
SEM_DATA_OBRIGATORIAS = "obrigatorias_faltando"   # o plano não inclui todas as obrigatórias
SEM_DATA_PLANO_VAZIO = "plano_vazio"
SEM_DATA_PERIODO = "sem_periodo"                  # nenhum período letivo no plano nem no histórico


@dataclass(frozen=True)
class FormaturaPeloPlano:
    periodo_fim: str | None                 # último período com disciplina no plano
    formatura: str | None                   # o plano fecha o curso (obrigatórias E optativas)
    so_obrigatorias: str | None             # o plano fecha as obrigatórias (data delas)
    optativas_exigidas: int | None
    optativas_cumpridas: int
    optativas_planejadas: int
    optativas_faltam: int | None            # None = o curso não informa as optativas exigidas
    formatura_com_optativas: str | None     # encaixando as que faltam (teto respeitado)
    faltam_obrigatorias: tuple[int, ...]
    sem_data: str | None                    # por que não há data (SEM_DATA_*)


def formatura_pelo_plano(
    semestres: Sequence[tuple[str | None, Sequence[int]]],
    disciplinas: Mapping[int, Disciplina],
    concluidas: Iterable[int],
    creditos_obrigatorios: int | None,
    creditos_optativos_exigidos: int | None,
    teto_creditos: int | None,
    periodo_inicial: str | None,
) -> FormaturaPeloPlano:
    """
    Quando o aluno forma SE seguir o plano. `semestres` = [(período letivo ou None, ids)]; semestre sem
    período continua a sequência (ou começa em `periodo_inicial`, o seguinte ao histórico).

    Optativas: exigidas − cumpridas (histórico) − planejadas. Se faltam, estima onde cabem nos
    semestres do plano (teto respeitado, `otimizador.encaixar_optativas`) e quantos semestres a mais
    pediriam. Sem créditos exigidos conhecidos, não há data (vazio = desconhecido).
    """
    from .otimizador import encaixar_optativas   # import tardio: o otimizador é pesado e só isto o usa

    feitas = set(concluidas)
    periodos: list[str | None] = []
    anterior = None
    for per, _ids in semestres:
        p = normalizar_periodo(per) if per else None
        if p is None:
            p = (somar_periodos(anterior, 1) if anterior else periodo_inicial)
        periodos.append(p)
        anterior = p or anterior
    planejadas = [{i for i in ids if i in disciplinas and i not in feitas} for _p, ids in semestres]
    todas = set().union(*planejadas) if planejadas else set()
    faltam_obrig = tuple(sorted(d.id for d in disciplinas.values()
                                if d.tipo == "obrigatoria" and d.id not in feitas and d.id not in todas))
    com_itens = [k for k, ids in enumerate(planejadas) if ids]
    prog = calcular_progresso(disciplinas.values(), feitas, creditos_obrigatorios, creditos_optativos_exigidos)
    cumpridas = prog.optativos_cumpridos
    opt_plan = sum(disciplinas[i].creditos or 0 for i in todas if disciplinas[i].tipo != "obrigatoria")
    faltam_opt = None if creditos_optativos_exigidos is None else max(0, creditos_optativos_exigidos - cumpridas - opt_plan)

    vazio = FormaturaPeloPlano(None, None, None, creditos_optativos_exigidos, cumpridas, opt_plan, faltam_opt,
                               None, faltam_obrig, None)
    if not com_itens:
        return FormaturaPeloPlano(**{**vazio.__dict__, "sem_data": SEM_DATA_PLANO_VAZIO})
    ultimo = com_itens[-1]
    fim = periodos[ultimo]
    if fim is None:
        return FormaturaPeloPlano(**{**vazio.__dict__, "sem_data": SEM_DATA_PERIODO})
    base = {**vazio.__dict__, "periodo_fim": fim}
    # mesma regra do progresso: sem o total informado, vale a soma das obrigatórias do catálogo
    if prog.obrigatorios_exigidos is None:
        return FormaturaPeloPlano(**{**base, "sem_data": SEM_DATA_CREDITOS})
    if faltam_obrig:
        return FormaturaPeloPlano(**{**base, "sem_data": SEM_DATA_OBRIGATORIAS})
    com_opt = fim
    if faltam_opt:
        cargas = [sum(disciplinas[i].creditos_no_limite for i in ids) for ids in planejadas[:ultimo + 1]]
        _extra, sobra = encaixar_optativas(cargas, teto_creditos, faltam_opt)
        novos = (-(-sobra // teto_creditos) if teto_creditos else 1) if sobra else 0
        com_opt = somar_periodos(fim, novos) if novos else fim
    return FormaturaPeloPlano(**{**base, "so_obrigatorias": fim,
                                 "formatura": fim if faltam_opt == 0 else None,
                                 "formatura_com_optativas": com_opt if faltam_opt is not None else None})

"""
Estágio 3 — regras semânticas (o dado é coerente com o mundo acadêmico?).

Cada regra é uma função pequena `regra(ctx)`; o estágio só as executa em ordem.
Para acrescentar uma regra, escreva a função e inclua em `REGRAS`.

Severidade: ERRO quando o dado é impossível (ciclo de pré-requisito, turma em
dois lugares ao mesmo tempo); AVISO quando é apenas incomum e quem conhece o
curso pode ter razão (período, créditos × carga horária).

As regras avaliam o estado FINAL do curso (banco + arquivo), não só o arquivo:
um requisito novo pode fechar um ciclo com requisitos já gravados.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from ...domain.ciclos import componentes_ciclicos
from ...domain.conflitos import encontros_se_sobrepoem
from ...domain.entidades import REQ_PRE
from .contexto import ContextoValidacao
from .estagio import Estagio

# Convenção usual no Brasil: 1 crédito = 15 h. É só um sinal de alerta (aviso),
# pois cada instituição pode contar diferente.
HORAS_POR_CREDITO_MIN = 10
HORAS_POR_CREDITO_MAX = 20

@dataclass(frozen=True)
class _Efetiva:
    """Valores de uma disciplina depois do upsert (arquivo sobre banco; vazio não apaga)."""

    periodo_sugerido: int | None = None
    creditos: int | None = None
    carga_h: int | None = None


def _disciplinas_efetivas(ctx: ContextoValidacao) -> dict[str, _Efetiva]:
    efetivas = {d.codigo: _Efetiva(d.periodo_sugerido, d.creditos, d.carga_h) for d in ctx.estado.disciplinas}
    for d in ctx.ativos("disciplinas.csv"):
        antes = efetivas.get(d.codigo, _Efetiva())
        efetivas[d.codigo] = _Efetiva(
            d.periodo_sugerido if d.periodo_sugerido is not None else antes.periodo_sugerido,
            d.creditos if d.creditos is not None else antes.creditos,
            d.carga_h if d.carga_h is not None else antes.carga_h,
        )
    return efetivas


def _requisitos_finais(ctx: ContextoValidacao) -> dict[tuple[str, str, str], str | None]:
    """`(disciplina, requisito, tipo) → grupo_alt` já com o arquivo aplicado sobre o banco."""
    finais = {(r.disciplina, r.requisito, r.tipo): r.grupo_alt for r in ctx.estado.requisitos}
    for r in ctx.ativos("requisitos.csv"):
        finais[(r.disciplina, r.requisito, r.tipo)] = r.grupo_alt  # grupo vazio no arquivo = AND
    return finais


# ── regras ───────────────────────────────────────────────────────────────
def ciclos_de_prerequisito(ctx: ContextoValidacao) -> None:
    """
    Pré-requisitos circulares tornam as disciplinas impossíveis de cursar.

    Ciclo só com requisitos obrigatórios (sem grupo OR) = ERRO: as linhas do
    arquivo que o formam são descartadas. Ciclo que passa por um "A ou B" =
    AVISO, pois pode existir uma alternativa de fora do ciclo.
    """
    def arestas(somente_and: bool) -> list[tuple[str, str]]:
        return [(d, req) for (d, req, tipo), grupo in _requisitos_finais(ctx).items()
                if tipo == REQ_PRE and (grupo is None or not somente_and)]

    descartar: set[int] = set()
    for ciclo in componentes_ciclicos(arestas(somente_and=True)):
        linhas = _linhas_do_ciclo(ctx, set(ciclo), somente_and=True)
        descartar |= set(linhas)
        for linha in linhas:
            ctx.erro("requisitos.csv", linha, "requisito",
                     "Pré-requisito circular entre " + ", ".join(ciclo)
                     + ": nenhuma delas poderia ser cursada primeiro.")
    ctx.descartar("requisitos.csv", descartar)

    erros_ja_resolvidos = {tuple(c) for c in componentes_ciclicos(arestas(somente_and=True))}
    for ciclo in componentes_ciclicos(arestas(somente_and=False)):
        if tuple(ciclo) in erros_ja_resolvidos:
            continue
        linhas = _linhas_do_ciclo(ctx, set(ciclo), somente_and=False)
        if linhas:  # ciclo que só existe no banco não é desta importação
            ctx.aviso("requisitos.csv", min(linhas), "requisito",
                      "Possível ciclo de pré-requisitos entre " + ", ".join(ciclo)
                      + " (passa por alternativas 'A ou B'): confira se há uma saída.")


def _linhas_do_ciclo(ctx: ContextoValidacao, membros: set[str], *, somente_and: bool) -> list[int]:
    return sorted(
        r.linha for r in ctx.ativos("requisitos.csv")
        if r.tipo == REQ_PRE and r.disciplina in membros and r.requisito in membros
        and (r.grupo_alt is None or not somente_and)
    )


def requisito_em_periodo_posterior(ctx: ContextoValidacao) -> None:
    """Pré-requisito de período igual/posterior (ou correquisito posterior) é suspeito."""
    efetivas = _disciplinas_efetivas(ctx)
    for r in ctx.ativos("requisitos.csv"):
        de = efetivas.get(r.disciplina, _Efetiva()).periodo_sugerido
        exigido = efetivas.get(r.requisito, _Efetiva()).periodo_sugerido
        if de is None or exigido is None:
            continue  # período desconhecido: nada a julgar
        anterior_ok = exigido < de if r.tipo == REQ_PRE else exigido <= de
        if not anterior_ok:
            quando = "no mesmo período" if exigido == de else "em período posterior"
            ctx.aviso("requisitos.csv", r.linha, "requisito",
                      f"{r.requisito} (período {exigido}) é exigida por {r.disciplina} "
                      f"(período {de}) mas fica {quando}. Confira a matriz.")


def grupos_or_com_membro_unico(ctx: ContextoValidacao) -> None:
    """Um grupo 'A ou B' com uma só disciplina na verdade é obrigatório."""
    membros: dict[tuple[str, str, str], int] = defaultdict(int)
    for (disciplina, _req, tipo), grupo in _requisitos_finais(ctx).items():
        if grupo is not None:
            membros[(disciplina, tipo, grupo)] += 1
    for r in ctx.ativos("requisitos.csv"):
        if r.grupo_alt is not None and membros[(r.disciplina, r.tipo, r.grupo_alt)] == 1:
            ctx.aviso("requisitos.csv", r.linha, "grupo_alt",
                      f"O grupo '{r.grupo_alt}' de {r.disciplina} tem só uma disciplina; "
                      "ele vale como requisito obrigatório. Faltou a alternativa?")


def encontros_sobrepostos_na_turma(ctx: ContextoValidacao) -> None:
    """Uma turma não pode estar em dois lugares ao mesmo tempo: ERRO, turma descartada."""
    descartar: set[int] = set()
    for t in ctx.ativos("turmas.csv"):
        pares = [(a, b) for i, a in enumerate(t.encontros) for b in t.encontros[i + 1:]
                 if encontros_se_sobrepoem(a, b)]
        if pares:
            descartar.add(t.linha)
            a, b = pares[0]
            ctx.erro("turmas.csv", t.linha, "horarios",
                     f"Encontros da mesma turma se sobrepõem: {_txt(a)} e {_txt(b)}. "
                     "Para oferecer alternativas, use uma linha por turma.")
    ctx.descartar("turmas.csv", descartar)


def _txt(encontro) -> str:
    return f"{encontro.dia} {encontro.inicio:%H:%M}-{encontro.fim:%H:%M}"


def razao_creditos_carga_horaria(ctx: ContextoValidacao) -> None:
    """Créditos e carga horária incompatíveis (ex.: 4 créditos e 15 h) costumam ser erro de digitação."""
    efetivas = _disciplinas_efetivas(ctx)
    for d in ctx.ativos("disciplinas.csv"):
        e = efetivas[d.codigo]
        if e.creditos is None or e.carga_h is None or (e.creditos == 0 and e.carga_h == 0):
            continue
        if e.creditos == 0 or e.carga_h == 0:
            ctx.aviso("disciplinas.csv", d.linha, "carga_h",
                      f"{d.codigo}: {e.creditos} crédito(s) e {e.carga_h} h — um dos dois é zero.")
        elif not HORAS_POR_CREDITO_MIN <= e.carga_h / e.creditos <= HORAS_POR_CREDITO_MAX:
            ctx.aviso("disciplinas.csv", d.linha, "carga_h",
                      f"{d.codigo}: {e.carga_h} h para {e.creditos} crédito(s) dá "
                      f"{e.carga_h / e.creditos:.1f} h por crédito (o usual é cerca de 15). Confira.")


def periodo_acima_da_duracao(ctx: ContextoValidacao) -> None:
    """Disciplina sugerida para depois do último semestre do curso."""
    curso = ctx.ativos("curso.csv")
    duracao = curso[0].duracao_semestres if curso and curso[0].duracao_semestres is not None else (
        ctx.estado.curso.duracao_semestres if ctx.estado.curso else None)
    if duracao is None:
        return
    for d in ctx.ativos("disciplinas.csv"):
        if d.periodo_sugerido is not None and d.periodo_sugerido > duracao:
            ctx.aviso("disciplinas.csv", d.linha, "periodo_sugerido",
                      f"{d.codigo} é sugerida para o período {d.periodo_sugerido}, "
                      f"mas o curso tem {duracao} semestre(s).")


def tipo_da_disciplina_mudou(ctx: ContextoValidacao) -> None:
    """Trocar obrigatória↔optativa muda o cálculo de progresso: vale um aviso explícito."""
    anteriores = {d.codigo: d.tipo for d in ctx.estado.disciplinas}
    for d in ctx.ativos("disciplinas.csv"):
        antes = anteriores.get(d.codigo)
        if antes is not None and antes != d.tipo:
            ctx.aviso("disciplinas.csv", d.linha, "tipo",
                      f"{d.codigo} muda de '{antes}' para '{d.tipo}': isso altera o cálculo de progresso.")


REGRAS: tuple[Callable[[ContextoValidacao], None], ...] = (
    encontros_sobrepostos_na_turma,   # primeiro: descartam linhas antes das regras que dependem delas
    ciclos_de_prerequisito,
    requisito_em_periodo_posterior,
    grupos_or_com_membro_unico,
    razao_creditos_carga_horaria,
    periodo_acima_da_duracao,
    tipo_da_disciplina_mudou,
)


class EstagioSemantico(Estagio):
    nome = "semantico"

    def executar(self, ctx: ContextoValidacao) -> None:
        for regra in REGRAS:
            regra(ctx)

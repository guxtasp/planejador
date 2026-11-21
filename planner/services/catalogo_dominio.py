"""
Catálogo do curso convertido em entidades do domínio.

Os serviços que alimentam o motor de regras (análise de plano, painel do aluno)
precisam da mesma tradução modelos → value objects; fica num lugar só.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.componentes import id_combinado, opcoes_de_matricula
from ..domain.entidades import Disciplina, Encontro, Requisito, Tentativa, Turma
from ..repositories import DisciplinaRepository


@dataclass(frozen=True)
class CatalogoDominio:
    disciplinas: dict[int, Disciplina]
    requisitos: dict[int, list[Requisito]]
    turmas: dict[int, list[Turma]]       # vazio quando `com_turmas=False`


def carregar_catalogo(
    repositorio: DisciplinaRepository, curso_id: int, *, com_turmas: bool = False
) -> CatalogoDominio:
    """Uma consulta fixa por relação (sem N+1)."""
    modelos = repositorio.listar_do_curso(curso_id, com_requisitos=True, com_turmas=com_turmas)
    disciplinas = {
        d.id: Disciplina(d.id, d.codigo, d.nome, d.creditos, d.tipo, d.periodo_sugerido, d.periodicidade,
                         d.conta_no_limite is not False)
        for d in modelos
    }
    requisitos = {
        d.id: [Requisito(d.id, r.requisito_id, r.tipo, r.grupo_alt) for r in d.requisitos]
        for d in modelos
    }
    # teórica + prática separadas viram opções combinadas (id negativo): o motor escolhe UMA por disciplina
    turmas = {
        d.id: [turma_do_dominio(d.id, partes) for partes in opcoes_de_matricula(d.turmas)]
        for d in modelos
    } if com_turmas else {}
    return CatalogoDominio(disciplinas, requisitos, turmas)


def tentativas_do_dominio(historico) -> list:
    """`Historico` (modelos) → `Tentativa` (domínio). Nota fica de fora: nenhuma regra a usa."""
    return [Tentativa(h.disciplina_id, h.status, h.periodo_letivo) for h in historico]


def turma_do_dominio(disciplina_id: int, partes) -> Turma:
    """Uma opção de matrícula (1 turma, ou teórica + prática) como `Turma` do domínio."""
    if len(partes) == 1:
        t = partes[0]
        return Turma(t.id, disciplina_id, tuple(Encontro(e.dia, e.inicio, e.fim) for e in t.encontros),
                     t.periodo_letivo, t.codigo_turma)
    teo, pra = partes
    return Turma(id_combinado(teo.id, pra.id), disciplina_id,
                 tuple(Encontro(e.dia, e.inicio, e.fim) for t in partes for e in t.encontros),
                 teo.periodo_letivo, f"{teo.codigo_turma}+{pra.codigo_turma}")

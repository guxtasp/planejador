"""
Serviço de importação: CONFIRMA (grava) o que a prévia mostrou — Etapa 3C.

Garantias:
  * a prévia é refeita aqui dentro (os arquivos podem ter mudado, ou o banco,
    desde a tela de validação) e só segue se `pode_confirmar`;
  * tudo numa ÚNICA transação: qualquer falha dá `rollback` e não sobra nada pela metade;
  * só grava o que a prévia classificou como `novo` ou `atualizar`;
  * célula vazia nunca apaga valor conhecido e nada é removido (ver `previa.py`);
  * só o dono altera um curso existente (`dono_id`); o curso novo nasce com esse dono.

O histórico do aluno não faz parte da importação: é informado dentro do app (Etapa 5B).
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Mapping

from sqlalchemy.orm import Session

from ..api.errors import AppError, NotFoundError
from ..extensions import db
from ..importers.validacao import ATUALIZAR, INALTERADO, NOVO, ImportPreview
from ..models import Curso, Disciplina, Encontro, Requisito, Turma, Visibilidade
from ..repositories import (CursoRepository, DisciplinaRepository, RequisitoRepository,
                            TurmaRepository)
from .previa_importacao import PreviaImportacaoService


@dataclass(frozen=True)
class RelatorioImportacao:
    """Resultado final: contagem por arquivo e o curso que recebeu os dados."""

    curso_id: int
    curso_criado: bool
    por_arquivo: Mapping[str, Mapping[str, int]]
    avisos: tuple[dict[str, Any], ...] = field(default=(), repr=False)

    def para_dict(self) -> dict[str, Any]:
        return {"curso_id": self.curso_id, "curso_criado": self.curso_criado,
                "por_arquivo": {a: dict(c) for a, c in self.por_arquivo.items()},
                "avisos": list(self.avisos)}


class ImportacaoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._previa = PreviaImportacaoService(sessao)
        self._cursos = CursoRepository(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._requisitos = RequisitoRepository(sessao)
        self._turmas = TurmaRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def confirmar(
        self,
        arquivos: Mapping[str, bytes | str],
        *,
        curso_id: int | None = None,
        dono_id: int | None = None,
        visibilidade: str | None = None,
    ) -> RelatorioImportacao:
        if visibilidade is not None and visibilidade not in {v.value for v in Visibilidade}:
            raise AppError(f"Visibilidade inválida: '{visibilidade}'.")
        previa = self._previa.gerar(arquivos, curso_id=curso_id, dono_id=dono_id)
        self._exigir_confirmavel(previa)
        try:
            relatorio = self._gravar(previa, curso_id, dono_id, visibilidade)
            self.sessao.commit()
        except Exception:
            self.sessao.rollback()
            raise
        return relatorio

    # ── validações de entrada ────────────────────────────────────────────
    @staticmethod
    def _exigir_confirmavel(previa: ImportPreview) -> None:
        if previa.erros:
            raise AppError("A importação tem erros; corrija os arquivos e valide de novo.",
                           422, details=previa.para_dict())
        if not previa.pode_confirmar:
            raise AppError("Nada a importar: os dados enviados já estão iguais aos do curso.",
                           422, details=previa.para_dict())

    def _resolver_curso(self, previa: ImportPreview, curso_id: int | None, dono_id: int | None) -> Curso | None:
        """Curso existente que receberá os dados; None = será criado a partir de curso.csv."""
        if curso_id is not None:
            curso = self._cursos.obter(curso_id)
            if curso is None or curso.dono_id != dono_id:   # alheio = mesmo 404 de inexistente
                raise NotFoundError(f"Curso {curso_id} não encontrado.")
            return curso
        registros = previa.registros.get("curso.csv", ())
        if not registros:
            raise AppError("Informe o curso: envie curso.csv ou indique o curso de destino (curso_id).")
        return self._cursos.obter_por_nome(registros[0].nome, dono_id)

    # ── escrita (uma função por arquivo, na ordem de dependência) ─────────
    def _gravar(self, previa, curso_id, dono_id, visibilidade) -> RelatorioImportacao:
        curso = self._resolver_curso(previa, curso_id, dono_id)
        acoes = {(i.arquivo, i.linha): i.acao for a in previa.arquivos for i in a.itens}
        contagem = {a.arquivo: {NOVO: 0, ATUALIZAR: 0, INALTERADO: 0} for a in previa.arquivos}
        for (arquivo, _), acao in acoes.items():
            contagem[arquivo][acao] += 1

        criado = curso is None
        curso = self._gravar_curso(previa, curso, acoes, dono_id, visibilidade)

        existentes = {d.codigo: d for d in self._disciplinas.listar_do_curso(
            curso.id, com_requisitos=True, com_turmas=True)}
        self._gravar_disciplinas(previa, curso, existentes, acoes)
        self._gravar_requisitos(previa, existentes, acoes)
        self._gravar_turmas(previa, existentes, acoes)

        return RelatorioImportacao(
            curso_id=curso.id, curso_criado=criado,
            por_arquivo={a: {"criados": c[NOVO], "atualizados": c[ATUALIZAR], "inalterados": c[INALTERADO]}
                         for a, c in contagem.items()},
            avisos=tuple(i.para_dict() for i in previa.avisos),
        )

    def _gravar_curso(self, previa, curso, acoes, dono_id, visibilidade) -> Curso:
        registros = previa.registros.get("curso.csv", ())
        dados = {f.name: getattr(registros[0], f.name) for f in fields(registros[0]) if f.name != "linha"} \
            if registros else {}
        dados = {k: (list(v) if k == "dias_letivos" and v is not None else v)
                 for k, v in dados.items() if v is not None}  # vazio nunca apaga
        if curso is None:
            curso = Curso(dono_id=dono_id, visibilidade=visibilidade or Visibilidade.PRIVADO.value, **dados)
            return self._cursos.adicionar(curso)
        if visibilidade is not None:
            curso.visibilidade = visibilidade
        if registros and acoes.get(("curso.csv", registros[0].linha)) != INALTERADO:
            for campo, valor in dados.items():
                setattr(curso, campo, valor)
            self.sessao.flush()
        return curso

    def _gravar_disciplinas(self, previa, curso, existentes, acoes) -> None:
        for r in previa.registros.get("disciplinas.csv", ()):
            acao = acoes[("disciplinas.csv", r.linha)]
            if acao == INALTERADO:
                continue
            valores = {c: getattr(r, c) for c in ("nome", "tipo", "creditos", "carga_h", "periodo_sugerido", "cor",
                                                "periodicidade")
                       if getattr(r, c) is not None}
            if acao == NOVO:
                existentes[r.codigo] = self._disciplinas.adicionar(
                    Disciplina(curso_id=curso.id, codigo=r.codigo, **valores))
            else:
                for campo, valor in valores.items():
                    setattr(existentes[r.codigo], campo, valor)
        self.sessao.flush()

    def _gravar_requisitos(self, previa, existentes, acoes) -> None:
        for r in previa.registros.get("requisitos.csv", ()):
            acao = acoes[("requisitos.csv", r.linha)]
            if acao == INALTERADO:
                continue
            disc, req = existentes[r.disciplina], existentes[r.requisito]
            if acao == NOVO:
                self._requisitos.adicionar(Requisito(
                    disciplina_id=disc.id, requisito_id=req.id, tipo=r.tipo, grupo_alt=r.grupo_alt))
            else:  # só o grupo pode mudar (e a prévia só marca "atualizar" se o arquivo traz um grupo)
                self._requisitos.obter(disc.id, req.id, r.tipo).grupo_alt = r.grupo_alt
        self.sessao.flush()

    def _gravar_turmas(self, previa, existentes, acoes) -> None:
        for r in previa.registros.get("turmas.csv", ()):
            acao = acoes[("turmas.csv", r.linha)]
            if acao == INALTERADO:
                continue
            disc = existentes[r.disciplina]
            if acao == NOVO:
                turma = self._turmas.adicionar(Turma(
                    disciplina_id=disc.id, periodo_letivo=r.periodo_letivo, codigo_turma=r.codigo_turma,
                    docente=r.docente, vagas=r.vagas))
            else:
                turma = self._turmas.obter_por_chave(disc.id, r.periodo_letivo, r.codigo_turma)
                if r.docente is not None:
                    turma.docente = r.docente
                if r.vagas is not None:
                    turma.vagas = r.vagas
            if r.encontros:  # sem horários no arquivo = desconhecido: mantém os do banco
                turma.encontros = [Encontro(dia=e.dia, inicio=e.inicio, fim=e.fim, local=r.local)
                                   for e in r.encontros]
            elif r.local is not None:  # só a sala mudou: aplica aos encontros já gravados
                for encontro in turma.encontros:
                    encontro.local = r.local
        self.sessao.flush()

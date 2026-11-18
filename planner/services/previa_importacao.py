"""
Serviço da prévia de importação (dry-run): liga arquivos enviados ao banco.

Fluxo: lê cada CSV (3A) → carrega o estado atual do curso pelos repositories
(SOMENTE leitura) → roda o pipeline de validação (3B). Nunca grava e nunca dá
`commit`; quem confirma a importação é a Etapa 3C.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from ..api.errors import NotFoundError
from ..domain.entidades import Encontro
from ..importers import IMPORTADORES
from ..importers.base import Issue, ResultadoLeitura, Severidade
from ..importers.validacao import (CursoExistente, DisciplinaExistente, EstadoExistente, ImportPreview,
                                   RequisitoExistente, TurmaExistente, gerar_previa)
from ..models import Curso
from ..repositories import CursoRepository, DisciplinaRepository


class PreviaImportacaoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoRepository(sessao)
        self._disciplinas = DisciplinaRepository(sessao)

    def gerar(
        self,
        arquivos: Mapping[str, bytes | str],
        *,
        curso_id: int | None = None,
        dono_id: int | None = None,
    ) -> ImportPreview:
        """
        Prévia da importação de `arquivos` (`{"disciplinas.csv": conteúdo, …}`).

        `curso_id` indica o curso que receberá os dados e precisa ser de `dono_id`
        (senão `NotFoundError`: a prévia mostra os dados atuais do curso, e esses
        não são de quem não é o dono). Sem `curso_id`, o curso é o de mesmo nome
        (e `dono_id`) citado em `curso.csv`; se não existir, a prévia trata tudo
        como curso novo. Arquivos com nome fora do formato viram ERRO
        na prévia (e não exceção), para a tela mostrar junto dos demais problemas.
        """
        leituras: dict[str, ResultadoLeitura] = {}
        desconhecidos: list[Issue] = []
        for nome, conteudo in arquivos.items():
            if nome == "historico.csv":
                desconhecidos.append(Issue(
                    nome, None, None, Severidade.ERRO,
                    "O histórico do aluno não é importado por CSV: ele será informado dentro do app. "
                    "Retire este arquivo do envio."))
            elif nome in IMPORTADORES:
                leituras[nome] = IMPORTADORES[nome].importar(conteudo)
            else:
                desconhecidos.append(Issue(
                    nome, None, None, Severidade.ERRO,
                    f"Arquivo não reconhecido. Nomes aceitos: {', '.join(IMPORTADORES)}."))

        if curso_id is None:
            curso_id = self._descobrir_curso(leituras, dono_id)
        else:
            self._exigir_dono(curso_id, dono_id)
        previa = gerar_previa(leituras, self.carregar_estado(curso_id))
        if not desconhecidos:
            return previa
        return ImportPreview(previa.arquivos, previa.issues + tuple(desconhecidos), previa.registros)

    def _exigir_dono(self, curso_id: int, dono_id: int | None) -> None:
        curso = self._cursos.obter(curso_id)
        # Id inexistente segue como "curso novo" na prévia (a confirmação recusa); o que
        # não pode é ler os dados de um curso alheio.
        if curso is not None and curso.dono_id != dono_id:
            raise NotFoundError(f"Curso {curso_id} não encontrado.")

    def _descobrir_curso(self, leituras: Mapping[str, ResultadoLeitura], dono_id: int | None) -> int | None:
        registros = leituras["curso.csv"].registros if "curso.csv" in leituras else []
        if not registros:
            return None
        curso = self._cursos.obter_por_nome(registros[0].nome, dono_id)
        return curso.id if curso else None

    def carregar_estado(self, curso_id: int | None) -> EstadoExistente:
        """Retrato do curso no banco (curso novo = estado vazio). Consultas fixas, sem N+1."""
        curso = self._cursos.obter(curso_id) if curso_id is not None else None
        if curso is None:
            return EstadoExistente()
        disciplinas = self._disciplinas.listar_do_curso(curso.id, com_requisitos=True, com_turmas=True)
        codigos = {d.id: d.codigo for d in disciplinas}
        return EstadoExistente(
            curso=_curso(curso),
            disciplinas=tuple(_disciplina(d) for d in disciplinas),
            requisitos=tuple(sorted(
                (RequisitoExistente(d.codigo, codigos[r.requisito_id], r.tipo, r.grupo_alt)
                 for d in disciplinas for r in d.requisitos),
                key=lambda r: (r.disciplina, r.requisito, r.tipo))),
            turmas=tuple(sorted(
                (_turma(d.codigo, t) for d in disciplinas for t in d.turmas),
                key=lambda t: (t.disciplina, t.periodo_letivo, t.codigo_turma))),
        )


def _curso(c: Curso) -> CursoExistente:
    return CursoExistente(
        nome=c.nome, instituicao=c.instituicao, versao_matriz=c.versao_matriz,
        creditos_obrigatorios=c.creditos_obrigatorios,
        creditos_optativos_exigidos=c.creditos_optativos_exigidos, ch_total=c.ch_total,
        max_creditos_semestre=c.max_creditos_semestre, duracao_semestres=c.duracao_semestres,
        dias_letivos=tuple(c.dias_letivos) if c.dias_letivos else None)


def _disciplina(d) -> DisciplinaExistente:
    return DisciplinaExistente(d.codigo, d.nome, d.tipo, d.creditos, d.carga_h, d.periodo_sugerido, d.cor,
                               d.periodicidade)


def _turma(codigo_disciplina: str, t) -> TurmaExistente:
    return TurmaExistente(
        codigo_disciplina, t.periodo_letivo, t.codigo_turma, t.docente, t.vagas,
        tuple(Encontro(e.dia, e.inicio, e.fim) for e in t.encontros),
        next((e.local for e in t.encontros if e.local), None))

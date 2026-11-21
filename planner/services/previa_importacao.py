"""
Serviço da prévia de importação (dry-run): liga arquivos enviados ao banco.

Fluxo: lê cada CSV (3A) → carrega o estado atual do curso pelos repositories
(SOMENTE leitura) → roda o pipeline de validação (3B). Nunca grava e nunca dá
`commit`; quem confirma a importação é a Etapa 3C.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from sqlalchemy.orm import Session

from ..api.errors import NotFoundError
from ..domain.cursos_parecidos import Candidato, CursoConhecido, candidatos_a_atualizar
from ..domain.entidades import Encontro
from ..importers import IMPORTADORES
from ..importers.base import Issue, ResultadoLeitura, Severidade
from ..importers.validacao import (CursoExistente, DisciplinaExistente, EstadoExistente, ImportPreview,
                                   RequisitoExistente, TurmaExistente, gerar_previa)
from ..models import Curso
from ..repositories import CursoRepository, DisciplinaRepository


@dataclass(frozen=True)
class DestinoImportacao:
    """Para qual curso vão os dados. Com candidatos e sem escolha, a pessoa PRECISA decidir."""

    curso_id: int | None                     # curso que será atualizado (None = curso novo)
    curso_nome: str | None = None
    candidatos: tuple[Candidato, ...] = ()
    decisao_necessaria: bool = False         # há candidato e a pessoa não disse "atualizar" nem "criar novo"
    mensagem: str | None = None
    nota_curso: str | None = None            # atualização sem curso.csv: os dados do curso não mudam
    extra: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        return {
            "curso_id": self.curso_id, "curso_nome": self.curso_nome,
            "decisao_necessaria": self.decisao_necessaria, "mensagem": self.mensagem,
            "nota_curso": self.nota_curso,
            "candidatos": [{"curso_id": c.curso_id, "nome": c.nome, "motivo": c.motivo,
                            "em_comum": c.em_comum, "enviados": c.enviados, "no_curso": c.no_curso,
                            "texto": _texto_candidato(c)} for c in self.candidatos],
        }


def _texto_candidato(c: Candidato) -> str:
    if c.em_comum:
        return f"Parece o curso “{c.nome}” ({c.em_comum} de {c.enviados} disciplinas em comum)."
    return f"Parece o curso “{c.nome}” (mesmo nome)."


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
        criar_novo: bool = False,
    ) -> ImportPreview:
        """Só a prévia (compatível com quem já chamava). Ver `previa_e_destino`."""
        return self.previa_e_destino(arquivos, curso_id=curso_id, dono_id=dono_id, criar_novo=criar_novo)[0]

    def previa_e_destino(
        self,
        arquivos: Mapping[str, bytes | str],
        *,
        curso_id: int | None = None,
        dono_id: int | None = None,
        criar_novo: bool = False,
    ) -> tuple[ImportPreview, DestinoImportacao]:
        """
        Prévia da importação de `arquivos` (`{"disciplinas.csv": conteúdo, …}`).

        `curso_id` indica o curso que receberá os dados e precisa ser de `dono_id`
        (senão `NotFoundError`: a prévia mostra os dados atuais do curso, e esses
        não são de quem não é o dono). `criar_novo` = a pessoa escolheu curso novo.
        Sem nenhum dos dois, procura cursos PARECIDOS do mesmo dono (nome normalizado +
        instituição ou ≥ 60% dos códigos, `domain.cursos_parecidos`): havendo candidato, a
        prévia compara com o mais parecido, mas exige a decisão (nunca junta nem cria em
        silêncio). Arquivos com nome fora do formato viram ERRO
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

        destino = self._destino(leituras, curso_id, dono_id, criar_novo)
        comparar_com = destino.curso_id if destino.curso_id is not None else (
            destino.candidatos[0].curso_id if destino.candidatos else None)
        previa = gerar_previa(leituras, self.carregar_estado(comparar_com))
        if desconhecidos:
            previa = ImportPreview(previa.arquivos, previa.issues + tuple(desconhecidos), previa.registros)
        return previa, destino

    def _exigir_dono(self, curso_id: int, dono_id: int | None) -> None:
        curso = self._cursos.obter(curso_id)
        # Id inexistente segue como "curso novo" na prévia (a confirmação recusa); o que
        # não pode é ler os dados de um curso alheio.
        if curso is not None and curso.dono_id != dono_id:
            raise NotFoundError(f"Curso {curso_id} não encontrado.")

    def _destino(self, leituras, curso_id, dono_id, criar_novo) -> DestinoImportacao:
        registros = leituras["curso.csv"].registros if "curso.csv" in leituras else []
        if curso_id is not None:
            self._exigir_dono(curso_id, dono_id)
            curso = self._cursos.obter(curso_id)
            nota = None if registros else \
                "Sem curso.csv (ou vazio): os dados do curso (nome, créditos, duração…) não mudam."
            return DestinoImportacao(curso_id, curso.nome if curso else None,
                                     mensagem=f"Atualizando “{curso.nome}”." if curso else None, nota_curso=nota)
        if criar_novo:
            return DestinoImportacao(None, registros[0].nome if registros else None,
                                     mensagem="Será criado um curso novo.")
        codigos = [r.codigo for r in (leituras["disciplinas.csv"].registros if "disciplinas.csv" in leituras else [])]
        nome = registros[0].nome if registros else None
        inst = getattr(registros[0], "instituicao", None) if registros else None
        conhecidos = [CursoConhecido(c.id, c.nome, c.instituicao, frozenset(cods))
                      for c, cods in self._cursos.listar_do_dono_com_codigos(dono_id)]
        candidatos = candidatos_a_atualizar(nome, inst, codigos, conhecidos)
        if not candidatos:
            return DestinoImportacao(None, nome, mensagem="Nenhum curso seu parecido: será criado um curso novo.")
        c = candidatos[0]
        outros = f" Há {len(candidatos)} cursos parecidos; escolha um." if len(candidatos) > 1 else ""
        return DestinoImportacao(
            None, nome, candidatos, True,
            mensagem=f"{_texto_candidato(c)} Atualizar “{c.nome}” ou criar um curso novo?{outros} "
                     f"A comparação abaixo é com “{c.nome}”.")

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
        next((e.local for e in t.encontros if e.local), None), t.componente)

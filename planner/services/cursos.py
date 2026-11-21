"""
Casos de uso de leitura de cursos (Etapa 4A): listar, abrir e catálogo.

Só leitura — gravar curso é da importação (`ImportacaoService`) e editar disciplina, do
`DisciplinaService`.
Devolve dicionários prontos para JSON; a camada HTTP não conhece modelos.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import ConflictError, NotFoundError, ProibidoError
from ..models import Curso, Visibilidade
from ..repositories import CursoRepository, DisciplinaRepository
from .disciplinas_json import disciplina_json


class CursoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoRepository(sessao)
        self._disciplinas = DisciplinaRepository(sessao)

    # ── listar ────────────────────────────────────────────────────────────
    def listar(self, usuario_id: int | None = None) -> list[dict]:
        """Cursos que o visitante pode abrir, com contadores para o onboarding."""
        cursos = self._cursos.listar_acessiveis(usuario_id)
        contagens = self._cursos.contagens([c.id for c in cursos])
        return [
            {**self._resumo(c), "total_disciplinas": contagens[c.id][0], "total_turmas": contagens[c.id][1],
             "meu": usuario_id is not None and c.dono_id == usuario_id}
            for c in cursos
        ]

    # ── abrir ─────────────────────────────────────────────────────────────
    def obter(self, curso_id: int, usuario_id: int | None = None) -> dict:
        return self._resumo(self._curso_acessivel(curso_id, usuario_id))

    def catalogo(self, curso_id: int, usuario_id: int | None = None) -> dict:
        """
        Curso + disciplinas com requisitos. Campos desconhecidos saem `null`
        (nunca 0): a tela decide como mostrar.
        """
        curso = self._curso_acessivel(curso_id, usuario_id)
        disciplinas = self._disciplinas.listar_do_curso(curso.id, com_requisitos=True)
        por_id = {d.id: d for d in disciplinas}   # resolve requisitos sem nova consulta
        return {
            "curso": self._resumo(curso),
            # a tela só mostra a edição da oferta (par/ímpar) para quem pode alterá-la: o dono
            "pode_editar_oferta": usuario_id is not None and curso.dono_id == usuario_id,
            # …e editar/criar disciplinas (a mesma regra: só quem trouxe o curso)
            "pode_editar_catalogo": usuario_id is not None and curso.dono_id == usuario_id,
            "disciplinas": [disciplina_json(d, por_id, _oferta(d)) for d in disciplinas],
        }

    # ── excluir ───────────────────────────────────────────────────────────
    def excluir(self, curso_id: int, usuario_id: int) -> None:
        """
        Apaga o curso e tudo que depende dele (disciplinas, requisitos, turmas, planos, histórico).

        Só o DONO pode. Curso que o visitante nem enxerga dá 404 (não revela que existe); curso
        público de outra pessoa dá 403. Se OUTRA conta tem histórico nele, não apaga (409): seria
        destruir dados que não são do dono.
        """
        curso = self._curso_acessivel(curso_id, usuario_id)
        if curso.dono_id != usuario_id:
            raise ProibidoError("Só quem trouxe o curso pode excluí-lo.")
        outros = self._cursos.usuarios_com_historico(curso.id) - {usuario_id}
        if outros:
            raise ConflictError(
                "Outras pessoas já registraram histórico neste curso, então ele não pode ser excluído. "
                "Deixe-o privado para tirá-lo da lista pública.")
        self._cursos.apagar_historico_do_curso(curso.id)
        self._cursos.remover(curso)
        self._cursos.sessao.commit()

    # ── internos ──────────────────────────────────────────────────────────
    def _curso_acessivel(self, curso_id: int, usuario_id: int | None) -> Curso:
        curso = self._cursos.obter(curso_id)
        # Mesma regra de `listar`. Curso inexistente e curso alheio dão o MESMO
        # 404, para não revelar a existência de cursos privados de outras pessoas.
        publico = curso is not None and curso.visibilidade == Visibilidade.PUBLICO.value
        meu = curso is not None and usuario_id is not None and curso.dono_id == usuario_id
        if not (publico or meu):
            raise NotFoundError("Curso não encontrado.")
        return curso

    @staticmethod
    def _resumo(c: Curso) -> dict:
        return {
            "id": c.id, "nome": c.nome, "instituicao": c.instituicao, "versao_matriz": c.versao_matriz,
            "creditos_obrigatorios": c.creditos_obrigatorios,
            "creditos_optativos_exigidos": c.creditos_optativos_exigidos,
            "ch_total": c.ch_total, "max_creditos_semestre": c.max_creditos_semestre,
            "duracao_semestres": c.duracao_semestres, "dias_letivos": c.dias_letivos,
            "visibilidade": c.visibilidade,
        }


def _oferta(d) -> dict:
    from ..domain.entidades import Disciplina as DiscDominio
    from ..domain.periodicidade import periodicidade_efetiva
    e = periodicidade_efetiva(DiscDominio(d.id, d.codigo, d.nome, d.creditos, d.tipo, d.periodo_sugerido, d.periodicidade))
    return {"valor": e.valor, "origem": e.origem}

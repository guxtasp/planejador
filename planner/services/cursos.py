"""
Casos de uso de leitura de cursos (Etapa 4A): listar, abrir e catálogo.

Só leitura — gravar curso continua sendo da importação (`ImportacaoService`).
Devolve dicionários prontos para JSON; a camada HTTP não conhece modelos.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..api.errors import NotFoundError
from ..models import Curso, Visibilidade
from ..repositories import CursoRepository, DisciplinaRepository


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
            {**self._resumo(c), "total_disciplinas": contagens[c.id][0], "total_turmas": contagens[c.id][1]}
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
            "disciplinas": [
                {
                    "id": d.id, "codigo": d.codigo, "nome": d.nome, "tipo": d.tipo,
                    "creditos": d.creditos, "carga_h": d.carga_h,
                    "periodo_sugerido": d.periodo_sugerido, "cor": d.cor,
                    "requisitos": [
                        {"id": r.requisito_id, "codigo": por_id[r.requisito_id].codigo,
                         "nome": por_id[r.requisito_id].nome, "tipo": r.tipo, "grupo_alt": r.grupo_alt}
                        for r in d.requisitos if r.requisito_id in por_id
                    ],
                }
                for d in disciplinas
            ],
        }

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

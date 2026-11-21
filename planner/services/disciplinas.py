"""
Editar e criar disciplinas pela tela (sem reimportar o CSV).

Só quem trouxe o curso pode. A edição muda só os campos enviados; `requisitos` troca a lista
inteira e é recusada se criar um círculo de pré-requisitos (ninguém conseguiria cursar).
Planos e histórico apontam para a disciplina pelo id, então trocar o código não quebra nada.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..api.errors import AppError, ConflictError, NotFoundError, ProibidoError
from ..domain.edicao_catalogo import ciclo_com_novos_requisitos
from ..extensions import db
from ..models import Disciplina
from ..repositories import CursoRepository, DisciplinaRepository
from .cursos import CursoService, _oferta
from .disciplinas_json import disciplina_json, ler_disciplina


class DisciplinaService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoService(sessao)
        self._repo_cursos = CursoRepository(sessao)
        self._disciplinas = DisciplinaRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def editar(self, curso_id: int, usuario_id: int, disciplina_id: int, payload) -> dict:
        por_id = self._do_dono(curso_id, usuario_id)
        d = por_id.get(disciplina_id)
        if d is None:
            raise NotFoundError("Disciplina não encontrada neste curso.")
        return self._gravar(d, por_id, ler_disciplina(payload, nova=False))

    def criar(self, curso_id: int, usuario_id: int, payload) -> dict:
        por_id = self._do_dono(curso_id, usuario_id)
        dados = ler_disciplina(payload, nova=True)
        d = Disciplina(curso_id=curso_id, codigo=dados["codigo"], nome=dados["nome"], tipo=dados["tipo"])
        return self._gravar(d, por_id, dados, nova=True)

    # ── internos ──────────────────────────────────────────────────────────
    def _do_dono(self, curso_id: int, usuario_id: int) -> dict[int, Disciplina]:
        self._cursos.obter(curso_id, usuario_id)          # 404 se não pode nem ver o curso
        curso = self._repo_cursos.obter(curso_id)
        if curso.dono_id != usuario_id:
            raise ProibidoError("Só quem trouxe o curso pode editar as disciplinas.")
        return {d.id: d for d in self._disciplinas.listar_do_curso(curso_id, com_requisitos=True)}

    def _gravar(self, d: Disciplina, por_id: dict[int, Disciplina], dados: dict, nova: bool = False) -> dict:
        codigo = dados.get("codigo")
        if codigo and any(o.codigo.lower() == codigo.lower() and o is not d for o in por_id.values()):
            raise AppError(f"Já existe outra disciplina com o código {codigo} neste curso.", 409, {"campo": "codigo"})
        requisitos = dados.pop("requisitos", None)
        if requisitos is not None:
            self._conferir_requisitos(d, por_id, requisitos)
        try:
            for campo, valor in dados.items():
                setattr(d, campo, valor)
            if nova:
                self._disciplinas.adicionar(d)
                por_id[d.id] = d
            if requisitos is not None:
                self._disciplinas.substituir_requisitos(d, requisitos)
            self.sessao.commit()
        except IntegrityError:
            self.sessao.rollback()
            raise ConflictError("Não foi possível salvar: o código já existe ou um requisito se repete.") from None
        self.sessao.refresh(d)
        return {"disciplina": disciplina_json(d, por_id, _oferta(d))}

    @staticmethod
    def _conferir_requisitos(d: Disciplina, por_id: dict[int, Disciplina], requisitos) -> None:
        fora = [rid for rid, _, _ in requisitos if rid not in por_id]
        if fora:
            raise AppError("Há um requisito que não é disciplina deste curso.", 422, {"campo": "requisitos"})
        if d.id is not None and any(rid == d.id for rid, _, _ in requisitos):
            raise AppError("Uma disciplina não pode exigir ela mesma.", 422, {"campo": "requisitos"})
        if d.id is None:
            return                                        # nova: ninguém a exige ainda, não fecha círculo
        arestas = [(o.id, r.requisito_id) for o in por_id.values() for r in o.requisitos if r.tipo == "pre"]
        ciclo = ciclo_com_novos_requisitos(d.id, [rid for rid, tipo, _ in requisitos if tipo == "pre"], arestas)
        if ciclo:
            nomes = ", ".join(por_id[i].codigo for i in ciclo if i in por_id)
            raise AppError(f"Esses pré-requisitos fecham um círculo ({nomes}): ninguém conseguiria cursar. "
                           "Tire um deles.", 422, {"campo": "requisitos"})

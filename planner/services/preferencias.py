"""
Preferências do aluno por curso: guardar uma vez e valer em Simulador, Sugestão, Planejamento e
Calendário. Valida com as mesmas regras do pedido de simulação (`simulacao_json.preferencias_para_salvar`).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..extensions import db
from ..repositories import DisciplinaRepository, PreferenciaRepository
from ..api.errors import AppError
from .cursos import CursoService
from .simulacao_json import preferencias_para_salvar


class PreferenciaService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._sessao = sessao
        self._cursos = CursoService(sessao)
        self._repo = PreferenciaRepository(sessao)
        self._disciplinas = DisciplinaRepository(sessao)

    @property
    def sessao(self) -> Session:
        return self._sessao if self._sessao is not None else db.session

    def dados(self, curso_id: int, usuario_id: int) -> dict:
        """O que está guardado ({} se nada). Não valida o curso: quem chama já validou."""
        registro = self._repo.obter(usuario_id, curso_id)
        return dict(registro.dados) if registro else {}

    def obter(self, curso_id: int, usuario_id: int) -> dict:
        self._cursos.obter(curso_id, usuario_id)
        return {"preferencias": self.dados(curso_id, usuario_id)}

    def salvar(self, curso_id: int, usuario_id: int, payload) -> dict:
        self._cursos.obter(curso_id, usuario_id)
        bruto = payload.get("preferencias", payload) if isinstance(payload, dict) else payload
        dados = preferencias_para_salvar(bruto)
        ids = (set(dados["pesadas"]) | {i for g in dados["juntas"] for i in g["disciplinas"]}
               | {f["disciplina_id"] for f in dados["fixas"]})
        if ids:
            do_curso = {d.id for d in self._disciplinas.listar_do_curso(curso_id)}
            if ids - do_curso:
                fora = ids - do_curso
                campo = ("pesadas" if set(dados["pesadas"]) & fora else
                         "fixas" if {f["disciplina_id"] for f in dados["fixas"]} & fora else "juntas")
                raise AppError("Há uma disciplina que não pertence a este curso.", 422, {"campo": campo})
        self._repo.salvar(usuario_id, curso_id, dados)
        self.sessao.commit()
        return {"preferencias": dados, "avisos_juntas": self._avisos_juntas(curso_id, dados)}

    def _avisos_juntas(self, curso_id: int, dados: dict) -> list[str]:
        """Por que algum grupo "cursar junto" não tem como ficar junto (o grupo fica guardado, mas é ignorado)."""
        if not dados["juntas"]:
            return []
        from ..domain.juntas import problemas_do_grupo
        from ..domain.preferencias import GrupoJunto
        from .catalogo_dominio import carregar_catalogo
        from .simulacao_json import texto_problema_grupo
        cat = carregar_catalogo(self._disciplinas, curso_id)
        avisos = []
        for g in dados["juntas"]:
            for pr in problemas_do_grupo(GrupoJunto(tuple(g["disciplinas"]), g["regra"]), cat.disciplinas, cat.requisitos):
                avisos.append(texto_problema_grupo(pr, cat.disciplinas) + " O grupo será ignorado até você desfazê-lo.")
        return avisos

"""
Painel do aluno num curso (Etapa 5B-2): situação de cada disciplina, progresso e
previsão de formatura, a partir do histórico DO USUÁRIO.

Só leitura. As regras estão em `domain.painel`; aqui só se carrega e se traduz.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain.painel import montar_painel
from ..repositories import DisciplinaRepository, HistoricoRepository
from .catalogo_dominio import carregar_catalogo, tentativas_do_dominio
from .cursos import CursoService
from .painel_json import serializar_painel


class PainelService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)

    def obter(self, curso_id: int, usuario_id: int) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)     # também valida o acesso
        catalogo = carregar_catalogo(self._disciplinas, curso_id)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        painel = montar_painel(
            list(catalogo.disciplinas.values()), catalogo.requisitos, tentativas,
            curso["creditos_obrigatorios"], curso["creditos_optativos_exigidos"],
            curso["duracao_semestres"],
        )
        return serializar_painel(painel, catalogo.disciplinas)

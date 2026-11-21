"""
Painel do aluno num curso (Etapa 5B-2): situação de cada disciplina, progresso e
previsão de formatura, a partir do histórico DO USUÁRIO.

Só leitura. As regras estão em `domain.painel`; aqui só se carrega e se traduz.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain.historico import aprovadas, cursando
from ..domain.painel import formatura_pelo_plano, montar_painel
from ..repositories import DisciplinaRepository, HistoricoRepository, PlanoRepository
from .catalogo_dominio import carregar_catalogo, tentativas_do_dominio
from .cursos import CursoService
from .painel_json import formatura_plano_json, serializar_painel


class PainelService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)
        self._planos = PlanoRepository(sessao)

    def obter(self, curso_id: int, usuario_id: int, plano_id: int | None = None) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)     # também valida o acesso
        catalogo = carregar_catalogo(self._disciplinas, curso_id)
        tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
        painel = montar_painel(
            list(catalogo.disciplinas.values()), catalogo.requisitos, tentativas,
            curso["creditos_obrigatorios"], curso["creditos_optativos_exigidos"],
            curso["duracao_semestres"],
        )
        saida = serializar_painel(painel, catalogo.disciplinas)
        # formatura pelo plano: o escolhido na tela (se for deste aluno e curso) ou o mais recente
        plano = self._planos.obter_completo_do_usuario(plano_id, usuario_id, curso_id) if plano_id else None
        if plano is None:
            planos = self._planos.listar_completos(usuario_id, curso_id)
            plano = planos[-1] if planos else None
        if plano is None:
            saida["previsao_plano"] = formatura_plano_json(None, None, catalogo.disciplinas)
            return saida
        semestres = [(s.periodo_letivo, [i.disciplina_id for i in s.itens]) for s in plano.semestres]
        fp = formatura_pelo_plano(
            semestres, catalogo.disciplinas, aprovadas(tentativas) | cursando(tentativas),
            curso["creditos_obrigatorios"], curso["creditos_optativos_exigidos"], curso["max_creditos_semestre"],
            painel.primeiro_periodo_livre,
        )
        saida["previsao_plano"] = formatura_plano_json(fp, {"id": plano.id, "nome": plano.nome}, catalogo.disciplinas)
        return saida

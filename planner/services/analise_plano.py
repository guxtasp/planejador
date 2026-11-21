"""
Análise de plano sem estado (Etapa 4B; histórico na 5B-2).

Esta rota apenas JULGA o plano recebido: aplica as regras do domínio e devolve os
problemas. Nada é gravado. Com um usuário logado, o histórico dele entra no
julgamento (aprovadas satisfazem pré-requisitos; cursando satisfaz correquisitos).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import analise as dom
from ..domain.historico import aprovadas, cursando
from ..repositories import DisciplinaRepository, HistoricoRepository
from .analise_json import contar_problemas, ler_payload, serializar_semestre
from .catalogo_dominio import carregar_catalogo, tentativas_do_dominio
from .cursos import CursoService
from .preferencias import PreferenciaService
from .simulacao_json import ler_preferencias


class AnalisePlanoService:
    def __init__(self, sessao: Session | None = None) -> None:
        self._cursos = CursoService(sessao)
        self._disciplinas = DisciplinaRepository(sessao)
        self._historico = HistoricoRepository(sessao)
        self._preferencias = PreferenciaService(sessao)

    def analisar(self, curso_id: int, payload, usuario_id: int | None = None) -> dict:
        curso = self._cursos.obter(curso_id, usuario_id)
        semestres = ler_payload(payload)

        catalogo = carregar_catalogo(self._disciplinas, curso_id, com_turmas=True)

        # Sem usuário (visitante) não há histórico: o plano é julgado "do zero".
        tentativas = []
        semana = None
        junto_com: dict[int, tuple[int, ...]] = {}
        if usuario_id is not None:
            tentativas = tentativas_do_dominio(self._historico.listar_do_usuario(usuario_id, curso_id))
            # a disponibilidade guardada vale aqui também (marca na hora o que não cabe)
            guardadas = self._preferencias.dados(curso_id, usuario_id)
            if guardadas:
                lidas = ler_preferencias({"preferencias": guardadas})
                semana = lidas["semana"]
                for g in lidas["juntas"]:
                    for i in g.disciplinas:
                        junto_com[i] = tuple(sorted(set(junto_com.get(i, ())) | {x for x in g.disciplinas if x != i}))

        analises = dom.analisar_plano(
            semestres, catalogo.disciplinas, catalogo.requisitos, catalogo.turmas,
            curso["max_creditos_semestre"],
            aprovadas=sorted(aprovadas(tentativas)), cursando=sorted(cursando(tentativas)),
            preferencias_semana=semana,
        )
        codigos = {t.id: t.codigo_turma for ts in catalogo.turmas.values() for t in ts}
        checa = bool(semana and semana.indisponiveis)
        return {
            "semestres": [serializar_semestre(a, catalogo.disciplinas, codigos, checa, junto_com) for a in analises],
            "total_problemas": sum(contar_problemas(a) for a in analises),
        }

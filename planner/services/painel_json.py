"""
Formato JSON do painel do aluno (Etapa 5B-2). Sem SQLAlchemy/Flask — testável sem banco.

Desconhecido sai `null` (nunca 0): a tela decide como mostrar.
"""
from __future__ import annotations

from typing import Mapping

from ..domain.entidades import Disciplina
from ..domain.painel import Painel


def _ref(d: Disciplina) -> dict:
    return {"id": d.id, "codigo": d.codigo, "nome": d.nome}


def serializar_painel(painel: Painel, disciplinas: Mapping[int, Disciplina]) -> dict:
    p = painel.progresso
    return {
        "disciplinas": [
            {
                "id": s.disciplina_id,
                "situacao": s.situacao,
                "reprovada_antes": s.reprovada_antes,
                "pendencias": [
                    {
                        "tipo": pend.tipo,
                        "e_alternativa": pend.e_alternativa,
                        "alternativas": [_ref(disciplinas[i]) for i in pend.alternativas if i in disciplinas],
                    }
                    for pend in s.pendencias
                ],
            }
            for s in painel.status
        ],
        "progresso": {
            "percentual": p.percentual,
            "obrigatorios_exigidos": p.obrigatorios_exigidos,
            "obrigatorios_cumpridos": p.obrigatorios_cumpridos,
            "optativos_exigidos": p.optativos_exigidos,
            "optativos_cumpridos": p.optativos_cumpridos,
            "optativos_validos": p.optativos_validos,
            "creditos_validos": p.creditos_validos,
            "creditos_exigidos": p.creditos_exigidos,
            "creditos_restantes": p.creditos_restantes,
            "concluido": p.concluido,
            "disciplinas_sem_creditos": list(p.disciplinas_sem_creditos),
        },
        "resumo": {
            "disciplinas_concluidas": painel.disciplinas_concluidas,
            "total_disciplinas": painel.total_disciplinas,
        },
        "previsao": {
            "formatura": painel.previsao_formatura,
            "semestres_restantes": painel.semestres_restantes,
            "media_creditos_periodo": painel.media_creditos_periodo,
            "origem_media": painel.origem_media,
            "primeiro_periodo_livre": painel.primeiro_periodo_livre,
        },
    }

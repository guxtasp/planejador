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


def formatura_plano_json(fp, plano: dict | None, disciplinas: Mapping[int, Disciplina]) -> dict:
    """Formatura "pelo seu plano", com o texto pronto (o histórico dá a outra data, "pelo seu ritmo")."""
    from ..domain.painel import (SEM_DATA_CREDITOS, SEM_DATA_OBRIGATORIAS, SEM_DATA_PERIODO,
                                 SEM_DATA_PLANO_VAZIO)
    if fp is None:
        return {"plano": None, "formatura": None, "mensagem": "Você ainda não tem um plano. Monte um para ver a data pelo plano."}
    base = {"plano": plano, "periodo_fim": fp.periodo_fim, "formatura": fp.formatura,
            "so_obrigatorias": fp.so_obrigatorias, "formatura_com_optativas": fp.formatura_com_optativas,
            "optativas": {"exigidas": fp.optativas_exigidas, "cumpridas": fp.optativas_cumpridas,
                          "planejadas": fp.optativas_planejadas, "faltam": fp.optativas_faltam},
            "faltam_obrigatorias": [_ref(disciplinas[i]) for i in fp.faltam_obrigatorias if i in disciplinas],
            "sem_data": fp.sem_data}
    nome = plano["nome"] if plano else "plano"
    if fp.sem_data == SEM_DATA_PLANO_VAZIO:
        msg = f"O plano “{nome}” ainda não tem disciplinas."
    elif fp.sem_data == SEM_DATA_PERIODO:
        msg = f"O plano “{nome}” não tem período letivo. Informe o período do 1º semestre para ver a data."
    elif fp.sem_data == SEM_DATA_CREDITOS:
        msg = ("O curso não informa os créditos exigidos e as disciplinas não têm créditos cadastrados "
               "(creditos_obrigatorios em curso.csv ou creditos em disciplinas.csv): não dá para afirmar a "
               f"formatura. O plano vai até {fp.periodo_fim}.")
    elif fp.sem_data == SEM_DATA_OBRIGATORIAS:
        n = len(fp.faltam_obrigatorias)
        msg = f"O plano “{nome}” vai até {fp.periodo_fim}, mas ainda faltam {n} obrigatória{'s' if n > 1 else ''} nele."
    elif fp.optativas_faltam is None:
        msg = (f"Pelo plano “{nome}”, as obrigatórias terminam em {fp.so_obrigatorias}. O curso não informa "
               "quantos créditos de optativas exige (creditos_optativos_exigidos em curso.csv).")
    elif fp.optativas_faltam:
        msg = (f"Pelo plano “{nome}”, as obrigatórias terminam em {fp.so_obrigatorias}. Faltam "
               f"{fp.optativas_faltam} créditos de optativas; com elas, formatura em {fp.formatura_com_optativas}.")
    else:
        msg = f"Pelo plano “{nome}”, formatura em {fp.formatura}."
    return {**base, "mensagem": msg, "cartao": _cartao_plano(fp)}


def _cartao_plano(fp) -> dict:
    """O que o cartão "pelo seu plano" mostra: a melhor data conhecida e, embaixo, do que ela depende."""
    if fp.formatura:
        return {"valor": fp.formatura, "sub": "com tudo que o curso exige"}
    if fp.formatura_com_optativas:
        return {"valor": fp.formatura_com_optativas, "sub": f"contando {fp.optativas_faltam} cr de optativas"}
    if fp.so_obrigatorias:
        return {"valor": fp.so_obrigatorias, "sub": "só obrigatórias (optativas: o curso não informa)"}
    if fp.faltam_obrigatorias:
        n = len(fp.faltam_obrigatorias)
        return {"valor": None, "sub": f"faltam {n} obrigatória{'s' if n > 1 else ''} no plano"}
    return {"valor": None, "sub": None}


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

"""
Rotas do simulador de futuro e da sugestão de plano (Peças 3 e 4). Só traduzem HTTP ⇄ services.
Tudo exige login (usam o histórico do aluno) e nada é gravado, exceto a oferta.

  POST  /api/cursos/<id>/simulacao                      simula o plano enviado, semestre a semestre
  POST  /api/cursos/<id>/simulacao/sugerir              sugere um plano otimizado (grafos + recozimento)
  PATCH /api/cursos/<id>/disciplinas/periodicidade      define a oferta par/ímpar (só o dono do curso)
  GET   /api/cursos/<id>/rotina                         as obrigatórias que faltam cabem nos horários livres?
  GET   /api/cursos/<id>/preferencias                    preferências guardadas do aluno neste curso
  PUT   /api/cursos/<id>/preferencias                    guarda (substitui) as preferências
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.periodicidade import PeriodicidadeService
from ..services.preferencias import PreferenciaService
from ..services.simulacao import SimulacaoService
from .sessao import login_obrigatorio, usuario_atual_id

bp = Blueprint("simulacao", __name__, url_prefix="/api/cursos")


@bp.post("/<int:curso_id>/simulacao")
@login_obrigatorio
def simular(curso_id: int):
    return jsonify({"ok": True, **SimulacaoService().simular(curso_id, usuario_atual_id(), request.get_json(silent=True))})


@bp.post("/<int:curso_id>/simulacao/sugerir")
@login_obrigatorio
def sugerir(curso_id: int):
    return jsonify({"ok": True, **SimulacaoService().sugerir(curso_id, usuario_atual_id(), request.get_json(silent=True))})


@bp.post("/<int:curso_id>/simulacao/optativas")
@login_obrigatorio
def optativas(curso_id: int):
    return jsonify({"ok": True, **SimulacaoService().optativas(curso_id, usuario_atual_id(), request.get_json(silent=True))})


@bp.get("/<int:curso_id>/rotina")
@login_obrigatorio
def rotina(curso_id: int):
    return jsonify({"ok": True, **SimulacaoService().rotina(curso_id, usuario_atual_id())})


@bp.get("/<int:curso_id>/juntas/candidatas")
@login_obrigatorio
def candidatas_juntas(curso_id: int):
    return jsonify({"ok": True, **SimulacaoService().candidatas_juntas(curso_id, usuario_atual_id())})


@bp.get("/<int:curso_id>/preferencias")
@login_obrigatorio
def obter_preferencias(curso_id: int):
    return jsonify({"ok": True, **PreferenciaService().obter(curso_id, usuario_atual_id())})


@bp.put("/<int:curso_id>/preferencias")
@login_obrigatorio
def salvar_preferencias(curso_id: int):
    return jsonify({"ok": True, **PreferenciaService().salvar(curso_id, usuario_atual_id(), request.get_json(silent=True) or {})})


@bp.patch("/<int:curso_id>/disciplinas/periodicidade")
@login_obrigatorio
def definir_periodicidade(curso_id: int):
    return jsonify({"ok": True, **PeriodicidadeService().definir(curso_id, usuario_atual_id(), request.get_json(silent=True))})

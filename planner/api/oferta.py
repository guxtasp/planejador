"""
Rotas da oferta de turmas e da análise de plano (Etapa 4B).

  GET  /api/cursos/<id>/turmas[?periodo=AAAA/N]   turmas, encontros e grade do curso
  POST /api/cursos/<id>/plano/analisar            julga um plano (sem gravar nada)
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.analise_plano import AnalisePlanoService
from ..services.oferta import OfertaService
from .sessao import usuario_atual_id

bp = Blueprint("oferta", __name__, url_prefix="/api/cursos")


@bp.get("/<int:curso_id>/turmas")
def turmas(curso_id: int):
    periodo = request.args.get("periodo") or None
    return jsonify({"ok": True, **OfertaService().listar(curso_id, periodo, usuario_atual_id())})


@bp.post("/<int:curso_id>/plano/analisar")
def analisar(curso_id: int):
    payload = request.get_json(silent=True)
    return jsonify({"ok": True, **AnalisePlanoService().analisar(curso_id, payload, usuario_atual_id())})

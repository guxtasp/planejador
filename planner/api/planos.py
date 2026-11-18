"""
Rotas dos planos de matrícula do aluno (Etapa 5B-2). Só traduzem HTTP ⇄ services.
Tudo exige login e vale só para quem está logado.

  GET    /api/cursos/<id>/planos            planos do aluno neste curso
  POST   /api/cursos/<id>/planos            cria um plano                     (201)
  PUT    /api/cursos/<id>/planos/<pid>      substitui o plano inteiro (nome + semestres)
  DELETE /api/cursos/<id>/planos/<pid>      exclui o plano
A análise (`POST /api/cursos/<id>/plano/analisar`) continua em `oferta.py`.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.planos import PlanoService
from .sessao import login_obrigatorio, usuario_atual_id

bp = Blueprint("planos", __name__, url_prefix="/api/cursos")


@bp.get("/<int:curso_id>/planos")
@login_obrigatorio
def listar(curso_id: int):
    return jsonify({"ok": True, "planos": PlanoService().listar(curso_id, usuario_atual_id())})


@bp.post("/<int:curso_id>/planos")
@login_obrigatorio
def criar(curso_id: int):
    plano = PlanoService().criar(curso_id, usuario_atual_id(), request.get_json(silent=True))
    return jsonify({"ok": True, "plano": plano}), 201


@bp.put("/<int:curso_id>/planos/<int:plano_id>")
@login_obrigatorio
def salvar(curso_id: int, plano_id: int):
    plano = PlanoService().salvar(curso_id, plano_id, usuario_atual_id(), request.get_json(silent=True))
    return jsonify({"ok": True, "plano": plano})


@bp.delete("/<int:curso_id>/planos/<int:plano_id>")
@login_obrigatorio
def excluir(curso_id: int, plano_id: int):
    PlanoService().excluir(curso_id, plano_id, usuario_atual_id())
    return jsonify({"ok": True})

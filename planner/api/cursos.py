"""
Rotas de cursos e do onboarding (Etapa 4A). Só traduzem HTTP ⇄ services.

  GET /api/cursos                         cursos que o visitante pode abrir (públicos + os seus)
  GET /api/cursos/<id>                    dados de um curso
  GET /api/cursos/<id>/disciplinas        curso + catálogo (disciplinas e requisitos)
  DELETE /api/cursos/<id>                 exclui o curso (só o dono) e tudo que depende dele
  GET /                                   onboarding: escolher curso ou trazer um novo
  GET /curso/<id>                         planejador do curso
"""
from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request

from ..services.cursos import CursoService
from .errors import NotFoundError
from .sessao import login_obrigatorio, usuario_atual, usuario_atual_id

bp = Blueprint("cursos", __name__, url_prefix="/api/cursos")
bp_pagina = Blueprint("cursos_pagina", __name__)


@bp.get("")
def listar():
    return jsonify({"ok": True, "cursos": CursoService().listar(usuario_atual_id())})


@bp.get("/<int:curso_id>")
def obter(curso_id: int):
    return jsonify({"ok": True, "curso": CursoService().obter(curso_id, usuario_atual_id())})


@bp.delete("/<int:curso_id>")
@login_obrigatorio
def excluir(curso_id: int):
    CursoService().excluir(curso_id, usuario_atual_id())
    return jsonify({"ok": True})


@bp.get("/<int:curso_id>/disciplinas")
def catalogo(curso_id: int):
    return jsonify({"ok": True, **CursoService().catalogo(curso_id, usuario_atual_id())})


@bp_pagina.get("/")
def inicio():
    return render_template("inicio.html")


@bp_pagina.get("/curso/<int:curso_id>")
def planejador(curso_id: int):
    # Histórico e planos são por conta (5B-2): o planejador exige login, mesmo em curso público.
    if usuario_atual() is None:
        return redirect(f"/entrar?proximo={request.path}")
    try:
        CursoService().obter(curso_id, usuario_atual_id())
    except NotFoundError:
        # Link velho, curso apagado ou curso privado de outra pessoa: de volta ao início.
        # A resposta é a mesma exista o curso ou não, então nada vaza.
        return redirect("/")
    return render_template("index.html", curso_id=curso_id)

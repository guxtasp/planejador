"""
Rotas do histórico escolar e do painel do aluno (Etapa 5B-2). Só traduzem HTTP ⇄ services.
Tudo exige login e vale só para quem está logado.

  GET    /api/cursos/<id>/historico         tentativas do aluno neste curso
  POST   /api/cursos/<id>/historico         registra uma tentativa           (201)
  PUT    /api/cursos/<id>/historico/<hid>   edita status/período/nota
  DELETE /api/cursos/<id>/historico/<hid>   remove a tentativa
  GET    /api/cursos/<id>/painel            status por disciplina, progresso e previsão
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.historico import HistoricoService
from ..services.painel import PainelService
from .sessao import login_obrigatorio, usuario_atual_id

bp = Blueprint("historico", __name__, url_prefix="/api/cursos")


@bp.get("/<int:curso_id>/historico")
@login_obrigatorio
def listar(curso_id: int):
    return jsonify({"ok": True, "historico": HistoricoService().listar(curso_id, usuario_atual_id())})


@bp.post("/<int:curso_id>/historico")
@login_obrigatorio
def criar(curso_id: int):
    tentativa = HistoricoService().criar(curso_id, usuario_atual_id(), request.get_json(silent=True))
    return jsonify({"ok": True, "tentativa": tentativa}), 201


@bp.put("/<int:curso_id>/historico/<int:historico_id>")
@login_obrigatorio
def atualizar(curso_id: int, historico_id: int):
    tentativa = HistoricoService().atualizar(
        curso_id, historico_id, usuario_atual_id(), request.get_json(silent=True))
    return jsonify({"ok": True, "tentativa": tentativa})


@bp.delete("/<int:curso_id>/historico/<int:historico_id>")
@login_obrigatorio
def remover(curso_id: int, historico_id: int):
    HistoricoService().remover(curso_id, historico_id, usuario_atual_id())
    return jsonify({"ok": True})


@bp.post("/<int:curso_id>/historico/colar")
@login_obrigatorio
def colar(curso_id: int):
    """Tabela colada do sistema acadêmico: prévia, ou grava com `{"confirmar": true}`."""
    return jsonify({"ok": True, **HistoricoService().colar(curso_id, usuario_atual_id(), request.get_json(silent=True))})


@bp.get("/<int:curso_id>/painel")
@login_obrigatorio
def painel(curso_id: int):
    # `?plano_id=` = o plano aberto na tela (a formatura "pelo seu plano" usa ele; senão, o mais recente)
    plano_id = request.args.get("plano_id", type=int)
    return jsonify({"ok": True, **PainelService().obter(curso_id, usuario_atual_id(), plano_id)})

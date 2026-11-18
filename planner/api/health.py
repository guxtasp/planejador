"""Endpoint de verificação de saúde (usado por deploy, CI e monitoramento)."""
from flask import Blueprint, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    """Confirma que a aplicação sobe e que o banco responde."""
    db.session.execute(text("SELECT 1"))
    return jsonify({"status": "ok", "database": "ok"})

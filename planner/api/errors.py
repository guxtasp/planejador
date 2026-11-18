"""
Tratamento centralizado de erros da API.

Camadas internas (services/domain) lançam `AppError`; somente aqui o erro vira
resposta HTTP. Assim a regra de negócio não conhece HTTP.
"""
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class AppError(Exception):
    """Erro esperado de negócio/validação, com status HTTP associado."""

    status_code = 400

    def __init__(self, message: str, status_code: int | None = None, details=None):
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code


class NaoAutenticadoError(AppError):
    """Precisa entrar (ter uma sessão) para fazer isto."""

    status_code = 401


class ProibidoError(AppError):
    """Entendido, mas não permitido (ex.: requisição vinda de outro site)."""

    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


def register_error_handlers(app: Flask) -> None:
    """Registra handlers que devolvem sempre JSON no mesmo formato."""

    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        body = {"ok": False, "erro": err.message}
        if err.details is not None:
            body["detalhes"] = err.details
        return jsonify(body), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        return jsonify({"ok": False, "erro": err.description}), err.code

"""Comandos de linha (`flask --app planner <comando>`) para quem administra a instalação."""
from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from .api.errors import AppError
from .services.posse import PosseService


@click.command("reivindicar-cursos")
@click.argument("email")
@with_appcontext
def reivindicar_cursos(email: str) -> None:
    """Atribui a EMAIL todos os cursos sem dono (criados antes do login existir)."""
    try:
        total = PosseService().reivindicar_orfaos(email)
    except AppError as erro:
        raise click.ClickException(erro.message) from erro
    click.echo(f"{total} curso(s) atribuído(s) a {email}.")


def registrar_comandos(app: Flask) -> None:
    app.cli.add_command(reivindicar_cursos)

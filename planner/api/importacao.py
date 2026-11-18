"""
Rotas da importação de CSV (Etapa 3C). Só traduzem HTTP ⇄ services.

  POST /api/importacao/validar    prévia (dry-run), não grava          (exige login)
  POST /api/importacao/confirmar  grava numa transação                 (exige login)
  GET  /api/importacao/modelos[/<arquivo>]   modelos CSV
  GET  /api/importacao/prompt-ia[?fonte=matriz|horarios|web]  prompt para gerar os CSVs com uma IA
  GET  /importar                  tela de importação                   (exige login)

O curso criado pertence a quem importou; só o dono atualiza um curso existente.
Os arquivos vão em multipart/form-data; o nome do arquivo enviado (ex.:
`disciplinas.csv`) identifica o tipo. Campos opcionais: `curso_id`, `visibilidade`.
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, render_template, request

from ..importers.modelos import FONTES, gerar_prompt_ia, listar_fontes, listar_modelos, modelo_csv
from ..services.importacao import ImportacaoService
from ..services.previa_importacao import PreviaImportacaoService
from .errors import AppError, NotFoundError
from .sessao import login_obrigatorio, login_obrigatorio_pagina, usuario_atual_id

bp = Blueprint("importacao", __name__, url_prefix="/api/importacao")
bp_pagina = Blueprint("importacao_pagina", __name__)


def _ler_requisicao() -> tuple[dict[str, bytes], int | None]:
    """Arquivos enviados (`{nome: bytes}`) e o `curso_id` opcional."""
    arquivos = {(f.filename or campo).strip(): f.read() for campo, f in request.files.items()}
    if not arquivos:
        raise AppError("Envie ao menos um arquivo CSV (multipart/form-data).")
    bruto = request.form.get("curso_id", "").strip()
    if bruto and not bruto.isdigit():
        raise AppError("curso_id inválido.")
    return arquivos, int(bruto) if bruto else None


@bp.post("/validar")
@login_obrigatorio
def validar():
    arquivos, curso_id = _ler_requisicao()
    previa = PreviaImportacaoService().gerar(arquivos, curso_id=curso_id, dono_id=usuario_atual_id())
    return jsonify({"ok": True, "previa": previa.para_dict()})


@bp.post("/confirmar")
@login_obrigatorio
def confirmar():
    arquivos, curso_id = _ler_requisicao()
    visibilidade = request.form.get("visibilidade", "").strip() or None
    relatorio = ImportacaoService().confirmar(
        arquivos, curso_id=curso_id, dono_id=usuario_atual_id(), visibilidade=visibilidade)
    return jsonify({"ok": True, "relatorio": relatorio.para_dict()}), 201 if relatorio.curso_criado else 200


@bp.get("/modelos")
def modelos():
    return jsonify({"ok": True, "modelos": listar_modelos()})


@bp.get("/modelos/<arquivo>")
def baixar_modelo(arquivo: str):
    if arquivo not in listar_modelos():
        raise NotFoundError(f"Não há modelo '{arquivo}'. Disponíveis: {', '.join(listar_modelos())}.")
    # BOM: o Excel abre acentos corretamente.
    conteudo = "﻿" + modelo_csv(arquivo)
    return Response(conteudo, mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


@bp.get("/prompt-ia")
def prompt_ia():
    """`?fonte=matriz|horarios|web` (padrão: matriz)."""
    fonte = request.args.get("fonte", "matriz")
    if fonte not in FONTES:
        raise AppError(f"Fonte inválida: '{fonte}'. Use uma destas: {', '.join(listar_fontes())}.")
    return jsonify({"ok": True, "fonte": fonte, "prompt": gerar_prompt_ia(fonte)})


@bp_pagina.get("/importar")
@login_obrigatorio_pagina
def pagina():
    return render_template("importacao.html")

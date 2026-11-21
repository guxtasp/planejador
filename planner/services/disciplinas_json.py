"""
JSON da edição de disciplinas: lê o que a tela manda e devolve a disciplina pronta para a tela.

Campo desconhecido continua `null` (nunca vira 0). Erros dizem qual campo está errado
(`detalhes.campo`), para a tela mostrar a mensagem junto dele.
"""
from __future__ import annotations

from typing import Mapping

from ..api.errors import AppError
from ..models.enums import TipoDisciplina

TIPOS = {t.value for t in TipoDisciplina}
OFERTAS = {"impar", "par", "sempre"}
MAX_REQUISITOS = 30


def _erro(msg: str, campo: str) -> AppError:
    return AppError(msg, 422, {"campo": campo})


def _texto(valor, campo: str, rotulo: str, maximo: int) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise _erro(f"Preencha {rotulo}.", campo)
    valor = " ".join(valor.split())
    if len(valor) > maximo:
        raise _erro(f"{rotulo[0].upper() + rotulo[1:]} pode ter no máximo {maximo} caracteres.", campo)
    return valor


def _inteiro(valor, campo: str, rotulo: str, minimo: int, maximo: int) -> int | None:
    if valor is None or valor == "":
        return None                                    # em branco = não informado
    if isinstance(valor, str) and valor.strip().isdigit():
        valor = int(valor.strip())
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise _erro(f"{rotulo}: use um número inteiro de {minimo} a {maximo}, ou deixe em branco.", campo)
    return valor


def ler_disciplina(payload, *, nova: bool) -> dict:
    """
    Campos enviados, já validados. Na edição só muda o que veio; na criação código e nome
    são obrigatórios. `requisitos` substitui a lista inteira:
    `[{"id": 3, "tipo": "pre"|"co", "grupo_alt": null|"A"}]`.
    """
    if not isinstance(payload, dict):
        raise AppError("Envie os dados da disciplina.", 422)
    saida: dict = {}
    if nova or "codigo" in payload:
        saida["codigo"] = _texto(payload.get("codigo"), "codigo", "o código", 30).replace(" ", "")
    if nova or "nome" in payload:
        saida["nome"] = _texto(payload.get("nome"), "nome", "o nome", 200)
    if "creditos" in payload:
        saida["creditos"] = _inteiro(payload["creditos"], "creditos", "Créditos", 0, 60)
    if "carga_h" in payload:
        saida["carga_h"] = _inteiro(payload["carga_h"], "carga_h", "Carga horária", 0, 2000)
    if "periodo_sugerido" in payload:
        saida["periodo_sugerido"] = _inteiro(payload["periodo_sugerido"], "periodo_sugerido", "Período", 1, 20)
    if nova or "tipo" in payload:
        tipo = payload.get("tipo") or TipoDisciplina.OBRIGATORIA.value
        if tipo not in TIPOS:
            raise _erro("Tipo inválido: use obrigatória, optativa ou eletiva.", "tipo")
        saida["tipo"] = tipo
    if "periodicidade" in payload:
        oferta = payload["periodicidade"] or None
        if oferta is not None and oferta not in OFERTAS:
            raise _erro("Oferta inválida: use ímpar, par, sempre ou não informada.", "periodicidade")
        saida["periodicidade"] = oferta
    if "conta_no_limite" in payload:
        if not isinstance(payload["conta_no_limite"], bool):
            raise _erro("Conta no limite de créditos: sim ou não.", "conta_no_limite")
        saida["conta_no_limite"] = payload["conta_no_limite"]
    if "requisitos" in payload:
        saida["requisitos"] = _requisitos(payload["requisitos"])
    if not saida:
        raise AppError("Nada para alterar.", 422)
    return saida


def _requisitos(bruto) -> list[tuple[int, str, str | None]]:
    if not isinstance(bruto, list) or len(bruto) > MAX_REQUISITOS:
        raise _erro(f"Requisitos: no máximo {MAX_REQUISITOS}.", "requisitos")
    vistos: dict[tuple[int, str], str | None] = {}
    for r in bruto:
        rid = r.get("id") if isinstance(r, dict) else None
        tipo = r.get("tipo") if isinstance(r, dict) else None
        grupo = r.get("grupo_alt") if isinstance(r, dict) else None
        if isinstance(rid, bool) or not isinstance(rid, int):
            raise _erro("Escolha a disciplina do requisito.", "requisitos")
        if tipo not in ("pre", "co"):
            raise _erro("Requisito: o tipo é pré ou correquisito.", "requisitos")
        if grupo is not None and (not isinstance(grupo, str) or len(grupo) > 30):
            raise _erro("Requisito: grupo de alternativas inválido.", "requisitos")
        vistos[(rid, tipo)] = (grupo or "").strip() or None      # repetido conta uma vez
    return [(rid, tipo, g) for (rid, tipo), g in vistos.items()]


def disciplina_json(d, por_id: Mapping[int, object], oferta: dict) -> dict:
    """Uma disciplina do catálogo, no formato da tela (o mesmo do `GET …/disciplinas`)."""
    return {
        "id": d.id, "codigo": d.codigo, "nome": d.nome, "tipo": d.tipo,
        "creditos": d.creditos, "carga_h": d.carga_h,
        "periodo_sugerido": d.periodo_sugerido, "cor": d.cor,
        "periodicidade": d.periodicidade,
        "conta_no_limite": d.conta_no_limite is not False,
        # o que o motor assume (cadastrada, estimada pelo período sugerido ou desconhecida):
        # é a mesma regra do simulador, e a tela usa para o selo par/ímpar em todo lugar
        "oferta": oferta,
        "requisitos": [
            {"id": r.requisito_id, "codigo": por_id[r.requisito_id].codigo,
             "nome": por_id[r.requisito_id].nome, "tipo": r.tipo, "grupo_alt": r.grupo_alt}
            for r in d.requisitos if r.requisito_id in por_id
        ],
    }

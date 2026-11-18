"""
Pipeline de validação (padrão Chain): leituras da 3A → estágios → prévia.

    duplicatas → referencial → semântico → prévia

A ordem importa: primeiro tiram-se as repetições, depois confere-se quem
referencia quem (e normalizam-se os códigos), e só então as regras de negócio
olham para dados já consistentes.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from ..base import ResultadoLeitura
from .contexto import ContextoValidacao
from .duplicatas import EstagioDuplicatas
from .estado import EstadoExistente
from .estagio import Estagio
from .previa import ImportPreview, montar_previa
from .referencial import EstagioReferencial
from .semantico import EstagioSemantico


def estagios_padrao() -> tuple[Estagio, ...]:
    return (EstagioDuplicatas(), EstagioReferencial(), EstagioSemantico())


def gerar_previa(
    leituras: Mapping[str, ResultadoLeitura],
    estado: EstadoExistente | None = None,
    estagios: Sequence[Estagio] | None = None,
) -> ImportPreview:
    """
    Valida os arquivos já lidos (3A) contra o estado do curso e devolve a prévia.

    `leituras` é `{nome_do_arquivo: ResultadoLeitura}` e pode conter só alguns
    dos cinco arquivos. Nada é gravado e as leituras recebidas não são alteradas.
    """
    ctx = ContextoValidacao(leituras, estado or EstadoExistente())
    for estagio in (estagios if estagios is not None else estagios_padrao()):
        estagio.executar(ctx)
    return montar_previa(ctx)

"""
Estágio 1 — duplicatas DENTRO dos arquivos enviados.

Duplicata contra o banco não é erro: a chave natural identifica o registro e
a importação é um upsert (o que já existe aparece como "a atualizar" ou
"inalterado" na prévia). Aqui só tratamos a mesma chave repetida no arquivo:

  * linha idêntica à anterior → AVISO, a repetição é ignorada (sem perda);
  * mesma chave com valores diferentes → ERRO na repetição (qual vale?);
    a primeira ocorrência é mantida.

No histórico não há chave natural (reprovar duas vezes é legítimo): linhas
idênticas só geram aviso e ficam.
"""
from __future__ import annotations

from dataclasses import fields
from typing import Callable

from ..leitor_csv import normalizar
from .contexto import ContextoValidacao, chave
from .estagio import Estagio

# arquivo → (função que extrai a chave natural, coluna citada na mensagem, rótulo)
_CHAVES: dict[str, tuple[Callable, str | None, str]] = {
    "disciplinas.csv": (lambda r: (chave(r.codigo),), "codigo", "Disciplina {0}"),
    "requisitos.csv": (lambda r: (chave(r.disciplina), chave(r.requisito), r.tipo), None,
                       "Requisito {0} → {1} ({2})"),
    "turmas.csv": (lambda r: (chave(r.disciplina), r.periodo_letivo, chave(r.codigo_turma)), None,
                   "Turma {0} · {1} · {2}"),
}


def _conteudo(registro) -> tuple:
    """Valores do registro sem o número da linha e sem diferenças de caixa/acento."""
    return tuple(
        normalizar(v) if isinstance(v, str) else v
        for f in fields(registro) if f.name != "linha"
        for v in [getattr(registro, f.name)]
    )


class EstagioDuplicatas(Estagio):
    nome = "duplicatas"

    def executar(self, ctx: ContextoValidacao) -> None:
        for arquivo, (extrair, coluna, rotulo) in _CHAVES.items():
            vistos: dict[tuple, object] = {}
            descartar: set[int] = set()
            for r in ctx.ativos(arquivo):
                k = extrair(r)
                primeiro = vistos.setdefault(k, r)
                if primeiro is r:
                    continue
                descartar.add(r.linha)
                nome = rotulo.format(*[getattr(r, c) for c in self._campos(arquivo)])
                if _conteudo(primeiro) == _conteudo(r):
                    ctx.aviso(arquivo, r.linha, coluna,
                              f"{nome} repetida (idêntica à linha {primeiro.linha}): ignorada.")
                else:
                    ctx.erro(arquivo, r.linha, coluna,
                             f"{nome} aparece de novo com valores diferentes dos da linha "
                             f"{primeiro.linha}. Deixe só uma.")
            ctx.descartar(arquivo, descartar)

    @staticmethod
    def _campos(arquivo: str) -> tuple[str, ...]:
        return {"disciplinas.csv": ("codigo",), "requisitos.csv": ("disciplina", "requisito", "tipo"),
                "turmas.csv": ("disciplina", "periodo_letivo", "codigo_turma")}[arquivo]

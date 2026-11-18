"""
Estágio 2 — integridade referencial.

Monta o catálogo (disciplinas já no banco + as do `disciplinas.csv`) e confere
que requisitos, turmas e histórico só apontam para disciplinas que existem
NESTE curso. Isso também impede, por construção, requisito para disciplina de
outro curso (pendência da Etapa 1A). Referência quebrada = ERRO e descarta a linha.

Como os códigos são comparados sem caixa/acento, os registros saem daqui com o
código escrito EXATAMENTE como no catálogo ('inf110' vira 'INF110'): o commit
da 3C não precisa repetir a normalização.
"""
from __future__ import annotations

from .contexto import ContextoValidacao, chave, com_codigo
from .estagio import Estagio

# arquivo → colunas que contêm códigos de disciplina
_REFERENCIAS = {
    "requisitos.csv": ("disciplina", "requisito"),
    "turmas.csv": ("disciplina",),
}


class EstagioReferencial(Estagio):
    nome = "referencial"

    def executar(self, ctx: ContextoValidacao) -> None:
        self._montar_catalogo(ctx)
        for arquivo, colunas in _REFERENCIAS.items():
            self._resolver(ctx, arquivo, colunas)

    @staticmethod
    def _montar_catalogo(ctx: ContextoValidacao) -> None:
        # Banco primeiro (ordenado, para o resultado não depender da ordem das consultas).
        for d in sorted(ctx.estado.disciplinas, key=lambda d: d.codigo):
            ctx.catalogo.setdefault(chave(d.codigo), d.codigo)

        def ajustar(registro):
            existente = ctx.catalogo.setdefault(chave(registro.codigo), registro.codigo)
            if existente != registro.codigo:
                # O banco só aceita 'INF110' OU 'inf110' (UNIQUE por caixa); mantemos o já gravado.
                ctx.aviso("disciplinas.csv", registro.linha, "codigo",
                          f"'{registro.codigo}' é a disciplina já cadastrada como '{existente}' "
                          "(só a caixa difere): será tratada como a mesma.")
            return com_codigo(registro, "codigo", existente)

        ctx.transformar("disciplinas.csv", ajustar)

    @staticmethod
    def _resolver(ctx: ContextoValidacao, arquivo: str, colunas: tuple[str, ...]) -> None:
        if arquivo not in ctx.registros:
            return
        descartar: set[int] = set()
        corrigidos = []
        for r in ctx.ativos(arquivo):
            novo = r
            for coluna in colunas:
                codigo = getattr(r, coluna)
                canonico = ctx.canonico(codigo)
                if canonico is None:
                    descartar.add(r.linha)
                    ctx.erro(arquivo, r.linha, coluna, _mensagem_inexistente(ctx, codigo))
                else:
                    novo = com_codigo(novo, coluna, canonico)
            corrigidos.append(novo)
        ctx.registros[arquivo] = corrigidos
        ctx.descartar(arquivo, descartar)


def _mensagem_inexistente(ctx: ContextoValidacao, codigo: str) -> str:
    texto = (f"Disciplina '{codigo}' não existe neste curso "
             "(nem em disciplinas.csv, nem no catálogo já cadastrado).")
    if "disciplinas.csv" in ctx.com_erro_de_schema:
        texto += " Corrija antes os erros de disciplinas.csv: ela pode ter sido descartada."
    return texto

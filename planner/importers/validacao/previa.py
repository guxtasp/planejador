"""
`ImportPreview`: o que a importação FARIA, sem gravar nada (dry-run).

Para cada arquivo, cada linha válida vira um `ItemPrevia` com a ação:
  * `novo`       — não existe no curso;
  * `atualizar`  — existe e o arquivo traz valor diferente (`mudancas` lista antes → depois);
  * `inalterado` — existe e já é igual.

Regra do upsert (decisão registrada em PROGRESSO.md): célula VAZIA no CSV
significa "não sei", então NUNCA apaga um valor já conhecido no banco; e o que
está no banco mas não aparece no arquivo é mantido (a importação não remove).

Chaves naturais: curso = nome; disciplina = código; requisito = (disciplina,
requisito, tipo); turma = (disciplina, período, código da turma). O histórico
não tem chave natural nem usuário nesta etapa: toda linha válida aparece como `novo`.

A prévia é determinística: mesma entrada → mesma saída, byte a byte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ...domain.entidades import Encontro
from ..base import Issue, Severidade
from .contexto import ORDEM_ARQUIVOS, ContextoValidacao, chave as _norm

NOVO, ATUALIZAR, INALTERADO = "novo", "atualizar", "inalterado"


@dataclass(frozen=True)
class Mudanca:
    campo: str
    antes: Any
    depois: Any

    def para_dict(self) -> dict[str, Any]:
        return {"campo": self.campo, "antes": self.antes, "depois": self.depois}


@dataclass(frozen=True)
class ItemPrevia:
    arquivo: str
    linha: int
    chave: str            # texto legível, ex.: "INF112 ← INF110 (pre)"
    acao: str
    mudancas: tuple[Mudanca, ...] = ()

    def para_dict(self) -> dict[str, Any]:
        return {"arquivo": self.arquivo, "linha": self.linha, "chave": self.chave,
                "acao": self.acao, "mudancas": [m.para_dict() for m in self.mudancas]}


@dataclass(frozen=True)
class PreviaArquivo:
    arquivo: str
    linhas_lidas: int
    itens: tuple[ItemPrevia, ...]
    mantidos_no_banco: int   # já existiam e não aparecem neste arquivo (não são tocados)
    erros: int
    avisos: int

    def _contar(self, acao: str) -> int:
        return sum(1 for i in self.itens if i.acao == acao)

    @property
    def novos(self) -> int:
        return self._contar(NOVO)

    @property
    def a_atualizar(self) -> int:
        return self._contar(ATUALIZAR)

    @property
    def inalterados(self) -> int:
        return self._contar(INALTERADO)

    @property
    def descartadas(self) -> int:
        """Linhas lidas que não entram na importação (erro ou repetição ignorada)."""
        return self.linhas_lidas - len(self.itens)

    def para_dict(self) -> dict[str, Any]:
        return {"arquivo": self.arquivo, "linhas_lidas": self.linhas_lidas, "novos": self.novos,
                "a_atualizar": self.a_atualizar, "inalterados": self.inalterados,
                "descartadas": self.descartadas, "mantidos_no_banco": self.mantidos_no_banco,
                "erros": self.erros, "avisos": self.avisos,
                "itens": [i.para_dict() for i in self.itens]}


@dataclass(frozen=True)
class ImportPreview:
    """Resultado completo do dry-run. `registros` é o que a 3C gravará (não vai para o JSON)."""

    arquivos: tuple[PreviaArquivo, ...]
    issues: tuple[Issue, ...]
    registros: Mapping[str, tuple] = field(default_factory=dict, repr=False, compare=False)

    @property
    def erros(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severidade is Severidade.ERRO)

    @property
    def avisos(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severidade is Severidade.AVISO)

    def _somar(self, atributo: str) -> int:
        return sum(getattr(a, atributo) for a in self.arquivos)

    @property
    def novos(self) -> int:
        return self._somar("novos")

    @property
    def a_atualizar(self) -> int:
        return self._somar("a_atualizar")

    @property
    def inalterados(self) -> int:
        return self._somar("inalterados")

    @property
    def pode_confirmar(self) -> bool:
        """Só há o que confirmar se NÃO houver erro (tudo-ou-nada) e algo a gravar."""
        return not self.erros and (self.novos + self.a_atualizar) > 0

    def para_dict(self) -> dict[str, Any]:
        """Formato JSON da API e da tela de prévia (3C)."""
        return {
            "pode_confirmar": self.pode_confirmar,
            "totais": {"novos": self.novos, "a_atualizar": self.a_atualizar,
                       "inalterados": self.inalterados, "erros": len(self.erros),
                       "avisos": len(self.avisos)},
            "arquivos": [a.para_dict() for a in self.arquivos],
            "issues": [i.para_dict() for i in self.issues],
        }


# ── diff ─────────────────────────────────────────────────────────────────
def _txt_encontros(encontros: tuple[Encontro, ...]) -> str:
    ordenados = sorted(encontros, key=lambda e: (e.dia, e.inicio, e.fim))
    return " | ".join(f"{e.dia} {e.inicio:%H:%M}-{e.fim:%H:%M}" for e in ordenados)


def _valor(valor: Any) -> Any:
    """Valor simples (JSON): encontros e dias viram texto."""
    if isinstance(valor, tuple) and valor and isinstance(valor[0], Encontro):
        return _txt_encontros(valor)
    if isinstance(valor, tuple):
        return "|".join(valor) if valor else None
    return valor


def _mudancas(novo, existente, campos: tuple[str, ...]) -> tuple[Mudanca, ...]:
    """Campos em que o arquivo traz valor (não vazio) diferente do gravado."""
    resultado = []
    for campo in campos:
        depois, antes = getattr(novo, campo), getattr(existente, campo)
        if depois in (None, ()) or _valor(depois) == _valor(antes):
            continue
        resultado.append(Mudanca(campo, _valor(antes), _valor(depois)))
    return tuple(resultado)


@dataclass(frozen=True)
class _Tipo:
    """Como comparar um arquivo: chave natural, texto legível e campos que contam no diff."""

    chave: Callable[[Any], tuple]
    rotulo: Callable[[Any], str]
    campos: tuple[str, ...]
    existentes: Callable[[ContextoValidacao], list]


_TIPOS: dict[str, _Tipo] = {
    "curso.csv": _Tipo(
        chave=lambda r: (_norm(r.nome),),
        rotulo=lambda r: r.nome,
        campos=("nome", "instituicao", "versao_matriz", "creditos_obrigatorios",
                "creditos_optativos_exigidos", "ch_total", "max_creditos_semestre",
                "duracao_semestres", "dias_letivos"),
        existentes=lambda ctx: [ctx.estado.curso] if ctx.estado.curso else [],
    ),
    "disciplinas.csv": _Tipo(
        chave=lambda r: (_norm(r.codigo),),
        rotulo=lambda r: r.codigo,
        campos=("nome", "tipo", "creditos", "carga_h", "periodo_sugerido", "cor", "periodicidade"),
        existentes=lambda ctx: list(ctx.estado.disciplinas),
    ),
    "requisitos.csv": _Tipo(
        chave=lambda r: (_norm(r.disciplina), _norm(r.requisito), r.tipo),
        rotulo=lambda r: f"{r.disciplina} ← {r.requisito} ({r.tipo})",
        campos=("grupo_alt",),
        existentes=lambda ctx: list(ctx.estado.requisitos),
    ),
    "turmas.csv": _Tipo(
        chave=lambda r: (_norm(r.disciplina), r.periodo_letivo, _norm(r.codigo_turma)),
        rotulo=lambda r: f"{r.disciplina} · {r.periodo_letivo} · {r.codigo_turma}",
        campos=("docente", "vagas", "encontros", "local", "componente"),
        existentes=lambda ctx: list(ctx.estado.turmas),
    ),
}


def _previa_do_arquivo(ctx: ContextoValidacao, arquivo: str) -> PreviaArquivo:
    registros = ctx.ativos(arquivo)
    itens: list[ItemPrevia] = []
    if arquivo in _TIPOS:
        tipo = _TIPOS[arquivo]
        no_banco = {tipo.chave(e): e for e in tipo.existentes(ctx)}
        tocados = set()
        for r in sorted(registros, key=lambda r: r.linha):
            k = tipo.chave(r)
            existente = no_banco.get(k)
            if existente is None and arquivo == "curso.csv" and no_banco:
                existente = next(iter(no_banco.values()))  # curso alvo já escolhido: o nome pode mudar
                k = tipo.chave(existente)
            tocados.add(k)
            if existente is None:
                itens.append(ItemPrevia(arquivo, r.linha, tipo.rotulo(r), NOVO))
                continue
            mudancas = _mudancas(r, existente, tipo.campos)
            itens.append(ItemPrevia(arquivo, r.linha, tipo.rotulo(r),
                                    ATUALIZAR if mudancas else INALTERADO, mudancas))
        mantidos = len([k for k in no_banco if k not in tocados])
    else:  # arquivo sem tipo de upsert registrado: nada a comparar
        mantidos = 0
    deste = [i for i in ctx.issues if i.arquivo == arquivo]
    return PreviaArquivo(
        arquivo=arquivo, linhas_lidas=ctx.linhas_lidas[arquivo], itens=tuple(itens),
        mantidos_no_banco=mantidos,
        erros=sum(i.severidade is Severidade.ERRO for i in deste),
        avisos=sum(i.severidade is Severidade.AVISO for i in deste),
    )


def _ordem_issue(i: Issue) -> tuple:
    return (ORDEM_ARQUIVOS.index(i.arquivo) if i.arquivo in ORDEM_ARQUIVOS else len(ORDEM_ARQUIVOS),
            i.arquivo, i.linha or 0, i.coluna or "", i.severidade is not Severidade.ERRO, i.mensagem)


def montar_previa(ctx: ContextoValidacao) -> ImportPreview:
    """Converte o contexto já validado na prévia final (issues ordenadas, sem duplicatas)."""
    issues = tuple(sorted(dict.fromkeys(ctx.issues), key=_ordem_issue))
    return ImportPreview(
        arquivos=tuple(_previa_do_arquivo(ctx, a) for a in ctx.arquivos),
        issues=issues,
        registros={a: tuple(ctx.ativos(a)) for a in ctx.arquivos},
    )

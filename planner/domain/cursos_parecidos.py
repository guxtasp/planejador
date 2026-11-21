"""
"Este curso já existe?" — candidatos a receber uma importação, para não duplicar curso.

Antes, o curso era achado pelo nome EXATO de curso.csv: um acento, uma maiúscula ou um
"Bacharelado em" a mais criavam um curso novo. Agora há dois sinais, cada um suficiente:

  * NOME normalizado (sem acento, minúsculo, sem pontuação, espaços colapsados, sem o grau
    "bacharelado em / licenciatura em / curso de…") igual — e a instituição também igual quando
    as duas forem conhecidas (instituição vazia = desconhecida, não atrapalha);
  * DISCIPLINAS: pelo menos `LIMIAR_CODIGOS` (60%) dos códigos enviados já existem no curso.

Esta função só aponta candidatos. Quem decide é a pessoa ("atualizar X" ou "criar novo"):
nunca se cria nem se junta em silêncio. Quem chama passa só cursos do próprio dono.
Função pura, só stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Collection, Iterable

LIMIAR_CODIGOS = 0.6
_GRAUS = ("bacharelado em ", "bacharelado ", "licenciatura em ", "licenciatura ", "graduacao em ",
          "curso de ", "curso superior de ", "tecnologia em ")

MOTIVO_NOME = "nome"
MOTIVO_DISCIPLINAS = "disciplinas"
MOTIVO_AMBOS = "nome_e_disciplinas"


def normalizar_texto(texto: str | None) -> str:
    """'  Ciência   da Computação! ' → 'ciencia da computacao'."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    so_letras = re.sub(r"[^a-z0-9]+", " ", sem_acento.lower())
    return " ".join(so_letras.split())


def normalizar_nome_curso(nome: str | None) -> str:
    """Nome normalizado e sem o grau ("Bacharelado em Ciência da Computação" → "ciencia da computacao")."""
    n = normalizar_texto(nome)
    mudou = True
    while mudou:
        mudou = False
        for g in _GRAUS:
            if n.startswith(g):
                n, mudou = n[len(g):], True
    return n


def normalizar_codigo(codigo: str) -> str:
    return re.sub(r"\s+", "", codigo or "").upper()


@dataclass(frozen=True)
class CursoConhecido:
    id: int
    nome: str
    instituicao: str | None
    codigos: frozenset[str]


@dataclass(frozen=True)
class Candidato:
    curso_id: int
    nome: str
    motivo: str               # nome | disciplinas | nome_e_disciplinas
    em_comum: int             # códigos enviados que já existem no curso
    enviados: int             # códigos enviados
    no_curso: int             # disciplinas que o curso tem hoje


def candidatos_a_atualizar(
    nome: str | None,
    instituicao: str | None,
    codigos: Collection[str],
    cursos: Iterable[CursoConhecido],
    limiar: float = LIMIAR_CODIGOS,
) -> tuple[Candidato, ...]:
    """Cursos (já filtrados pelo dono) que parecem ser o mesmo da importação, do mais parecido ao menos."""
    alvo_nome = normalizar_nome_curso(nome)
    alvo_inst = normalizar_texto(instituicao)
    enviados = {normalizar_codigo(c) for c in codigos if c}
    saida = []
    for c in cursos:
        inst = normalizar_texto(c.instituicao)
        mesmo_nome = bool(alvo_nome) and normalizar_nome_curso(c.nome) == alvo_nome and \
            (not alvo_inst or not inst or alvo_inst == inst)
        existentes = {normalizar_codigo(x) for x in c.codigos}
        comum = len(enviados & existentes)
        mesmas_disciplinas = bool(enviados) and comum / len(enviados) >= limiar
        if not (mesmo_nome or mesmas_disciplinas):
            continue
        motivo = MOTIVO_AMBOS if mesmo_nome and mesmas_disciplinas else (MOTIVO_NOME if mesmo_nome else MOTIVO_DISCIPLINAS)
        saida.append(Candidato(c.id, c.nome, motivo, comum, len(enviados), len(existentes)))
    saida.sort(key=lambda x: (x.motivo != MOTIVO_AMBOS, -x.em_comum, x.curso_id))
    return tuple(saida)

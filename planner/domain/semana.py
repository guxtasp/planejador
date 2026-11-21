"""
A semana do aluno: preferências de horário e o quanto uma grade as respeita.

Usado pela alocação de turmas (`alocacao`) como critério SECUNDÁRIO (colisão entre disciplinas
continua dominante) e, depois, pelas métricas de semana do simulador.

  * `BlocoIndisponivel`   dia + faixa em que o aluno não pode ter aula (trabalho, estágio, transporte);
  * `PreferenciasSemana`  blocos indisponíveis, turno preferido, dias que quer livres e os pesos;
  * `penalidade`          custo de uma grade (encontros) frente às preferências; 0 = perfeita;
  * `janelas_horas`       horas de "buraco" entre aulas no mesmo dia.

Sem preferências (`None`), nada é penalizado: quem chama mantém o comportamento de antes.
Função pura, só stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Iterable, Mapping, Sequence

from .entidades import Encontro

TURNO_MANHA, TURNO_TARDE, TURNO_NOITE = "manha", "tarde", "noite"
TURNOS = (TURNO_MANHA, TURNO_TARDE, TURNO_NOITE)
_FIM_MANHA, _FIM_TARDE = 12 * 60, 18 * 60       # um encontro é do turno em que COMEÇA


@dataclass(frozen=True)
class BlocoIndisponivel:
    dia: str          # SEG … DOM (mesmo vocabulário dos encontros)
    inicio: time
    fim: time
    motivo: str | None = None   # "trabalho", "estágio"… só para a tela


@dataclass(frozen=True)
class PreferenciasSemana:
    indisponiveis: tuple[BlocoIndisponivel, ...] = ()
    turno: str | None = None              # manha | tarde | noite
    dias_livres: tuple[str, ...] = ()     # dias em que prefere não ter aula
    peso_indisponivel: float = 10.0       # por encontro que bate num bloco indisponível
    peso_janela: float = 1.0              # por hora de buraco entre aulas no mesmo dia
    peso_dia: float = 2.0                 # por dia com aula
    peso_turno: float = 1.0               # por encontro fora do turno preferido
    peso_dia_livre: float = 5.0           # por dia "livre" que ganhou aula


def _min(t: time) -> int:
    return t.hour * 60 + t.minute


def turno_do(e: Encontro) -> str:
    inicio = _min(e.inicio)
    return TURNO_MANHA if inicio < _FIM_MANHA else (TURNO_TARDE if inicio < _FIM_TARDE else TURNO_NOITE)


def bate_indisponivel(e: Encontro, blocos: Iterable[BlocoIndisponivel]) -> bool:
    """O encontro cruza algum bloco indisponível (tocar na borda não conta, como nos conflitos)."""
    return any(b.dia == e.dia and e.inicio < b.fim and e.fim > b.inicio for b in blocos)


def janelas_horas(encontros: Iterable[Encontro]) -> float:
    """Horas vazias entre aulas do mesmo dia (encontros sobrepostos se fundem)."""
    por_dia: dict[str, list[tuple[int, int]]] = {}
    for e in encontros:
        por_dia.setdefault(e.dia, []).append((_min(e.inicio), _min(e.fim)))
    total = 0
    for faixas in por_dia.values():
        faixas.sort()
        fim = faixas[0][1]
        for ini, f in faixas[1:]:
            if ini > fim:
                total += ini - fim
            fim = max(fim, f)
    return total / 60


def dias_com_aula(encontros: Iterable[Encontro]) -> frozenset[str]:
    return frozenset(e.dia for e in encontros)


def penalidade_monotona(encontros: Sequence[Encontro], p: PreferenciasSemana) -> float:
    """
    Parte da penalidade que só cresce quando se acrescentam encontros (indisponível, turno, dias):
    serve de limite inferior seguro para a poda do branch & bound. Janelas ficam de fora, pois um
    encontro novo pode TAPAR um buraco.
    """
    bloq = sum(1 for e in encontros if bate_indisponivel(e, p.indisponiveis))
    fora = sum(1 for e in encontros if p.turno and turno_do(e) != p.turno)
    dias = dias_com_aula(encontros)
    livres_ocupados = len(dias & set(p.dias_livres))
    return (p.peso_indisponivel * bloq + p.peso_turno * fora + p.peso_dia * len(dias)
            + p.peso_dia_livre * livres_ocupados)


def penalidade(encontros: Sequence[Encontro], p: PreferenciasSemana | None) -> float:
    """Custo da grade frente às preferências (0 sem preferências)."""
    if p is None or not encontros:
        return 0.0
    return penalidade_monotona(encontros, p) + p.peso_janela * janelas_horas(encontros)


DIAS_UTEIS = ("SEG", "TER", "QUA", "QUI", "SEX")


@dataclass(frozen=True)
class MetricasSemana:
    """Como fica a semana de um semestre com as turmas escolhidas."""

    horas_aula: float
    dias_com_aula: tuple[str, ...]
    dias_livres: tuple[str, ...]          # entre os dias de referência (`dias_base`)
    janelas_horas: float
    choques_indisponiveis: int            # encontros que batem num bloco indisponível
    aulas_em_dias_livres: tuple[str, ...] # dias que a pessoa queria livres e têm aula
    fora_do_turno: int                    # encontros fora do turno preferido
    completo: bool                        # todas as disciplinas tinham horário conhecido


def metricas_semana(
    encontros: Sequence[Encontro],
    preferencias: PreferenciasSemana | None = None,
    dias_base: Sequence[str] = DIAS_UTEIS,
    completo: bool = True,
) -> MetricasSemana:
    """Horas em aula, dias livres, janelas e o que bate com as preferências. Só com os horários conhecidos."""
    p = preferencias or PreferenciasSemana()
    dias = dias_com_aula(encontros)
    ordem = {d: k for k, d in enumerate(("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"))}
    em_ordem = lambda xs: tuple(sorted(xs, key=lambda d: ordem.get(d, 9)))
    horas = sum(_min(e.fim) - _min(e.inicio) for e in encontros) / 60
    return MetricasSemana(
        horas_aula=round(horas, 1),
        dias_com_aula=em_ordem(dias),
        dias_livres=em_ordem(d for d in dias_base if d not in dias),
        janelas_horas=round(janelas_horas(encontros), 1),
        choques_indisponiveis=sum(1 for e in encontros if bate_indisponivel(e, p.indisponiveis)),
        aulas_em_dias_livres=em_ordem(dias & set(p.dias_livres)),
        fora_do_turno=sum(1 for e in encontros if p.turno and turno_do(e) != p.turno),
        completo=completo,
    )


def turma_bate_indisponivel(encontros: Iterable[Encontro], p: PreferenciasSemana | None) -> bool:
    return bool(p and p.indisponiveis) and any(bate_indisponivel(e, p.indisponiveis) for e in encontros)


@dataclass(frozen=True)
class RotinaComporta:
    """Responde "dá para cursar o que falta com esta rotina?" olhando TODAS as turmas conhecidas."""
    cabem: tuple[int, ...]       # têm ao menos uma turma conhecida fora dos horários bloqueados
    nao_cabem: tuple[int, ...]   # todas as turmas conhecidas caem num horário bloqueado
    sem_turma: tuple[int, ...]   # nenhuma turma conhecida: não dá para saber (nunca conta como "cabe")


def rotina_comporta(
    disciplinas: Iterable[int],
    turmas_por_disciplina: Mapping[int, Sequence],
    p: PreferenciasSemana | None,
) -> RotinaComporta:
    """
    Classifica as disciplinas pela rotina do aluno. Uma turma sem encontros (horário não
    informado) não prova nada e é ignorada. Sem horários bloqueados, tudo o que tem turma cabe.
    """
    cabem, nao, sem = [], [], []
    for d in sorted(set(disciplinas)):
        turmas = [t for t in turmas_por_disciplina.get(d, ()) if t.encontros]
        if not turmas:
            sem.append(d)
        elif any(not turma_bate_indisponivel(t.encontros, p) for t in turmas):
            cabem.append(d)
        else:
            nao.append(d)
    return RotinaComporta(tuple(cabem), tuple(nao), tuple(sem))

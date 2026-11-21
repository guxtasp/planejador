"""
Mede o otimizador no exemplo de Ciência da Computação (sem banco).

Uso (a partir da raiz do projeto):
    python -m tools.medir_otimizador

1. Velocidade do recozimento: iterações por segundo de UMA corrida no modo refino (teto 24,
   h = menor horizonte + 1, mesma solução inicial do guloso), o mesmo cenário medido antes da Fase 1.
2. Qualidade da prova: para tetos de 10 a 18 créditos, começando do zero e do meio do curso
   (1º ao 3º período concluídos), quantos semestres, o limite inferior e se o ótimo foi comprovado.

Os números entram em docs/PROGRESSO.md (Fase 1).
"""
from __future__ import annotations

import random
import time

from planner.domain import otimizador as ot
from planner.domain.grafo import construir_grafo, menor_horizonte, primeiros_semestres, ultimos_semestres
from planner.domain.restante import CalendarioDeOferta, nos_a_cursar, periodicidades_efetivas
from tests.exemplo_cc import carregar

INICIO = "2027/1"


def iteracoes_por_segundo(ex, teto: int = 24, iteracoes: int = 6000, repeticoes: int = 3) -> float:
    """Melhor de `repeticoes` corridas (tira o ruído da máquina)."""
    nos, _ = nos_a_cursar(ex.disciplinas, ex.requisitos, set())
    cal = CalendarioDeOferta(INICIO, periodicidades_efetivas(ex.disciplinas.values()))
    g = construir_grafo(nos, ex.requisitos, set())
    m = ot._Modelo(nos, g, ex.disciplinas, ex.requisitos, ex.turmas, cal, ot.ParametrosOtimizacao(max_creditos=teto), 14)
    h = int(menor_horizonte(primeiros_semestres(g, 14, cal))) + 1
    asg = m.guloso(h, ultimos_semestres(g, h, cal))
    alvo = sum(m.cred) / h
    melhor = 0.0
    for r in range(repeticoes):
        t0 = time.perf_counter()
        _a, _c, _d, feitas = m.recozer(asg, h, alvo, iteracoes, random.Random(r), time.monotonic() + 60)
        melhor = max(melhor, feitas / (time.perf_counter() - t0))
    return melhor


def main() -> None:
    ex = carregar()
    print(f"recozimento (refino, teto 24): {iteracoes_por_segundo(ex):,.0f} iterações/s")
    meio = {i for i, d in ex.disciplinas.items() if d.periodo_sugerido in (1, 2, 3)}
    print(f"{'teto':>4} {'aluno':<6}{'sem.':>5}{'LB':>4}  {'ótimo':<6}{'tempo':>7}")
    comprovados = 0
    for teto in (18, 16, 14, 12, 10):
        for nome, feitas in (("zero", set()), ("meio", meio)):
            t0 = time.perf_counter()
            r = ot.otimizar_plano(ex.disciplinas, ex.requisitos, ex.turmas, feitas, INICIO,
                                  ot.ParametrosOtimizacao(max_creditos=teto))
            n = r.metricas.n_semestres if r.metricas else "-"
            comprovados += r.otimo_comprovado
            print(f"{teto:>4} {nome:<6}{n:>5}{r.limite_inferior:>4}  {str(r.otimo_comprovado):<6}"
                  f"{time.perf_counter() - t0:>6.2f}s")
    print(f"ótimo comprovado em {comprovados}/10 cenários")


if __name__ == "__main__":
    main()

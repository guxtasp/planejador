"""Etapa 3B — detecção de ciclos (regra pura do domínio)."""
from planner.domain.ciclos import componentes_ciclicos


def test_sem_ciclo():
    assert componentes_ciclicos([("A", "B"), ("B", "C")]) == ()
    assert componentes_ciclicos([]) == ()


def test_ciclo_simples_e_longo():
    assert componentes_ciclicos([("A", "B"), ("B", "A")]) == (("A", "B"),)
    assert componentes_ciclicos([("A", "B"), ("B", "C"), ("C", "A"), ("D", "A")]) == (("A", "B", "C"),)


def test_dois_ciclos_independentes_em_ordem_estavel():
    arestas = [("D", "C"), ("C", "D"), ("B", "A"), ("A", "B")]
    assert componentes_ciclicos(arestas) == (("A", "B"), ("C", "D"))
    assert componentes_ciclicos(reversed(arestas)) == componentes_ciclicos(arestas)


def test_autodependencia_conta_como_ciclo():
    assert componentes_ciclicos([("A", "A")]) == (("A",),)


def test_dependencia_em_diamante_nao_e_ciclo():
    assert componentes_ciclicos([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]) == ()


def test_cadeia_muito_longa_nao_estoura_recursao():
    n = 5000
    arestas = [(i, i + 1) for i in range(n)] + [(n, 0)]
    assert len(componentes_ciclicos(arestas)[0]) == n + 1

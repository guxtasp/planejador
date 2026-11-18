"""
Etapa 3A — os CSVs de `examples/` (gerados na 1B) precisam passar na validação de
schema sem nenhum erro: provam que os nomes de colunas formalizados na 3A
continuam compatíveis com o que já foi versionado.
"""
import ast
from pathlib import Path

import pytest

from planner.importers import IMPORTADORES

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "examples" / "ciencia-da-computacao"
ESPERADO = {"curso.csv": 1, "disciplinas.csv": 49, "requisitos.csv": 46, "turmas.csv": 61}


@pytest.mark.parametrize("arquivo, total", ESPERADO.items())
def test_exemplo_passa_sem_erros_nem_avisos(arquivo, total):
    resultado = IMPORTADORES[arquivo].importar((EXEMPLO / arquivo).read_bytes())  # bytes: com BOM
    assert resultado.issues == []
    assert len(resultado.registros) == resultado.linhas_lidas == total


def test_exemplo_nao_tem_tipo_em_branco_nem_inventado():
    disciplinas = IMPORTADORES["disciplinas.csv"].importar((EXEMPLO / "disciplinas.csv").read_bytes()).registros
    assert {d.tipo for d in disciplinas} == {"obrigatoria", "optativa"}
    # INF497 vale 0 no seed original: zero explícito é preservado, não vira "desconhecido".
    inf497 = next(d for d in disciplinas if d.codigo == "INF497")
    assert (inf497.creditos, inf497.carga_h) == (0, 0)


def test_exemplo_horarios_multiplos_viram_encontros_da_mesma_turma():
    turmas = IMPORTADORES["turmas.csv"].importar((EXEMPLO / "turmas.csv").read_bytes()).registros
    inf110 = next(t for t in turmas if t.disciplina == "INF110" and t.periodo_letivo == "2026/1")
    assert [e.dia for e in inf110.encontros] == ["SEG", "QUI", "SEX"]


def test_importadores_cobrem_todos_os_arquivos_do_formato():
    assert list(IMPORTADORES) == ["curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv"]


def test_importadores_nao_tocam_no_banco():
    """3A/3B só leem e validam: nenhum módulo de importers (inclusive validacao/) pode usar sessão, repositories ou services."""
    proibidos = ("planner.extensions", "planner.repositories", "planner.services", "flask")
    for caminho in (RAIZ / "planner" / "importers").rglob("*.py"):
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                base = "planner." + (no.module or "") if no.level == 2 else (no.module or "")
                nomes = [base]
            assert not any(n == p or n.startswith(p + ".") for n in nomes for p in proibidos), \
                f"{caminho.name} importa {nomes}"

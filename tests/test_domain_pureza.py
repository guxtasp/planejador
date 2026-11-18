"""Regra de arquitetura: `planner/domain` usa apenas a biblioteca padrão."""
import ast
import sys
from pathlib import Path

DOMINIO = Path(__file__).resolve().parent.parent / "planner" / "domain"


def _importados(arquivo: Path) -> set[str]:
    nomes = set()
    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            nomes |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            nomes.add(no.module.split(".")[0])
    return nomes


def test_dominio_importa_so_stdlib():
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    for arquivo in DOMINIO.glob("*.py"):
        fora = _importados(arquivo) - stdlib
        assert not fora, f"{arquivo.name} importa fora da stdlib: {fora}"

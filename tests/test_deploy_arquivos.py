"""Etapa 6 — arquivos de deploy coerentes (sem rede, sem banco)."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_vercel_json_aponta_para_a_funcao():
    cfg = json.loads((RAIZ / "vercel.json").read_text())
    assert cfg["rewrites"][0]["destination"].startswith("/api/index")
    assert (RAIZ / "api" / "index.py").exists()


def test_driver_do_postgres_esta_nas_dependencias():
    assert "psycopg2-binary" in (RAIZ / "requirements.txt").read_text()


def test_entrypoint_forca_producao():
    assert 'APP_ENV"] = "production"' in (RAIZ / "api" / "index.py").read_text()
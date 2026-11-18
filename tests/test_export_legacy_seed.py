"""
Testes do exportador do seed legado (Etapa 1B) e dos CSVs de exemplo.

Garantem três coisas: (1) o CSV reflete o seed sem inventar dados, (2) os
arquivos versionados em `examples/` não ficaram defasados em relação ao
exportador e (3) o conteúdo cabe no schema (carrega no banco sem violar nenhuma
constraint).
"""
import csv
from datetime import time

import pytest

from planner.extensions import db
from planner.models import Curso, Disciplina, Encontro, Requisito, Turma
from tools.export_legacy_seed import (
    CABECALHOS, DESTINO_PADRAO, exportar, formatar_horarios, ler_seed_legado,
)


def _ler(pasta, nome):
    with open(pasta / nome, encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.fixture(scope="module")
def pasta(tmp_path_factory):
    destino = tmp_path_factory.mktemp("exemplo")
    exportar(destino)
    return destino


@pytest.fixture(scope="module")
def legado():
    return ler_seed_legado()


# ── conteúdo fiel ao seed ──────────────────────────────────────────────────
def test_cabecalhos_dos_quatro_arquivos(pasta):
    for nome, cabecalho in CABECALHOS.items():
        with open(pasta / nome, encoding="utf-8-sig") as arquivo:
            assert next(csv.reader(arquivo)) == cabecalho


def test_exporta_as_49_disciplinas_do_seed(pasta, legado):
    disciplinas = _ler(pasta, "disciplinas.csv")
    assert len(disciplinas) == 49 == len(legado["disciplinas"])
    assert len({d["codigo"] for d in disciplinas}) == 49


def test_optativas_nao_herdam_o_periodo_9_do_legado(pasta):
    disciplinas = _ler(pasta, "disciplinas.csv")
    optativas = [d for d in disciplinas if d["tipo"] == "optativa"]
    assert len(optativas) == 13
    assert all(d["periodo_sugerido"] == "" for d in optativas)
    assert {d["periodo_sugerido"] for d in disciplinas if d["tipo"] == "obrigatoria"} <= set("12345678")


def test_requisitos_sao_os_do_legado_e_apontam_para_codigos_existentes(pasta, legado):
    requisitos = _ler(pasta, "requisitos.csv")
    codigos = {d["codigo"] for d in _ler(pasta, "disciplinas.csv")}
    assert len(requisitos) == len(legado["requisitos"])
    assert all(r["disciplina"] in codigos and r["requisito"] in codigos for r in requisitos)
    assert all(r["disciplina"] != r["requisito"] and r["grupo_alt"] == "" for r in requisitos)


def test_horarios_de_cada_turma_reproduzem_os_do_legado(pasta, legado):
    codigo_de = {d["id"]: d["codigo"] for d in legado["disciplinas"]}
    esperado: dict[str, list] = {}
    for h in legado["horarios"]:
        esperado.setdefault(codigo_de[h["disciplina_id"]], []).append(h)

    for turma in _ler(pasta, "turmas.csv"):
        assert turma["horarios"] == formatar_horarios(esperado[turma["disciplina"]])


def test_disciplina_sem_horario_no_seed_fica_sem_turma(pasta):
    turmas = _ler(pasta, "turmas.csv")
    assert "INF497" not in {t["disciplina"] for t in turmas}


def test_periodo_letivo_segue_paridade_do_periodo_e_optativas_nos_dois(pasta):
    disciplinas = {d["codigo"]: d for d in _ler(pasta, "disciplinas.csv")}
    periodos: dict[str, set] = {}
    for t in _ler(pasta, "turmas.csv"):
        periodos.setdefault(t["disciplina"], set()).add(t["periodo_letivo"])

    assert periodos["INF110"] == {"2026/1"}      # 1º período (ímpar)
    assert periodos["INF112"] == {"2026/2"}      # 2º período (par)
    assert periodos["INF498"] == {"2026/1"}      # 7º
    assert periodos["INF499"] == {"2026/2"}      # 8º
    for codigo, d in disciplinas.items():
        if d["tipo"] == "optativa":
            assert periodos[codigo] == {"2026/1", "2026/2"}


def test_o_que_o_seed_nao_informa_fica_vazio(pasta):
    curso = _ler(pasta, "curso.csv")[0]
    assert curso["nome"] == "Ciência da Computação" and curso["versao_matriz"] == "2023"
    campos_vazios = [c for c in CABECALHOS["curso.csv"] if c not in ("nome", "versao_matriz")]
    assert all(curso[c] == "" for c in campos_vazios)
    assert all(t["docente"] == "" and t["vagas"] == "" for t in _ler(pasta, "turmas.csv"))


def test_formatar_horarios():
    encontros = [
        {"dia": "SEG", "inicio": "16:00", "fim": "18:00"},
        {"dia": "QUI", "inicio": "14:00", "fim": "16:00"},
    ]
    assert formatar_horarios(encontros) == "SEG 16:00-18:00 | QUI 14:00-16:00"


# ── arquivos versionados ───────────────────────────────────────────────────
def test_csvs_versionados_estao_em_dia_com_o_exportador(pasta):
    """Se falhar: rode `python -m tools.export_legacy_seed` e revise o diff."""
    for nome in CABECALHOS:
        assert (DESTINO_PADRAO / nome).read_bytes() == (pasta / nome).read_bytes(), nome


# ── cabe no schema ─────────────────────────────────────────────────────────
def test_csvs_carregam_no_banco_sem_violar_constraints(app, pasta):
    """Carga mínima (a importação de verdade é a Etapa 3): valida o exemplo contra o schema."""
    linha_curso = _ler(pasta, "curso.csv")[0]
    curso = Curso(nome=linha_curso["nome"], versao_matriz=linha_curso["versao_matriz"])
    db.session.add(curso)
    db.session.flush()

    por_codigo = {}
    for d in _ler(pasta, "disciplinas.csv"):
        disc = Disciplina(
            curso_id=curso.id, codigo=d["codigo"], nome=d["nome"], tipo=d["tipo"], cor=d["cor"],
            creditos=int(d["creditos"]), carga_h=int(d["carga_h"]),
            periodo_sugerido=int(d["periodo_sugerido"]) if d["periodo_sugerido"] else None,
        )
        db.session.add(disc)
        por_codigo[d["codigo"]] = disc
    db.session.flush()

    for r in _ler(pasta, "requisitos.csv"):
        db.session.add(Requisito(
            disciplina_id=por_codigo[r["disciplina"]].id,
            requisito_id=por_codigo[r["requisito"]].id, tipo=r["tipo"],
        ))

    for t in _ler(pasta, "turmas.csv"):
        turma = Turma(
            disciplina_id=por_codigo[t["disciplina"]].id,
            periodo_letivo=t["periodo_letivo"], codigo_turma=t["codigo_turma"],
        )
        for bloco in t["horarios"].split(" | "):
            dia, faixa = bloco.split(" ")
            ini, fim = (time.fromisoformat(h) for h in faixa.split("-"))
            turma.encontros.append(Encontro(dia=dia, inicio=ini, fim=fim))
        db.session.add(turma)
    db.session.commit()

    assert db.session.query(Disciplina).count() == 49
    assert db.session.query(Turma).count() == 61

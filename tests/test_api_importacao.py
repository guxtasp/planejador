"""Etapa 3C — endpoints, modelos de CSV, prompt de IA e a tela."""
import io
from pathlib import Path

import pytest

from planner.importers import IMPORTADORES
from planner.importers.modelos import FONTES, gerar_prompt_ia, listar_fontes, listar_modelos, modelo_csv

EXEMPLO = Path(__file__).resolve().parent.parent / "examples" / "ciencia-da-computacao"
NOMES = ("curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv")


@pytest.fixture
def client(client_logado):
    """Desde a 5A importar exige login: estes testes usam um cliente já logado."""
    return client_logado


def multipart(**extra):
    dados = {n: (io.BytesIO((EXEMPLO / n).read_bytes()), n) for n in NOMES}
    dados.update(extra)
    return dados


def test_validar_devolve_a_previa_sem_gravar(client):
    r = client.post("/api/importacao/validar", data=multipart(), content_type="multipart/form-data")
    j = r.get_json()
    assert r.status_code == 200 and j["ok"] and j["previa"]["pode_confirmar"]
    assert j["previa"]["totais"] == {"novos": 157, "a_atualizar": 0, "inalterados": 0, "erros": 0, "avisos": 0}
    # nada foi gravado: confirmar ainda cria o curso
    assert client.post("/api/importacao/confirmar", data=multipart(), content_type="multipart/form-data").status_code == 201


def test_confirmar_e_repetir(client):
    r = client.post("/api/importacao/confirmar", data=multipart(), content_type="multipart/form-data")
    assert r.status_code == 201
    rel = r.get_json()["relatorio"]
    assert rel["curso_criado"] and rel["por_arquivo"]["disciplinas.csv"]["criados"] == 49
    outra = client.post("/api/importacao/confirmar", data=multipart(), content_type="multipart/form-data")
    assert outra.status_code == 422 and "Nada a importar" in outra.get_json()["erro"]


def test_confirmar_com_erro_devolve_422_com_a_previa(client):
    dados = multipart(**{"requisitos.csv": (io.BytesIO(b"disciplina,requisito,tipo\nX,Y,pre\n"), "requisitos.csv")})
    r = client.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    j = r.get_json()
    assert r.status_code == 422 and not j["ok"] and j["detalhes"]["totais"]["erros"] == 2


def test_sem_arquivos_e_curso_id_invalido(client):
    assert client.post("/api/importacao/validar").status_code == 400
    r = client.post("/api/importacao/validar", data={**multipart(), "curso_id": "abc"}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_modelos_e_prompt(client):
    assert client.get("/api/importacao/modelos").get_json()["modelos"] == list(IMPORTADORES)
    r = client.get("/api/importacao/modelos/disciplinas.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv" and "attachment" in r.headers["Content-Disposition"]
    assert client.get("/api/importacao/modelos/xyz.csv").status_code == 404
    assert "NUNCA invente" in client.get("/api/importacao/prompt-ia").get_json()["prompt"]
    for fonte in listar_fontes():
        r = client.get(f"/api/importacao/prompt-ia?fonte={fonte}").get_json()
        assert r["fonte"] == fonte and "NUNCA invente" in r["prompt"]
    assert client.get("/api/importacao/prompt-ia?fonte=xyz").status_code == 400


@pytest.mark.parametrize("arquivo", listar_modelos())
def test_cada_modelo_csv_e_valido(arquivo):
    r = IMPORTADORES[arquivo].importar(modelo_csv(arquivo))
    assert r.issues == [] and len(r.registros) == 1


@pytest.mark.parametrize("fonte", listar_fontes())
def test_prompt_lista_as_colunas_dos_arquivos_da_fonte(fonte):
    prompt = gerar_prompt_ia(fonte)
    for nome in FONTES[fonte].arquivos:
        assert nome in prompt
        assert all(c in prompt for c in IMPORTADORES[nome].esquema.colunas)


def test_prompt_nao_menciona_historico_e_o_do_quadro_so_pede_turmas():
    for fonte in listar_fontes():
        assert "historico.csv" not in gerar_prompt_ia(fonte)
    quadro = gerar_prompt_ia("horarios")
    assert "turmas.csv" in quadro and "disciplinas.csv: obrigatórias" not in quadro
    assert "local" in quadro


def test_pagina_de_importacao(client):
    r = client.get("/importar")
    assert r.status_code == 200 and b"/api/importacao/validar" in r.data

"""Histórico colado do sistema acadêmico: parser (sem banco) e prévia/confirmação (API)."""
from decimal import Decimal

import pytest

from planner.importers.historico_colado import APROVADO, CURSANDO, REPROVADO, ler_historico_colado, ler_linha

TABELA = """Código\tDisciplina\tPeríodo\tCH\tNota\tSituação
INF110\tProgramação I\t2024/1\t90\t8,5\tAprovado
MAT 140\tCálculo I\t2024.1\t60\t3,0\tReprovado por nota
MAT140;Cálculo I;2024-2;60;7;APR
INF112  Programação II  2025/1  90    Matriculado
INF213 Estruturas de Dados 2025/1 90 ???
Total de créditos: 210
"""


def test_reconhece_formatos_diferentes_na_mesma_colagem():
    l = {x.numero: x for x in ler_historico_colado(TABELA)}
    assert set(l) == {2, 3, 4, 5, 6}                         # cabeçalho e total ficam de fora
    assert (l[2].codigo, l[2].periodo_letivo, l[2].status, l[2].nota) == ("INF110", "2024/1", APROVADO, Decimal("8.5"))
    assert (l[3].codigo, l[3].periodo_letivo, l[3].status) == ("MAT140", "2024/1", REPROVADO)
    assert (l[4].periodo_letivo, l[4].status, l[4].nota) == ("2024/2", APROVADO, Decimal(7))
    assert (l[5].status, l[5].nota) == (CURSANDO, None)    # 90 é a CH, não nota
    assert l[6].status is None and "situação" in l[6].problema


@pytest.mark.parametrize("texto,status", [("INF110 2024/1 RF", REPROVADO), ("INF110 2024/1 Dispensado", APROVADO),
                                          ("INF110 2024/1 em andamento", CURSANDO), ("INF110 2024/1 REP 2,5", REPROVADO)])
def test_situacoes_abreviadas(texto, status):
    assert ler_linha(1, texto).status == status


def test_numero_sozinho_nao_vira_nota_e_sem_periodo_fica_vazio():
    x = ler_linha(1, "INF110 Programação I 60 Aprovado")
    assert x.nota is None and x.periodo_letivo is None and x.status == APROVADO


# ── API ──────────────────────────────────────────────────────────────────────
def url(curso):
    return f"/api/cursos/{curso['id']}/historico/colar"


def test_previa_e_confirmacao(client_logado, curso_pequeno):
    texto = ("AAA100 2025/1 Aprovado 8,0\nAAA100 2025/1 Aprovado 8,0\n"
             "ZZZ999 2025/1 Aprovado\nBBB100 2025/2 ???\nCCC100 2025/2 Reprovado")
    p = client_logado.post(url(curso_pequeno), json={"texto": texto}).get_json()
    assert p["totais"] == {"reconhecida": 2, "nao_encontrada": 1, "duplicada": 1, "nao_entendida": 1}
    assert p["pode_confirmar"] and "2 reconhecidas" in p["resumo"]
    assert client_logado.get(f"/api/cursos/{curso_pequeno['id']}/historico").get_json()["historico"] == []   # prévia não grava
    c = client_logado.post(url(curso_pequeno), json={"texto": texto, "confirmar": True}).get_json()
    assert c["gravadas"] == 2
    again = client_logado.post(url(curso_pequeno), json={"texto": texto}).get_json()
    assert again["totais"]["reconhecida"] == 0 and again["totais"]["duplicada"] == 3   # já está no histórico


def test_texto_vazio_e_erro_de_campo(client_logado, curso_pequeno):
    r = client_logado.post(url(curso_pequeno), json={"texto": "  "})
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "texto"}


# ── arquivo CSV exportado do sistema acadêmico ───────────────────────────────
def test_csv_com_virgula_nao_confunde_carga_horaria_com_nota():
    csv_texto = '\ufeffcodigo,disciplina,periodo,ch,nota,situacao\nINF110,Programação I,2024/1,60,"7,5",Aprovado\nMAT140,"Cálculo I, turma A",2024/1,60,3,Reprovado\n'
    l = {x.codigo: x for x in ler_historico_colado(csv_texto)}
    assert l["INF110"].nota == Decimal("7.5") and l["INF110"].status == APROVADO
    assert l["MAT140"].nota == Decimal(3) and l["MAT140"].status == REPROVADO and l["MAT140"].periodo_letivo == "2024/1"


def test_csv_com_ponto_e_virgula():
    l = ler_historico_colado("INF110;2024/1;8,5;APR\nINF112;2024/2;;Cursando\n")
    assert [(x.codigo, x.nota, x.status) for x in l] == [("INF110", Decimal("8.5"), APROVADO), ("INF112", None, CURSANDO)]


def test_texto_colado_com_nota_decimal_nao_vira_csv():
    x = ler_historico_colado("INF110 Programação I 2024/1 8,5 Aprovado\nINF112 Programação II 2024/2 7,0 Aprovado")
    assert [y.nota for y in x] == [Decimal("8.5"), Decimal("7.0")]

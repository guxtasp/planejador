"""
Turma teórica e prática separadas (matrícula = uma de cada) e disciplinas cujos créditos não contam
no limite do semestre (estágio/TCC com muitos créditos e pouca aula).
"""
import io
from types import SimpleNamespace as NS

import pytest

from planner.domain.carga import avaliar_carga
from planner.domain.componentes import (e_combinado, id_combinado, normalizar_componente, opcoes_de_matricula,
                                        partes_do_id)
from planner.domain.entidades import Disciplina
from planner.domain.otimizador import ParametrosOtimizacao, otimizar_plano


# ── domínio: opções de matrícula ─────────────────────────────────────────────
def test_teoricas_vezes_praticas_no_mesmo_periodo():
    t1, p1, p2 = NS(id=1, periodo_letivo="2026/1", componente="teorica"), \
        NS(id=2, periodo_letivo="2026/1", componente="pratica"), NS(id=3, periodo_letivo="2026/1", componente="pratica")
    completa, so_teo = NS(id=4, periodo_letivo="2026/1", componente=None), NS(id=5, periodo_letivo="2026/2", componente="teorica")
    opcoes = opcoes_de_matricula([t1, p1, p2, completa, so_teo])
    assert [tuple(x.id for x in o) for o in opcoes] == [(4,), (1, 2), (1, 3), (5,)]


def test_id_combinado_ida_e_volta():
    v = id_combinado(12, 345)
    assert v < 0 and e_combinado(v) and partes_do_id(v) == (12, 345)
    assert partes_do_id(12) == (12,) and not e_combinado(12) and not e_combinado(None)


@pytest.mark.parametrize("texto,esperado", [("Teórica", "teorica"), ("T", "teorica"), ("prática", "pratica"),
                                            ("Laboratório", "pratica"), ("", None), (None, None)])
def test_normaliza_componente(texto, esperado):
    assert normalizar_componente(texto) == esperado


def test_componente_desconhecido_e_erro():
    with pytest.raises(ValueError):
        normalizar_componente("seminario")


# ── domínio: créditos fora do limite ─────────────────────────────────────────
def test_estagio_fora_do_limite_nao_gera_sobrecarga_mas_conta_nos_creditos():
    est = Disciplina(1, "EST", "Estágio", 10, conta_no_limite=False)
    a = Disciplina(2, "A", "A", 6)
    c = avaliar_carga([est, a], 8)
    assert (c.creditos, c.creditos_no_limite, c.sobrecarga) == (16, 6, False)
    assert avaliar_carga([Disciplina(1, "EST", "Estágio", 10), a], 8).sobrecarga


def test_sugestao_encaixa_disciplinas_junto_do_estagio_fora_do_limite():
    def rodar(conta):
        discs = {1: Disciplina(1, "EST", "Estágio", 10, conta_no_limite=conta),
                 2: Disciplina(2, "A", "A", 4), 3: Disciplina(3, "B", "B", 4)}
        return otimizar_plano(discs, {i: [] for i in discs}, {}, set(), "2027/1", ParametrosOtimizacao(max_creditos=10))
    assert rodar(True).metricas.n_semestres == 2         # 10 cr de estágio enchem o semestre
    fora = rodar(False)
    assert fora.metricas.n_semestres == 1                 # cabe tudo: o estágio não ocupa o limite
    assert fora.semestres[0].creditos == 18               # mas os créditos aparecem inteiros


# ── via HTTP ────────────────────────────────────────────────────────────────
CSVS = {
    "curso.csv": "nome,max_creditos_semestre\nCurso TP,20\n",
    "disciplinas.csv": "codigo,nome,creditos,tipo\nQUI100,Química,6,obrigatoria\nFIS100,Física,4,obrigatoria\n",
    "turmas.csv": (
        "disciplina,periodo_letivo,codigo_turma,horarios,componente\n"
        "QUI100,2026/1,T1,SEG 08:00-10:00,teórica\n"
        "QUI100,2026/1,P1,TER 08:00-10:00,prática\n"
        "QUI100,2026/1,P2,QUA 14:00-16:00,pratica\n"
        "FIS100,2026/1,T1,TER 08:00-10:00,\n"          # bate com a prática P1
    ),
}


@pytest.fixture
def curso_tp(client_logado):
    dados = {n: (io.BytesIO(t.encode()), n) for n, t in CSVS.items()}
    r = client_logado.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["relatorio"]["curso_id"]
    disc = {d["codigo"]: d["id"] for d in client_logado.get(f"/api/cursos/{cid}/disciplinas").get_json()["disciplinas"]}
    return {"id": cid, "disc": disc}


def test_oferta_devolve_teorica_mais_pratica_como_uma_opcao(client_logado, curso_tp):
    j = client_logado.get(f"/api/cursos/{curso_tp['id']}/turmas").get_json()
    qui = [t for t in j["turmas"] if t["disciplina_id"] == curso_tp["disc"]["QUI100"]]
    assert sorted(t["codigo_turma"] for t in qui) == ["T1+P1", "T1+P2"]
    assert all(t["componente"] == "combinada" and len(t["encontros"]) == 2 for t in qui)
    assert {e.get("componente") for e in qui[0]["encontros"]} == {"teorica", "pratica"}


def test_escolha_automatica_pega_a_pratica_sem_choque_e_o_plano_guarda_as_duas(client_logado, curso_tp):
    cid, d = curso_tp["id"], curso_tp["disc"]
    itens = [{"disciplina_id": d["QUI100"]}, {"disciplina_id": d["FIS100"]}]
    r = client_logado.post(f"/api/cursos/{cid}/plano/analisar",
                           json={"semestres": [{"periodo_letivo": "2026/1", "itens": itens}]})
    m = r.get_json()["semestres"][0]["marcas"]
    escolhida = m[str(d["QUI100"])]["turma_sugerida"]
    turmas = {t["id"]: t for t in client_logado.get(f"/api/cursos/{cid}/turmas").get_json()["turmas"]}
    assert turmas[escolhida]["codigo_turma"] == "T1+P2" and not m[str(d["QUI100"])]["choques"]

    plano = {"nome": "TP", "semestres": [{"rotulo": "S1", "periodo_letivo": "2026/1",
                                          "itens": [{"disciplina_id": d["QUI100"], "turma_id": escolhida},
                                                    {"disciplina_id": d["FIS100"]}]}]}
    r = client_logado.post(f"/api/cursos/{cid}/planos", json=plano)
    assert r.status_code in (200, 201), r.get_json()
    salvo = r.get_json()["plano"]["semestres"][0]["itens"]
    assert next(i for i in salvo if i["disciplina_id"] == d["QUI100"])["turma_id"] == escolhida


def test_plano_recusa_combinacao_de_outra_disciplina(client_logado, curso_tp):
    cid, d = curso_tp["id"], curso_tp["disc"]
    turmas = client_logado.get(f"/api/cursos/{cid}/turmas").get_json()["turmas"]
    combinada = next(t["id"] for t in turmas if t["componente"] == "combinada")
    plano = {"nome": "X", "semestres": [{"rotulo": "S1", "periodo_letivo": "2026/1",
                                         "itens": [{"disciplina_id": d["FIS100"], "turma_id": combinada}]}]}
    assert client_logado.post(f"/api/cursos/{cid}/planos", json=plano).status_code == 422


def test_componente_invalido_no_csv_e_erro_de_importacao(client_logado):
    csvs = {**CSVS, "turmas.csv": "disciplina,periodo_letivo,codigo_turma,horarios,componente\nQUI100,2026/1,T1,SEG 08:00-10:00,seminario\n"}
    dados = {n: (io.BytesIO(t.encode()), n) for n, t in csvs.items()}
    r = client_logado.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    assert r.status_code == 422


def test_edicao_marca_fora_do_limite_e_analise_nao_acusa_sobrecarga(client_logado, curso_tp):
    cid, d = curso_tp["id"], curso_tp["disc"]
    client_logado.patch(f"/api/cursos/{cid}/disciplinas/{d['QUI100']}", json={"creditos": 18})
    itens = [{"disciplina_id": d["QUI100"]}, {"disciplina_id": d["FIS100"]}]
    analisar = lambda: client_logado.post(f"/api/cursos/{cid}/plano/analisar", json={
        "semestres": [{"periodo_letivo": "2026/1", "itens": itens}]}).get_json()["semestres"][0]
    assert analisar()["sobrecarga"] is True                       # 22 de 20
    r = client_logado.patch(f"/api/cursos/{cid}/disciplinas/{d['QUI100']}", json={"conta_no_limite": False})
    assert r.get_json()["disciplina"]["conta_no_limite"] is False
    s = analisar()
    assert (s["sobrecarga"], s["creditos"], s["creditos_no_limite"], s["creditos_fora_do_limite"]) == (False, 22, 4, 18)

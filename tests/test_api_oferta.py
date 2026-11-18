"""Etapa 4B — oferta de turmas, grade derivada e análise de plano (via HTTP)."""
import io

import pytest


@pytest.fixture
def client(client_logado):
    """Desde a 5A importar exige login: estes testes usam um cliente já logado."""
    return client_logado

CSVS = {
    "curso.csv": "nome,max_creditos_semestre\nCurso Pequeno,6\n",
    "disciplinas.csv": (
        "codigo,nome,creditos,tipo\n"
        "AAA100,Alfa,4,obrigatoria\nBBB100,Beta,4,obrigatoria\nCCC100,Gama,2,obrigatoria\n"
    ),
    "requisitos.csv": "disciplina,requisito,tipo,grupo_alt\nBBB100,AAA100,pre,\n",
    "turmas.csv": (
        "disciplina,periodo_letivo,codigo_turma,horarios\n"
        "AAA100,2026/1,T1,SEG 08:00-10:00\n"
        "BBB100,2026/1,T1,SEG 09:00-11:00\n"       # colide com AAA100 T1
        "BBB100,2026/1,T2,TER 19:00-22:30\n"        # alternativa livre, noturna
        "CCC100,2026/1,T1,SAB 08:00-12:00\n"        # sábado
        "BBB100,2026/2,T1,SEG 09:00-11:00\n"
    ),
}


@pytest.fixture
def curso(client):
    dados = {n: (io.BytesIO(t.encode()), n) for n, t in CSVS.items()}
    r = client.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["relatorio"]["curso_id"]
    disc = {d["codigo"]: d["id"] for d in client.get(f"/api/cursos/{cid}/disciplinas").get_json()["disciplinas"]}
    turmas = {}
    for t in client.get(f"/api/cursos/{cid}/turmas").get_json()["turmas"]:
        codigo = next(c for c, i in disc.items() if i == t["disciplina_id"])
        turmas[(codigo, t["periodo_letivo"], t["codigo_turma"])] = t["id"]
    return {"id": cid, "disc": disc, "turmas": turmas}


def analisar(client, curso, semestres):
    return client.post(f"/api/cursos/{curso['id']}/plano/analisar", json={"semestres": semestres})


def item(curso, codigo, turma=None, periodo="2026/1"):
    tid = curso["turmas"][(codigo, periodo, turma)] if turma else None
    return {"disciplina_id": curso["disc"][codigo], "turma_id": tid}


# ── /turmas ──────────────────────────────────────────────────────────────────
def test_turmas_trazem_encontros_periodos_e_grade_derivada(client, curso):
    j = client.get(f"/api/cursos/{curso['id']}/turmas").get_json()
    assert j["ok"] and len(j["turmas"]) == 5
    assert j["periodos"] == ["2026/1", "2026/2"]
    assert j["grade"] == {"dias": ["SEG", "TER", "SAB"], "hora_inicio": 8, "hora_fim": 23}
    t2 = next(t for t in j["turmas"] if t["codigo_turma"] == "T2")
    assert t2["encontros"] == [{"dia": "TER", "inicio": "19:00", "fim": "22:30", "local": None}]


def test_turmas_filtram_por_periodo_mas_listam_todos_os_periodos(client, curso):
    j = client.get(f"/api/cursos/{curso['id']}/turmas?periodo=2026/2").get_json()
    assert len(j["turmas"]) == 1 and j["periodos"] == ["2026/1", "2026/2"]
    assert client.get(f"/api/cursos/{curso['id']}/turmas?periodo=1999/1").get_json()["turmas"] == []


def test_turmas_de_curso_inexistente_da_404(client):
    assert client.get("/api/cursos/999/turmas").status_code == 404


def test_curso_sem_turmas_tem_grade_padrao_e_lista_vazia(client):
    dados = {n: (io.BytesIO(CSVS[n].encode()), n) for n in ("curso.csv", "disciplinas.csv")}
    cid = client.post("/api/importacao/confirmar", data=dados,
                      content_type="multipart/form-data").get_json()["relatorio"]["curso_id"]
    j = client.get(f"/api/cursos/{cid}/turmas").get_json()
    assert j["turmas"] == [] and j["periodos"] == []
    assert j["grade"] == {"dias": ["SEG", "TER", "QUA", "QUI", "SEX"], "hora_inicio": 7, "hora_fim": 22}


# ── /plano/analisar ──────────────────────────────────────────────────────────
def test_duas_turmas_escolhidas_que_colidem_dao_conflito(client, curso):
    r = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                  "itens": [item(curso, "AAA100", "T1"), item(curso, "CCC100", "T1")]}])
    assert r.get_json()["semestres"][0]["conflitos"] == []   # SEG × SAB: não colidem

    r = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                  "itens": [item(curso, "AAA100", "T1"), item(curso, "BBB100", "T1")]}])
    (c,) = r.get_json()["semestres"][0]["conflitos"]
    assert c["tipo"] == "conflito" and c["dia"] == "SEG"
    assert {c["a"]["codigo"], c["b"]["codigo"]} == {"AAA100", "BBB100"}
    assert c["horario_a"] == "08:00–10:00" and c["horario_b"] == "09:00–11:00"


def test_sem_escolher_turma_o_conflito_e_apenas_possivel(client, curso):
    j = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                  "itens": [item(curso, "AAA100", "T1"), item(curso, "BBB100")]}]).get_json()
    s = j["semestres"][0]
    assert [c["tipo"] for c in s["conflitos"]] == ["conflito_possivel"]
    assert s["sem_turma_escolhida"] == [curso["disc"]["BBB100"]]


def test_escolher_a_turma_livre_resolve_o_conflito(client, curso):
    j = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                  "itens": [item(curso, "AAA100", "T1"), item(curso, "BBB100", "T2")]}]).get_json()
    assert j["semestres"][0]["conflitos"] == []


def test_carga_usa_o_limite_do_curso(client, curso):
    j = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                  "itens": [item(curso, "AAA100"), item(curso, "CCC100")]}]).get_json()
    s = j["semestres"][0]
    assert (s["creditos"], s["limite_creditos"], s["sobrecarga"]) == (6, 6, False)
    j = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                  "itens": [item(curso, "AAA100"), item(curso, "BBB100")]}]).get_json()
    assert j["semestres"][0]["sobrecarga"] is True and j["total_problemas"] >= 1


def test_pre_requisito_no_mesmo_semestre_pendente_e_em_semestre_anterior_cumprido(client, curso):
    juntos = analisar(client, curso, [{"periodo_letivo": "2026/1",
                                       "itens": [item(curso, "AAA100"), item(curso, "BBB100")]}]).get_json()
    (p,) = juntos["semestres"][0]["pendencias"]
    assert p["disciplina"]["codigo"] == "BBB100" and p["tipo"] == "pre"
    assert [a["codigo"] for a in p["alternativas"]] == ["AAA100"]

    seq = analisar(client, curso, [{"periodo_letivo": "2026/1", "itens": [item(curso, "AAA100")]},
                                   {"periodo_letivo": "2026/2", "itens": [item(curso, "BBB100")]}]).get_json()
    assert all(s["pendencias"] == [] for s in seq["semestres"])


def test_semestre_sem_periodo_nao_julga_horario(client, curso):
    j = analisar(client, curso, [{"periodo_letivo": None, "itens": [item(curso, "AAA100"), item(curso, "BBB100")]}])
    assert j.get_json()["semestres"][0]["conflitos"] == []


def test_turma_de_outro_periodo_ou_disciplina_desconhecida_vai_para_invalidos(client, curso):
    t_outro_periodo = curso["turmas"][("BBB100", "2026/2", "T1")]
    j = analisar(client, curso, [{"periodo_letivo": "2026/1", "itens": [
        {"disciplina_id": curso["disc"]["BBB100"], "turma_id": t_outro_periodo},
        {"disciplina_id": 99999, "turma_id": None}]}]).get_json()
    motivos = {(i["disciplina_id"], i["motivo"]) for i in j["semestres"][0]["invalidos"]}
    assert motivos == {(curso["disc"]["BBB100"], "turma_invalida"), (99999, "disciplina_desconhecida")}
    assert j["semestres"][0]["creditos"] == 4   # a Beta segue no plano, a desconhecida não conta


@pytest.mark.parametrize("corpo", [
    None, [], {}, {"semestres": "x"}, {"semestres": [1]},
    {"semestres": [{"itens": "x"}]}, {"semestres": [{"itens": [{"disciplina_id": "1"}]}]},
    {"semestres": [{"itens": [{"disciplina_id": True}]}]},
    {"semestres": [{"itens": [{"disciplina_id": 1, "turma_id": 1.5}]}]},
    {"semestres": [{"periodo_letivo": 5, "itens": []}]},
    {"semestres": [{"itens": []}] * 21},
])
def test_formato_invalido_da_400_em_json(client, curso, corpo):
    r = client.post(f"/api/cursos/{curso['id']}/plano/analisar", json=corpo)
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_plano_vazio_e_valido_e_curso_inexistente_da_404(client, curso):
    assert analisar(client, curso, []).get_json() == {"ok": True, "semestres": [], "total_problemas": 0}
    r = client.post("/api/cursos/999/plano/analisar", json={"semestres": []})
    assert r.status_code == 404


def test_analise_nao_grava_nada(client, curso, app):
    from planner.extensions import db
    from planner.models import Plano

    analisar(client, curso, [{"periodo_letivo": "2026/1", "itens": [item(curso, "AAA100", "T1")]}])
    assert db.session.query(Plano).count() == 0

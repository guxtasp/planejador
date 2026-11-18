"""Etapa 5B-2 — planos de matrícula guardados no servidor, por usuário (via HTTP)."""
from tests.conftest import CSVS_CURSO_PEQUENO, tornar_publico


def base(curso):
    return f"/api/cursos/{curso['id']}/planos"


def plano_exemplo(curso, nome="Plano A"):
    d, t = curso["disc"], curso["turmas"]
    return {"nome": nome, "semestres": [
        {"rotulo": "Semestre 1", "periodo_letivo": "2026/1",
         "itens": [{"disciplina_id": d["AAA100"], "turma_id": t[("AAA100", "2026/1", "T1")]},
                   {"disciplina_id": d["CCC100"], "turma_id": None}]},
        {"rotulo": "Semestre 2", "periodo_letivo": None, "itens": [{"disciplina_id": d["BBB100"], "turma_id": None}]},
    ]}


def criar(client, curso, corpo=None):
    r = client.post(base(curso), json=corpo or plano_exemplo(curso))
    assert r.status_code == 201, r.get_json()
    return r.get_json()["plano"]


# ── acesso ───────────────────────────────────────────────────────────────────
def test_visitante_recebe_401(client, curso_pequeno):
    for metodo, caminho in [("get", base(curso_pequeno)), ("post", base(curso_pequeno)),
                            ("put", base(curso_pequeno) + "/1"), ("delete", base(curso_pequeno) + "/1")]:
        assert getattr(client, metodo)(caminho, json={}).status_code == 401


def test_o_planejador_exige_login_mesmo_em_curso_publico(client, curso_pequeno):
    tornar_publico(curso_pequeno["id"])
    r = client.get(f"/curso/{curso_pequeno['id']}")
    assert r.status_code == 302 and "/entrar?proximo=/curso/" in r.headers["Location"]


# ── CRUD ─────────────────────────────────────────────────────────────────────
def test_comeca_sem_planos(client_logado, curso_pequeno):
    assert client_logado.get(base(curso_pequeno)).get_json() == {"ok": True, "planos": []}


def test_criar_e_listar_preserva_semestres_itens_e_turmas(client_logado, curso_pequeno):
    criado = criar(client_logado, curso_pequeno)
    assert criado["id"] and criado["nome"] == "Plano A"
    lista = client_logado.get(base(curso_pequeno)).get_json()["planos"]
    assert len(lista) == 1
    s1, s2 = lista[0]["semestres"]
    assert (s1["rotulo"], s1["periodo_letivo"], s2["periodo_letivo"]) == ("Semestre 1", "2026/1", None)
    assert {i["disciplina_id"]: i["turma_id"] for i in s1["itens"]} == {
        curso_pequeno["disc"]["AAA100"]: curso_pequeno["turmas"][("AAA100", "2026/1", "T1")],
        curso_pequeno["disc"]["CCC100"]: None}


def test_salvar_substitui_o_plano_inteiro(client_logado, curso_pequeno):
    p = criar(client_logado, curso_pequeno)
    d = curso_pequeno["disc"]
    novo = {"nome": "Renomeado", "semestres": [{"rotulo": "Único", "periodo_letivo": None,
                                               "itens": [{"disciplina_id": d["BBB100"], "turma_id": None}]}]}
    r = client_logado.put(f"{base(curso_pequeno)}/{p['id']}", json=novo)
    assert r.status_code == 200, r.get_json()
    salvo = r.get_json()["plano"]
    assert salvo["nome"] == "Renomeado" and len(salvo["semestres"]) == 1
    assert [i["disciplina_id"] for i in salvo["semestres"][0]["itens"]] == [d["BBB100"]]


def test_salvar_varias_vezes_o_mesmo_conteudo_nao_viola_a_unicidade_da_ordem(client_logado, curso_pequeno):
    p = criar(client_logado, curso_pequeno)
    for _ in range(3):
        r = client_logado.put(f"{base(curso_pequeno)}/{p['id']}", json=plano_exemplo(curso_pequeno))
        assert r.status_code == 200, r.get_json()
    assert len(client_logado.get(base(curso_pequeno)).get_json()["planos"][0]["semestres"]) == 2


def test_excluir_remove_plano_semestres_e_itens(client_logado, curso_pequeno, app):
    from planner.extensions import db
    from planner.models import PlanoItem, PlanoSemestre

    p = criar(client_logado, curso_pequeno)
    assert client_logado.delete(f"{base(curso_pequeno)}/{p['id']}").status_code == 200
    assert client_logado.get(base(curso_pequeno)).get_json()["planos"] == []
    assert db.session.query(PlanoSemestre).count() == 0 and db.session.query(PlanoItem).count() == 0
    assert client_logado.delete(f"{base(curso_pequeno)}/{p['id']}").status_code == 404


# ── validação ────────────────────────────────────────────────────────────────
def test_formato_invalido_da_400(client_logado, curso_pequeno):
    assert client_logado.post(base(curso_pequeno), json={"nome": ""}).status_code == 400
    assert client_logado.post(base(curso_pequeno), data="x", content_type="text/plain").status_code == 400


def test_referencias_invalidas_dao_422_e_nao_gravam(client_logado, curso_pequeno):
    d, t = curso_pequeno["disc"], curso_pequeno["turmas"]
    ruins = [
        {"nome": "x", "semestres": [{"itens": [{"disciplina_id": 99999}]}]},                       # fora do curso
        {"nome": "x", "semestres": [{"itens": [{"disciplina_id": d["AAA100"]}]},
                                    {"itens": [{"disciplina_id": d["AAA100"]}]}]},                  # repetida
        {"nome": "x", "semestres": [{"periodo_letivo": "2026/1",
                                     "itens": [{"disciplina_id": d["AAA100"], "turma_id": t[("BBB100", "2026/1", "T1")]}]}]},
        {"nome": "x", "semestres": [{"periodo_letivo": "2026/2",
                                     "itens": [{"disciplina_id": d["BBB100"], "turma_id": t[("BBB100", "2026/1", "T1")]}]}]},
        {"nome": "x", "semestres": [{"itens": [{"disciplina_id": d["BBB100"], "turma_id": t[("BBB100", "2026/1", "T1")]}]}]},
    ]
    for corpo in ruins:
        assert client_logado.post(base(curso_pequeno), json=corpo).status_code == 422, corpo
    assert client_logado.get(base(curso_pequeno)).get_json()["planos"] == []


def test_salvar_invalido_mantem_o_plano_como_estava(client_logado, curso_pequeno):
    p = criar(client_logado, curso_pequeno)
    ruim = {"nome": "x", "semestres": [{"itens": [{"disciplina_id": 99999}]}]}
    assert client_logado.put(f"{base(curso_pequeno)}/{p['id']}", json=ruim).status_code == 422
    atual = client_logado.get(base(curso_pequeno)).get_json()["planos"][0]
    assert atual["nome"] == "Plano A" and len(atual["semestres"]) == 2


def test_limite_de_planos_por_curso(client_logado, curso_pequeno):
    from planner.services.planos import MAX_PLANOS_POR_CURSO

    for i in range(MAX_PLANOS_POR_CURSO):
        criar(client_logado, curso_pequeno, {"nome": f"P{i}", "semestres": []})
    assert client_logado.post(base(curso_pequeno), json={"nome": "demais", "semestres": []}).status_code == 422


# ── isolamento entre usuários ────────────────────────────────────────────────
def test_cada_usuario_ve_e_altera_so_os_proprios_planos(client_logado, client_outro, curso_pequeno):
    tornar_publico(curso_pequeno["id"])
    meu = criar(client_logado, curso_pequeno)
    assert client_outro.get(base(curso_pequeno)).get_json()["planos"] == []
    # editar, excluir e analisar plano alheio: mesmo 404 de plano inexistente
    assert client_outro.put(f"{base(curso_pequeno)}/{meu['id']}", json=plano_exemplo(curso_pequeno, "invadido")).status_code == 404
    assert client_outro.delete(f"{base(curso_pequeno)}/{meu['id']}").status_code == 404
    assert client_logado.get(base(curso_pequeno)).get_json()["planos"][0]["nome"] == "Plano A"
    # a outra conta tem os seus, separados
    dela = criar(client_outro, curso_pequeno, plano_exemplo(curso_pequeno, "Da outra"))
    assert [p["nome"] for p in client_outro.get(base(curso_pequeno)).get_json()["planos"]] == ["Da outra"]
    assert dela["id"] != meu["id"]


def test_plano_nao_vale_em_outro_curso_do_mesmo_usuario(client_logado, curso_pequeno):
    import io

    dados = {n: (io.BytesIO(t.replace("Curso Pequeno", "Outro Curso").encode()), n)
             for n, t in CSVS_CURSO_PEQUENO.items()}
    r = client_logado.post("/api/importacao/confirmar", data=dados, content_type="multipart/form-data")
    outro_id = r.get_json()["relatorio"]["curso_id"]
    p = criar(client_logado, curso_pequeno)
    assert client_logado.put(f"/api/cursos/{outro_id}/planos/{p['id']}", json={"nome": "x", "semestres": []}).status_code == 404
    assert client_logado.get(f"/api/cursos/{outro_id}/planos").get_json()["planos"] == []


def test_apagar_o_usuario_apaga_os_planos_e_o_historico(client_logado, curso_pequeno, usuario, app):
    from planner.extensions import db
    from planner.models import Historico, Plano, Usuario

    criar(client_logado, curso_pequeno)
    client_logado.post(f"/api/cursos/{curso_pequeno['id']}/historico",
                       json={"disciplina_id": curso_pequeno["disc"]["AAA100"], "status": "aprovado"})
    db.session.delete(db.session.get(Usuario, usuario.id))
    db.session.commit()
    assert db.session.query(Plano).count() == 0 and db.session.query(Historico).count() == 0

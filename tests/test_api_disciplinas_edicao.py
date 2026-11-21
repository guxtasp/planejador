"""Editar e criar disciplinas pela tela (sem reimportar o CSV)."""
from planner.domain.edicao_catalogo import ciclo_com_novos_requisitos
from tests.conftest import tornar_publico


def url(curso, fim=""):
    return f"/api/cursos/{curso['id']}/disciplinas{fim}"


def catalogo(client, curso):
    return {d["codigo"]: d for d in client.get(url(curso)).get_json()["disciplinas"]}


# ── domínio ──────────────────────────────────────────────────────────────────
def test_ciclo_detecta_circulo_novo_e_ignora_as_arestas_antigas_da_propria_disciplina():
    # B exige A; dar a A o pré-requisito B fecha o círculo
    assert ciclo_com_novos_requisitos(1, [2], [(2, 1)]) == (1, 2)
    # A exigia B antes (aresta antiga trocada pela nova lista vazia): sem círculo
    assert ciclo_com_novos_requisitos(1, [], [(1, 2), (2, 1)]) == ()
    assert ciclo_com_novos_requisitos(1, [3], [(2, 1)]) == ()


# ── editar ───────────────────────────────────────────────────────────────────
def test_dono_edita_campos_e_o_catalogo_reflete(client_logado, curso_pequeno):
    did = curso_pequeno["disc"]["AAA100"]
    r = client_logado.patch(url(curso_pequeno, f"/{did}"), json={
        "nome": "  Alfa   revisada ", "creditos": 6, "carga_h": "90", "periodo_sugerido": 2,
        "periodicidade": "impar", "tipo": "optativa"})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()["disciplina"]
    assert (d["nome"], d["creditos"], d["carga_h"], d["periodo_sugerido"], d["periodicidade"], d["tipo"]) == \
        ("Alfa revisada", 6, 90, 2, "impar", "optativa")
    assert d["oferta"] == {"valor": "impar", "origem": "cadastrada"}
    assert catalogo(client_logado, curso_pequeno)["AAA100"]["nome"] == "Alfa revisada"


def test_campo_em_branco_vira_desconhecido_nunca_zero(client_logado, curso_pequeno):
    did = curso_pequeno["disc"]["AAA100"]
    d = client_logado.patch(url(curso_pequeno, f"/{did}"), json={"creditos": "", "carga_h": None}).get_json()["disciplina"]
    assert d["creditos"] is None and d["carga_h"] is None


def test_troca_de_codigo_mantem_requisitos_e_recusa_codigo_repetido(client_logado, curso_pequeno):
    a, b = curso_pequeno["disc"]["AAA100"], curso_pequeno["disc"]["BBB100"]
    assert client_logado.patch(url(curso_pequeno, f"/{a}"), json={"codigo": "AAA 101"}).status_code == 200
    cat = catalogo(client_logado, curso_pequeno)
    assert [r["codigo"] for r in cat["BBB100"]["requisitos"]] == ["AAA101"]
    r = client_logado.patch(url(curso_pequeno, f"/{b}"), json={"codigo": "aaa101"})
    assert r.status_code == 409 and r.get_json()["detalhes"]["campo"] == "codigo"


def test_requisitos_substituem_a_lista_e_ciclo_e_recusado(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    r = client_logado.patch(url(curso_pequeno, f"/{d['CCC100']}"), json={"requisitos": [
        {"id": d["AAA100"], "tipo": "pre"}, {"id": d["BBB100"], "tipo": "co"}, {"id": d["AAA100"], "tipo": "pre"}]})
    assert r.status_code == 200, r.get_json()
    assert sorted((x["codigo"], x["tipo"]) for x in r.get_json()["disciplina"]["requisitos"]) == \
        [("AAA100", "pre"), ("BBB100", "co")]
    # BBB100 exige AAA100; AAA100 exigir BBB100 fecharia o círculo
    r = client_logado.patch(url(curso_pequeno, f"/{d['AAA100']}"), json={"requisitos": [{"id": d["BBB100"], "tipo": "pre"}]})
    assert r.status_code == 422 and "círculo" in r.get_json()["erro"]
    r = client_logado.patch(url(curso_pequeno, f"/{d['AAA100']}"), json={"requisitos": [{"id": d["AAA100"], "tipo": "pre"}]})
    assert r.status_code == 422 and r.get_json()["detalhes"]["campo"] == "requisitos"


def test_erros_apontam_o_campo(client_logado, curso_pequeno):
    did = curso_pequeno["disc"]["AAA100"]
    for corpo, campo in (({"nome": "  "}, "nome"), ({"creditos": -1}, "creditos"),
                         ({"periodicidade": "anual"}, "periodicidade"), ({"tipo": "x"}, "tipo"),
                         ({"requisitos": [{"id": 99999, "tipo": "pre"}]}, "requisitos")):
        r = client_logado.patch(url(curso_pequeno, f"/{did}"), json=corpo)
        assert r.status_code == 422 and r.get_json()["detalhes"]["campo"] == campo, corpo


# ── criar ────────────────────────────────────────────────────────────────────
def test_dono_cria_disciplina_com_requisito(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    r = client_logado.post(url(curso_pequeno), json={"codigo": "DDD100", "nome": "Delta", "creditos": 4,
                                                     "requisitos": [{"id": d["BBB100"], "tipo": "pre"}]})
    assert r.status_code == 201, r.get_json()
    nova = r.get_json()["disciplina"]
    assert nova["tipo"] == "obrigatoria" and nova["carga_h"] is None and nova["requisitos"][0]["codigo"] == "BBB100"
    assert "DDD100" in catalogo(client_logado, curso_pequeno)
    assert client_logado.post(url(curso_pequeno), json={"nome": "Sem código"}).get_json()["detalhes"]["campo"] == "codigo"


# ── acesso ───────────────────────────────────────────────────────────────────
def test_so_o_dono_edita(client, client_outro, curso_pequeno):
    did = curso_pequeno["disc"]["AAA100"]
    assert client.patch(url(curso_pequeno, f"/{did}"), json={"nome": "X"}).status_code == 401
    assert client_outro.patch(url(curso_pequeno, f"/{did}"), json={"nome": "X"}).status_code == 404
    tornar_publico(curso_pequeno["id"])
    assert client_outro.patch(url(curso_pequeno, f"/{did}"), json={"nome": "X"}).status_code == 403
    assert client_outro.post(url(curso_pequeno), json={"codigo": "Z1", "nome": "Z"}).status_code == 403
    assert client_outro.get(url(curso_pequeno)).get_json()["pode_editar_catalogo"] is False


def test_disciplina_de_outro_curso_da_404(client_logado, curso_pequeno):
    assert client_logado.patch(url(curso_pequeno, "/999999"), json={"nome": "X"}).status_code == 404

"""Etapa 5B-2 — histórico escolar e painel do aluno (via HTTP)."""
from tests.conftest import tornar_publico


def url(curso, sufixo=""):
    return f"/api/cursos/{curso['id']}/historico{sufixo}"


def registrar(client, curso, codigo, status="aprovado", **extra):
    r = client.post(url(curso), json={"disciplina_id": curso["disc"][codigo], "status": status, **extra})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["tentativa"]


def painel(client, curso):
    r = client.get(f"/api/cursos/{curso['id']}/painel")
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def situacao(p, curso, codigo):
    return next(d for d in p["disciplinas"] if d["id"] == curso["disc"][codigo])


# ── acesso ───────────────────────────────────────────────────────────────────
def test_visitante_recebe_401_em_todas_as_rotas(client, curso_pequeno):
    for metodo, caminho in [("get", url(curso_pequeno)), ("post", url(curso_pequeno)),
                            ("put", url(curso_pequeno, "/1")), ("delete", url(curso_pequeno, "/1")),
                            ("get", f"/api/cursos/{curso_pequeno['id']}/painel")]:
        r = getattr(client, metodo)(caminho, json={})
        assert r.status_code == 401, (metodo, caminho)


def test_historico_comeca_vazio(client_logado, curso_pequeno):
    assert client_logado.get(url(curso_pequeno)).get_json() == {"ok": True, "historico": []}


# ── CRUD ─────────────────────────────────────────────────────────────────────
def test_registrar_devolve_a_tentativa_com_dados_da_disciplina(client_logado, curso_pequeno):
    t = registrar(client_logado, curso_pequeno, "AAA100", periodo_letivo="2025.2", nota=8.5)
    assert t["codigo"] == "AAA100" and t["nome"] == "Alfa" and t["creditos"] == 4
    assert t["periodo_letivo"] == "2025/2" and t["nota"] == 8.5 and t["status"] == "aprovado"


def test_varias_tentativas_na_mesma_disciplina_se_acumulam(client_logado, curso_pequeno):
    registrar(client_logado, curso_pequeno, "AAA100", "reprovado", periodo_letivo="2025/1")
    registrar(client_logado, curso_pequeno, "AAA100", "aprovado", periodo_letivo="2025/2")
    lista = client_logado.get(url(curso_pequeno)).get_json()["historico"]
    assert [t["status"] for t in lista] == ["reprovado", "aprovado"]


def test_editar_muda_status_periodo_e_nota(client_logado, curso_pequeno):
    t = registrar(client_logado, curso_pequeno, "AAA100", "cursando", periodo_letivo="2026/1")
    r = client_logado.put(url(curso_pequeno, f"/{t['id']}"), json={"status": "aprovado", "periodo_letivo": "2026/1", "nota": 9})
    assert r.status_code == 200
    assert r.get_json()["tentativa"]["status"] == "aprovado" and r.get_json()["tentativa"]["nota"] == 9


def test_remover_apaga_a_tentativa(client_logado, curso_pequeno):
    t = registrar(client_logado, curso_pequeno, "AAA100")
    assert client_logado.delete(url(curso_pequeno, f"/{t['id']}")).status_code == 200
    assert client_logado.get(url(curso_pequeno)).get_json()["historico"] == []
    assert client_logado.delete(url(curso_pequeno, f"/{t['id']}")).status_code == 404


def test_dados_invalidos_dao_400_sem_gravar(client_logado, curso_pequeno):
    for corpo in [{"status": "aprovado"}, {"disciplina_id": curso_pequeno["disc"]["AAA100"], "status": "xis"},
                  {"disciplina_id": curso_pequeno["disc"]["AAA100"], "status": "aprovado", "nota": 500},
                  {"disciplina_id": curso_pequeno["disc"]["AAA100"], "status": "aprovado", "periodo_letivo": "2026/7"}]:
        assert client_logado.post(url(curso_pequeno), json=corpo).status_code == 400
    assert client_logado.post(url(curso_pequeno), data="não é json", content_type="text/plain").status_code == 400
    assert client_logado.get(url(curso_pequeno)).get_json()["historico"] == []


def test_disciplina_inexistente_ou_de_outro_curso_da_404(client_logado, curso_pequeno):
    assert client_logado.post(url(curso_pequeno), json={"disciplina_id": 99999, "status": "aprovado"}).status_code == 404


def test_requisicao_de_outro_site_e_barrada(client_logado, curso_pequeno):
    r = client_logado.post(url(curso_pequeno), json={"disciplina_id": curso_pequeno["disc"]["AAA100"], "status": "aprovado"},
                           headers={"Origin": "https://malicioso.example", "Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


# ── isolamento entre usuários ────────────────────────────────────────────────
def test_cada_usuario_ve_so_o_proprio_historico_no_mesmo_curso(client_logado, client_outro, curso_pequeno):
    tornar_publico(curso_pequeno["id"])
    mine = registrar(client_logado, curso_pequeno, "AAA100")
    assert client_outro.get(url(curso_pequeno)).get_json()["historico"] == []
    assert situacao(painel(client_outro, curso_pequeno), curso_pequeno, "AAA100")["situacao"] == "elegivel"
    assert situacao(painel(client_logado, curso_pequeno), curso_pequeno, "AAA100")["situacao"] == "concluida"
    # a outra conta não consegue editar nem apagar a tentativa alheia (mesmo 404 de inexistente)
    assert client_outro.put(url(curso_pequeno, f"/{mine['id']}"), json={"status": "reprovado"}).status_code == 404
    assert client_outro.delete(url(curso_pequeno, f"/{mine['id']}")).status_code == 404
    assert client_logado.get(url(curso_pequeno)).get_json()["historico"][0]["status"] == "aprovado"


def test_curso_privado_de_outra_pessoa_da_404_no_historico_e_no_painel(client_outro, curso_pequeno):
    assert client_outro.get(url(curso_pequeno)).status_code == 404
    assert client_outro.post(url(curso_pequeno), json={"disciplina_id": curso_pequeno["disc"]["AAA100"], "status": "aprovado"}).status_code == 404
    assert client_outro.get(f"/api/cursos/{curso_pequeno['id']}/painel").status_code == 404


# ── painel ───────────────────────────────────────────────────────────────────
def test_painel_sem_historico_mostra_elegiveis_e_bloqueadas(client_logado, curso_pequeno):
    p = painel(client_logado, curso_pequeno)
    assert situacao(p, curso_pequeno, "AAA100")["situacao"] == "elegivel"
    beta = situacao(p, curso_pequeno, "BBB100")
    assert beta["situacao"] == "bloqueada"
    assert beta["pendencias"][0]["alternativas"][0]["codigo"] == "AAA100"
    assert p["progresso"]["percentual"] == 0.0 and p["previsao"]["formatura"] is None


def test_aprovacao_libera_a_proxima_e_atualiza_progresso_e_previsao(client_logado, curso_pequeno):
    registrar(client_logado, curso_pequeno, "AAA100", periodo_letivo="2025/1")
    p = painel(client_logado, curso_pequeno)
    assert situacao(p, curso_pequeno, "AAA100")["situacao"] == "concluida"
    assert situacao(p, curso_pequeno, "BBB100")["situacao"] == "elegivel"
    assert p["progresso"]["percentual"] == 40.0 and p["progresso"]["creditos_restantes"] == 6
    # média do aluno = 4 créditos/período; restam 6 → 2 períodos a partir de 2025/2 → termina em 2026/1
    assert p["previsao"]["origem_media"] == "aluno" and p["previsao"]["media_creditos_periodo"] == 4.0
    assert p["previsao"]["formatura"] == "2026/1"


def test_reprovar_depois_aprovar_nao_apaga_a_aprovacao(client_logado, curso_pequeno):
    registrar(client_logado, curso_pequeno, "AAA100", "aprovado", periodo_letivo="2025/1")
    registrar(client_logado, curso_pequeno, "AAA100", "reprovado", periodo_letivo="2025/2")   # inserido depois
    assert situacao(painel(client_logado, curso_pequeno), curso_pequeno, "AAA100")["situacao"] == "concluida"


def test_cursando_libera_correquisito_mas_nao_prerequisito(client_logado, curso_pequeno):
    registrar(client_logado, curso_pequeno, "AAA100", "cursando", periodo_letivo="2026/1")
    p = painel(client_logado, curso_pequeno)
    assert situacao(p, curso_pequeno, "AAA100")["situacao"] == "cursando"
    assert situacao(p, curso_pequeno, "BBB100")["situacao"] == "bloqueada"


def test_remover_a_tentativa_volta_a_bloquear(client_logado, curso_pequeno):
    t = registrar(client_logado, curso_pequeno, "AAA100")
    client_logado.delete(url(curso_pequeno, f"/{t['id']}"))
    assert situacao(painel(client_logado, curso_pequeno), curso_pequeno, "BBB100")["situacao"] == "bloqueada"


# ── a análise do plano passa a considerar o histórico ────────────────────────
def test_analise_do_plano_considera_o_historico_do_usuario(client_logado, curso_pequeno):
    corpo = {"semestres": [{"periodo_letivo": None, "itens": [{"disciplina_id": curso_pequeno["disc"]["BBB100"], "turma_id": None}]}]}
    url_analise = f"/api/cursos/{curso_pequeno['id']}/plano/analisar"
    antes = client_logado.post(url_analise, json=corpo).get_json()
    assert antes["total_problemas"] == 1 and antes["semestres"][0]["pendencias"][0]["tipo"] == "pre"
    registrar(client_logado, curso_pequeno, "AAA100")
    depois = client_logado.post(url_analise, json=corpo).get_json()
    assert depois["total_problemas"] == 0

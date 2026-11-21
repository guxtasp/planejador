"""Peças 3/4 (parte C) — rotas do simulador, da sugestão e da edição da oferta (via HTTP)."""
from tests.conftest import tornar_publico


def url(curso, fim):
    return f"/api/cursos/{curso['id']}/{fim}"


def plano_simples(curso, periodo1="2027/1", periodo2="2027/2"):
    d = curso["disc"]
    return {"semestres": [
        {"periodo_letivo": periodo1, "itens": [{"disciplina_id": d["AAA100"]}, {"disciplina_id": d["CCC100"]}]},
        {"periodo_letivo": periodo2, "itens": [{"disciplina_id": d["BBB100"]}]},
    ]}


def definir_oferta(client, curso, **por_codigo):
    itens = [{"disciplina_id": curso["disc"][c], "periodicidade": v} for c, v in por_codigo.items()]
    return client.patch(url(curso, "disciplinas/periodicidade"), json={"itens": itens})


# ── acesso ───────────────────────────────────────────────────────────────────
def test_visitante_recebe_401_nas_tres_rotas(client, curso_pequeno):
    assert client.post(url(curso_pequeno, "simulacao"), json={}).status_code == 401
    assert client.post(url(curso_pequeno, "simulacao/sugerir"), json={}).status_code == 401
    assert client.patch(url(curso_pequeno, "disciplinas/periodicidade"), json={}).status_code == 401


def test_curso_de_outra_pessoa_da_404(client_outro, curso_pequeno):
    assert client_outro.post(url(curso_pequeno, "simulacao"), json=plano_simples(curso_pequeno)).status_code == 404
    assert client_outro.post(url(curso_pequeno, "simulacao/sugerir"), json={}).status_code == 404


# ── simulação ────────────────────────────────────────────────────────────────
def test_plano_vazio_diz_o_que_fazer(client_logado, curso_pequeno):
    r = client_logado.post(url(curso_pequeno, "simulacao"), json={"semestres": [{"periodo_letivo": "2027/1", "itens": []}]})
    assert r.status_code == 422 and "vazio" in r.get_json()["erro"]


def test_sem_periodo_em_lugar_nenhum_pede_o_periodo(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    r = client_logado.post(url(curso_pequeno, "simulacao"), json={"semestres": [{"itens": [{"disciplina_id": d["AAA100"]}]}]})
    assert r.status_code == 422 and "período" in r.get_json()["erro"]


def test_simulacao_devolve_blocos_e_riscos_com_frase_pronta(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="sempre", BBB100="impar", CCC100="sempre")
    r = client_logado.post(url(curso_pequeno, "simulacao"), json=plano_simples(curso_pequeno))   # BBB (ímpar) em 2027/2
    assert r.status_code == 200
    j = r.get_json()
    assert j["periodo_inicial"] == "2027/1" and [s["periodo"] for s in j["semestres"]] == ["2027/1", "2027/2"]
    assert j["veredito"]["nivel"] == "alto"
    fora = next(x for x in j["riscos"] if x["tipo"] == "fora_de_oferta")
    assert fora["gravidade"] == "alta" and fora["mensagem"] and fora["acao"] and "2028/1" in fora["acao"]
    assert {"resumo", "critico", "cenarios", "premissas"} <= set(j)
    assert "cadeia" in j["critico"] and "cadeia_mensagem" in j["critico"]


def test_plano_correto_tem_veredito_ok_ou_medio_e_cenarios(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="sempre", BBB100="sempre", CCC100="sempre")
    j = client_logado.post(url(curso_pequeno, "simulacao"), json=plano_simples(curso_pequeno)).get_json()
    assert j["veredito"]["nivel"] in ("ok", "medio") and j["cenarios"]
    assert all(c["mensagem"] for c in j["cenarios"])


def test_periodo_invalido_no_semestre_da_erro_claro(client_logado, curso_pequeno):
    r = client_logado.post(url(curso_pequeno, "simulacao"), json=plano_simples(curso_pequeno, periodo1="abc"))
    assert r.status_code == 422 and "Semestre 1" in r.get_json()["erro"]


# ── sugestão ─────────────────────────────────────────────────────────────────
def test_sugestao_sem_periodo_e_sem_historico_pede_o_periodo(client_logado, curso_pequeno):
    r = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json={})
    assert r.status_code == 422


def test_sugestao_respeita_prerequisito_e_pode_virar_plano(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="sempre", BBB100="sempre", CCC100="sempre")
    r = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json={"periodo_inicial": "2027/1"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["viavel"] and j["explicacao"]
    pos = {i["disciplina"]["codigo"]: s["posicao"] for s in j["semestres"] for i in s["itens"]}
    assert pos["AAA100"] < pos["BBB100"] and set(pos) == {"AAA100", "BBB100", "CCC100"}
    criado = client_logado.post(f"/api/cursos/{curso_pequeno['id']}/planos", json=j["plano"])    # o plano é "salvável" como está
    assert criado.status_code == 201


def test_sugestao_com_limite_de_creditos_e_extras(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="sempre", BBB100="sempre", CCC100="sempre")
    j = client_logado.post(url(curso_pequeno, "simulacao/sugerir"),
                           json={"periodo_inicial": "2027/1", "max_creditos": 4, "semestres_extras": 1}).get_json()
    assert j["viavel"] and all(s["creditos"] <= 4 for s in j["semestres"])


def test_sugestao_com_parametros_ruins_da_422(client_logado, curso_pequeno):
    for corpo in ({"max_creditos": 0}, {"semestres_extras": 99}, {"periodo_inicial": "x"}, {"optativas": [999999]}):
        assert client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json=corpo).status_code == 422


# ── edição da oferta ─────────────────────────────────────────────────────────
def test_dono_define_a_oferta_e_ela_aparece_no_catalogo(client_logado, curso_pequeno):
    r = definir_oferta(client_logado, curso_pequeno, AAA100="impar", BBB100="par")
    assert r.status_code == 200 and len(r.get_json()["atualizadas"]) == 2
    cat = client_logado.get(url(curso_pequeno, "disciplinas")).get_json()
    assert cat["pode_editar_oferta"] is True
    assert {d["codigo"]: d["periodicidade"] for d in cat["disciplinas"]}["AAA100"] == "impar"


def test_voltar_para_nao_informada_grava_nulo_nunca_sempre(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="par")
    definir_oferta(client_logado, curso_pequeno, AAA100=None)
    cat = client_logado.get(url(curso_pequeno, "disciplinas")).get_json()
    assert {d["codigo"]: d["periodicidade"] for d in cat["disciplinas"]}["AAA100"] is None


def test_valor_invalido_nao_grava_nada(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    r = client_logado.patch(url(curso_pequeno, "disciplinas/periodicidade"), json={"itens": [
        {"disciplina_id": d["AAA100"], "periodicidade": "par"}, {"disciplina_id": d["BBB100"], "periodicidade": "talvez"}]})
    assert r.status_code == 422
    cat = client_logado.get(url(curso_pequeno, "disciplinas")).get_json()
    assert {x["codigo"]: x["periodicidade"] for x in cat["disciplinas"]}["AAA100"] is None


def test_quem_nao_e_dono_nao_edita_mesmo_em_curso_publico(client_outro, curso_pequeno):
    tornar_publico(curso_pequeno["id"])
    r = definir_oferta(client_outro, curso_pequeno, AAA100="par")
    assert r.status_code == 403
    assert client_outro.get(url(curso_pequeno, "disciplinas")).get_json()["pode_editar_oferta"] is False


def test_disciplina_de_outro_curso_da_404(client_logado, curso_pequeno):
    r = client_logado.patch(url(curso_pequeno, "disciplinas/periodicidade"),
                            json={"itens": [{"disciplina_id": 999999, "periodicidade": "par"}]})
    assert r.status_code == 404


# ── Fase 2 ───────────────────────────────────────────────────────────────────
def _registrar(client, curso, codigo, status, periodo):
    r = client.post(url(curso, "historico"), json={"disciplina_id": curso["disc"][codigo], "status": status,
                                                   "periodo_letivo": periodo})
    assert r.status_code == 201, r.get_json()


def test_simulacao_traz_prazo_monte_carlo_e_semana(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="sempre", BBB100="sempre", CCC100="sempre")
    _registrar(client_logado, curso_pequeno, "CCC100", "reprovado", "2026/1")
    corpo = {**plano_simples(curso_pequeno), "preferencias": {"simulacoes": 100, "max_pesadas": 1}}
    j = client_logado.post(url(curso_pequeno, "simulacao"), json=corpo).get_json()
    # duração do curso = 2 semestres; ingresso = 2026/1 (histórico); formatura 2027/2 = 4 semestres
    assert j["prazo"]["origem_ingresso"] == "historico" and j["prazo"]["semestres_usados"] == 4
    assert j["prazo"]["no_prazo_maximo"] is False and any(r["tipo"] == "prazo_maximo" for r in j["riscos"])
    mc = j["monte_carlo"]
    assert mc["n"] == 100 and mc["taxa"]["origem"] == "historico" and mc["mensagem"]
    assert abs(sum(d["pct"] for d in mc["distribuicao"]) + mc["nao_formou_pct"] - 100) < 0.5
    assert j["semestres"][0]["semana"]["resumo"]
    assert [p["codigo"] for p in j["preferencias"]["pesadas"]] == ["CCC100"]          # reprovada = pesada
    assert j["preferencias"]["pesadas"][0]["motivo"] == "reprovada"


def test_preferencia_invalida_volta_422_com_o_campo(client_logado, curso_pequeno):
    corpo = {**plano_simples(curso_pequeno), "preferencias": {"turno": "madrugada"}}
    r = client_logado.post(url(curso_pequeno, "simulacao"), json=corpo)
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "turno"}
    r = client_logado.post(url(curso_pequeno, "simulacao/sugerir"),
                           json={"periodo_inicial": "2027/1", "preferencias": {"pesadas": [999999]}})
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "pesadas"}


def test_sugestao_respeita_trancamento_e_traz_chance_no_prazo(client_logado, curso_pequeno):
    definir_oferta(client_logado, curso_pequeno, AAA100="sempre", BBB100="sempre", CCC100="sempre")
    corpo = {"periodo_inicial": "2027/1", "preferencias": {"periodos_pulados": ["2027/2"], "simulacoes": 100}}
    j = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json=corpo).get_json()
    assert j["viavel"] and "2027/2" not in [s["periodo"] for s in j["semestres"] if s["itens"]]
    assert j["monte_carlo"]["chance_no_prazo_do_plano_pct"] >= 0 and j["prazo"]["mensagem"]
    assert j["preferencias"]["periodos_pulados"] == ["2027/2"]

"""Turma escolhida automaticamente no plano e optativas da rotina (mesmos números na simulação e na sugestão)."""


def url(curso, fim):
    return f"/api/cursos/{curso['id']}/{fim}"


def analisar(client, curso, itens, periodo="2026/1"):
    r = client.post(url(curso, "plano/analisar"), json={"semestres": [{"periodo_letivo": periodo, "itens": itens}]})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["semestres"][0]["marcas"]


def test_analise_sugere_a_turma_da_melhor_combinacao(client_logado, curso_pequeno):
    d, t = curso_pequeno["disc"], curso_pequeno["turmas"]
    m = analisar(client_logado, curso_pequeno, [{"disciplina_id": d["AAA100"]}, {"disciplina_id": d["BBB100"]}])
    # AAA só tem T1 (SEG 8–10); BBB T1 (SEG 9–11) bate com ela: a melhor combinação usa BBB T2
    assert m[str(d["AAA100"])]["turma_sugerida"] == t[("AAA100", "2026/1", "T1")]
    assert m[str(d["BBB100"])]["turma_sugerida"] == t[("BBB100", "2026/1", "T2")]


def test_turma_automatica_nao_prende_e_a_do_aluno_prende(client_logado, curso_pequeno):
    d, t = curso_pequeno["disc"], curso_pequeno["turmas"]
    bbb_t1 = t[("BBB100", "2026/1", "T1")]
    # escolhida pelo aluno: fica, e o choque aparece
    m = analisar(client_logado, curso_pequeno, [{"disciplina_id": d["AAA100"]},
                                                {"disciplina_id": d["BBB100"], "turma_id": bbb_t1}])
    assert m[str(d["BBB100"])]["turma_sugerida"] == bbb_t1 and m[str(d["BBB100"])]["choques"]
    # escolhida pelo Rumo: a melhor combinação troca para a T2, sem choque
    m = analisar(client_logado, curso_pequeno, [{"disciplina_id": d["AAA100"]},
                                                {"disciplina_id": d["BBB100"], "turma_id": bbb_t1, "turma_auto": True}])
    assert m[str(d["BBB100"])]["turma_sugerida"] == t[("BBB100", "2026/1", "T2")] and not m[str(d["BBB100"])]["choques"]


def test_turma_auto_e_guardada_no_plano(client_logado, curso_pequeno):
    d, t = curso_pequeno["disc"], curso_pequeno["turmas"]
    corpo = {"nome": "P", "semestres": [{"rotulo": "S1", "periodo_letivo": "2026/1", "itens": [
        {"disciplina_id": d["AAA100"], "turma_id": t[("AAA100", "2026/1", "T1")], "turma_auto": True},
        {"disciplina_id": d["CCC100"], "turma_id": t[("CCC100", "2026/1", "T1")]}]}]}
    r = client_logado.post(url(curso_pequeno, "planos"), json=corpo)
    assert r.status_code == 201, r.get_json()
    itens = r.get_json()["plano"]["semestres"][0]["itens"]
    assert itens[0].get("turma_auto") is True and "turma_auto" not in itens[1]


def test_optativas_da_rotina_valem_na_simulacao(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    client_logado.put(url(curso_pequeno, "preferencias"), json={"optativas_faltando": 8})
    plano = {"semestres": [{"periodo_letivo": "2027/1", "itens": [{"disciplina_id": d["AAA100"]}]}],
             "preferencias": None}
    plano.pop("preferencias")
    j = client_logado.post(url(curso_pequeno, "simulacao"), json=plano).get_json()
    o = j["resumo"]["optativas"]
    assert o["origem"] == "informado" and o["faltam"] == 8 and "Minha rotina" not in o["mensagem"]
    assert any(r["tipo"] == "faltam_optativas" for r in j["riscos"])


def test_optativa_feita_fora_do_historico_invalida(client_logado, curso_pequeno):
    r = client_logado.put(url(curso_pequeno, "preferencias"), json={"optativas_feitas": ["x"]})
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "optativas_feitas"}


# ── disciplina em período específico ─────────────────────────────────────────
def test_fixacao_guardada_respeitada_na_sugestao_e_avisada_no_simulador(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    for c in ("AAA100", "BBB100", "CCC100"):
        client_logado.patch(url(curso_pequeno, "disciplinas/periodicidade"),
                            json={"itens": [{"disciplina_id": d[c], "periodicidade": "sempre"}]})
    r = client_logado.put(url(curso_pequeno, "preferencias"), json={"fixas": [{"disciplina_id": d["CCC100"], "periodo": "2028.1"}]})
    assert r.status_code == 200 and r.get_json()["preferencias"]["fixas"] == [{"disciplina_id": d["CCC100"], "periodo": "2028/1"}]
    sug = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json={"periodo_inicial": "2027/1"}).get_json()
    onde = {i["disciplina"]["codigo"]: s["periodo"] for s in sug["semestres"] for i in s["itens"]}
    assert onde["CCC100"] == "2028/1" and sug["fixas_mensagens"][0]["ok"]
    plano = {"semestres": [{"periodo_letivo": "2027/1", "itens": [{"disciplina_id": d["AAA100"]}, {"disciplina_id": d["CCC100"]}]}]}
    sim = client_logado.post(url(curso_pequeno, "simulacao"), json=plano).get_json()
    risco = next(x for x in sim["riscos"] if x["tipo"] == "fixa_fora_do_periodo")
    assert "2028/1" in risco["mensagem"] and "2027/1" in risco["mensagem"]


def test_fixacao_de_disciplina_de_outro_curso_e_recusada(client_logado, curso_pequeno):
    r = client_logado.put(url(curso_pequeno, "preferencias"), json={"fixas": [{"disciplina_id": 999999, "periodo": "2028/1"}]})
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "fixas"}


def test_sugestao_recebe_o_plano_atual(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    plano = {"semestres": [{"periodo_letivo": "2027/1", "itens": [{"disciplina_id": d["AAA100"]}]},
                           {"periodo_letivo": "2027/2", "itens": [{"disciplina_id": d["BBB100"]}, {"disciplina_id": d["CCC100"]}]}]}
    j = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json={"periodo_inicial": "2027/1", "plano_atual": plano}).get_json()
    assert j["partiu_do_plano"] is True and j["metricas"]["n_semestres"] <= 2


def test_sugestao_diz_quanto_os_pedidos_custam(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    for c in ("AAA100", "BBB100", "CCC100"):
        client_logado.patch(url(curso_pequeno, "disciplinas/periodicidade"),
                            json={"itens": [{"disciplina_id": d[c], "periodicidade": "sempre"}]})
    client_logado.put(url(curso_pequeno, "preferencias"), json={"fixas": [{"disciplina_id": d["BBB100"], "periodo": "2029/1"}]})
    j = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json={"periodo_inicial": "2027/1"}).get_json()
    assert "BBB100 em 2029/1" in j["pedidos_mensagem"] and "sem eles seria 2027/2" in j["pedidos_mensagem"]

"""Fase 3 — o que o servidor entrega para a tela: etapas, selo do ótimo, indicadores e avisos."""
from planner.domain.entidades import Disciplina, Requisito
from planner.domain.otimizador import ParametrosOtimizacao, otimizar_plano
from planner.services.simulacao_json import (indicadores, selo_otimo, serializar_sugestao)


def _sug(**kw):
    cat = {i: Disciplina(i, f"D{i}", f"Disc {i}", 4, "obrigatoria", None, "sempre") for i in (1, 2, 3)}
    req = {1: [], 2: [Requisito(2, 1)], 3: [Requisito(3, 2)]}
    return cat, otimizar_plano(cat, req, {}, set(), "2027/1", ParametrosOtimizacao(**kw))


def test_sugestao_traz_tempo_de_cada_etapa_e_selo_compreensivel():
    cat, res = _sug()
    assert set(res.tempos_ms) == {"grafo", "guloso", "recozimento", "turmas"}
    j = serializar_sugestao(res, cat, "S")
    assert [e["chave"] for e in j["etapas"]] == ["grafo", "guloso", "recozimento", "turmas"]
    assert j["selo"]["tipo"] == "otimo" and "Não existe plano com menos de 3 semestres" in j["selo"]["texto"]


def test_selo_melhor_encontrado_quando_ha_folga():
    _cat, res = _sug(semestres_extras=1)
    assert selo_otimo(res)["tipo"] == "melhor"


def test_indicadores_tem_as_mesmas_chaves_e_direcao():
    ind = indicadores("2029/2", 18.5, 24, 0, 1.5, "2030/2", 40)
    assert [x["chave"] for x in ind] == ["formatura", "p50", "chance", "carga_media", "carga_maxima", "choques", "dias_livres"]
    assert {x["chave"]: x["melhor"] for x in ind}["chance"] == "maior"
    assert {x["chave"]: x["texto"] for x in ind}["carga_media"] == "18,5 cr"
    assert indicadores(None, None, None, None, None, None, None)[0]["texto"] == "–"     # desconhecido ≠ 0


def url(curso, fim):
    return f"/api/cursos/{curso['id']}/{fim}"


def test_simulacao_e_sugestao_devolvem_indicadores_comparaveis(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    plano = {"semestres": [{"periodo_letivo": "2027/1", "itens": [{"disciplina_id": d["AAA100"]}]},
                           {"periodo_letivo": "2027/2", "itens": [{"disciplina_id": d["BBB100"]}]}],
             "preferencias": {"simulacoes": 50}}
    sim = client_logado.post(url(curso_pequeno, "simulacao"), json=plano).get_json()
    sug = client_logado.post(url(curso_pequeno, "simulacao/sugerir"),
                             json={"periodo_inicial": "2027/1", "preferencias": {"simulacoes": 50}}).get_json()
    assert [x["chave"] for x in sim["indicadores"]] == [x["chave"] for x in sug["indicadores"]]


def test_analise_conta_os_choques_do_semestre(client_logado, curso_pequeno):
    d, t = curso_pequeno["disc"], curso_pequeno["turmas"]
    corpo = {"semestres": [{"periodo_letivo": "2026/1", "itens": [
        {"disciplina_id": d["AAA100"], "turma_id": t[("AAA100", "2026/1", "T1")]},
        {"disciplina_id": d["BBB100"], "turma_id": t[("BBB100", "2026/1", "T1")]}]}]}
    a = client_logado.post(url(curso_pequeno, "plano/analisar"), json=corpo).get_json()["semestres"][0]
    assert a["n_choques"] == 1 and a["choques_texto"] == "1 choque"


def test_grupo_impossivel_e_avisado_ao_salvar(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    r = client_logado.put(url(curso_pequeno, "preferencias"),
                          json={"juntas": [{"disciplinas": [d["AAA100"], d["BBB100"]]}]})   # BBB exige AAA antes
    assert r.status_code == 200 and "BBB100 exige AAA100 antes" in r.get_json()["avisos_juntas"][0]

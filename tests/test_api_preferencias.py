"""Preferências guardadas por aluno + curso e as marcas (choque/disponibilidade) no Planejamento."""


def url(curso, fim):
    return f"/api/cursos/{curso['id']}/{fim}"


def salvar(client, curso, **prefs):
    return client.put(url(curso, "preferencias"), json=prefs)


def analisar(client, curso, *itens, periodo="2026/1"):
    d = curso["disc"]
    corpo = {"semestres": [{"periodo_letivo": periodo, "itens": [
        {"disciplina_id": d[c], **({"turma_id": curso["turmas"][(c, periodo, t)]} if t else {})} for c, t in itens]}]}
    r = client.post(url(curso, "plano/analisar"), json=corpo)
    assert r.status_code == 200, r.get_json()
    return r.get_json()["semestres"][0]["marcas"]


def tipos(marcas, curso, codigo):
    return [t["tipo"] for t in marcas[str(curso["disc"][codigo])]["tags"]]


def test_comeca_vazio_guarda_normalizado_e_devolve(client_logado, curso_pequeno):
    assert client_logado.get(url(curso_pequeno, "preferencias")).get_json()["preferencias"] == {}
    r = salvar(client_logado, curso_pequeno, indisponiveis=[{"dia": "ter", "inicio": "18:00", "fim": "23:00"}],
               periodos_pulados=["2028.2"], juntas=[{"disciplinas": [curso_pequeno["disc"]["AAA100"], curso_pequeno["disc"]["CCC100"]]}])
    assert r.status_code == 200
    p = client_logado.get(url(curso_pequeno, "preferencias")).get_json()["preferencias"]
    assert p["indisponiveis"] == [{"dia": "TER", "inicio": "18:00", "fim": "23:00"}]
    assert p["periodos_pulados"] == ["2028/2"] and p["juntas"][0]["regra"] == "obrigatoria"


def test_preferencia_invalida_ou_de_outro_curso(client_logado, client_outro, curso_pequeno):
    r = salvar(client_logado, curso_pequeno, turno="madrugada")
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "turno"}
    r = salvar(client_logado, curso_pequeno, pesadas=[999999])
    assert r.status_code == 422 and r.get_json()["detalhes"] == {"campo": "pesadas"}
    assert client_outro.get(url(curso_pequeno, "preferencias")).status_code == 404


def test_sem_preferencias_no_pedido_a_sugestao_usa_as_guardadas(client_logado, curso_pequeno):
    salvar(client_logado, curso_pequeno, periodos_pulados=["2027/2"])
    j = client_logado.post(url(curso_pequeno, "simulacao/sugerir"), json={"periodo_inicial": "2027/1"}).get_json()
    assert j["preferencias"]["periodos_pulados"] == ["2027/2"]


def test_planejamento_marca_choque_e_disponibilidade_como_o_simulador(client_logado, curso_pequeno):
    # sem preferências: BBB tem a turma T2 (TER à noite), então AAA (SEG 8–10) e BBB não colidem
    m = analisar(client_logado, curso_pequeno, ("AAA100", None), ("BBB100", None))
    assert tipos(m, curso_pequeno, "AAA100") == [] and tipos(m, curso_pequeno, "BBB100") == []
    # trabalha TER à noite: a T2 sai (regra dura) e sobra a T1 (SEG 9–11), que bate com AAA
    salvar(client_logado, curso_pequeno, indisponiveis=[{"dia": "TER", "inicio": "18:00", "fim": "23:00"}])
    m = analisar(client_logado, curso_pequeno, ("AAA100", None), ("BBB100", None))
    tag = m[str(curso_pequeno["disc"]["AAA100"])]["tags"][0]
    assert tag["tipo"] == "choque" and tag["texto"] == "Choque com BBB100 (Seg 9–10)"


def test_turma_escolhida_que_bate_sugere_a_que_cabe_e_unica_turma_nao_cabe(client_logado, curso_pequeno):
    salvar(client_logado, curso_pequeno, indisponiveis=[{"dia": "TER", "inicio": "18:00", "fim": "23:00"},
                                                        {"dia": "SAB", "inicio": "07:00", "fim": "12:00"}])
    m = analisar(client_logado, curso_pequeno, ("BBB100", "T2"), ("CCC100", None))
    bbb = m[str(curso_pequeno["disc"]["BBB100"])]
    assert "disponibilidade" in [t["tipo"] for t in bbb["tags"]]
    assert bbb["turma_que_cabe"] == curso_pequeno["turmas"][("BBB100", "2026/1", "T1")]
    assert "nao_cabe" in tipos(m, curso_pequeno, "CCC100")


def test_sem_horario_avisa_que_a_disponibilidade_nao_foi_checada(client_logado, curso_pequeno):
    salvar(client_logado, curso_pequeno, indisponiveis=[{"dia": "SEG", "inicio": "07:00", "fim": "12:00"}])
    m = analisar(client_logado, curso_pequeno, ("CCC100", None), periodo="2030/2")    # período par: sem quadro nem projeção
    tag = m[str(curso_pequeno["disc"]["CCC100"])]["tags"][0]
    assert tag["tipo"] == "sem_horario" and "disponibilidade não verificados" in tag["texto"]


def test_catalogo_traz_a_oferta_efetiva_para_o_selo(client_logado, curso_pequeno):
    cat = client_logado.get(url(curso_pequeno, "disciplinas")).get_json()
    assert {d["codigo"]: d["oferta"] for d in cat["disciplinas"]}["AAA100"] == {"valor": "sempre", "origem": "desconhecida"}


# ── optativas que cabem ──────────────────────────────────────────────────────
from datetime import time

from planner.domain.entidades import Disciplina, Encontro, Requisito, Turma
from planner.domain.optativas import optativas_que_cabem
from planner.domain.semana import BlocoIndisponivel, PreferenciasSemana


def _op(i, per="sempre"):
    return Disciplina(i, f"OP{i}", f"Opt {i}", 4, "optativa", None, per)


def test_optativas_que_cabem_filtra_oferta_requisito_e_disponibilidade():
    cat = {1: Disciplina(1, "OB1", "Obrig", 4, "obrigatoria", None, "sempre"), 2: _op(2), 3: _op(3, "par"),
           4: _op(4), 5: _op(5), 6: _op(6)}
    reqs = {4: [Requisito(4, 1)], 5: []}
    turmas = {5: [Turma(50, 5, (Encontro("SEG", time(8), time(10)),), "2027/1", "T1")],
              6: [Turma(60, 6, (Encontro("TER", time(19), time(21)),), "2027/1", "T1")]}
    semana = PreferenciasSemana(indisponiveis=(BlocoIndisponivel("SEG", time(7), time(12)),))
    plano = [("2027/1", {1}), ("2027/2", set())]
    lista = optativas_que_cabem(plano, 0, cat, reqs, turmas, set(), semana)
    # 3 só abre em par; 4 exige 1 (no mesmo semestre ainda não vale); 5 só tem turma no horário indisponível
    assert [o.disciplina_id for o in lista] == [6, 2]
    assert lista[0].disponibilidade == "cabe" and lista[1].disponibilidade == "sem_horario"
    # no 2º semestre, 1 já foi feita antes: 4 passa a caber; 3 abre em período par
    assert {3, 4} <= {o.disciplina_id for o in optativas_que_cabem(plano, 1, cat, reqs, turmas, set(), semana)}


def test_rota_de_optativas_que_cabem(client_logado, curso_pequeno):
    d = curso_pequeno["disc"]
    r = client_logado.post(url(curso_pequeno, "simulacao/optativas"), json={
        "semestres": [{"periodo_letivo": "2027/1", "itens": [{"disciplina_id": d["AAA100"]}]}], "posicao": 1})
    assert r.status_code == 200 and r.get_json()["optativas"] == [] and "Nenhuma optativa" in r.get_json()["mensagem"]


def test_planejamento_projeta_o_quadro_como_o_simulador(client_logado, curso_pequeno):
    # 2030/1 não tem quadro: usa o de 2026/1 (mesma paridade), e o choque AAA × BBB vira "possível"
    salvar(client_logado, curso_pequeno, indisponiveis=[{"dia": "TER", "inicio": "18:00", "fim": "23:00"}])
    m = analisar(client_logado, curso_pequeno, ("AAA100", None), ("BBB100", None), periodo="2030/1")
    assert tipos(m, curso_pequeno, "AAA100") == ["possivel_choque"]

"""Formatura pelo PLANO no Painel (além da previsão pelo ritmo do histórico)."""
from planner.domain.entidades import Disciplina
from planner.domain.painel import (SEM_DATA_CREDITOS, SEM_DATA_OBRIGATORIAS, SEM_DATA_PLANO_VAZIO,
                                   formatura_pelo_plano)


def d(i, tipo="obrigatoria", cr=4):
    return Disciplina(i, f"D{i}", f"Disc {i}", cr, tipo)


CAT = {1: d(1), 2: d(2), 3: d(3, "optativa"), 4: d(4, "optativa")}


def fp(semestres, concluidas=(), obrig=8, opt=8, teto=8, inicio="2027/1"):
    return formatura_pelo_plano(semestres, CAT, concluidas, obrig, opt, teto, inicio)


def test_plano_que_fecha_tudo_da_a_data():
    r = fp([("2027/1", [1, 3]), (None, [2, 4])])
    assert r.formatura == "2027/2" and r.optativas_faltam == 0


def test_faltam_optativas_diz_a_data_com_elas_respeitando_o_teto():
    r = fp([("2027/1", [1]), (None, [2])])          # 4 livres por semestre, 8 de optativas faltando
    assert r.formatura is None and r.so_obrigatorias == "2027/2"
    assert r.optativas_faltam == 8 and r.formatura_com_optativas == "2027/2"     # cabem 4 + 4
    r = fp([("2027/1", [1]), (None, [2])], teto=4)  # sem espaço: 2 semestres a mais
    assert r.formatura_com_optativas == "2028/2"


def test_optativa_do_historico_conta_como_cumprida():
    r = fp([("2027/1", [1, 3]), (None, [2])], concluidas={4})
    assert r.optativas_cumpridas == 4 and r.optativas_faltam == 0 and r.formatura == "2027/2"


def test_sem_creditos_exigidos_nao_afirma_data():
    # o curso não informa e o catálogo não tem créditos: não há base para a data
    sem_cred = {1: d(1, cr=None), 3: d(3, "optativa")}
    r = formatura_pelo_plano([("2027/1", [1, 3])], sem_cred, (), None, 4, 8, "2027/1")
    assert r.formatura is None and r.sem_data == SEM_DATA_CREDITOS and r.periodo_fim == "2027/1"
    # sem o total informado, vale a soma das obrigatórias do catálogo (mesma regra do progresso)
    assert fp([("2027/1", [1, 2, 3, 4])], obrig=None).formatura == "2027/1"


def test_obrigatoria_fora_do_plano_e_plano_vazio():
    assert fp([("2027/1", [1])]).sem_data == SEM_DATA_OBRIGATORIAS
    assert fp([("2027/1", [])]).sem_data == SEM_DATA_PLANO_VAZIO


def test_painel_traz_a_data_pelo_plano(client_logado, curso_pequeno):
    di = curso_pequeno["disc"]
    r = client_logado.post(f"/api/cursos/{curso_pequeno['id']}/planos", json={"nome": "Meu", "semestres": [
        {"rotulo": "S1", "periodo_letivo": "2027/1", "itens": [{"disciplina_id": di["AAA100"]}, {"disciplina_id": di["CCC100"]}]},
        {"rotulo": "S2", "periodo_letivo": "2027/2", "itens": [{"disciplina_id": di["BBB100"]}]}]})
    assert r.status_code == 201, r.get_json()
    pp = client_logado.get(f"/api/cursos/{curso_pequeno['id']}/painel").get_json()["previsao_plano"]
    assert pp["plano"]["nome"] == "Meu" and pp["so_obrigatorias"] == "2027/2"
    assert "optativas" in pp["mensagem"]          # o curso pequeno não informa optativas exigidas
